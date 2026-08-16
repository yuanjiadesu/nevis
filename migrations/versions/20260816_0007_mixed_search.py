"""mixed client and document search

Revision ID: 20260816_0007
Revises: 20260816_0006
Create Date: 2026-08-16 20:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260816_0007"
down_revision = "20260816_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(first_name, '') || ' ' || "
                "coalesce(last_name, '') || ' ' || coalesce(description, ''))",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_clients_search_vector", "clients", ["search_vector"], postgresql_using="gin"
    )
    op.create_index(
        "ix_clients_tenant_normalized_full_name",
        "clients",
        ["tenant_id", sa.text("lower(first_name || ' ' || last_name)")],
    )


def downgrade() -> None:
    op.drop_index("ix_clients_tenant_normalized_full_name", table_name="clients")
    op.drop_index("ix_clients_search_vector", table_name="clients")
    op.drop_column("clients", "search_vector")
