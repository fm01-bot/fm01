"""The moderation case store and the guild's case retention."""

from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any

import asyncpg
from api import (
	RETENTION_SETTING,
	CaseClosed,
	CaseCreate,
	CaseFilter,
	CaseRecord,
	CaseUpdate,
	ErrorCode,
	PendingCase,
	Retention,
)

from app.errors import ApiError
from app.events import Announcer

__all__ = ("CaseStore",)

_COLUMNS = "case_id, guild_id, type, user_id, moderator_id, reason, expires, message, created, active"

_FILTERS: dict[CaseFilter, str] = {
	"open": " AND active = true",
	"active": " AND active = true AND (expires IS NULL OR expires > now())",
	"expired": " AND (active = false OR (expires IS NOT NULL AND expires <= now()))",
	"all": "",
}


def _case(row: Mapping[str, Any]) -> CaseRecord:
	"""Build a case from a ``cases`` row.

	Args:
		row: The row.

	Returns:
		The case. Rows without ``created`` (from before the column had a default) count as created now.
	"""
	return CaseRecord(
		case_id=int(row["case_id"]),
		guild_id=int(row["guild_id"]),
		type=row["type"],
		user_id=int(row["user_id"]),
		moderator_id=int(row["moderator_id"]),
		reason=row["reason"],
		expires=row["expires"],
		message=row["message"],
		created=row["created"] or datetime.datetime.now(tz=datetime.UTC),
		active=row["active"],
	)


class CaseStore:
	"""Reads and writes moderation cases and guilds' case retention. Announces retention writes.

	Args:
		db: The database pool.
		announcer: Tells bot instances about changes.
	"""

	def __init__(self, db: asyncpg.Pool, announcer: Announcer) -> None:
		self._db = db
		self._announcer = announcer

	async def retention(self, guild_id: int) -> Retention:
		"""Get a guild's case retention.

		Args:
			guild_id: The guild.

		Returns:
			The retention. ``keep`` if the guild never set one.
		"""
		value = await self._db.fetchval("SELECT case_retention FROM mod_config WHERE guild_id = $1", guild_id)
		return "delete" if value == "delete" else "keep"

	async def set_retention(self, guild_id: int, retention: Retention, origin: str | None) -> None:
		"""Set a guild's case retention.

		Args:
			guild_id: The guild.
			retention: The retention.
			origin: The calling bot instance. ``None`` for the dashboard.
		"""
		await self._db.execute(
			"INSERT INTO mod_config (guild_id, case_retention) VALUES ($1, $2) "
			"ON CONFLICT (guild_id) DO UPDATE SET case_retention = EXCLUDED.case_retention",
			guild_id,
			retention,
		)
		await self._announcer.setting_changed(RETENTION_SETTING, guild_id, origin)

	async def get(self, case_id: int, guild_id: int | None = None) -> CaseRecord | None:
		"""Get a case.

		Args:
			case_id: The case.
			guild_id: The guild it must belong to. ``None`` for any guild.

		Returns:
			The case, or ``None`` if there is none.
		"""
		if guild_id is None:
			row = await self._db.fetchrow(f"SELECT {_COLUMNS} FROM cases WHERE case_id = $1", case_id)
		else:
			row = await self._db.fetchrow(
				f"SELECT {_COLUMNS} FROM cases WHERE case_id = $1 AND guild_id = $2", case_id, guild_id
			)
		return _case(row) if row else None

	async def for_user(
		self, guild_id: int, user_id: int, which: CaseFilter = "all", case_type: int | None = None
	) -> list[CaseRecord]:
		"""List a user's cases in a guild, oldest first.

		Args:
			guild_id: The guild.
			user_id: The user the cases are about.
			which: Which cases. See `CaseFilter`.
			case_type: Only cases of this type. ``None`` for every type.

		Returns:
			The cases.
		"""
		query = f"SELECT {_COLUMNS} FROM cases WHERE guild_id = $1 AND user_id = $2" + _FILTERS[which]
		params: list[Any] = [guild_id, user_id]
		if case_type is not None:
			query += " AND type = $3"
			params.append(case_type)
		rows = await self._db.fetch(query + " ORDER BY created, case_id", *params)
		return [_case(row) for row in rows]

	async def create(self, guild_id: int, case: CaseCreate) -> CaseRecord:
		"""Record a new case.

		Args:
			guild_id: The guild.
			case: The case.

		Returns:
			The stored case.
		"""
		row = await self._db.fetchrow(
			"INSERT INTO cases (case_id, guild_id, type, user_id, moderator_id, reason, expires, message, created, "
			f"active) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING {_COLUMNS}",
			case.case_id,
			guild_id,
			case.type,
			case.user_id,
			case.moderator_id,
			case.reason,
			case.expires,
			case.message,
			case.created,
			case.active,
		)
		assert row is not None
		return _case(row)

	async def update(self, guild_id: int, case_id: int, changes: CaseUpdate) -> CaseRecord:
		"""Set a case's reason, expiry and message.

		Args:
			guild_id: The guild.
			case_id: The case.
			changes: The new values.

		Returns:
			The stored case.

		Raises:
			ApiError: ``not_found`` if the guild has no such case.
		"""
		row = await self._db.fetchrow(
			f"UPDATE cases SET reason = $3, expires = $4, message = $5 WHERE case_id = $1 AND guild_id = $2 "
			f"RETURNING {_COLUMNS}",
			case_id,
			guild_id,
			changes.reason,
			changes.expires,
			changes.message,
		)
		if row is None:
			raise ApiError(ErrorCode.NOT_FOUND, "no such case")
		return _case(row)

	async def close(self, guild_id: int, case_id: int) -> CaseClosed:
		"""Close a case following the guild's retention: delete it or mark it inactive. A missing case stays missing.

		Args:
			guild_id: The guild.
			case_id: The case.

		Returns:
			What closing did.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			retention = await conn.fetchval("SELECT case_retention FROM mod_config WHERE guild_id = $1", guild_id)
			if retention == "delete":
				await conn.execute("DELETE FROM cases WHERE case_id = $1 AND guild_id = $2", case_id, guild_id)
				return CaseClosed(outcome="deleted")
			await conn.execute(
				"UPDATE cases SET active = false WHERE case_id = $1 AND guild_id = $2", case_id, guild_id
			)
			return CaseClosed(outcome="deactivated")

	async def delete(self, guild_id: int, case_id: int) -> None:
		"""Delete a case regardless of retention. Deleting a case that doesn't exist does nothing.

		Args:
			guild_id: The guild.
			case_id: The case.
		"""
		await self._db.execute("DELETE FROM cases WHERE case_id = $1 AND guild_id = $2", case_id, guild_id)

	async def pending(self) -> list[PendingCase]:
		"""List every open case that expires.

		Returns:
			The cases, with their guild and expiry.
		"""
		rows = await self._db.fetch(
			"SELECT case_id, guild_id, expires FROM cases WHERE active = true AND expires IS NOT NULL"
		)
		return [
			PendingCase(case_id=int(row["case_id"]), guild_id=int(row["guild_id"]), expires=row["expires"])
			for row in rows
		]
