import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nevis.application.authorization import authorize
from nevis.application.ingestion import ingest_plain_text
from nevis.application.search import search_documents
from nevis.domain.authorization import AuthorizationAction
from nevis.domain.documents import IngestionCommand
from nevis.domain.embeddings import EmbeddingProfileIdentity
from nevis.domain.search import MatchBand, RetrievalMode, SearchQuery
from nevis.infrastructure.cursors import SearchCursorCodec
from nevis.infrastructure.embeddings import DeterministicFakeProvider
from nevis.infrastructure.models import Advisor, AdvisorTenantMembership, AuditEvent, Client, Tenant
from nevis.infrastructure.repositories import (
    get_active_embedding_profile,
    search_fuzzy_title_candidates,
)
from nevis.infrastructure.reranking import DeterministicFakeReranker
from nevis.workers.main import process_indexing_once


def _profile() -> EmbeddingProfileIdentity:
    return EmbeddingProfileIdentity("fake", "fixture", "1", 384, "l2", 1, 1)


class _TypoSensitiveProvider:
    def __init__(self) -> None:
        self._base = DeterministicFakeProvider(_profile())
        self._document_vector: list[float] | None = None
        self.query_calls: list[str] = []

    @property
    def profile(self) -> EmbeddingProfileIdentity:
        return _profile()

    async def healthcheck(self):
        return await self._base.healthcheck()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = await self._base.embed_documents(texts)
        if vectors:
            self._document_vector = vectors[0]
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        assert self._document_vector is not None
        if text == "investment opportunity":
            return self._document_vector
        return [-value for value in self._document_vector]


class _RecordingReranker(DeterministicFakeReranker):
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def rerank(self, query: str, passages: list[str]) -> list[float]:
        self.queries.append(query)
        return await super().rerank(query, passages)


class _RejectingReranker(DeterministicFakeReranker):
    async def rerank(self, query: str, passages: list[str]) -> list[float]:
        del query
        return [0.0] * len(passages)


@pytest.mark.asyncio
async def test_exact_and_prefix_titles_survive_unrelated_content_rejection(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    provider = DeterministicFakeProvider(_profile())
    async with database_session_factory() as session:
        await ingest_plain_text(
            session,
            IngestionCommand(
                client_id,
                "crm",
                "title-only-evidence",
                "Test ingestion",
                "Postgres database indexes support JSONB and array columns.",
                "title-only-ingest",
                "title-only-ingest-key",
            ),
            _profile(),
            authorized_context,
        )
    assert await process_indexing_once(database_session_factory, provider)

    async with database_session_factory() as session:
        search_context = await authorize(
            session,
            tenant_slug="nevis-global",
            advisor_external_id="test-advisor",
            action=AuthorizationAction.MIXED_SEARCH,
            request_id="title-only-search-authorization",
        )
        await session.commit()

    async def run(query: str):
        async with database_session_factory() as session:
            return await search_documents(
                session,
                query=SearchQuery.create(query, 10, max_length=100, max_limit=50),
                request_id=f"title-only-{query}",
                cursor=None,
                authorization=search_context,
                provider=provider,
                reranker=_RejectingReranker(),
                cursor_codec=SearchCursorCodec("x" * 32, 900),
                lexical_limit=100,
                semantic_limit=100,
                client_limit=100,
                semantic_candidate_threshold=1.1,
                reranker_limit=10,
                reranker_threshold=0.5,
                rrf_constant=60,
                snippet_length=200,
                client_excerpt_length=100,
                client_weight=1.0,
                document_lexical_weight=1.0,
                document_semantic_weight=1.0,
                document_reranker_weight=1.0,
            )

    exact = await run("Test ingestion")
    prefix = await run("Test ing")
    content = await run("Postgres")

    assert "Test ingestion" in [item.title for item in exact.results]
    assert "Test ingestion" in [item.title for item in prefix.results]
    assert content.results == ()


@pytest.mark.asyncio
async def test_fuzzy_title_and_empty_result_spelling_retry_are_bounded_and_audited(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    provider = _TypoSensitiveProvider()
    content = (
        "The client wants investments aligned with environmental and social goals while "
        "retaining broad diversification."
    )
    async with database_session_factory() as session:
        await ingest_plain_text(
            session,
            IngestionCommand(
                client_id,
                "crm",
                "responsible-goals",
                "Responsible goals",
                content,
                "typo-ingest",
                "typo-ingest-key",
            ),
            _profile(),
            authorized_context,
        )
    assert await process_indexing_once(database_session_factory, provider)

    async with database_session_factory() as session:
        active_profile = await get_active_embedding_profile(session)
        assert active_profile is not None
        fuzzy_titles = await search_fuzzy_title_candidates(
            session,
            tenant_id=authorized_context.tenant_id,
            profile_id=active_profile.id,
            query="Responsble goals",
            threshold=0.5,
            limit=10,
            snippet_length=200,
        )
    assert fuzzy_titles

    async with database_session_factory() as session:
        search_context = await authorize(
            session,
            tenant_slug="nevis-global",
            advisor_external_id="test-advisor",
            action=AuthorizationAction.MIXED_SEARCH,
            request_id="typo-search-authorization",
        )
        await session.commit()

    reranker = _RecordingReranker()
    async with database_session_factory() as session:
        page = await search_documents(
            session,
            query=SearchQuery.create("investment opportunit", 10, max_length=100, max_limit=50),
            request_id="typo-search",
            cursor=None,
            authorization=search_context,
            provider=provider,
            reranker=reranker,
            cursor_codec=SearchCursorCodec("x" * 32, 900),
            lexical_limit=100,
            semantic_limit=100,
            client_limit=100,
            semantic_candidate_threshold=0.99,
            reranker_limit=10,
            reranker_threshold=0.5,
            rrf_constant=60,
            snippet_length=200,
            client_excerpt_length=100,
            client_weight=1.0,
            document_lexical_weight=1.0,
            document_semantic_weight=1.0,
            document_reranker_weight=1.0,
        )

    assert [item.title for item in page.results] == ["Responsible goals"]
    assert page.results[0].match_band is MatchBand.FUZZY
    assert provider.query_calls == ["investment opportunit", "investment opportunity"]
    assert reranker.queries == ["investment opportunity"]
    async with database_session_factory() as session:
        event = await session.scalar(
            select(AuditEvent).where(AuditEvent.request_id == "typo-search")
        )
        assert event is not None
        assert event.metadata_["spelling_fallback_used"] is True
        assert "investment opportunity" not in str(event.metadata_)

    provider.query_calls.clear()
    reranker.queries.clear()
    async with database_session_factory() as session:
        title_page = await search_documents(
            session,
            query=SearchQuery.create("Responsble goals", 10, max_length=100, max_limit=50),
            request_id="fuzzy-title-search",
            cursor=None,
            authorization=search_context,
            provider=provider,
            reranker=reranker,
            cursor_codec=SearchCursorCodec("x" * 32, 900),
            lexical_limit=100,
            semantic_limit=100,
            client_limit=100,
            semantic_candidate_threshold=0.99,
            reranker_limit=10,
            reranker_threshold=0.5,
            rrf_constant=60,
            snippet_length=200,
            client_excerpt_length=100,
            client_weight=1.0,
            document_lexical_weight=1.0,
            document_semantic_weight=1.0,
            document_reranker_weight=1.0,
        )
    assert [item.title for item in title_page.results] == ["Responsible goals"]
    assert title_page.results[0].match_band is MatchBand.FUZZY
    assert reranker.queries == []

    provider.query_calls.clear()
    async with database_session_factory() as session:
        identifier_page = await search_documents(
            session,
            query=SearchQuery.create("responsble.example", 10, max_length=100, max_limit=50),
            request_id="fuzzy-identifier-search",
            cursor=None,
            authorization=search_context,
            provider=provider,
            reranker=reranker,
            cursor_codec=SearchCursorCodec("x" * 32, 900),
            lexical_limit=100,
            semantic_limit=100,
            client_limit=100,
            semantic_candidate_threshold=0.99,
            reranker_limit=10,
            reranker_threshold=0.5,
            rrf_constant=60,
            snippet_length=200,
            client_excerpt_length=100,
            client_weight=1.0,
            document_lexical_weight=1.0,
            document_semantic_weight=1.0,
            document_reranker_weight=1.0,
        )
    assert identifier_page.mode is RetrievalMode.LEXICAL_IDENTIFIER
    assert identifier_page.results == ()
    assert provider.query_calls == []


@pytest.mark.asyncio
async def test_search_is_tenant_scoped_current_version_only_and_audited(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    provider = DeterministicFakeProvider(_profile())
    async with database_session_factory() as session:
        first = await ingest_plain_text(
            session,
            IngestionCommand(
                client_id,
                "crm",
                "retirement-plan",
                "Retirement plan",
                "Pension drawdown and retirement income planning",
                "search-1",
                "ingest-search-1",
            ),
            _profile(),
            authorized_context,
        )
    assert await process_indexing_once(database_session_factory, provider)

    # A stronger match in another tenant must never enter the authorized ranking relation.
    identity_suffix = uuid.uuid4().hex
    async with database_session_factory() as session:
        async with session.begin():
            other_tenant = Tenant(
                slug=f"other-search-{identity_suffix}", name="Other search tenant"
            )
            other_advisor = Advisor(external_id=f"other-search-{identity_suffix}")
            session.add_all([other_tenant, other_advisor])
            await session.flush()
            session.add(
                AdvisorTenantMembership(
                    tenant_id=other_tenant.id,
                    advisor_id=other_advisor.id,
                )
            )
        other_context = await authorize(
            session,
            tenant_slug=other_tenant.slug,
            advisor_external_id=other_advisor.external_id,
            action=AuthorizationAction.DOCUMENT_INGEST,
            request_id="other-ingest",
        )
        await session.commit()
        async with session.begin():
            other_client = Client(
                tenant_id=other_context.tenant_id,
                first_name="Other",
                last_name="Client",
                email="other@example.com",
                normalized_email="other@example.com",
                description=None,
                social_links=[],
                source_type="fixture",
                source_reference="other-client",
                creation_authorization_decision_id=other_context.decision.decision_id,
            )
            session.add(other_client)
            await session.flush()
            other_client_id = other_client.id
    async with database_session_factory() as session:
        await ingest_plain_text(
            session,
            IngestionCommand(
                other_client_id,
                "crm",
                "other-retirement-plan",
                "Pension retirement pension retirement",
                "Pension retirement " * 50,
                "other-search-1",
                "other-ingest-1",
            ),
            _profile(),
            other_context,
        )
    assert await process_indexing_once(database_session_factory, provider)

    async with database_session_factory() as session:
        search_context = await authorize(
            session,
            tenant_slug="nevis-global",
            advisor_external_id="test-advisor",
            action=AuthorizationAction.MIXED_SEARCH,
            request_id="search-request-1",
        )
        await session.commit()
    async with database_session_factory() as session:
        page = await search_documents(
            session,
            query=SearchQuery.create("pension retirement", 10, max_length=100, max_limit=50),
            request_id="search-request-1",
            cursor=None,
            authorization=search_context,
            provider=provider,
            reranker=DeterministicFakeReranker(),
            cursor_codec=SearchCursorCodec("x" * 32, 900),
            lexical_limit=100,
            semantic_limit=100,
            client_limit=100,
            semantic_candidate_threshold=-1.0,
            reranker_limit=10,
            reranker_threshold=-1.0,
            rrf_constant=60,
            snippet_length=200,
            client_excerpt_length=100,
            client_weight=1.0,
            document_lexical_weight=1.0,
            document_semantic_weight=1.0,
            document_reranker_weight=1.0,
        )
    assert page.mode is RetrievalMode.HYBRID
    assert [item.provenance.document_version_id for item in page.results] == [
        first.document_version_id
    ]
    assert all(item.provenance.tenant_id == authorized_context.tenant_id for item in page.results)
    assert all(item.title != "Pension retirement pension retirement" for item in page.results)

    async with database_session_factory() as session:
        await ingest_plain_text(
            session,
            IngestionCommand(
                client_id,
                "crm",
                "retirement-allowance",
                "Retirement allowance",
                "Pension annual allowance for retirement contributions",
                "search-page-2",
                "ingest-page-2",
            ),
            _profile(),
            authorized_context,
        )
    assert await process_indexing_once(database_session_factory, provider)
    query = SearchQuery.create("pension retirement", 1, max_length=100, max_limit=50)
    async with database_session_factory() as session:
        first_page = await search_documents(
            session,
            query=query,
            request_id="pagination-1",
            cursor=None,
            authorization=search_context,
            provider=provider,
            reranker=DeterministicFakeReranker(),
            cursor_codec=SearchCursorCodec("x" * 32, 900),
            lexical_limit=100,
            semantic_limit=100,
            client_limit=100,
            semantic_candidate_threshold=-1.0,
            reranker_limit=10,
            reranker_threshold=-1.0,
            rrf_constant=60,
            snippet_length=200,
            client_excerpt_length=100,
            client_weight=1.0,
            document_lexical_weight=1.0,
            document_semantic_weight=1.0,
            document_reranker_weight=1.0,
        )
    assert first_page.next_cursor is not None
    async with database_session_factory() as session:
        second_page = await search_documents(
            session,
            query=query,
            request_id="pagination-2",
            cursor=first_page.next_cursor,
            authorization=search_context,
            provider=provider,
            reranker=DeterministicFakeReranker(),
            cursor_codec=SearchCursorCodec("x" * 32, 900),
            lexical_limit=100,
            semantic_limit=100,
            client_limit=100,
            semantic_candidate_threshold=-1.0,
            reranker_limit=10,
            reranker_threshold=-1.0,
            rrf_constant=60,
            snippet_length=200,
            client_excerpt_length=100,
            client_weight=1.0,
            document_lexical_weight=1.0,
            document_semantic_weight=1.0,
            document_reranker_weight=1.0,
        )
    assert second_page.results
    assert (
        first_page.results[0].provenance.document_id
        != second_page.results[0].provenance.document_id
    )

    async with database_session_factory() as session:
        event = await session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "mixed.search.completed")
        )
        assert event is not None
        assert event.metadata_["query_fingerprint"]
        assert "pension" not in str(event.metadata_)

    # A newer, not-yet-indexed version makes the completed older version non-current.
    async with database_session_factory() as session:
        await ingest_plain_text(
            session,
            IngestionCommand(
                client_id,
                "crm",
                "retirement-plan",
                "Retirement plan",
                "A replacement version awaiting indexing",
                "search-2",
                str(uuid.uuid4()),
            ),
            _profile(),
            authorized_context,
        )
    async with database_session_factory() as session:
        empty = await search_documents(
            session,
            query=SearchQuery.create("pension retirement", 10, max_length=100, max_limit=50),
            request_id="search-request-2",
            cursor=None,
            authorization=search_context,
            provider=provider,
            reranker=DeterministicFakeReranker(),
            cursor_codec=SearchCursorCodec("x" * 32, 900),
            lexical_limit=100,
            semantic_limit=100,
            client_limit=100,
            semantic_candidate_threshold=-1.0,
            reranker_limit=10,
            reranker_threshold=-1.0,
            rrf_constant=60,
            snippet_length=200,
            client_excerpt_length=100,
            client_weight=1.0,
            document_lexical_weight=1.0,
            document_semantic_weight=1.0,
            document_reranker_weight=1.0,
        )
    assert all(
        item.provenance.document_version_id != first.document_version_id for item in empty.results
    )
