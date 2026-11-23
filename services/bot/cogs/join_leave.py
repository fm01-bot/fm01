from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any

import discord
from args.channel import convert_to_custom_channel
from args.format_date_time import FormatDateTime
from args.guild import Guild
from args.member import Member
from discord.ext import commands
from helpers.custom_response import KWARG_MAPPING
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
		self, template: str, member: discord.Member, channel: discord.abc.Messageable | None = None, **extra: Any
	) -> str:
		try:
			formatter = SafeFormatter()
			member_arg = Member.from_member(member)
			guild_arg = Guild.from_guild(member.guild) if member.guild else None
			channel_arg = (
				convert_to_custom_channel(channel)
				if isinstance(channel, (discord.abc.GuildChannel, discord.Thread))
				else None
			)

			format_kwargs: dict[str, Any] = {
				"member": member_arg,
				"user": member_arg,
				"author": member_arg,
				"guild": guild_arg,
				"server": guild_arg,
				"channel": channel_arg,
				"now": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
				"username": member.name,
				"member_count": member.guild.member_count if member.guild else 1,
			}
			for k, v in extra.items():
				for _type, converter in KWARG_MAPPING.items():
					if isinstance(v, _type):
						format_kwargs[k] = converter(v)
						break
				else:
					if isinstance(v, datetime.datetime):
						format_kwargs[k] = FormatDateTime(v, default_style="F")
					elif isinstance(v, (discord.abc.GuildChannel, discord.Thread)):
						format_kwargs[k] = convert_to_custom_channel(v)
					else:
						format_kwargs[k] = v

			return formatter.format(template, **format_kwargs)
		except Exception as e:  # noqa: BLE001
			logger.warning(f"Failed to format member event template '{template}': {e}")
			return template

	@commands.Cog.listener()
	async def on_member_join(self, member: discord.Member):
		if member.bot:
			return

		cfg = await self.join.get(member.guild.id)
		if not cfg or not cfg.enabled or not cfg.channel_id or not cfg.message:
			return

		channel_id = cfg.channel_id
		channel = member.guild.get_channel(channel_id)
		if not channel or not isinstance(channel, discord.abc.Messageable):
			return

		content = self.format_message(cfg.message, member, channel=channel)

		try:
			await channel.send(content)
		except (discord.Forbidden, discord.HTTPException):
			logger.debug(f"Failed to send join message in {channel_id} for guild {member.guild.id}")

	@commands.Cog.listener()
	async def on_member_remove(self, member: discord.Member):
		if member.bot:
			return

		cfg = await self.leave.get(member.guild.id)
		if not cfg or not cfg.enabled or not cfg.channel_id or not cfg.message:
			return

		channel_id = cfg.channel_id
		channel = member.guild.get_channel(channel_id)
		if not channel or not isinstance(channel, discord.abc.Messageable):
			return

		content = self.format_message(cfg.message, member, channel=channel)

		try:
			await channel.send(content)
		except (discord.Forbidden, discord.HTTPException):
			logger.debug(f"Failed to send leave message in {channel_id} for guild {member.guild.id}")


async def setup(client: Bot):
	await client.add_cog(JoinLeave(client))
