"""AFK routes for the Internal API."""

from __future__ import annotations

from api import AfkMember, AfkToggle, AfkToggled, Snowflake
from fastapi import APIRouter, Response

from app.auth import State

__all__ = ("internal",)

internal = APIRouter(tags=["afk"])


@internal.get("/afk")
async def internal_away_members(state: State) -> list[AfkMember]:
	"""List every member who is away, in every guild.

	\f
	Args:
		state: The app state.

	Returns:
		The members, with their reason and previous nickname.
	"""
	return await state.afk.away()


@internal.post("/guilds/{guild_id}/afk/{user_id}/toggle")
async def internal_toggle_afk(guild_id: Snowflake, user_id: Snowflake, body: AfkToggle, state: State) -> AfkToggled:
	"""Make a member away, or back if they are away.

	\f
	Args:
		guild_id: The guild.
		user_id: The member.
		body: The reason and current nickname, recorded if the member becomes away.
		state: The app state.

	Returns:
		Whether the member is now away, and the nickname to restore if they're back.
	"""
	return await state.afk.toggle(guild_id, user_id, body)


@internal.delete("/guilds/{guild_id}/afk/{user_id}", status_code=204)
async def internal_afk_back(guild_id: Snowflake, user_id: Snowflake, state: State) -> Response:
	"""Mark a member as back. Does nothing if they weren't away.

	\f
	Args:
		guild_id: The guild.
		user_id: The member.
		state: The app state.

	Returns:
		An empty response.
	"""
	await state.afk.back(guild_id, user_id)
	return Response(status_code=204)
