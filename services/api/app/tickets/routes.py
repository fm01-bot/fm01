"""Support ticket and ticket configuration routes for the Internal API."""

from __future__ import annotations

from typing import Annotated

from api import ErrorCode, OpenTicketCount, Snowflake, Ticket, TicketClose, TicketConfig, TicketConfigUpdate, TicketOpen
from fastapi import APIRouter, Query, Response

from app.auth import Origin, State
from app.errors import ApiError

__all__ = ("internal",)

internal = APIRouter(tags=["tickets"])


@internal.get("/guilds/{guild_id}/settings/tickets")
async def internal_ticket_config(guild_id: Snowflake, state: State) -> TicketConfig | None:
	"""Get a guild's ticket configuration. `null` if the guild never configured tickets.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The configuration, or ``None``.
	"""
	return await state.tickets.config(guild_id)


@internal.patch("/guilds/{guild_id}/settings/tickets")
async def internal_update_ticket_config(
	guild_id: Snowflake, body: TicketConfigUpdate, state: State, origin: Origin = None
) -> TicketConfig:
	"""Change a guild's ticket configuration. Fields left out keep their value; `null` clears a channel or role.

	\f
	Args:
		guild_id: The guild.
		body: The changes.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored configuration.
	"""
	return await state.tickets.update_config(guild_id, body, origin)


@internal.post("/guilds/{guild_id}/tickets", status_code=201)
async def internal_open_ticket(guild_id: Snowflake, body: TicketOpen, state: State) -> Ticket:
	"""Record a ticket the bot opened a channel for.

	\f
	Args:
		guild_id: The guild.
		body: The ticket.
		state: The app state.

	Returns:
		The stored ticket.
	"""
	return await state.tickets.open(guild_id, body)


@internal.get("/guilds/{guild_id}/tickets/open-count")
async def internal_open_ticket_count(
	guild_id: Snowflake, user_id: Annotated[Snowflake, Query()], state: State
) -> OpenTicketCount:
	"""Count a member's open tickets.

	\f
	Args:
		guild_id: The guild.
		user_id: The member.
		state: The app state.

	Returns:
		The count.
	"""
	return OpenTicketCount(count=await state.tickets.open_count(guild_id, user_id))


@internal.post("/guilds/{guild_id}/tickets/{ticket_id}/archive")
async def internal_archive_ticket(guild_id: Snowflake, ticket_id: int, state: State) -> Ticket:
	"""Archive a ticket: the opener can still read it but no longer write.

	\f
	Args:
		guild_id: The guild.
		ticket_id: The ticket.
		state: The app state.

	Returns:
		The stored ticket.
	"""
	return await state.tickets.set_archived(guild_id, ticket_id, archived=True)


@internal.post("/guilds/{guild_id}/tickets/{ticket_id}/reopen")
async def internal_reopen_ticket(guild_id: Snowflake, ticket_id: int, state: State) -> Ticket:
	"""Reopen an archived ticket.

	\f
	Args:
		guild_id: The guild.
		ticket_id: The ticket.
		state: The app state.

	Returns:
		The stored ticket.
	"""
	return await state.tickets.set_archived(guild_id, ticket_id, archived=False)


@internal.post("/guilds/{guild_id}/tickets/{ticket_id}/close")
async def internal_close_ticket(guild_id: Snowflake, ticket_id: int, body: TicketClose, state: State) -> Ticket:
	"""Close a ticket.

	\f
	Args:
		guild_id: The guild.
		ticket_id: The ticket.
		body: Who closed it.
		state: The app state.

	Returns:
		The stored ticket.
	"""
	return await state.tickets.close(guild_id, ticket_id, body.closed_by)


@internal.get("/channels/{channel_id}/ticket")
async def internal_channel_ticket(channel_id: Snowflake, state: State) -> Ticket:
	"""Get the open ticket of a channel.

	\f
	Args:
		channel_id: The channel.
		state: The app state.

	Returns:
		The ticket.

	Raises:
		ApiError: ``not_found`` if the channel has no open ticket.
	"""
	ticket = await state.tickets.by_channel(channel_id)
	if ticket is None:
		raise ApiError(ErrorCode.NOT_FOUND, "no open ticket in this channel")
	return ticket


@internal.post("/channels/{channel_id}/deleted", status_code=204)
async def internal_channel_deleted(channel_id: Snowflake, state: State) -> Response:
	"""Close the open tickets of a deleted channel.

	\f
	Args:
		channel_id: The deleted channel.
		state: The app state.

	Returns:
		An empty response.
	"""
	await state.tickets.channel_deleted(channel_id)
	return Response(status_code=204)
