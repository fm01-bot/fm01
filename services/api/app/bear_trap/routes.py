"""Bear trap routes for the Internal API and the Dashboard API."""

from __future__ import annotations

from api import (
	BearTrap,
	BearTrapChannel,
	BearTrapKicks,
	BearTrapMessage,
	BearTrapState,
	ErrorCode,
	GuildBearTrap,
	Snowflake,
)
from fastapi import APIRouter

from app.auth import BanManagedGuildId, ManagedGuildId, Origin, State
from app.errors import ApiError

__all__ = ("dashboard", "internal")

GUILD_TEXT = 0
"""Discord's channel type for a plain text channel, the only kind a trap can be set in."""

internal = APIRouter(tags=["bear_trap"])
dashboard = APIRouter(prefix="/guilds/{guild_id}/settings/bear-trap", tags=["bear_trap"])


@internal.get("/settings/bear-trap")
async def all_bear_traps(state: State) -> list[GuildBearTrap]:
	"""List every guild whose trap is on or still has a message posted.

	\f
	Args:
		state: The app state.

	Returns:
		The traps the bot has to watch or clean up.
	"""
	return await state.bear_traps.all()


@internal.get("/guilds/{guild_id}/settings/bear-trap")
async def internal_bear_trap(guild_id: Snowflake, state: State) -> BearTrapState:
	"""Get a guild's bear trap.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The trap. Off with no kicks if the guild never set one.
	"""
	return await state.bear_traps.get(guild_id)


@internal.put("/guilds/{guild_id}/settings/bear-trap")
async def internal_set_bear_trap(
	guild_id: Snowflake, body: BearTrapChannel, state: State, origin: Origin = None
) -> BearTrapState:
	"""Set a guild's bear trap channel. A `null` channel turns the trap off.

	\f
	Args:
		guild_id: The guild.
		body: The channel.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored trap.
	"""
	return await state.bear_traps.set_channel(guild_id, body.channel_id, origin)


@internal.put("/guilds/{guild_id}/settings/bear-trap/message")
async def internal_set_bear_trap_message(
	guild_id: Snowflake, body: BearTrapMessage, state: State, origin: Origin = None
) -> BearTrapState:
	"""Record the trap message the bot posted. `null` fields record that it removed it.

	\f
	Args:
		guild_id: The guild.
		body: The message.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored trap.
	"""
	return await state.bear_traps.set_message(guild_id, body, origin)


@internal.post("/guilds/{guild_id}/settings/bear-trap/kicks")
async def internal_add_bear_trap_kick(guild_id: Snowflake, state: State, origin: Origin = None) -> BearTrapKicks:
	"""Count one more member the trap soft-banned.

	\f
	Args:
		guild_id: The guild.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The new count.
	"""
	return await state.bear_traps.add_kick(guild_id, origin)


@dashboard.get("")
async def bear_trap(guild_id: ManagedGuildId, state: State) -> BearTrap:
	"""Get a guild's bear trap.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		state: The app state.

	Returns:
		The trap's channel and kick count.
	"""
	trap = await state.bear_traps.get(guild_id)
	return BearTrap(channel_id=trap.channel_id, kicks=trap.kicks)


@dashboard.put("")
async def set_bear_trap(guild_id: BanManagedGuildId, body: BearTrapChannel, state: State) -> BearTrap:
	"""Set a guild's bear trap channel. A `null` channel turns the trap off.

	The bot posts the trap message in the channel. If it can't, it turns the trap off again. The trap soft-bans
	whoever posts there, so the caller needs Ban Members as well as managing the guild.

	\f
	Args:
		guild_id: The guild. The caller must manage it and be able to ban members.
		body: The channel. It must be a text channel in the guild.
		state: The app state.

	Returns:
		The stored trap.

	Raises:
		ApiError: ``invalid_channel`` if the channel isn't a text channel in the guild.
	"""
	if body.channel_id is not None:
		channel = await state.discord.guild_channel(guild_id, body.channel_id)
		if channel is None or channel.get("type") != GUILD_TEXT:
			raise ApiError(ErrorCode.INVALID_CHANNEL, "the channel is not a text channel in this guild")
	trap = await state.bear_traps.set_channel(guild_id, body.channel_id, origin=None)
	return BearTrap(channel_id=trap.channel_id, kicks=trap.kicks)
