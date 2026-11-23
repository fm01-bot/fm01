"""Log configuration routes for the Internal API."""

from __future__ import annotations

from api import GuildLogConfig, LogConfig, Snowflake
from fastapi import APIRouter, Response

from app.auth import Origin, State

__all__ = ("internal",)

internal = APIRouter(tags=["log"])


@internal.get("/settings/log")
async def all_log_configs(state: State) -> list[GuildLogConfig]:
	"""List every guild's log configuration.

	\f
	Args:
		state: The app state.

	Returns:
		The configurations of every guild that configured logging.
	"""
	return await state.log.all()


@internal.get("/guilds/{guild_id}/settings/log")
async def internal_log_config(guild_id: Snowflake, state: State) -> LogConfig | None:
	"""Get a guild's log configuration. `null` if the guild never configured logging.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The configuration, or ``None``.
	"""
	return await state.log.get(guild_id)


@internal.put("/guilds/{guild_id}/settings/log")
async def internal_set_log_config(
	guild_id: Snowflake, body: LogConfig, state: State, origin: Origin = None
) -> LogConfig:
	"""Replace a guild's log configuration.

	\f
	Args:
		guild_id: The guild.
		body: The configuration.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored configuration.
	"""
	return await state.log.set(guild_id, body, origin)


@internal.delete("/guilds/{guild_id}/settings/log", status_code=204)
async def internal_delete_log_config(guild_id: Snowflake, state: State, origin: Origin = None) -> Response:
	"""Remove a guild's log configuration.

	\f
	Args:
		guild_id: The guild.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		An empty response.
	"""
	await state.log.delete(guild_id, origin)
	return Response(status_code=204)
