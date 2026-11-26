from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
from helpers.cli_parser import CLINode, CLIParseError

from .helpers import resolve_channel

if TYPE_CHECKING:
	from cogs.suggestions import Suggestions
	from core import Context


def setup_suggestions_subcommands(parent_node: CLINode) -> CLINode:
	"""Set up CLI commands for suggestions."""
	node = parent_node.create_subcommand("suggestions", description="Configure the suggestions channel.")

	def cog(ctx: Context) -> Suggestions:
		from cogs.suggestions import Suggestions

		found = ctx.bot.get_cog("Suggestions")
		if not isinstance(found, Suggestions):
			raise CLIParseError("The suggestions module is not loaded.", node)
		return found

	async def status(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		config = await cog(ctx).setting.get(ctx.guild.id)
		channel = ctx.guild.get_channel(config.channel_id) if config.channel_id else None
		state = f"on in #{channel.name}" if channel else "off"
		threads = "on" if config.threads else "off"
		return await ctx.send(content=f"```ansi\nSuggestions: {state}\nThreads: {threads}\n```")

	node.callback = status

	channel_node = node.create_subcommand("channel", description="Post suggestions in a channel.")
	channel_node.add_argument("channel", required=True, help="Suggestions channel (e.g. #suggestions)")

	async def set_channel(ctx: Context, channel: str | None = None, **kwargs: Any):
		assert ctx.guild is not None
		target = resolve_channel(ctx.guild, channel)
		if not isinstance(target, discord.TextChannel) or target.is_news():
			raise CLIParseError(f"Channel `{channel}` was not found or is not a text channel.", channel_node)

		from cogs.suggestions import missing_permissions

		if missing := missing_permissions(target):
			raise CLIParseError(f"I need these permissions in #{target.name}: {', '.join(missing)}", channel_node)

		suggestions = cog(ctx).setting
		config = await suggestions.get(ctx.guild.id)
		await suggestions.set(ctx.guild.id, config.model_copy(update={"channel_id": target.id}))
		return await ctx.send(content=f"```ansi\n[+] Suggestions are posted in #{target.name}\n```")

	channel_node.callback = set_channel

	off_node = node.create_subcommand("off", description="Turn suggestions off.")

	async def turn_off(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		suggestions = cog(ctx).setting
		config = await suggestions.get(ctx.guild.id)
		await suggestions.set(ctx.guild.id, config.model_copy(update={"channel_id": None}))
		return await ctx.send(content="```ansi\n[-] Suggestions are off\n```")

	off_node.callback = turn_off

	threads_node = node.create_subcommand("threads", description="Open a thread under each suggestion.")
	threads_node.add_argument("state", required=True, help="on or off")

	async def set_threads(ctx: Context, state: str | None = None, **kwargs: Any):
		assert ctx.guild is not None
		if state not in ("on", "off"):
			raise CLIParseError("Please say `on` or `off`, e.g. `?!config suggestions threads on`.", threads_node)
		suggestions = cog(ctx).setting
		config = await suggestions.get(ctx.guild.id)
		await suggestions.set(ctx.guild.id, config.model_copy(update={"threads": state == "on"}))
		return await ctx.send(content=f"```ansi\n[+] Suggestion threads are {state}\n```")

	threads_node.callback = set_threads
	return node
