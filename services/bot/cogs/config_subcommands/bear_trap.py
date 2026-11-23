from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
from helpers.cli_parser import CLINode, CLIParseError

from .helpers import resolve_channel

if TYPE_CHECKING:
	from cogs.bear_trap import BearTrap
	from core import Context


def setup_bear_trap_subcommands(parent_node: CLINode) -> CLINode:
	"""Set up CLI commands for the bear trap."""
	node = parent_node.create_subcommand(
		"beartrap", description="Configure the bear trap, a channel where anyone who posts is kicked."
	)

	def cog(ctx: Context) -> BearTrap:
		from cogs.bear_trap import BearTrap

		found = ctx.bot.get_cog("BearTrap")
		if not isinstance(found, BearTrap):
			raise CLIParseError("The bear trap module is not loaded.", node)
		return found

	async def status(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		trap = await cog(ctx).setting.get(ctx.guild.id)
		channel = ctx.guild.get_channel(trap.channel_id) if trap.channel_id else None
		state = f"on in #{channel.name}" if channel else "off"
		return await ctx.send(content=f"```ansi\nBear trap: {state}\nKicked: {trap.kicks}\n```")

	node.callback = status

	enable_node = node.create_subcommand("enable", description="Set the bear trap in a channel.")
	enable_node.add_option("channel", "c", help="Trap channel (e.g. #do-not-post)")
	enable_node.add_argument("channel_pos", required=False, help="Trap channel positional argument")

	async def enable(ctx: Context, channel: str | None = None, channel_pos: str | None = None, **kwargs: Any):
		assert ctx.guild is not None
		raw = channel or channel_pos
		if not raw:
			raise CLIParseError("Please provide a channel, e.g. `?!config beartrap enable #do-not-post`.", enable_node)
		target = resolve_channel(ctx.guild, raw)
		if not isinstance(target, discord.TextChannel) or target.is_news():
			raise CLIParseError(f"Channel `{raw}` was not found or is not a text channel.", enable_node)

		from cogs.bear_trap import missing_permissions

		required, optional = missing_permissions(target)
		if required:
			raise CLIParseError(
				f"I need these permissions in #{target.name} to run the bear trap: {', '.join(required)}", enable_node
			)

		if not await cog(ctx).set_channel(ctx.guild.id, target.id):
			return await ctx.send(content="```ansi\n[-] Could not post the bear trap message. The trap is off.\n```")
		lines = [f"[+] Bear trap set in #{target.name}"]
		if optional:
			lines.append(f"[!] Without {', '.join(optional)}, kicked members get no invite back.")
		return await ctx.send(content="```ansi\n" + "\n".join(lines) + "\n```")

	enable_node.callback = enable

	disable_node = node.create_subcommand("disable", description="Remove the bear trap and its message.")

	async def disable(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		await cog(ctx).set_channel(ctx.guild.id, None)
		return await ctx.send(content="```ansi\n[-] Bear trap removed\n```")

	disable_node.callback = disable
	return node
