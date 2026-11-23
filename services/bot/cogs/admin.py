from io import StringIO
from logging import getLogger
from pathlib import Path
from time import perf_counter
from typing import Literal

import discord
from core import Bot, Context, command, group, update_slash_localizations
from discord import app_commands
from discord.ext import commands
from helpers.custom_response import LOCALIZATION_ROOT, RESPONSES_PATH

from api import BlacklistEntry, BlacklistKind

logger = getLogger(__name__)

KIND_CHOICES = [
	app_commands.Choice(name="blacklist_add-args-kind-user", value="user"),
	app_commands.Choice(name="blacklist_add-args-kind-guild", value="guild"),
]


def _format_entry(entry: BlacklistEntry) -> str:
	"""Render a blacklist entry as one line of the ``blacklist`` listing.

	Args:
		entry: The entry.

	Returns:
		The line: kind, ID, reason, who added it and when.
	"""
	reason = entry.reason or "no reason"
	return (
		f"`{entry.kind}` `{entry.target_id}`: {reason} "
		f"(by <@{entry.created_by}>, {discord.utils.format_dt(entry.created_at, 'R')})"
	)


class Admin(commands.GroupCog, name="admin"):
	def __init__(self, client: Bot):
		self.client: Bot = client

	@command(hidden=True)
	@commands.is_owner()
	async def reload(self, ctx: Context, cog: str):
		try:
			benchmark = perf_counter()
			await self.client.reload_extension(f"cogs.{cog}")
			end = perf_counter() - benchmark
			await ctx.reply(content=f"Reloaded extension `{cog}` in **{end:.2f}s**")
			logger.info(f"{ctx.author.name} reloaded {cog}.py")
		except (
			commands.ExtensionNotLoaded,
			commands.ExtensionNotFound,
			commands.NoEntryPointError,
			commands.ExtensionFailed,
		) as e:
			await ctx.reply(content=f"Failed to reload extension `{cog}`: {e}")

	@command(hidden=True)
	@commands.is_owner()
	async def load(self, ctx: Context, cog: str):
		try:
			benchmark = perf_counter()
			await self.client.load_extension(f"cogs.{cog}")
			end = perf_counter() - benchmark
			await ctx.reply(content=f"Loaded extension `{cog}` in **{end:.2f}s**")
			logger.info(f"{ctx.author.name} loaded {cog}.py")
		except (
			commands.ExtensionNotLoaded,
			commands.ExtensionNotFound,
			commands.NoEntryPointError,
			commands.ExtensionFailed,
		) as e:
			await ctx.reply(content=f"Failed to load extension `{cog}`: {e}")

	@command(hidden=True)
	@commands.is_owner()
	async def unload(self, ctx: Context, cog: str):
		try:
			benchmark = perf_counter()
			await self.client.unload_extension(f"cogs.{cog}")
			end = perf_counter() - benchmark
			await ctx.reply(content=f"Unloaded extension `{cog}` in **{end:.2f}s**")
			logger.info(f"{ctx.author.name} unloaded {cog}.py")
		except (
			commands.ExtensionNotLoaded,
			commands.ExtensionNotFound,
			commands.NoEntryPointError,
			commands.ExtensionFailed,
		) as e:
			await ctx.reply(content=f"Failed to unload extension `{cog}`: {e}")

	@command(hidden=True)
	@commands.is_owner()
	async def l10nreload(self, ctx: Context, path: str = str(RESPONSES_PATH)):
		target_path = Path(path).resolve()
		root = LOCALIZATION_ROOT.resolve()
		if target_path != root and root not in target_path.parents:
			await ctx.reply(content=f"⚠️ Access denied: path must be within {root}.")
			return

		ctx.bot.custom_response.load_localizations(target_path)
		await ctx.reply(content="Reloaded localization files.")
		logger.info(f"{ctx.author.name} reloaded localization files from {target_path}.")

	@command(hidden=True)
	@commands.is_owner()
	@app_commands.choices(
		scope=[
			app_commands.Choice(name="sync-args-scope-local", value="~"),
			app_commands.Choice(name="sync-args-scope-global", value="*"),
			app_commands.Choice(name="sync-args-scope-resync", value="^"),
			app_commands.Choice(name="sync-args-scope-slash", value="/"),
		]
	)
	async def sync(
		self,
		ctx: Context,
		guilds: commands.Greedy[discord.Object] = None,  # ty:ignore[invalid-parameter-default]
		# ^ until 2.7.1+ comes out dpy is gonna cry about `Greedy[X] | Y`,
		# this is fixed and merged in https://github.com/Rapptz/discord.py/pull/10452
		# but rapptz didn't release it yet
		scope: Literal["~", "*", "^", "/"] | None = None,
	) -> None:
		tree: discord.app_commands.CommandTree[ctx.bot] = ctx.bot.tree
		benchmark = perf_counter()

		if guilds is None:
			if scope == "~":
				synced = await tree.sync(guild=ctx.guild)
			elif scope == "*":
				tree.copy_global_to(guild=ctx.guild)
				synced = await tree.sync(guild=ctx.guild)
			elif scope == "^":
				tree.clear_commands(guild=ctx.guild)
				await tree.sync(guild=ctx.guild)
				synced = []
			elif scope == "/":
				update_slash_localizations()
				await ctx.reply(content="Reloaded slash localizations")
				return
			else:
				update_slash_localizations()
				synced = await tree.sync()

			end = perf_counter() - benchmark
			await ctx.reply(
				content=f"Synced **{len(synced)}** {'commands' if len(synced) != 1 else 'command'} {'globally' if scope is None else 'to the current guild'}, took **{end:.2f}s**"
			)
		else:
			update_slash_localizations()
			guilds_synced = 0
			for guild in guilds:
				try:
					await tree.sync(guild=guild)
				except discord.HTTPException:
					pass
				else:
					guilds_synced += 1

			end = perf_counter() - benchmark
			await ctx.reply(content=f"Synced the tree to **{guilds_synced}/{len(guilds)}** guilds, took **{end:.2f}s**")

	@group(hidden=True, l10n_key="blacklist", name="blacklist")
	@commands.is_owner()
	async def blacklist(self, ctx: Context):
		entries = await self.client.api.blacklist.entries()
		if not entries:
			await ctx.reply(content="Nobody is blacklisted.")
			return
		listing = f"**{len(entries)}** blacklisted:\n" + "\n".join(_format_entry(entry) for entry in entries)
		if len(listing) > 2000:
			file = discord.File(StringIO(listing), filename="blacklist.txt")  # type: ignore # StringIO is supported
			await ctx.reply(content=f"**{len(entries)}** blacklisted, listed in the file.", file=file)
			return
		await ctx.reply(content=listing, allowed_mentions=discord.AllowedMentions.none())

	@blacklist.command(hidden=True, l10n_key="blacklist_add", name="add")
	@commands.is_owner()
	@app_commands.choices(kind=KIND_CHOICES)
	async def blacklist_add(
		self, ctx: Context, kind: BlacklistKind, target: discord.Object, *, reason: str | None = None
	) -> None:
		if kind == "user" and (target.id in (self.client.owner_ids or ()) or target.id == self.client.owner_id):
			await ctx.reply(content="Bot owners can't be blacklisted.")
			return
		if reason is not None and len(reason) > 500:
			await ctx.reply(content="The reason can be at most 500 characters long.")
			return
		await self.client.blacklist.add(kind, target.id, ctx.author.id, reason)
		await ctx.reply(content=f"Blacklisted {kind} `{target.id}`.")
		logger.info(f"{ctx.author.name} blacklisted {kind} {target.id}: {reason}")

	@blacklist.command(hidden=True, l10n_key="blacklist_remove", name="remove")
	@commands.is_owner()
	@app_commands.choices(kind=KIND_CHOICES)
	async def blacklist_remove(self, ctx: Context, kind: BlacklistKind, target: discord.Object) -> None:
		if not await self.client.blacklist.remove(kind, target.id):
			await ctx.reply(content=f"{kind.capitalize()} `{target.id}` isn't blacklisted.")
			return
		await ctx.reply(content=f"Took {kind} `{target.id}` off the blacklist.")
		logger.info(f"{ctx.author.name} took {kind} {target.id} off the blacklist")


async def setup(client: Bot):
	await client.add_cog(Admin(client))
