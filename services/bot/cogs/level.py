"""Leveling system cog for XP tracking, rank cards, leaderboards, and rewards."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

import discord
from args import User
from core import Bot, Context, command
from discord import app_commands
from discord.ext import commands
from helpers.level_card import create_level_card
from helpers.leveling import GuildLevelConfig, LevelupMessage, level_from_total_xp

from api import (
	LEVEL_CONFIG_SETTING,
	LEVEL_OVERRIDES_SETTING,
	LEVEL_REWARDS_SETTING,
	LevelConfig,
	LevelConfigUpdate,
	LevelOverrideUpdate,
)

if TYPE_CHECKING:
	from core.api import ApiClient
	from core.settings import GuildSetting, GuildSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LevelOverrides:
	"""A guild's per-channel and per-role XP overrides: ID -> (multiplier, is_ignored)."""

	channels: Mapping[int, tuple[float, bool]] = field(default_factory=dict)
	roles: Mapping[int, tuple[float, bool]] = field(default_factory=dict)


def _guild_config(guild_id: int, stored: LevelConfig) -> GuildLevelConfig:
	"""Build the bot's leveling configuration from the one the API stores.

	Args:
		guild_id: The guild.
		stored: The stored configuration.

	Returns:
		The configuration.
	"""
	return GuildLevelConfig(
		guild_id=guild_id,
		is_on=stored.enabled,
		multiplier=stored.multiplier,
		min_xp=stored.min_xp,
		max_xp=stored.max_xp,
		cooldown=stored.cooldown,
		message_mode=LevelupMessage(stored.message_mode),
		message_channel=stored.message_channel_id,
		levelup_message=stored.levelup_message,
		stack_roles=stored.stack_roles,
	)


def level_config_setting(settings: GuildSettings, api: ApiClient) -> GuildSetting[GuildLevelConfig]:
	"""Register the guild's leveling configuration, stored behind the API (usable without the Level cog loaded).

	Args:
		settings: The registry to add it to.
		api: The API client it loads through.

	Returns:
		The setting. The defaults for guilds that never configured leveling.
	"""

	async def load(guild_id: int) -> GuildLevelConfig:
		return _guild_config(guild_id, await api.levels.config(guild_id))

	return settings.add_remote(LEVEL_CONFIG_SETTING, load, None)


class LevelSettings:
	"""A guild's leveling configuration, role rewards and XP overrides, and the changes the commands make to them.

	Usable without the Level cog loaded (the config commands use it directly). Every change goes through the API,
	which announces it; this instance caches what the API stored, or reloads it.

	Args:
		bot: The bot, whose settings registry and API client it uses.
	"""

	def __init__(self, bot: Bot) -> None:
		api = bot.api
		self._api = api.levels

		async def load_rewards(guild_id: int) -> list[tuple[int, int]]:
			return [(reward.level, reward.role_id) for reward in await api.levels.rewards(guild_id)]

		async def load_overrides(guild_id: int) -> LevelOverrides:
			stored = await api.levels.overrides(guild_id)
			return LevelOverrides(
				channels={o.id: (o.multiplier, o.ignored) for o in stored.channels},
				roles={o.id: (o.multiplier, o.ignored) for o in stored.roles},
			)

		self.config: GuildSetting[GuildLevelConfig] = level_config_setting(bot.settings, api)
		self.rewards: GuildSetting[list[tuple[int, int]]] = bot.settings.add_remote(
			LEVEL_REWARDS_SETTING, load_rewards, None
		)
		self.overrides: GuildSetting[LevelOverrides] = bot.settings.add_remote(
			LEVEL_OVERRIDES_SETTING, load_overrides, None
		)

	async def get_guild_config(self, guild_id: int) -> GuildLevelConfig:
		"""The guild's leveling configuration (defaults if it has none)."""
		return await self.config.get(guild_id)

	async def get_role_rewards(self, guild_id: int) -> list[tuple[int, int]]:
		"""The guild's (level, role_id) rewards, lowest level first."""
		return await self.rewards.get(guild_id)

	async def _update(self, guild_id: int, **changes: Any) -> None:
		"""Change the leveling configuration and cache what the API stored.

		Args:
			guild_id: The guild.
			**changes: `LevelConfigUpdate` fields. ``None`` clears the channel or message.
		"""
		stored = await self._api.update_config(guild_id, LevelConfigUpdate(**changes))
		self.config.remember(guild_id, _guild_config(guild_id, stored))

	async def enable_leveling(self, guild_id: int) -> None:
		"""Enable leveling in the given guild.

		Args:
			guild_id: Discord guild ID.
		"""
		await self._update(guild_id, enabled=True)

	async def disable_leveling(self, guild_id: int) -> None:
		"""Disable leveling in the given guild.

		Args:
			guild_id: Discord guild ID.
		"""
		await self._update(guild_id, enabled=False)

	async def update_xp_config(
		self,
		guild_id: int,
		*,
		min_xp: int | None = None,
		max_xp: int | None = None,
		multiplier: float | None = None,
		cooldown: int | None = None,
	) -> None:
		"""Update XP generation rates and cooldown settings for a guild. ``None`` keeps a value.

		Args:
			guild_id: Discord guild ID.
			min_xp: Minimum base XP awarded per message.
			max_xp: Maximum base XP awarded per message.
			multiplier: Global XP multiplier.
			cooldown: Cooldown in seconds between XP gains per member.
		"""
		changes = {"min_xp": min_xp, "max_xp": max_xp, "multiplier": multiplier, "cooldown": cooldown}
		await self._update(guild_id, **{key: value for key, value in changes.items() if value is not None})

	async def update_message_config(
		self, guild_id: int, *, mode: str | None = None, channel_id: int | None = None, template: str | None = None
	) -> None:
		"""Update level-up announcement delivery mode, channel, and message template. ``None`` keeps a value.

		Args:
			guild_id: Discord guild ID.
			mode: Delivery mode ('current', 'channel', or 'disabled').
			channel_id: Target channel ID when mode is 'channel'.
			template: Custom announcement message template.
		"""
		changes = {"message_mode": mode, "message_channel_id": channel_id, "levelup_message": template}
		await self._update(guild_id, **{key: value for key, value in changes.items() if value is not None})

	async def set_stack_roles(self, guild_id: int, stack: bool) -> None:
		"""Configure whether role rewards stack or replace previous tiers.

		Args:
			guild_id: Discord guild ID.
			stack: True to keep all previous role rewards, False to retain only highest unlocked.
		"""
		await self._update(guild_id, stack_roles=stack)

	async def add_role_reward(self, guild_id: int, level: int, role_id: int) -> None:
		"""Add a role reward unlocked upon reaching a level.

		Args:
			guild_id: Discord guild ID.
			level: Level milestone.
			role_id: Discord role ID to award.
		"""
		await self._api.add_reward(guild_id, level, role_id)
		await self.rewards.refresh(guild_id)

	async def remove_role_reward(self, guild_id: int, level: int, role_id: int | None = None) -> None:
		"""Remove role reward(s) associated with a level.

		Args:
			guild_id: Discord guild ID.
			level: Level milestone.
			role_id: Optional specific role ID to remove. If None, removes all roles for that level.
		"""
		await self._api.remove_rewards(guild_id, level, role_id)
		await self.rewards.refresh(guild_id)

	async def _override(self, guild_id: int, kind: Literal["channel", "role"], target_id: int, **changes: Any) -> None:
		await self._api.update_override(guild_id, kind, target_id, LevelOverrideUpdate(**changes))
		await self.overrides.refresh(guild_id)

	async def set_channel_ignored(self, guild_id: int, channel_id: int, is_ignored: bool) -> None:
		"""Set whether a channel is excluded from XP gain.

		Args:
			guild_id: Discord guild ID.
			channel_id: Discord channel ID.
			is_ignored: True to ignore channel, False to allow XP.
		"""
		await self._override(guild_id, "channel", channel_id, ignored=is_ignored)

	async def set_channel_multiplier(self, guild_id: int, channel_id: int, multiplier: float) -> None:
		"""Set custom XP multiplier for a channel.

		Args:
			guild_id: Discord guild ID.
			channel_id: Discord channel ID.
			multiplier: XP multiplier factor.
		"""
		await self._override(guild_id, "channel", channel_id, multiplier=multiplier)

	async def set_role_ignored(self, guild_id: int, role_id: int, is_ignored: bool) -> None:
		"""Set whether members with a role are excluded from XP gain.

		Args:
			guild_id: Discord guild ID.
			role_id: Discord role ID.
			is_ignored: True to ignore role, False to allow XP.
		"""
		await self._override(guild_id, "role", role_id, ignored=is_ignored)

	async def set_role_multiplier(self, guild_id: int, role_id: int, multiplier: float) -> None:
		"""Set custom XP multiplier for a role.

		Args:
			guild_id: Discord guild ID.
			role_id: Discord role ID.
			multiplier: XP multiplier factor.
		"""
		await self._override(guild_id, "role", role_id, multiplier=multiplier)


@app_commands.guild_only()
@commands.guild_only()
class Level(commands.Cog, name="Level"):
	"""Cog handling user XP gain, rank card rendering, leaderboards, and automated role rewards."""

	def __init__(self, client: Bot):
		"""Initialize the Level cog.

		Args:
			client: The main bot instance.
		"""
		self.client = client
		self.levels = LevelSettings(client)
		self.config = self.levels.config
		self.rewards = self.levels.rewards
		self.overrides = self.levels.overrides
		self.cooldowns: dict[tuple[int, int], float] = {}

	async def get_guild_config(self, guild_id: int) -> GuildLevelConfig:
		"""The guild's leveling configuration (defaults if it has none)."""
		return await self.levels.get_guild_config(guild_id)

	async def get_role_rewards(self, guild_id: int) -> list[tuple[int, int]]:
		"""The guild's (level, role_id) rewards, lowest level first."""
		return await self.levels.get_role_rewards(guild_id)

	async def get_channel_override(self, guild_id: int, channel_id: int) -> tuple[float, bool] | None:
		"""The (multiplier, is_ignored) override for a channel, if any."""
		return (await self.overrides.get(guild_id)).channels.get(channel_id)

	async def get_role_overrides(self, guild_id: int) -> Mapping[int, tuple[float, bool]]:
		"""The guild's role_id -> (multiplier, is_ignored) overrides."""
		return (await self.overrides.get(guild_id)).roles

	@command(name="level", aliases=["rank", "xp", "lvl"], user=False)
	async def level_command(self, ctx: Context, member: discord.Member | None = None) -> None:
		if not ctx.guild:
			return
		await ctx.defer()  # slow: renders the rank card image

		target = member or (ctx.author if isinstance(ctx.author, discord.Member) else None)
		if not target:
			return

		member_level = await self.client.api.levels.member(ctx.guild.id, target.id)
		progress = level_from_total_xp(member_level.xp)
		rank = member_level.rank

		localized_label = await self.client.custom_response.get_message("level_card.label", ctx)
		level_label = localized_label if isinstance(localized_label, str) else "lvl"

		card_buffer = await create_level_card(
			user=target,
			rank=rank,
			level=progress.level,
			current_xp=progress.current_xp,
			needed_xp=progress.needed_xp,
			level_label=level_label,
		)
		file = discord.File(card_buffer, filename=f"level_{target.id}.png")
		await ctx.send(file=file)

	@command(name="levels", aliases=["top", "lvlleaderboard", "lvls"], user=False)
	async def levels_command(self, ctx: Context, page: int = 1) -> None:
		if not ctx.guild:
			return

		page = max(page, 1)

		per_page = 10
		offset = (page - 1) * per_page

		board = await self.client.api.levels.leaderboard(ctx.guild.id, offset, per_page)
		total_pages = max(1, (board.total + per_page - 1) // per_page)

		if page > total_pages:
			page = total_pages
			offset = (page - 1) * per_page
			board = await self.client.api.levels.leaderboard(ctx.guild.id, offset, per_page)

		entries = []
		for idx, row in enumerate(board.entries):
			user_id = row.user_id
			cached_user = self.client.get_user(user_id)
			entries.append(
				{
					"number": offset + idx + 1,
					"user": User.from_user(cached_user)
					if cached_user
					else await self.client.custom_response.get_message("level_unknown_user", ctx, user_id=user_id),
					"level": row.level,
					"xp": f"{row.xp:,}",
				}
			)
		(message,) = await self.client.custom_response.get_list(
			"levels_leaderboard", ctx, entries, page=page, pages=total_pages
		)
		await ctx.send(**message)

	async def _reward_reason(self, member: discord.Member, key: str, **kwargs: Any) -> str | None:
		text = await self.client.custom_response.get_message(f"level_reward.{key}", member.guild, **kwargs)
		return text if isinstance(text, str) else None

	async def handle_role_rewards(
		self, member: discord.Member, old_level: int, new_level: int, stack_roles: bool
	) -> None:
		"""Assign role rewards based on levels earned.

		Args:
			member: The member who leveled up.
			old_level: Member's level prior to the XP update.
			new_level: Member's newly reached level.
			stack_roles: Whether all unlocked roles are kept or only highest tier.
		"""
		rewards = await self.get_role_rewards(member.guild.id)
		if not rewards:
			return

		if stack_roles:
			for lvl, r_id in rewards:
				if old_level < lvl <= new_level:
					role = member.guild.get_role(r_id)
					if role and role not in member.roles:
						try:
							await member.add_roles(role, reason=await self._reward_reason(member, "reason", level=lvl))
						except (discord.Forbidden, discord.HTTPException):
							logger.warning(f"Failed to add role {role.name} to {member.name} in {member.guild.name}")
		else:
			unlocked = [r for r in rewards if r[0] <= new_level]
			if unlocked:
				highest_lvl, highest_r_id = unlocked[-1]
				highest_role = member.guild.get_role(highest_r_id)

				roles_to_remove = [
					r_obj
					for _lvl, rid in unlocked[:-1]
					if rid != highest_r_id
					and (r_obj := member.guild.get_role(rid)) is not None
					and r_obj in member.roles
				]
				if roles_to_remove:
					try:
						await member.remove_roles(
							*roles_to_remove, reason=await self._reward_reason(member, "replace_reason")
						)
					except (discord.Forbidden, discord.HTTPException):
						pass

				if highest_role and highest_role not in member.roles:
					try:
						await member.add_roles(
							highest_role, reason=await self._reward_reason(member, "reason", level=highest_lvl)
						)
					except (discord.Forbidden, discord.HTTPException):
						logger.warning(
							f"Failed to add highest role {highest_role.name} to {member.name} in {member.guild.name}"
						)

	async def send_levelup_notification(
		self, message: discord.Message, config: GuildLevelConfig, new_level: int, total_xp: int
	) -> None:
		"""Send custom level up announcement if configured.

		Args:
			message: The original trigger message sent by member.
			config: Guild leveling configuration.
			new_level: Newly reached level.
			total_xp: Total cumulative XP for the member.
		"""
		if config.message_mode == LevelupMessage.DISABLED:
			return

		target_channel: discord.abc.Messageable | None = None
		if config.message_mode == LevelupMessage.CHANNEL and config.message_channel and message.guild:
			ch = message.guild.get_channel(config.message_channel)
			if isinstance(ch, discord.abc.Messageable):
				target_channel = ch

		if not target_channel:
			target_channel = message.channel

		if config.levelup_message:
			text = (
				config.levelup_message.replace("{user.mention}", message.author.mention)
				.replace("{user}", message.author.mention)
				.replace("{username}", message.author.name)
				.replace("{display_name}", message.author.display_name)
				.replace("{level}", str(new_level))
				.replace("{xp}", f"{total_xp:,}")
			)
			try:
				await target_channel.send(text)
			except (discord.Forbidden, discord.HTTPException):
				guild_id = message.guild.id if message.guild else 0
				logger.warning(f"Failed to send level-up message in guild {guild_id}")
			return

		payload = await self.client.custom_response.get_message(
			"levelup_message", message, user=message.author, level=new_level, xp=f"{total_xp:,}"
		)
		if isinstance(payload, dict):
			send_kwargs = dict(payload)
			if getattr(target_channel, "id", None) != getattr(message.channel, "id", None):
				send_kwargs.pop("reference", None)
			try:
				await target_channel.send(**send_kwargs)
			except (discord.Forbidden, discord.HTTPException):
				guild_id = message.guild.id if message.guild else 0
				logger.warning(f"Failed to send level-up message in guild {guild_id}")
		else:
			try:
				await target_channel.send(str(payload))
			except (discord.Forbidden, discord.HTTPException):
				guild_id = message.guild.id if message.guild else 0
				logger.warning(f"Failed to send level-up message in guild {guild_id}")

	@commands.Cog.listener("on_message")
	async def on_message_xp(self, message: discord.Message) -> None:
		"""Award XP to members on message send with cooldowns and multipliers."""
		if message.author.bot or not message.guild or not isinstance(message.author, discord.Member):
			return

		guild_id = message.guild.id
		config = await self.get_guild_config(guild_id)
		if not config.is_on:
			return

		ch_override = await self.get_channel_override(guild_id, message.channel.id)
		if ch_override and ch_override[1]:
			return

		role_overrides = await self.get_role_overrides(guild_id)
		member_role_ids = {r.id for r in message.author.roles}
		for r_id in member_role_ids:
			if r_id in role_overrides and role_overrides[r_id][1]:
				return

		now = time.time()
		cd_key = (guild_id, message.author.id)
		last_xp_time = self.cooldowns.get(cd_key, 0.0)
		if now - last_xp_time < config.cooldown:
			return

		self.cooldowns[cd_key] = now

		effective_mult = config.multiplier
		if ch_override and ch_override[0] > 0:
			effective_mult *= ch_override[0]

		role_mults = [
			role_overrides[r_id][0]
			for r_id in member_role_ids
			if r_id in role_overrides and role_overrides[r_id][0] > 0
		]
		if role_mults:
			effective_mult *= max(role_mults)

		raw_xp = random.randint(config.min_xp, config.max_xp)
		xp_to_add = round(raw_xp * effective_mult)
		if xp_to_add <= 0:
			return

		result = await self.client.api.levels.award(guild_id, message.author.id, xp_to_add)
		if result.level > result.previous_level:
			await self.handle_role_rewards(message.author, result.previous_level, result.level, config.stack_roles)
			await self.send_levelup_notification(message, config, result.level, result.xp)


async def setup(client: Bot):
	await client.add_cog(Level(client))
