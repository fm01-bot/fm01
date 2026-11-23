from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
from cogs.join_leave import greeting_setting, update_greeting
from helpers.cli_parser import CLINode, CLIParseError

from api import GreetingUpdate

from .helpers import resolve_channel

if TYPE_CHECKING:
	from core import Context


def setup_join_subcommands(parent_node: CLINode) -> CLINode:
	join_node = parent_node.create_subcommand("join", description="Configure member join messages.")

	enable_node = join_node.create_subcommand("enable", description="Enable member join messages.")
	enable_node.add_option("channel", "c", help="Target channel for join messages (e.g. #welcome)")
	enable_node.add_option("message", "m", help='Join message template (e.g. "Welcome {user} to {guild}!")')
	enable_node.add_argument("channel_pos", required=False, help="Target channel positional argument")

	async def join_enable(
		ctx: Context,
		channel: str | None = None,
		message: str | None = None,
		channel_pos: str | None = None,
		**kwargs: Any,
	):
		assert ctx.guild is not None
		ch_raw = channel or channel_pos
		target_channel: discord.abc.GuildChannel | discord.Thread | None = None

		if ch_raw:
			target_channel = resolve_channel(ctx.guild, ch_raw)
			if not target_channel or not isinstance(target_channel, discord.abc.Messageable):
				raise CLIParseError(f"Channel `{ch_raw}` was not found or is not a valid text channel.", enable_node)
		else:
			config = await greeting_setting(ctx.bot.settings, ctx.bot.api, "join").get(ctx.guild.id)
			if config and config.channel_id:
				target_channel = ctx.guild.get_channel(config.channel_id)
			if not target_channel and isinstance(ctx.channel, (discord.abc.GuildChannel, discord.Thread)):
				target_channel = ctx.channel

		channel_id = target_channel.id if target_channel else None

		changes = GreetingUpdate(enabled=True, channel_id=channel_id, message=message or None)
		await update_greeting(ctx.bot, "join", ctx.guild.id, changes)

		ch_name = f"#{target_channel.name}" if target_channel else "(unknown)"
		lines = [f"[+] Join messages enabled in {ch_name}"]
		if message:
			lines.append(f"Message: {message}")
		return await ctx.send(content="```ansi\n" + "\n".join(lines) + "\n```")

	enable_node.callback = join_enable

	disable_node = join_node.create_subcommand("disable", description="Disable member join messages.")

	async def join_disable(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		await update_greeting(ctx.bot, "join", ctx.guild.id, GreetingUpdate(enabled=False))
		return await ctx.send(content="```ansi\n[-] Join messages disabled\n```")

	disable_node.callback = join_disable

	msg_node = join_node.create_subcommand("message", description="Set the join message template.")
	msg_node.add_option("message", "m", help="Join message template")
	msg_node.add_argument("message_pos", nargs="*", required=False, help="Join message positional tokens")

	async def join_message(
		ctx: Context, message: str | None = None, message_pos: list[str] | None = None, **kwargs: Any
	):
		assert ctx.guild is not None
		text = message or (" ".join(message_pos) if message_pos else None)
		if not text:
			raise CLIParseError('Please provide a message template via `--message "..."` or as arguments.', msg_node)

		changes = GreetingUpdate(message=text, fallback_channel_id=ctx.channel.id)
		await update_greeting(ctx.bot, "join", ctx.guild.id, changes)

		return await ctx.send(content=f"```ansi\nJoin message template updated:\n{text}\n```")

	msg_node.callback = join_message

	status_node = join_node.create_subcommand("status", description="Show the current join configuration.")

	async def join_status(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		row = await greeting_setting(ctx.bot.settings, ctx.bot.api, "join").get(ctx.guild.id)
		if not row:
			return await ctx.send(content="```ansi\nJoin messages are not configured for this server.\n```")

		is_on = row.enabled
		channel = ctx.guild.get_channel(row.channel_id) if row.channel_id else None
		ch_str = f"#{channel.name}" if channel else "(None)"
		msg_template = row.message or "(None)"

		content = (
			f"```ansi\n"
			f"Join Configuration ({ctx.guild.name})\n\n"
			f"Status: {'Enabled' if is_on else 'Disabled'}\n"
			f"Channel: {ch_str}\n"
			f"Template: {msg_template}\n"
			f"```"
		)
		return await ctx.send(content=content)

	status_node.callback = join_status

	return join_node
