import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nevis.application.ingestion import ingest_plain_text
from nevis.domain.documents import IdempotencyConflict, IndexingStatus, IngestionCommand
from nevis.domain.embeddings import EmbeddingProfileIdentity
from nevis.infrastructure.embeddings import DeterministicFakeProvider, EmbeddingProviderUnavailable
from nevis.infrastructure.models import DocumentChunk, IndexingJob
from nevis.workers.main import process_indexing_once


def command(
    client_id: uuid.UUID, *, key: str = "key-1", content: str = "one two three"
) -> IngestionCommand:
    return IngestionCommand(
        client_id, "crm", "client-1", "Client note", content, key, str(uuid.uuid4())
    )


def profile() -> EmbeddingProfileIdentity:
    return EmbeddingProfileIdentity("fake", "fixture", "1", 384, "l2", 1, 1)


@pytest.mark.asyncio
async def test_ingestion_is_idempotent_and_versions_content(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    async with database_session_factory() as session:
        first = await ingest_plain_text(session, command(client_id), profile(), authorized_context)
    async with database_session_factory() as session:
        replay = await ingest_plain_text(session, command(client_id), profile(), authorized_context)
    assert replay.document_version_id == first.document_version_id
    assert replay.indexing_status == IndexingStatus.QUEUED
    async with database_session_factory() as session:
        changed = await ingest_plain_text(
            session,
            command(client_id, key="key-2", content="changed"),
            profile(),
            authorized_context,
        )
    assert changed.version_number == 2
    async with database_session_factory() as session:
        with pytest.raises(IdempotencyConflict):
            await ingest_plain_text(
                session, command(client_id, content="conflict"), profile(), authorized_context
            )


@pytest.mark.asyncio
async def test_worker_persists_complete_lineage_and_retries_safely(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    async with database_session_factory() as session:
        result = await ingest_plain_text(
            session, command(client_id, content="x" * 1_200), profile(), authorized_context
        )
    provider = DeterministicFakeProvider(profile())
    assert await process_indexing_once(database_session_factory, provider)
    assert not await process_indexing_once(database_session_factory, provider)
    async with database_session_factory() as session:
        job = await session.scalar(
            select(IndexingJob).where(IndexingJob.document_version_id == result.document_version_id)
        )
        chunks = (
            await session.scalars(
                select(DocumentChunk).where(
                    DocumentChunk.document_version_id == result.document_version_id
                )
            )
        ).all()
    assert job is not None and job.status == IndexingStatus.COMPLETED
    assert len(chunks) == 2
    assert all(chunk.embedding_profile_id == job.embedding_profile_id for chunk in chunks)
    assert all(
        chunk.authorization_decision_id == authorized_context.decision.decision_id
        for chunk in chunks
    )


class FailingFakeProvider(DeterministicFakeProvider):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingProviderUnavailable("fixture failure")


@pytest.mark.asyncio
async def test_worker_records_provider_failure_and_recovers_expired_lease(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    async with database_session_factory() as session:
        failed = await ingest_plain_text(
            session, command(client_id, key="failure"), profile(), authorized_context
        )
    assert await process_indexing_once(database_session_factory, FailingFakeProvider(profile()))
    async with database_session_factory() as session:
        failed_job = await session.scalar(
            select(IndexingJob).where(IndexingJob.document_version_id == failed.document_version_id)
        )
    assert failed_job is not None and failed_job.status == IndexingStatus.FAILED

    async with database_session_factory() as session:
        recovered = await ingest_plain_text(
            session, command(client_id, key="recovery"), profile(), authorized_context
        )
        async with session.begin():
            job = await session.scalar(
                select(IndexingJob).where(
                    IndexingJob.document_version_id == recovered.document_version_id
                )
            )
            assert job is not None
            job.status = IndexingStatus.PROCESSING
            job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert await process_indexing_once(
        database_session_factory, DeterministicFakeProvider(profile())
    )
    async with database_session_factory() as session:
        recovered_job = await session.scalar(
            select(IndexingJob).where(
                IndexingJob.document_version_id == recovered.document_version_id
            )
        )
    assert recovered_job is not None and recovered_job.status == IndexingStatus.COMPLETED
