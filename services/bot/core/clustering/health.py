"""Shard health reporting: raw per-shard facts for the API's status page."""

from __future__ import annotations

import datetime
import math
from collections.abc import Iterable
from logging import getLogger

import discord
import redis.asyncio as aioredis
from redis.typing import EncodableT, FieldT

from api import HEALTH_KEY, SHARDS_PER_CLUSTER_KEY, SHARDS_TOTAL_KEY, ShardHealth

__all__ = ("HealthReporter", "shard_health")

logger = getLogger(__name__)


def shard_health(
	shard: discord.ShardInfo, cluster_id: str, guild_count: int, ready: bool, now: datetime.datetime
) -> ShardHealth:
	"""Collect a shard's health facts.

	Args:
		shard: The shard.
		cluster_id: The reporting process.
		guild_count: How many guilds the shard holds.
		ready: Whether the shard received READY (or resumed) and hasn't disconnected since.
		now: The report time.

	Returns:
		The report. Latency is ``None`` until the first heartbeat is acknowledged.
	"""
	latency = shard.latency
	closed = shard.is_closed()
	return ShardHealth(
		shard_id=shard.id,
		cluster_id=cluster_id,
		latency_ms=round(latency * 1000, 2) if math.isfinite(latency) and latency >= 0 else None,
		guild_count=guild_count,
		ready=ready and not closed,
		closed=closed,
		ratelimited=not closed and shard.is_ws_ratelimited(),
		updated_at=now,
	)


class HealthReporter:
	"""Writes shard health and the status block layout to Redis, where the API reads them.

	Writing health is separate from leasing shards: a standalone bot reports too, as one block of every shard.

	Args:
		redis: The Redis client.
	"""

	def __init__(self, redis: aioredis.Redis) -> None:
		self._redis = redis

	@classmethod
	def from_url(cls, url: str) -> HealthReporter:
		"""Connect to Redis.

		Args:
			url: The Redis URL.

		Returns:
			The reporter.
		"""
		return cls(aioredis.from_url(url, decode_responses=False))

	async def report(self, total: int, per_cluster: int, shards: Iterable[ShardHealth]) -> None:
		"""Write the layout and the shards' reports. Redis failures are logged, not raised.

		Args:
			total: The bot's shard count.
			per_cluster: Shards per status block.
			shards: This process's shards' reports.
		"""
		mapping: dict[FieldT, EncodableT] = {str(shard.shard_id): shard.model_dump_json() for shard in shards}
		try:
			async with self._redis.pipeline(transaction=False) as pipe:
				pipe.mset({SHARDS_TOTAL_KEY: total, SHARDS_PER_CLUSTER_KEY: per_cluster})
				if mapping:
					pipe.hset(HEALTH_KEY, mapping=mapping)
				await pipe.execute()
		except (aioredis.RedisError, OSError) as e:
			logger.debug(f"Failed to report shard health: {e}")

	async def close(self) -> None:
		"""Close the Redis connection."""
		await self._redis.aclose()
