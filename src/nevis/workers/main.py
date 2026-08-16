import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nevis.domain.authorization import AuthorizationAction, AuthorizationDecision
from nevis.domain.documents import DEFAULT_CHUNKING, chunk_text, content_hash
from nevis.domain.embeddings import EmbeddingProfileIdentity, EmbeddingProvider
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
from nevis.settings import get_settings


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
                vectors = await provider.embed_documents([item[2] for _, item in pending])
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
    try:
        while True:
            worked = await process_indexing_once(session_factory, provider)
            if not worked:
                await asyncio.sleep(0.5)
    finally:
        await engine.dispose()


def run() -> None:
    asyncio.run(serve())
