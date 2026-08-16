"""tenant and advisor authorization

Revision ID: 20260816_0003
Revises: 20260816_0002
Create Date: 2026-08-16 01:00:00
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20260816_0003"
down_revision = "20260816_0002"
branch_labels = None
depends_on = None

_MIGRATION_DECISION_ID = uuid.uuid5(uuid.NAMESPACE_URL, "nevis-global-migration-decision-v1")


def upgrade() -> None:
    op.rename_table("organizations", "tenants")
    for table in (
        "audit_events",
        "document_sources",
        "documents",
        "document_versions",
        "ingestion_requests",
        "indexing_jobs",
        "document_chunks",
    ):
        op.alter_column(table, "organization_id", new_column_name="tenant_id")

    op.create_table(
        "advisors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("external_id", sa.String(200), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "advisor_tenant_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("advisor_id", sa.Uuid(), sa.ForeignKey("advisors.id"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("advisor_id", "tenant_id"),
    )
    op.create_table(
        "authorization_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("advisor_id", sa.Uuid(), sa.ForeignKey("advisors.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("policy", sa.String(100), nullable=False),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("context", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    tenant_id = uuid.uuid5(uuid.NAMESPACE_URL, "nevis-global")
    op.execute(
        sa.text(
            "INSERT INTO authorization_decisions "
            "(id, tenant_id, action, policy, result, request_id, context) "
            "VALUES (:id, :tenant_id, 'migration.backfill', 'global-policy-v1', "
            "'allow', 'migration-20260816', '{}'::json)"
        ).bindparams(id=_MIGRATION_DECISION_ID, tenant_id=tenant_id)
    )
    for table in ("document_versions", "indexing_jobs", "document_chunks"):
        op.add_column(table, sa.Column("authorization_decision_id", sa.Uuid(), nullable=True))
        op.execute(
            sa.text(f"UPDATE {table} SET authorization_decision_id = :decision_id").bindparams(
                decision_id=_MIGRATION_DECISION_ID
            )
        )
        op.alter_column(table, "authorization_decision_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_authorization_decision",
            table,
            "authorization_decisions",
            ["authorization_decision_id"],
            ["id"],
        )
    op.add_column("audit_events", sa.Column("authorization_decision_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_audit_events_authorization_decision",
        "audit_events",
        "authorization_decisions",
        ["authorization_decision_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_audit_events_authorization_decision", "audit_events", type_="foreignkey")
    op.drop_column("audit_events", "authorization_decision_id")
    for table in ("document_chunks", "indexing_jobs", "document_versions"):
        op.drop_constraint(f"fk_{table}_authorization_decision", table, type_="foreignkey")
        op.drop_column(table, "authorization_decision_id")
    op.drop_table("authorization_decisions")
    op.drop_table("advisor_tenant_memberships")
    op.drop_table("advisors")
    for table in (
        "audit_events",
        "document_sources",
        "documents",
        "document_versions",
        "ingestion_requests",
        "indexing_jobs",
        "document_chunks",
    ):
        op.alter_column(table, "tenant_id", new_column_name="organization_id")
    op.rename_table("tenants", "organizations")
