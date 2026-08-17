import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nevis.domain.authorization import AuthorizationAction, AuthorizationDecision
from nevis.domain.documents import DEFAULT_CHUNKING, chunk_text, content_hash
from nevis.domain.embeddings import EmbeddingProfileIdentity, EmbeddingProvider
from nevis.domain.summarization import (
    DocumentSummarizer,
    SummarizationError,
    SummaryResult,
    normalize_summary,
    summary_capability_hash,
)
from nevis.infrastructure.database import build_engine, build_session_factory
from nevis.infrastructure.embeddings import EmbeddingProviderUnavailable, LocalTEIProvider
from nevis.infrastructure.logging import configure_logging
from nevis.infrastructure.models import DocumentVersion, EmbeddingProfile
from nevis.infrastructure.repositories import (
    add_document_chunk,
    append_audit_event,
    claim_indexing_job,
    complete_indexing_job,
    existing_chunk_ordinals,
    fail_indexing_job,
)
from nevis.infrastructure.summarization import OpenAICompatibleSummarizer
from nevis.infrastructure.summary_repository import (
    claim_document_summary,
    complete_document_summary,
    fail_document_summary,
    upsert_runtime_capability,
)
from nevis.settings import Settings, get_settings

EMBEDDING_REQUEST_BATCH_SIZE = 32


async def publish_summary_worker_heartbeat(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    identity_hash = summary_capability_hash(
        enabled=settings.document_summaries_enabled,
        provider=settings.llm_provider,
        model=settings.llm_model,
        prompt_version=settings.document_summary_prompt_version,
    )
    async with session_factory() as session:
        async with session.begin():
            await upsert_runtime_capability(
                session,
                role="summary-worker",
                identity_hash=identity_hash,
                enabled=settings.document_summaries_enabled,
            )


async def process_indexing_once(
    session_factory: async_sessionmaker[AsyncSession], provider: EmbeddingProvider
) -> bool:
    async with session_factory() as session:
        async with session.begin():
            job = await claim_indexing_job(session)
            if job is None:
                return False
            version = await session.get(DocumentVersion, job.document_version_id)
            profile = await session.get(EmbeddingProfile, job.embedding_profile_id)
            if version is None or profile is None:
                await fail_indexing_job(session, job, "missing_lineage")
                return True
            if profile.dimensions != provider.profile.dimensions:
                await fail_indexing_job(session, job, "embedding_profile_mismatch")
                return True
            chunks = chunk_text(version.content)
            existing = await existing_chunk_ordinals(session, version.id, profile.id)
            pending = [
                (ordinal, item) for ordinal, item in enumerate(chunks) if ordinal not in existing
            ]
            try:
                vectors: list[list[float]] = []
                for start in range(0, len(pending), EMBEDDING_REQUEST_BATCH_SIZE):
                    batch = pending[start : start + EMBEDDING_REQUEST_BATCH_SIZE]
                    vectors.extend(await provider.embed_documents([item[2] for _, item in batch]))
            except EmbeddingProviderUnavailable:
                await fail_indexing_job(session, job, "embedding_runtime_unavailable")
                await append_audit_event(
                    session,
                    event_type="indexing.failed",
                    request_id=str(job.id),
                    decision=AuthorizationDecision(
                        tenant_id=job.tenant_id,
                        advisor_id=None,
                        action=AuthorizationAction.DOCUMENT_INGEST,
                        policy=job.authorization_policy,
                        result=job.authorization_result,
                        decision_id=job.authorization_decision_id,
                    ),
                    metadata={
                        "job_id": str(job.id),
                        "failure_code": "embedding_runtime_unavailable",
                    },
                )
                return True
            for (ordinal, (start, end, text)), vector in zip(pending, vectors, strict=True):
                await add_document_chunk(
                    session,
                    job=job,
                    ordinal=ordinal,
                    start_offset=start,
                    end_offset=end,
                    content=text,
                    content_sha256=content_hash(text),
                    chunking_version=DEFAULT_CHUNKING.version,
                    embedding=vector,
                )
            await complete_indexing_job(session, job)
            await append_audit_event(
                session,
                event_type="indexing.completed",
                request_id=str(job.id),
                decision=AuthorizationDecision(
                    tenant_id=job.tenant_id,
                    advisor_id=None,
                    action=AuthorizationAction.DOCUMENT_INGEST,
                    policy=job.authorization_policy,
                    result=job.authorization_result,
                    decision_id=job.authorization_decision_id,
                ),
                metadata={"job_id": str(job.id), "chunk_count": len(chunks)},
            )
            return True


async def process_summary_once(
    session_factory: async_sessionmaker[AsyncSession],
    summarizer: DocumentSummarizer,
    *,
    input_max_chars: int,
    output_max_chars: int,
    lease_seconds: int,
    max_attempts: int,
) -> bool:
    async with session_factory() as session:
        async with session.begin():
            summary = await claim_document_summary(
                session, lease_seconds=lease_seconds, max_attempts=max_attempts
            )
            if summary is None:
                return False
            version = await session.get(DocumentVersion, summary.document_version_id)
            if version is None:
                await fail_document_summary(session, summary, "missing_lineage", retry=False)
                return True
            if not version.content.strip():
                await fail_document_summary(session, summary, "empty_input", retry=False)
                return True
            if len(version.content) > input_max_chars:
                await fail_document_summary(session, summary, "input_too_large", retry=False)
                return True
            try:
                result = await summarizer.summarize(version.content)
                bounded = normalize_summary(result.text, max_chars=output_max_chars)
            except SummarizationError as error:
                code = str(error)
                safe_code = (
                    code
                    if code
                    in {
                        "empty_response",
                        "invalid_response",
                        "output_too_large",
                        "provider_unavailable",
                        "too_many_sentences",
                    }
                    else "generation_failed"
                )
                await fail_document_summary(
                    session,
                    summary,
                    safe_code,
                    retry=summary.attempt_count < max_attempts,
                )
                await append_audit_event(
                    session,
                    event_type="summarization.failed",
                    request_id=str(summary.id),
                    decision=AuthorizationDecision(
                        tenant_id=version.tenant_id,
                        advisor_id=None,
                        action=AuthorizationAction.DOCUMENT_INGEST,
                        policy=version.authorization_policy,
                        result=version.authorization_result,
                        decision_id=version.authorization_decision_id,
                    ),
                    metadata={"summary_id": str(summary.id), "failure_code": safe_code},
                )
                return True
            await complete_document_summary(
                session,
                summary,
                SummaryResult(bounded, result.provider, result.model, result.prompt_version),
            )
            await append_audit_event(
                session,
                event_type="summarization.completed",
                request_id=str(summary.id),
                decision=AuthorizationDecision(
                    tenant_id=version.tenant_id,
                    advisor_id=None,
                    action=AuthorizationAction.DOCUMENT_INGEST,
                    policy=version.authorization_policy,
                    result=version.authorization_result,
                    decision_id=version.authorization_decision_id,
                ),
                metadata={"summary_id": str(summary.id), "document_version_id": str(version.id)},
            )
            return True


async def process_work_once(
    session_factory: async_sessionmaker[AsyncSession],
    provider: EmbeddingProvider,
    summarizer: DocumentSummarizer | None,
    settings: Settings,
) -> bool:
    if await process_indexing_once(session_factory, provider):
        return True
    if summarizer is None:
        return False
    return await process_summary_once(
        session_factory,
        summarizer,
        input_max_chars=settings.document_summary_input_max_chars,
        output_max_chars=settings.document_summary_output_max_chars,
        lease_seconds=settings.document_summary_lease_seconds,
        max_attempts=settings.document_summary_max_attempts,
    )


async def serve() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = structlog.get_logger(__name__)
    logger.info("worker_started", environment=settings.environment)
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    provider = LocalTEIProvider(
        str(settings.tei_base_url),
        EmbeddingProfileIdentity(
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            model_revision=settings.embedding_model_revision,
            dimensions=settings.embedding_dimensions,
            normalization=settings.embedding_normalization,
            chunking_version=settings.embedding_chunking_version,
            pipeline_version=settings.embedding_pipeline_version,
        ),
    )
    summarizer = None
    if settings.document_summaries_enabled:
        assert settings.llm_api_key is not None
        summarizer = OpenAICompatibleSummarizer(
            api_key=settings.llm_api_key,
            provider=settings.llm_provider,
            model=settings.llm_model,
            endpoint=settings.llm_endpoint,
            prompt_version=settings.document_summary_prompt_version,
            input_max_chars=settings.document_summary_input_max_chars,
            output_max_chars=settings.document_summary_output_max_chars,
            max_tokens=settings.document_summary_provider_max_tokens,
            timeout_seconds=settings.document_summary_timeout_seconds,
        )
    try:
        loop = asyncio.get_running_loop()
        next_heartbeat = 0.0
        while True:
            if loop.time() >= next_heartbeat:
                await publish_summary_worker_heartbeat(session_factory, settings)
                next_heartbeat = loop.time() + settings.summary_worker_heartbeat_interval_seconds
            worked = await process_work_once(session_factory, provider, summarizer, settings)
            if not worked:
                await asyncio.sleep(0.5)
    finally:
        await engine.dispose()


def run() -> None:
    asyncio.run(serve())
