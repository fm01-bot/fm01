"""The bear trap store."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import asyncpg
from api import BEAR_TRAP_SETTING, BearTrapKicks, BearTrapMessage, BearTrapState, GuildBearTrap

from app.db import snowflake
from app.events import Announcer

__all__ = ("BearTrapStore",)

_COLUMNS = "channel_id, message_channel_id, message_id, kicks"


def _state(row: Mapping[str, Any] | None) -> BearTrapState:
	"""Build a bear trap state from a ``bear_trap`` row.

	Args:
		row: The row. ``None`` for a guild that never set a trap.

	Returns:
		The state.
	"""
	if row is None:
		return BearTrapState()
	return BearTrapState(
		channel_id=snowflake(row["channel_id"]),
		message_channel_id=snowflake(row["message_channel_id"]),
		message_id=snowflake(row["message_id"]),
		kicks=row["kicks"],
	)


class BearTrapStore:
	"""Reads and writes guild bear traps. Announces every write.

	Args:
		db: The database pool.
		announcer: Tells bot instances about changes.
	"""

	def __init__(self, db: asyncpg.Pool, announcer: Announcer) -> None:
		self._db = db
		self._announcer = announcer

	async def get(self, guild_id: int) -> BearTrapState:
		"""Get a guild's bear trap.

		Args:
			guild_id: The guild.

		Returns:
			The trap. Off with no kicks if the guild never set one.
		"""
		return _state(await self._db.fetchrow(f"SELECT {_COLUMNS} FROM bear_trap WHERE guild_id = $1", guild_id))

	async def all(self) -> list[GuildBearTrap]:
		"""List every guild whose trap is on or still has a message posted.

		Returns:
			The traps the bot has to watch or clean up.
		"""
		rows = await self._db.fetch(
			f"SELECT guild_id, {_COLUMNS} FROM bear_trap WHERE channel_id IS NOT NULL OR message_id IS NOT NULL"
		)
		return [GuildBearTrap(guild_id=int(row["guild_id"]), **_state(row).model_dump()) for row in rows]

	async def set_channel(self, guild_id: int, channel_id: int | None, origin: str | None) -> BearTrapState:
		"""Set the trap's channel. The bot then moves, posts or deletes the trap message.

		Args:
			guild_id: The guild.
			channel_id: The channel. ``None`` turns the trap off.
			origin: The calling bot instance. ``None`` for the dashboard.

		Returns:
			The stored trap.
		"""
		row = await self._db.fetchrow(
			"INSERT INTO bear_trap (guild_id, channel_id) VALUES ($1, $2) "
			f"ON CONFLICT (guild_id) DO UPDATE SET channel_id = EXCLUDED.channel_id RETURNING {_COLUMNS}",
			guild_id,
			channel_id,
		)
		await self._announcer.setting_changed(BEAR_TRAP_SETTING, guild_id, origin)
		return _state(row)

	async def set_message(self, guild_id: int, message: BearTrapMessage, origin: str | None) -> BearTrapState:
		"""Record the trap message the bot posted, or that it removed it.

		Args:
			guild_id: The guild.
			message: The posted message. ``None`` fields mean there is none.
			origin: The calling bot instance.

		Returns:
			The stored trap.
		"""
		row = await self._db.fetchrow(
			"INSERT INTO bear_trap (guild_id, message_channel_id, message_id) VALUES ($1, $2, $3) "
			"ON CONFLICT (guild_id) DO UPDATE "
			"SET message_channel_id = EXCLUDED.message_channel_id, message_id = EXCLUDED.message_id "
			f"RETURNING {_COLUMNS}",
			guild_id,
			message.message_channel_id,
			message.message_id,
		)
		await self._announcer.setting_changed(BEAR_TRAP_SETTING, guild_id, origin)
		return _state(row)

	async def add_kick(self, guild_id: int, origin: str | None) -> BearTrapKicks:
		"""Count one more member the trap soft-banned.

		Args:
			guild_id: The guild.
			origin: The calling bot instance.

		Returns:
			The new count.
		"""
		kicks = await self._db.fetchval(
			"INSERT INTO bear_trap (guild_id, kicks) VALUES ($1, 1) "
			"ON CONFLICT (guild_id) DO UPDATE SET kicks = bear_trap.kicks + 1 RETURNING kicks",
			guild_id,
		)
		await self._announcer.setting_changed(BEAR_TRAP_SETTING, guild_id, origin)
		return BearTrapKicks(kicks=kicks)
