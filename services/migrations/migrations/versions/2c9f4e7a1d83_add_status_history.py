"""add_status_history

Revision ID: 2c9f4e7a1d83
Revises: 8d4b2c6e1f70
Create Date: 2026-11-19 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2c9f4e7a1d83"
down_revision: str | Sequence[str] | None = "8d4b2c6e1f70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
	"""Upgrade schema."""
	op.create_table(
		"shard_status_changes",
		sa.Column("shard_id", sa.Integer(), nullable=False),
		sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
		sa.Column("status", sa.Text(), nullable=False),
		sa.PrimaryKeyConstraint("shard_id", "changed_at"),
		sa.CheckConstraint("status IN ('operational', 'lagging', 'unresponsive')", name="shard_status_valid"),
	)
	op.create_index("shard_status_changes_changed_at", "shard_status_changes", ["changed_at"])
	op.create_table(
		"status_sampler_runs",
		sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
		sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
		sa.Column("last_sample_at", sa.DateTime(timezone=True), nullable=False),
	)


def downgrade() -> None:
	"""Downgrade schema."""
	op.drop_table("status_sampler_runs")
	op.drop_index("shard_status_changes_changed_at", table_name="shard_status_changes")
	op.drop_table("shard_status_changes")
