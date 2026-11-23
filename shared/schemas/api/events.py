"""Events the API and bot exchange over the Redis event bus."""

from typing import Literal

from pydantic import BaseModel

from api.snowflake import Snowflake

__all__ = ("EVENTS_CHANNEL", "INVALIDATE_SETTING", "InvalidateSetting")

EVENTS_CHANNEL = "fm01:events"
INVALIDATE_SETTING = "INVALIDATE_SETTING"


class InvalidateSetting(BaseModel):
	"""A guild setting changed and bot instances should reload it."""

	type: Literal["INVALIDATE_SETTING"] = "INVALIDATE_SETTING"
	key: str
	"""The setting's key, as registered on the bot's ``GuildSettings`` (e.g. ``"prefix"``)."""
	guild_id: Snowflake
	origin: str | None = None
	"""The bot instance that asked for the change and already updated its own cache. ``None`` for the dashboard."""
