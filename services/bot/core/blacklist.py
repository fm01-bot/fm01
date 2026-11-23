"""The blacklist: users and guilds the bot's owners barred from using commands.

The API keeps the blacklist and announces each change as a ``BLACKLIST_CHANGED`` event, so every instance holds the
whole blacklist in memory and checks it synchronously before each command (`Blacklist.check`, a global bot check).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from discord.ext import commands

from api import BLACKLIST_CHANGED, BlacklistEntry, BlacklistKind
from core.api import ApiClient

__all__ = ("Blacklist", "Blacklisted")

logger = logging.getLogger(__name__)


class Blacklisted(commands.CheckFailure):
	"""The command's author or guild is blacklisted. The bot doesn't answer."""


class Blacklist:
	"""The blacklisted users and guilds, cached from the API.

	Args:
		api: The API client.
	"""

	def __init__(self, api: ApiClient) -> None:
		self._api = api
		self._targets: dict[BlacklistKind, set[int]] = {"user": set(), "guild": set()}
		self.loaded = False
		"""Whether the blacklist was loaded. Until it is, nothing is blocked."""

	def __contains__(self, target: tuple[BlacklistKind, int]) -> bool:
		kind, target_id = target
		return target_id in self._targets[kind]

	async def load(self) -> None:
		"""Load the whole blacklist from the API. Logs failures instead of raising, leaving the cache as it was."""
		try:
			entries = await self._api.blacklist.entries()
		except Exception:
			logger.exception("Failed to load the blacklist")
			return
		self._targets = {"user": set(), "guild": set()}
		for entry in entries:
			self._targets[entry.kind].add(entry.target_id)
		self.loaded = True

	async def add(self, kind: BlacklistKind, target_id: int, created_by: int, reason: str | None) -> BlacklistEntry:
		"""Blacklist a user or guild through the API. Blacklisting it again replaces the reason.

		Args:
			kind: Whether the target is a user or a guild.
			target_id: The user or guild.
			created_by: The bot owner adding it.
			reason: Why, if given.

		Returns:
			The entry.
		"""
		entry = await self._api.blacklist.add(kind, target_id, created_by, reason)
		self._targets[kind].add(target_id)
		return entry

	async def remove(self, kind: BlacklistKind, target_id: int) -> bool:
		"""Take a user or guild off the blacklist through the API.

		Args:
			kind: Whether the target is a user or a guild.
			target_id: The user or guild.

		Returns:
			Whether it was blacklisted.
		"""
		removed = await self._api.blacklist.remove(kind, target_id)
		self._targets[kind].discard(target_id)
		return removed

	def handle_event(self, event: Mapping[str, Any]) -> bool:
		"""Apply a ``BLACKLIST_CHANGED`` event from the API.

		Returns:
			Whether the event was a blacklist change.
		"""
		if event.get("type") != BLACKLIST_CHANGED:
			return False
		kind, target_id = event.get("kind"), event.get("target_id")
		if kind not in self._targets or target_id is None:
			return True
		if event.get("blacklisted"):
			self._targets[kind].add(int(target_id))
		else:
			self._targets[kind].discard(int(target_id))
		return True

	async def check(self, ctx: commands.Context[Any]) -> bool:
		"""Refuse commands from blacklisted users and in blacklisted guilds. Bot owners are never refused.

		Raises:
			Blacklisted: The author or the guild is blacklisted.
		"""
		if not self.loaded:
			await self.load()
		blocked = ("user", ctx.author.id) in self or (ctx.guild is not None and ("guild", ctx.guild.id) in self)
		if blocked and not await ctx.bot.is_owner(ctx.author):
			raise Blacklisted()
		return True
