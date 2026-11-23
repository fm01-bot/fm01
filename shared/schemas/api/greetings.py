"""Join and leave messages: what the bot posts when a member joins or leaves a guild."""

from typing import Literal

from pydantic import BaseModel, Field

from api.snowflake import Snowflake

__all__ = ("JOIN_SETTING", "LEAVE_SETTING", "GreetingConfig", "GreetingKind", "GreetingUpdate")

JOIN_SETTING = "join"
"""The setting key of join messages, as the bot registers it and INVALIDATE_SETTING events name it."""
LEAVE_SETTING = "leave"
"""The setting key of leave messages."""

GreetingKind = Literal["join", "leave"]
"""Which greeting: join messages or leave messages."""


class GreetingConfig(BaseModel):
	"""A guild's join or leave message configuration. The bot posts only when it is on with a channel and a message."""

	enabled: bool = True
	channel_id: Snowflake | None = None
	message: str | None = None
	"""The message template, formatted with the member, the guild and the channel."""


class GreetingUpdate(BaseModel):
	"""Changes to a join or leave configuration. ``None`` fields keep their value; a new configuration starts on."""

	enabled: bool | None = None
	channel_id: Snowflake | None = None
	message: str | None = Field(default=None, min_length=1, max_length=2000)
	fallback_channel_id: Snowflake | None = None
	"""Used as the channel only if the configuration has none, e.g. the channel the command ran in."""
