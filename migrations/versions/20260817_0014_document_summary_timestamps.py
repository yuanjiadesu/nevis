"""Require document summary timestamps."""

import sqlalchemy as sa
from alembic import op

revision = "20260817_0014"
down_revision = "20260817_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE document_summaries SET queued_at = now() WHERE queued_at IS NULL")
    op.execute("UPDATE document_summaries SET created_at = now() WHERE created_at IS NULL")
    op.execute("UPDATE document_summaries SET updated_at = now() WHERE updated_at IS NULL")
    for column in ("queued_at", "created_at", "updated_at"):
        op.alter_column(
            "document_summaries",
            column,
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )


def downgrade() -> None:
    for column in ("queued_at", "created_at", "updated_at"):
        op.alter_column(
            "document_summaries",
            column,
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
