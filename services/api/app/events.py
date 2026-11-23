"""Change events for bot instances, over the Redis event bus."""

from __future__ import annotations

import logging

import redis.asyncio as aioredis
from api import EVENTS_CHANNEL, BlacklistChanged, BlacklistKind, InvalidateSetting

__all__ = ("Announcer",)

logger = logging.getLogger(__name__)


class Announcer:
	"""Publishes events to bot instances.

	Args:
		redis: The Redis the event bus runs on.
	"""

	def __init__(self, redis: aioredis.Redis) -> None:
		self._redis = redis

	async def setting_changed(self, key: str, guild_id: int, origin: str | None) -> None:
		"""Tell bot instances to reload a guild setting. Logs Redis failures instead of raising.

		Args:
			key: The setting's key on the bot's ``GuildSettings``.
			guild_id: The guild whose setting changed.
			origin: The bot instance that caused the change. ``None`` for the dashboard.
		"""
		event = InvalidateSetting(key=key, guild_id=guild_id, origin=origin)
		try:
			await self._redis.publish(EVENTS_CHANNEL, event.model_dump_json())
		except aioredis.RedisError:
			# The write already committed. Stale bot caches until they reload beat failing the request.
			logger.exception(f"Failed to announce change of setting {key!r} for guild {guild_id}")

	async def blacklist_changed(self, kind: BlacklistKind, target_id: int, blacklisted: bool) -> None:
		"""Tell bot instances that a user or guild was added to or removed from the blacklist. Logs Redis failures.

		Args:
			kind: Whether the target is a user or a guild.
			target_id: The user or guild.
			blacklisted: Whether the target is blacklisted now.
		"""
		event = BlacklistChanged(kind=kind, target_id=target_id, blacklisted=blacklisted)
		try:
			await self._redis.publish(EVENTS_CHANNEL, event.model_dump_json())
		except aioredis.RedisError:
			# Bot instances pick the change up when they next load the blacklist.
			logger.exception(f"Failed to announce blacklist change of {kind} {target_id}")
