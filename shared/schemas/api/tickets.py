"""Support tickets and the guild's ticket configuration."""

import datetime

from pydantic import BaseModel, Field

from api.snowflake import Snowflake

__all__ = (
	"TICKET_SETTING",
	"OpenTicketCount",
	"Ticket",
	"TicketClose",
	"TicketConfig",
	"TicketConfigUpdate",
	"TicketOpen",
)

TICKET_SETTING = "ticket"
"""The setting key the bot registers and INVALIDATE_SETTING events name."""


class TicketConfig(BaseModel):
	"""A guild's ticket configuration."""

	enabled: bool = True
	category_id: Snowflake | None = None
	"""The category ticket channels are created in."""
	log_channel_id: Snowflake | None = None
	support_role_id: Snowflake | None = None
	max_tickets: int = 1
	"""How many open tickets one member may have."""
	dm_transcript: bool = True
	"""Whether the opener gets the transcript by DM when the ticket closes."""
	topic_min_length: int = 3
	topic_max_length: int = 100
	description_min_length: int = 10
	description_max_length: int = 1800


class TicketConfigUpdate(BaseModel):
	"""Changes to a ticket configuration. Fields left out keep their value; ``null`` clears a channel or role."""

	enabled: bool | None = None
	category_id: Snowflake | None = None
	log_channel_id: Snowflake | None = None
	support_role_id: Snowflake | None = None
	max_tickets: int | None = Field(default=None, ge=1, le=100)
	dm_transcript: bool | None = None
	topic_min_length: int | None = Field(default=None, ge=0, le=4000)
	topic_max_length: int | None = Field(default=None, ge=1, le=4000)
	description_min_length: int | None = Field(default=None, ge=0, le=4000)
	description_max_length: int | None = Field(default=None, ge=1, le=4000)


class TicketOpen(BaseModel):
	"""A ticket the bot just opened a channel for."""

	channel_id: Snowflake
	user_id: Snowflake
	title: str
	description: str


class Ticket(TicketOpen):
	"""A stored ticket."""

	id: int
	guild_id: Snowflake
	archived: bool = False
	closed: bool = False
	created_at: datetime.datetime
	closed_at: datetime.datetime | None = None
	closed_by: Snowflake | None = None


class TicketClose(BaseModel):
	"""Who closed a ticket."""

	closed_by: Snowflake


class OpenTicketCount(BaseModel):
	"""How many open tickets a member has."""

	count: int
