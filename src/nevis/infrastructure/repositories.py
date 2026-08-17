from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from nevis.domain.authorization import AuthorizationAction, AuthorizationDecision
from nevis.domain.documents import IndexingStatus
from nevis.domain.embeddings import EmbeddingProfileIdentity
from nevis.domain.search import ClientRetrievalCandidate, MatchBand, RetrievalCandidate
from nevis.infrastructure.models import (
    Advisor,
    AdvisorTenantMembership,
    AuditEvent,
    AuthorizationDecisionRecord,
    Client,
    ClientCreationRequest,
    Document,
    DocumentChunk,
    DocumentSource,
    DocumentSummary,
    DocumentVersion,
    EmbeddingProfile,
    IndexingJob,
    IngestionRequest,
    Tenant,
)


async def get_client(session: AsyncSession, tenant_id: object, client_id: object) -> Client | None:
    return cast(
        Client | None,
        await session.scalar(
            select(Client).where(Client.tenant_id == tenant_id, Client.id == client_id)
        ),
    )


async def get_client_by_normalized_email(
    session: AsyncSession, tenant_id: object, normalized_email: str
) -> Client | None:
    return cast(
        Client | None,
        await session.scalar(
            select(Client).where(
                Client.tenant_id == tenant_id,
                Client.normalized_email == normalized_email,
            )
        ),
    )


async def list_clients(
    session: AsyncSession,
    tenant_id: object,
    *,
    limit: int,
    before_created_at: datetime | None = None,
    before_id: object | None = None,
) -> list[Client]:
    statement = select(Client).where(Client.tenant_id == tenant_id)
    if before_created_at is not None and before_id is not None:
        statement = statement.where(
            or_(
                Client.created_at < before_created_at,
                and_(Client.created_at == before_created_at, Client.id < before_id),
            )
        )
    rows = await session.scalars(
        statement.order_by(Client.created_at.desc(), Client.id.desc()).limit(limit)
    )
    return list(rows)


async def update_client_record(session: AsyncSession, *, client: Client, command: object) -> Client:
    from nevis.domain.clients import UpdateClientCommand

    assert isinstance(command, UpdateClientCommand)
    client.first_name = command.first_name
    client.last_name = command.last_name
    client.email = command.email
    client.normalized_email = command.email
    client.description = command.description
    client.social_links = list(command.social_links)
    await session.flush()
    return client


async def get_client_creation_request(
    session: AsyncSession, tenant_id: object, idempotency_key: str
) -> ClientCreationRequest | None:
    return cast(
        ClientCreationRequest | None,
        await session.scalar(
            select(ClientCreationRequest).where(
                ClientCreationRequest.tenant_id == tenant_id,
                ClientCreationRequest.idempotency_key == idempotency_key,
            )
        ),
    )


async def create_client_record(
    session: AsyncSession, *, tenant_id: object, command: object, decision: AuthorizationDecision
) -> Client:
    from nevis.domain.clients import CreateClientCommand

    assert isinstance(command, CreateClientCommand)
    assert decision.decision_id is not None
    client = Client(
        tenant_id=tenant_id,
        first_name=command.first_name,
        last_name=command.last_name,
        email=command.email,
        normalized_email=command.email,
        description=command.description,
        social_links=list(command.social_links),
        source_type=command.source_type,
        source_reference=command.source_reference,
        creation_authorization_decision_id=decision.decision_id,
    )
    session.add(client)
    await session.flush()
    return client


async def record_client_creation_request(
    session: AsyncSession,
    *,
    tenant_id: object,
    idempotency_key: str,
    fingerprint: str,
    client_id: object,
) -> ClientCreationRequest:
    record = ClientCreationRequest(
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        client_id=client_id,
    )
    session.add(record)
    await session.flush()
    return record


async def get_tenant_by_slug(session: AsyncSession, slug: str) -> Tenant | None:
    return cast(Tenant | None, await session.scalar(select(Tenant).where(Tenant.slug == slug)))


async def get_global_tenant(session: AsyncSession) -> Tenant:
    tenant = await get_tenant_by_slug(session, "nevis-global")
    if tenant is None:
        raise RuntimeError("nevis-global tenant has not been bootstrapped")
    return tenant


async def get_active_membership(
    session: AsyncSession, tenant_id: object, advisor_id: object
) -> AdvisorTenantMembership | None:
    return cast(
        AdvisorTenantMembership | None,
        await session.scalar(
            select(AdvisorTenantMembership).where(
                AdvisorTenantMembership.tenant_id == tenant_id,
                AdvisorTenantMembership.advisor_id == advisor_id,
                AdvisorTenantMembership.is_active.is_(True),
            )
        ),
    )


async def get_advisor_by_external_id(session: AsyncSession, external_id: str) -> Advisor | None:
    return cast(
        Advisor | None,
        await session.scalar(select(Advisor).where(Advisor.external_id == external_id)),
    )


async def create_authorization_decision(
    session: AsyncSession,
    *,
    tenant_id: object,
    advisor_id: object | None,
    action: AuthorizationAction,
    request_id: str,
    result: str,
    context: Mapping[str, object] | None = None,
) -> AuthorizationDecision:
    record = AuthorizationDecisionRecord(
        tenant_id=tenant_id,
        advisor_id=advisor_id,
        action=action,
        policy="tenant-membership-v1",
        result=result,
        request_id=request_id,
        context=dict(context or {}),
    )
    session.add(record)
    await session.flush()
    return AuthorizationDecision(
        tenant_id=record.tenant_id,
        advisor_id=record.advisor_id,
        action=action,
        policy=record.policy,
        result=record.result,
        decision_id=record.id,
    )


async def append_audit_event(
    session: AsyncSession,
    *,
    event_type: str,
    request_id: str,
    decision: AuthorizationDecision,
    metadata: Mapping[str, object] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        tenant_id=decision.tenant_id,
        request_id=request_id,
        authorization_policy=decision.policy,
        authorization_result=decision.result,
        authorization_decision_id=decision.decision_id,
        metadata_=dict(metadata or {}),
    )
    session.add(event)
    await session.flush()
    return event


async def ensure_active_embedding_profile(
    session: AsyncSession, identity: EmbeddingProfileIdentity
) -> EmbeddingProfile:
    profile = await session.scalar(
        select(EmbeddingProfile).where(
            EmbeddingProfile.provider == identity.provider,
            EmbeddingProfile.model == identity.model,
            EmbeddingProfile.model_revision == identity.model_revision,
            EmbeddingProfile.pipeline_version == identity.pipeline_version,
        )
    )
    if profile is None:
        profile = EmbeddingProfile(
            provider=identity.provider,
            model=identity.model,
            model_revision=identity.model_revision,
            dimensions=identity.dimensions,
            normalization=identity.normalization,
            chunking_version=identity.chunking_version,
            pipeline_version=identity.pipeline_version,
            is_active=False,
        )
        session.add(profile)
        await session.flush()
    await session.execute(
        update(EmbeddingProfile)
        .where(EmbeddingProfile.id != profile.id, EmbeddingProfile.is_active.is_(True))
        .values(is_active=False)
    )
    profile.is_active = True
    await session.flush()
    return profile


async def get_active_embedding_profile(session: AsyncSession) -> EmbeddingProfile | None:
    result = await session.execute(
        select(EmbeddingProfile).where(EmbeddingProfile.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def get_or_create_source(
    session: AsyncSession, tenant_id: object, source_reference: str
) -> DocumentSource:
    source = await session.scalar(
        select(DocumentSource).where(
            DocumentSource.tenant_id == tenant_id,
            DocumentSource.source_reference == source_reference,
        )
    )
    if source is None:
        source = DocumentSource(tenant_id=tenant_id, source_reference=source_reference)
        session.add(source)
        await session.flush()
    return source


async def get_or_create_document(
    session: AsyncSession,
    *,
    tenant_id: object,
    source: DocumentSource,
    external_document_id: str,
    title: str,
    client_id: object,
) -> Document:
    document = await session.scalar(
        select(Document).where(
            Document.tenant_id == tenant_id,
            Document.source_id == source.id,
            Document.external_document_id == external_document_id,
        )
    )
    if document is None:
        document = Document(
            tenant_id=tenant_id,
            client_id=client_id,
            source_id=source.id,
            external_document_id=external_document_id,
            title=title,
        )
        session.add(document)
        await session.flush()
    return document


async def update_document_title(
    session: AsyncSession, tenant_id: object, document_id: object, title: str
) -> Document | None:
    document = await session.scalar(
        select(Document).where(Document.tenant_id == tenant_id, Document.id == document_id)
    )
    if document is not None:
        document.title = title
        await session.flush()
    return document


async def get_document_resource_rows(
    session: AsyncSession, tenant_id: object, document_id: object
) -> tuple[Document, DocumentSource, DocumentVersion, IndexingJob, DocumentSummary | None] | None:
    row = (
        await session.execute(
            select(Document, DocumentSource, DocumentVersion, IndexingJob, DocumentSummary)
            .join(DocumentSource, DocumentSource.id == Document.source_id)
            .join(DocumentVersion, DocumentVersion.document_id == Document.id)
            .join(IndexingJob, IndexingJob.document_version_id == DocumentVersion.id)
            .outerjoin(DocumentSummary, DocumentSummary.document_version_id == DocumentVersion.id)
            .where(Document.tenant_id == tenant_id, Document.id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        return None
    return row[0], row[1], row[2], row[3], row[4]


async def get_client_document_rows(
    session: AsyncSession,
    tenant_id: object,
    client_id: object,
    *,
    limit: int,
    before_created_at: datetime | None = None,
    before_id: object | None = None,
) -> list[tuple[Document, DocumentSource, DocumentVersion, IndexingJob, DocumentSummary | None]]:
    latest_version = (
        select(func.max(DocumentVersion.version_number))
        .where(DocumentVersion.document_id == Document.id)
        .correlate(Document)
        .scalar_subquery()
    )
    statement = (
        select(Document, DocumentSource, DocumentVersion, IndexingJob, DocumentSummary)
        .join(DocumentSource, DocumentSource.id == Document.source_id)
        .join(
            DocumentVersion,
            and_(
                DocumentVersion.document_id == Document.id,
                DocumentVersion.version_number == latest_version,
            ),
        )
        .join(IndexingJob, IndexingJob.document_version_id == DocumentVersion.id)
        .outerjoin(DocumentSummary, DocumentSummary.document_version_id == DocumentVersion.id)
        .where(Document.tenant_id == tenant_id, Document.client_id == client_id)
    )
    if before_created_at is not None and before_id is not None:
        statement = statement.where(
            or_(
                Document.created_at < before_created_at,
                and_(Document.created_at == before_created_at, Document.id < before_id),
            )
        )
    rows = await session.execute(
        statement.order_by(Document.created_at.desc(), Document.id.desc()).limit(limit)
    )
    return [(row[0], row[1], row[2], row[3], row[4]) for row in rows]


async def get_document_version_rows(
    session: AsyncSession, tenant_id: object, document_id: object
) -> list[tuple[DocumentVersion, IndexingJob]] | None:
    document = await session.scalar(
        select(Document.id).where(Document.tenant_id == tenant_id, Document.id == document_id)
    )
    if document is None:
        return None
    rows = await session.execute(
        select(DocumentVersion, IndexingJob)
        .join(IndexingJob, IndexingJob.document_version_id == DocumentVersion.id)
        .where(DocumentVersion.tenant_id == tenant_id, DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(200)
    )
    return [(row[0], row[1]) for row in rows]


async def get_latest_document_version(
    session: AsyncSession, document_id: object
) -> DocumentVersion | None:
    return cast(
        DocumentVersion | None,
        await session.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        ),
    )


async def create_document_version(
    session: AsyncSession,
    *,
    tenant_id: object,
    source_id: object,
    document_id: object,
    version_number: int,
    content: str,
    content_sha256: str,
    decision: AuthorizationDecision,
) -> DocumentVersion:
    version = DocumentVersion(
        tenant_id=tenant_id,
        source_id=source_id,
        document_id=document_id,
        version_number=version_number,
        content=content,
        content_hash=content_sha256,
        authorization_policy=decision.policy,
        authorization_result=decision.result,
        authorization_decision_id=decision.decision_id,
    )
    session.add(version)
    await session.flush()
    return version


async def get_ingestion_request(
    session: AsyncSession, tenant_id: object, idempotency_key: str
) -> IngestionRequest | None:
    return cast(
        IngestionRequest | None,
        await session.scalar(
            select(IngestionRequest).where(
                IngestionRequest.tenant_id == tenant_id,
                IngestionRequest.idempotency_key == idempotency_key,
            )
        ),
    )


async def record_ingestion_request(
    session: AsyncSession,
    *,
    tenant_id: object,
    idempotency_key: str,
    fingerprint: str,
    document_version_id: object,
) -> IngestionRequest:
    request = IngestionRequest(
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        document_version_id=document_version_id,
    )
    session.add(request)
    await session.flush()
    return request


async def create_indexing_job(
    session: AsyncSession,
    *,
    tenant_id: object,
    source_id: object,
    document_id: object,
    version: DocumentVersion,
    profile: EmbeddingProfile,
    decision: AuthorizationDecision,
) -> IndexingJob:
    job = IndexingJob(
        tenant_id=tenant_id,
        source_id=source_id,
        document_id=document_id,
        document_version_id=version.id,
        embedding_profile_id=profile.id,
        authorization_policy=decision.policy,
        authorization_result=decision.result,
        authorization_decision_id=decision.decision_id,
        status=IndexingStatus.QUEUED,
    )
    session.add(job)
    await session.flush()
    return job


async def get_document_version(
    session: AsyncSession, version_id: object, tenant_id: object | None = None
) -> DocumentVersion | None:
    statement = select(DocumentVersion).where(DocumentVersion.id == version_id)
    if tenant_id is not None:
        statement = statement.where(tenant_document_predicate(DocumentVersion, tenant_id))
    return cast(DocumentVersion | None, await session.scalar(statement))


def tenant_document_predicate(
    model: type[DocumentVersion], tenant_id: object
) -> ColumnElement[bool]:
    """Compose tenant authorization before any retrieval candidate ordering or projection."""
    return model.tenant_id == tenant_id


async def get_indexing_job_for_version(
    session: AsyncSession, version_id: object, tenant_id: object | None = None
) -> IndexingJob | None:
    statement = select(IndexingJob).where(IndexingJob.document_version_id == version_id)
    if tenant_id is not None:
        statement = statement.where(IndexingJob.tenant_id == tenant_id)
    return cast(
        IndexingJob | None,
        await session.scalar(statement),
    )


async def count_chunks_for_version(session: AsyncSession, version_id: object) -> int:
    rows = await session.scalars(
        select(DocumentChunk.id).where(DocumentChunk.document_version_id == version_id)
    )
    return len(rows.all())


async def claim_indexing_job(
    session: AsyncSession, *, lease_seconds: int = 60
) -> IndexingJob | None:
    now = datetime.now(UTC)
    job = await session.scalar(
        select(IndexingJob)
        .where(
            or_(
                IndexingJob.status == IndexingStatus.QUEUED,
                and_(
                    IndexingJob.status == IndexingStatus.PROCESSING,
                    IndexingJob.lease_expires_at < now,
                ),
            )
        )
        .order_by(IndexingJob.queued_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    job.status = IndexingStatus.PROCESSING
    job.attempt_count += 1
    job.started_at = now
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.failure_code = None
    await session.flush()
    return job


async def complete_indexing_job(session: AsyncSession, job: IndexingJob) -> None:
    job.status = IndexingStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
    job.lease_expires_at = None
    await session.flush()


async def fail_indexing_job(session: AsyncSession, job: IndexingJob, failure_code: str) -> None:
    job.status = IndexingStatus.FAILED
    job.failed_at = datetime.now(UTC)
    job.lease_expires_at = None
    job.failure_code = failure_code
    await session.flush()


async def existing_chunk_ordinals(
    session: AsyncSession, version_id: object, profile_id: object
) -> set[int]:
    ordinals = await session.scalars(
        select(DocumentChunk.ordinal).where(
            DocumentChunk.document_version_id == version_id,
            DocumentChunk.embedding_profile_id == profile_id,
        )
    )
    return set(ordinals.all())


async def add_document_chunk(
    session: AsyncSession,
    *,
    job: IndexingJob,
    ordinal: int,
    start_offset: int,
    end_offset: int,
    content: str,
    content_sha256: str,
    chunking_version: int,
    embedding: list[float],
) -> DocumentChunk:
    chunk = DocumentChunk(
        tenant_id=job.tenant_id,
        source_id=job.source_id,
        document_id=job.document_id,
        document_version_id=job.document_version_id,
        embedding_profile_id=job.embedding_profile_id,
        authorization_policy=job.authorization_policy,
        authorization_result=job.authorization_result,
        authorization_decision_id=job.authorization_decision_id,
        chunking_version=chunking_version,
        ordinal=ordinal,
        start_offset=start_offset,
        end_offset=end_offset,
        content=content,
        content_hash=content_sha256,
        embedding=embedding,
    )
    session.add(chunk)
    await session.flush()
    return chunk


_AUTHORIZED_SEARCH_RELATION = """
latest_versions AS (
    SELECT document_id, max(version_number) AS version_number
    FROM document_versions
    WHERE tenant_id = :tenant_id
    GROUP BY document_id
),
authorized_chunks AS MATERIALIZED (
    SELECT
        c.tenant_id, c.source_id, c.document_id, c.document_version_id,
        c.embedding_profile_id, c.authorization_decision_id,
        c.id AS chunk_id, c.content, c.content_search_vector, c.embedding,
        d.client_id, d.title, d.title_search_vector,
        cl.first_name || ' ' || cl.last_name AS client_name
    FROM document_chunks c
    JOIN document_versions v ON v.id = c.document_version_id
    JOIN latest_versions lv
      ON lv.document_id = v.document_id AND lv.version_number = v.version_number
    JOIN documents d ON d.id = c.document_id
    JOIN clients cl ON cl.id = d.client_id
    JOIN indexing_jobs j
      ON j.document_version_id = c.document_version_id
     AND j.embedding_profile_id = c.embedding_profile_id
    WHERE c.tenant_id = :tenant_id
      AND v.tenant_id = :tenant_id
      AND d.tenant_id = :tenant_id
      AND cl.tenant_id = :tenant_id
      AND j.tenant_id = :tenant_id
      AND c.embedding_profile_id = :profile_id
      AND c.authorization_result = 'allow'
      AND j.authorization_result = 'allow'
      AND j.status = 'completed'
)
"""


def _candidate_from_mapping(row: RowMapping) -> RetrievalCandidate:
    return RetrievalCandidate(
        tenant_id=cast(UUID, row["tenant_id"]),
        client_id=cast(UUID, row["client_id"]),
        client_name=str(row["client_name"]),
        source_id=cast(UUID, row["source_id"]),
        document_id=cast(UUID, row["document_id"]),
        document_version_id=cast(UUID, row["document_version_id"]),
        embedding_profile_id=cast(UUID, row["embedding_profile_id"]),
        indexing_authorization_decision_id=cast(UUID, row["authorization_decision_id"]),
        title=str(row["title"]),
        chunk_id=cast(UUID, row["chunk_id"]),
        content=str(row["content"]),
        snippet=str(row["snippet"]),
        score=float(cast(float, row["score"])),
        title_match=bool(row.get("title_match", False)),
        content_match=bool(row.get("content_match", False)),
        semantic_match=bool(row.get("semantic_match", False)),
    )


async def search_lexical_candidates(
    session: AsyncSession,
    *,
    tenant_id: object,
    profile_id: object,
    query: str,
    limit: int,
    snippet_length: int,
) -> list[RetrievalCandidate]:
    statement = text(
        """
        WITH parsed_query AS (
            SELECT
                websearch_to_tsquery('english', :query) AS content_value,
                websearch_to_tsquery(
                    'english',
                    regexp_replace(:query, '[^[:alnum:]]+', ' ', 'g')
                ) AS title_value,
                (
                    SELECT to_tsquery(
                        'english',
                        string_agg(quote_literal(lexeme) || ':*', ' & ')
                    )
                    FROM unnest(
                        tsvector_to_array(
                            to_tsvector(
                                'english',
                                regexp_replace(:query, '[^[:alnum:]]+', ' ', 'g')
                            )
                        )
                    ) lexeme
                ) AS title_prefix_value
        ),
        matching_chunk_ids AS MATERIALIZED (
            SELECT c.id AS chunk_id
            FROM document_chunks c CROSS JOIN parsed_query pq
            WHERE c.tenant_id = :tenant_id
              AND c.embedding_profile_id = :profile_id
              AND c.authorization_result = 'allow'
              AND c.content_search_vector @@ pq.content_value
            UNION
            SELECT c.id AS chunk_id
            FROM documents d
            JOIN document_chunks c ON c.document_id = d.id
            CROSS JOIN parsed_query pq
            WHERE d.tenant_id = :tenant_id
              AND c.tenant_id = :tenant_id
              AND c.embedding_profile_id = :profile_id
              AND c.authorization_result = 'allow'
              AND (
                  d.title_search_vector @@ pq.title_value
                  OR d.title_search_vector @@ pq.title_prefix_value
              )
        ),
        ranked AS (
            SELECT
                c.tenant_id, d.client_id, c.source_id, c.document_id,
                c.document_version_id, c.embedding_profile_id,
                c.authorization_decision_id, c.id AS chunk_id, c.content, d.title,
                cl.first_name || ' ' || cl.last_name AS client_name,
                (
                    d.title_search_vector @@ pq.title_value
                    OR d.title_search_vector @@ pq.title_prefix_value
                ) AS title_match,
                c.content_search_vector @@ pq.content_value AS content_match,
                pq.content_value,
                greatest(
                    ts_rank_cd(d.title_search_vector, pq.title_value),
                    COALESCE(ts_rank_cd(d.title_search_vector, pq.title_prefix_value), 0),
                    ts_rank_cd(c.content_search_vector, pq.content_value)
                ) AS score
            FROM matching_chunk_ids matches
            JOIN document_chunks c ON c.id = matches.chunk_id
            JOIN documents d
              ON d.id = c.document_id AND d.tenant_id = :tenant_id
            JOIN clients cl
              ON cl.id = d.client_id AND cl.tenant_id = :tenant_id
            JOIN document_versions v
              ON v.id = c.document_version_id AND v.tenant_id = :tenant_id
            JOIN indexing_jobs j
              ON j.document_version_id = c.document_version_id
             AND j.embedding_profile_id = c.embedding_profile_id
             AND j.tenant_id = :tenant_id
            CROSS JOIN parsed_query pq
            WHERE j.authorization_result = 'allow'
              AND j.status = 'completed'
              AND NOT EXISTS (
                  SELECT 1
                  FROM document_versions newer
                  WHERE newer.tenant_id = :tenant_id
                    AND newer.document_id = v.document_id
                    AND newer.version_number > v.version_number
              )
        )
        SELECT tenant_id, client_id, client_name, source_id, document_id,
               document_version_id, embedding_profile_id, authorization_decision_id,
               title, chunk_id, content, title_match, content_match,
               false AS semantic_match,
               left(
                   CASE
                       WHEN content_match THEN ts_headline(
                           'english', content, content_value,
                           'StartSel=, StopSel=, MaxFragments=1, MaxWords=35, MinWords=12'
                       )
                       ELSE content
                   END,
                   :snippet_length
               ) AS snippet,
               score
        FROM ranked
        WHERE score > 0
        ORDER BY score DESC, chunk_id ASC
        LIMIT :limit
        """
    )
    rows = (
        await session.execute(
            statement,
            {
                "tenant_id": tenant_id,
                "profile_id": profile_id,
                "query": query,
                "snippet_length": snippet_length,
                "limit": limit,
            },
        )
    ).mappings()
    return [_candidate_from_mapping(row) for row in rows]


async def search_semantic_candidates(
    session: AsyncSession,
    *,
    tenant_id: object,
    profile_id: object,
    embedding: list[float],
    threshold: float,
    limit: int,
    snippet_length: int,
) -> list[RetrievalCandidate]:
    statement = text(
        f"""
        WITH {_AUTHORIZED_SEARCH_RELATION},
        ranked AS (
            SELECT ac.*, 1 - (ac.embedding <=> CAST(:embedding AS vector)) AS score
            FROM authorized_chunks ac
        )
        SELECT tenant_id, client_id, client_name, source_id, document_id,
               document_version_id, embedding_profile_id, authorization_decision_id,
               title, chunk_id, content, false AS title_match,
               false AS content_match, true AS semantic_match,
               left(content, :snippet_length) AS snippet, score
        FROM ranked
        WHERE score >= :threshold
        ORDER BY score DESC, chunk_id ASC
        LIMIT :limit
        """
    )
    vector = "[" + ",".join(format(value, ".9g") for value in embedding) + "]"
    rows = (
        await session.execute(
            statement,
            {
                "tenant_id": tenant_id,
                "profile_id": profile_id,
                "embedding": vector,
                "threshold": threshold,
                "snippet_length": snippet_length,
                "limit": limit,
            },
        )
    ).mappings()
    return [_candidate_from_mapping(row) for row in rows]


async def _set_strict_word_similarity_threshold(session: AsyncSession, threshold: float) -> None:
    await session.execute(
        text(
            "SELECT set_config("
            "'pg_trgm.strict_word_similarity_threshold', CAST(:threshold AS text), true)"
        ),
        {"threshold": format(threshold, "g")},
    )


async def search_fuzzy_title_candidates(
    session: AsyncSession,
    *,
    tenant_id: object,
    profile_id: object,
    query: str,
    threshold: float,
    limit: int,
    snippet_length: int,
) -> list[RetrievalCandidate]:
    await _set_strict_word_similarity_threshold(session, threshold)
    statement = text(
        """
        WITH ranked AS (
            SELECT DISTINCT ON (d.id)
                c.tenant_id, d.client_id, c.source_id, c.document_id,
                c.document_version_id, c.embedding_profile_id,
                c.authorization_decision_id, c.id AS chunk_id, c.content, d.title,
                cl.first_name || ' ' || cl.last_name AS client_name,
                left(c.content, :snippet_length) AS snippet,
                strict_word_similarity(:query, d.title) AS score
            FROM documents d
            JOIN document_chunks c ON c.document_id = d.id
            JOIN clients cl
              ON cl.id = d.client_id AND cl.tenant_id = :tenant_id
            JOIN document_versions v
              ON v.id = c.document_version_id AND v.tenant_id = :tenant_id
            JOIN indexing_jobs j
              ON j.document_version_id = c.document_version_id
             AND j.embedding_profile_id = c.embedding_profile_id
             AND j.tenant_id = :tenant_id
            WHERE d.tenant_id = :tenant_id
              AND c.tenant_id = :tenant_id
              AND c.embedding_profile_id = :profile_id
              AND c.authorization_result = 'allow'
              AND j.authorization_result = 'allow'
              AND j.status = 'completed'
              AND :query <<% d.title
              AND NOT EXISTS (
                  SELECT 1
                  FROM document_versions newer
                  WHERE newer.tenant_id = :tenant_id
                    AND newer.document_id = v.document_id
                    AND newer.version_number > v.version_number
              )
            ORDER BY d.id, c.ordinal, c.id
        )
        SELECT tenant_id, client_id, client_name, source_id, document_id,
               document_version_id, embedding_profile_id, authorization_decision_id,
               title, chunk_id, content, true AS title_match,
               false AS content_match, false AS semantic_match, snippet, score
        FROM ranked
        ORDER BY score DESC, document_id ASC
        LIMIT :limit
        """
    )
    rows = (
        await session.execute(
            statement,
            {
                "tenant_id": tenant_id,
                "profile_id": profile_id,
                "query": query,
                "snippet_length": snippet_length,
                "limit": limit,
            },
        )
    ).mappings()
    return [_candidate_from_mapping(row) for row in rows]


def _client_candidate(row: RowMapping, band: MatchBand) -> ClientRetrievalCandidate:
    return ClientRetrievalCandidate(
        tenant_id=cast(UUID, row["tenant_id"]),
        client_id=cast(UUID, row["id"]),
        first_name=str(row["first_name"]),
        last_name=str(row["last_name"]),
        email=str(row["email"]),
        description=cast(str | None, row["description"]),
        creation_authorization_decision_id=cast(UUID, row["creation_authorization_decision_id"]),
        match_band=band,
        score=float(cast(float, row["score"])),
    )


async def search_exact_email_clients(
    session: AsyncSession, *, tenant_id: object, query: str
) -> list[ClientRetrievalCandidate]:
    rows = (
        await session.execute(
            text(
                "SELECT tenant_id, id, first_name, last_name, email, description, "
                "creation_authorization_decision_id, 1.0 AS score FROM clients "
                "WHERE tenant_id=:tenant_id AND normalized_email=:query ORDER BY id"
            ),
            {"tenant_id": tenant_id, "query": query.strip().lower()},
        )
    ).mappings()
    return [_client_candidate(row, MatchBand.EXACT_EMAIL) for row in rows]


async def search_exact_name_clients(
    session: AsyncSession, *, tenant_id: object, query: str, limit: int
) -> list[ClientRetrievalCandidate]:
    rows = (
        await session.execute(
            text(
                "SELECT tenant_id, id, first_name, last_name, email, description, "
                "creation_authorization_decision_id, 1.0 AS score FROM clients "
                "WHERE tenant_id=:tenant_id "
                "AND lower(first_name || ' ' || last_name)=:query "
                "ORDER BY id LIMIT :limit"
            ),
            {"tenant_id": tenant_id, "query": query.strip().lower(), "limit": limit},
        )
    ).mappings()
    return [_client_candidate(row, MatchBand.EXACT_NAME) for row in rows]


async def search_lexical_clients(
    session: AsyncSession, *, tenant_id: object, query: str, limit: int
) -> list[ClientRetrievalCandidate]:
    rows = (
        await session.execute(
            text(
                "WITH parsed AS ("
                "SELECT websearch_to_tsquery("
                "'english', regexp_replace(:query, '[^[:alnum:]]+', ' ', 'g')"
                ") exact_value, "
                "(SELECT to_tsquery('english', "
                "string_agg(quote_literal(lexeme) || ':*', ' & ')) "
                "FROM unnest(tsvector_to_array(to_tsvector("
                "'english', regexp_replace(:query, '[^[:alnum:]]+', ' ', 'g')"
                "))) lexeme) "
                "prefix_value) "
                "SELECT c.tenant_id, c.id, c.first_name, c.last_name, c.email, "
                "c.description, c.creation_authorization_decision_id, "
                "GREATEST(ts_rank_cd(c.search_vector, p.exact_value), "
                "COALESCE(ts_rank_cd(c.search_vector, p.prefix_value), 0)) AS score "
                "FROM clients c CROSS JOIN parsed p "
                "WHERE c.tenant_id=:tenant_id AND (c.search_vector @@ p.exact_value "
                "OR c.search_vector @@ p.prefix_value) "
                "ORDER BY score DESC, c.id ASC LIMIT :limit"
            ),
            {"tenant_id": tenant_id, "query": query, "limit": limit},
        )
    ).mappings()
    return [_client_candidate(row, MatchBand.GENERAL) for row in rows]


async def search_fuzzy_name_clients(
    session: AsyncSession,
    *,
    tenant_id: object,
    query: str,
    threshold: float,
    limit: int,
) -> list[ClientRetrievalCandidate]:
    await _set_strict_word_similarity_threshold(session, threshold)
    rows = (
        await session.execute(
            text(
                "SELECT tenant_id, id, first_name, last_name, email, description, "
                "creation_authorization_decision_id, "
                "strict_word_similarity(:query, first_name || ' ' || last_name) AS score "
                "FROM clients "
                "WHERE tenant_id=:tenant_id "
                "AND :query <<% (first_name || ' ' || last_name) "
                "ORDER BY score DESC, id ASC LIMIT :limit"
            ),
            {"tenant_id": tenant_id, "query": query, "limit": limit},
        )
    ).mappings()
    return [_client_candidate(row, MatchBand.FUZZY) for row in rows]
