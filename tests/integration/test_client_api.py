import asyncio
import os
import uuid

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nevis.application.authorization import authorize
from nevis.application.clients import create_client
from nevis.domain.authorization import AuthorizationAction
from nevis.domain.clients import ClientConflict, ClientCreationOutcome, CreateClientCommand
from nevis.domain.search import MatchBand
from nevis.infrastructure.models import Advisor, AdvisorTenantMembership, AuditEvent, Client, Tenant
from nevis.infrastructure.repositories import (
    search_exact_email_clients,
    search_exact_name_clients,
    search_lexical_clients,
)
from nevis.main import create_app
from nevis.settings import Settings


def client_command(key: str, request_id: str) -> CreateClientCommand:
    return CreateClientCommand(
        first_name="Race",
        last_name="Fixture",
        email="race@example.com",
        description=None,
        social_links=(),
        source_type="test",
        source_reference="race",
        idempotency_key=key,
        request_id=request_id,
    )


@pytest.mark.asyncio
async def test_client_lookup_indexes_support_tenant_first_plans(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
) -> None:
    async with database_session_factory() as session:
        indexes = (
            (
                await session.execute(
                    text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE tablename IN ('clients', 'documents')"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert "uq_clients_tenant_normalized_email" in indexes
        assert "ix_clients_tenant_id_id" in indexes
        assert "ix_clients_search_vector" in indexes
        assert "ix_clients_tenant_normalized_full_name" in indexes
        assert "ix_documents_tenant_client" in indexes
        await session.execute(
            text(
                "INSERT INTO clients "
                "(id, tenant_id, first_name, last_name, email, normalized_email, "
                "description, social_links, source_type, source_reference, "
                "creation_authorization_decision_id) "
                "SELECT ('00000000-0000-0000-0000-' || lpad(n::text, 12, '0'))::uuid, "
                ":tenant, 'Load', n::text, 'load-' || n || '@example.com', "
                "'load-' || n || '@example.com', 'balanced portfolio planning', "
                "'[]'::jsonb, 'volume-fixture', 'volume-' || n, :decision "
                "FROM generate_series(1, 10000) AS n"
            ),
            {
                "tenant": authorized_context.tenant_id,
                "decision": authorized_context.decision.decision_id,
            },
        )
        await session.execute(text("ANALYZE clients"))
        await session.execute(text("SET LOCAL enable_seqscan = off"))
        name_plan = "\n".join(
            (
                await session.execute(
                    text(
                        "EXPLAIN SELECT id FROM clients WHERE tenant_id=:tenant "
                        "AND lower(first_name || ' ' || last_name)='test client'"
                    ),
                    {"tenant": authorized_context.tenant_id},
                )
            ).scalars()
        )
        assert "ix_clients_tenant_normalized_full_name" in name_plan
        lexical_plan = "\n".join(
            (
                await session.execute(
                    text(
                        "EXPLAIN SELECT id FROM clients WHERE tenant_id=:tenant "
                        "AND search_vector @@ websearch_to_tsquery('english', 'client')"
                    ),
                    {"tenant": authorized_context.tenant_id},
                )
            ).scalars()
        )
        assert "ix_clients_search_vector" in lexical_plan


@pytest.mark.asyncio
async def test_client_search_branches_are_tenant_scoped_and_deterministic(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    suffix = uuid.uuid4().hex
    async with database_session_factory() as session:
        async with session.begin():
            matching = Client(
                tenant_id=authorized_context.tenant_id,
                first_name="Ada",
                last_name="Lovelace",
                email=f"ada-{suffix}@example.com",
                normalized_email=f"ada-{suffix}@example.com",
                description="Analytical engine retirement specialist",
                social_links=[],
                source_type="fixture",
                source_reference=f"search-{suffix}",
                creation_authorization_decision_id=authorized_context.decision.decision_id,
            )
            session.add(matching)
            other_tenant = Tenant(slug=f"search-other-{suffix}", name="Other")
            other_advisor = Advisor(external_id=f"search-other-{suffix}")
            session.add_all([other_tenant, other_advisor])
            await session.flush()
            session.add(
                AdvisorTenantMembership(tenant_id=other_tenant.id, advisor_id=other_advisor.id)
            )
        other_context = await authorize(
            session,
            tenant_slug=other_tenant.slug,
            advisor_external_id=other_advisor.external_id,
            action=AuthorizationAction.CLIENT_CREATE,
            request_id=f"other-search-{suffix}",
        )
        await session.commit()
        async with session.begin():
            session.add(
                Client(
                    tenant_id=other_tenant.id,
                    first_name="Ada",
                    last_name="Lovelace",
                    email=f"ada-{suffix}@example.com",
                    normalized_email=f"ada-{suffix}@example.com",
                    description="Analytical engine retirement specialist",
                    social_links=[],
                    source_type="fixture",
                    source_reference=f"other-search-{suffix}",
                    creation_authorization_decision_id=other_context.decision.decision_id,
                )
            )

    async with database_session_factory() as session:
        email = await search_exact_email_clients(
            session,
            tenant_id=authorized_context.tenant_id,
            query=f"  ADA-{suffix}@EXAMPLE.COM  ",
        )
        name = await search_exact_name_clients(
            session,
            tenant_id=authorized_context.tenant_id,
            query="  ADA LOVELACE  ",
            limit=10,
        )
        lexical = await search_lexical_clients(
            session,
            tenant_id=authorized_context.tenant_id,
            query="analytical retirement",
            limit=10,
        )
        nonsense = await search_lexical_clients(
            session,
            tenant_id=authorized_context.tenant_id,
            query="zzzxqv unmatched",
            limit=10,
        )

    assert [(item.client_id, item.match_band) for item in email] == [
        (matching.id, MatchBand.EXACT_EMAIL)
    ]
    assert [(item.client_id, item.match_band) for item in name] == [
        (matching.id, MatchBand.EXACT_NAME)
    ]
    assert [(item.client_id, item.match_band) for item in lexical] == [
        (matching.id, MatchBand.GENERAL)
    ]
    assert nonsense == []
    assert all(item.client_id != client_id for item in lexical)


@pytest.mark.asyncio
async def test_client_creation_constraints_are_race_safe(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
) -> None:
    async def submit(key: str, request_id: str):
        async with database_session_factory() as session:
            return await create_client(session, client_command(key, request_id), authorized_context)

    replays = await asyncio.gather(submit("same-key", "race-1"), submit("same-key", "race-2"))
    assert {result.outcome for result in replays} == {
        ClientCreationOutcome.CREATED,
        ClientCreationOutcome.REPLAYED,
    }
    conflicts = await asyncio.gather(
        submit("different-key-1", "race-3"),
        submit("different-key-2", "race-4"),
        return_exceptions=True,
    )
    assert all(isinstance(result, ClientConflict) for result in conflicts)


@pytest.mark.asyncio
async def test_client_create_replay_conflict_retrieve_and_document_workflow(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
) -> None:
    app = create_app(Settings(database_url=os.environ["NEVIS_TEST_DATABASE_URL"]))
    app.state.session_factory = database_session_factory
    transport = httpx.ASGITransport(app=app)
    identity = {"X-Nevis-Tenant": "nevis-global", "X-Nevis-Advisor": "test-advisor"}
    headers = {**identity, "Idempotency-Key": "client-create-1"}
    payload = {
        "first_name": " Ada ",
        "last_name": " Lovelace ",
        "email": " Ada@Example.COM ",
        "description": "Mathematician",
        "social_links": ["https://example.com/ada"],
        "source_type": "crm",
        "source_reference": "contact-1",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/v1/clients", json=payload, headers=headers)
        assert created.status_code == 201
        body = created.json()
        assert body["email"] == "ada@example.com"
        assert body["outcome"] == "created"
        client_id = body["id"]
        replay = await client.post("/v1/clients", json=payload, headers=headers)
        assert replay.status_code == 201 and replay.json()["outcome"] == "replayed"
        conflict = await client.post(
            "/v1/clients", json={**payload, "last_name": "Byron"}, headers=headers
        )
        assert conflict.status_code == 409
        email_conflict = await client.post(
            "/v1/clients",
            json={**payload, "email": "ADA@example.com"},
            headers={**identity, "Idempotency-Key": "client-create-2"},
        )
        assert email_conflict.status_code == 409
        found = await client.get(f"/v1/clients/{client_id}", headers=identity)
        assert found.status_code == 200
        assert found.json()["retrieval_authorization_decision_id"]
        missing = await client.get(f"/v1/clients/{uuid.uuid4()}", headers=identity)
        assert missing.status_code == 404
        document = await client.post(
            f"/v1/clients/{client_id}/documents",
            json={
                "source_reference": "crm",
                "external_document_id": "note-1",
                "title": "Client note",
                "content": "Retirement planning",
            },
            headers={**identity, "Idempotency-Key": "document-1"},
        )
        assert document.status_code == 202
        resource = await client.get(
            f"/v1/documents/{document.json()['document_id']}", headers=identity
        )
        assert resource.status_code == 200
        assert resource.json()["client_id"] == client_id
        assert "content" not in resource.json()
        assert (await client.post("/v1/documents", json={}, headers=headers)).status_code == 404

        async with database_session_factory() as session:
            async with session.begin():
                suffix = uuid.uuid4().hex
                other_tenant = Tenant(slug=f"client-api-other-{suffix}", name="Other")
                other_advisor = Advisor(external_id=f"client-api-other-advisor-{suffix}")
                session.add_all([other_tenant, other_advisor])
                await session.flush()
                session.add(
                    AdvisorTenantMembership(tenant_id=other_tenant.id, advisor_id=other_advisor.id)
                )
        other_identity = {
            "X-Nevis-Tenant": other_tenant.slug,
            "X-Nevis-Advisor": other_advisor.external_id,
        }
        assert (
            await client.get(f"/v1/clients/{client_id}", headers=other_identity)
        ).status_code == 404
        assert (
            await client.get(
                f"/v1/documents/{document.json()['document_id']}", headers=other_identity
            )
        ).status_code == 404
        cross_tenant_email = await client.post(
            "/v1/clients",
            json=payload,
            headers={**other_identity, "Idempotency-Key": "other-client-create"},
        )
        assert cross_tenant_email.status_code == 201

    async with database_session_factory() as session:
        events = (await session.scalars(select(AuditEvent))).all()
    serialized = str([event.metadata_ for event in events])
    for secret in ["ada@example.com", "Mathematician", "client-create-1"]:
        assert secret not in serialized
