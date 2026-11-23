"""The bear trap: a honeypot channel. Anyone who posts in it is soft-banned and told their account was likely hacked.

The trap's channel, its message and its kick count live behind the API (`BearTrapApi`) as the ``bear_trap`` guild
setting. Whoever changes the channel (``?!config beartrap`` or the dashboard), the instance that owns the guild's shard
reconciles the trap message: posts it, moves it, or deletes it.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from collections import defaultdict
from collections.abc import Awaitable, Mapping
from typing import Any

import discord
from cogs.mod.cases import Case, CaseStore, Softban
from core import Bot
from core.api import ApiClient, ApiUnavailable
from core.context import VALID_SEND_KWARGS
from core.settings import GuildSetting, GuildSettings
from discord.ext import commands
from helpers.custom_response import CustomResponse
from helpers.scheduler import is_guild_on_shard

from api import BEAR_TRAP_SETTING, BearTrapState

__all__ = (
	"OPTIONAL_PERMISSIONS",
	"REQUIRED_PERMISSIONS",
	"BearTrap",
	"BearTrapSoftban",
	"bear_trap_setting",
	"is_exempt",
	"missing_permissions",
	"needs_reconcile",
)

logger = logging.getLogger(__name__)

COUNTER_DELAY = 3.0
"""Seconds to wait before editing the counter, so a raid edits the message once instead of once per kick."""
INVITE_MAX_AGE = int(datetime.timedelta(days=7).total_seconds())

REQUIRED_PERMISSIONS = ("view_channel", "send_messages", "read_message_history", "manage_messages", "ban_members")
"""Permissions the trap can't work without: post and find its message, delete messages, soft-ban."""
OPTIONAL_PERMISSIONS = ("create_instant_invite",)
"""Without these the DM goes out without an invite."""

TRAPPED_MESSAGE_TYPES = (discord.MessageType.default, discord.MessageType.reply)
"""Messages a member wrote. Excludes system messages such as "X joined", which name the member as the author."""


def bear_trap_setting(settings: GuildSettings, api: ApiClient, bot: Bot) -> GuildSetting[BearTrapState]:
	"""Register the bear trap setting, stored behind the API and preloaded so ``on_message`` can read it synchronously.

	Changes reach the loaded `BearTrap` cog, which reconciles the trap message. The hook looks the cog up on each
	change, so it keeps working after the cog is reloaded.

	Args:
		settings: The registry to add it to.
		api: The API client it loads and saves through.
		bot: The bot, to find the cog on.

	Returns:
		The setting. `GuildSetting.set` stores only the channel.
	"""

	async def save(guild_id: int, value: BearTrapState) -> None:
		await api.bear_trap.set_channel(guild_id, value.channel_id)

	def on_change(guild_id: int, value: BearTrapState | None) -> None:
		cog = bot.get_cog("BearTrap")
		if isinstance(cog, BearTrap) and value is not None and needs_reconcile(value):
			cog.schedule_reconcile(guild_id)

	return settings.add_remote(
		BEAR_TRAP_SETTING, api.bear_trap.get, save, load_all=api.bear_trap.all, on_change=on_change
	)


def needs_reconcile(trap: BearTrapState) -> bool:
	"""Check whether the trap message doesn't match the trap's channel.

	Args:
		trap: The trap.

	Returns:
		Whether a message has to be posted (trap on, no message) or deleted (message outside the trap's channel).
	"""
	if trap.message_id is not None and trap.message_channel_id != trap.channel_id:
		return True
	return trap.channel_id is not None and trap.message_id is None


def is_exempt(member: discord.Member) -> bool:
	"""Check whether a member may post in the trap channel without being soft-banned.

	Args:
		member: The member who posted.

	Returns:
		Whether the member is a bot, the owner, a manager (Administrator or Manage Server), or someone the bot can't
		ban because their top role isn't below its own.
	"""
	guild = member.guild
	if member.bot or member.id == guild.owner_id:
		return True
	permissions = member.guild_permissions
	if permissions.administrator or permissions.manage_guild:
		return True
	return member.top_role >= guild.me.top_role


def missing_permissions(channel: discord.TextChannel) -> tuple[list[str], list[str]]:
	"""List the permissions the bot lacks to run a trap in a channel.

	Args:
		channel: The trap channel.

	Returns:
		The missing `REQUIRED_PERMISSIONS` and the missing `OPTIONAL_PERMISSIONS`.
	"""
	permissions = channel.permissions_for(channel.guild.me)
	required = [name for name in REQUIRED_PERMISSIONS if not getattr(permissions, name)]
	optional = [name for name in OPTIONAL_PERMISSIONS if not getattr(permissions, name)]
	return required, optional


def _send_kwargs(payload: Any) -> dict[str, Any]:
	if isinstance(payload, dict):
		return {k: v for k, v in payload.items() if k in VALID_SEND_KWARGS}
	return {"content": str(payload)}


def _stop_view(kwargs: Mapping[str, Any]) -> None:
	# The counter button is disabled and never sends interactions, so the stored view would only leak memory.
	view = kwargs.get("view")
	if isinstance(view, (discord.ui.View, discord.ui.LayoutView)):
		view.stop()


class BearTrapSoftban(Softban):
	"""The softban the trap opens: it DMs the bear trap notice, with an invite back, instead of the softban notice."""

	audit_reason_key = "bear_trap.reason"

	def __init__(self, *args: Any, invite: str | None = None, **kwargs: Any) -> None:
		super().__init__(*args, **kwargs)
		self.invite = invite

	async def before_creation(self) -> None:
		"""DMs the user to secure their account, with the invite if there is one."""
		await self._notify("bear_trap.notify", softban=self, invite=self.invite)


class BearTrap(commands.Cog, name="BearTrap"):
	def __init__(self, bot: Bot) -> None:
		self.bot = bot
		self.setting = bear_trap_setting(bot.settings, bot.api, bot)
		self.cases = CaseStore(bot)
		self.responses = CustomResponse(bot, "bear_trap")
		self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
		self._catching: set[tuple[int, int]] = set()
		self._counter_updates: set[int] = set()
		self._background: set[asyncio.Task[Any]] = set()

	async def cog_load(self) -> None:
		# The setting may have been preloaded before this cog loaded (a reload), so catch up on what changed.
		for guild_id, trap in self.setting.cache.items():
			if needs_reconcile(trap):
				self.schedule_reconcile(guild_id)

	async def cog_unload(self) -> None:
		for task in self._background:
			task.cancel()

	def _spawn(self, coro: Awaitable[Any]) -> None:
		async def runner() -> None:
			try:
				await coro
			except Exception:
				logger.exception("Bear trap background task failed")

		task = asyncio.create_task(runner())
		self._background.add(task)
		task.add_done_callback(self._background.discard)

	def _owns(self, guild_id: int) -> discord.Guild | None:
		"""The guild, if this instance handles its shard."""
		if not is_guild_on_shard(self.bot, guild_id):
			return None
		return self.bot.get_guild(guild_id)

	def schedule_reconcile(self, guild_id: int) -> None:
		"""Reconcile the guild's trap message in the background, if this instance handles the guild's shard."""
		if is_guild_on_shard(self.bot, guild_id):
			self._spawn(self.reconcile(guild_id))

	async def reconcile(self, guild_id: int, *, verify: bool = False) -> bool:
		"""Make the trap message match the trap: delete a message outside the trap's channel, post a missing one.

		If the bot can't post in the trap's channel, it turns the trap off.

		Args:
			guild_id: The guild.
			verify: Also check that a message the API knows of still exists, and post a new one if it doesn't.

		Returns:
			Whether the trap is off, or on with its message in place.
		"""
		await self.bot.wait_until_ready()
		guild = self._owns(guild_id)
		if guild is None:
			return False
		async with self._locks[guild_id]:
			trap = await self.setting.get(guild_id)
			if trap.message_id is not None and (
				trap.message_channel_id != trap.channel_id or (verify and not await self._message_exists(guild, trap))
			):
				await self._delete_message(guild, trap)
				trap = await self._record_message(guild_id, None)
			if trap.channel_id is None or trap.message_id is not None:
				return True
			return await self._post(guild, trap.channel_id)

	async def _message_exists(self, guild: discord.Guild, trap: BearTrapState) -> bool:
		channel = guild.get_channel(trap.message_channel_id or 0)
		if not isinstance(channel, discord.TextChannel) or trap.message_id is None:
			return False
		try:
			await channel.fetch_message(trap.message_id)
		except discord.NotFound:
			return False
		except discord.HTTPException:
			return True  # unknown; better than posting a duplicate
		return True

	async def _delete_message(self, guild: discord.Guild, trap: BearTrapState) -> None:
		channel = guild.get_channel(trap.message_channel_id or 0)
		if isinstance(channel, discord.TextChannel) and trap.message_id is not None:
			try:
				await channel.get_partial_message(trap.message_id).delete()
			except discord.HTTPException:
				pass  # already gone, or no longer ours to delete

	async def _record_message(self, guild_id: int, message: discord.Message | None) -> BearTrapState:
		trap = await self.bot.api.bear_trap.set_message(
			guild_id, message.channel.id if message else None, message.id if message else None
		)
		self.setting.remember(guild_id, trap)
		return trap

	async def _post(self, guild: discord.Guild, channel_id: int) -> bool:
		channel = guild.get_channel(channel_id)
		if not isinstance(channel, discord.TextChannel) or missing_permissions(channel)[0]:
			logger.warning(f"Turning off the bear trap in {guild.id}: can't run it in channel {channel_id}")
			await self._turn_off(guild.id)
			return False
		kwargs = await self._layout(guild)
		try:
			message = await channel.send(**kwargs)
		except discord.HTTPException:
			logger.warning(
				f"Turning off the bear trap in {guild.id}: can't post in channel {channel_id}", exc_info=True
			)
			await self._turn_off(guild.id)
			return False
		finally:
			_stop_view(kwargs)
		await self._record_message(guild.id, message)
		return True

	async def _turn_off(self, guild_id: int) -> None:
		self.setting.remember(guild_id, await self.bot.api.bear_trap.set_channel(guild_id, None))

	async def _layout(self, guild: discord.Guild) -> dict[str, Any]:
		trap = self.setting.cache.get(guild.id) or BearTrapState()
		return _send_kwargs(await self.responses.get_message("bear_trap.message", guild, kicks=trap.kicks))

	async def set_channel(self, guild_id: int, channel_id: int | None) -> bool:
		"""Move the trap to a channel, or turn it off, and reconcile the message at once.

		Args:
			guild_id: The guild.
			channel_id: The channel. ``None`` turns the trap off.

		Returns:
			Whether the trap message is in place (or removed, when turning the trap off).
		"""
		self.setting.remember(guild_id, await self.bot.api.bear_trap.set_channel(guild_id, channel_id))
		return await self.reconcile(guild_id, verify=True)

	@commands.Cog.listener()
	async def on_message(self, message: discord.Message) -> None:
		if message.guild is None or message.webhook_id is not None or message.type not in TRAPPED_MESSAGE_TYPES:
			return
		trap = self.setting.cache.get(message.guild.id)
		if trap is None or trap.channel_id != message.channel.id:
			return
		member = message.author
		if not isinstance(member, discord.Member) or is_exempt(member):
			return

		key = (message.guild.id, member.id)
		if key in self._catching:
			await self._delete(message)
			return
		self._catching.add(key)
		try:
			await self._catch(message, member)
		finally:
			self._catching.discard(key)

	async def _delete(self, message: discord.Message) -> None:
		try:
			await message.delete()
		except discord.HTTPException:
			pass

	async def _catch(self, message: discord.Message, member: discord.Member) -> None:
		"""Soft-ban a member who posted in the trap, DMing them first, and count it."""
		guild = member.guild
		await self._delete(message)
		reason = await self.responses.get_message("bear_trap.reason", guild)
		softban = BearTrapSoftban(
			Case.generate_id(message),
			self.bot,
			guild,
			member,
			guild.me,
			reason if isinstance(reason, str) else None,
			invite=await self._invite(guild),
		)
		try:
			if await self.cases.open(softban) is None:
				return  # left before the ban
		except discord.HTTPException:
			logger.warning(f"Bear trap failed to soft-ban {member.id} in {guild.id}", exc_info=True)
			return

		try:
			kicks = await self.bot.api.bear_trap.add_kick(guild.id)
		except ApiUnavailable:
			logger.warning(f"Bear trap soft-banned {member.id} in {guild.id} but couldn't count it", exc_info=True)
			return
		trap = await self.setting.get(guild.id)
		self.setting.remember(guild.id, trap.model_copy(update={"kicks": kicks}))
		self._schedule_counter_update(guild.id)

	async def _invite(self, guild: discord.Guild) -> str | None:
		"""An invite for a soft-banned member to come back: the vanity URL, else a single-use one for 7 days."""
		if guild.vanity_url_code:
			return f"https://discord.gg/{guild.vanity_url_code}"
		trap = self.setting.cache.get(guild.id)
		trap_channel = trap.channel_id if trap else None
		candidates = [guild.rules_channel, guild.system_channel, *guild.text_channels]
		for channel in candidates:
			if (
				isinstance(channel, discord.TextChannel)
				and channel.id != trap_channel
				and channel.permissions_for(guild.default_role).view_channel
				and channel.permissions_for(guild.me).create_instant_invite
			):
				try:
					invite = await channel.create_invite(max_age=INVITE_MAX_AGE, max_uses=1, unique=True)
				except discord.HTTPException:
					return None
				return invite.url
		return None

	def _schedule_counter_update(self, guild_id: int) -> None:
		if guild_id in self._counter_updates:
			return
		self._counter_updates.add(guild_id)
		self._spawn(self._update_counter(guild_id))

	async def _update_counter(self, guild_id: int) -> None:
		"""After `COUNTER_DELAY`, re-render the trap message with the current count, re-posting it if it's gone."""
		try:
			await asyncio.sleep(COUNTER_DELAY)
		finally:
			# Kicks from now on schedule another update, so none is lost while this one edits.
			self._counter_updates.discard(guild_id)
		guild = self._owns(guild_id)
		if guild is None:
			return
		async with self._locks[guild_id]:
			trap = await self.setting.get(guild_id)
			channel = guild.get_channel(trap.message_channel_id or 0)
			if trap.message_id is None or not isinstance(channel, discord.TextChannel):
				return
			kwargs = await self._layout(guild)
			try:
				await channel.get_partial_message(trap.message_id).edit(
					view=kwargs.get("view"), allowed_mentions=kwargs.get("allowed_mentions")
				)
				return
			except discord.NotFound:
				pass
			except discord.HTTPException:
				logger.warning(f"Failed to update the bear trap counter in {guild_id}", exc_info=True)
				return
			finally:
				_stop_view(kwargs)
		await self._record_message(guild_id, None)  # deleted by hand: the change hook posts a new one


async def setup(bot: Bot) -> None:
	await bot.add_cog(BearTrap(bot))
