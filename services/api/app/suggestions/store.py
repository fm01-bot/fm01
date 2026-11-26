"""The suggestion store and the guild's suggestions configuration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import asyncpg
from api import (
	SUGGESTIONS_SETTING,
	CastVote,
	Decide,
	DecisionStatus,
	ErrorCode,
	NewSuggestion,
	Suggestion,
	SuggestionConfig,
	SuggestionDecision,
	SuggestionMessage,
	Vote,
	VoteResult,
)

from app.db import snowflake, upsert
from app.errors import ApiError
from app.events import Announcer

__all__ = ("SuggestionStore",)

_SELECT = """
SELECT s.number, s.author_id, s.content, s.channel_id, s.message_id, s.decision, s.moderator_id, s.reason,
	(SELECT count(*) FROM suggestion_votes v WHERE v.guild_id = s.guild_id AND v.number = s.number AND v.vote = 1) AS up,
	(SELECT count(*) FROM suggestion_votes v WHERE v.guild_id = s.guild_id AND v.number = s.number AND v.vote = -1) AS down
FROM suggestions s
"""
_VOTE_VALUES = {Vote.UP: 1, Vote.DOWN: -1}


def _suggestion(row: Mapping[str, Any]) -> Suggestion:
	"""Build a suggestion from a ``suggestions`` row with its vote counts.

	Args:
		row: The row, with ``up`` and ``down`` counts.

	Returns:
		The suggestion.
	"""
	decision = None
	if row["decision"] is not None:
		decision = SuggestionDecision(
			status=DecisionStatus(row["decision"]), moderator_id=int(row["moderator_id"]), reason=row["reason"]
		)
	return Suggestion(
		number=row["number"],
		author_id=int(row["author_id"]),
		content=row["content"],
		channel_id=snowflake(row["channel_id"]),
		message_id=snowflake(row["message_id"]),
		up=row["up"],
		down=row["down"],
		decision=decision,
	)


class SuggestionStore:
	"""Reads and writes suggestions, their votes and each guild's suggestions configuration.

	Every operation is one transaction. Announces configuration writes.

	Args:
		db: The database pool.
		announcer: Tells bot instances about configuration changes.
	"""

	def __init__(self, db: asyncpg.Pool, announcer: Announcer) -> None:
		self._db = db
		self._announcer = announcer

	async def get_config(self, guild_id: int) -> SuggestionConfig:
		"""Get a guild's suggestions configuration.

		Args:
			guild_id: The guild.

		Returns:
			The configuration. Off if the guild never set one.
		"""
		row = await self._db.fetchrow("SELECT channel_id, threads FROM suggestion_config WHERE guild_id = $1", guild_id)
		if row is None:
			return SuggestionConfig()
		return SuggestionConfig(channel_id=snowflake(row["channel_id"]), threads=row["threads"])

	async def set_config(self, guild_id: int, config: SuggestionConfig, origin: str | None) -> SuggestionConfig:
		"""Set a guild's suggestions configuration. The numbering is kept.

		Args:
			guild_id: The guild.
			config: The configuration. A ``None`` channel turns suggestions off.
			origin: The calling bot instance. ``None`` for the dashboard.

		Returns:
			The stored configuration.
		"""
		await upsert(
			self._db,
			"suggestion_config",
			{"guild_id": guild_id},
			{"channel_id": config.channel_id, "threads": config.threads},
		)
		await self._announcer.setting_changed(SUGGESTIONS_SETTING, guild_id, origin)
		return config

	async def create(self, guild_id: int, new: NewSuggestion) -> Suggestion:
		"""Create a suggestion with the guild's next number.

		The update of the guild's counter locks its row, so concurrent suggestions never share a number.

		Args:
			guild_id: The guild.
			new: The suggestion.

		Returns:
			The suggestion, with no votes and no message yet.

		Raises:
			ApiError: ``suggestions_disabled`` if the guild has no suggestions channel.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			number = await conn.fetchval(
				"UPDATE suggestion_config SET next_number = next_number + 1 "
				"WHERE guild_id = $1 AND channel_id IS NOT NULL RETURNING next_number - 1",
				guild_id,
			)
			if number is None:
				raise ApiError(ErrorCode.SUGGESTIONS_DISABLED, "the guild has no suggestions channel")
			await conn.execute(
				"INSERT INTO suggestions (guild_id, number, author_id, content) VALUES ($1, $2, $3, $4)",
				guild_id,
				number,
				new.author_id,
				new.content,
			)
		return Suggestion(number=number, author_id=new.author_id, content=new.content, up=0, down=0)

	async def get(self, guild_id: int, number: int) -> Suggestion | None:
		"""Get a suggestion.

		Args:
			guild_id: The guild.
			number: The suggestion's number in the guild.

		Returns:
			The suggestion, or ``None`` if there is none.
		"""
		row = await self._db.fetchrow(f"{_SELECT} WHERE s.guild_id = $1 AND s.number = $2", guild_id, number)
		return None if row is None else _suggestion(row)

	async def set_message(self, guild_id: int, number: int, message: SuggestionMessage) -> Suggestion | None:
		"""Record the message the bot posted for a suggestion.

		Args:
			guild_id: The guild.
			number: The suggestion's number in the guild.
			message: The posted message.

		Returns:
			The suggestion, or ``None`` if there is none.
		"""
		updated = await self._db.execute(
			"UPDATE suggestions SET channel_id = $3, message_id = $4 WHERE guild_id = $1 AND number = $2",
			guild_id,
			number,
			message.channel_id,
			message.message_id,
		)
		return await self.get(guild_id, number) if updated == "UPDATE 1" else None

	async def vote(self, guild_id: int, number: int, cast: CastVote) -> VoteResult | None:
		"""Cast a vote: the same vote again takes it back, the opposite one replaces it.

		The suggestion's row is locked, so concurrent votes and decisions queue up.

		Args:
			guild_id: The guild.
			number: The suggestion's number in the guild.
			cast: The voter and their vote.

		Returns:
			The counts and the voter's vote now, or ``None`` if there is no such suggestion.

		Raises:
			ApiError: ``suggestion_closed`` if the suggestion has a decision.
		"""
		wanted = _VOTE_VALUES[cast.vote]
		async with self._db.acquire() as conn, conn.transaction():
			suggestion = await conn.fetchrow(
				"SELECT decision FROM suggestions WHERE guild_id = $1 AND number = $2 FOR UPDATE", guild_id, number
			)
			if suggestion is None:
				return None
			if suggestion["decision"] is not None:
				raise ApiError(ErrorCode.SUGGESTION_CLOSED, "the suggestion has a decision")
			current = await conn.fetchval(
				"SELECT vote FROM suggestion_votes WHERE guild_id = $1 AND number = $2 AND user_id = $3",
				guild_id,
				number,
				cast.user_id,
			)
			if current == wanted:
				await conn.execute(
					"DELETE FROM suggestion_votes WHERE guild_id = $1 AND number = $2 AND user_id = $3",
					guild_id,
					number,
					cast.user_id,
				)
				now = None
			else:
				await upsert(
					conn,
					"suggestion_votes",
					{"guild_id": guild_id, "number": number, "user_id": cast.user_id},
					{"vote": wanted},
				)
				now = cast.vote
			counts = await conn.fetchrow(
				"SELECT count(*) FILTER (WHERE vote = 1) AS up, count(*) FILTER (WHERE vote = -1) AS down "
				"FROM suggestion_votes WHERE guild_id = $1 AND number = $2",
				guild_id,
				number,
			)
		assert counts is not None
		return VoteResult(up=counts["up"], down=counts["down"], vote=now)

	async def decide(self, guild_id: int, number: int, decision: Decide) -> Suggestion | None:
		"""Approve or deny a suggestion. Deciding again overwrites the earlier decision.

		Args:
			guild_id: The guild.
			number: The suggestion's number in the guild.
			decision: The moderator's decision.

		Returns:
			The decided suggestion, or ``None`` if there is none.
		"""
		updated = await self._db.execute(
			"UPDATE suggestions SET decision = $3, moderator_id = $4, reason = $5 WHERE guild_id = $1 AND number = $2",
			guild_id,
			number,
			decision.status.value,
			decision.moderator_id,
			decision.reason,
		)
		return await self.get(guild_id, number) if updated == "UPDATE 1" else None
