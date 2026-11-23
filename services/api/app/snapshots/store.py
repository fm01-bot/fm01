"""The snapshot store."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from typing import Any

import asyncpg
from api import Snapshot, SnapshotCreate

__all__ = ("SnapshotStore",)


def _snapshot(row: Mapping[str, Any]) -> Snapshot:
	"""Build a snapshot from a ``snapshots`` row.

	Args:
		row: The row.

	Returns:
		The snapshot.
	"""
	payload = row["payload"]
	if isinstance(payload, str):  # rows the bot wrote as a JSON string inside jsonb
		payload = json.loads(payload)
	return Snapshot(
		code=row["code"],
		guild_id=int(row["guild_id"]),
		name=row["name"],
		author_id=int(row["author_id"]),
		date=row["date"],
		payload=payload if isinstance(payload, dict) else {},
	)


class SnapshotStore:
	"""Saves and loads snapshots.

	Args:
		db: The database pool.
	"""

	def __init__(self, db: asyncpg.Pool) -> None:
		self._db = db

	async def create(self, guild_id: int, snapshot: SnapshotCreate) -> Snapshot:
		"""Save a snapshot under a new random code.

		Args:
			guild_id: The guild the snapshot is of.
			snapshot: The snapshot.

		Returns:
			The saved snapshot, with its code.
		"""
		row = await self._db.fetchrow(
			"INSERT INTO snapshots (guild_id, name, payload, author_id, date, code) "
			"VALUES ($1, $2, $3, $4, now(), $5) RETURNING *",
			guild_id,
			snapshot.name,
			snapshot.payload,
			snapshot.author_id,
			str(uuid.uuid4()),
		)
		assert row is not None
		return _snapshot(row)

	async def get(self, code: str) -> Snapshot | None:
		"""Get a snapshot.

		Args:
			code: The snapshot's code, ignoring case.

		Returns:
			The snapshot, or ``None`` if there is none with that code.
		"""
		row = await self._db.fetchrow("SELECT * FROM snapshots WHERE code = $1", code.lower())
		return _snapshot(row) if row else None
