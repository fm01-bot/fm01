"""The join and leave message store."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import asyncpg
from api import JOIN_SETTING, LEAVE_SETTING, GreetingConfig, GreetingKind, GreetingUpdate

from app.db import snowflake
from app.events import Announcer

__all__ = ("GreetingStore",)

_TABLES: dict[GreetingKind, str] = {"join": "join_config", "leave": "leave_config"}
_SETTINGS: dict[GreetingKind, str] = {"join": JOIN_SETTING, "leave": LEAVE_SETTING}


def _config(row: Mapping[str, Any]) -> GreetingConfig:
	"""Build a greeting configuration from a ``join_config`` or ``leave_config`` row.

	Args:
		row: The row.

	Returns:
		The configuration.
	"""
	return GreetingConfig(enabled=row["is_on"], channel_id=snowflake(row["channel"]), message=row["message"])


class GreetingStore:
	"""Reads and writes guilds' join and leave messages. Announces every write.

	Args:
		db: The database pool.
		announcer: Tells bot instances about changes.
	"""

	def __init__(self, db: asyncpg.Pool, announcer: Announcer) -> None:
		self._db = db
		self._announcer = announcer

	async def get(self, kind: GreetingKind, guild_id: int) -> GreetingConfig | None:
		"""Get a guild's join or leave configuration.

		Args:
			kind: Join or leave messages.
			guild_id: The guild.

		Returns:
			The configuration, or ``None`` if the guild never configured it.
		"""
		row = await self._db.fetchrow(
			f"SELECT is_on, channel, message FROM {_TABLES[kind]} WHERE guild_id = $1", guild_id
		)
		return _config(row) if row else None

	async def update(
		self, kind: GreetingKind, guild_id: int, changes: GreetingUpdate, origin: str | None
	) -> GreetingConfig:
		"""Change a guild's join or leave configuration, creating it (on) if it doesn't exist.

		Args:
			kind: Join or leave messages.
			guild_id: The guild.
			changes: The changes. ``None`` fields keep their value.
			origin: The calling bot instance. ``None`` for the dashboard.

		Returns:
			The stored configuration.
		"""
		table = _TABLES[kind]
		row = await self._db.fetchrow(
			f"INSERT INTO {table} (guild_id, is_on, channel, message) "
			"VALUES ($1, COALESCE($2::boolean, true), COALESCE($3::numeric, $5::numeric), $4::text) "
			"ON CONFLICT (guild_id) DO UPDATE SET "
			f"is_on = COALESCE($2, {table}.is_on), "
			f"channel = COALESCE($3, {table}.channel, $5), "
			f"message = COALESCE($4, {table}.message) "
			"RETURNING is_on, channel, message",
			guild_id,
			changes.enabled,
			changes.channel_id,
			changes.message,
			changes.fallback_channel_id,
		)
		await self._announcer.setting_changed(_SETTINGS[kind], guild_id, origin)
		return _config(row)
