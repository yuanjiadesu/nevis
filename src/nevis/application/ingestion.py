import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from nevis.domain.authorization import AuthorizationContext
from nevis.domain.documents import (
    DocumentAssociationConflict,
    DocumentNotFound,
    DocumentResource,
    DocumentTimelineItem,
    DocumentVersionContent,
    DocumentVersionStatus,
    DocumentVersionTimelineItem,
    EditableDocument,
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
from nevis.domain.summarization import SummaryConfiguration, SummaryStatus
from nevis.infrastructure.repositories import (
    acquire_ingestion_locks,
    append_audit_event,
    count_chunks_for_version,
    create_document_version,
    create_indexing_job,
    ensure_active_embedding_profile,
    get_client,
    get_client_document_rows,
    get_document_resource_rows,
    get_document_version,
    get_document_version_rows,
    get_indexing_job_for_version,
    get_ingestion_request,
    get_latest_document_version,
    get_or_create_document,
    get_or_create_source,
    record_ingestion_request,
    update_document_title,
)
from nevis.infrastructure.summary_repository import create_document_summary


async def ingest_plain_text(
    session: AsyncSession,
    command: IngestionCommand,
    profile_identity: EmbeddingProfileIdentity,
    authorization: AuthorizationContext,
    summary_configuration: SummaryConfiguration | None = None,
    *,
    revision_document_id: uuid.UUID | None = None,
) -> IngestionResult:
    normalized = normalize_text(command.content)
    if not normalized:
        raise ValueError("content must not be empty")
    source_reference = command.source_reference.strip()
    external_document_id = command.external_document_id.strip()
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
        await acquire_ingestion_locks(
            session,
            tenant_id=authorization.tenant_id,
            idempotency_key=command.idempotency_key,
            source_reference=source_reference,
            external_document_id=external_document_id,
        )
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
            if revision_document_id is not None:
                if version.document_id != revision_document_id:
                    raise DocumentNotFound("document not found")
                updated = await update_document_title(
                    session,
                    authorization.tenant_id,
                    revision_document_id,
                    command.title.strip(),
                )
                if updated is None:
                    raise DocumentNotFound("document not found")
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

        source = await get_or_create_source(session, authorization.tenant_id, source_reference)
        document = await get_or_create_document(
            session,
            tenant_id=authorization.tenant_id,
            source=source,
            external_document_id=external_document_id,
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
        if revision_document_id is not None:
            if document.id != revision_document_id:
                raise DocumentNotFound("document not found")
            updated = await update_document_title(
                session,
                authorization.tenant_id,
                revision_document_id,
                command.title.strip(),
            )
            if updated is None:
                raise DocumentNotFound("document not found")
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
        if summary_configuration is not None and summary_configuration.enabled:
            await create_document_summary(
                session,
                version=version,
                provider=summary_configuration.provider,
                model=summary_configuration.model,
                prompt_version=summary_configuration.prompt_version,
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


async def retrieve_document_version_content(
    session: AsyncSession,
    version_id: uuid.UUID,
    authorization: AuthorizationContext,
    request_id: str,
) -> DocumentVersionContent:
    version = await get_document_version(session, version_id, authorization.tenant_id)
    if version is None:
        await append_audit_event(
            session,
            event_type="document.version_content_not_found",
            request_id=request_id,
            decision=authorization.decision,
            metadata={"reason": "not_found"},
        )
        await session.commit()
        raise DocumentNotFound("document version not found")
    await append_audit_event(
        session,
        event_type="document.version_content_found",
        request_id=request_id,
        decision=authorization.decision,
        metadata={
            "document_id": str(version.document_id),
            "version_number": version.version_number,
        },
    )
    await session.commit()
    return DocumentVersionContent(
        document_version_id=version.id,
        document_id=version.document_id,
        version_number=version.version_number,
        content=version.content,
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
    document, source, version, job, summary = row
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
        summary_status=(
            SummaryStatus(summary.status) if summary is not None else SummaryStatus.NOT_REQUESTED
        ),
        summary=(
            summary.summary
            if summary is not None and summary.status == SummaryStatus.READY
            else None
        ),
    )


async def retrieve_editable_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    authorization: AuthorizationContext,
    request_id: str,
) -> EditableDocument:
    row = await get_document_resource_rows(session, authorization.tenant_id, document_id)
    if row is None:
        await append_audit_event(
            session,
            event_type="document.edit_not_found",
            request_id=request_id,
            decision=authorization.decision,
            metadata={"reason": "not_found"},
        )
        await session.commit()
        raise DocumentNotFound("document not found")
    document, source, version, _job, _summary = row
    await append_audit_event(
        session,
        event_type="document.edit_found",
        request_id=request_id,
        decision=authorization.decision,
        metadata={"document_id": str(document.id), "version_number": version.version_number},
    )
    await session.commit()
    return EditableDocument(
        document_id=document.id,
        client_id=document.client_id,
        source_reference=source.source_reference,
        external_document_id=document.external_document_id,
        title=document.title,
        content=version.content,
        current_document_version_id=version.id,
        current_version_number=version.version_number,
    )


async def revise_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    *,
    title: str,
    content: str,
    idempotency_key: str,
    profile_identity: EmbeddingProfileIdentity,
    authorization: AuthorizationContext,
    request_id: str,
    summary_configuration: SummaryConfiguration | None = None,
) -> IngestionResult:
    editable = await retrieve_editable_document(session, document_id, authorization, request_id)
    result = await ingest_plain_text(
        session,
        IngestionCommand(
            client_id=editable.client_id,
            source_reference=editable.source_reference,
            external_document_id=editable.external_document_id,
            title=title,
            content=content,
            idempotency_key=idempotency_key,
            request_id=request_id,
        ),
        profile_identity,
        authorization,
        summary_configuration,
        revision_document_id=document_id,
    )
    return result


async def list_client_documents(
    session: AsyncSession,
    client_id: uuid.UUID,
    authorization: AuthorizationContext,
    request_id: str,
    *,
    limit: int,
    before_created_at: datetime | None = None,
    before_id: uuid.UUID | None = None,
) -> tuple[tuple[DocumentTimelineItem, ...], bool]:
    if await get_client(session, authorization.tenant_id, client_id) is None:
        await append_audit_event(
            session,
            event_type="client.document_list_not_found",
            request_id=request_id,
            decision=authorization.decision,
            metadata={"reason": "not_found"},
        )
        await session.commit()
        raise DocumentNotFound("client not found")
    rows = await get_client_document_rows(
        session,
        authorization.tenant_id,
        client_id,
        limit=limit + 1,
        before_created_at=before_created_at,
        before_id=before_id,
    )
    page = rows[:limit]
    await append_audit_event(
        session,
        event_type="client.document_listed",
        request_id=request_id,
        decision=authorization.decision,
        metadata={"result_count": len(page)},
    )
    await session.commit()
    return (
        tuple(
            DocumentTimelineItem(
                document_id=document.id,
                client_id=client_id,
                title=document.title,
                current_document_version_id=version.id,
                current_version_number=version.version_number,
                indexing_status=IndexingStatus(job.status),
                created_at=document.created_at.isoformat(),
                summary_status=(
                    SummaryStatus(summary.status)
                    if summary is not None
                    else SummaryStatus.NOT_REQUESTED
                ),
                summary=(
                    summary.summary
                    if summary is not None and summary.status == SummaryStatus.READY
                    else None
                ),
            )
            for document, _source, version, job, summary in page
        ),
        len(rows) > limit,
    )


async def list_document_versions(
    session: AsyncSession,
    document_id: uuid.UUID,
    authorization: AuthorizationContext,
    request_id: str,
) -> tuple[DocumentVersionTimelineItem, ...]:
    rows = await get_document_version_rows(session, authorization.tenant_id, document_id)
    if rows is None:
        await append_audit_event(
            session,
            event_type="document.version_list_not_found",
            request_id=request_id,
            decision=authorization.decision,
            metadata={"reason": "not_found"},
        )
        await session.commit()
        raise DocumentNotFound("document not found")
    await append_audit_event(
        session,
        event_type="document.version_listed",
        request_id=request_id,
        decision=authorization.decision,
        metadata={"result_count": len(rows), "document_id": str(document_id)},
    )
    await session.commit()
    return tuple(
        DocumentVersionTimelineItem(
            document_version_id=version.id,
            document_id=document_id,
            version_number=version.version_number,
            indexing_status=IndexingStatus(job.status),
            created_at=version.created_at.isoformat(),
        )
        for version, job in rows
    )
