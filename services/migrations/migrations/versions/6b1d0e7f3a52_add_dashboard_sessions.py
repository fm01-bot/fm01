"""add_dashboard_sessions

Revision ID: 6b1d0e7f3a52
Revises: 19baef2a8fe3
Create Date: 2026-11-16 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "6b1d0e7f3a52"
down_revision: str | Sequence[str] | None = "19baef2a8fe3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
	"""Upgrade schema."""
	op.create_table(
		"dashboard_sessions",
		# The public half of the session token (<id>.<secret>). The secret is stored only as a salted SHA-256 hash.
		sa.Column("id", sa.Text(), primary_key=True),
		sa.Column("token_salt", sa.Text(), nullable=False),
		sa.Column("token_hash", sa.Text(), nullable=False),
		sa.Column("user_id", sa.Numeric(), nullable=False),
		sa.Column("user_profile", postgresql.JSONB(), nullable=False),
		# Discord OAuth2 tokens, Fernet-encrypted with SESSION_ENCRYPTION_KEY.
		sa.Column("access_token", sa.Text(), nullable=False),
		sa.Column("refresh_token", sa.Text(), nullable=False),
		sa.Column("discord_expires_at", sa.DateTime(timezone=True), nullable=False),
		sa.Column("scopes", postgresql.ARRAY(sa.Text()), nullable=False),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
		sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
	)
	op.create_index("ix_dashboard_sessions_user_id", "dashboard_sessions", ["user_id"])
	op.create_index("ix_dashboard_sessions_expires_at", "dashboard_sessions", ["expires_at"])


def downgrade() -> None:
	"""Downgrade schema."""
	op.drop_index("ix_dashboard_sessions_expires_at", table_name="dashboard_sessions")
	op.drop_index("ix_dashboard_sessions_user_id", table_name="dashboard_sessions")
	op.drop_table("dashboard_sessions")
