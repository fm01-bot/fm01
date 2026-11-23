"""The guild settings store."""

from __future__ import annotations

import asyncpg
from api import LOCALE_SETTING, PREFIX_SETTING, GuildLocale, GuildPrefix, LocaleOverride, Prefix

from app.events import Announcer

__all__ = ("GuildSettingsStore",)


class GuildSettingsStore:
	"""Reads and writes guild settings. Announces every write.

	Args:
		db: The database pool.
		announcer: Tells bot instances about changes.
	"""

	def __init__(self, db: asyncpg.Pool, announcer: Announcer) -> None:
		self._db = db
		self._announcer = announcer

	async def prefix(self, guild_id: int) -> Prefix:
		"""Get a guild's prefix. Creates the guild's ``guilds`` row if missing.

		Args:
			guild_id: The guild.

		Returns:
			The prefix.
		"""
		row = await self._db.fetchrow(
			"INSERT INTO guilds (guild_id) VALUES ($1) "
			"ON CONFLICT (guild_id) DO UPDATE SET guild_id = EXCLUDED.guild_id RETURNING prefix, mention",
			guild_id,
		)
		assert row is not None
		return Prefix(prefix=row["prefix"], mention=row["mention"])

	async def set_prefix(self, guild_id: int, value: Prefix, origin: str | None) -> Prefix:
		"""Set a guild's prefix.

		Args:
			guild_id: The guild.
			value: The new prefix.
			origin: The calling bot instance. ``None`` for the dashboard.

		Returns:
			The stored prefix.
		"""
		await self._db.execute(
			"INSERT INTO guilds (guild_id, prefix, mention) VALUES ($1, $2, $3) "
			"ON CONFLICT (guild_id) DO UPDATE SET prefix = EXCLUDED.prefix, mention = EXCLUDED.mention",
			guild_id,
			value.prefix,
			value.mention,
		)
		await self._announcer.setting_changed(PREFIX_SETTING, guild_id, origin)
		return value

	async def all_prefixes(self) -> list[GuildPrefix]:
		"""List every guild's prefix.

		Returns:
			The prefix of every guild with a ``guilds`` row.
		"""
		rows = await self._db.fetch("SELECT guild_id, prefix, mention FROM guilds")
		return [GuildPrefix(guild_id=int(r["guild_id"]), prefix=r["prefix"], mention=r["mention"]) for r in rows]

	async def locale(self, guild_id: int) -> LocaleOverride:
		"""Get a guild's locale override.

		Args:
			guild_id: The guild.

		Returns:
			The override. Its ``locale`` is ``None`` if there is none.
		"""
		value = await self._db.fetchval("SELECT locale FROM guild_locale_overrides WHERE guild_id = $1", guild_id)
		return LocaleOverride(locale=value)

	async def set_locale(self, guild_id: int, value: LocaleOverride, origin: str | None) -> LocaleOverride:
		"""Set a guild's locale override.

		Args:
			guild_id: The guild.
			value: The new override. A ``None`` locale removes it.
			origin: The calling bot instance. ``None`` for the dashboard.

		Returns:
			The stored override.
		"""
		if value.locale is None:
			await self._db.execute("DELETE FROM guild_locale_overrides WHERE guild_id = $1", guild_id)
		else:
			await self._db.execute(
				"INSERT INTO guild_locale_overrides (guild_id, locale) VALUES ($1, $2) "
				"ON CONFLICT (guild_id) DO UPDATE SET locale = EXCLUDED.locale",
				guild_id,
				value.locale,
			)
		await self._announcer.setting_changed(LOCALE_SETTING, guild_id, origin)
		return value

	async def all_locales(self) -> list[GuildLocale]:
		"""List every guild's locale override.

		Returns:
			The locale of every guild with an override.
		"""
		rows = await self._db.fetch("SELECT guild_id, locale FROM guild_locale_overrides")
		return [GuildLocale(guild_id=int(r["guild_id"]), locale=r["locale"]) for r in rows]
