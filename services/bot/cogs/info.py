import ipaddress
import re
from typing import Any

import discord
from args import Bot as BotArg
from args import (
	Category,
	Emoji,
	ForumChannel,
	Guild,
	IPAddress,
	Member,
	PartialEmoji,
	Role,
	StageChannel,
	Template,
	TextChannel,
	User,
	VoiceChannel,
)
from core import Bot, Context, group
from discord.ext import commands
from emoji.unicode_codes import EMOJI_DATA
from helpers.regex import DISCORD_TEMPLATE


class Info(commands.Cog, name="Information"):
	def __init__(self, client: Bot):
		self.client = client

	@group()
	async def info(
		self,
		ctx: Context,
		argument: discord.User | discord.abc.GuildChannel | discord.Role | discord.Emoji | discord.PartialEmoji,
	):
		if isinstance(argument, discord.User):
			await self._invoke(ctx, "user", argument)
		elif isinstance(argument, (discord.abc.GuildChannel, discord.Role)):
			# Outside a guild the converters search every guild the bot is in.
			if argument.guild != ctx.guild:
				raise commands.BadArgument
			await self._invoke(ctx, "channel" if isinstance(argument, discord.abc.GuildChannel) else "role", argument)
		elif isinstance(argument, (discord.Emoji, discord.PartialEmoji)):
			await self._invoke(ctx, "emoji", argument)
		else:
			raise commands.BadArgument

	async def _invoke(self, ctx: Context, name: str, argument: Any) -> None:
		"""Run an ``info`` subcommand with its checks, which ``ctx.invoke`` skips."""
		if cmd := self.info.get_command(name):
			await cmd.can_run(ctx)
			await ctx.invoke(cmd, argument)

	@info.command(l10n_key="userinfo", full_aliases=["ui", "userinfo", "user", "memberinfo", "member", "infomember"])
	async def user(self, ctx: Context, user: discord.Member | discord.User | None = None):
		user = user or ctx.author
		if isinstance(user, discord.Member) and user.guild != ctx.guild:
			# Outside a guild the converter finds members of any guild; show only what's public.
			user = self.client.get_user(user.id) or await self.client.fetch_user(user.id)

		if not ctx.guild and type(user) is discord.User:
			await ctx.send("info.user.not_member", member=User.from_user(user))
			return

		if isinstance(user, discord.Member):
			await ctx.send("info.user.member", member=Member.from_member(user))
			return

		if ctx.guild:
			try:
				member = await ctx.guild.fetch_member(user.id)
				await ctx.send("info.user.member", member=Member.from_member(member))
				return
			except discord.NotFound:
				pass
		await ctx.send("info.user.not_member", member=User.from_user(user))

	@info.command(
		user=False,
		l10n_key="serverinfo",
		full_aliases=["serverinfo", "server", "guildinfo", "guild", "si", "infoguild"],
	)
	async def server(self, ctx: Context):
		assert ctx.guild is not None
		await ctx.send("info.server", server=Guild.from_guild(ctx.guild))

	@info.command(user=False, l10n_key="roleinfo")
	async def role(self, ctx: Context, role: discord.Role | None = None):
		role = role or (ctx.author.top_role if isinstance(ctx.author, discord.Member) else None)
		if not role:
			raise commands.BadArgument("role")
		await ctx.send("info.role", role=Role.from_role(role))

	@info.command(user=False, l10n_key="ipinfo", full_aliases=["ipinfo", "ip"])
	async def ip(self, ctx: Context, ip_addr: str):
		try:
			address = ipaddress.ip_address(ip_addr)
		except ValueError:
			raise commands.BadArgument("ip")
		await ctx.defer()  # slow: calls ipinfo.io
		try:
			ip_json = await self.client.request(f"https://ipinfo.io/{address}/json")
		except RuntimeError:
			raise commands.BadArgument("ip")
		ip = IPAddress(ip_json)
		await ctx.send("info.ip", ip=ip)

	@info.command(l10n_key="botinfo", full_aliases=["botinfo", "bot"])
	async def bot(self, ctx: Context):
		await ctx.send("info.bot", bot=BotArg(self.client))

	@info.command(l10n_key="emojiinfo", full_aliases=["emojiinfo", "einfo", "emoji"])
	async def emoji(self, ctx: Context, emoji_name: str):
		try:
			emoji = await commands.EmojiConverter().convert(ctx, emoji_name)
		except commands.BadArgument:
			emoji = discord.PartialEmoji.from_str(emoji_name)
		if isinstance(emoji, discord.Emoji):
			await ctx.send("info.emoji.custom_emoji", emoji=Emoji.from_emoji(emoji))
		elif isinstance(emoji, discord.PartialEmoji) and emoji.name in EMOJI_DATA:
			await ctx.send("info.emoji.unicode_emoji", emoji=PartialEmoji.from_emoji(emoji))
		else:
			raise commands.BadArgument("emoji")

	@info.command(user=False, l10n_key="chinfo", full_aliases=["chinfo", "channelinfo", "channel"])
	async def channel(self, ctx: Context, channel: discord.abc.GuildChannel):
		if isinstance(channel, discord.TextChannel):
			await ctx.send("info.channel.text", channel=TextChannel.from_channel(channel))
		elif isinstance(channel, discord.VoiceChannel):
			await ctx.send("info.channel.voice", channel=VoiceChannel.from_channel(channel))
		elif isinstance(channel, discord.CategoryChannel):
			await ctx.send("info.channel.category", category=Category.from_category(channel))
		elif isinstance(channel, discord.ForumChannel):
			await ctx.send("info.channel.forum", channel=ForumChannel.from_channel(channel))
		elif isinstance(channel, discord.StageChannel):
			await ctx.send("info.channel.stage", channel=StageChannel.from_channel(channel))
		else:
			raise commands.BadArgument("channel")

	@info.command(l10n_key="tmplteinfo")
	async def template(self, ctx: Context, template: str):
		await ctx.defer()  # slow: fetches the template from Discord
		regex = DISCORD_TEMPLATE.search(template)
		if regex:
			template_code = regex.group(1)
		elif re.fullmatch(r"[a-zA-Z0-9]{5,}", template):
			template_code = template
		else:
			template_code = None

		if template_code:
			try:
				template_obj = await self.client.fetch_template(template_code)
				return await ctx.send("info.template", template=Template.from_template(template_obj))
			except discord.NotFound:
				pass

		template_code = await self.client.db.fetchrow("SELECT * FROM snapshots WHERE code = $1", template.lower())
		if template_code:
			return await ctx.send("info.template", template=await Template.from_dict(self.client, template_code))
		raise commands.BadArgument("template")


async def setup(client: Bot):
	await client.add_cog(Info(client))
