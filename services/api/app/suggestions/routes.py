"""Suggestion routes for the Internal API, and the suggestions setting for the Dashboard API."""

from __future__ import annotations

from api import (
	CastVote,
	Decide,
	ErrorCode,
	NewSuggestion,
	Snowflake,
	Suggestion,
	SuggestionConfig,
	SuggestionMessage,
	VoteResult,
)
from fastapi import APIRouter

from app.auth import ManagedGuildId, Origin, State
from app.errors import ApiError

__all__ = ("dashboard", "internal")

GUILD_TEXT = 0
"""Discord's channel type for a plain text channel, the only kind suggestions can be posted in."""

internal = APIRouter(tags=["suggestions"])
dashboard = APIRouter(prefix="/guilds/{guild_id}/settings/suggestions", tags=["suggestions"])


def _found[T](value: T | None) -> T:
	"""Return a looked-up result, or fail with ``not_found``.

	Args:
		value: The lookup's result.

	Returns:
		The value.

	Raises:
		ApiError: ``not_found`` if the value is ``None``.
	"""
	if value is None:
		raise ApiError(ErrorCode.NOT_FOUND, "no such suggestion")
	return value


@internal.get("/guilds/{guild_id}/settings/suggestions")
async def internal_suggestion_config(guild_id: Snowflake, state: State) -> SuggestionConfig:
	"""Get a guild's suggestions setting.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The setting. Off if the guild never set it.
	"""
	return await state.suggestions.get_config(guild_id)


@internal.put("/guilds/{guild_id}/settings/suggestions")
async def internal_set_suggestion_config(
	guild_id: Snowflake, body: SuggestionConfig, state: State, origin: Origin = None
) -> SuggestionConfig:
	"""Set a guild's suggestions setting. A `null` channel turns suggestions off.

	\f
	Args:
		guild_id: The guild.
		body: The setting.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored setting.
	"""
	return await state.suggestions.set_config(guild_id, body, origin)


@internal.post("/guilds/{guild_id}/suggestions")
async def create_suggestion(guild_id: Snowflake, body: NewSuggestion, state: State) -> Suggestion:
	"""Create a suggestion with the guild's next number.

	\f
	Args:
		guild_id: The guild.
		body: The suggestion.
		state: The app state.

	Returns:
		The suggestion. The bot posts it and records the message.

	Raises:
		ApiError: ``suggestions_disabled`` if the guild has no suggestions channel.
	"""
	return await state.suggestions.create(guild_id, body)


@internal.get("/guilds/{guild_id}/suggestions/{number}")
async def get_suggestion(guild_id: Snowflake, number: int, state: State) -> Suggestion:
	"""Get a suggestion.

	\f
	Args:
		guild_id: The guild.
		number: The suggestion's number in the guild.
		state: The app state.

	Returns:
		The suggestion with its vote counts.

	Raises:
		ApiError: ``not_found`` if there is no such suggestion.
	"""
	return _found(await state.suggestions.get(guild_id, number))


@internal.put("/guilds/{guild_id}/suggestions/{number}/message")
async def set_suggestion_message(guild_id: Snowflake, number: int, body: SuggestionMessage, state: State) -> Suggestion:
	"""Record the message the bot posted for a suggestion.

	\f
	Args:
		guild_id: The guild.
		number: The suggestion's number in the guild.
		body: The message.
		state: The app state.

	Returns:
		The suggestion.

	Raises:
		ApiError: ``not_found`` if there is no such suggestion.
	"""
	return _found(await state.suggestions.set_message(guild_id, number, body))


@internal.post("/guilds/{guild_id}/suggestions/{number}/votes")
async def vote_on_suggestion(guild_id: Snowflake, number: int, body: CastVote, state: State) -> VoteResult:
	"""Cast a vote. The same vote again takes it back, the opposite vote replaces it.

	\f
	Args:
		guild_id: The guild.
		number: The suggestion's number in the guild.
		body: The voter and their vote.
		state: The app state.

	Returns:
		The counts and the voter's vote after the call.

	Raises:
		ApiError: ``not_found`` if there is no such suggestion, ``suggestion_closed`` if it has a decision.
	"""
	return _found(await state.suggestions.vote(guild_id, number, body))


@internal.post("/guilds/{guild_id}/suggestions/{number}/decision")
async def decide_suggestion(guild_id: Snowflake, number: int, body: Decide, state: State) -> Suggestion:
	"""Approve or deny a suggestion. Deciding again overwrites the earlier decision.

	\f
	Args:
		guild_id: The guild.
		number: The suggestion's number in the guild.
		body: The moderator's decision.
		state: The app state.

	Returns:
		The decided suggestion.

	Raises:
		ApiError: ``not_found`` if there is no such suggestion.
	"""
	return _found(await state.suggestions.decide(guild_id, number, body))


@dashboard.get("")
async def suggestion_config(guild_id: ManagedGuildId, state: State) -> SuggestionConfig:
	"""Get a guild's suggestions setting.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		state: The app state.

	Returns:
		The setting. Off if the guild never set it.
	"""
	return await state.suggestions.get_config(guild_id)


@dashboard.put("")
async def set_suggestion_config(guild_id: ManagedGuildId, body: SuggestionConfig, state: State) -> SuggestionConfig:
	"""Set a guild's suggestions setting. A `null` channel turns suggestions off.

	\f
	Args:
		guild_id: The guild. The caller must manage it.
		body: The setting. The channel must be a text channel in the guild.
		state: The app state.

	Returns:
		The stored setting.

	Raises:
		ApiError: ``invalid_channel`` if the channel isn't a text channel in the guild.
	"""
	if body.channel_id is not None:
		channel = await state.discord.guild_channel(guild_id, body.channel_id)
		if channel is None or channel.get("type") != GUILD_TEXT:
			raise ApiError(ErrorCode.INVALID_CHANNEL, "the channel is not a text channel in this guild")
	return await state.suggestions.set_config(guild_id, body, origin=None)
