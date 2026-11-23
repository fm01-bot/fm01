from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import aiohttp
import discord
from core.api import ApiError
from helpers.alert_providers import (
	SUPPORTED_PLATFORMS,
	AccountNotFoundError,
	AlertSourceError,
	FeedUnavailableError,
	ProviderNotConfiguredError,
	get_provider,
)
from helpers.cli_parser import CLINode, CLIParseError

from api import MAX_ALERTS, AlertCreate, ErrorCode

from .helpers import resolve_channel

if TYPE_CHECKING:
	from core import Context

logger = logging.getLogger(__name__)


def setup_alert_subcommands(parent_node: CLINode) -> CLINode:
	"""Registers alert configuration subcommands under the ?!config tree."""
	alert_node = parent_node.create_subcommand(
		"alert",
		description="Configure YouTube, Twitch, and TikTok upload and stream alerts.",
	)

	# 1. alert add
	add_node = alert_node.create_subcommand("add", description="Add an upload or stream alert.")
	add_node.add_argument("platform", help="Platform name: youtube, twitch, or tiktok")
	add_node.add_argument("account", help="Channel account name, handle, URL, or ID")
	add_node.add_argument("channel_pos", required=False, help="Target Discord channel mention or name")
	add_node.add_option("channel", "c", help="Target Discord channel")

	async def alert_add(
		ctx: Context,
		platform: str,
		account: str,
		channel: str | None = None,
		channel_pos: str | None = None,
		**kwargs: Any,
	):
		assert ctx.guild is not None
		plat = platform.lower().strip()
		if plat not in SUPPORTED_PLATFORMS:
			supported_str = ", ".join(SUPPORTED_PLATFORMS)
			raise CLIParseError(
				f"Unsupported platform `{platform}`. Supported platforms are: {supported_str}.",
				add_node,
			)

		provider = get_provider(plat)
		if not provider:
			raise CLIParseError(f"Provider for platform `{platform}` is not available.", add_node)

		# Check 5-alert total limit per server
		count = len(await ctx.bot.api.alerts.for_guild(ctx.guild.id))
		if count >= MAX_ALERTS:
			raise CLIParseError(
				"This server has reached the maximum limit of 5 alert subscriptions. "
				"Remove an existing alert using `?!config alert remove` before adding a new one.",
				add_node,
			)

		# Resolve target Discord channel
		ch_raw = channel or channel_pos
		target_channel: discord.abc.GuildChannel | discord.Thread | None = None
		if ch_raw:
			target_channel = resolve_channel(ctx.guild, ch_raw)
			if not target_channel or not isinstance(target_channel, discord.abc.Messageable):
				raise CLIParseError(
					f"Channel `{ch_raw}` was not found or is not a valid text channel.",
					add_node,
				)
		elif isinstance(ctx.channel, (discord.abc.GuildChannel, discord.Thread)):
			target_channel = ctx.channel
		else:
			raise CLIParseError("Please specify a target Discord channel for alerts.", add_node)

		# Resolve account handle/ID via provider
		alerts_cog: Any = ctx.bot.get_cog("Alerts")
		session: aiohttp.ClientSession
		if alerts_cog and hasattr(alerts_cog, "get_session"):
			session = await alerts_cog.get_session()
		else:
			session = aiohttp.ClientSession()

		try:
			account_id, account_name = await provider.resolve_channel(session, account, bot=ctx.bot)
		except ProviderNotConfiguredError as e:
			logger.warning(f"{provider.display_name} alerts are not configured: {e.reason}")
			raise CLIParseError(f"{provider.display_name} alerts are not configured on this bot.", add_node) from e
		except AccountNotFoundError as e:
			raise CLIParseError(f"No {provider.display_name} account named `{account}` was found.", add_node) from e
		except FeedUnavailableError as e:
			raise CLIParseError(
				f"Could not load the {provider.display_name} feed for `{account}` ({e.reason}). "
				"Check the account name, and that the bot's RSSHub instance is configured for this platform.",
				add_node,
			) from e
		except AlertSourceError as e:
			raise CLIParseError(
				f"Could not reach {provider.display_name} to verify `{account}` ({e.reason}). Try again later.",
				add_node,
			) from e
		finally:
			if not alerts_cog or not hasattr(alerts_cog, "get_session"):
				await session.close()

		# Add alert to database
		try:
			alert = await ctx.bot.api.alerts.add(
				ctx.guild.id,
				AlertCreate(
					platform=plat,
					channel_account=account,
					account_id=account_id,
					account_name=account_name,
					target_channel_id=target_channel.id,
				),
			)
		except ApiError as exc:
			if exc.code is not ErrorCode.ALERT_LIMIT:
				raise
			raise CLIParseError(
				"This server has reached the maximum limit of 5 alert subscriptions.", add_node
			) from exc
		alert_id = alert.id

		lines = [
			f"[+] Alert #{alert_id} successfully added ({plat})",
			f"Creator: {account_name} ({account_id})",
			f"Target: #{target_channel.name}",
		]
		return await ctx.send(content="```ansi\n" + "\n".join(lines) + "\n```")

	add_node.callback = alert_add

	# 2. alert remove
	remove_node = alert_node.create_subcommand("remove", description="Remove an alert subscription.")
	remove_node.add_argument("target", help="Numeric alert ID from list, or platform name (youtube, twitch, etc.)")
	remove_node.add_argument("account", required=False, help="Channel account name if platform was given")

	async def alert_remove(ctx: Context, target: str, account: str | None = None, **kwargs: Any):
		assert ctx.guild is not None
		target_clean = target.strip()

		# If target is numeric alert ID
		if target_clean.isdigit():
			alert_id = int(target_clean)
			removed = await ctx.bot.api.alerts.remove(ctx.guild.id, alert_id)

			if not removed:
				raise CLIParseError(f"Alert #{alert_id} was not found in this server.", remove_node)
			return await ctx.send(content=f"```ansi\n[-] Alert #{alert_id} removed\n```")

		# If target is platform
		plat = target_clean.lower()
		if plat in SUPPORTED_PLATFORMS:
			if not account:
				raise CLIParseError(
					f"Please provide the account name to remove: `?!config alert remove {plat} <account>`",
					remove_node,
				)
			del_count = await ctx.bot.api.alerts.remove_account(ctx.guild.id, plat, account.strip())

			if del_count == 0:
				raise CLIParseError(
					f"No alerts found for {plat} account `{account}` in this server.",
					remove_node,
				)
			return await ctx.send(
				content=f"```ansi\n[-] Removed {del_count} alert(s) for {plat} account {account}\n```"
			)

		raise CLIParseError(
			f"Invalid target `{target}`. Provide an alert ID (e.g. `1`) or platform name (e.g. `youtube <account>`).",
			remove_node,
		)

	remove_node.callback = alert_remove

	# 3. alert list
	list_node = alert_node.create_subcommand("list", description="List all configured alerts in this server.")

	async def alert_list(ctx: Context, **kwargs: Any):
		assert ctx.guild is not None
		rows = [dict(alert) for alert in await ctx.bot.api.alerts.for_guild(ctx.guild.id)]
		if not rows:
			return await ctx.send(
				content="```ansi\n[-] No media alerts configured for this server (Limit: 5).\nUse `?!config alert add <platform> <channel>` to add one.\n```"
			)

		lines = [f"[Configured Social Media Alerts ({len(rows)}/5)]"]
		for row in rows:
			status = "Active" if row["enabled"] else "Disabled"
			target_ch = ctx.guild.get_channel(int(row["target_channel_id"]))
			ch_name = f"#{target_ch.name}" if target_ch else str(row["target_channel_id"])
			creator = row["account_name"] or row["channel_account"]
			lines.append(f"#{row['id']} [{row['platform'].upper()}] {creator} -> {ch_name} [{status}]")
		return await ctx.send(content="```ansi\n" + "\n".join(lines) + "\n```")

	list_node.callback = alert_list

	# 4. alert enable
	enable_node = alert_node.create_subcommand("enable", description="Enable a media alert.")
	enable_node.add_argument("target", help="Numeric alert ID")

	async def alert_enable(ctx: Context, target: str, **kwargs: Any):
		assert ctx.guild is not None
		if not target.strip().isdigit():
			raise CLIParseError("Target must be a numeric alert ID.", enable_node)
		alert_id = int(target.strip())
		if not await ctx.bot.api.alerts.set_enabled(ctx.guild.id, alert_id, True):
			raise CLIParseError(f"Alert #{alert_id} was not found in this server.", enable_node)
		return await ctx.send(content=f"```ansi\n[+] Alert #{alert_id} enabled\n```")

	enable_node.callback = alert_enable

	# 5. alert disable
	disable_node = alert_node.create_subcommand("disable", description="Disable a media alert.")
	disable_node.add_argument("target", help="Numeric alert ID")

	async def alert_disable(ctx: Context, target: str, **kwargs: Any):
		assert ctx.guild is not None
		if not target.strip().isdigit():
			raise CLIParseError("Target must be a numeric alert ID.", disable_node)
		alert_id = int(target.strip())
		if not await ctx.bot.api.alerts.set_enabled(ctx.guild.id, alert_id, False):
			raise CLIParseError(f"Alert #{alert_id} was not found in this server.", disable_node)
		return await ctx.send(content=f"```ansi\n[-] Alert #{alert_id} disabled\n```")

	disable_node.callback = alert_disable

	return alert_node
