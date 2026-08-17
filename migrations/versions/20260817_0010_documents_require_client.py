"""Require every document to belong to a client.

Documents were briefly allowed to exist without a client while client records were
introduced. That association is now mandatory: search, retrieval, and the advisor
console all present a document in the context of its client.

This migration deletes any document that has no client, together with its versions,
chunks, indexing jobs, and ingestion requests. Those rows are unreachable from the
product and cannot be repaired automatically, because the owning client is unknown.
"""

from alembic import op

revision = "20260817_0010"
down_revision = "20260817_0009"
branch_labels = None
depends_on = None

_ORPHANS = "SELECT id FROM documents WHERE client_id IS NULL"
_ORPHAN_VERSIONS = f"SELECT id FROM document_versions WHERE document_id IN ({_ORPHANS})"


def upgrade() -> None:
    op.execute(f"DELETE FROM document_chunks WHERE document_id IN ({_ORPHANS})")
    op.execute(f"DELETE FROM ingestion_requests WHERE document_version_id IN ({_ORPHAN_VERSIONS})")
    op.execute(f"DELETE FROM indexing_jobs WHERE document_id IN ({_ORPHANS})")
    op.execute(f"DELETE FROM document_versions WHERE document_id IN ({_ORPHANS})")
    op.execute("DELETE FROM documents WHERE client_id IS NULL")
    op.alter_column("documents", "client_id", nullable=False)


def downgrade() -> None:
    op.alter_column("documents", "client_id", nullable=True)
