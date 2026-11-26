"""add_suggestions

Revision ID: 9b4d6f8a1c35
Revises: 7a3c5e9b2d14
Create Date: 2026-11-26 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b4d6f8a1c35"
down_revision: str | Sequence[str] | None = "7a3c5e9b2d14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
	"""Upgrade schema."""
	op.create_table(
		"suggestion_config",
		sa.Column("guild_id", sa.Numeric(), primary_key=True),
		sa.Column("channel_id", sa.Numeric(), nullable=True),
		sa.Column("threads", sa.Boolean(), nullable=False, server_default=sa.text("false")),
		sa.Column("next_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
	)
	op.create_table(
		"suggestions",
		sa.Column("guild_id", sa.Numeric(), nullable=False),
		sa.Column("number", sa.Integer(), nullable=False),
		sa.Column("author_id", sa.Numeric(), nullable=False),
		sa.Column("content", sa.Text(), nullable=False),
		sa.Column("channel_id", sa.Numeric(), nullable=True),
		sa.Column("message_id", sa.Numeric(), nullable=True),
		sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
		sa.Column("decision", sa.Text(), nullable=True),
		sa.Column("moderator_id", sa.Numeric(), nullable=True),
		sa.Column("reason", sa.Text(), nullable=True),
		sa.PrimaryKeyConstraint("guild_id", "number"),
		sa.CheckConstraint("decision IN ('approved', 'denied')", name="ck_suggestions_decision"),
		sa.CheckConstraint(
			"(decision IS NULL) = (moderator_id IS NULL)",
			name="ck_suggestions_decision_has_moderator",
		),
	)
	op.create_table(
		"suggestion_votes",
		sa.Column("guild_id", sa.Numeric(), nullable=False),
		sa.Column("number", sa.Integer(), nullable=False),
		sa.Column("user_id", sa.Numeric(), nullable=False),
		sa.Column("vote", sa.SmallInteger(), nullable=False),
		sa.PrimaryKeyConstraint("guild_id", "number", "user_id"),
		sa.ForeignKeyConstraint(
			["guild_id", "number"], ["suggestions.guild_id", "suggestions.number"], ondelete="CASCADE"
		),
		sa.CheckConstraint("vote IN (-1, 1)", name="ck_suggestion_votes_vote"),
	)


def downgrade() -> None:
	"""Downgrade schema."""
	op.drop_table("suggestion_votes")
	op.drop_table("suggestions")
	op.drop_table("suggestion_config")
