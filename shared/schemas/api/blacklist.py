"""The blacklist: users and guilds the bot's owners barred from commands and the Dashboard API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from api.snowflake import Snowflake

__all__ = ("BLACKLIST_CHANGED", "BlacklistAdd", "BlacklistChanged", "BlacklistEntry", "BlacklistKind")

BLACKLIST_CHANGED = "BLACKLIST_CHANGED"

BlacklistKind = Literal["user", "guild"]
"""What a blacklist entry bars: a user everywhere, or every user in a guild."""


class BlacklistAdd(BaseModel):
	"""Who blacklists the target, and why."""

	created_by: Snowflake
	"""The bot owner who added the entry."""
	reason: str | None = Field(default=None, max_length=500)


class BlacklistEntry(BlacklistAdd):
	"""A blacklisted user or guild."""

	kind: BlacklistKind
	target_id: Snowflake
	created_at: datetime


class BlacklistChanged(BaseModel):
	"""A user or guild was added to or removed from the blacklist, and bot instances should update theirs."""

	type: Literal["BLACKLIST_CHANGED"] = "BLACKLIST_CHANGED"
	kind: BlacklistKind
	target_id: Snowflake
	blacklisted: bool
	"""Whether the target is blacklisted now."""
