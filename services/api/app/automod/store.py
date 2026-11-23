"""The AutoMod configuration store."""

from __future__ import annotations

import asyncpg
from api import AUTOMOD_SETTING, AutoModConfig

from app.events import Announcer

__all__ = ("AutoModStore",)


class AutoModStore:
	"""Reads and writes guilds' AutoMod configurations. Announces every write.

	Args:
		db: The database pool.
		announcer: Tells bot instances about changes.
	"""

	def __init__(self, db: asyncpg.Pool, announcer: Announcer) -> None:
		self._db = db
		self._announcer = announcer

	async def get(self, guild_id: int) -> AutoModConfig:
		"""Get a guild's AutoMod configuration.

		Args:
			guild_id: The guild.

		Returns:
			The configuration. Off with no settings if the guild never configured AutoMod.
		"""
		row = await self._db.fetchrow("SELECT is_on, settings FROM automod_config WHERE guild_id = $1", guild_id)
		if row is None:
			return AutoModConfig()
		settings = row["settings"]
		return AutoModConfig(enabled=row["is_on"], settings=settings if isinstance(settings, dict) else {})

	async def set(self, guild_id: int, config: AutoModConfig, origin: str | None) -> AutoModConfig:
		"""Replace a guild's AutoMod configuration.

		Args:
			guild_id: The guild.
			config: The configuration.
			origin: The calling bot instance. ``None`` for the dashboard.

		Returns:
			The stored configuration.
		"""
		await self._db.execute(
			"INSERT INTO automod_config (guild_id, is_on, settings) VALUES ($1, $2, $3) "
			"ON CONFLICT (guild_id) DO UPDATE SET is_on = EXCLUDED.is_on, settings = EXCLUDED.settings",
			guild_id,
			config.enabled,
			config.settings,
		)
		await self._announcer.setting_changed(AUTOMOD_SETTING, guild_id, origin)
		return config
