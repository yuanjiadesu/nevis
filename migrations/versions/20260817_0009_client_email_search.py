"""include client email in lexical search

Revision ID: 20260817_0009
Revises: 20260816_0007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260817_0009"
down_revision = "20260816_0007"
branch_labels = None
depends_on = None


def _search_vector(expression: str) -> sa.Column[object]:
    return sa.Column(
        "search_vector",
        postgresql.TSVECTOR(),
        sa.Computed(expression, persisted=True),
        nullable=False,
    )


def upgrade() -> None:
    op.drop_index("ix_clients_search_vector", table_name="clients")
    op.drop_column("clients", "search_vector")
    op.add_column(
        "clients",
        _search_vector(
            "to_tsvector('english', coalesce(first_name, '') || ' ' || "
            "coalesce(last_name, '') || ' ' || "
            "regexp_replace(coalesce(email, ''), '[^[:alnum:]]+', ' ', 'g') || ' ' || "
            "coalesce(description, ''))"
        ),
    )
    op.create_index(
        "ix_clients_search_vector", "clients", ["search_vector"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_clients_search_vector", table_name="clients")
    op.drop_column("clients", "search_vector")
    op.add_column(
        "clients",
        _search_vector(
            "to_tsvector('english', coalesce(first_name, '') || ' ' || "
            "coalesce(last_name, '') || ' ' || coalesce(description, ''))"
        ),
    )
    op.create_index(
        "ix_clients_search_vector", "clients", ["search_vector"], postgresql_using="gin"
    )
