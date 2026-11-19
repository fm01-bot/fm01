"""The starboard store: boards, the stars on messages, and the messages' entries on boards."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import asyncpg
from api import (
	MAX_STARBOARDS,
	STARBOARD_SETTING,
	ErrorCode,
	GuildStarboards,
	Starboard,
	StarboardBlock,
	StarboardEntry,
	StarboardPost,
	StarboardUpdate,
	StarChange,
	StarredMessage,
	StarResult,
	StarSeed,
)

from app.errors import ApiError
from app.events import Announcer

__all__ = ("StarboardStore",)

_BOARD_COLUMNS = "name, channel_id, emoji, threshold, enabled, channel_mode, channel_ids, max_age_days"
_ENTRY_COLUMNS = "b.name, e.message_id, e.post_channel_id, e.post_id, e.blocked"
_NOT_NULL = frozenset({"name", "channel_id", "emoji", "threshold", "enabled", "channel_mode", "channel_ids"})
"""Board columns a ``null`` in an update leaves alone, because they can't be empty."""

_CONSTRAINT_ERRORS = {
	"starboards_guild_name_key": (ErrorCode.STARBOARD_NAME_TAKEN, "another board in this guild has that name"),
	"starboards_guild_tier_key": (
		ErrorCode.STARBOARD_TIER_TAKEN,
		"another board in this guild has that emoji and threshold",
	),
}


def _id(value: Any) -> int | None:
	"""Convert a ``numeric`` snowflake column to an ``int``.

	Args:
		value: The column value.

	Returns:
		The snowflake, or ``None`` for ``NULL``.
	"""
	return None if value is None else int(value)


def _board(row: Mapping[str, Any]) -> Starboard:
	"""Build a board from a ``starboards`` row.

	Args:
		row: The row, with `_BOARD_COLUMNS`.

	Returns:
		The board.
	"""
	return Starboard(
		name=row["name"],
		channel_id=int(row["channel_id"]),
		emoji=row["emoji"],
		threshold=row["threshold"],
		enabled=row["enabled"],
		channel_mode=row["channel_mode"],
		channel_ids=[int(channel_id) for channel_id in row["channel_ids"]],
		max_age_days=row["max_age_days"],
	)


def _entry(row: Mapping[str, Any]) -> StarboardEntry:
	"""Build an entry from a ``starboard_entries`` row joined to its board.

	Args:
		row: The row, with `_ENTRY_COLUMNS`.

	Returns:
		The entry.
	"""
	return StarboardEntry(
		board=row["name"],
		message_id=int(row["message_id"]),
		post_channel_id=_id(row["post_channel_id"]),
		post_id=_id(row["post_id"]),
		blocked=row["blocked"],
	)


def _conflict(exc: asyncpg.UniqueViolationError) -> ApiError:
	"""Turn a unique violation on ``starboards`` into the error the caller branches on.

	Args:
		exc: The violation.

	Returns:
		``starboard_name_taken`` or ``starboard_tier_taken``.
	"""
	code, message = _CONSTRAINT_ERRORS.get(
		getattr(exc, "constraint_name", None) or "", _CONSTRAINT_ERRORS["starboards_guild_name_key"]
	)
	return ApiError(code, message)


class StarboardStore:
	"""Reads and writes starboards. Announces every board write; star and entry writes are not settings.

	Args:
		db: The database pool.
		announcer: Tells bot instances about board changes.
	"""

	def __init__(self, db: asyncpg.Pool, announcer: Announcer) -> None:
		self._db = db
		self._announcer = announcer

	async def boards(self, guild_id: int) -> list[Starboard]:
		"""List a guild's boards.

		Args:
			guild_id: The guild.

		Returns:
			The boards, by name.
		"""
		rows = await self._db.fetch(
			f"SELECT {_BOARD_COLUMNS} FROM starboards WHERE guild_id = $1 ORDER BY name", guild_id
		)
		return [_board(row) for row in rows]

	async def all(self) -> list[GuildStarboards]:
		"""List the boards of every guild that has any.

		Returns:
			Each guild's boards, by name.
		"""
		rows = await self._db.fetch(f"SELECT guild_id, {_BOARD_COLUMNS} FROM starboards ORDER BY guild_id, name")
		guilds: dict[int, list[Starboard]] = {}
		for row in rows:
			guilds.setdefault(int(row["guild_id"]), []).append(_board(row))
		return [GuildStarboards(guild_id=guild_id, boards=boards) for guild_id, boards in guilds.items()]

	async def create(self, guild_id: int, board: Starboard, origin: str | None) -> Starboard:
		"""Add a board to a guild.

		Args:
			guild_id: The guild.
			board: The board.
			origin: The calling bot instance. ``None`` for the dashboard.

		Returns:
			The stored board.

		Raises:
			ApiError: ``starboard_limit`` if the guild has `MAX_STARBOARDS` boards, ``starboard_name_taken`` or
				``starboard_tier_taken`` if another board has its name, or its emoji and threshold.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			# Serializes creates per guild, so two at once can't both pass the limit.
			await conn.execute(
				"SELECT pg_advisory_xact_lock(hashtextextended('starboards:' || $1::numeric::text, 0))", guild_id
			)
			if await conn.fetchval("SELECT count(*) FROM starboards WHERE guild_id = $1", guild_id) >= MAX_STARBOARDS:
				raise ApiError(ErrorCode.STARBOARD_LIMIT, f"a guild can have at most {MAX_STARBOARDS} boards")
			try:
				row = await conn.fetchrow(
					f"INSERT INTO starboards (guild_id, {_BOARD_COLUMNS}) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
					f"RETURNING {_BOARD_COLUMNS}",
					guild_id,
					board.name,
					board.channel_id,
					board.emoji,
					board.threshold,
					board.enabled,
					board.channel_mode,
					board.channel_ids,
					board.max_age_days,
				)
			except asyncpg.UniqueViolationError as exc:
				raise _conflict(exc) from exc
		await self._announcer.setting_changed(STARBOARD_SETTING, guild_id, origin)
		return _board(row)

	async def update(self, guild_id: int, name: str, changes: StarboardUpdate, origin: str | None) -> Starboard:
		"""Change a board. If its emoji changes, stars with the old emoji that no board uses any more are removed.

		Its posts and entries stay as they are; they follow the new settings at their next star change.

		Args:
			guild_id: The guild.
			name: The board's current name.
			changes: The fields to change.
			origin: The calling bot instance. ``None`` for the dashboard.

		Returns:
			The stored board.

		Raises:
			ApiError: ``not_found`` if the guild has no such board, ``starboard_name_taken`` or
				``starboard_tier_taken`` if the change clashes with another board.
		"""
		fields = {
			key: value
			for key, value in changes.model_dump(exclude_unset=True).items()
			if value is not None or key not in _NOT_NULL
		}
		if not fields:
			board = await self._db.fetchrow(
				f"SELECT {_BOARD_COLUMNS} FROM starboards WHERE guild_id = $1 AND name = $2", guild_id, name
			)
			if board is None:
				raise ApiError(ErrorCode.NOT_FOUND, f"no board named {name!r}")
			return _board(board)

		assignments = ", ".join(f"{key} = ${index}" for index, key in enumerate(fields, start=3))
		async with self._db.acquire() as conn, conn.transaction():
			try:
				row = await conn.fetchrow(
					f"UPDATE starboards SET {assignments} WHERE guild_id = $1 AND name = $2 RETURNING {_BOARD_COLUMNS}",
					guild_id,
					name,
					*fields.values(),
				)
			except asyncpg.UniqueViolationError as exc:
				raise _conflict(exc) from exc
			if row is None:
				raise ApiError(ErrorCode.NOT_FOUND, f"no board named {name!r}")
			if "emoji" in fields:
				await self._drop_unused_stars(conn, guild_id)
		await self._announcer.setting_changed(STARBOARD_SETTING, guild_id, origin)
		return _board(row)

	async def delete(self, guild_id: int, name: str, origin: str | None) -> None:
		"""Remove a board with its entries and blocks. Its posts stay in the channel.

		Stars with its emoji are removed too, unless another board uses the emoji.

		Args:
			guild_id: The guild.
			name: The board.
			origin: The calling bot instance. ``None`` for the dashboard.

		Raises:
			ApiError: ``not_found`` if the guild has no such board.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			deleted = await conn.fetchval(
				"DELETE FROM starboards WHERE guild_id = $1 AND name = $2 RETURNING id", guild_id, name
			)
			if deleted is None:
				raise ApiError(ErrorCode.NOT_FOUND, f"no board named {name!r}")
			await self._drop_unused_stars(conn, guild_id)
		await self._announcer.setting_changed(STARBOARD_SETTING, guild_id, origin)

	@staticmethod
	async def _drop_unused_stars(conn: asyncpg.Connection, guild_id: int) -> None:
		"""Remove a guild's starred messages (with their stars) whose emoji no board uses.

		Args:
			conn: The connection, inside the transaction that changed the boards.
			guild_id: The guild.
		"""
		await conn.execute(
			"DELETE FROM starboard_messages m WHERE m.guild_id = $1 AND NOT EXISTS "
			"(SELECT 1 FROM starboards b WHERE b.guild_id = m.guild_id AND b.emoji = m.emoji)",
			guild_id,
		)

	async def star(self, guild_id: int, change: StarChange) -> StarResult:
		"""Add or remove one member's star on a message, or on one of its posts.

		Args:
			guild_id: The guild.
			change: The star.

		Returns:
			The message's stars and entries after the change. No message if the API has never seen it (the bot then
			seeds it), or if ``change.message_id`` is in a board channel but isn't a post with this emoji.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			message_id = await self._original(conn, guild_id, change.message_id, change.emoji)
			if message_id is None:
				return StarResult()
			if change.starred:
				await conn.execute(
					"INSERT INTO starboard_stars (guild_id, message_id, emoji, user_id) VALUES ($1, $2, $3, $4) "
					"ON CONFLICT DO NOTHING",
					guild_id,
					message_id,
					change.emoji,
					change.user_id,
				)
			else:
				await conn.execute(
					"DELETE FROM starboard_stars WHERE guild_id = $1 AND message_id = $2 AND emoji = $3 AND user_id = $4",
					guild_id,
					message_id,
					change.emoji,
					change.user_id,
				)
			return StarResult(message=await self._message(conn, guild_id, message_id, change.emoji))

	@staticmethod
	async def _original(conn: asyncpg.Connection, guild_id: int, message_id: int, emoji: str) -> int | None:
		"""Find the seeded original a star change is about.

		Args:
			conn: The connection.
			guild_id: The guild.
			message_id: The original, or a post of it on a board with ``emoji``.
			emoji: The emoji.

		Returns:
			The original's ID, or ``None`` if it was never seeded.
		"""
		original = await conn.fetchval(
			"SELECT e.message_id FROM starboard_entries e JOIN starboards b ON b.id = e.board_id "
			"WHERE b.guild_id = $1 AND b.emoji = $3 AND e.post_id = $2 LIMIT 1",
			guild_id,
			message_id,
			emoji,
		)
		candidate = message_id if original is None else original
		seeded = await conn.fetchval(
			"SELECT message_id FROM starboard_messages WHERE guild_id = $1 AND message_id = $2 AND emoji = $3",
			guild_id,
			candidate,
			emoji,
		)
		return _id(seeded)

	async def seed(self, guild_id: int, seed: StarSeed) -> StarredMessage:
		"""Record everyone who starred a message with an emoji, replacing the stars recorded so far.

		Args:
			guild_id: The guild.
			seed: The message and its starrers, read from Discord.

		Returns:
			The message's stars and entries.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			await conn.execute(
				"INSERT INTO starboard_messages (guild_id, message_id, emoji, channel_id, author_id) "
				"VALUES ($1, $2, $3, $4, $5) ON CONFLICT (guild_id, message_id, emoji) DO UPDATE "
				"SET channel_id = EXCLUDED.channel_id, author_id = EXCLUDED.author_id",
				guild_id,
				seed.message_id,
				seed.emoji,
				seed.channel_id,
				seed.author_id,
			)
			await conn.execute(
				"DELETE FROM starboard_stars WHERE guild_id = $1 AND message_id = $2 AND emoji = $3",
				guild_id,
				seed.message_id,
				seed.emoji,
			)
			await conn.execute(
				"INSERT INTO starboard_stars (guild_id, message_id, emoji, user_id) "
				"SELECT $1, $2, $3, user_id FROM unnest($4::numeric[]) AS user_id ON CONFLICT DO NOTHING",
				guild_id,
				seed.message_id,
				seed.emoji,
				seed.user_ids,
			)
			return await self._message(conn, guild_id, seed.message_id, seed.emoji)

	@staticmethod
	async def _message(conn: asyncpg.Connection, guild_id: int, message_id: int, emoji: str) -> StarredMessage:
		"""Read a seeded message's star count and its entries on the boards that use the emoji.

		Args:
			conn: The connection.
			guild_id: The guild.
			message_id: The original.
			emoji: The emoji.

		Returns:
			The message.
		"""
		row = await conn.fetchrow(
			"SELECT m.channel_id, m.author_id, "
			"(SELECT count(*) FROM starboard_stars s WHERE s.guild_id = m.guild_id AND s.message_id = m.message_id "
			"AND s.emoji = m.emoji AND s.user_id <> m.author_id) AS count "
			"FROM starboard_messages m WHERE m.guild_id = $1 AND m.message_id = $2 AND m.emoji = $3",
			guild_id,
			message_id,
			emoji,
		)
		entries = await conn.fetch(
			f"SELECT {_ENTRY_COLUMNS} FROM starboard_entries e JOIN starboards b ON b.id = e.board_id "
			"WHERE b.guild_id = $1 AND b.emoji = $3 AND e.message_id = $2 ORDER BY b.name",
			guild_id,
			message_id,
			emoji,
		)
		return StarredMessage(
			message_id=message_id,
			channel_id=int(row["channel_id"]),
			author_id=int(row["author_id"]),
			emoji=emoji,
			count=row["count"],
			entries=[_entry(entry) for entry in entries],
		)

	async def set_post(self, guild_id: int, post: StarboardPost) -> StarboardEntry:
		"""Record the post the bot made for a message on a board, or that it removed the post.

		Args:
			guild_id: The guild.
			post: The post.

		Returns:
			The message's entry on the board.

		Raises:
			ApiError: ``not_found`` if the guild has no such board.
		"""
		row = await self._db.fetchrow(
			"WITH e AS (INSERT INTO starboard_entries (board_id, message_id, post_channel_id, post_id) "
			"SELECT id, $3, $4, $5 FROM starboards WHERE guild_id = $1 AND name = $2 "
			"ON CONFLICT (board_id, message_id) DO UPDATE "
			"SET post_channel_id = EXCLUDED.post_channel_id, post_id = EXCLUDED.post_id "
			"RETURNING board_id, message_id, post_channel_id, post_id, blocked) "
			f"SELECT {_ENTRY_COLUMNS} FROM e JOIN starboards b ON b.id = e.board_id",
			guild_id,
			post.board,
			post.message_id,
			post.post_channel_id,
			post.post_id,
		)
		if row is None:
			raise ApiError(ErrorCode.NOT_FOUND, f"no board named {post.board!r}")
		return _entry(row)

	async def posts_deleted(self, guild_id: int, post_ids: list[int]) -> list[StarboardEntry]:
		"""Block the messages whose posts someone other than the bot deleted, each on its own board.

		The bot records its own deletions with `set_post` first, so they are no longer posts by the time they're gone.

		Args:
			guild_id: The guild.
			post_ids: The deleted messages. Ones that aren't posts are ignored.

		Returns:
			The entries now blocked.
		"""
		rows = await self._db.fetch(
			"WITH e AS (UPDATE starboard_entries e SET blocked = true, post_channel_id = NULL, post_id = NULL "
			"FROM starboards b WHERE b.id = e.board_id AND b.guild_id = $1 AND e.post_id = ANY($2::numeric[]) "
			"RETURNING e.board_id, e.message_id, e.post_channel_id, e.post_id, e.blocked) "
			f"SELECT {_ENTRY_COLUMNS} FROM e JOIN starboards b ON b.id = e.board_id",
			guild_id,
			post_ids,
		)
		return [_entry(row) for row in rows]

	async def messages_deleted(self, guild_id: int, message_ids: list[int]) -> list[StarboardEntry]:
		"""Forget deleted originals: their stars and their entries, blocks included.

		Args:
			guild_id: The guild.
			message_ids: The deleted messages. Ones the API doesn't know are ignored.

		Returns:
			The entries that had a post, which the bot then deletes.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			rows = await conn.fetch(
				"WITH e AS (DELETE FROM starboard_entries e USING starboards b "
				"WHERE b.id = e.board_id AND b.guild_id = $1 AND e.message_id = ANY($2::numeric[]) "
				"RETURNING e.board_id, e.message_id, e.post_channel_id, e.post_id, e.blocked) "
				f"SELECT {_ENTRY_COLUMNS} FROM e JOIN starboards b ON b.id = e.board_id WHERE e.post_id IS NOT NULL",
				guild_id,
				message_ids,
			)
			await conn.execute(
				"DELETE FROM starboard_messages WHERE guild_id = $1 AND message_id = ANY($2::numeric[])",
				guild_id,
				message_ids,
			)
		return [_entry(row) for row in rows]

	async def clear(self, guild_id: int, message_id: int, emoji: str | None) -> list[StarboardEntry]:
		"""Forget a message's stars after its reactions were cleared, and take down its posts. Blocks stay.

		The next star seeds the message again.

		Args:
			guild_id: The guild.
			message_id: The original.
			emoji: The emoji whose reactions were cleared. ``None`` for all of them.

		Returns:
			The entries that had a post, as they were, which the bot then deletes.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			await conn.execute(
				"DELETE FROM starboard_messages WHERE guild_id = $1 AND message_id = $2 "
				"AND ($3::text IS NULL OR emoji = $3)",
				guild_id,
				message_id,
				emoji,
			)
			rows = await conn.fetch(
				f"SELECT {_ENTRY_COLUMNS} FROM starboard_entries e JOIN starboards b ON b.id = e.board_id "
				"WHERE b.guild_id = $1 AND e.message_id = $2 AND ($3::text IS NULL OR b.emoji = $3) "
				"AND e.post_id IS NOT NULL FOR UPDATE OF e",
				guild_id,
				message_id,
				emoji,
			)
			await conn.execute(
				"UPDATE starboard_entries e SET post_channel_id = NULL, post_id = NULL FROM starboards b "
				"WHERE b.id = e.board_id AND b.guild_id = $1 AND e.message_id = $2 "
				"AND ($3::text IS NULL OR b.emoji = $3)",
				guild_id,
				message_id,
				emoji,
			)
		return [_entry(row) for row in rows]

	async def blocks(self, guild_id: int, name: str) -> list[StarboardBlock]:
		"""List the messages blocked from a board.

		Args:
			guild_id: The guild.
			name: The board.

		Returns:
			The blocked messages, newest first.

		Raises:
			ApiError: ``not_found`` if the guild has no such board.
		"""
		async with self._db.acquire() as conn:
			board_id = await self._board_id(conn, guild_id, name)
			rows = await conn.fetch(
				"SELECT message_id FROM starboard_entries WHERE board_id = $1 AND blocked ORDER BY message_id DESC",
				board_id,
			)
		return [StarboardBlock(message_id=int(row["message_id"])) for row in rows]

	async def unblock(self, guild_id: int, name: str, message_id: int) -> None:
		"""Let a blocked message be posted on a board again, at its next star change. Unblocking twice is fine.

		Args:
			guild_id: The guild.
			name: The board.
			message_id: The original.

		Raises:
			ApiError: ``not_found`` if the guild has no such board.
		"""
		async with self._db.acquire() as conn:
			board_id = await self._board_id(conn, guild_id, name)
			await conn.execute(
				"UPDATE starboard_entries SET blocked = false WHERE board_id = $1 AND message_id = $2",
				board_id,
				message_id,
			)

	@staticmethod
	async def _board_id(conn: asyncpg.Connection, guild_id: int, name: str) -> int:
		"""Look up a board's row ID.

		Args:
			conn: The connection.
			guild_id: The guild.
			name: The board.

		Returns:
			The ID.

		Raises:
			ApiError: ``not_found`` if the guild has no such board.
		"""
		board_id = await conn.fetchval("SELECT id FROM starboards WHERE guild_id = $1 AND name = $2", guild_id, name)
		if board_id is None:
			raise ApiError(ErrorCode.NOT_FOUND, f"no board named {name!r}")
		return board_id
