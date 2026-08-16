"""platform foundation

Revision ID: 20260815_0001
Revises:
Create Date: 2026-08-15 00:00:00
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20260815_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(length=80), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("authorization_policy", sa.String(length=100), nullable=False),
        sa.Column("authorization_result", sa.String(length=20), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_table(
        "embedding_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("model_revision", sa.String(length=255)),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("normalization", sa.String(length=30), nullable=False),
        sa.Column("chunking_version", sa.Integer(), nullable=False),
        sa.Column("pipeline_version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("provider", "model", "model_revision", "pipeline_version"),
    )
    organization_id = uuid.uuid5(uuid.NAMESPACE_URL, "nevis-global")
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, slug, name) "
            "VALUES (:id, 'nevis-global', 'Nevis Global') "
            "ON CONFLICT (slug) DO NOTHING"
        ).bindparams(id=organization_id)
    )


def downgrade() -> None:
    op.drop_table("embedding_profiles")
    op.drop_table("audit_events")
    op.drop_table("organizations")
