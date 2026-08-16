"""document ingestion and indexing lineage

Revision ID: 20260816_0002
Revises: 20260815_0001
Create Date: 2026-08-16 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "20260816_0002"
down_revision = "20260815_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("source_reference", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("organization_id", "source_reference"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("document_sources.id"), nullable=False),
        sa.Column("external_document_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("organization_id", "source_id", "external_document_id"),
    )
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("document_sources.id"), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("authorization_policy", sa.String(100), nullable=False),
        sa.Column("authorization_result", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("document_id", "version_number"),
    )
    op.create_table(
        "ingestion_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "document_version_id", sa.Uuid(), sa.ForeignKey("document_versions.id"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("organization_id", "idempotency_key"),
    )
    op.create_table(
        "indexing_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("document_sources.id"), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column(
            "document_version_id", sa.Uuid(), sa.ForeignKey("document_versions.id"), nullable=False
        ),
        sa.Column(
            "embedding_profile_id",
            sa.Uuid(),
            sa.ForeignKey("embedding_profiles.id"),
            nullable=False,
        ),
        sa.Column("authorization_policy", sa.String(100), nullable=False),
        sa.Column("authorization_result", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(100)),
        sa.Column(
            "queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("document_version_id", "embedding_profile_id"),
    )
    op.create_index("ix_indexing_jobs_claim", "indexing_jobs", ["status", "lease_expires_at"])
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("document_sources.id"), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column(
            "document_version_id", sa.Uuid(), sa.ForeignKey("document_versions.id"), nullable=False
        ),
        sa.Column(
            "embedding_profile_id",
            sa.Uuid(),
            sa.ForeignKey("embedding_profiles.id"),
            nullable=False,
        ),
        sa.Column("authorization_policy", sa.String(100), nullable=False),
        sa.Column("authorization_result", sa.String(20), nullable=False),
        sa.Column("chunking_version", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("document_version_id", "embedding_profile_id", "ordinal"),
    )


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_index("ix_indexing_jobs_claim", table_name="indexing_jobs")
    op.drop_table("indexing_jobs")
    op.drop_table("ingestion_requests")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("document_sources")
