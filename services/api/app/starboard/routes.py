"""Starboard routes for the Internal API and the Dashboard API."""

from __future__ import annotations

from api import (
	ClearStars,
	ErrorCode,
	GuildStarboards,
	MessageIds,
	Snowflake,
	Starboard,
	StarboardBlock,
	StarboardEntry,
	StarboardName,
	StarboardPost,
	StarboardUpdate,
	StarChange,
	StarredMessage,
	StarResult,
	StarSeed,
)
from fastapi import APIRouter, Response

from app.auth import ManagedGuildId, Origin, State
from app.errors import ApiError
from app.state import AppState

__all__ = ("dashboard", "internal")

GUILD_TEXT = 0
"""Discord's channel type for a plain text channel, the only kind a board can post in."""

internal = APIRouter(tags=["starboard"])
dashboard = APIRouter(prefix="/guilds/{guild_id}/settings/starboards", tags=["starboard"])


@internal.get("/settings/starboards")
async def all_starboards(state: State) -> list[GuildStarboards]:
	"""List the boards of every guild that has any.

	\f
	Args:
		state: The app state.

	Returns:
		Each guild's boards.
	"""
	return await state.starboards.all()


@internal.get("/guilds/{guild_id}/settings/starboards")
async def internal_starboards(guild_id: Snowflake, state: State) -> list[Starboard]:
	"""List a guild's boards.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The boards, by name.
	"""
	return await state.starboards.boards(guild_id)


@internal.post("/guilds/{guild_id}/settings/starboards", status_code=201)
async def internal_create_starboard(
	guild_id: Snowflake, body: Starboard, state: State, origin: Origin = None
) -> Starboard:
	"""Add a board to a guild.

	\f
	Args:
		guild_id: The guild.
		body: The board.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored board.
	"""
	return await state.starboards.create(guild_id, body, origin)


@internal.patch("/guilds/{guild_id}/settings/starboards/{name}")
async def internal_update_starboard(
	guild_id: Snowflake, name: StarboardName, body: StarboardUpdate, state: State, origin: Origin = None
) -> Starboard:
	"""Change a board. Fields left out keep their value.

	\f
	Args:
		guild_id: The guild.
		name: The board.
		body: The changes.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored board.
	"""
	return await state.starboards.update(guild_id, name, body, origin)


@internal.delete("/guilds/{guild_id}/settings/starboards/{name}", status_code=204)
async def internal_delete_starboard(
	guild_id: Snowflake, name: StarboardName, state: State, origin: Origin = None
) -> Response:
	"""Remove a board with its entries and blocks. Its posts stay in the channel.

	\f
	Args:
		guild_id: The guild.
		name: The board.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		An empty response.
	"""
	await state.starboards.delete(guild_id, name, origin)
	return Response(status_code=204)


@internal.post("/guilds/{guild_id}/starboard/stars")
async def internal_star(guild_id: Snowflake, body: StarChange, state: State) -> StarResult:
	"""Add or remove one member's star on a message, or on one of its posts.

	`message` is `null` if the API has never seen the message. The bot then seeds it, or ignores the star if it was
	on a message in a board channel that isn't a post.

	\f
	Args:
		guild_id: The guild.
		body: The star.
		state: The app state.

	Returns:
		The message's stars and entries after the change.
	"""
	return await state.starboards.star(guild_id, body)


@internal.post("/guilds/{guild_id}/starboard/seeds")
async def internal_seed_stars(guild_id: Snowflake, body: StarSeed, state: State) -> StarredMessage:
	"""Record everyone who starred a message with an emoji, as read from Discord.

	\f
	Args:
		guild_id: The guild.
		body: The message and its starrers.
		state: The app state.

	Returns:
		The message's stars and entries.
	"""
	return await state.starboards.seed(guild_id, body)


@internal.put("/guilds/{guild_id}/starboard/posts")
async def internal_set_starboard_post(guild_id: Snowflake, body: StarboardPost, state: State) -> StarboardEntry:
	"""Record the post the bot made for a message on a board. `null` fields record that it removed the post.

	\f
	Args:
		guild_id: The guild.
		body: The post.
		state: The app state.

	Returns:
		The message's entry on the board.
	"""
	return await state.starboards.set_post(guild_id, body)


@internal.post("/guilds/{guild_id}/starboard/posts/deleted")
async def internal_starboard_posts_deleted(guild_id: Snowflake, body: MessageIds, state: State) -> list[StarboardEntry]:
	"""Block the messages whose posts were deleted by someone other than the bot.

	\f
	Args:
		guild_id: The guild.
		body: The deleted messages from board channels.
		state: The app state.

	Returns:
		The entries now blocked.
	"""
	return await state.starboards.posts_deleted(guild_id, body.message_ids)


@internal.post("/guilds/{guild_id}/starboard/messages/deleted")
async def internal_starred_messages_deleted(
	guild_id: Snowflake, body: MessageIds, state: State
) -> list[StarboardEntry]:
	"""Forget deleted originals with their stars and entries.

	\f
	Args:
		guild_id: The guild.
		body: The deleted messages.
		state: The app state.

	Returns:
		The entries that had a post, for the bot to delete.
	"""
	return await state.starboards.messages_deleted(guild_id, body.message_ids)


@internal.post("/guilds/{guild_id}/starboard/messages/{message_id}/clear")
async def internal_clear_stars(
	guild_id: Snowflake, message_id: Snowflake, body: ClearStars, state: State
) -> list[StarboardEntry]:
	"""Forget a message's stars after its reactions were cleared, and take down its posts.

	\f
	Args:
		guild_id: The guild.
		message_id: The original.
		body: The emoji cleared, or `null` for all of them.
		state: The app state.

	Returns:
		The entries that had a post, as they were, for the bot to delete.
	"""
	return await state.starboards.clear(guild_id, message_id, body.emoji)


async def _check_board(state: AppState, guild_id: int, channel_id: int | None, emoji: str | None) -> None:
	"""Check a board's channel and emoji against Discord.

	Args:
		state: The app state.
		guild_id: The guild.
		channel_id: The board's channel, if it is being set.
		emoji: The board's emoji, if it is being set.

	Raises:
		ApiError: ``invalid_channel`` if the channel isn't a text channel in the guild, ``invalid_emoji`` if the emoji
			is a custom emoji the guild doesn't have.
	"""
	if channel_id is not None:
		channel = await state.discord.guild_channel(guild_id, channel_id)
		if channel is None or channel.get("type") != GUILD_TEXT:
			raise ApiError(ErrorCode.INVALID_CHANNEL, "the channel is not a text channel in this guild")
	if emoji is not None and emoji.isdigit() and await state.discord.guild_emoji(guild_id, int(emoji)) is None:
		raise ApiError(ErrorCode.INVALID_EMOJI, "the emoji is not a custom emoji of this guild")


@dashboard.get("")
async def starboards(guild_id: ManagedGuildId, state: State) -> list[Starboard]:
	"""List a guild's boards.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		state: The app state.

	Returns:
		The boards, by name.
	"""
	return await state.starboards.boards(guild_id)


@dashboard.post("", status_code=201)
async def create_starboard(guild_id: ManagedGuildId, body: Starboard, state: State) -> Starboard:
	"""Add a board. A guild can have at most 5.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		body: The board. Its channel must be a text channel in the guild, and a custom emoji must be the guild's.
		state: The app state.

	Returns:
		The stored board.

	Raises:
		ApiError: ``invalid_channel``, ``invalid_emoji``, ``starboard_limit``, ``starboard_name_taken`` or
			``starboard_tier_taken``.
	"""
	await _check_board(state, guild_id, body.channel_id, body.emoji)
	return await state.starboards.create(guild_id, body, origin=None)


@dashboard.patch("/{name}")
async def update_starboard(
	guild_id: ManagedGuildId, name: StarboardName, body: StarboardUpdate, state: State
) -> Starboard:
	"""Change a board. Fields left out keep their value. Existing posts follow the change at their next star.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		name: The board.
		body: The changes. A new channel or emoji is checked like on create.
		state: The app state.

	Returns:
		The stored board.

	Raises:
		ApiError: ``not_found``, ``invalid_channel``, ``invalid_emoji``, ``starboard_name_taken`` or
			``starboard_tier_taken``.
	"""
	await _check_board(state, guild_id, body.channel_id, body.emoji)
	return await state.starboards.update(guild_id, name, body, origin=None)


@dashboard.delete("/{name}", status_code=204)
async def delete_starboard(guild_id: ManagedGuildId, name: StarboardName, state: State) -> Response:
	"""Remove a board with its entries and blocks. Its posts stay in the channel.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		name: The board.
		state: The app state.

	Returns:
		An empty response.

	Raises:
		ApiError: ``not_found`` if the guild has no such board.
	"""
	await state.starboards.delete(guild_id, name, origin=None)
	return Response(status_code=204)


@dashboard.get("/{name}/blocks")
async def starboard_blocks(guild_id: ManagedGuildId, name: StarboardName, state: State) -> list[StarboardBlock]:
	"""List the messages blocked from a board: those whose post someone deleted.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		name: The board.
		state: The app state.

	Returns:
		The blocked messages, newest first.

	Raises:
		ApiError: ``not_found`` if the guild has no such board.
	"""
	return await state.starboards.blocks(guild_id, name)


@dashboard.delete("/{name}/blocks/{message_id}", status_code=204)
async def unblock_starboard_message(
	guild_id: ManagedGuildId, name: StarboardName, message_id: Snowflake, state: State
) -> Response:
	"""Let a blocked message be posted on the board again, at its next star.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		name: The board.
		message_id: The original message.
		state: The app state.

	Returns:
		An empty response.

	Raises:
		ApiError: ``not_found`` if the guild has no such board.
	"""
	await state.starboards.unblock(guild_id, name, message_id)
	return Response(status_code=204)
