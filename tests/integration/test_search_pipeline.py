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
from nevis.domain.search import RetrievalMode, SearchQuery
from nevis.infrastructure.cursors import SearchCursorCodec
from nevis.infrastructure.embeddings import DeterministicFakeProvider
from nevis.infrastructure.models import Advisor, AdvisorTenantMembership, AuditEvent, Client, Tenant
from nevis.workers.main import process_indexing_once


def _profile() -> EmbeddingProfileIdentity:
    return EmbeddingProfileIdentity("fake", "fixture", "1", 384, "l2", 1, 1)


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
            cursor_codec=SearchCursorCodec("x" * 32, 900),
            lexical_limit=100,
            semantic_limit=100,
            client_limit=100,
            semantic_threshold=-1.0,
            rrf_constant=60,
            snippet_length=200,
            client_excerpt_length=100,
            client_weight=1.0,
            document_lexical_weight=1.0,
            document_semantic_weight=1.0,
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
            cursor_codec=SearchCursorCodec("x" * 32, 900),
            lexical_limit=100,
            semantic_limit=100,
            client_limit=100,
            semantic_threshold=-1.0,
            rrf_constant=60,
            snippet_length=200,
            client_excerpt_length=100,
            client_weight=1.0,
            document_lexical_weight=1.0,
            document_semantic_weight=1.0,
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
            cursor_codec=SearchCursorCodec("x" * 32, 900),
            lexical_limit=100,
            semantic_limit=100,
            client_limit=100,
            semantic_threshold=-1.0,
            rrf_constant=60,
            snippet_length=200,
            client_excerpt_length=100,
            client_weight=1.0,
            document_lexical_weight=1.0,
            document_semantic_weight=1.0,
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
            cursor_codec=SearchCursorCodec("x" * 32, 900),
            lexical_limit=100,
            semantic_limit=100,
            client_limit=100,
            semantic_threshold=-1.0,
            rrf_constant=60,
            snippet_length=200,
            client_excerpt_length=100,
            client_weight=1.0,
            document_lexical_weight=1.0,
            document_semantic_weight=1.0,
        )
    assert all(
        item.provenance.document_version_id != first.document_version_id for item in empty.results
    )
