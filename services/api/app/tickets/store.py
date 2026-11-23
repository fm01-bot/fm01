"""The support ticket store and the guild's ticket configuration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import asyncpg
from api import TICKET_SETTING, ErrorCode, Ticket, TicketConfig, TicketConfigUpdate, TicketOpen

from app.db import snowflake, upsert
from app.errors import ApiError
from app.events import Announcer

__all__ = ("TicketStore",)

_CONFIG_COLUMNS = {
	"enabled": "is_on",
	"category_id": "category_id",
	"log_channel_id": "log_channel_id",
	"support_role_id": "support_role_id",
	"max_tickets": "max_tickets",
	"dm_transcript": "dm_transcript",
	"topic_min_length": "topic_min_length",
	"topic_max_length": "topic_max_length",
	"description_min_length": "description_min_length",
	"description_max_length": "description_max_length",
}
"""`TicketConfig` field -> ``ticket_config`` column."""
_NULLABLE = frozenset({"category_id", "log_channel_id", "support_role_id"})

_TICKET_COLUMNS = (
	"id, guild_id, channel_id, user_id, title, description, is_archived, is_closed, created_at, closed_at, closed_by"
)


def _config(row: Mapping[str, Any]) -> TicketConfig:
	"""Build a ticket configuration from a ``ticket_config`` row.

	Args:
		row: The row.

	Returns:
		The configuration.
	"""
	values = {field: row[column] for field, column in _CONFIG_COLUMNS.items()}
	for field in ("category_id", "log_channel_id", "support_role_id"):
		values[field] = snowflake(values[field])
	return TicketConfig(**values)


def _ticket(row: Mapping[str, Any]) -> Ticket:
	"""Build a ticket from a ``tickets`` row.

	Args:
		row: The row.

	Returns:
		The ticket.
	"""
	return Ticket(
		id=row["id"],
		guild_id=int(row["guild_id"]),
		channel_id=int(row["channel_id"]),
		user_id=int(row["user_id"]),
		title=row["title"],
		description=row["description"],
		archived=row["is_archived"],
		closed=row["is_closed"],
		created_at=row["created_at"],
		closed_at=row["closed_at"],
		closed_by=snowflake(row["closed_by"]),
	)


class TicketStore:
	"""Reads and writes support tickets and guilds' ticket configurations. Announces configuration writes.

	Args:
		db: The database pool.
		announcer: Tells bot instances about changes.
	"""

	def __init__(self, db: asyncpg.Pool, announcer: Announcer) -> None:
		self._db = db
		self._announcer = announcer

	async def config(self, guild_id: int) -> TicketConfig | None:
		"""Get a guild's ticket configuration.

		Args:
			guild_id: The guild.

		Returns:
			The configuration, or ``None`` if the guild never configured tickets.
		"""
		row = await self._db.fetchrow("SELECT * FROM ticket_config WHERE guild_id = $1", guild_id)
		return _config(row) if row else None

	async def update_config(self, guild_id: int, changes: TicketConfigUpdate, origin: str | None) -> TicketConfig:
		"""Change a guild's ticket configuration, creating it from the defaults if it doesn't exist.

		Args:
			guild_id: The guild.
			changes: The changes. Only the fields set on it are written; ``None`` clears a channel or role.
			origin: The calling bot instance. ``None`` for the dashboard.

		Returns:
			The stored configuration.

		Raises:
			ApiError: ``invalid_request`` if a minimum length would exceed its maximum.
		"""
		fields = {
			_CONFIG_COLUMNS[field]: value
			for field, value in changes.model_dump(exclude_unset=True).items()
			if value is not None or field in _NULLABLE
		}
		async with self._db.acquire() as conn, conn.transaction():
			config = _config(await upsert(conn, "ticket_config", {"guild_id": guild_id}, fields))
			if config.topic_min_length > config.topic_max_length:
				raise ApiError(ErrorCode.INVALID_REQUEST, "the topic's minimum length exceeds its maximum")
			if config.description_min_length > config.description_max_length:
				raise ApiError(ErrorCode.INVALID_REQUEST, "the description's minimum length exceeds its maximum")
		await self._announcer.setting_changed(TICKET_SETTING, guild_id, origin)
		return config

	async def open(self, guild_id: int, ticket: TicketOpen) -> Ticket:
		"""Record a ticket the bot opened a channel for.

		Args:
			guild_id: The guild.
			ticket: The ticket.

		Returns:
			The stored ticket.
		"""
		row = await self._db.fetchrow(
			"INSERT INTO tickets (guild_id, channel_id, user_id, title, description) VALUES ($1, $2, $3, $4, $5) "
			f"RETURNING {_TICKET_COLUMNS}",
			guild_id,
			ticket.channel_id,
			ticket.user_id,
			ticket.title,
			ticket.description,
		)
		assert row is not None
		return _ticket(row)

	async def by_channel(self, channel_id: int) -> Ticket | None:
		"""Get the open ticket of a channel.

		Args:
			channel_id: The ticket's channel.

		Returns:
			The ticket, or ``None`` if the channel has no open ticket.
		"""
		row = await self._db.fetchrow(
			f"SELECT {_TICKET_COLUMNS} FROM tickets WHERE channel_id = $1 AND is_closed = false "
			"ORDER BY id DESC LIMIT 1",
			channel_id,
		)
		return _ticket(row) if row else None

	async def open_count(self, guild_id: int, user_id: int) -> int:
		"""Count a member's open tickets.

		Args:
			guild_id: The guild.
			user_id: The member.

		Returns:
			How many tickets the member has open.
		"""
		return await self._db.fetchval(
			"SELECT count(*) FROM tickets WHERE guild_id = $1 AND user_id = $2 AND is_closed = false",
			guild_id,
			user_id,
		)

	async def set_archived(self, guild_id: int, ticket_id: int, archived: bool) -> Ticket:
		"""Archive a ticket (the opener can read but not write) or reopen it.

		Args:
			guild_id: The guild.
			ticket_id: The ticket.
			archived: Whether it is archived.

		Returns:
			The stored ticket.

		Raises:
			ApiError: ``not_found`` if the guild has no such ticket.
		"""
		row = await self._db.fetchrow(
			f"UPDATE tickets SET is_archived = $3 WHERE id = $1 AND guild_id = $2 RETURNING {_TICKET_COLUMNS}",
			ticket_id,
			guild_id,
			archived,
		)
		if row is None:
			raise ApiError(ErrorCode.NOT_FOUND, "no such ticket")
		return _ticket(row)

	async def close(self, guild_id: int, ticket_id: int, closed_by: int) -> Ticket:
		"""Close a ticket.

		Args:
			guild_id: The guild.
			ticket_id: The ticket.
			closed_by: Who closed it.

		Returns:
			The stored ticket.

		Raises:
			ApiError: ``not_found`` if the guild has no such ticket.
		"""
		row = await self._db.fetchrow(
			"UPDATE tickets SET is_closed = true, is_archived = true, closed_at = now(), closed_by = $3 "
			f"WHERE id = $1 AND guild_id = $2 RETURNING {_TICKET_COLUMNS}",
			ticket_id,
			guild_id,
			closed_by,
		)
		if row is None:
			raise ApiError(ErrorCode.NOT_FOUND, "no such ticket")
		return _ticket(row)

	async def channel_deleted(self, channel_id: int) -> None:
		"""Close the open tickets of a deleted channel.

		Args:
			channel_id: The deleted channel.
		"""
		await self._db.execute(
			"UPDATE tickets SET is_closed = true, is_archived = true, closed_at = now() "
			"WHERE channel_id = $1 AND is_closed = false",
			channel_id,
		)
