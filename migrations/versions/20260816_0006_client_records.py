"""client records and document association

Revision ID: 20260816_0006
Revises: 20260816_0005
Create Date: 2026-08-16 12:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260816_0006"
down_revision = "20260816_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("normalized_email", sa.String(320), nullable=False),
        sa.Column("description", sa.String(2000)),
        sa.Column("social_links", postgresql.JSONB(), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("source_reference", sa.String(200), nullable=False),
        sa.Column("creation_authorization_decision_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["creation_authorization_decision_id"], ["authorization_decisions.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "normalized_email", name="uq_clients_tenant_normalized_email"
        ),
    )
    op.create_index("ix_clients_tenant_id_id", "clients", ["tenant_id", "id"])
    op.create_table(
        "client_creation_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_client_creation_tenant_key"),
    )
    op.create_index(
        "ix_client_creation_requests_tenant_client",
        "client_creation_requests",
        ["tenant_id", "client_id"],
    )
    op.add_column("documents", sa.Column("client_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_documents_client_id", "documents", "clients", ["client_id"], ["id"])
    op.create_index("ix_documents_tenant_client", "documents", ["tenant_id", "client_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_tenant_client", table_name="documents")
    op.drop_constraint("fk_documents_client_id", "documents", type_="foreignkey")
    op.drop_column("documents", "client_id")
    op.drop_index(
        "ix_client_creation_requests_tenant_client", table_name="client_creation_requests"
    )
    op.drop_table("client_creation_requests")
    op.drop_index("ix_clients_tenant_id_id", table_name="clients")
    op.drop_table("clients")
