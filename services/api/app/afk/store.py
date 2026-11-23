"""The AFK store."""

from __future__ import annotations

import asyncpg
from api import AfkMember, AfkToggle, AfkToggled

__all__ = ("AfkStore",)


class AfkStore:
	"""Reads and writes which members are away.

	Args:
		db: The database pool.
	"""

	def __init__(self, db: asyncpg.Pool) -> None:
		self._db = db

	async def away(self) -> list[AfkMember]:
		"""List every member who is away, in every guild.

		Returns:
			The members, with their reason and previous nickname.
		"""
		rows = await self._db.fetch("SELECT guild_id, user_id, message, previous_nick FROM afk WHERE state = true")
		return [
			AfkMember(
				guild_id=int(row["guild_id"]),
				user_id=int(row["user_id"]),
				message=row["message"],
				previous_nick=row["previous_nick"],
			)
			for row in rows
		]

	async def toggle(self, guild_id: int, user_id: int, status: AfkToggle) -> AfkToggled:
		"""Make a member away, or back if they are away.

		Args:
			guild_id: The guild.
			user_id: The member.
			status: The reason and current nickname, recorded if the member becomes away.

		Returns:
			Whether the member is now away, and the nickname to restore if they're back.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			row = await conn.fetchrow(
				"SELECT id, state, previous_nick FROM afk WHERE user_id = $1 AND guild_id = $2 ORDER BY id LIMIT 1 "
				"FOR UPDATE",
				user_id,
				guild_id,
			)
			if row is None:
				await conn.execute(
					"INSERT INTO afk (user_id, guild_id, message, state, previous_nick) VALUES ($1, $2, $3, true, $4)",
					user_id,
					guild_id,
					status.message,
					status.previous_nick,
				)
				return AfkToggled(away=True, previous_nick=status.previous_nick)
			if row["state"]:
				await conn.execute("UPDATE afk SET state = false WHERE id = $1", row["id"])
				return AfkToggled(away=False, previous_nick=row["previous_nick"])
			await conn.execute(
				"UPDATE afk SET state = true, message = $2, previous_nick = $3 WHERE id = $1",
				row["id"],
				status.message,
				status.previous_nick,
			)
			return AfkToggled(away=True, previous_nick=status.previous_nick)

	async def back(self, guild_id: int, user_id: int) -> None:
		"""Mark a member as back. Does nothing if they weren't away.

		Args:
			guild_id: The guild.
			user_id: The member.
		"""
		await self._db.execute("UPDATE afk SET state = false WHERE user_id = $1 AND guild_id = $2", user_id, guild_id)
