"""AFK: members who said they're away. The bot answers mentions of them and renames them while they're away."""

from pydantic import BaseModel

from api.snowflake import Snowflake

__all__ = ("AfkMember", "AfkStatus", "AfkToggle", "AfkToggled")


class AfkStatus(BaseModel):
	"""Why a member is away, and the nickname they had before."""

	message: str
	previous_nick: str


class AfkMember(AfkStatus):
	"""A member who is away."""

	guild_id: Snowflake
	user_id: Snowflake


class AfkToggle(AfkStatus):
	"""The reason and current nickname to record if the toggle makes the member away."""


class AfkToggled(BaseModel):
	"""The result of toggling a member's AFK."""

	away: bool
	"""Whether the member is now away."""
	previous_nick: str
	"""The nickname to restore when ``away`` is false; the one recorded when it is true."""
