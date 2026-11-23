"""Log configuration: which server events the bot logs, and where."""

from pydantic import BaseModel

from api.snowflake import Snowflake

__all__ = ("ALL_LOG_MODULES", "LOG_SETTING", "GuildLogConfig", "LogConfig")

LOG_SETTING = "log"
"""The setting key the bot registers and INVALIDATE_SETTING events name."""

ALL_LOG_MODULES = "*"
"""A module name meaning every module, including ones added later. New configurations start with it."""


class LogConfig(BaseModel):
	"""A guild's log configuration."""

	enabled: bool = True
	channel_id: Snowflake | None = None
	"""The default channel, for events without a channel of their own."""
	channels: dict[str, Snowflake] = {}
	"""Event name -> the channel that event is logged in."""
	modules: list[str] = [ALL_LOG_MODULES]
	"""The events that are logged."""
	webhook_url: str | None = None


class GuildLogConfig(LogConfig):
	"""A guild's log configuration, with the guild's ID."""

	guild_id: Snowflake
