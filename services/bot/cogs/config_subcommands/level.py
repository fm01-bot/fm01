"""CLI subcommands for configuring the server leveling system."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
from cogs.level import LevelSettings
from helpers.cli_parser import CLINode, CLIParseError

from .helpers import resolve_channel, resolve_role

if TYPE_CHECKING:
	from core import Context


def _parse_number[N: (int, float)](
	raw: str, cast: type[N], node: CLINode, error: str, *, allow_zero: bool = False
) -> N:
	"""Parse a positive number (or a non-negative one with ``allow_zero``), raising ``error`` otherwise."""
	try:
		value = cast(raw)
	except ValueError:
		raise CLIParseError(error, node) from None
	if value < 0 or (value == 0 and not allow_zero):
		raise CLIParseError(error, node)
	return value


def setup_level_subcommands(parent_node: CLINode) -> CLINode:
	"""Set up leveling configuration subcommands on the CLI parser root.

	Args:
		parent_node: The parent CLINode to attach the 'level' subcommand to.

	Returns:
		CLINode: The configured level CLINode.
	"""
	level_node = parent_node.create_subcommand("level", description="Configure server leveling system.")

	enable_node = level_node.create_subcommand("enable", description="Enable leveling system.")

	async def level_enable(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		cog = LevelSettings(ctx.bot)
		await cog.enable_leveling(ctx.guild.id)

		return await ctx.send(content="```ansi\n[+] Leveling system enabled\n```")

	enable_node.callback = level_enable

	disable_node = level_node.create_subcommand("disable", description="Disable leveling system.")

	async def level_disable(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		cog = LevelSettings(ctx.bot)
		await cog.disable_leveling(ctx.guild.id)

		return await ctx.send(content="```ansi\n[-] Leveling system disabled\n```")

	disable_node.callback = level_disable

	xp_node = level_node.create_subcommand("xp", description="Configure XP gain rates, limits, and cooldown.")
	xp_node.add_option("min", "n", help="Minimum XP per message (e.g. 15)")
	xp_node.add_option("max", "x", help="Maximum XP per message (e.g. 25)")
	xp_node.add_option("multiplier", "m", help="Global guild XP multiplier (e.g. 1.0, 1.5, 2.0)")
	xp_node.add_option("cooldown", "c", help="Cooldown in seconds between XP gain (e.g. 60)")

	async def level_xp(
		ctx: Context,
		min: str | None = None,
		max: str | None = None,
		multiplier: str | None = None,
		cooldown: str | None = None,
		**kwargs: Any,
	):
		assert ctx.guild is not None
		if min is None and max is None and multiplier is None and cooldown is None:
			raise CLIParseError(
				"Please specify at least one option: `--min`, `--max`, `--multiplier`, or `--cooldown`.", xp_node
			)

		min_val: int | None = None
		max_val: int | None = None
		mult_val: float | None = None
		cd_val: int | None = None

		if min is not None:
			min_val = _parse_number(min, int, xp_node, "`--min` must be a positive integer greater than 0.")
		if max is not None:
			max_val = _parse_number(max, int, xp_node, "`--max` must be a positive integer greater than 0.")
		if multiplier is not None:
			mult_val = _parse_number(
				multiplier, float, xp_node, "`--multiplier` must be a positive number greater than 0."
			)
		if cooldown is not None:
			cd_val = _parse_number(
				cooldown, int, xp_node, "`--cooldown` must be a non-negative integer.", allow_zero=True
			)

		cog = LevelSettings(ctx.bot)
		cfg = await cog.get_guild_config(ctx.guild.id)
		cur_min = min_val if min_val is not None else cfg.min_xp
		cur_max = max_val if max_val is not None else cfg.max_xp
		if cur_min > cur_max:
			raise CLIParseError(f"Minimum XP ({cur_min}) cannot be greater than Maximum XP ({cur_max}).", xp_node)

		await cog.update_xp_config(ctx.guild.id, min_xp=min_val, max_xp=max_val, multiplier=mult_val, cooldown=cd_val)

		lines = ["[+] Leveling XP configuration updated:"]
		if min_val is not None:
			lines.append(f"  Minimum XP: {min_val}")
		if max_val is not None:
			lines.append(f"  Maximum XP: {max_val}")
		if mult_val is not None:
			lines.append(f"  Multiplier: {mult_val}x")
		if cd_val is not None:
			lines.append(f"  Cooldown: {cd_val}s")
		return await ctx.send(content="```ansi\n" + "\n".join(lines) + "\n```")

	xp_node.callback = level_xp

	msg_node = level_node.create_subcommand("message", description="Configure level-up announcements.")
	msg_node.add_option("mode", "m", help="Delivery mode: `current`, `channel`, or `disabled`")
	msg_node.add_option("channel", "c", help="Target channel when mode is `channel`")
	msg_node.add_option(
		"template", "t", help="Level-up message template (e.g. 'GG {user}, you reached level {level}!')"
	)
	msg_node.add_argument("template_pos", nargs="*", required=False, help="Message template positional argument")

	async def level_message(
		ctx: Context,
		mode: str | None = None,
		channel: str | None = None,
		template: str | None = None,
		template_pos: list[str] | None = None,
		**kwargs: Any,
	):
		assert ctx.guild is not None
		tmpl_text = template or (" ".join(template_pos) if template_pos else None)

		if mode is None and channel is None and tmpl_text is None:
			raise CLIParseError("Please specify at least one option: `--mode`, `--channel`, or `--template`.", msg_node)

		mode_clean = mode.lower().strip() if mode else None
		if mode_clean and mode_clean not in {"current", "channel", "disabled"}:
			raise CLIParseError("Invalid mode. Choose `current`, `channel`, or `disabled`.", msg_node)

		target_channel: discord.abc.GuildChannel | discord.Thread | None = None
		if channel:
			target_channel = resolve_channel(ctx.guild, channel)
			if not isinstance(target_channel, discord.abc.Messageable):
				raise CLIParseError(f"Channel `{channel}` was not found or is not a valid text channel.", msg_node)
			if mode_clean is None:
				mode_clean = "channel"

		cog = LevelSettings(ctx.bot)
		ch_id = target_channel.id if target_channel else None
		await cog.update_message_config(ctx.guild.id, mode=mode_clean, channel_id=ch_id, template=tmpl_text)

		lines = ["[+] Level-up message configuration updated:"]
		if mode_clean:
			lines.append(f"  Mode: {mode_clean}")
		if target_channel:
			lines.append(f"  Channel: #{target_channel.name}")
		if tmpl_text:
			lines.append(f"  Template: {tmpl_text}")
		return await ctx.send(content="```ansi\n" + "\n".join(lines) + "\n```")

	msg_node.callback = level_message

	rewards_node = level_node.create_subcommand("rewards", description="Configure role rewards for reaching levels.")

	rewards_add_node = rewards_node.create_subcommand("add", description="Add a role reward for a level.")
	rewards_add_node.add_argument("level", required=True, help="Level required for the role reward")
	rewards_add_node.add_argument("role", required=True, help="Target role mention, ID, or name")

	async def rewards_add(ctx: Context, level: str | None = None, role: str | None = None, **kwargs: Any):
		assert ctx.guild is not None
		if not level or not role:
			raise CLIParseError("Usage: `config level rewards add <level> <role>`", rewards_add_node)

		lvl_int = _parse_number(level, int, rewards_add_node, "Level must be a positive integer greater than 0.")

		target_role = resolve_role(ctx.guild, role)
		if not target_role:
			raise CLIParseError(f"Role `{role}` was not found.", rewards_add_node)
		author = ctx.author
		if author.id != ctx.guild.owner_id and (
			not isinstance(author, discord.Member) or target_role >= author.top_role
		):
			raise CLIParseError("You can only reward roles below your own top role.", rewards_add_node)

		cog = LevelSettings(ctx.bot)
		await cog.add_role_reward(ctx.guild.id, lvl_int, target_role.id)

		return await ctx.send(content=f"```ansi\n[+] Added reward: @{target_role.name} at Level {lvl_int}\n```")

	rewards_add_node.callback = rewards_add

	rewards_rm_node = rewards_node.create_subcommand("remove", description="Remove a role reward for a level.")
	rewards_rm_node.add_argument("level", required=True, help="Level to remove role reward for")
	rewards_rm_node.add_argument("role", required=False, help="Optional specific role to remove")

	async def rewards_remove(ctx: Context, level: str | None = None, role: str | None = None, **kwargs: Any):
		assert ctx.guild is not None
		if not level:
			raise CLIParseError("Usage: `config level rewards remove <level> [role]`", rewards_rm_node)

		try:
			lvl_int = int(level)
		except ValueError:
			raise CLIParseError("Level must be a valid integer.", rewards_rm_node)

		target_role = resolve_role(ctx.guild, role) if role else None
		cog = LevelSettings(ctx.bot)
		await cog.remove_role_reward(ctx.guild.id, lvl_int, target_role.id if target_role else None)

		return await ctx.send(content=f"```ansi\n[-] Removed role reward(s) for Level {lvl_int}\n```")

	rewards_rm_node.callback = rewards_remove

	rewards_stack_node = rewards_node.create_subcommand(
		"stack", description="Set whether role rewards stack or replace previous rewards."
	)
	rewards_stack_node.add_argument("stack", required=True, help="`true` (stack rewards) or `false` (replace previous)")

	async def rewards_stack(ctx: Context, stack: str | None = None, **kwargs: Any):
		assert ctx.guild is not None
		if stack is None or stack.lower() not in {"true", "false", "yes", "no", "1", "0"}:
			raise CLIParseError("Please specify `true` (stack) or `false` (replace previous).", rewards_stack_node)

		is_stack = stack.lower() in {"true", "yes", "1"}
		cog = LevelSettings(ctx.bot)
		await cog.set_stack_roles(ctx.guild.id, is_stack)

		mode_str = (
			"Stackable (keep all previous unlocked roles)"
			if is_stack
			else "Replace previous (keep only highest unlocked role)"
		)
		return await ctx.send(content=f"```ansi\n[+] Role reward mode set to: {mode_str}\n```")

	rewards_stack_node.callback = rewards_stack

	rewards_list_node = rewards_node.create_subcommand("list", description="List all configured role rewards.")

	async def rewards_list(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		rewards = await LevelSettings(ctx.bot).get_role_rewards(ctx.guild.id)
		if not rewards:
			return await ctx.send(content="```ansi\n[!] No role rewards configured for this server.\n```")

		lines = ["[+] Level Role Rewards:"]
		for level, role_id in rewards:
			role_obj = ctx.guild.get_role(role_id)
			role_name = f"@{role_obj.name}" if role_obj else f"(Deleted role ID: {role_id})"
			lines.append(f"  Level {level}: {role_name}")
		return await ctx.send(content="```ansi\n" + "\n".join(lines) + "\n```")

	rewards_list_node.callback = rewards_list

	channel_node = level_node.create_subcommand("channel", description="Configure channel XP ignores and multipliers.")

	ch_ignore_node = channel_node.create_subcommand("ignore", description="Ignore a channel from earning XP.")
	ch_ignore_node.add_argument("channel", required=True, help="Target channel to ignore")

	async def channel_ignore(ctx: Context, channel: str | None = None, **kwargs: Any):
		assert ctx.guild is not None
		if not channel:
			raise CLIParseError("Usage: `config level channel ignore <channel>`", ch_ignore_node)
		target_channel = resolve_channel(ctx.guild, channel)
		if not target_channel:
			raise CLIParseError(f"Channel `{channel}` was not found.", ch_ignore_node)

		cog = LevelSettings(ctx.bot)
		await cog.set_channel_ignored(ctx.guild.id, target_channel.id, True)

		return await ctx.send(content=f"```ansi\n[-] Ignored channel #{target_channel.name} from earning XP\n```")

	ch_ignore_node.callback = channel_ignore

	ch_unignore_node = channel_node.create_subcommand("unignore", description="Allow a channel to earn XP again.")
	ch_unignore_node.add_argument("channel", required=True, help="Target channel to unignore")

	async def channel_unignore(ctx: Context, channel: str | None = None, **kwargs: Any):
		assert ctx.guild is not None
		if not channel:
			raise CLIParseError("Usage: `config level channel unignore <channel>`", ch_unignore_node)
		target_channel = resolve_channel(ctx.guild, channel)
		if not target_channel:
			raise CLIParseError(f"Channel `{channel}` was not found.", ch_unignore_node)

		cog = LevelSettings(ctx.bot)
		await cog.set_channel_ignored(ctx.guild.id, target_channel.id, False)

		return await ctx.send(content=f"```ansi\n[+] Unignored channel #{target_channel.name}\n```")

	ch_unignore_node.callback = channel_unignore

	ch_mult_node = channel_node.create_subcommand("multiplier", description="Set a custom XP multiplier for a channel.")
	ch_mult_node.add_argument("channel", required=True, help="Target channel")
	ch_mult_node.add_argument("multiplier", required=True, help="XP multiplier for this channel (e.g. 1.5, 2.0)")

	async def channel_multiplier(
		ctx: Context, channel: str | None = None, multiplier: str | None = None, **kwargs: Any
	):
		assert ctx.guild is not None
		if not channel or not multiplier:
			raise CLIParseError("Usage: `config level channel multiplier <channel> <multiplier>`", ch_mult_node)
		target_channel = resolve_channel(ctx.guild, channel)
		if not target_channel:
			raise CLIParseError(f"Channel `{channel}` was not found.", ch_mult_node)

		mult_val = _parse_number(multiplier, float, ch_mult_node, "Multiplier must be a positive number.")

		cog = LevelSettings(ctx.bot)
		await cog.set_channel_multiplier(ctx.guild.id, target_channel.id, mult_val)

		return await ctx.send(content=f"```ansi\n[+] XP multiplier in #{target_channel.name} set to {mult_val}x\n```")

	ch_mult_node.callback = channel_multiplier

	ch_list_node = channel_node.create_subcommand("list", description="List channel XP overrides.")

	async def channel_list(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		overrides = await LevelSettings(ctx.bot).overrides.get(ctx.guild.id)
		if not overrides.channels:
			return await ctx.send(content="```ansi\n[!] No channel overrides configured for this server.\n```")

		lines = ["[+] Channel Overrides:"]
		for channel_id, (multiplier, ignored) in overrides.channels.items():
			ch_obj = ctx.guild.get_channel_or_thread(channel_id)
			ch_name = f"#{ch_obj.name}" if ch_obj else f"(Unknown channel ID: {channel_id})"
			status_parts = []
			if ignored:
				status_parts.append("IGNORED")
			if multiplier != 1.0:
				status_parts.append(f"{multiplier}x multiplier")
			lines.append(f"  {ch_name}: {', '.join(status_parts) if status_parts else 'Normal'}")
		return await ctx.send(content="```ansi\n" + "\n".join(lines) + "\n```")

	ch_list_node.callback = channel_list

	role_node = level_node.create_subcommand("role", description="Configure role XP ignores and multipliers.")

	role_ignore_node = role_node.create_subcommand("ignore", description="Ignore members with a role from earning XP.")
	role_ignore_node.add_argument("role", required=True, help="Target role")

	async def role_ignore(ctx: Context, role: str | None = None, **kwargs: Any):
		assert ctx.guild is not None
		if not role:
			raise CLIParseError("Usage: `config level role ignore <role>`", role_ignore_node)
		target_role = resolve_role(ctx.guild, role)
		if not target_role:
			raise CLIParseError(f"Role `{role}` was not found.", role_ignore_node)

		cog = LevelSettings(ctx.bot)
		await cog.set_role_ignored(ctx.guild.id, target_role.id, True)

		return await ctx.send(content=f"```ansi\n[-] Ignored role @{target_role.name} from earning XP\n```")

	role_ignore_node.callback = role_ignore

	role_unignore_node = role_node.create_subcommand("unignore", description="Allow members with a role to earn XP.")
	role_unignore_node.add_argument("role", required=True, help="Target role")

	async def role_unignore(ctx: Context, role: str | None = None, **kwargs: Any):
		assert ctx.guild is not None
		if not role:
			raise CLIParseError("Usage: `config level role unignore <role>`", role_unignore_node)
		target_role = resolve_role(ctx.guild, role)
		if not target_role:
			raise CLIParseError(f"Role `{role}` was not found.", role_unignore_node)

		cog = LevelSettings(ctx.bot)
		await cog.set_role_ignored(ctx.guild.id, target_role.id, False)

		return await ctx.send(content=f"```ansi\n[+] Unignored role @{target_role.name}\n```")

	role_unignore_node.callback = role_unignore

	role_mult_node = role_node.create_subcommand("multiplier", description="Set a custom XP multiplier for a role.")
	role_mult_node.add_argument("role", required=True, help="Target role")
	role_mult_node.add_argument("multiplier", required=True, help="XP multiplier for this role (e.g. 1.5, 2.0)")

	async def role_multiplier(ctx: Context, role: str | None = None, multiplier: str | None = None, **kwargs: Any):
		assert ctx.guild is not None
		if not role or not multiplier:
			raise CLIParseError("Usage: `config level role multiplier <role> <multiplier>`", role_mult_node)
		target_role = resolve_role(ctx.guild, role)
		if not target_role:
			raise CLIParseError(f"Role `{role}` was not found.", role_mult_node)

		mult_val = _parse_number(multiplier, float, role_mult_node, "Multiplier must be a positive number.")

		cog = LevelSettings(ctx.bot)
		await cog.set_role_multiplier(ctx.guild.id, target_role.id, mult_val)

		return await ctx.send(content=f"```ansi\n[+] XP multiplier for @{target_role.name} set to {mult_val}x\n```")

	role_mult_node.callback = role_multiplier

	role_list_node = role_node.create_subcommand("list", description="List role XP overrides.")

	async def role_list(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		overrides = await LevelSettings(ctx.bot).overrides.get(ctx.guild.id)
		if not overrides.roles:
			return await ctx.send(content="```ansi\n[!] No role overrides configured for this server.\n```")

		lines = ["[+] Role Overrides:"]
		for role_id, (multiplier, ignored) in overrides.roles.items():
			role_obj = ctx.guild.get_role(role_id)
			role_name = f"@{role_obj.name}" if role_obj else f"(Unknown role ID: {role_id})"
			status_parts = []
			if ignored:
				status_parts.append("IGNORED")
			if multiplier != 1.0:
				status_parts.append(f"{multiplier}x multiplier")
			lines.append(f"  {role_name}: {', '.join(status_parts) if status_parts else 'Normal'}")
		return await ctx.send(content="```ansi\n" + "\n".join(lines) + "\n```")

	role_list_node.callback = role_list

	show_node = level_node.create_subcommand("show", description="Show full leveling configuration for this server.")

	async def level_show(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		cfg = await LevelSettings(ctx.bot).get_guild_config(ctx.guild.id)
		ch_obj = ctx.guild.get_channel(cfg.message_channel) if cfg.message_channel else None
		ch_str = f"#{ch_obj.name}" if ch_obj else "(None)"

		lines = [
			"=== Leveling System Configuration ===",
			f"Status:          {'Enabled' if cfg.is_on else 'Disabled'}",
			f"XP Range:        {cfg.min_xp} - {cfg.max_xp} XP",
			f"Global Mult:     {cfg.multiplier}x",
			f"Cooldown:        {cfg.cooldown}s",
			f"Level-up Mode:   {cfg.message_mode.value}",
			f"Target Channel:  {ch_str}",
			f"Message:         {cfg.levelup_message or '(Default: localized)'}",
			f"Role Stacking:   {'Enabled (stack)' if cfg.stack_roles else 'Disabled (replace previous)'}",
		]
		return await ctx.send(content="```ansi\n" + "\n".join(lines) + "\n```")

	show_node.callback = level_show

	return level_node
