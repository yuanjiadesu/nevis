from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from nevis.domain.summarization import SummaryResult, SummaryStatus
from nevis.infrastructure.models import DocumentSummary, DocumentVersion, RuntimeCapability


async def create_document_summary(
    session: AsyncSession,
    *,
    version: DocumentVersion,
    provider: str,
    model: str,
    prompt_version: str,
) -> DocumentSummary:
    summary = DocumentSummary(
        document_version_id=version.id,
        status=SummaryStatus.PENDING,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
    )
    session.add(summary)
    await session.flush()
    return summary


def _current_version_predicate() -> ColumnElement[bool]:
    newer = aliased(DocumentVersion)
    return (
        ~select(newer.id)
        .where(
            newer.document_id == DocumentVersion.document_id,
            newer.version_number > DocumentVersion.version_number,
        )
        .exists()
    )


def _eligible_current_version_predicate(input_max_chars: int) -> tuple[ColumnElement[bool], ...]:
    return (
        _current_version_predicate(),
        func.length(func.btrim(DocumentVersion.content)) > 0,
        func.length(DocumentVersion.content) <= input_max_chars,
    )


async def summary_lifecycle_counts(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(
        select(DocumentSummary.status, func.count(DocumentVersion.id))
        .select_from(DocumentVersion)
        .outerjoin(DocumentSummary, DocumentSummary.document_version_id == DocumentVersion.id)
        .where(_current_version_predicate())
        .group_by(DocumentSummary.status)
    )
    counts = {status.value: 0 for status in SummaryStatus}
    for status, count in rows:
        key = str(status) if status is not None else SummaryStatus.NOT_REQUESTED.value
        counts[key] = int(count)
    return counts


async def create_missing_current_summaries(
    session: AsyncSession,
    *,
    provider: str,
    model: str,
    prompt_version: str,
    input_max_chars: int,
    limit: int,
) -> int:
    version_ids = list(
        await session.scalars(
            select(DocumentVersion.id)
            .outerjoin(DocumentSummary, DocumentSummary.document_version_id == DocumentVersion.id)
            .where(
                DocumentSummary.id.is_(None),
                *_eligible_current_version_predicate(input_max_chars),
            )
            .order_by(DocumentVersion.created_at, DocumentVersion.id)
            .with_for_update(skip_locked=True, of=DocumentVersion)
            .limit(limit)
        )
    )
    if not version_ids:
        return 0
    result = await session.scalars(
        pg_insert(DocumentSummary)
        .values(
            [
                {
                    "document_version_id": version_id,
                    "status": SummaryStatus.PENDING,
                    "provider": provider,
                    "model": model,
                    "prompt_version": prompt_version,
                }
                for version_id in version_ids
            ]
        )
        .on_conflict_do_nothing(index_elements=[DocumentSummary.document_version_id])
        .returning(DocumentSummary.id)
    )
    return len(result.all())


async def requeue_failed_current_summaries(
    session: AsyncSession, *, input_max_chars: int, limit: int
) -> list[tuple[DocumentSummary, DocumentVersion, str | None]]:
    rows = (
        await session.execute(
            select(DocumentSummary, DocumentVersion)
            .join(DocumentVersion, DocumentVersion.id == DocumentSummary.document_version_id)
            .where(
                DocumentSummary.status == SummaryStatus.FAILED,
                DocumentSummary.manual_requeue_count < 1,
                *_eligible_current_version_predicate(input_max_chars),
            )
            .order_by(DocumentSummary.failed_at, DocumentSummary.id)
            .with_for_update(skip_locked=True, of=DocumentSummary)
            .limit(limit)
        )
    ).all()
    now = datetime.now(UTC)
    requeued: list[tuple[DocumentSummary, DocumentVersion, str | None]] = []
    for summary, version in rows:
        previous_failure = summary.failure_code
        summary.status = SummaryStatus.PENDING
        summary.summary = None
        summary.attempt_count = 0
        summary.manual_requeue_count += 1
        summary.lease_expires_at = None
        summary.failure_code = None
        summary.queued_at = now
        summary.started_at = None
        summary.completed_at = None
        summary.failed_at = None
        summary.updated_at = now
        requeued.append((summary, version, previous_failure))
    await session.flush()
    return requeued


async def upsert_runtime_capability(
    session: AsyncSession, *, role: str, identity_hash: str, enabled: bool
) -> None:
    now = datetime.now(UTC)
    await session.execute(
        pg_insert(RuntimeCapability)
        .values(
            role=role,
            identity_hash=identity_hash,
            enabled=enabled,
            heartbeat_at=now,
        )
        .on_conflict_do_update(
            index_elements=[RuntimeCapability.role],
            set_={
                "identity_hash": identity_hash,
                "enabled": enabled,
                "heartbeat_at": now,
            },
        )
    )


async def get_runtime_capability(session: AsyncSession, role: str) -> RuntimeCapability | None:
    return cast(RuntimeCapability | None, await session.get(RuntimeCapability, role))


async def summary_failure_counts(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(
        select(DocumentSummary.failure_code, func.count(DocumentSummary.id))
        .join(DocumentVersion, DocumentVersion.id == DocumentSummary.document_version_id)
        .where(
            DocumentSummary.status == SummaryStatus.FAILED,
            _current_version_predicate(),
        )
        .group_by(DocumentSummary.failure_code)
    )
    return {str(code or "unknown"): int(count) for code, count in rows}


async def claim_document_summary(
    session: AsyncSession, *, lease_seconds: int, max_attempts: int
) -> DocumentSummary | None:
    now = datetime.now(UTC)
    summary = await session.scalar(
        select(DocumentSummary)
        .where(
            DocumentSummary.attempt_count < max_attempts,
            or_(
                DocumentSummary.status == SummaryStatus.PENDING,
                and_(
                    DocumentSummary.status == SummaryStatus.PROCESSING,
                    DocumentSummary.lease_expires_at < now,
                ),
            ),
        )
        .order_by(DocumentSummary.queued_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if summary is None:
        return None
    summary.status = SummaryStatus.PROCESSING
    summary.attempt_count += 1
    summary.started_at = now
    summary.lease_expires_at = now + timedelta(seconds=lease_seconds)
    summary.failure_code = None
    summary.updated_at = now
    await session.flush()
    return summary


async def complete_document_summary(
    session: AsyncSession, summary: DocumentSummary, result: SummaryResult
) -> None:
    now = datetime.now(UTC)
    summary.status = SummaryStatus.READY
    summary.summary = result.text
    summary.provider = result.provider
    summary.model = result.model
    summary.prompt_version = result.prompt_version
    summary.completed_at = now
    summary.failed_at = None
    summary.failure_code = None
    summary.lease_expires_at = None
    summary.updated_at = now
    await session.flush()


async def fail_document_summary(
    session: AsyncSession,
    summary: DocumentSummary,
    failure_code: str,
    *,
    retry: bool,
) -> None:
    now = datetime.now(UTC)
    summary.summary = None
    summary.failure_code = failure_code
    summary.lease_expires_at = None
    summary.updated_at = now
    if retry:
        summary.status = SummaryStatus.PENDING
    else:
        summary.status = SummaryStatus.FAILED
        summary.failed_at = now
    await session.flush()
