"""AutoMod routes for the Internal API."""

from __future__ import annotations

from api import AutoModConfig, Snowflake
from fastapi import APIRouter

from app.auth import Origin, State

__all__ = ("internal",)

internal = APIRouter(prefix="/guilds/{guild_id}/settings/automod", tags=["automod"])


@internal.get("")
async def internal_automod(guild_id: Snowflake, state: State) -> AutoModConfig:
	"""Get a guild's AutoMod configuration. Off with no settings if the guild never configured AutoMod.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The configuration.
	"""
	return await state.automod.get(guild_id)


@internal.put("")
async def internal_set_automod(
	guild_id: Snowflake, body: AutoModConfig, state: State, origin: Origin = None
) -> AutoModConfig:
	"""Replace a guild's AutoMod configuration.

	\f
	Args:
		guild_id: The guild.
		body: The configuration.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored configuration.
	"""
	return await state.automod.set(guild_id, body, origin)
