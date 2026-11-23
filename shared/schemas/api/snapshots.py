"""Snapshots: saved copies of a guild's roles and channels that can be restored later."""

import datetime
from typing import Any

from pydantic import BaseModel

from api.snowflake import Snowflake

__all__ = ("Snapshot", "SnapshotCreate")


class SnapshotCreate(BaseModel):
	"""A snapshot to save."""

	name: str
	author_id: Snowflake
	payload: dict[str, Any]
	"""The guild's roles and channels, as the bot reads them."""


class Snapshot(SnapshotCreate):
	"""A saved snapshot."""

	code: str
	"""The code to restore it with."""
	guild_id: Snowflake
	date: datetime.datetime
