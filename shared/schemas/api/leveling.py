"""Leveling: members' XP and levels, the guild's leveling configuration, role rewards and XP overrides.

The level math lives here so the API (which stores levels) and the bot (which draws rank cards) agree on it.
"""

from typing import Literal, NamedTuple

from pydantic import BaseModel, Field

from api.snowflake import Snowflake

__all__ = (
	"LEVEL_CONFIG_SETTING",
	"LEVEL_OVERRIDES_SETTING",
	"LEVEL_REWARDS_SETTING",
	"LevelConfig",
	"LevelConfigUpdate",
	"LevelOverride",
	"LevelOverrideUpdate",
	"LevelOverrides",
	"LevelProgress",
	"LevelReward",
	"LevelupMode",
	"Leaderboard",
	"MemberLevel",
	"UserIds",
	"XpAward",
	"XpResult",
	"level_from_total_xp",
	"total_xp_for_level",
	"xp_to_next_level",
)

LEVEL_CONFIG_SETTING = "level.config"
"""The setting keys the bot registers and INVALIDATE_SETTING events name."""
LEVEL_REWARDS_SETTING = "level.rewards"
LEVEL_OVERRIDES_SETTING = "level.overrides"

LevelupMode = Literal["disabled", "current", "channel"]
"""Where level-up messages go: nowhere, the channel the member wrote in, or the configured channel."""


class LevelProgress(NamedTuple):
	"""Progress towards the next level.

	Attributes:
		level: The current level.
		current_xp: XP earned towards the next level.
		needed_xp: XP needed to go from the current level to the next.
		remaining_xp: XP still missing to reach the next level.
	"""

	level: int
	current_xp: int
	needed_xp: int
	remaining_xp: int


def xp_to_next_level(level: int) -> int:
	"""Calculate the XP needed to go from ``level`` to ``level + 1``: ``5 * level² + 50 * level + 100``.

	Args:
		level: The current level. Negative levels count as 0.

	Returns:
		The XP needed.
	"""
	level = max(level, 0)
	return 5 * (level**2) + (50 * level) + 100


def total_xp_for_level(level: int) -> int:
	"""Calculate the total XP needed to reach ``level`` from 0.

	Args:
		level: The target level.

	Returns:
		The sum of `xp_to_next_level` for every level below ``level``.
	"""
	if level <= 0:
		return 0
	n = level
	sum_sq = (n - 1) * n * (2 * n - 1) // 6
	sum_i = (n - 1) * n // 2
	return 5 * sum_sq + 50 * sum_i + 100 * n


def level_from_total_xp(total_xp: int) -> LevelProgress:
	"""Derive a member's level and progress from their total XP.

	Args:
		total_xp: The member's total XP.

	Returns:
		The level and the progress towards the next one.
	"""
	if total_xp <= 0:
		needed = xp_to_next_level(0)
		return LevelProgress(level=0, current_xp=0, needed_xp=needed, remaining_xp=needed)

	# The highest level whose total is at most total_xp.
	low, high, lvl = 0, 1_000_000, 0
	while low <= high:
		mid = (low + high) // 2
		if total_xp_for_level(mid) <= total_xp:
			lvl = mid
			low = mid + 1
		else:
			high = mid - 1

	current_xp = total_xp - total_xp_for_level(lvl)
	needed = xp_to_next_level(lvl)
	return LevelProgress(level=lvl, current_xp=current_xp, needed_xp=needed, remaining_xp=max(0, needed - current_xp))


class LevelConfig(BaseModel):
	"""A guild's leveling configuration. The defaults apply to guilds that never configured leveling."""

	enabled: bool = True
	multiplier: float = 1.0
	"""Multiplies all XP awarded in the guild."""
	min_xp: int = 15
	"""The least base XP one message awards."""
	max_xp: int = 25
	"""The most base XP one message awards."""
	cooldown: int = 60
	"""Seconds a member waits between messages that award XP."""
	message_mode: LevelupMode = "current"
	message_channel_id: Snowflake | None = None
	"""The channel level-up messages go to in ``channel`` mode."""
	levelup_message: str | None = None
	"""A custom level-up message. ``None`` for the localized default."""
	stack_roles: bool = True
	"""Whether members keep lower role rewards when they reach a higher one."""


class LevelConfigUpdate(BaseModel):
	"""Changes to a leveling configuration. Fields left out keep their value; ``null`` clears the channel or message."""

	enabled: bool | None = None
	multiplier: float | None = Field(default=None, ge=0, le=100)
	min_xp: int | None = Field(default=None, ge=0, le=100_000)
	max_xp: int | None = Field(default=None, ge=0, le=100_000)
	cooldown: int | None = Field(default=None, ge=0, le=86_400)
	message_mode: LevelupMode | None = None
	message_channel_id: Snowflake | None = None
	levelup_message: str | None = Field(default=None, max_length=2000)
	stack_roles: bool | None = None


class LevelReward(BaseModel):
	"""A role members get when they reach a level."""

	level: int = Field(ge=0)
	role_id: Snowflake


class LevelOverride(BaseModel):
	"""A channel's or role's XP multiplier, and whether it awards no XP at all."""

	id: Snowflake
	"""The channel or role."""
	multiplier: float = 1.0
	ignored: bool = False


class LevelOverrides(BaseModel):
	"""A guild's channel and role XP overrides."""

	channels: list[LevelOverride] = []
	roles: list[LevelOverride] = []


class LevelOverrideUpdate(BaseModel):
	"""Changes to a channel's or role's override. ``None`` fields keep their value."""

	multiplier: float | None = Field(default=None, ge=0, le=100)
	ignored: bool | None = None


class XpAward(BaseModel):
	"""XP a member earned with a message."""

	amount: int = Field(gt=0)


class XpResult(BaseModel):
	"""A member's XP and level after an award."""

	xp: int
	level: int
	previous_level: int


class MemberLevel(BaseModel):
	"""A member's XP and level in a guild."""

	user_id: Snowflake
	xp: int = 0
	level: int = 0
	rank: int | None = None
	"""1 for the member with the most XP. ``None`` for members without XP."""


class Leaderboard(BaseModel):
	"""One page of a guild's members by XP, most first."""

	total: int
	"""How many members have XP."""
	entries: list[MemberLevel]


class UserIds(BaseModel):
	"""Members to look up."""

	user_ids: list[Snowflake] = Field(max_length=10_000)
