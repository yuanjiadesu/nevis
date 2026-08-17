import asyncio
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nevis.application.health import readiness
from nevis.application.ingestion import (
    ingest_plain_text,
    list_client_documents,
    retrieve_document,
)
from nevis.application.summaries import get_summary_diagnostics, reconcile_summary_work
from nevis.domain.documents import DocumentNotFound, IngestionCommand
from nevis.domain.embeddings import EmbeddingProfileIdentity
from nevis.domain.summarization import (
    SummarizationError,
    SummaryConfiguration,
    SummaryStatus,
)
from nevis.infrastructure.embeddings import DeterministicFakeProvider
from nevis.infrastructure.models import AuditEvent, DocumentSummary, RuntimeCapability
from nevis.infrastructure.summarization import DeterministicFakeSummarizer
from nevis.settings import Settings
from nevis.workers.main import (
    process_summary_once,
    process_work_once,
    publish_summary_worker_heartbeat,
)


def profile() -> EmbeddingProfileIdentity:
    return EmbeddingProfileIdentity("fake", "fixture", "1", 384, "l2", 1, 1)


def summary_configuration() -> SummaryConfiguration:
    return SummaryConfiguration(True, "fixture-provider", "fixture-model", "v1")


def settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        document_summaries_enabled=True,
        fictional_test_data=True,
        llm_api_key="fixture-key",
        **overrides,
    )


def command(
    client_id: uuid.UUID,
    *,
    key: str,
    content: str,
    external_document_id: str = "summary-document",
) -> IngestionCommand:
    return IngestionCommand(
        client_id=client_id,
        source_reference="summary-fixture",
        external_document_id=external_document_id,
        title="Address evidence",
        content=content,
        idempotency_key=key,
        request_id=str(uuid.uuid4()),
    )


@pytest.mark.asyncio
async def test_worker_indexes_before_generating_one_version_scoped_summary(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    source = "Fictional utility bill for 10 Test Street."
    async with database_session_factory() as session:
        result = await ingest_plain_text(
            session,
            command(client_id, key="summary-v1", content=source),
            profile(),
            authorized_context,
            summary_configuration(),
        )
        queued = await session.scalar(
            select(DocumentSummary).where(
                DocumentSummary.document_version_id == result.document_version_id
            )
        )
    assert queued is not None
    assert queued.status == SummaryStatus.PENDING
    assert queued.provider == "fixture-provider"
    assert queued.model == "fixture-model"
    summarizer = DeterministicFakeSummarizer("A utility bill confirms the fictional address.")
    worker_settings = settings()

    assert await process_work_once(
        database_session_factory,
        DeterministicFakeProvider(profile()),
        summarizer,
        worker_settings,
    )
    assert summarizer.calls == []
    assert await process_work_once(
        database_session_factory,
        DeterministicFakeProvider(profile()),
        summarizer,
        worker_settings,
    )

    async with database_session_factory() as session:
        rows = (
            await session.scalars(
                select(DocumentSummary).where(
                    DocumentSummary.document_version_id == result.document_version_id
                )
            )
        ).all()
    assert len(rows) == 1
    assert rows[0].status == SummaryStatus.READY
    assert rows[0].summary == "A utility bill confirms the fictional address."
    assert rows[0].provider == "fake"
    assert rows[0].model == "fixture"
    assert summarizer.calls == [source]

    assert not await process_work_once(
        database_session_factory,
        DeterministicFakeProvider(profile()),
        summarizer,
        worker_settings,
    )
    assert summarizer.calls == [source]

    async with database_session_factory() as session:
        resource = await retrieve_document(
            session, result.document_id, authorized_context, "summary-resource"
        )
        timeline, _ = await list_client_documents(
            session, client_id, authorized_context, "summary-timeline", limit=20
        )
    assert resource.summary == rows[0].summary
    assert resource.summary_status == SummaryStatus.READY
    assert timeline[0].summary == rows[0].summary
    assert timeline[0].summary_status == SummaryStatus.READY

    async with database_session_factory() as session:
        persisted = await retrieve_document(
            session,
            result.document_id,
            authorized_context,
            "disabled-summary-resource",
        )
    assert persisted.summary == rows[0].summary

    other_tenant = replace(authorized_context, tenant_id=uuid.uuid4())
    async with database_session_factory() as session:
        with pytest.raises(DocumentNotFound):
            await retrieve_document(
                session, result.document_id, other_tenant, "cross-tenant-summary"
            )


@pytest.mark.asyncio
async def test_new_version_is_null_until_its_own_summary_is_ready(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    fake = DeterministicFakeSummarizer("The first fictional version is summarized.")
    async with database_session_factory() as session:
        first = await ingest_plain_text(
            session,
            command(client_id, key="version-1", content="First version."),
            profile(),
            authorized_context,
            summary_configuration(),
        )
    await process_summary_once(
        database_session_factory,
        fake,
        input_max_chars=1_000,
        output_max_chars=200,
        lease_seconds=60,
        max_attempts=3,
    )
    async with database_session_factory() as session:
        second = await ingest_plain_text(
            session,
            command(client_id, key="version-2", content="Second version."),
            profile(),
            authorized_context,
            summary_configuration(),
        )
        timeline, _ = await list_client_documents(
            session, client_id, authorized_context, "timeline", limit=20
        )

    assert first.document_version_id != second.document_version_id
    assert timeline[0].current_document_version_id == second.document_version_id
    assert timeline[0].summary_status == SummaryStatus.PENDING
    assert timeline[0].summary is None


class FailingSummarizer(DeterministicFakeSummarizer):
    async def summarize(self, content: str):
        self.calls.append(content)
        raise SummarizationError("provider_unavailable")


@pytest.mark.asyncio
async def test_generation_retries_then_fails_without_sensitive_telemetry(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    sensitive = "fictional-secret-content"
    async with database_session_factory() as session:
        result = await ingest_plain_text(
            session,
            command(client_id, key="failure", content=sensitive),
            profile(),
            authorized_context,
            summary_configuration(),
        )
    fake = FailingSummarizer()
    for _ in range(2):
        assert await process_summary_once(
            database_session_factory,
            fake,
            input_max_chars=1_000,
            output_max_chars=200,
            lease_seconds=60,
            max_attempts=2,
        )

    async with database_session_factory() as session:
        summary = await session.scalar(
            select(DocumentSummary).where(
                DocumentSummary.document_version_id == result.document_version_id
            )
        )
        events = (
            await session.scalars(
                select(AuditEvent).where(AuditEvent.event_type == "summarization.failed")
            )
        ).all()
    assert summary is not None
    assert summary.status == SummaryStatus.FAILED
    assert summary.attempt_count == 2
    assert summary.summary is None
    assert len(events) == 2
    assert all(sensitive not in str(event.metadata_) for event in events)


@pytest.mark.asyncio
async def test_expired_lease_recovers_and_oversized_input_never_calls_provider(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    async with database_session_factory() as session:
        result = await ingest_plain_text(
            session,
            command(client_id, key="lease", content="1234567890"),
            profile(),
            authorized_context,
            summary_configuration(),
        )
        async with session.begin():
            summary = await session.scalar(
                select(DocumentSummary).where(
                    DocumentSummary.document_version_id == result.document_version_id
                )
            )
            assert summary is not None
            summary.status = SummaryStatus.PROCESSING
            summary.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    fake = DeterministicFakeSummarizer()
    assert await process_summary_once(
        database_session_factory,
        fake,
        input_max_chars=5,
        output_max_chars=200,
        lease_seconds=60,
        max_attempts=3,
    )
    async with database_session_factory() as session:
        summary = await session.scalar(
            select(DocumentSummary).where(
                DocumentSummary.document_version_id == result.document_version_id
            )
        )
    assert summary is not None
    assert summary.status == SummaryStatus.FAILED
    assert summary.failure_code == "input_too_large"
    assert fake.calls == []


def test_summary_is_not_part_of_search_contract() -> None:
    from nevis.main import SearchResultResponse

    assert "summary" not in SearchResultResponse.model_fields


@pytest.mark.asyncio
async def test_enabling_generation_does_not_enqueue_existing_versions(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    async with database_session_factory() as session:
        await ingest_plain_text(
            session,
            command(client_id, key="before-enable", content="Existing version."),
            profile(),
            authorized_context,
        )
    fake = DeterministicFakeSummarizer()

    assert not await process_summary_once(
        database_session_factory,
        fake,
        input_max_chars=1_000,
        output_max_chars=200,
        lease_seconds=60,
        max_attempts=3,
    )
    assert fake.calls == []

    async with database_session_factory() as session:
        assert await session.scalar(select(DocumentSummary.id)) is None


@pytest.mark.asyncio
async def test_reconciliation_is_current_only_idempotent_and_dry_runnable(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    async with database_session_factory() as session:
        first = await ingest_plain_text(
            session,
            command(client_id, key="reconcile-v1", content="Historical version."),
            profile(),
            authorized_context,
        )
        second = await ingest_plain_text(
            session,
            command(client_id, key="reconcile-v2", content="Current version."),
            profile(),
            authorized_context,
        )

    async with database_session_factory() as session:
        preview = await reconcile_summary_work(
            session, settings(), dry_run=True, retry_failed=False, batch_size=100
        )
    assert preview.states[SummaryStatus.NOT_REQUESTED] == 1
    assert preview.created == 0

    async with database_session_factory() as session:
        applied = await reconcile_summary_work(
            session, settings(), dry_run=False, retry_failed=False, batch_size=100
        )
    assert applied.created == 1

    async with database_session_factory() as session:
        rows = (
            await session.scalars(select(DocumentSummary).order_by(DocumentSummary.queued_at))
        ).all()
    async with database_session_factory() as session:
        repeated = await reconcile_summary_work(
            session, settings(), dry_run=False, retry_failed=False, batch_size=100
        )
    assert [row.document_version_id for row in rows] == [second.document_version_id]
    assert first.document_version_id != second.document_version_id
    assert repeated.created == 0


@pytest.mark.asyncio
async def test_reconciliation_retries_failed_work_only_when_explicit(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    async with database_session_factory() as session:
        result = await ingest_plain_text(
            session,
            command(client_id, key="reconcile-failed", content="Current failed version."),
            profile(),
            authorized_context,
            summary_configuration(),
        )
        async with session.begin():
            summary = await session.scalar(
                select(DocumentSummary).where(
                    DocumentSummary.document_version_id == result.document_version_id
                )
            )
            assert summary is not None
            summary.status = SummaryStatus.FAILED
            summary.attempt_count = 3
            summary.failure_code = "provider_unavailable"

    async with database_session_factory() as session:
        unchanged = await reconcile_summary_work(
            session, settings(), dry_run=False, retry_failed=False, batch_size=100
        )
    assert unchanged.requeued == 0

    async with database_session_factory() as session:
        retried = await reconcile_summary_work(
            session,
            settings(),
            dry_run=False,
            retry_failed=True,
            batch_size=100,
            request_id="reconcile-retry",
        )
        summary = await session.scalar(
            select(DocumentSummary).where(
                DocumentSummary.document_version_id == result.document_version_id
            )
        )
        event = await session.scalar(
            select(AuditEvent).where(AuditEvent.request_id == "reconcile-retry")
        )
    assert retried.requeued == 1
    assert summary is not None
    assert summary.status == SummaryStatus.PENDING
    assert summary.attempt_count == 0
    assert summary.manual_requeue_count == 1
    assert event is not None
    assert event.metadata_["previous_failure_code"] == "provider_unavailable"

    async with database_session_factory() as session:
        async with session.begin():
            summary = await session.scalar(
                select(DocumentSummary).where(
                    DocumentSummary.document_version_id == result.document_version_id
                )
            )
            assert summary is not None
            summary.status = SummaryStatus.FAILED
            summary.attempt_count = 3
            summary.failure_code = "provider_unavailable"
    async with database_session_factory() as session:
        repeated_retry = await reconcile_summary_work(
            session,
            settings(),
            dry_run=False,
            retry_failed=True,
            batch_size=100,
            request_id="reconcile-retry-again",
        )
        summary = await session.scalar(
            select(DocumentSummary).where(
                DocumentSummary.document_version_id == result.document_version_id
            )
        )
    assert repeated_retry.requeued == 0
    assert summary is not None
    assert summary.status == SummaryStatus.FAILED
    assert summary.attempt_count == 3
    assert summary.manual_requeue_count == 1


@pytest.mark.asyncio
async def test_concurrent_reconciliation_does_not_duplicate_work(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    async with database_session_factory() as session:
        await ingest_plain_text(
            session,
            command(client_id, key="reconcile-concurrent", content="Concurrent version."),
            profile(),
            authorized_context,
        )

    async def run_reconciliation():
        async with database_session_factory() as session:
            return await reconcile_summary_work(
                session, settings(), dry_run=False, retry_failed=False, batch_size=100
            )

    results = await asyncio.gather(run_reconciliation(), run_reconciliation())
    async with database_session_factory() as session:
        rows = (await session.scalars(select(DocumentSummary))).all()
    assert len(rows) == 1
    assert sum(result.created for result in results) == 1


@pytest.mark.asyncio
async def test_reconciliation_requires_enabled_fictional_settings(
    database_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with database_session_factory() as session:
        with pytest.raises(ValueError, match="enabled fictional"):
            await reconcile_summary_work(
                session,
                Settings(_env_file=None),
                dry_run=True,
                retry_failed=False,
                batch_size=100,
            )


@pytest.mark.asyncio
async def test_summary_worker_heartbeat_gates_enabled_readiness(
    database_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    configured = settings()
    provider = DeterministicFakeProvider(profile())

    missing, missing_statuses = await readiness(
        database_session_factory, provider, settings=configured
    )
    assert not missing
    assert {item.name: item.available for item in missing_statuses}["summary_worker"] is False

    await publish_summary_worker_heartbeat(database_session_factory, configured)
    available, statuses = await readiness(database_session_factory, provider, settings=configured)
    assert available
    assert {item.name: item.available for item in statuses}["summary_worker"] is True

    mismatched = settings(llm_model="different-model")
    available, statuses = await readiness(database_session_factory, provider, settings=mismatched)
    assert not available
    assert {item.name: item.available for item in statuses}["summary_worker"] is False

    async with database_session_factory() as session:
        async with session.begin():
            heartbeat = await session.get(RuntimeCapability, "summary-worker")
            assert heartbeat is not None
            heartbeat.heartbeat_at = datetime.now(UTC) - timedelta(minutes=5)
    available, statuses = await readiness(database_session_factory, provider, settings=configured)
    assert not available
    assert {item.name: item.available for item in statuses}["summary_worker"] is False


@pytest.mark.asyncio
async def test_disabled_summaries_do_not_require_worker_heartbeat(
    database_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    available, statuses = await readiness(
        database_session_factory,
        DeterministicFakeProvider(profile()),
        settings=Settings(_env_file=None),
    )
    assert available
    assert "summary_worker" not in {item.name for item in statuses}


@pytest.mark.asyncio
async def test_summary_diagnostics_are_aggregate_and_redacted(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    sensitive = "diagnostic-secret-content"
    async with database_session_factory() as session:
        result = await ingest_plain_text(
            session,
            command(client_id, key="diagnostic-failed", content=sensitive),
            profile(),
            authorized_context,
            summary_configuration(),
        )
        await ingest_plain_text(
            session,
            command(
                client_id,
                key="diagnostic-oversized",
                content="x" * (settings().document_summary_input_max_chars + 1),
                external_document_id="oversized-document",
            ),
            profile(),
            authorized_context,
        )
        async with session.begin():
            summary = await session.scalar(
                select(DocumentSummary).where(
                    DocumentSummary.document_version_id == result.document_version_id
                )
            )
            assert summary is not None
            summary.status = SummaryStatus.FAILED
            summary.failure_code = "provider_unavailable"

    configured = settings()
    await publish_summary_worker_heartbeat(database_session_factory, configured)
    async with database_session_factory() as session:
        diagnostics = await get_summary_diagnostics(session, configured)

    assert diagnostics.states[SummaryStatus.FAILED] == 1
    assert diagnostics.states[SummaryStatus.NOT_REQUESTED] == 1
    assert diagnostics.failure_codes == {"provider_unavailable": 1}
    assert diagnostics.heartbeat_fresh
    assert diagnostics.capability_match
    assert sensitive not in str(diagnostics)
