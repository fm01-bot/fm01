"""Guild settings routes for the Internal API and the Dashboard API."""

from __future__ import annotations

from api import GuildLocale, GuildPrefix, LocaleOverride, Prefix, Snowflake
from fastapi import APIRouter

from app.auth import ManagedGuildId, Origin, State

__all__ = ("dashboard", "internal")

internal = APIRouter(tags=["settings"])
dashboard = APIRouter(prefix="/guilds/{guild_id}/settings", tags=["settings"])


@internal.get("/settings/prefix")
async def all_prefixes(state: State) -> list[GuildPrefix]:
	"""List every guild's prefix.

	\f
	Args:
		state: The app state.

	Returns:
		The prefix of every guild with a ``guilds`` row.
	"""
	return await state.guild_settings.all_prefixes()


@internal.get("/guilds/{guild_id}/settings/prefix")
async def internal_prefix(guild_id: Snowflake, state: State) -> Prefix:
	"""Get a guild's prefix.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The prefix.
	"""
	return await state.guild_settings.prefix(guild_id)


@internal.put("/guilds/{guild_id}/settings/prefix")
async def internal_set_prefix(guild_id: Snowflake, body: Prefix, state: State, origin: Origin = None) -> Prefix:
	"""Set a guild's prefix.

	\f
	Args:
		guild_id: The guild.
		body: The new prefix.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored prefix.
	"""
	return await state.guild_settings.set_prefix(guild_id, body, origin)


@internal.get("/settings/locale")
async def all_locales(state: State) -> list[GuildLocale]:
	"""List every guild's locale override.

	\f
	Args:
		state: The app state.

	Returns:
		The locale of every guild with an override.
	"""
	return await state.guild_settings.all_locales()


@internal.get("/guilds/{guild_id}/settings/locale")
async def internal_locale(guild_id: Snowflake, state: State) -> LocaleOverride:
	"""Get a guild's locale override.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The override. Its ``locale`` is ``None`` if there is none.
	"""
	return await state.guild_settings.locale(guild_id)


@internal.put("/guilds/{guild_id}/settings/locale")
async def internal_set_locale(
	guild_id: Snowflake, body: LocaleOverride, state: State, origin: Origin = None
) -> LocaleOverride:
	"""Set a guild's locale override. A `null` locale removes it.

	\f
	Args:
		guild_id: The guild.
		body: The new override.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored override.
	"""
	return await state.guild_settings.set_locale(guild_id, body, origin)


@dashboard.get("/prefix")
async def prefix(guild_id: ManagedGuildId, state: State) -> Prefix:
	"""Get a guild's prefix.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		state: The app state.

	Returns:
		The prefix.
	"""
	return await state.guild_settings.prefix(guild_id)


@dashboard.put("/prefix")
async def set_prefix(guild_id: ManagedGuildId, body: Prefix, state: State) -> Prefix:
	"""Set a guild's prefix.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		body: The new prefix.
		state: The app state.

	Returns:
		The stored prefix.
	"""
	return await state.guild_settings.set_prefix(guild_id, body, origin=None)


@dashboard.get("/locale")
async def locale(guild_id: ManagedGuildId, state: State) -> LocaleOverride:
	"""Get a guild's locale override.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		state: The app state.

	Returns:
		The override. Its ``locale`` is ``None`` if there is none.
	"""
	return await state.guild_settings.locale(guild_id)


@dashboard.put("/locale")
async def set_locale(guild_id: ManagedGuildId, body: LocaleOverride, state: State) -> LocaleOverride:
	"""Set a guild's locale override. A `null` locale removes it.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		body: The new override.
		state: The app state.

	Returns:
		The stored override.
	"""
	return await state.guild_settings.set_locale(guild_id, body, origin=None)
