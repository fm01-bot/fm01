"""The giveaway store: giveaways, their entries, and entrants' message counts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

import asyncpg
from api import (
	GIVEAWAY_RETENTION_DAYS,
	MAX_ACTIVE_GIVEAWAYS,
	ErrorCode,
	GiveawayCreate,
	GiveawayEntry,
	GiveawayRecord,
	GiveawayStatus,
	MessageCount,
)

from app.db import snowflake
from app.errors import ApiError

__all__ = ("GiveawayStore",)

_COLUMNS = (
	"id, guild_id, channel_id, message_id, host_id, prize, winner_count, required_level, required_role_id, "
	"required_messages, status, created_at, ends_at, ended_at"
)


def _giveaway(row: Mapping[str, Any]) -> GiveawayRecord:
	"""Build a giveaway from a ``giveaways`` row.

	Args:
		row: The row.

	Returns:
		The giveaway.
	"""
	return GiveawayRecord(
		id=row["id"],
		guild_id=int(row["guild_id"]),
		channel_id=int(row["channel_id"]),
		message_id=snowflake(row["message_id"]),
		host_id=int(row["host_id"]),
		prize=row["prize"],
		winner_count=row["winner_count"],
		required_level=row["required_level"],
		required_role_id=snowflake(row["required_role_id"]),
		required_messages=row["required_messages"],
		status=row["status"],
		created_at=row["created_at"],
		ends_at=row["ends_at"],
		ended_at=row["ended_at"],
	)


class GiveawayStore:
	"""Reads and writes giveaways, their entries and entrants' message counts.

	Args:
		db: The database pool.
	"""

	def __init__(self, db: asyncpg.Pool) -> None:
		self._db = db

	async def active(self) -> list[GiveawayRecord]:
		"""List every active giveaway, in every guild.

		Returns:
			The giveaways.
		"""
		rows = await self._db.fetch(f"SELECT {_COLUMNS} FROM giveaways WHERE status = 'active' ORDER BY id")
		return [_giveaway(row) for row in rows]

	async def get(self, giveaway_id: int) -> GiveawayRecord | None:
		"""Get a giveaway.

		Args:
			giveaway_id: The giveaway.

		Returns:
			The giveaway, or ``None`` if there is none.
		"""
		row = await self._db.fetchrow(f"SELECT {_COLUMNS} FROM giveaways WHERE id = $1", giveaway_id)
		return _giveaway(row) if row else None

	async def lookup(
		self, channel_id: int, status: GiveawayStatus, message_id: int | None = None
	) -> GiveawayRecord | None:
		"""Find a channel's giveaway: the one with a message, else the newest.

		Args:
			channel_id: The channel the giveaway runs in.
			status: The status it must have.
			message_id: Its message. ``None`` for the newest giveaway in the channel.

		Returns:
			The giveaway, or ``None`` if none matches.
		"""
		if message_id is not None:
			row = await self._db.fetchrow(
				f"SELECT {_COLUMNS} FROM giveaways WHERE channel_id = $1 AND message_id = $2 AND status = $3",
				channel_id,
				message_id,
				status,
			)
		else:
			row = await self._db.fetchrow(
				f"SELECT {_COLUMNS} FROM giveaways WHERE channel_id = $1 AND status = $2 "
				"ORDER BY created_at DESC, id DESC LIMIT 1",
				channel_id,
				status,
			)
		return _giveaway(row) if row else None

	async def create(self, guild_id: int, giveaway: GiveawayCreate) -> GiveawayRecord:
		"""Start a giveaway. The bot posts its message next.

		Args:
			guild_id: The guild.
			giveaway: The giveaway.

		Returns:
			The stored giveaway.

		Raises:
			ApiError: ``giveaway_limit`` if the guild runs the most active giveaways it may.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			# Serialize starts per guild, so two at once can't both pass the limit.
			await conn.execute(
				"SELECT pg_advisory_xact_lock(hashtextextended('giveaways:' || $1::text, 0))", str(guild_id)
			)
			active = await conn.fetchval(
				"SELECT count(*) FROM giveaways WHERE guild_id = $1 AND status = 'active'", guild_id
			)
			if active >= MAX_ACTIVE_GIVEAWAYS:
				raise ApiError(ErrorCode.GIVEAWAY_LIMIT)
			row = await conn.fetchrow(
				"INSERT INTO giveaways (guild_id, channel_id, host_id, prize, winner_count, required_level, "
				"required_role_id, required_messages, ends_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
				f"RETURNING {_COLUMNS}",
				guild_id,
				giveaway.channel_id,
				giveaway.host_id,
				giveaway.prize,
				giveaway.winner_count,
				giveaway.required_level,
				giveaway.required_role_id,
				giveaway.required_messages,
				giveaway.ends_at,
			)
		assert row is not None
		return _giveaway(row)

	async def set_message(self, giveaway_id: int, message_id: int) -> GiveawayRecord | None:
		"""Record the message the bot posted for a giveaway.

		Args:
			giveaway_id: The giveaway.
			message_id: The message.

		Returns:
			The stored giveaway, or ``None`` if there is none.
		"""
		row = await self._db.fetchrow(
			f"UPDATE giveaways SET message_id = $2 WHERE id = $1 RETURNING {_COLUMNS}", giveaway_id, message_id
		)
		return _giveaway(row) if row else None

	async def delete(self, giveaway_id: int) -> None:
		"""Delete a giveaway with its entries, e.g. when its message couldn't be posted.

		Args:
			giveaway_id: The giveaway.
		"""
		await self._db.execute("DELETE FROM giveaways WHERE id = $1", giveaway_id)

	async def finish(self, giveaway_id: int, status: Literal["ended", "cancelled"]) -> GiveawayRecord | None:
		"""End or cancel an active giveaway.

		Args:
			giveaway_id: The giveaway.
			status: ``ended`` (winners are drawn) or ``cancelled`` (none are).

		Returns:
			The finished giveaway, or ``None`` if it wasn't active.
		"""
		row = await self._db.fetchrow(
			f"UPDATE giveaways SET status = $2, ended_at = now() WHERE id = $1 AND status = 'active' "
			f"RETURNING {_COLUMNS}",
			giveaway_id,
			status,
		)
		return _giveaway(row) if row else None

	async def entry(self, giveaway_id: int, user_id: int) -> GiveawayEntry:
		"""Get a member's entry in a giveaway.

		Args:
			giveaway_id: The giveaway.
			user_id: The member.

		Returns:
			Whether they entered, and their stored message count.
		"""
		row = await self._db.fetchrow(
			"SELECT EXISTS (SELECT 1 FROM giveaway_entries WHERE giveaway_id = $1 AND user_id = $2) AS entered, "
			"(SELECT count FROM giveaway_message_counts WHERE giveaway_id = $1 AND user_id = $2) AS messages",
			giveaway_id,
			user_id,
		)
		assert row is not None
		return GiveawayEntry(entered=row["entered"], messages=row["messages"] or 0)

	async def enter(self, giveaway_id: int, user_id: int) -> bool:
		"""Enter a member into a giveaway.

		Args:
			giveaway_id: The giveaway.
			user_id: The member.

		Returns:
			Whether they were newly entered (``False`` if they had entered already).
		"""
		status = await self._db.execute(
			"INSERT INTO giveaway_entries (giveaway_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
			giveaway_id,
			user_id,
		)
		return status == "INSERT 0 1"

	async def leave(self, giveaway_id: int, user_id: int) -> bool:
		"""Remove a member's entry from a giveaway.

		Args:
			giveaway_id: The giveaway.
			user_id: The member.

		Returns:
			Whether they had entered.
		"""
		status = await self._db.execute(
			"DELETE FROM giveaway_entries WHERE giveaway_id = $1 AND user_id = $2", giveaway_id, user_id
		)
		return status != "DELETE 0"

	async def entry_count(self, giveaway_id: int) -> int:
		"""Count a giveaway's entries.

		Args:
			giveaway_id: The giveaway.

		Returns:
			How many members entered.
		"""
		return await self._db.fetchval("SELECT count(*) FROM giveaway_entries WHERE giveaway_id = $1", giveaway_id)

	async def entrants(self, giveaway_id: int) -> list[int]:
		"""List the members who entered a giveaway and haven't won it.

		Args:
			giveaway_id: The giveaway.

		Returns:
			The members, by when they entered.
		"""
		rows = await self._db.fetch(
			"SELECT user_id FROM giveaway_entries WHERE giveaway_id = $1 AND NOT has_won ORDER BY joined_at",
			giveaway_id,
		)
		return [int(row["user_id"]) for row in rows]

	async def mark_winners(self, giveaway_id: int, user_ids: Sequence[int]) -> None:
		"""Record that members won a giveaway, so a reroll doesn't draw them again.

		Args:
			giveaway_id: The giveaway.
			user_ids: The winners.
		"""
		await self._db.execute(
			"UPDATE giveaway_entries SET has_won = true WHERE giveaway_id = $1 AND user_id = ANY($2::numeric[])",
			giveaway_id,
			list(user_ids),
		)

	async def add_message_counts(self, counts: Sequence[MessageCount]) -> None:
		"""Add messages members sent to their counts. Counts of giveaways that don't exist are dropped.

		Args:
			counts: The messages since the last flush, per giveaway and member.
		"""
		await self._db.execute(
			"INSERT INTO giveaway_message_counts (giveaway_id, user_id, count) "
			"SELECT c.giveaway_id, c.user_id, sum(c.count) "
			"FROM unnest($1::bigint[], $2::numeric[], $3::int[]) AS c (giveaway_id, user_id, count) "
			"JOIN giveaways g ON g.id = c.giveaway_id GROUP BY c.giveaway_id, c.user_id "
			"ON CONFLICT (giveaway_id, user_id) DO UPDATE SET count = giveaway_message_counts.count + EXCLUDED.count",
			[count.giveaway_id for count in counts],
			[count.user_id for count in counts],
			[count.count for count in counts],
		)

	async def message_counts(self, giveaway_id: int) -> list[MessageCount]:
		"""List the message counts of a giveaway's members.

		Args:
			giveaway_id: The giveaway.

		Returns:
			The counts of members who sent messages since it started.
		"""
		rows = await self._db.fetch(
			"SELECT user_id, count FROM giveaway_message_counts WHERE giveaway_id = $1 AND count > 0", giveaway_id
		)
		return [MessageCount(giveaway_id=giveaway_id, user_id=int(row["user_id"]), count=row["count"]) for row in rows]

	async def purge(self) -> None:
		"""Delete the entries and message counts of giveaways that finished more than the retention period ago."""
		for table in ("giveaway_entries", "giveaway_message_counts"):
			await self._db.execute(
				f"DELETE FROM {table} t USING giveaways g WHERE t.giveaway_id = g.id AND g.status <> 'active' "
				"AND g.ended_at < now() - make_interval(days => $1)",
				GIVEAWAY_RETENTION_DAYS,
			)
