"""Giveaways: prizes drawn among the members who entered, optionally with entry requirements."""

import datetime
from typing import Literal

from pydantic import BaseModel, Field

from api.snowflake import Snowflake

__all__ = (
	"GIVEAWAY_RETENTION_DAYS",
	"MAX_ACTIVE_GIVEAWAYS",
	"GiveawayCreate",
	"GiveawayEntrants",
	"GiveawayEntry",
	"GiveawayEntryChange",
	"GiveawayEntryCount",
	"GiveawayMessage",
	"GiveawayRecord",
	"GiveawayStatus",
	"GiveawayWinners",
	"MessageCount",
)

MAX_ACTIVE_GIVEAWAYS = 25
"""The most active giveaways one guild may run at once."""
GIVEAWAY_RETENTION_DAYS = 30
"""Days entries and message counts are kept after a giveaway ends."""

GiveawayStatus = Literal["active", "ended", "cancelled"]


class GiveawayCreate(BaseModel):
	"""A giveaway to start."""

	channel_id: Snowflake
	host_id: Snowflake
	prize: str = Field(min_length=1, max_length=256)
	winner_count: int = Field(ge=1, le=50)
	required_level: int | None = Field(default=None, ge=1)
	required_role_id: Snowflake | None = None
	required_messages: int | None = Field(default=None, ge=1)
	"""Messages an entrant must send after the giveaway starts to be drawn."""
	ends_at: datetime.datetime


class GiveawayRecord(BaseModel):
	"""A stored giveaway."""

	id: int
	guild_id: Snowflake
	channel_id: Snowflake
	message_id: Snowflake | None = None
	"""The giveaway's message. ``None`` until the bot posted it."""
	host_id: Snowflake
	prize: str
	winner_count: int
	required_level: int | None = None
	required_role_id: Snowflake | None = None
	required_messages: int | None = None
	status: GiveawayStatus = "active"
	created_at: datetime.datetime
	ends_at: datetime.datetime
	ended_at: datetime.datetime | None = None


class GiveawayMessage(BaseModel):
	"""The message the bot posted for a giveaway."""

	message_id: Snowflake


class GiveawayEntry(BaseModel):
	"""Whether a member entered a giveaway, and how many messages they sent since it started."""

	entered: bool
	messages: int = 0
	"""Messages written to the API so far. The bot adds the ones it hasn't flushed yet."""


class MessageCount(BaseModel):
	"""Messages a member sent in a guild with giveaways that count messages, since the last flush."""

	giveaway_id: int
	user_id: Snowflake
	count: int = Field(gt=0)


class GiveawayWinners(BaseModel):
	"""Members drawn as winners. They aren't drawn again in a reroll."""

	user_ids: list[Snowflake] = Field(max_length=100)


class GiveawayEntryChange(BaseModel):
	"""Whether entering or leaving a giveaway changed anything."""

	changed: bool
	"""False if the member had already entered (entering) or hadn't entered (leaving)."""


class GiveawayEntryCount(BaseModel):
	"""How many members entered a giveaway."""

	count: int


class GiveawayEntrants(BaseModel):
	"""The members who entered a giveaway and haven't won it yet."""

	user_ids: list[Snowflake]
