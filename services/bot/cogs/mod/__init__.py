from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from copy import deepcopy
from typing import Literal

import discord
from args import TextChannel
from cogs.mod.cases import (
	Ban,
	Case,
	CaseExpirationManager,
	CaseStatus,
	CaseStore,
	CaseType,
	Kick,
	Mute,
	Retention,
	Softban,
	Warn,
	retention_setting,
)
from core import Bot, Context
from core.hybrid import command, group
from discord import app_commands
from discord.ext import commands, localization
from helpers import custom_response, seconds_to_text, text_to_seconds
from helpers.pagination import PaginationView
from helpers.permissions import require_channel_permissions
from helpers.regex import URL_REGEX

__all__ = (
	"Ban",
	"Case",
	"CaseExpirationManager",
	"CaseStore",
	"CaseType",
	"Cases",
	"Kick",
	"Moderation",
	"Mute",
	"Softban",
	"Warn",
)

logger = logging.getLogger(__name__)


type PurgeFilter = Literal["bots", "humans", "links", "attachments", "embeds"]

# Discord only bulk-deletes messages younger than 14 days; the margin keeps a message from ageing past it mid-purge.
BULK_DELETE_MAX_AGE = datetime.timedelta(days=14) - datetime.timedelta(minutes=5)
# Discord bulk-deletes at most 100 messages per request.
BULK_DELETE_CHUNK = 100
# How far back `purge` looks for matching messages before giving up.
PURGE_SCAN_LIMIT = 2000


def _purge_check(
	user: discord.abc.Snowflake | None, filter: PurgeFilter | None, contains: str | None
) -> Callable[[discord.Message], bool]:
	"""Build the predicate deciding which scanned messages `purge` deletes. Pinned messages are always kept.

	Args:
		user: Only delete this user's messages.
		filter: Only delete messages of this kind.
		contains: Only delete messages whose content contains this text, ignoring case.
	"""
	needle = contains.casefold() if contains else None

	def check(message: discord.Message) -> bool:
		if message.pinned:
			return False
		if user is not None and message.author.id != user.id:
			return False
		if needle is not None and needle not in message.content.casefold():
			return False
		match filter:
			case "bots":
				return message.author.bot
			case "humans":
				return not message.author.bot
			case "links":
				return URL_REGEX.search(message.content) is not None
			case "attachments":
				return bool(message.attachments)
			case "embeds":
				# Components V2 messages (containers, sections) can't carry embeds; they are what replaces them.
				return bool(message.embeds) or message.flags.components_v2
		return True

	return check


def _target_error(ctx: Context, member: discord.Member, action: str, *, bot_acts: bool = True) -> str | None:
	"""Check whether the author may moderate a member, so nothing is recorded or DMed for an action that can't happen.

	Args:
		ctx: The command's context.
		member: The member to moderate.
		action: The command's localization key under ``mod``.
		bot_acts: Whether the bot changes the member (all but warnings), so it must outrank them too.

	Returns:
		The localization key of the error, or ``None`` if the author may go ahead. Only the owner may moderate members
		whose top role isn't below the author's, and the owner can't be moderated.
	"""
	guild = member.guild
	if member == ctx.me:
		return f"mod.{action}.errors.bot"
	author = ctx.author
	if member.id == guild.owner_id or (
		author.id != guild.owner_id and isinstance(author, discord.Member) and member.top_role >= author.top_role
	):
		return f"mod.{action}.errors.hierarchy"
	if bot_acts and member.top_role >= guild.me.top_role:
		return f"mod.{action}.errors.bot_hierarchy"
	return None


def _replied_content(ctx: Context) -> str | None:
	"""The content of the message the command replies to, or ``None`` if it replies to none (or it was deleted)."""
	resolved = ctx.message.reference.resolved if ctx.message.reference else None
	return resolved.content if isinstance(resolved, discord.Message) else None


async def _guild_member(guild: discord.Guild, user_id: int) -> discord.Member | None:
	"""Find a member from the cache, or from Discord: members aren't chunked at startup, so most aren't cached.

	Returns:
		The member, or ``None`` if the user isn't in the guild.
	"""
	if member := guild.get_member(user_id):
		return member
	try:
		return await guild.fetch_member(user_id)
	except discord.NotFound:
		return None


_CASE_PERMISSIONS: dict[CaseType, str] = {
	CaseType.BAN: "ban_members",
	CaseType.SOFTBAN: "ban_members",
	CaseType.KICK: "kick_members",
}
"""The permission, besides Timeout Members, needed to remove, delete or edit a case of a type: closing a ban unbans."""


def _require_case_permission(ctx: Context, case: Case) -> None:
	"""Check that the author holds the permission the case's type needs.

	Raises:
		commands.MissingPermissions: They don't.
	"""
	permission = _CASE_PERMISSIONS.get(case.type)
	author = ctx.author
	if permission and not (isinstance(author, discord.Member) and getattr(author.guild_permissions, permission)):
		raise commands.MissingPermissions([permission])


def _parse_case_id(case_id: str) -> int:
	try:
		return int(case_id)
	except ValueError:
		raise commands.BadArgument("case_id")


@commands.guild_only()
@app_commands.guild_only()
class Moderation(commands.GroupCog, name="Moderation", group_name="mod"):
	def __init__(self, client: Bot, cases: CaseStore):
		self.client = client
		self.custom_response = custom_response.CustomResponse(client, "mod")
		self.cases = cases

	async def cog_load(self):
		self.cases.start()

	async def cog_unload(self):
		self.cases.stop()

	@command(user=False, permissions=["moderate_members"])
	async def warn(
		self, ctx: Context, member: discord.Member, expires: str | None = None, *, reason: str | None = None
	):
		assert ctx.guild is not None
		assert isinstance(ctx.author, discord.Member)
		try:
			member = await commands.MemberConverter().convert(
				ctx, str(member.name) if isinstance(member, discord.Member) else member
			)
		except commands.MemberNotFound:
			if not ctx.message.reference:
				reason = " ".join(
					[str(member), expires or "", reason or ""] if reason else [str(member), expires or ""]
				)
			else:
				raise commands.MemberNotFound(str(member))
		try:
			expiry_date = (
				datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(seconds=text_to_seconds(expires))
				if expires
				else None
			)
		except (ValueError, TypeError):
			reason = " ".join([expires or "", reason or ""] if reason else [expires or ""])
			expiry_date = None

		if error := _target_error(ctx, member, "warn", bot_acts=False):
			await ctx.send(error)
			return

		warn = Warn(
			Case.generate_id(ctx.message),
			self.client,
			ctx.guild,
			member,
			ctx.author,
			reason,
			expiry_date,
			_replied_content(ctx),
		)
		await self.cases.open(warn)

		await ctx.send("mod.warn.response", warn=warn)

	@command(user=False, permissions=["moderate_members"], aliases=["timeout"])
	@commands.bot_has_permissions(moderate_members=True)
	async def mute(self, ctx: Context, member: discord.Member, expires: str, *, reason: str | None = None):
		assert ctx.guild is not None
		try:
			seconds = text_to_seconds(expires)
		except (ValueError, TypeError):
			raise commands.BadArgument
		max_timeout = 28 * 24 * 60 * 60  # 28 days
		if seconds <= 0 or seconds > max_timeout:
			raise commands.BadArgument("Mute duration must be between 1 second and 28 days.")
		expiry_date = datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(seconds=seconds)
		if error := _target_error(ctx, member, "mute"):
			await ctx.send(error)
			return
		if member.guild_permissions.administrator:
			await ctx.send("mod.mute.errors.administrator")
			return
		mute = Mute(
			Case.generate_id(ctx.message),
			self.client,
			ctx.guild,
			member,
			ctx.author,
			expiry_date,
			reason,
			_replied_content(ctx),
		)
		await self.cases.open(mute)

		await ctx.send("mod.mute.response", mute=mute)

	@command(user=False, permissions=["moderate_members"])
	async def unmute(self, ctx: Context, member: discord.Member):
		assert ctx.guild is not None
		was_timed_out = member.timed_out_until is not None
		cases = await self.cases.active(ctx.guild, member, CaseType.MUTE)
		for case in cases:
			await self.cases.close(case)  # Mute.before_deletion lifts the timeout

		if cases and was_timed_out:
			await ctx.send("mod.unmute.response", member=member, user=member)
		elif cases:
			await ctx.send("mod.unmute.timeout_already_removed", member=member, user=member)
		elif was_timed_out:
			reason = await self.custom_response("mod.unmute.reason", ctx, moderator=ctx.author)
			await member.edit(timed_out_until=None, reason=reason if isinstance(reason, str) else None)
			await ctx.send("mod.unmute.no_case", member=member, user=member)
		else:
			await ctx.send("mod.unmute.errors.not_muted", member=member, user=member)

	@command(user=False, permissions=["kick_members"])
	@commands.bot_has_permissions(kick_members=True)
	async def kick(self, ctx: Context, member: discord.Member, *, reason: str | None = None):
		assert ctx.guild is not None
		if error := _target_error(ctx, member, "kick"):
			await ctx.send(error)
			return
		kick = Kick(
			Case.generate_id(ctx.message),
			self.client,
			ctx.guild,
			member,
			ctx.author,
			reason,
			_replied_content(ctx),
		)
		await self.cases.open(kick)

		await ctx.send("mod.kick.response", kick=kick)

	@command(user=False, permissions=["ban_members"])
	@commands.bot_has_permissions(ban_members=True)
	async def ban(self, ctx: Context, user: discord.User, expires: str | None = None, *, reason: str | None = None):
		assert ctx.guild is not None
		try:
			expiry_date = (
				datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(seconds=text_to_seconds(expires))
				if expires
				else None
			)
		except (ValueError, TypeError):
			if ctx.interaction:
				raise commands.BadArgument
			reason = f"{expires} {reason}" if reason else expires
			expiry_date = None
		if user == ctx.me:
			await ctx.send("mod.ban.errors.bot")
			return
		if (member := await _guild_member(ctx.guild, user.id)) and (error := _target_error(ctx, member, "ban")):
			await ctx.send(error)
			return
		ban = Ban(
			Case.generate_id(ctx.message),
			self.client,
			ctx.guild,
			user,
			ctx.author,
			reason,
			expiry_date,
			_replied_content(ctx),
		)
		await self.cases.open(ban)

		await ctx.send("mod.ban.response", ban=ban)

	@command(user=False, permissions=["ban_members"])
	async def unban(self, ctx: Context, user: discord.User):
		assert ctx.guild is not None
		cases = await self.cases.active(ctx.guild, user, CaseType.BAN)
		for case in cases:
			await self.cases.close(case)  # Ban.before_deletion lifts the ban
		if not cases:
			try:
				reason = await self.custom_response("mod.unban.reason", ctx, moderator=ctx.author)
				await ctx.guild.unban(user, reason=reason if isinstance(reason, str) else None)
			except discord.NotFound:
				pass

		await ctx.send("mod.unban.response", user=user)

	@command(user=False, permissions=["manage_channels"], l10n_key="sm", name="slowmode", aliases=["sm"])
	async def slowmode(self, ctx: Context, duration: str | None = None, channel: discord.TextChannel | None = None):
		target_channel = channel or (ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None)
		if not target_channel:
			raise commands.BadArgument("Channel is not a text channel")
		require_channel_permissions(ctx.author, target_channel, "manage_channels")
		if not duration:
			await ctx.send("mod.slowmode.current_slowmode", channel=TextChannel.from_channel(target_channel))
			return
		if duration.lower() == "off":
			duration = "0s"
		max_slowmode_delay = 60 * 60 * 6  # 6 hours
		slowmode_before = target_channel.slowmode_delay
		try:
			seconds = text_to_seconds(duration, target_channel.slowmode_delay)
		except ValueError:
			raise commands.BadArgument
		seconds = max(
			0, min(seconds, max_slowmode_delay)
		)  # clamp between 0 and 6hrs (silently, but whatever, its easier for the user)
		reason: str = await self.custom_response("mod.slowmode.reason", ctx, moderator=ctx.author)
		await target_channel.edit(slowmode_delay=seconds, reason=reason)
		await ctx.send(
			"mod.slowmode.response",
			channel=target_channel,
			time_before=seconds_to_text(slowmode_before),
			time=seconds_to_text(seconds),
		)

	@command(user=False, permissions=["manage_messages"])
	@commands.bot_has_permissions(manage_messages=True, read_message_history=True)
	@app_commands.choices(
		filter=[
			app_commands.Choice(name="purge-args-filter-bots", value="bots"),
			app_commands.Choice(name="purge-args-filter-humans", value="humans"),
			app_commands.Choice(name="purge-args-filter-links", value="links"),
			app_commands.Choice(name="purge-args-filter-attachments", value="attachments"),
			app_commands.Choice(name="purge-args-filter-embeds", value="embeds"),
		]
	)
	async def purge(
		self,
		ctx: Context,
		amount: commands.Range[int, 1, 1000],
		user: discord.User | None = None,
		filter: PurgeFilter | None = None,
		*,
		contains: str | None = None,
	):
		channel = ctx.channel
		if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel, discord.StageChannel)):
			raise commands.BadArgument("Channel can't be purged")
		await ctx.defer()
		# Scan from just before the command, so neither the invoking message nor the deferred response is counted.
		before = discord.Object(ctx.interaction.id) if ctx.interaction else ctx.message
		reason: str = await self.custom_response("mod.purge.reason", ctx, moderator=ctx.author)
		check = _purge_check(user, filter, contains)
		deleted: list[discord.Message] = []
		async for message in channel.history(
			limit=PURGE_SCAN_LIMIT,
			before=before,
			after=discord.utils.utcnow() - BULK_DELETE_MAX_AGE,
			oldest_first=False,
		):
			if check(message):
				deleted.append(message)
				if len(deleted) == amount:
					break
		for start in range(0, len(deleted), BULK_DELETE_CHUNK):
			try:
				await channel.delete_messages(deleted[start : start + BULK_DELETE_CHUNK], reason=reason)
			except discord.NotFound:  # a single message deleted by someone else in the meantime
				pass
		if not ctx.interaction:
			try:
				await ctx.message.delete()
			except discord.NotFound:
				pass
		if not deleted:
			await ctx.send("mod.purge.none", channel=channel)
			return
		await ctx.send("mod.purge.response", channel=channel, count=len(deleted))


class Cases(commands.Cog, name="Cases"):
	def __init__(self, client: Bot, cases: CaseStore) -> None:
		self.client = client
		self.custom_response = custom_response.CustomResponse(client, "mod")
		self.cases = cases

	@group(user=False, l10n_key="caseinfo", name="case", aliases=["caseinfo"])
	async def case(self, ctx: Context, case_id: str):
		assert ctx.guild is not None
		assert isinstance(ctx.author, discord.Member)
		try:
			fetched_case_id = int(case_id)
		except ValueError:
			raise commands.BadArgument

		case = await self.cases.get(ctx.guild, fetched_case_id)
		if case is None:
			await ctx.send("mod.info.errors.not_found", case_id=fetched_case_id)
			return

		if case._user.id != ctx.author.id and not ctx.author.guild_permissions.moderate_members:
			raise commands.MissingPermissions(["moderate_members"])

		await ctx.send("mod.info.response", case=case)

	@case.command(
		user=False,
		permissions=["moderate_members"],
		l10n_key="casedel",
		full_aliases=["casedel", "delcase", "deletecase", "casedelete", "cd"],
	)
	async def delete(self, ctx: Context, case_id: str):
		assert ctx.guild is not None
		fetched_case_id = _parse_case_id(case_id)
		case = await self.cases.get(ctx.guild, fetched_case_id)
		if case is None:
			await ctx.send("mod.delete.errors.not_found", case_id=fetched_case_id)
			return
		_require_case_permission(ctx, case)

		await self.cases.delete(case)
		await ctx.send("mod.delete.response", case=case)

	@case.command(
		user=False,
		permissions=["moderate_members"],
		l10n_key="caserem",
		full_aliases=["caserem", "remcase", "removecase", "caseremove", "cr"],
	)
	async def remove(self, ctx: Context, case_id: str):
		assert ctx.guild is not None
		fetched_case_id = _parse_case_id(case_id)
		case = await self.cases.get(ctx.guild, fetched_case_id)
		if case is None:
			await ctx.send("mod.remove.errors.not_found", case_id=fetched_case_id)
			return
		_require_case_permission(ctx, case)

		outcome = await self.cases.close(case)
		await ctx.send("mod.delete.response" if outcome == "deleted" else "mod.remove.response", case=case)

	@case.command(
		user=False,
		permissions=["moderate_members"],
		l10n_key="caseedit",
		full_aliases=["caseedit", "editcase", "casemod", "modcase", "ce"],
	)
	@app_commands.choices(
		value=[
			app_commands.Choice(name="caseedit-args-value-expires", value="expires"),
			app_commands.Choice(name="caseedit-args-value-reason", value="reason"),
			app_commands.Choice(name="caseedit-args-value-message", value="message"),
		]
	)
	async def edit(self, ctx: Context, case_id: str, value: Literal["expires", "reason", "message"], *, new_value: str):
		assert ctx.guild is not None
		fetched_case_id = _parse_case_id(case_id)
		case = await self.cases.get(ctx.guild, fetched_case_id)
		if case is None:
			await ctx.send("mod.edit.errors.not_found", case_id=fetched_case_id)
			return
		_require_case_permission(ctx, case)

		if value == "expires":
			try:
				expires = datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(
					seconds=text_to_seconds(new_value)
				)
			except (ValueError, TypeError):
				await ctx.send("mod.edit.errors.invalid_time", case_id=fetched_case_id)
				return
			await self.cases.edit(case, expires=expires)
		elif value == "reason":
			await self.cases.edit(case, reason=new_value)
		else:
			await self.cases.edit(case, message=new_value)

		await ctx.send("mod.edit.response", case=case)

	@case.command(user=False, l10n_key="caselist", full_aliases=["cl", "caselist", "cases", "listcase", "listcases"])
	@app_commands.choices(
		filter=[
			app_commands.Choice(name="caselist-args-filter-active", value="active"),
			app_commands.Choice(name="caselist-args-filter-expired", value="expired"),
			app_commands.Choice(name="caselist-args-filter-all", value="all"),
		]
	)
	async def list(
		self,
		ctx: Context,
		user: discord.Member | None = None,
		filter: Literal["active", "expired", "all"] | None = None,
	):
		assert ctx.guild is not None
		assert isinstance(ctx.author, discord.Member)
		target_user: discord.Member | discord.User = user or ctx.author

		is_moderator = ctx.author.guild_permissions.moderate_members
		if target_user.id != ctx.author.id and not is_moderator:
			raise commands.MissingPermissions(["moderate_members"])

		effective_filter: CaseStatus = filter or ("all" if is_moderator else "active")
		if effective_filter not in ("active", "expired", "all"):
			raise commands.BadArgument("Filter must be 'active', 'expired', or 'all'.")

		cases = await self.cases.for_user(ctx.guild, target_user, effective_filter)

		pages = await self.custom_response.get_list(
			"mod.list.response", ctx, [{"case": case} for case in cases], page_size=5, cases=cases
		)
		if len(pages) == 1:
			await ctx.send(**pages[0])
			return
		view = PaginationView([page["embeds"][0] for page in pages], author_id=ctx.author.id)
		view.message = await ctx.send(embed=pages[0]["embeds"][0], view=view)


async def setup(client: Bot):
	cases = CaseStore(client)
	await client.add_cog(Moderation(client, cases))
	await client.add_cog(Cases(client, cases))
