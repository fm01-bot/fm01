from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
from core.api import ApiError, ApiUnavailable
from helpers.cli_parser import CLINode, CLIParseError

from api import MAX_STARBOARDS, ErrorCode, Starboard, StarboardUpdate

from .helpers import resolve_channel

if TYPE_CHECKING:
	from cogs.starboard import Starboards
	from core import Context

_ERRORS = {
	ErrorCode.STARBOARD_LIMIT: f"A server can have at most {MAX_STARBOARDS} starboards.",
	ErrorCode.STARBOARD_NAME_TAKEN: "Another starboard already has that name.",
	ErrorCode.STARBOARD_TIER_TAKEN: "Another starboard already uses that emoji with that threshold.",
	ErrorCode.NOT_FOUND: "There is no starboard with that name.",
}


def setup_starboard_subcommands(parent_node: CLINode) -> CLINode:
	"""Set up CLI commands for starboards."""
	node = parent_node.create_subcommand(
		"starboard", description="Configure starboards, channels that repost messages with enough reactions."
	)

	def cog(ctx: Context) -> Starboards:
		from cogs.starboard import Starboards

		found = ctx.bot.get_cog("Starboard")
		if not isinstance(found, Starboards):
			raise CLIParseError("The starboard module is not loaded.", node)
		return found

	def board_channel(ctx: Context, raw: str, at: CLINode) -> discord.TextChannel:
		assert ctx.guild is not None
		target = resolve_channel(ctx.guild, raw)
		if not isinstance(target, discord.TextChannel) or target.is_news():
			raise CLIParseError(f"Channel `{raw}` was not found or is not a text channel.", at)
		from cogs.starboard import missing_permissions

		if missing := missing_permissions(target):
			raise CLIParseError(f"I need these permissions in #{target.name}: {', '.join(missing)}", at)
		return target

	def emoji(ctx: Context, raw: str, at: CLINode) -> str:
		assert ctx.guild is not None
		parsed = discord.PartialEmoji.from_str(raw.strip())
		if parsed.id is None:
			return parsed.name
		if ctx.guild.get_emoji(parsed.id) is None:
			raise CLIParseError(f"`{raw}` is not an emoji of this server.", at)
		return str(parsed.id)

	def channel_list(ctx: Context, raw: str, at: CLINode) -> list[int]:
		if raw.strip().lower() in ("", "none"):
			return []
		ids = []
		for part in raw.replace(",", " ").split():
			target = resolve_channel(ctx.guild, part)
			if target is None:
				raise CLIParseError(f"Channel `{part}` was not found.", at)
			ids.append(target.id)
		return ids

	def max_age(raw: str, at: CLINode) -> int | None:
		if raw.strip().lower() in ("off", "none", "0"):
			return None
		if not raw.isdigit():
			raise CLIParseError("The maximum age is a number of days, or `off`.", at)
		return int(raw)

	async def write(ctx: Context, at: CLINode, operation: Any) -> Any:
		assert ctx.guild is not None
		try:
			result = await operation
		except ApiError as exc:
			raise CLIParseError(_ERRORS.get(exc.code, exc.message), at) from exc
		except ValueError as exc:
			raise CLIParseError(str(exc), at) from exc
		except ApiUnavailable as exc:
			raise CLIParseError("The starboard service is unavailable. Try again later.", at) from exc
		await cog(ctx).reload(ctx.guild.id)
		return result

	def describe(ctx: Context, board: Starboard) -> str:
		assert ctx.guild is not None
		channel = ctx.guild.get_channel(board.channel_id)
		where = f"#{channel.name}" if channel else str(board.channel_id)
		shown = board.emoji
		if board.emoji.isdigit():
			found = ctx.guild.get_emoji(int(board.emoji))
			shown = f":{found.name}:" if found else board.emoji
		state = "on" if board.enabled else "off"
		names = []
		for channel_id in board.channel_ids:
			listed = ctx.guild.get_channel_or_thread(channel_id)
			names.append(f"#{listed.name}" if listed else str(channel_id))
		filtered = f"{board.channel_mode}: {', '.join(names) or 'none'}"
		age = f", max age {board.max_age_days}d" if board.max_age_days else ""
		return f"{board.name} [{state}] {shown} x{board.threshold} -> {where} ({filtered}{age})"

	async def status(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		boards = await cog(ctx).setting.get(ctx.guild.id)
		lines = [describe(ctx, board) for board in boards] or ["No starboards."]
		return await ctx.send(content="```ansi\n" + "\n".join(lines) + "\n```")

	node.callback = status

	create_node = node.create_subcommand("create", description="Add a starboard.")
	create_node.add_argument("name", help="Name (lowercase letters, digits, - and _)")
	create_node.add_argument("channel", help="Channel to post in (e.g. #starboard)")
	create_node.add_option("emoji", "e", help="Emoji (default ⭐)")
	create_node.add_option("threshold", "t", type=int, help="Reactions needed (default 3)")
	create_node.add_option("max-age", "a", help="Ignore messages older than this many days")

	async def create(ctx: Context, name: str, channel: str, threshold: int | None = None, **kwargs: Any):
		assert ctx.guild is not None
		fields: dict[str, Any] = {"name": name.lower(), "channel_id": board_channel(ctx, channel, create_node).id}
		if kwargs.get("emoji"):
			fields["emoji"] = emoji(ctx, kwargs["emoji"], create_node)
		if threshold is not None:
			fields["threshold"] = threshold
		if kwargs.get("max_age"):
			fields["max_age_days"] = max_age(kwargs["max_age"], create_node)
		try:
			board = Starboard(**fields)
		except ValueError as exc:
			raise CLIParseError(f"Invalid starboard: {exc}", create_node) from exc
		board = await write(ctx, create_node, ctx.bot.api.starboard.create(ctx.guild.id, board))
		return await ctx.send(content=f"```ansi\n[+] {describe(ctx, board)}\n```")

	create_node.callback = create

	edit_node = node.create_subcommand(
		"edit", description="Change a starboard. Existing posts follow at their next star."
	)
	edit_node.add_argument("name", help="The starboard to change")
	edit_node.add_option("rename", "r", help="New name")
	edit_node.add_option("channel", "c", help="Channel to post in")
	edit_node.add_option("emoji", "e", help="Emoji")
	edit_node.add_option("threshold", "t", type=int, help="Reactions needed")
	edit_node.add_option("enabled", help="on or off")
	edit_node.add_option("mode", "m", help="blocklist (watch all but --channels) or allowlist (only --channels)")
	edit_node.add_option("channels", help='Channels for the mode, e.g. "#a #b", or none')
	edit_node.add_option("max-age", "a", help="Ignore messages older than this many days, or off")

	async def edit(ctx: Context, name: str, **kwargs: Any):
		assert ctx.guild is not None
		fields: dict[str, Any] = {}
		if kwargs.get("rename"):
			fields["name"] = kwargs["rename"].lower()
		if kwargs.get("channel"):
			fields["channel_id"] = board_channel(ctx, kwargs["channel"], edit_node).id
		if kwargs.get("emoji"):
			fields["emoji"] = emoji(ctx, kwargs["emoji"], edit_node)
		if kwargs.get("threshold") is not None:
			fields["threshold"] = kwargs["threshold"]
		if kwargs.get("enabled"):
			if kwargs["enabled"].lower() not in ("on", "off"):
				raise CLIParseError("--enabled is `on` or `off`.", edit_node)
			fields["enabled"] = kwargs["enabled"].lower() == "on"
		if kwargs.get("mode"):
			fields["channel_mode"] = kwargs["mode"].lower()
		if kwargs.get("channels") is not None:
			fields["channel_ids"] = channel_list(ctx, kwargs["channels"], edit_node)
		if kwargs.get("max_age"):
			fields["max_age_days"] = max_age(kwargs["max_age"], edit_node)
		if not fields:
			raise CLIParseError("Nothing to change.", edit_node)
		try:
			changes = StarboardUpdate(**fields)
		except ValueError as exc:
			raise CLIParseError(f"Invalid change: {exc}", edit_node) from exc
		board = await write(ctx, edit_node, ctx.bot.api.starboard.update(ctx.guild.id, name.lower(), changes))
		return await ctx.send(content=f"```ansi\n[+] {describe(ctx, board)}\n```")

	edit_node.callback = edit

	delete_node = node.create_subcommand("delete", description="Remove a starboard. Its posts stay in the channel.")
	delete_node.add_argument("name", help="The starboard to remove")

	async def delete(ctx: Context, name: str, **kwargs: Any):
		assert ctx.guild is not None
		await write(ctx, delete_node, ctx.bot.api.starboard.delete(ctx.guild.id, name.lower()))
		return await ctx.send(content=f"```ansi\n[-] Starboard {name.lower()} removed\n```")

	delete_node.callback = delete
	return node
