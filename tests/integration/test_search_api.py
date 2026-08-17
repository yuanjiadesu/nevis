import os

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nevis.application.ingestion import ingest_plain_text
from nevis.domain.documents import IngestionCommand
from nevis.domain.embeddings import EmbeddingProfileIdentity
from nevis.infrastructure.embeddings import DeterministicFakeProvider, EmbeddingProviderUnavailable
from nevis.infrastructure.models import AuditEvent, Client
from nevis.infrastructure.reranking import DeterministicFakeReranker, RerankerProviderUnavailable
from nevis.main import create_app
from nevis.settings import Settings
from nevis.workers.main import process_indexing_once


def _profile() -> EmbeddingProfileIdentity:
    return EmbeddingProfileIdentity("fake", "fixture", "1", 384, "l2", 1, 1)


class QueryFailingProvider(DeterministicFakeProvider):
    async def embed_query(self, text: str) -> list[float]:
        raise EmbeddingProviderUnavailable("fixture unavailable")


class FailingReranker(DeterministicFakeReranker):
    async def rerank(self, query: str, passages: list[str]) -> list[float]:
        raise RerankerProviderUnavailable("fixture unavailable")


@pytest.mark.asyncio
async def test_protected_search_api_and_lexical_degradation(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = DeterministicFakeProvider(_profile())
    async with database_session_factory() as session:
        async with session.begin():
            matching_client = Client(
                tenant_id=authorized_context.tenant_id,
                first_name="Inheritance",
                last_name="Tax",
                email="inheritance@example.com",
                normalized_email="inheritance@example.com",
                description="Inheritance tax planning client",
                social_links=[],
                source_type="fixture",
                source_reference="mixed-search-client",
                creation_authorization_decision_id=authorized_context.decision.decision_id,
            )
            prefix_client = Client(
                tenant_id=authorized_context.tenant_id,
                first_name="Ada",
                last_name="Lovelace",
                email="ada@example.com",
                normalized_email="ada@example.com",
                description=None,
                social_links=[],
                source_type="fixture",
                source_reference="prefix-search-client",
                creation_authorization_decision_id=authorized_context.decision.decision_id,
            )
            session.add_all([matching_client, prefix_client])
        await ingest_plain_text(
            session,
            IngestionCommand(
                client_id,
                "crm",
                "api-search",
                "Inheritance tax planning",
                "Inheritance tax planning and trust allowances",
                "api-search-1",
                "api-ingest-1",
            ),
            _profile(),
            authorized_context,
        )
    assert await process_indexing_once(database_session_factory, provider)

    app = create_app(
        Settings(
            _env_file=None,
            environment="local",
            database_url=os.environ["NEVIS_TEST_DATABASE_URL"],
            search_semantic_candidate_threshold=-1.0,
            search_reranker_threshold=-1.0,
        )
    )
    app.state.session_factory = database_session_factory
    app.state.embedding_provider = provider
    app.state.reranker_provider = DeterministicFakeReranker()
    result_schema = app.openapi()["components"]["schemas"]["SearchResponse"]["properties"][
        "results"
    ]["items"]
    assert result_schema["discriminator"]["propertyName"] == "type"
    assert set(result_schema["discriminator"]["mapping"]) == {"client", "document"}
    transport = httpx.ASGITransport(app=app)
    headers = {"X-Nevis-Tenant": "nevis-global", "X-Nevis-Advisor": "test-advisor"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/search", params={"q": "inheritance tax"}, headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "hybrid"
        assert body["ranking_version"] == "mixed-rrf-v5"
        assert body["results"][0]["type"] == "client"
        assert {item["type"] for item in body["results"]} == {"client", "document"}
        assert body["results"][0]["provenance"]["tenant_id"] == str(authorized_context.tenant_id)
        prefix = await client.get("/search", params={"q": "ad"}, headers=headers)
        assert prefix.status_code == 200
        assert any(
            item["type"] == "client" and item["provenance"]["client_id"] == str(prefix_client.id)
            for item in prefix.json()["results"]
        )
        email_domain = await client.get("/search", params={"q": "example.com"}, headers=headers)
        assert email_domain.status_code == 200
        assert email_domain.json()["mode"] == "lexical_identifier"
        domain_client_ids = {
            item["provenance"]["client_id"]
            for item in email_domain.json()["results"]
            if item["type"] == "client"
        }
        assert {str(matching_client.id), str(prefix_client.id)} <= domain_client_ids
        first_page = await client.get(
            "/search", params={"q": "inheritance tax", "limit": 1}, headers=headers
        )
        assert first_page.status_code == 200
        assert first_page.json()["results"][0]["type"] == "client"
        assert first_page.json()["next_cursor"]
        second_page = await client.get(
            "/search",
            params={"q": "inheritance tax", "limit": 1, "cursor": first_page.json()["next_cursor"]},
            headers=headers,
        )
        assert second_page.status_code == 200
        assert second_page.json()["results"][0]["type"] == "document"
        assert (await client.get("/search", params={"q": "tax"})).status_code == 401
        assert (
            await client.get(
                "/search",
                params={"q": "tax"},
                headers={"X-Nevis-Tenant": "nevis-global", "X-Nevis-Advisor": "unknown"},
            )
        ).status_code == 403
        assert (
            await client.get("/search", params={"q": "   "}, headers=headers)
        ).status_code == 422
        assert (
            await client.get("/search", params={"q": "tax", "cursor": "modified"}, headers=headers)
        ).status_code == 400

        app.state.settings.search_semantic_candidate_threshold = 1.0
        empty = await client.get("/search", params={"q": "zzzxqv unmatched"}, headers=headers)
        assert empty.status_code == 200
        assert empty.json()["results"] == []

        app.state.settings.search_semantic_candidate_threshold = -1.0
        app.state.reranker_provider = FailingReranker()
        unreranked = await client.get("/search", params={"q": "inheritance tax"}, headers=headers)
        assert unreranked.status_code == 200
        assert unreranked.json()["mode"] == "hybrid_unreranked"
        app.state.reranker_provider = DeterministicFakeReranker()

        app.state.embedding_provider = QueryFailingProvider(_profile())
        identifier = await client.get("/search", params={"q": "example.com"}, headers=headers)
        assert identifier.status_code == 200
        assert identifier.json()["mode"] == "lexical_identifier"
        degraded = await client.get("/search", params={"q": "inheritance"}, headers=headers)
        assert degraded.status_code == 200
        assert degraded.json()["mode"] == "lexical_degraded"
        assert {item["type"] for item in degraded.json()["results"]} == {
            "client",
            "document",
        }
        title_prefix = await client.get("/search", params={"q": "inheri"}, headers=headers)
        assert title_prefix.status_code == 200
        assert any(
            item["type"] == "document" and item["title"] == "Inheritance tax planning"
            for item in title_prefix.json()["results"]
        )

        client_only = await client.get("/search", params={"q": "ada@exam"}, headers=headers)
        assert client_only.status_code == 200
        assert [item["type"] for item in client_only.json()["results"]] == ["client"]
        assert client_only.json()["results"][0]["provenance"]["client_id"] == str(prefix_client.id)

        content_prefix = await client.get("/search", params={"q": "allowan"}, headers=headers)
        assert content_prefix.status_code == 200
        assert not any(item["type"] == "document" for item in content_prefix.json()["results"])

        async with database_session_factory() as session:
            audit_metadata = [
                event.metadata_
                for event in (await session.scalars(select(AuditEvent))).all()
                if event.event_type == "mixed.search.completed"
            ]
        serialized_audit = str(audit_metadata).lower()
        for sensitive in (
            "inheritance tax",
            "inheritance@example.com",
            "inheritance tax planning client",
            "trust allowances",
        ):
            assert sensitive not in serialized_audit

        async def fail_audit(*args: object, **kwargs: object) -> None:
            raise SQLAlchemyError("fixture audit failure")

        monkeypatch.setattr("nevis.application.search.append_audit_event", fail_audit)
        unavailable = await client.get("/search", params={"q": "tax"}, headers=headers)
        assert unavailable.status_code == 503
        assert unavailable.json() == {"detail": "search unavailable"}
