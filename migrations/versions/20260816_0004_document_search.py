"""tenant-authorized document search

Revision ID: 20260816_0004
Revises: 20260816_0003
Create Date: 2026-08-16 02:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260816_0004"
down_revision = "20260816_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "title_search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', coalesce(title, ''))", persisted=True),
            nullable=False,
        ),
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "content_search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', coalesce(content, ''))", persisted=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_documents_title_search",
        "documents",
        ["title_search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_document_chunks_content_search",
        "document_chunks",
        ["content_search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_document_chunks_tenant_profile_version",
        "document_chunks",
        ["tenant_id", "embedding_profile_id", "document_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_tenant_profile_version", table_name="document_chunks")
    op.drop_index("ix_document_chunks_content_search", table_name="document_chunks")
    op.drop_index("ix_documents_title_search", table_name="documents")
    op.drop_column("document_chunks", "content_search_vector")
    op.drop_column("documents", "title_search_vector")
