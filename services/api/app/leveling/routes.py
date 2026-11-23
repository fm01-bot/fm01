"""Leveling routes for the Internal API: XP, levels, configuration, role rewards and XP overrides."""

from __future__ import annotations

from typing import Annotated, Literal

from api import (
	Leaderboard,
	LevelConfig,
	LevelConfigUpdate,
	LevelOverride,
	LevelOverrides,
	LevelOverrideUpdate,
	LevelReward,
	MemberLevel,
	Snowflake,
	UserIds,
	XpAward,
	XpResult,
)
from fastapi import APIRouter, Query, Response

from app.auth import Origin, State

__all__ = ("internal",)

internal = APIRouter(prefix="/guilds/{guild_id}", tags=["leveling"])


@internal.get("/settings/leveling")
async def internal_level_config(guild_id: Snowflake, state: State) -> LevelConfig:
	"""Get a guild's leveling configuration. The defaults if the guild never configured leveling.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The configuration.
	"""
	return await state.levels.config(guild_id)


@internal.patch("/settings/leveling")
async def internal_update_level_config(
	guild_id: Snowflake, body: LevelConfigUpdate, state: State, origin: Origin = None
) -> LevelConfig:
	"""Change a guild's leveling configuration. Fields left out keep their value; `null` clears the channel or message.

	\f
	Args:
		guild_id: The guild.
		body: The changes.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored configuration.
	"""
	return await state.levels.update_config(guild_id, body, origin)


@internal.get("/settings/leveling/rewards")
async def internal_level_rewards(guild_id: Snowflake, state: State) -> list[LevelReward]:
	"""List a guild's role rewards, lowest level first.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The rewards.
	"""
	return await state.levels.rewards(guild_id)


@internal.post("/settings/leveling/rewards", status_code=204)
async def internal_add_level_reward(
	guild_id: Snowflake, body: LevelReward, state: State, origin: Origin = None
) -> Response:
	"""Add a role reward. Adding one that exists does nothing.

	\f
	Args:
		guild_id: The guild.
		body: The reward.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		An empty response.
	"""
	await state.levels.add_reward(guild_id, body, origin)
	return Response(status_code=204)


@internal.delete("/settings/leveling/rewards/{level}", status_code=204)
async def internal_remove_level_rewards(
	guild_id: Snowflake,
	level: int,
	state: State,
	role_id: Annotated[Snowflake | None, Query()] = None,
	origin: Origin = None,
) -> Response:
	"""Remove a level's role rewards: one role's, or every one.

	\f
	Args:
		guild_id: The guild.
		level: The level.
		state: The app state.
		role_id: Only this role's reward.
		origin: The calling bot instance.

	Returns:
		An empty response.
	"""
	await state.levels.remove_rewards(guild_id, level, role_id, origin)
	return Response(status_code=204)


@internal.get("/settings/leveling/overrides")
async def internal_level_overrides(guild_id: Snowflake, state: State) -> LevelOverrides:
	"""List a guild's channel and role XP overrides.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The overrides.
	"""
	return await state.levels.overrides(guild_id)


@internal.patch("/settings/leveling/overrides/{kind}/{target_id}")
async def internal_update_level_override(
	guild_id: Snowflake,
	kind: Literal["channel", "role"],
	target_id: Snowflake,
	body: LevelOverrideUpdate,
	state: State,
	origin: Origin = None,
) -> LevelOverride:
	"""Change a channel's or role's XP override. `null` fields keep their value.

	\f
	Args:
		guild_id: The guild.
		kind: A channel or a role override.
		target_id: The channel or role.
		body: The changes.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored override.
	"""
	return await state.levels.update_override(guild_id, kind, target_id, body, origin)


@internal.post("/levels/{user_id}/xp")
async def internal_award_xp(guild_id: Snowflake, user_id: Snowflake, body: XpAward, state: State) -> XpResult:
	"""Give a member XP and update their level.

	\f
	Args:
		guild_id: The guild.
		user_id: The member.
		body: The XP.
		state: The app state.

	Returns:
		The member's new XP and level, and the level they had before.
	"""
	return await state.levels.award(guild_id, user_id, body.amount)


@internal.post("/levels/lookup")
async def internal_member_levels(guild_id: Snowflake, body: UserIds, state: State) -> list[MemberLevel]:
	"""Get several members' XP and level, without ranks. Members without XP are left out.

	\f
	Args:
		guild_id: The guild.
		body: The members.
		state: The app state.

	Returns:
		The levels.
	"""
	return await state.levels.members(guild_id, body.user_ids)


@internal.get("/levels/leaderboard")
async def internal_level_leaderboard(
	guild_id: Snowflake,
	state: State,
	offset: Annotated[int, Query(ge=0)] = 0,
	limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> Leaderboard:
	"""List one page of a guild's members by XP, most first.

	\f
	Args:
		guild_id: The guild.
		state: The app state.
		offset: How many members to skip.
		limit: The most members to return.

	Returns:
		The page, and how many members have XP.
	"""
	return await state.levels.leaderboard(guild_id, offset, limit)


@internal.get("/levels/{user_id}")
async def internal_member_level(guild_id: Snowflake, user_id: Snowflake, state: State) -> MemberLevel:
	"""Get a member's XP, level and rank. All zero, without a rank, if they have no XP.

	\f
	Args:
		guild_id: The guild.
		user_id: The member.
		state: The app state.

	Returns:
		The member's level.
	"""
	return await state.levels.member(guild_id, user_id)
