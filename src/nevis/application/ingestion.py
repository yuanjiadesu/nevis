import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from nevis.domain.authorization import AuthorizationContext
from nevis.domain.documents import (
    DocumentAssociationConflict,
    DocumentNotFound,
    DocumentResource,
    DocumentVersionStatus,
    IdempotencyConflict,
    IndexingStatus,
    IngestionCommand,
    IngestionOutcome,
    IngestionResult,
    content_hash,
    normalize_text,
    request_fingerprint,
)
from nevis.domain.embeddings import EmbeddingProfileIdentity
from nevis.infrastructure.repositories import (
    append_audit_event,
    count_chunks_for_version,
    create_document_version,
    create_indexing_job,
    ensure_active_embedding_profile,
    get_client,
    get_document_resource_rows,
    get_document_version,
    get_indexing_job_for_version,
    get_ingestion_request,
    get_latest_document_version,
    get_or_create_document,
    get_or_create_source,
    record_ingestion_request,
)


async def ingest_plain_text(
    session: AsyncSession,
    command: IngestionCommand,
    profile_identity: EmbeddingProfileIdentity,
    authorization: AuthorizationContext,
) -> IngestionResult:
    normalized = normalize_text(command.content)
    if not normalized:
        raise ValueError("content must not be empty")
    fingerprint = request_fingerprint(command)
    async with session.begin():
        decision = authorization.decision
        client = await get_client(session, authorization.tenant_id, command.client_id)
        if client is None:
            await append_audit_event(
                session,
                event_type="ingestion.client_not_found",
                request_id=command.request_id,
                decision=decision,
                metadata={"reason": "client_not_found"},
            )
            raise DocumentNotFound("client not found")
        existing = await get_ingestion_request(
            session, authorization.tenant_id, command.idempotency_key
        )
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                await append_audit_event(
                    session,
                    event_type="ingestion.rejected",
                    request_id=command.request_id,
                    decision=decision,
                    metadata={"reason": "idempotency_conflict"},
                )
                raise IdempotencyConflict("idempotency key was already used for another request")
            version = await get_document_version(session, existing.document_version_id)
            job = await get_indexing_job_for_version(session, existing.document_version_id)
            if version is None or job is None:
                raise RuntimeError("idempotency record has incomplete lineage")
            await append_audit_event(
                session,
                event_type="ingestion.replayed",
                request_id=command.request_id,
                decision=decision,
                metadata={"document_version_id": str(version.id)},
            )
            return IngestionResult(
                client_id=command.client_id,
                document_id=version.document_id,
                document_version_id=version.id,
                version_number=version.version_number,
                indexing_status=IndexingStatus(job.status),
                outcome=IngestionOutcome.REPLAYED,
            )

        source = await get_or_create_source(
            session, authorization.tenant_id, command.source_reference.strip()
        )
        document = await get_or_create_document(
            session,
            tenant_id=authorization.tenant_id,
            source=source,
            external_document_id=command.external_document_id.strip(),
            title=command.title.strip(),
            client_id=command.client_id,
        )
        if document.client_id != command.client_id:
            await append_audit_event(
                session,
                event_type="ingestion.rejected",
                request_id=command.request_id,
                decision=decision,
                metadata={"reason": "client_association_conflict"},
            )
            raise DocumentAssociationConflict("document client association conflict")
        latest = await get_latest_document_version(session, document.id)
        normalized_hash = content_hash(normalized)
        if latest is not None and latest.content_hash == normalized_hash:
            await record_ingestion_request(
                session,
                tenant_id=authorization.tenant_id,
                idempotency_key=command.idempotency_key,
                fingerprint=fingerprint,
                document_version_id=latest.id,
            )
            job = await get_indexing_job_for_version(session, latest.id)
            if job is None:
                raise RuntimeError("existing version has no indexing job")
            await append_audit_event(
                session,
                event_type="ingestion.replayed",
                request_id=command.request_id,
                decision=decision,
                metadata={"document_version_id": str(latest.id)},
            )
            return IngestionResult(
                client_id=command.client_id,
                document_id=document.id,
                document_version_id=latest.id,
                version_number=latest.version_number,
                indexing_status=IndexingStatus(job.status),
                outcome=IngestionOutcome.REPLAYED,
            )

        profile = await ensure_active_embedding_profile(session, profile_identity)
        version = await create_document_version(
            session,
            tenant_id=authorization.tenant_id,
            source_id=source.id,
            document_id=document.id,
            version_number=1 if latest is None else latest.version_number + 1,
            content=normalized,
            content_sha256=normalized_hash,
            decision=decision,
        )
        await create_indexing_job(
            session,
            tenant_id=authorization.tenant_id,
            source_id=source.id,
            document_id=document.id,
            version=version,
            profile=profile,
            decision=decision,
        )
        await record_ingestion_request(
            session,
            tenant_id=authorization.tenant_id,
            idempotency_key=command.idempotency_key,
            fingerprint=fingerprint,
            document_version_id=version.id,
        )
        await append_audit_event(
            session,
            event_type="ingestion.accepted",
            request_id=command.request_id,
            decision=decision,
            metadata={"document_id": str(document.id), "document_version_id": str(version.id)},
        )
        return IngestionResult(
            client_id=command.client_id,
            document_id=document.id,
            document_version_id=version.id,
            version_number=version.version_number,
            indexing_status=IndexingStatus.QUEUED,
            outcome=IngestionOutcome.ACCEPTED,
        )


async def document_version_status(
    session: AsyncSession, version_id: uuid.UUID, authorization: AuthorizationContext
) -> DocumentVersionStatus:
    version = await get_document_version(session, version_id, authorization.tenant_id)
    if version is None:
        raise DocumentNotFound("document version was not found")
    job = await get_indexing_job_for_version(session, version_id, authorization.tenant_id)
    if job is None:
        raise DocumentNotFound("document version was not found")
    return DocumentVersionStatus(
        document_version_id=version.id,
        document_id=version.document_id,
        version_number=version.version_number,
        indexing_status=IndexingStatus(job.status),
        queued_at=job.queued_at.isoformat() if job.queued_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        failed_at=job.failed_at.isoformat() if job.failed_at else None,
        failure_code=job.failure_code,
        chunk_count=await count_chunks_for_version(session, version_id),
    )


async def retrieve_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    authorization: AuthorizationContext,
    request_id: str,
) -> DocumentResource:
    row = await get_document_resource_rows(session, authorization.tenant_id, document_id)
    if row is None:
        await append_audit_event(
            session,
            event_type="document.not_found",
            request_id=request_id,
            decision=authorization.decision,
            metadata={"reason": "not_found"},
        )
        await session.commit()
        raise DocumentNotFound("document not found")
    document, source, version, job = row
    await append_audit_event(
        session,
        event_type="document.found",
        request_id=request_id,
        decision=authorization.decision,
        metadata={"document_id": str(document.id)},
    )
    await session.commit()
    assert authorization.decision.decision_id is not None
    return DocumentResource(
        document_id=document.id,
        tenant_id=document.tenant_id,
        client_id=document.client_id,
        source_id=source.id,
        source_reference=source.source_reference,
        external_document_id=document.external_document_id,
        title=document.title,
        current_document_version_id=version.id,
        current_version_number=version.version_number,
        indexing_status=IndexingStatus(job.status),
        ingestion_authorization_decision_id=version.authorization_decision_id,
        retrieval_authorization_decision_id=authorization.decision.decision_id,
        created_at=document.created_at.isoformat(),
    )
