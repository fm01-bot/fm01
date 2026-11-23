"""Helpers and mathematical algorithms for the leveling system."""

from __future__ import annotations

import enum
from dataclasses import dataclass

from api import LevelProgress, level_from_total_xp, total_xp_for_level, xp_to_next_level

__all__ = (
	"GuildLevelConfig",
	"LevelProgress",
	"LevelupMessage",
	"level_from_total_xp",
	"total_xp_for_level",
	"xp_to_next_level",
)


class LevelupMessage(str, enum.Enum):
	"""Delivery modes for level-up announcement messages."""

	DISABLED = "disabled"
	CURRENT = "current"
	CHANNEL = "channel"


@dataclass
class GuildLevelConfig:
	"""Configuration settings for server leveling system.

	Attributes:
		guild_id: Discord guild ID.
		is_on: Whether the leveling system is enabled.
		multiplier: Global XP multiplier.
		min_xp: Minimum base XP awarded per message.
		max_xp: Maximum base XP awarded per message.
		cooldown: Cooldown in seconds between XP gains per user.
		message_mode: Delivery mode for level-up announcements.
		message_channel: Channel ID when mode is CHANNEL.
		levelup_message: Custom announcement template or None for default.
		stack_roles: Whether lower-tier reward roles are kept on level up.
	"""

	guild_id: int
	is_on: bool = True
	multiplier: float = 1.0
	min_xp: int = 15
	max_xp: int = 25
	cooldown: int = 60
	message_mode: LevelupMessage = LevelupMessage.CURRENT
	message_channel: int | None = None
	levelup_message: str | None = None
	stack_roles: bool = True
