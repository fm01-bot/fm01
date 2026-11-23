"""The guild manager rule for the dashboard."""

from __future__ import annotations

import asyncio
import json
import weakref
from datetime import UTC, datetime, timedelta
from typing import Any

import redis.asyncio as aioredis
from api import ErrorCode, ManagedGuild

from app.blacklist.store import BlacklistStore
from app.dashboard.discord import DiscordClient, OAuthTokenSet
from app.dashboard.sessions import Session, SessionStore
from app.errors import ApiError

__all__ = ("ADMINISTRATOR", "BAN_MEMBERS", "MANAGE_GUILD", "GuildAccess", "has_permission", "is_guild_manager")

BAN_MEMBERS = 1 << 2
ADMINISTRATOR = 1 << 3
MANAGE_GUILD = 1 << 5
_REFRESH_MARGIN = timedelta(minutes=1)


def has_permission(guild: dict[str, Any], permission: int) -> bool:
	"""Check whether the user owns the guild, has Administrator, or has a permission in it.

	Args:
		guild: One entry of Discord's ``/users/@me/guilds``.
		permission: The permission bit.

	Returns:
		Whether the user has the permission.
	"""
	permissions = int(guild.get("permissions", 0))
	return bool(guild.get("owner")) or bool(permissions & (ADMINISTRATOR | permission))


def is_guild_manager(guild: dict[str, Any]) -> bool:
	"""Check whether the user owns the guild or has Administrator or Manage Server.

	Args:
		guild: One entry of Discord's ``/users/@me/guilds``.

	Returns:
		Whether the user is a guild manager.
	"""
	return has_permission(guild, MANAGE_GUILD)


class GuildAccess:
	"""Checks guild managers against the user's Discord guild list, cached in Redis.

	Blacklisted guilds are never managed: they aren't listed, and configuring them is refused.

	Args:
		discord: The Discord client.
		sessions: The session store, for saving refreshed Discord tokens.
		blacklist: The blacklist.
		redis: The cache.
		ttl: How long a result is cached. A demoted user keeps access this long.
	"""

	def __init__(
		self,
		discord: DiscordClient,
		sessions: SessionStore,
		blacklist: BlacklistStore,
		redis: aioredis.Redis,
		ttl: timedelta,
	) -> None:
		self._discord = discord
		self._sessions = sessions
		self._blacklist = blacklist
		self._redis = redis
		self._ttl = ttl
		self._refresh_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()

	async def managed_guilds(self, session: Session) -> list[ManagedGuild]:
		"""List the guilds the session's user manages, with or without the bot, except blacklisted ones.

		Args:
			session: The user's dashboard session.

		Returns:
			The managed guilds.

		Raises:
			ApiError: ``unauthorized`` if Discord rejects the user's tokens, which also ends the session.
				``discord_unavailable`` if Discord fails.
		"""
		guilds = await self._managed(session)
		blacklisted = await self._blacklist.blacklisted_guilds(int(guild["id"]) for guild in guilds)
		return [
			ManagedGuild(id=guild["id"], name=guild["name"], icon=guild.get("icon"))
			for guild in guilds
			if int(guild["id"]) not in blacklisted
		]

	async def require_manager(self, session: Session, guild_id: int, permission: int = 0) -> None:
		"""Check that the session's user may configure a guild.

		Args:
			session: The user's dashboard session.
			guild_id: The guild.
			permission: A permission bit the user needs on top, for settings that act on members (owners and
				Administrators have every permission).

		Raises:
			ApiError: ``forbidden`` if the user isn't a guild manager of it or lacks ``permission``. ``blacklisted``
				if the guild is blacklisted. ``not_found`` if the bot isn't in it. Also anything `managed_guilds`
				raises.
		"""
		guild = next((guild for guild in await self._managed(session) if int(guild["id"]) == guild_id), None)
		if guild is None:
			raise ApiError(ErrorCode.FORBIDDEN, "you are not a manager of this guild")
		if permission and not has_permission(guild, permission):
			raise ApiError(ErrorCode.FORBIDDEN, "you lack a permission this setting needs in this guild")
		if await self._blacklist.is_blacklisted("guild", guild_id):
			raise ApiError(ErrorCode.BLACKLISTED, "this guild is blacklisted")
		if not await self._bot_in_guild(guild_id):
			raise ApiError(ErrorCode.NOT_FOUND, "the bot is not in this guild")

	async def _managed(self, session: Session) -> list[dict[str, Any]]:
		"""Get the user's managed guilds, as Discord lists them (with ``owner`` and ``permissions``), with caching.

		Raises:
			ApiError: See `managed_guilds`.
		"""
		key = f"dashboard:guilds:{session.id}"
		cached = await self._redis.get(key)
		if cached is not None:
			return json.loads(cached)
		access_token = await self._fresh_access_token(session)
		guilds = [
			{field: guild.get(field) for field in ("id", "name", "icon", "owner", "permissions")}
			for guild in await self._discord.current_user_guilds(access_token)
			if is_guild_manager(guild)
		]
		await self._redis.set(key, json.dumps(guilds), ex=self._ttl)
		return guilds

	async def _bot_in_guild(self, guild_id: int) -> bool:
		"""Check whether the bot is in a guild, with caching.

		Args:
			guild_id: The guild.

		Returns:
			Whether the bot is a member.
		"""
		key = f"dashboard:bot_in_guild:{guild_id}"
		cached = await self._redis.get(key)
		if cached is not None:
			return cached in (b"1", "1")
		present = await self._discord.bot_in_guild(guild_id)
		await self._redis.set(key, "1" if present else "0", ex=self._ttl)
		return present

	async def _fresh_access_token(self, session: Session) -> str:
		"""Get the session's Discord access token, refreshed if it expires within a minute.

		Refreshes of one session run one at a time: Discord rotates the refresh token, so a second refresh with the
		old one would fail and end the session.

		Args:
			session: The user's dashboard session.

		Returns:
			A valid access token.

		Raises:
			ApiError: ``unauthorized`` if the refresh fails, which also ends the session. ``discord_unavailable`` if
				Discord fails.
		"""
		if not _expiring(session.discord):
			return session.discord.access_token
		lock = self._refresh_locks.get(session.id)
		if lock is None:
			lock = self._refresh_locks[session.id] = asyncio.Lock()
		async with lock:
			# Another request may have refreshed them while this one waited.
			current = await self._sessions.discord_tokens(session.id)
			if current is None:
				raise ApiError(ErrorCode.UNAUTHORIZED, "invalid or expired session")
			if not _expiring(current):
				return current.access_token
			try:
				tokens: OAuthTokenSet = await self._discord.refresh(current.refresh_token)
			except ApiError as exc:
				if exc.code is ErrorCode.UNAUTHORIZED:
					await self._sessions.revoke(session.id)
				raise
			await self._sessions.update_tokens(session.id, tokens)
			return tokens.access_token


def _expiring(tokens: OAuthTokenSet) -> bool:
	"""Check whether Discord tokens expire within a minute."""
	return tokens.expires_at - _REFRESH_MARGIN <= datetime.now(UTC)
