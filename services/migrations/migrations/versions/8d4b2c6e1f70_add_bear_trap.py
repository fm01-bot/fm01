"""add_bear_trap

Revision ID: 8d4b2c6e1f70
Revises: 6b1d0e7f3a52
Create Date: 2026-11-19 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d4b2c6e1f70"
down_revision: str | Sequence[str] | None = "6b1d0e7f3a52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
	"""Upgrade schema."""
	op.create_table(
		"bear_trap",
		sa.Column("guild_id", sa.Numeric(), primary_key=True),
		sa.Column("channel_id", sa.Numeric(), nullable=True),
		sa.Column("message_channel_id", sa.Numeric(), nullable=True),
		sa.Column("message_id", sa.Numeric(), nullable=True),
		sa.Column("kicks", sa.Integer(), nullable=False, server_default=sa.text("0")),
	)


def downgrade() -> None:
	"""Downgrade schema."""
	op.drop_table("bear_trap")
