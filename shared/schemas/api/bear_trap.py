"""The bear trap: a honeypot channel where anyone who posts is soft-banned."""

from pydantic import BaseModel

from api.snowflake import Snowflake

__all__ = (
	"BEAR_TRAP_SETTING",
	"BearTrap",
	"BearTrapChannel",
	"BearTrapKicks",
	"BearTrapMessage",
	"BearTrapState",
	"GuildBearTrap",
)

BEAR_TRAP_SETTING = "bear_trap"
"""The setting key the bot registers and INVALIDATE_SETTING events name."""


class BearTrapChannel(BaseModel):
	"""The channel to set the bear trap in. ``None`` turns the trap off."""

	channel_id: Snowflake | None = None


class BearTrap(BearTrapChannel):
	"""A guild's bear trap, as a guild manager sees it."""

	kicks: int = 0
	"""How many members the trap has soft-banned. Kept when the trap is moved or turned off."""


class BearTrapMessage(BaseModel):
	"""The trap message the bot posted. ``None`` fields mean there is no message."""

	message_channel_id: Snowflake | None = None
	message_id: Snowflake | None = None


class BearTrapState(BearTrap, BearTrapMessage):
	"""A guild's bear trap with the bot's own bookkeeping."""


class GuildBearTrap(BearTrapState):
	"""A guild's bear trap state, with the guild's ID."""

	guild_id: Snowflake


class BearTrapKicks(BaseModel):
	"""The bear trap's kick count after a kick."""

	kicks: int
