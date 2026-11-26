from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

import discord
from args.channel import convert_to_custom_channel
from args.guild import Guild
from args.member import Member
from discord.ext import commands
from helpers.formatting import SafeFormatter

from api import GreetingConfig, GreetingKind, GreetingUpdate

if TYPE_CHECKING:
	from core import Bot
	from core.api import ApiClient
	from core.settings import GuildSetting, GuildSettings

logger = logging.getLogger(__name__)


def greeting_setting(
	settings: GuildSettings, api: ApiClient, kind: GreetingKind
) -> GuildSetting[GreetingConfig | None]:
	"""Register a guild's join or leave configuration, stored behind the API (usable without the cog loaded).

	Args:
		settings: The registry to add it to.
		api: The API client it loads through.
		kind: Join or leave messages.

	Returns:
		The setting. ``None`` for guilds that never configured it.
	"""

	async def load(guild_id: int) -> GreetingConfig | None:
		return await api.greetings.get(kind, guild_id)

	return settings.add_remote(kind, load, None)


async def update_greeting(bot: Bot, kind: GreetingKind, guild_id: int, changes: GreetingUpdate) -> GreetingConfig:
	"""Change a guild's join or leave configuration and cache what the API stored.

	Args:
		bot: The bot.
		kind: Join or leave messages.
		guild_id: The guild.
		changes: The changes. ``None`` fields keep their value; a new configuration starts on.

	Returns:
		The stored configuration.
	"""
	config = await bot.api.greetings.update(kind, guild_id, changes)
	greeting_setting(bot.settings, bot.api, kind).remember(guild_id, config)
	return config


class JoinLeave(commands.Cog, name="JoinLeave"):
	def __init__(self, client: Bot):
		self.client = client
		self.join: GuildSetting[GreetingConfig | None] = greeting_setting(client.settings, client.api, "join")
		self.leave: GuildSetting[GreetingConfig | None] = greeting_setting(client.settings, client.api, "leave")

	def format_message(
		self, template: str, member: discord.Member, channel: discord.abc.Messageable | None = None
	) -> str:
		try:
			member_arg = Member.from_member(member)
			guild_arg = Guild.from_guild(member.guild) if member.guild else None
			channel_arg = (
				convert_to_custom_channel(channel)
				if isinstance(channel, (discord.abc.GuildChannel, discord.Thread))
				else None
			)
			return SafeFormatter().format(
				template,
				member=member_arg,
				user=member_arg,
				author=member_arg,
				guild=guild_arg,
				server=guild_arg,
				channel=channel_arg,
				now=datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
				username=member.name,
				member_count=member.guild.member_count if member.guild else 1,
			)
		except Exception as e:  # noqa: BLE001
			logger.warning(f"Failed to format member event template '{template}': {e}")
			return template

	async def _greet(self, kind: GreetingKind, cfg: GreetingConfig | None, member: discord.Member) -> None:
		if not cfg or not cfg.enabled or not cfg.channel_id or not cfg.message:
			return
		channel = member.guild.get_channel(cfg.channel_id)
		if not isinstance(channel, discord.abc.Messageable):
			return
		try:
			await channel.send(self.format_message(cfg.message, member, channel=channel))
		except discord.HTTPException:
			logger.debug(f"Failed to send {kind} message in {cfg.channel_id} for guild {member.guild.id}")

	@commands.Cog.listener()
	async def on_member_join(self, member: discord.Member):
		if not member.bot:
			await self._greet("join", await self.join.get(member.guild.id), member)

	@commands.Cog.listener()
	async def on_member_remove(self, member: discord.Member):
		if not member.bot:
			await self._greet("leave", await self.leave.get(member.guild.id), member)


async def setup(client: Bot):
	await client.add_cog(JoinLeave(client))
