from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as aioredis
from core.cooldowns import SharedCooldowns, shared_cooldown
from discord.ext import commands


class FakeRedis:
	"""Just enough of Redis for `SharedCooldowns`: SET NX EX and PTTL."""

	def __init__(self) -> None:
		self.keys: dict[str, int] = {}

	async def set(self, name: str, value: object, *, nx: bool, ex: int) -> bool:
		if nx and name in self.keys:
			return False
		self.keys[name] = ex * 1000
		return True

	async def pttl(self, name: str) -> int:
		return self.keys.get(name, -2)


async def test_second_hit_reports_the_time_left():
	cooldowns = SharedCooldowns(cast("aioredis.Redis", FakeRedis()))

	assert await cooldowns.hit("daily:1", 86400) is None
	assert await cooldowns.hit("daily:1", 86400) == 86400
	assert await cooldowns.hit("daily:2", 86400) is None


async def test_a_cooldown_that_expires_mid_hit_starts_a_new_one():
	redis = FakeRedis()
	redis.keys["fm01:cooldown:work:1"] = 1
	real_pttl = redis.pttl

	async def pttl(name: str) -> int:
		redis.keys.pop(name, None)  # expires between SET NX and PTTL
		redis.pttl = real_pttl
		return await real_pttl(name)

	redis.pttl = pttl
	cooldowns = SharedCooldowns(cast("aioredis.Redis", redis))

	assert await cooldowns.hit("work:1", 3600) is None
	assert redis.keys["fm01:cooldown:work:1"] == 3600 * 1000


async def test_hook_raises_command_on_cooldown():
	@shared_cooldown(60)
	async def callback(cog, ctx): ...

	command = commands.Command(callback, name="crime")
	ctx = MagicMock()
	ctx.command = command
	ctx.author.id = 7
	ctx.bot._before_invoke = None
	ctx.bot.cooldowns.hit = AsyncMock(side_effect=[None, 30.0])

	await command.call_before_hooks(ctx)
	with pytest.raises(commands.CommandOnCooldown) as raised:
		await command.call_before_hooks(ctx)

	assert raised.value.retry_after == 30.0
	ctx.bot.cooldowns.hit.assert_awaited_with("crime:7", 60)
