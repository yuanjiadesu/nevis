import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from nevis.domain.authorization import AuthorizationAction, AuthorizationDecision
from nevis.domain.summarization import (
    SummaryDiagnostics,
    SummaryReconciliationResult,
    summary_capability_hash,
)
from nevis.infrastructure.repositories import (
    append_audit_event,
)
from nevis.infrastructure.summary_repository import (
    create_missing_current_summaries,
    get_runtime_capability,
    requeue_failed_current_summaries,
    summary_failure_counts,
    summary_lifecycle_counts,
)
from nevis.settings import Settings


async def reconcile_summary_work(
    session: AsyncSession,
    settings: Settings,
    *,
    dry_run: bool,
    retry_failed: bool,
    batch_size: int,
    request_id: str | None = None,
) -> SummaryReconciliationResult:
    if not settings.document_summaries_enabled or not settings.fictional_test_data:
        raise ValueError("summary reconciliation requires enabled fictional summaries")
    if batch_size < 1 or batch_size > 10_000:
        raise ValueError("batch_size must be between 1 and 10000")

    async with session.begin():
        states = await summary_lifecycle_counts(session)
        if dry_run:
            return SummaryReconciliationResult(states, 0, 0, True)
        created = await create_missing_current_summaries(
            session,
            provider=settings.llm_provider,
            model=settings.llm_model,
            prompt_version=settings.document_summary_prompt_version,
            input_max_chars=settings.document_summary_input_max_chars,
            limit=batch_size,
        )
        requeued = []
        if retry_failed:
            requeued = await requeue_failed_current_summaries(
                session,
                input_max_chars=settings.document_summary_input_max_chars,
                limit=batch_size,
            )
            for summary, version, previous_failure in requeued:
                await append_audit_event(
                    session,
                    event_type="summarization.requeued",
                    request_id=request_id or str(uuid.uuid4()),
                    decision=AuthorizationDecision(
                        tenant_id=version.tenant_id,
                        advisor_id=None,
                        action=AuthorizationAction.DOCUMENT_INGEST,
                        policy=version.authorization_policy,
                        result=version.authorization_result,
                        decision_id=version.authorization_decision_id,
                    ),
                    metadata={
                        "summary_id": str(summary.id),
                        "previous_failure_code": previous_failure,
                    },
                )
        states = await summary_lifecycle_counts(session)
        return SummaryReconciliationResult(states, created, len(requeued), False)


async def get_summary_diagnostics(session: AsyncSession, settings: Settings) -> SummaryDiagnostics:
    states = await summary_lifecycle_counts(session)
    failures = await summary_failure_counts(session)
    heartbeat = await get_runtime_capability(session, "summary-worker")
    expected = summary_capability_hash(
        enabled=settings.document_summaries_enabled,
        provider=settings.llm_provider,
        model=settings.llm_model,
        prompt_version=settings.document_summary_prompt_version,
    )
    age = None
    if heartbeat is not None:
        age = max(0, int((datetime.now(UTC) - heartbeat.heartbeat_at).total_seconds()))
    return SummaryDiagnostics(
        enabled=settings.document_summaries_enabled,
        states=states,
        failure_codes=failures,
        heartbeat_fresh=(
            age is not None and age <= settings.summary_worker_heartbeat_freshness_seconds
        ),
        capability_match=heartbeat is not None and heartbeat.identity_hash == expected,
        heartbeat_age_seconds=age,
    )
