"""Per-user command cooldowns kept in Redis, so restarting the bot or running several bot processes doesn't reset them."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import redis.asyncio as aioredis
from discord.ext import commands

if TYPE_CHECKING:
	from core.context import Context

__all__ = ("SharedCooldowns", "shared_cooldown")


class SharedCooldowns:
	"""Starts and checks cooldowns in Redis.

	Args:
		redis: The Redis client.
	"""

	def __init__(self, redis: aioredis.Redis) -> None:
		self._redis = redis

	@classmethod
	def from_url(cls, url: str) -> SharedCooldowns:
		"""Connect to Redis.

		Args:
			url: The Redis URL.

		Returns:
			The cooldowns.
		"""
		return cls(aioredis.from_url(url))

	async def hit(self, key: str, seconds: int) -> float | None:
		"""Start a cooldown, unless one is running.

		Args:
			key: What is cooling down, e.g. a command and a user.
			seconds: How long the cooldown lasts.

		Returns:
			``None`` if the cooldown started, else the seconds left on the running one.
		"""
		name = f"fm01:cooldown:{key}"
		if await self._redis.set(name, 1, nx=True, ex=seconds):
			return None
		return max(await self._redis.pttl(name), 0) / 1000

	async def close(self) -> None:
		"""Close the Redis connection."""
		await self._redis.aclose()


def shared_cooldown(seconds: int) -> Callable[[Any], Any]:
	"""Like ``commands.cooldown(1, seconds, commands.BucketType.user)``, but kept in Redis (`Bot.cooldowns`).

	It runs as the command's before-invoke hook, so checks (which the help command also runs) don't start it.

	Args:
		seconds: How long a user waits between uses.

	Returns:
		The command decorator.
	"""

	async def hook(*args: Any) -> None:
		ctx: Context = args[-1]  # (cog, ctx) for commands in a cog, else (ctx,)
		assert ctx.command is not None
		retry_after = await ctx.bot.cooldowns.hit(f"{ctx.command.qualified_name}:{ctx.author.id}", seconds)
		if retry_after is not None:
			raise commands.CommandOnCooldown(commands.Cooldown(1, seconds), retry_after, commands.BucketType.user)

	return commands.before_invoke(hook)
