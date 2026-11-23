import discord
from args import Member, User
from core import Bot, Context, command
from discord import app_commands
from discord.ext import commands
from helpers import regex


@app_commands.guild_only()
@commands.guild_only()
class AFK(commands.Cog):
	def __init__(self, client: Bot):
		self.client = client
		self.custom_response = client.custom_response
		self.afk_cache: dict[tuple[int, int], dict[str, str]] = {}

	async def cog_load(self):
		for member in await self.client.api.afk.away():
			self.afk_cache[(member.guild_id, member.user_id)] = {
				"message": member.message,
				"previous_nick": member.previous_nick,
			}

	@commands.Cog.listener("on_message")
	async def check_afk(self, message: discord.Message) -> None:
		"""Listens to messages sent. If the author of the message is AFK, turn AFK off."""
		if not message.guild:
			return
		key = (message.guild.id, message.author.id)
		if key not in self.afk_cache:
			return

		ctx = await self.client.get_context(message)
		if ctx.command and ctx.command.name == "afk":
			return

		data = self.afk_cache.pop(key, None)
		await self.client.api.afk.back(message.guild.id, message.author.id)
		if data and data.get("previous_nick"):
			try:
				await ctx.author.edit(nick=data["previous_nick"])
			except (discord.Forbidden, discord.HTTPException):
				pass
		await ctx.reply("afk.off")

	@commands.Cog.listener("on_message")
	async def answer_afk_reason(self, message: discord.Message) -> None:
		"""Listens to messages. Replies with the AFK reason(s) if mentioned users are AFK."""
		if message.author.bot or not message.guild or not message.mentions:
			return

		afk_mentions = [
			u for u in message.mentions if (message.guild.id, u.id) in self.afk_cache and u.id != message.author.id
		]
		if not afk_mentions:
			return

		ctx = await self.client.get_context(message)
		afk_lines = []
		for user in afk_mentions:
			cached = self.afk_cache.get((message.guild.id, user.id))
			if not cached:
				continue
			text = await self.custom_response(
				"afk.reason",
				ctx,
				user=User.from_user(user) if isinstance(user, discord.User) else Member.from_member(user),
				reason=cached["message"],
			)
			if isinstance(text, dict) and "content" in text:
				afk_lines.append(text["content"])

		if afk_lines:
			await ctx.reply("\n".join(afk_lines))

	@command(user=False)
	async def afk(self, ctx: Context, reason: str | None = None):
		assert ctx.guild is not None
		reason_text = reason
		if not reason:
			reason_text = await self.custom_response("afk.dnd", ctx)

		if isinstance(reason_text, str) and regex.DISCORD_INVITE.search(reason_text):
			return await ctx.send("afk.link")

		key = (ctx.guild.id, ctx.author.id)
		toggled = await self.client.api.afk.toggle(
			ctx.guild.id, ctx.author.id, str(reason_text), ctx.author.display_name
		)
		if not toggled.away:
			self.afk_cache.pop(key, None)
			try:
				if isinstance(ctx.author, discord.Member):
					await ctx.author.edit(nick=toggled.previous_nick)
			except (discord.Forbidden, discord.HTTPException):
				pass
			return await ctx.send("afk.off")
		else:
			self.afk_cache[key] = {"message": str(reason_text), "previous_nick": ctx.author.display_name}
			try:
				nick = await self.custom_response("afk.name", ctx, nickname=ctx.author.display_name)
				if isinstance(nick, str):
					nick = nick[:32]
				if isinstance(ctx.author, discord.Member):
					await ctx.author.edit(nick=nick)
			except (discord.Forbidden, discord.HTTPException):
				pass
			return await ctx.send("afk.on")


async def setup(client: Bot):
	await client.add_cog(AFK(client))
