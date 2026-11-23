"""The log configuration store."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import asyncpg
from api import LOG_SETTING, GuildLogConfig, LogConfig

from app.db import snowflake
from app.events import Announcer

__all__ = ("LogStore",)

_COLUMNS = "guild_id, is_on, channel, channels, modules, webhook"


def _config(row: Mapping[str, Any]) -> GuildLogConfig:
	"""Build a log configuration from a ``log`` row.

	Args:
		row: The row.

	Returns:
		The configuration.
	"""
	channels = row["channels"] or {}
	if isinstance(channels, str):  # rows written before the jsonb codec, as a JSON string
		try:
			channels = json.loads(channels)
		except ValueError:
			channels = {}
	return GuildLogConfig(
		guild_id=int(row["guild_id"]),
		enabled=row["is_on"],
		channel_id=snowflake(row["channel"]),
		channels={str(k): int(v) for k, v in channels.items() if v} if isinstance(channels, dict) else {},
		modules=list(row["modules"] or ()),
		webhook_url=row["webhook"],
	)


class LogStore:
	"""Reads and writes guilds' log configurations. Announces every write.

	Args:
		db: The database pool.
		announcer: Tells bot instances about changes.
	"""

	def __init__(self, db: asyncpg.Pool, announcer: Announcer) -> None:
		self._db = db
		self._announcer = announcer

	async def get(self, guild_id: int) -> LogConfig | None:
		"""Get a guild's log configuration.

		Args:
			guild_id: The guild.

		Returns:
			The configuration, or ``None`` if the guild never configured logging.
		"""
		row = await self._db.fetchrow(f"SELECT {_COLUMNS} FROM log WHERE guild_id = $1", guild_id)
		return LogConfig.model_validate(_config(row).model_dump(exclude={"guild_id"})) if row else None

	async def all(self) -> list[GuildLogConfig]:
		"""List every guild's log configuration.

		Returns:
			The configurations of every guild that configured logging.
		"""
		return [_config(row) for row in await self._db.fetch(f"SELECT {_COLUMNS} FROM log")]

	async def set(self, guild_id: int, config: LogConfig, origin: str | None) -> LogConfig:
		"""Replace a guild's log configuration.

		Args:
			guild_id: The guild.
			config: The configuration.
			origin: The calling bot instance. ``None`` for the dashboard.

		Returns:
			The stored configuration.
		"""
		await self._db.execute(
			"INSERT INTO log (guild_id, is_on, channel, modules, channels, webhook) VALUES ($1, $2, $3, $4, $5, $6) "
			"ON CONFLICT (guild_id) DO UPDATE SET is_on = EXCLUDED.is_on, channel = EXCLUDED.channel, "
			"modules = EXCLUDED.modules, channels = EXCLUDED.channels, webhook = EXCLUDED.webhook",
			guild_id,
			config.enabled,
			config.channel_id,
			sorted(set(config.modules)),
			{event: str(channel) for event, channel in config.channels.items()},
			config.webhook_url,
		)
		await self._announcer.setting_changed(LOG_SETTING, guild_id, origin)
		return config

	async def delete(self, guild_id: int, origin: str | None) -> None:
		"""Remove a guild's log configuration.

		Args:
			guild_id: The guild.
			origin: The calling bot instance. ``None`` for the dashboard.
		"""
		await self._db.execute("DELETE FROM log WHERE guild_id = $1", guild_id)
		await self._announcer.setting_changed(LOG_SETTING, guild_id, origin)
