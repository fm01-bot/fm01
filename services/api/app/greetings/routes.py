"""Join and leave message routes for the Internal API."""

from __future__ import annotations

from api import GreetingConfig, GreetingKind, GreetingUpdate, Snowflake
from fastapi import APIRouter

from app.auth import Origin, State

__all__ = ("internal",)

internal = APIRouter(prefix="/guilds/{guild_id}/settings/greetings/{kind}", tags=["greetings"])


@internal.get("")
async def internal_greeting(guild_id: Snowflake, kind: GreetingKind, state: State) -> GreetingConfig | None:
	"""Get a guild's join or leave configuration. `null` if the guild never configured it.

	\f
	Args:
		guild_id: The guild.
		kind: Join or leave messages.
		state: The app state.

	Returns:
		The configuration, or ``None``.
	"""
	return await state.greetings.get(kind, guild_id)


@internal.patch("")
async def internal_update_greeting(
	guild_id: Snowflake, kind: GreetingKind, body: GreetingUpdate, state: State, origin: Origin = None
) -> GreetingConfig:
	"""Change a guild's join or leave configuration. `null` fields keep their value; a new configuration starts on.

	\f
	Args:
		guild_id: The guild.
		kind: Join or leave messages.
		body: The changes.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored configuration.
	"""
	return await state.greetings.update(kind, guild_id, body, origin)
