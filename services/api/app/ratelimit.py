"""Per-IP rate limits for the Public API, counted in Redis."""

from __future__ import annotations

import time
from collections.abc import Callable

import redis.asyncio as aioredis
from api import ErrorCode
from fastapi import Request

from app.errors import ApiError

__all__ = ("RateLimiter", "rate_limit")

WINDOW = 60
"""Seconds per counting window."""


class RateLimiter:
	"""Counts requests per IP in fixed one-minute windows.

	Args:
		redis: The Redis client holding the counters.
		clock: Returns the current Unix time.
	"""

	def __init__(self, redis: aioredis.Redis, clock: Callable[[], float] = time.time) -> None:
		self._redis = redis
		self._clock = clock

	async def hit(self, scope: str, ip: str, limit: int) -> None:
		"""Count a request.

		Args:
			scope: What is limited, e.g. a route name. Each scope counts separately.
			ip: The caller's IP.
			limit: Requests allowed per minute.

		Raises:
			ApiError: ``rate_limited``, with ``Retry-After`` set to the seconds left in the window.
		"""
		now = self._clock()
		window = int(now // WINDOW)
		key = f"fm01:ratelimit:{scope}:{ip}:{window}"
		async with self._redis.pipeline(transaction=True) as pipe:
			pipe.incr(key)
			pipe.expire(key, WINDOW)
			count, _ = await pipe.execute()
		if count > limit:
			retry_after = max(1, (window + 1) * WINDOW - int(now))
			raise ApiError(ErrorCode.RATE_LIMITED, headers={"Retry-After": str(retry_after)})


def rate_limit(scope: str, per_minute: int) -> Callable[..., object]:
	"""Build a dependency that limits a route per caller IP.

	Behind Caddy the IP comes from ``X-Forwarded-For``, which Uvicorn trusts (``--forwarded-allow-ips``).

	Args:
		scope: The route's name, so limits count separately per route.
		per_minute: Requests allowed per IP per minute.

	Returns:
		The dependency. It raises ``rate_limited`` past the limit.
	"""

	async def dependency(request: Request) -> None:
		"""Count the request against the caller's IP.

		Args:
			request: The request.
		"""
		ip = request.client.host if request.client else "unknown"
		# The app state, read directly: app.state imports this module.
		await request.app.state.fm01.rate_limiter.hit(scope, ip, per_minute)

	return dependency
