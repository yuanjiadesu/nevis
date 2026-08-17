import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    authorization_policy: Mapped[str] = mapped_column(String(100), nullable=False)
    authorization_result: Mapped[str] = mapped_column(String(20), nullable=False)
    authorization_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("authorization_decisions.id")
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )


class Advisor(Base):
    __tablename__ = "advisors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdvisorTenantMembership(Base):
    __tablename__ = "advisor_tenant_memberships"
    __table_args__ = (UniqueConstraint("advisor_id", "tenant_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    advisor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("advisors.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthorizationDecisionRecord(Base):
    __tablename__ = "authorization_decisions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    advisor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("advisors.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    policy: Mapped[str] = mapped_column(String(100), nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class EmbeddingProfile(Base):
    __tablename__ = "embedding_profiles"
    __table_args__ = (
        UniqueConstraint("provider", "model", "model_revision", "pipeline_version"),
        Index(
            "uq_embedding_profiles_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    model_revision: Mapped[str | None] = mapped_column(String(255))
    dimensions: Mapped[int] = mapped_column(nullable=False)
    normalization: Mapped[str] = mapped_column(String(30), nullable=False)
    chunking_version: Mapped[int] = mapped_column(nullable=False)
    pipeline_version: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentSource(Base):
    __tablename__ = "document_sources"
    __table_args__ = (UniqueConstraint("tenant_id", "source_reference"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "normalized_email", name="uq_clients_tenant_normalized_email"
        ),
        Index("ix_clients_tenant_id_id", "tenant_id", "id"),
        Index("ix_clients_search_vector", "search_vector", postgresql_using="gin"),
        Index(
            "ix_clients_tenant_normalized_full_name",
            "tenant_id",
            text("lower((first_name::text || ' '::text) || last_name::text)"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(first_name, '') || ' ' || "
            "coalesce(last_name, '') || ' ' || "
            "regexp_replace(coalesce(email, ''), '[^[:alnum:]]+', ' ', 'g') || ' ' || "
            "coalesce(description, ''))",
            persisted=True,
        ),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(String(2000))
    social_links: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    creation_authorization_decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authorization_decisions.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ClientCreationRequest(Base):
    __tablename__ = "client_creation_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_client_creation_tenant_key"),
        Index("ix_client_creation_requests_tenant_client", "tenant_id", "client_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_id", "external_document_id"),
        Index("ix_documents_title_search", "title_search_vector", postgresql_using="gin"),
        Index("ix_documents_tenant_client", "tenant_id", "client_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_sources.id"), nullable=False)
    external_document_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(title, ''))", persisted=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_sources.id"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_policy: Mapped[str] = mapped_column(String(100), nullable=False)
    authorization_result: Mapped[str] = mapped_column(String(20), nullable=False)
    authorization_decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authorization_decisions.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestionRequest(Base):
    __tablename__ = "ingestion_requests"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IndexingJob(Base):
    __tablename__ = "indexing_jobs"
    __table_args__ = (
        UniqueConstraint("document_version_id", "embedding_profile_id"),
        Index("ix_indexing_jobs_claim", "status", "lease_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_sources.id"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id"), nullable=False
    )
    embedding_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("embedding_profiles.id"), nullable=False
    )
    authorization_policy: Mapped[str] = mapped_column(String(100), nullable=False)
    authorization_result: Mapped[str] = mapped_column(String(20), nullable=False)
    authorization_decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authorization_decisions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_version_id", "embedding_profile_id", "ordinal"),
        Index("ix_document_chunks_content_search", "content_search_vector", postgresql_using="gin"),
        Index(
            "ix_document_chunks_tenant_profile_version",
            "tenant_id",
            "embedding_profile_id",
            "document_version_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_sources.id"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id"), nullable=False
    )
    embedding_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("embedding_profiles.id"), nullable=False
    )
    authorization_policy: Mapped[str] = mapped_column(String(100), nullable=False)
    authorization_result: Mapped[str] = mapped_column(String(20), nullable=False)
    authorization_decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authorization_decisions.id"), nullable=False
    )
    chunking_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(content, ''))", persisted=True),
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
