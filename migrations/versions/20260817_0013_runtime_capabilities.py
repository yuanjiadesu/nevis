"""Add runtime capability heartbeats."""

import sqlalchemy as sa
from alembic import op

revision = "20260817_0013"
down_revision = "20260817_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_capabilities",
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.Column("identity_hash", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("role"),
    )


def downgrade() -> None:
    op.drop_table("runtime_capabilities")
