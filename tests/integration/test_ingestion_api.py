import os
import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nevis.domain.embeddings import EmbeddingProfileIdentity
from nevis.infrastructure.embeddings import DeterministicFakeProvider
from nevis.infrastructure.models import Advisor, AdvisorTenantMembership, Tenant
from nevis.main import create_app
from nevis.settings import Settings


@pytest.mark.asyncio
async def test_ingestion_api_contract(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    app = create_app(Settings(database_url=os.environ["NEVIS_TEST_DATABASE_URL"]))
    app.state.session_factory = database_session_factory
    app.state.embedding_provider = DeterministicFakeProvider(
        EmbeddingProfileIdentity("fake", "fixture", "1", 384, "l2", 1, 1)
    )
    payload = {
        "source_reference": "api-test",
        "external_document_id": "document-1",
        "title": "Fixture",
        "content": "trusted text",
    }
    transport = httpx.ASGITransport(app=app)
    headers = {
        "Idempotency-Key": "api-1",
        "X-Nevis-Tenant": "nevis-global",
        "X-Nevis-Advisor": "test-advisor",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        path = f"/v1/clients/{client_id}/documents"
        accepted = await client.post(path, json=payload, headers=headers)
        assert accepted.status_code == 202
        replay = await client.post(path, json=payload, headers=headers)
        assert replay.status_code == 202
        assert replay.json()["outcome"] == "replayed"
        conflict = await client.post(
            path,
            json={**payload, "content": "different"},
            headers=headers,
        )
        assert conflict.status_code == 409
        rejected_file = await client.post(
            path,
            files={"file": ("x.txt", b"no")},
            headers=headers,
        )
        assert rejected_file.status_code == 422
        version = accepted.json()["document_version_id"]
        assert (
            await client.get(f"/v1/document-versions/{version}", headers=headers)
        ).status_code == 200
        assert (
            await client.post(path, json=payload, headers={"Idempotency-Key": "missing"})
        ).status_code == 401
        assert (
            await client.post("/v1/documents", json=payload, headers=headers)
        ).status_code == 404
        assert (
            await client.get(
                f"/v1/document-versions/{version}",
                headers={"X-Nevis-Tenant": "nevis-global", "X-Nevis-Advisor": "unknown"},
            )
        ).status_code == 403
        identity_suffix = uuid.uuid4().hex
        async with database_session_factory() as session:
            async with session.begin():
                second_tenant = Tenant(slug=f"other-{identity_suffix}", name="Other tenant")
                second_advisor = Advisor(external_id=f"other-{identity_suffix}")
                session.add_all([second_tenant, second_advisor])
                await session.flush()
                session.add(
                    AdvisorTenantMembership(
                        tenant_id=second_tenant.id, advisor_id=second_advisor.id
                    )
                )
        assert (
            await client.get(
                f"/v1/document-versions/{version}",
                headers={
                    "X-Nevis-Tenant": second_tenant.slug,
                    "X-Nevis-Advisor": second_advisor.external_id,
                },
            )
        ).status_code == 404
