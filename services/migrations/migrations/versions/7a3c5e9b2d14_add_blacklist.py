"""add_blacklist

Revision ID: 7a3c5e9b2d14
Revises: 3e5a7c9b1d24
Create Date: 2026-11-23 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a3c5e9b2d14"
down_revision: str | Sequence[str] | None = "3e5a7c9b1d24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
	"""Upgrade schema."""
	op.create_table(
		"blacklist",
		sa.Column("kind", sa.Text(), primary_key=True),
		sa.Column("target_id", sa.Numeric(), primary_key=True),
		sa.Column("reason", sa.Text(), nullable=True),
		sa.Column("created_by", sa.Numeric(), nullable=False),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
		sa.CheckConstraint("kind IN ('user', 'guild')", name="blacklist_kind_check"),
	)


def downgrade() -> None:
	"""Downgrade schema."""
	op.drop_table("blacklist")
