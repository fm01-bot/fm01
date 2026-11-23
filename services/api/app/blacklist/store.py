"""The blacklist store."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import asyncpg
from api import BlacklistAdd, BlacklistEntry, BlacklistKind

from app.events import Announcer

__all__ = ("BlacklistStore",)

_COLUMNS = "kind, target_id, reason, created_by, created_at"


def _entry(row: Mapping[str, Any]) -> BlacklistEntry:
	"""Build an entry from a ``blacklist`` row.

	Args:
		row: The row.

	Returns:
		The entry.
	"""
	return BlacklistEntry(
		kind=row["kind"],
		target_id=int(row["target_id"]),
		reason=row["reason"],
		created_by=int(row["created_by"]),
		created_at=row["created_at"],
	)


class BlacklistStore:
	"""Reads and writes the blacklist. Announces every change.

	Args:
		db: The database pool.
		announcer: Tells bot instances about changes.
	"""

	def __init__(self, db: asyncpg.Pool, announcer: Announcer) -> None:
		self._db = db
		self._announcer = announcer

	async def entries(self) -> list[BlacklistEntry]:
		"""List every blacklisted user and guild, oldest first.

		Returns:
			The entries.
		"""
		rows = await self._db.fetch(f"SELECT {_COLUMNS} FROM blacklist ORDER BY created_at, kind, target_id")
		return [_entry(row) for row in rows]

	async def add(self, kind: BlacklistKind, target_id: int, body: BlacklistAdd) -> BlacklistEntry:
		"""Blacklist a user or guild. Blacklisting it again replaces the reason and who added it.

		Args:
			kind: Whether the target is a user or a guild.
			target_id: The user or guild.
			body: Who blacklists it, and why.

		Returns:
			The entry.
		"""
		row = await self._db.fetchrow(
			"INSERT INTO blacklist (kind, target_id, reason, created_by) VALUES ($1, $2, $3, $4) "
			"ON CONFLICT (kind, target_id) DO UPDATE SET reason = EXCLUDED.reason, created_by = EXCLUDED.created_by "
			f"RETURNING {_COLUMNS}",
			kind,
			target_id,
			body.reason,
			body.created_by,
		)
		assert row is not None
		await self._announcer.blacklist_changed(kind, target_id, True)
		return _entry(row)

	async def remove(self, kind: BlacklistKind, target_id: int) -> bool:
		"""Take a user or guild off the blacklist.

		Args:
			kind: Whether the target is a user or a guild.
			target_id: The user or guild.

		Returns:
			Whether it was blacklisted.
		"""
		status = await self._db.execute("DELETE FROM blacklist WHERE kind = $1 AND target_id = $2", kind, target_id)
		if status == "DELETE 0":
			return False
		await self._announcer.blacklist_changed(kind, target_id, False)
		return True

	async def is_blacklisted(self, kind: BlacklistKind, target_id: int) -> bool:
		"""Check whether a user or guild is blacklisted.

		Args:
			kind: Whether the target is a user or a guild.
			target_id: The user or guild.

		Returns:
			Whether it is.
		"""
		return bool(
			await self._db.fetchval(
				"SELECT EXISTS (SELECT 1 FROM blacklist WHERE kind = $1 AND target_id = $2)", kind, target_id
			)
		)

	async def blacklisted_guilds(self, guild_ids: Iterable[int]) -> set[int]:
		"""Pick out the blacklisted guilds among some guilds.

		Args:
			guild_ids: The guilds.

		Returns:
			The ones that are blacklisted.
		"""
		rows = await self._db.fetch(
			"SELECT target_id FROM blacklist WHERE kind = 'guild' AND target_id = ANY($1::numeric[])", list(guild_ids)
		)
		return {int(row["target_id"]) for row in rows}
