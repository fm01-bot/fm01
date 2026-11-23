"""Giveaway routes for the Internal API."""

from __future__ import annotations

from typing import Annotated

from api import (
	ErrorCode,
	GiveawayCreate,
	GiveawayEntrants,
	GiveawayEntry,
	GiveawayEntryChange,
	GiveawayEntryCount,
	GiveawayMessage,
	GiveawayRecord,
	GiveawayStatus,
	GiveawayWinners,
	MessageCount,
	Snowflake,
)
from fastapi import APIRouter, Body, Query, Response

from app.auth import State
from app.errors import ApiError

__all__ = ("internal",)

internal = APIRouter(tags=["giveaways"])


def _found(giveaway: GiveawayRecord | None) -> GiveawayRecord:
	"""Check that a giveaway was found.

	Args:
		giveaway: The giveaway, or ``None``.

	Returns:
		The giveaway.

	Raises:
		ApiError: ``not_found`` if it is ``None``.
	"""
	if giveaway is None:
		raise ApiError(ErrorCode.NOT_FOUND, "no such giveaway")
	return giveaway


@internal.get("/giveaways/active")
async def internal_active_giveaways(state: State) -> list[GiveawayRecord]:
	"""List every active giveaway, in every guild.

	\f
	Args:
		state: The app state.

	Returns:
		The giveaways.
	"""
	return await state.giveaways.active()


@internal.post("/giveaways/message-counts", status_code=204)
async def internal_add_giveaway_message_counts(
	body: Annotated[list[MessageCount], Body(max_length=10_000)], state: State
) -> Response:
	"""Add messages members sent to their counts in giveaways that count messages.

	\f
	Args:
		body: The messages since the last flush, per giveaway and member.
		state: The app state.

	Returns:
		An empty response.
	"""
	await state.giveaways.add_message_counts(body)
	return Response(status_code=204)


@internal.post("/giveaways/purge", status_code=204)
async def internal_purge_giveaways(state: State) -> Response:
	"""Delete the entries and message counts of giveaways that finished more than 30 days ago.

	\f
	Args:
		state: The app state.

	Returns:
		An empty response.
	"""
	await state.giveaways.purge()
	return Response(status_code=204)


@internal.post("/guilds/{guild_id}/giveaways", status_code=201)
async def internal_create_giveaway(guild_id: Snowflake, body: GiveawayCreate, state: State) -> GiveawayRecord:
	"""Start a giveaway. The bot posts its message next.

	\f
	Args:
		guild_id: The guild.
		body: The giveaway.
		state: The app state.

	Returns:
		The stored giveaway.
	"""
	return await state.giveaways.create(guild_id, body)


@internal.get("/channels/{channel_id}/giveaway")
async def internal_find_giveaway(
	channel_id: Snowflake,
	status: GiveawayStatus,
	state: State,
	message_id: Annotated[Snowflake | None, Query()] = None,
) -> GiveawayRecord:
	"""Find a channel's giveaway with a status: the one with the message, else the newest.

	\f
	Args:
		channel_id: The channel.
		status: The status it must have.
		state: The app state.
		message_id: Its message.

	Returns:
		The giveaway.
	"""
	return _found(await state.giveaways.lookup(channel_id, status, message_id))


@internal.get("/giveaways/{giveaway_id}")
async def internal_giveaway(giveaway_id: int, state: State) -> GiveawayRecord:
	"""Get a giveaway.

	\f
	Args:
		giveaway_id: The giveaway.
		state: The app state.

	Returns:
		The giveaway.
	"""
	return _found(await state.giveaways.get(giveaway_id))


@internal.delete("/giveaways/{giveaway_id}", status_code=204)
async def internal_delete_giveaway(giveaway_id: int, state: State) -> Response:
	"""Delete a giveaway with its entries, e.g. when its message couldn't be posted.

	\f
	Args:
		giveaway_id: The giveaway.
		state: The app state.

	Returns:
		An empty response.
	"""
	await state.giveaways.delete(giveaway_id)
	return Response(status_code=204)


@internal.put("/giveaways/{giveaway_id}/message")
async def internal_set_giveaway_message(giveaway_id: int, body: GiveawayMessage, state: State) -> GiveawayRecord:
	"""Record the message the bot posted for a giveaway.

	\f
	Args:
		giveaway_id: The giveaway.
		body: The message.
		state: The app state.

	Returns:
		The stored giveaway.
	"""
	return _found(await state.giveaways.set_message(giveaway_id, body.message_id))


@internal.post("/giveaways/{giveaway_id}/end")
async def internal_end_giveaway(giveaway_id: int, state: State) -> GiveawayRecord:
	"""End an active giveaway. The bot draws the winners next.

	\f
	Args:
		giveaway_id: The giveaway.
		state: The app state.

	Returns:
		The ended giveaway. ``not_found`` if it wasn't active.
	"""
	return _found(await state.giveaways.finish(giveaway_id, "ended"))


@internal.post("/giveaways/{giveaway_id}/cancel")
async def internal_cancel_giveaway(giveaway_id: int, state: State) -> GiveawayRecord:
	"""Cancel an active giveaway without drawing winners.

	\f
	Args:
		giveaway_id: The giveaway.
		state: The app state.

	Returns:
		The cancelled giveaway. ``not_found`` if it wasn't active.
	"""
	return _found(await state.giveaways.finish(giveaway_id, "cancelled"))


@internal.get("/giveaways/{giveaway_id}/entries")
async def internal_giveaway_entrants(giveaway_id: int, state: State) -> GiveawayEntrants:
	"""List the members who entered a giveaway and haven't won it.

	\f
	Args:
		giveaway_id: The giveaway.
		state: The app state.

	Returns:
		The members.
	"""
	return GiveawayEntrants(user_ids=await state.giveaways.entrants(giveaway_id))


@internal.get("/giveaways/{giveaway_id}/entries/count")
async def internal_giveaway_entry_count(giveaway_id: int, state: State) -> GiveawayEntryCount:
	"""Count a giveaway's entries.

	\f
	Args:
		giveaway_id: The giveaway.
		state: The app state.

	Returns:
		The count.
	"""
	return GiveawayEntryCount(count=await state.giveaways.entry_count(giveaway_id))


@internal.get("/giveaways/{giveaway_id}/entries/{user_id}")
async def internal_giveaway_entry(giveaway_id: int, user_id: Snowflake, state: State) -> GiveawayEntry:
	"""Get a member's entry in a giveaway.

	\f
	Args:
		giveaway_id: The giveaway.
		user_id: The member.
		state: The app state.

	Returns:
		Whether they entered, and their stored message count.
	"""
	return await state.giveaways.entry(giveaway_id, user_id)


@internal.put("/giveaways/{giveaway_id}/entries/{user_id}")
async def internal_enter_giveaway(giveaway_id: int, user_id: Snowflake, state: State) -> GiveawayEntryChange:
	"""Enter a member into a giveaway. The bot checks the requirements first.

	\f
	Args:
		giveaway_id: The giveaway.
		user_id: The member.
		state: The app state.

	Returns:
		Whether they were newly entered.
	"""
	return GiveawayEntryChange(changed=await state.giveaways.enter(giveaway_id, user_id))


@internal.delete("/giveaways/{giveaway_id}/entries/{user_id}")
async def internal_leave_giveaway(giveaway_id: int, user_id: Snowflake, state: State) -> GiveawayEntryChange:
	"""Remove a member's entry from a giveaway.

	\f
	Args:
		giveaway_id: The giveaway.
		user_id: The member.
		state: The app state.

	Returns:
		Whether they had entered.
	"""
	return GiveawayEntryChange(changed=await state.giveaways.leave(giveaway_id, user_id))


@internal.post("/giveaways/{giveaway_id}/winners", status_code=204)
async def internal_giveaway_winners(giveaway_id: int, body: GiveawayWinners, state: State) -> Response:
	"""Record that members won a giveaway, so a reroll doesn't draw them again.

	\f
	Args:
		giveaway_id: The giveaway.
		body: The winners.
		state: The app state.

	Returns:
		An empty response.
	"""
	await state.giveaways.mark_winners(giveaway_id, body.user_ids)
	return Response(status_code=204)


@internal.get("/giveaways/{giveaway_id}/message-counts")
async def internal_giveaway_message_counts(giveaway_id: int, state: State) -> list[MessageCount]:
	"""List the message counts of a giveaway's members.

	\f
	Args:
		giveaway_id: The giveaway.
		state: The app state.

	Returns:
		The counts of members who sent messages since it started.
	"""
	return await state.giveaways.message_counts(giveaway_id)
