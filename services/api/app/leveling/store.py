"""The leveling store: members' XP and levels, leveling configuration, role rewards and XP overrides."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

import asyncpg
from api import (
	LEVEL_CONFIG_SETTING,
	LEVEL_OVERRIDES_SETTING,
	LEVEL_REWARDS_SETTING,
	Leaderboard,
	LevelConfig,
	LevelConfigUpdate,
	LevelOverride,
	LevelOverrides,
	LevelOverrideUpdate,
	LevelReward,
	MemberLevel,
	XpResult,
	level_from_total_xp,
)

from app.db import snowflake, upsert
from app.events import Announcer

__all__ = ("LevelStore",)

_CONFIG_COLUMNS = {
	"enabled": "is_on",
	"multiplier": "multiplier",
	"min_xp": "min_xp",
	"max_xp": "max_xp",
	"cooldown": "cooldown",
	"message_mode": "message_mode",
	"message_channel_id": "message_channel",
	"levelup_message": "levelup_message",
	"stack_roles": "stack_roles",
}
"""`LevelConfig` field -> ``level_config`` column."""
_NULLABLE = frozenset({"message_channel_id", "levelup_message"})

_OVERRIDE_TABLES = {"channel": ("level_channel_overrides", "channel_id"), "role": ("level_role_overrides", "role_id")}

type OverrideKind = Literal["channel", "role"]


def _config(row: Mapping[str, Any]) -> LevelConfig:
	"""Build a leveling configuration from a ``level_config`` row.

	Args:
		row: The row.

	Returns:
		The configuration. An unknown message mode counts as ``current``.
	"""
	values = {field: row[column] for field, column in _CONFIG_COLUMNS.items()}
	values["message_channel_id"] = snowflake(values["message_channel_id"]) or None
	values["levelup_message"] = values["levelup_message"] or None
	if values["message_mode"] not in ("disabled", "current", "channel"):
		values["message_mode"] = "current"
	return LevelConfig(**values)


class LevelStore:
	"""Reads and writes members' XP and guilds' leveling settings. Announces every settings write.

	Args:
		db: The database pool.
		announcer: Tells bot instances about changes.
	"""

	def __init__(self, db: asyncpg.Pool, announcer: Announcer) -> None:
		self._db = db
		self._announcer = announcer

	async def config(self, guild_id: int) -> LevelConfig:
		"""Get a guild's leveling configuration.

		Args:
			guild_id: The guild.

		Returns:
			The configuration. The defaults if the guild never configured leveling.
		"""
		row = await self._db.fetchrow("SELECT * FROM level_config WHERE guild_id = $1", guild_id)
		return _config(row) if row else LevelConfig()

	async def update_config(self, guild_id: int, changes: LevelConfigUpdate, origin: str | None) -> LevelConfig:
		"""Change a guild's leveling configuration, creating it from the defaults if it doesn't exist.

		Args:
			guild_id: The guild.
			changes: The changes. Only the fields set on it are written; ``None`` clears the channel or message.
			origin: The calling bot instance. ``None`` for the dashboard.

		Returns:
			The stored configuration.
		"""
		fields = {
			_CONFIG_COLUMNS[field]: value
			for field, value in changes.model_dump(exclude_unset=True).items()
			if value is not None or field in _NULLABLE
		}
		row = await upsert(self._db, "level_config", {"guild_id": guild_id}, fields)
		await self._announcer.setting_changed(LEVEL_CONFIG_SETTING, guild_id, origin)
		return _config(row)

	async def rewards(self, guild_id: int) -> list[LevelReward]:
		"""List a guild's role rewards.

		Args:
			guild_id: The guild.

		Returns:
			The rewards, lowest level first.
		"""
		rows = await self._db.fetch(
			"SELECT level, role_id FROM level_roles WHERE guild_id = $1 ORDER BY level, id", guild_id
		)
		return [LevelReward(level=row["level"], role_id=int(row["role_id"])) for row in rows]

	async def add_reward(self, guild_id: int, reward: LevelReward, origin: str | None) -> None:
		"""Add a role reward. Adding one that exists does nothing.

		Args:
			guild_id: The guild.
			reward: The reward.
			origin: The calling bot instance. ``None`` for the dashboard.
		"""
		await self._db.execute(
			"INSERT INTO level_roles (guild_id, level, role_id) VALUES ($1, $2, $3) "
			"ON CONFLICT (guild_id, level, role_id) DO NOTHING",
			guild_id,
			reward.level,
			reward.role_id,
		)
		await self._announcer.setting_changed(LEVEL_REWARDS_SETTING, guild_id, origin)

	async def remove_rewards(self, guild_id: int, level: int, role_id: int | None, origin: str | None) -> None:
		"""Remove a level's role rewards.

		Args:
			guild_id: The guild.
			level: The level.
			role_id: Only this role's reward. ``None`` for every reward of the level.
			origin: The calling bot instance. ``None`` for the dashboard.
		"""
		if role_id is None:
			await self._db.execute("DELETE FROM level_roles WHERE guild_id = $1 AND level = $2", guild_id, level)
		else:
			await self._db.execute(
				"DELETE FROM level_roles WHERE guild_id = $1 AND level = $2 AND role_id = $3", guild_id, level, role_id
			)
		await self._announcer.setting_changed(LEVEL_REWARDS_SETTING, guild_id, origin)

	async def overrides(self, guild_id: int) -> LevelOverrides:
		"""List a guild's channel and role XP overrides.

		Args:
			guild_id: The guild.

		Returns:
			The overrides.
		"""
		lists: dict[str, list[LevelOverride]] = {}
		for kind, (table, column) in _OVERRIDE_TABLES.items():
			rows = await self._db.fetch(
				f"SELECT {column}, multiplier, is_ignored FROM {table} WHERE guild_id = $1 ORDER BY id", guild_id
			)
			lists[kind] = [
				LevelOverride(id=int(row[column]), multiplier=row["multiplier"], ignored=row["is_ignored"])
				for row in rows
			]
		return LevelOverrides(channels=lists["channel"], roles=lists["role"])

	async def update_override(
		self, guild_id: int, kind: OverrideKind, target_id: int, changes: LevelOverrideUpdate, origin: str | None
	) -> LevelOverride:
		"""Change a channel's or role's XP override, creating it (multiplier 1, not ignored) if it doesn't exist.

		Args:
			guild_id: The guild.
			kind: A channel or a role override.
			target_id: The channel or role.
			changes: The changes. ``None`` fields keep their value.
			origin: The calling bot instance. ``None`` for the dashboard.

		Returns:
			The stored override.
		"""
		table, column = _OVERRIDE_TABLES[kind]
		fields: dict[str, Any] = {}
		if changes.multiplier is not None:
			fields["multiplier"] = changes.multiplier
		if changes.ignored is not None:
			fields["is_ignored"] = changes.ignored
		row = await upsert(self._db, table, {"guild_id": guild_id, column: target_id}, fields)
		await self._announcer.setting_changed(LEVEL_OVERRIDES_SETTING, guild_id, origin)
		return LevelOverride(id=target_id, multiplier=row["multiplier"], ignored=row["is_ignored"])

	async def award(self, guild_id: int, user_id: int, amount: int) -> XpResult:
		"""Give a member XP and update their level.

		Args:
			guild_id: The guild.
			user_id: The member.
			amount: The XP. Positive.

		Returns:
			The member's new XP and level, and the level they had before.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			row = await conn.fetchrow(
				"INSERT INTO user_levels (guild_id, user_id, xp, level, last_message_at) VALUES ($1, $2, $3, 0, now()) "
				"ON CONFLICT (guild_id, user_id) DO UPDATE SET xp = user_levels.xp + EXCLUDED.xp, last_message_at = now() "
				"RETURNING xp, level",
				guild_id,
				user_id,
				amount,
			)
			assert row is not None
			level = level_from_total_xp(row["xp"]).level
			if level != row["level"]:
				await conn.execute(
					"UPDATE user_levels SET level = $3 WHERE guild_id = $1 AND user_id = $2", guild_id, user_id, level
				)
		return XpResult(xp=row["xp"], level=level, previous_level=row["level"])

	async def member(self, guild_id: int, user_id: int) -> MemberLevel:
		"""Get a member's XP, level and rank.

		Args:
			guild_id: The guild.
			user_id: The member.

		Returns:
			The member's level. All zero, without a rank, if they have no XP.
		"""
		row = await self._db.fetchrow(
			"SELECT xp, level, (SELECT count(*) + 1 FROM user_levels o WHERE o.guild_id = u.guild_id AND o.xp > u.xp) "
			"AS rank FROM user_levels u WHERE guild_id = $1 AND user_id = $2",
			guild_id,
			user_id,
		)
		if row is None or row["xp"] <= 0:
			return MemberLevel(user_id=user_id, xp=row["xp"] if row else 0, level=row["level"] if row else 0)
		return MemberLevel(user_id=user_id, xp=row["xp"], level=row["level"], rank=row["rank"])

	async def members(self, guild_id: int, user_ids: Sequence[int]) -> list[MemberLevel]:
		"""Get several members' XP and level, without ranks.

		Args:
			guild_id: The guild.
			user_ids: The members.

		Returns:
			The members that have XP.
		"""
		rows = await self._db.fetch(
			"SELECT user_id, xp, level FROM user_levels WHERE guild_id = $1 AND user_id = ANY($2::numeric[])",
			guild_id,
			list(user_ids),
		)
		return [MemberLevel(user_id=int(row["user_id"]), xp=row["xp"], level=row["level"]) for row in rows]

	async def leaderboard(self, guild_id: int, offset: int, limit: int) -> Leaderboard:
		"""List one page of a guild's members by XP, most first.

		Args:
			guild_id: The guild.
			offset: How many members to skip.
			limit: The most members to return.

		Returns:
			The page, and how many members have XP.
		"""
		total = await self._db.fetchval("SELECT count(*) FROM user_levels WHERE guild_id = $1", guild_id)
		rows = await self._db.fetch(
			"SELECT user_id, xp, level FROM user_levels WHERE guild_id = $1 ORDER BY xp DESC, id LIMIT $2 OFFSET $3",
			guild_id,
			limit,
			offset,
		)
		return Leaderboard(
			total=total,
			entries=[
				MemberLevel(user_id=int(row["user_id"]), xp=row["xp"], level=row["level"], rank=offset + index + 1)
				for index, row in enumerate(rows)
			],
		)
