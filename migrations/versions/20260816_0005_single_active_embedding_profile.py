"""enforce one active embedding profile

Revision ID: 20260816_0005
Revises: 20260816_0004
Create Date: 2026-08-16 03:00:00
"""

from alembic import op

revision = "20260816_0005"
down_revision = "20260816_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE embedding_profiles SET is_active = false "
        "WHERE is_active AND id <> ("
        "SELECT id FROM embedding_profiles WHERE is_active "
        "ORDER BY created_at DESC, id DESC LIMIT 1)"
    )
    op.create_index(
        "uq_embedding_profiles_single_active",
        "embedding_profiles",
        ["is_active"],
        unique=True,
        postgresql_where="is_active",
    )


def downgrade() -> None:
    op.drop_index("uq_embedding_profiles_single_active", table_name="embedding_profiles")
