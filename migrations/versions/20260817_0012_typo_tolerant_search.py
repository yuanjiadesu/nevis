"""Add trigram indexes for typo-tolerant name and title search."""

from alembic import op

revision = "20260817_0012"
down_revision = "20260817_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_clients_full_name_trgm ON clients USING gin "
        "((first_name || ' ' || last_name) gin_trgm_ops)"
    )
    op.execute("CREATE INDEX ix_documents_title_trgm ON documents USING gin (title gin_trgm_ops)")


def downgrade() -> None:
    op.drop_index("ix_documents_title_trgm", table_name="documents")
    op.drop_index("ix_clients_full_name_trgm", table_name="clients")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
