"""add_starboards

Revision ID: 3e5a7c9b1d24
Revises: 2c9f4e7a1d83
Create Date: 2026-11-19 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3e5a7c9b1d24"
down_revision: str | Sequence[str] | None = "2c9f4e7a1d83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
	"""Upgrade schema."""
	op.create_table(
		"starboards",
		sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
		sa.Column("guild_id", sa.Numeric(), nullable=False),
		sa.Column("name", sa.Text(), nullable=False),
		sa.Column("channel_id", sa.Numeric(), nullable=False),
		sa.Column("emoji", sa.Text(), nullable=False),
		sa.Column("threshold", sa.Integer(), nullable=False),
		sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
		sa.Column("channel_mode", sa.Text(), nullable=False, server_default="blocklist"),
		sa.Column(
			"channel_ids", postgresql.ARRAY(sa.Numeric()), nullable=False, server_default=sa.text("'{}'::numeric[]")
		),
		sa.Column("max_age_days", sa.Integer(), nullable=True),
		sa.UniqueConstraint("guild_id", "name", name="starboards_guild_name_key"),
		sa.UniqueConstraint("guild_id", "emoji", "threshold", name="starboards_guild_tier_key"),
	)
	# A starred message and one of the emojis it was starred with. The row exists once its starrers were seeded.
	op.create_table(
		"starboard_messages",
		sa.Column("guild_id", sa.Numeric(), nullable=False),
		sa.Column("message_id", sa.Numeric(), nullable=False),
		sa.Column("emoji", sa.Text(), nullable=False),
		sa.Column("channel_id", sa.Numeric(), nullable=False),
		sa.Column("author_id", sa.Numeric(), nullable=False),
		sa.PrimaryKeyConstraint("guild_id", "message_id", "emoji"),
	)
	op.create_table(
		"starboard_stars",
		sa.Column("guild_id", sa.Numeric(), nullable=False),
		sa.Column("message_id", sa.Numeric(), nullable=False),
		sa.Column("emoji", sa.Text(), nullable=False),
		sa.Column("user_id", sa.Numeric(), nullable=False),
		sa.PrimaryKeyConstraint("guild_id", "message_id", "emoji", "user_id"),
		sa.ForeignKeyConstraint(
			["guild_id", "message_id", "emoji"],
			["starboard_messages.guild_id", "starboard_messages.message_id", "starboard_messages.emoji"],
			ondelete="CASCADE",
		),
	)
	op.create_table(
		"starboard_entries",
		sa.Column("board_id", sa.BigInteger(), sa.ForeignKey("starboards.id", ondelete="CASCADE"), nullable=False),
		sa.Column("message_id", sa.Numeric(), nullable=False),
		sa.Column("post_channel_id", sa.Numeric(), nullable=True),
		sa.Column("post_id", sa.Numeric(), nullable=True),
		sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
		sa.PrimaryKeyConstraint("board_id", "message_id"),
	)
	op.create_index("starboard_entries_post_id_idx", "starboard_entries", ["post_id"])


def downgrade() -> None:
	"""Downgrade schema."""
	op.drop_index("starboard_entries_post_id_idx", table_name="starboard_entries")
	op.drop_table("starboard_entries")
	op.drop_table("starboard_stars")
	op.drop_table("starboard_messages")
	op.drop_table("starboards")
