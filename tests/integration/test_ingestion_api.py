import asyncio
import os
import uuid

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nevis.domain.embeddings import EmbeddingProfileIdentity
from nevis.infrastructure.embeddings import DeterministicFakeProvider
from nevis.infrastructure.models import (
    Advisor,
    AdvisorTenantMembership,
    DocumentVersion,
    IndexingJob,
    IngestionRequest,
    Tenant,
)
from nevis.main import create_app
from nevis.settings import Settings


@pytest.mark.asyncio
async def test_concurrent_ingestion_has_deterministic_outcomes(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    app = create_app(Settings(_env_file=None, database_url=os.environ["NEVIS_TEST_DATABASE_URL"]))
    app.state.session_factory = database_session_factory
    app.state.embedding_provider = DeterministicFakeProvider(
        EmbeddingProfileIdentity("fake", "fixture", "1", 384, "l2", 1, 1)
    )
    transport = httpx.ASGITransport(app=app)
    identity = {
        "X-Nevis-Tenant": "nevis-global",
        "X-Nevis-Advisor": "test-advisor",
    }
    path = f"/v1/clients/{client_id}/documents"
    payload = {
        "source_reference": "concurrency-test",
        "external_document_id": "document-1",
        "title": "Concurrent document",
        "content": "initial content",
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        equivalent = await asyncio.gather(
            client.post(
                path,
                json=payload,
                headers={**identity, "Idempotency-Key": "same-request"},
            ),
            client.post(
                path,
                json=payload,
                headers={**identity, "Idempotency-Key": "same-request"},
            ),
        )
        assert [response.status_code for response in equivalent] == [202, 202]
        assert {response.json()["outcome"] for response in equivalent} == {
            "accepted",
            "replayed",
        }
        document_id = equivalent[0].json()["document_id"]

        revisions = await asyncio.gather(
            client.post(
                f"/v1/documents/{document_id}/revisions",
                json={"title": "Revision A", "content": "revision A"},
                headers={**identity, "Idempotency-Key": "revision-a"},
            ),
            client.post(
                f"/v1/documents/{document_id}/revisions",
                json={"title": "Revision B", "content": "revision B"},
                headers={**identity, "Idempotency-Key": "revision-b"},
            ),
        )
        assert [response.status_code for response in revisions] == [202, 202]
        assert sorted(response.json()["version_number"] for response in revisions) == [2, 3]
        expected_title = max(
            zip(revisions, ("Revision A", "Revision B"), strict=True),
            key=lambda item: item[0].json()["version_number"],
        )[1]
        current = await client.get(f"/v1/documents/{document_id}", headers=identity)
        assert current.status_code == 200
        assert current.json()["title"] == expected_title

        conflict_payload = {
            **payload,
            "external_document_id": "document-2",
        }
        conflicts = await asyncio.gather(
            client.post(
                path,
                json={**conflict_payload, "content": "winner A"},
                headers={**identity, "Idempotency-Key": "conflicting-request"},
            ),
            client.post(
                path,
                json={**conflict_payload, "content": "winner B"},
                headers={**identity, "Idempotency-Key": "conflicting-request"},
            ),
        )
        assert sorted(response.status_code for response in conflicts) == [202, 409]

    async with database_session_factory() as session:
        versions = (await session.scalars(select(DocumentVersion))).all()
        jobs = (await session.scalars(select(IndexingJob))).all()
        requests = (await session.scalars(select(IngestionRequest))).all()
    assert len(versions) == 4
    assert len(jobs) == 4
    assert len(requests) == 4


@pytest.mark.asyncio
async def test_revision_title_failure_rolls_back_the_new_version(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    app = create_app(Settings(_env_file=None, database_url=os.environ["NEVIS_TEST_DATABASE_URL"]))
    app.state.session_factory = database_session_factory
    app.state.embedding_provider = DeterministicFakeProvider(
        EmbeddingProfileIdentity("fake", "fixture", "1", 384, "l2", 1, 1)
    )
    transport = httpx.ASGITransport(app=app)
    headers = {
        "X-Nevis-Tenant": "nevis-global",
        "X-Nevis-Advisor": "test-advisor",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        accepted = await client.post(
            f"/v1/clients/{client_id}/documents",
            json={
                "source_reference": "atomic-revision-test",
                "external_document_id": "document-1",
                "title": "Initial title",
                "content": "initial content",
            },
            headers={**headers, "Idempotency-Key": "initial-request"},
        )
        assert accepted.status_code == 202
        document_id = uuid.UUID(accepted.json()["document_id"])

        async with database_session_factory() as session:
            await session.execute(
                text(
                    "ALTER TABLE documents ADD CONSTRAINT test_revision_title_atomicity "
                    "CHECK (title <> 'Blocked title')"
                )
            )
            await session.commit()
        try:
            revision = await client.post(
                f"/v1/documents/{document_id}/revisions",
                json={"title": "Blocked title", "content": "replacement content"},
                headers={**headers, "Idempotency-Key": "blocked-revision"},
            )
            assert revision.status_code == 409
        finally:
            async with database_session_factory() as session:
                await session.execute(
                    text("ALTER TABLE documents DROP CONSTRAINT test_revision_title_atomicity")
                )
                await session.commit()

    async with database_session_factory() as session:
        version_count = await session.scalar(
            select(func.count(DocumentVersion.id)).where(DocumentVersion.document_id == document_id)
        )
        job_count = await session.scalar(
            select(func.count(IndexingJob.id)).where(IndexingJob.document_id == document_id)
        )
        request_count = await session.scalar(
            select(func.count(IngestionRequest.id)).where(
                IngestionRequest.document_version_id.in_(
                    select(DocumentVersion.id).where(DocumentVersion.document_id == document_id)
                )
            )
        )
    assert version_count == 1
    assert job_count == 1
    assert request_count == 1


@pytest.mark.asyncio
async def test_ingestion_api_contract(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    app = create_app(Settings(_env_file=None, database_url=os.environ["NEVIS_TEST_DATABASE_URL"]))
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
        document_id = accepted.json()["document_id"]
        editable = await client.get(f"/v1/documents/{document_id}/edit", headers=headers)
        assert editable.status_code == 200
        assert editable.json()["content"] == "trusted text"
        revision = await client.post(
            f"/v1/documents/{document_id}/revisions",
            json={"title": "Updated fixture", "content": "updated trusted text"},
            headers={**headers, "Idempotency-Key": "revision-1"},
        )
        assert revision.status_code == 202
        assert revision.json()["document_id"] == document_id
        assert revision.json()["version_number"] == 2
        unchanged = await client.post(
            f"/v1/documents/{document_id}/revisions",
            json={"title": "Updated fixture", "content": "updated trusted text"},
            headers={**headers, "Idempotency-Key": "revision-2"},
        )
        assert unchanged.status_code == 202
        assert unchanged.json()["outcome"] == "replayed"
        versions = await client.get(f"/v1/documents/{document_id}/versions", headers=headers)
        assert [item["version_number"] for item in versions.json()["versions"]] == [2, 1]
        earlier_version_id = versions.json()["versions"][1]["document_version_id"]
        earlier_content = await client.get(
            f"/v1/document-versions/{earlier_version_id}/content", headers=headers
        )
        assert earlier_content.status_code == 200
        assert earlier_content.json()["content"] == "trusted text"
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
        assert (
            await client.get(
                f"/v1/documents/{document_id}/edit",
                headers={
                    "X-Nevis-Tenant": second_tenant.slug,
                    "X-Nevis-Advisor": second_advisor.external_id,
                },
            )
        ).status_code == 404
        assert (
            await client.get(
                f"/v1/document-versions/{earlier_version_id}/content",
                headers={
                    "X-Nevis-Tenant": second_tenant.slug,
                    "X-Nevis-Advisor": second_advisor.external_id,
                },
            )
        ).status_code == 404
        assert (
            await client.post(
                f"/v1/documents/{document_id}/revisions",
                json={"title": "Denied", "content": "Denied"},
                headers={
                    "Idempotency-Key": "revision-other",
                    "X-Nevis-Tenant": second_tenant.slug,
                    "X-Nevis-Advisor": second_advisor.external_id,
                },
            )
        ).status_code == 404
