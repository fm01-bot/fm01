from __future__ import annotations

import asyncio
import contextlib
from logging import getLogger

import redis.asyncio as aioredis

from core.clustering.interfaces import ShardCoordinator

logger = getLogger(__name__)

RELEASE_LEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

CLAIM_BLOCK_LUA = """
for _, key in ipairs(KEYS) do
    local owner = redis.call('get', key)
    if owner and owner ~= ARGV[1] then
        return 0
    end
end
for _, key in ipairs(KEYS) do
    redis.call('set', key, ARGV[1], 'EX', ARGV[2])
end
return 1
"""
"""Leases every shard in KEYS for ARGV[1] if none is held by another cluster. Returns 1 if it did."""

RENEW_LEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
else
    return 0
end
"""


class StandaloneCoordinator(ShardCoordinator):
	"""Coordinator for BOT_MODE=standalone (relies on default discord.py sharding)."""

	async def acquire_shards(self, total_shards: int, shards_per_cluster: int) -> list[int] | None:
		return None

	async def start_heartbeat(self) -> None:
		pass

	async def release_shards(self) -> None:
		pass

	async def close(self) -> None:
		pass


class RedisShardCoordinator(ShardCoordinator):
	"""Dynamic Redis lease-based shard coordinator for BOT_MODE=clustered."""

	def __init__(
		self,
		redis_client: aioredis.Redis,
		cluster_id: str,
		lease_ttl: int = 30,
		heartbeat_interval: int = 10,
		explicit_shard_ids: list[int] | None = None,
	) -> None:
		self.redis = redis_client
		self.cluster_id = cluster_id
		self.lease_ttl = lease_ttl
		self.heartbeat_interval = heartbeat_interval
		self.explicit_shard_ids = explicit_shard_ids
		self.claimed_shards: list[int] = []
		self.total_shards = 0
		self._unclaimed_shards: list[int] = []
		self._heartbeat_task: asyncio.Task | None = None
		self._running = False
		self.prefix = "fm01"

	@classmethod
	def from_url(
		cls,
		url: str,
		cluster_id: str,
		lease_ttl: int = 30,
		heartbeat_interval: int = 10,
		explicit_shard_ids: list[int] | None = None,
	) -> RedisShardCoordinator:
		client = aioredis.from_url(url, decode_responses=False)
		return cls(
			client,
			cluster_id=cluster_id,
			lease_ttl=lease_ttl,
			heartbeat_interval=heartbeat_interval,
			explicit_shard_ids=explicit_shard_ids,
		)

	async def acquire_shards(self, total_shards: int, shards_per_cluster: int) -> list[int]:
		self.total_shards = total_shards
		if self.explicit_shard_ids is not None:
			claimed = await self._claim_explicit(self.explicit_shard_ids, shards_per_cluster)
		else:
			claimed = await self._claim_block(total_shards, shards_per_cluster)

		if not claimed:
			raise RuntimeError(
				f"Cluster {self.cluster_id} found no free shards of {total_shards}: every block of "
				f"{shards_per_cluster} shards (or every SHARD_IDS shard) is leased by another cluster"
			)

		self.claimed_shards = claimed
		logger.info(f"Cluster {self.cluster_id} assigned shards: {self.claimed_shards}")
		return claimed

	async def _claim_explicit(self, shard_ids: list[int], limit: int) -> list[int]:
		"""Claim up to ``limit`` of the given shards, one by one.

		Args:
			shard_ids: The shards to claim (``SHARD_IDS``).
			limit: The most shards to claim.

		Returns:
			The shards claimed, or already held by this cluster.
		"""
		claimed: list[int] = []
		for shard_id in shard_ids:
			if len(claimed) >= limit:
				break
			key = f"{self.prefix}:shard:lease:{shard_id}"
			acquired = await self.redis.set(key, self.cluster_id.encode("utf-8"), nx=True, ex=self.lease_ttl)
			if acquired:
				claimed.append(shard_id)
				logger.info(f"Cluster {self.cluster_id} acquired lease on shard {shard_id}")
			else:
				current_owner = await self.redis.get(key)
				if current_owner and current_owner.decode("utf-8") == self.cluster_id:  # type: ignore
					# We already own the lease from previous run/reboot
					await self.redis.expire(key, self.lease_ttl)
					claimed.append(shard_id)
					logger.info(f"Cluster {self.cluster_id} reclaimed existing lease on shard {shard_id}")
		return claimed

	async def _claim_block(self, total_shards: int, block_size: int) -> list[int]:
		"""Claim the lowest status block whose shards no other cluster holds, all at once.

		A block is ``n * block_size`` up to ``(n + 1) * block_size - 1``, so the status page's blocks match the
		clusters running them. Partial blocks are never claimed.

		Args:
			total_shards: The shard count.
			block_size: Shards per block (``SHARDS_PER_CLUSTER``).

		Returns:
			The block's shards, or nothing if every block is taken.
		"""
		block_size = max(block_size, 1)
		for start in range(0, total_shards, block_size):
			block = list(range(start, min(start + block_size, total_shards)))
			keys = [f"{self.prefix}:shard:lease:{shard_id}" for shard_id in block]
			if await self.redis.eval(
				CLAIM_BLOCK_LUA, len(keys), *keys, self.cluster_id.encode("utf-8"), self.lease_ttl
			):
				logger.info(f"Cluster {self.cluster_id} acquired leases on block {start // block_size}: {block}")
				return block
		return []

	async def start_heartbeat(self) -> None:
		if self._running or not self.claimed_shards:
			return
		self._running = True
		self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

	async def _heartbeat_loop(self) -> None:
		logger.debug(f"Shard lease heartbeat started for {self.claimed_shards}")
		while self._running:
			try:
				await asyncio.sleep(self.heartbeat_interval)
				for shard_id in self.claimed_shards:
					key = f"{self.prefix}:shard:lease:{shard_id}"
					renewed = await self.redis.eval(
						RENEW_LEASE_LUA, 1, key, self.cluster_id.encode("utf-8"), self.lease_ttl
					)
					if not renewed:
						logger.warning(
							f"Shard {shard_id} lease lost by cluster {self.cluster_id}! Attempting re-acquisition..."
						)
						await self.redis.set(key, self.cluster_id.encode("utf-8"), ex=self.lease_ttl)
				await self._check_unclaimed_shards()
			except asyncio.CancelledError:
				break
			except Exception:
				logger.exception("Error in shard lease heartbeat loop")

	async def unclaimed_shards(self) -> list[int]:
		"""Return the shard IDs that no cluster holds a lease on.

		The gateway proxy keeps every shard connected to Discord, so an unleased shard's guilds see the bot online
		while nothing processes their events.
		"""
		if not self.total_shards:
			return []
		keys = [f"{self.prefix}:shard:lease:{shard_id}" for shard_id in range(self.total_shards)]
		owners = await self.redis.mget(keys)
		return [shard_id for shard_id, owner in enumerate(owners) if owner is None]

	async def _check_unclaimed_shards(self) -> None:
		"""Log when the set of unleased shards changes, so missing capacity never fails silently."""
		unclaimed = await self.unclaimed_shards()
		if unclaimed == self._unclaimed_shards:
			return
		if unclaimed:
			logger.warning(
				f"Shards {unclaimed} of {self.total_shards} are not claimed by any cluster; their guilds get no "
				"responses. Run more bot replicas or raise SHARDS_PER_CLUSTER so that "
				"replicas * SHARDS_PER_CLUSTER >= SHARD_COUNT."
			)
		else:
			logger.info(f"All {self.total_shards} shards are claimed")
		self._unclaimed_shards = unclaimed

	async def release_shards(self) -> None:
		logger.info(f"Releasing shard leases for cluster {self.cluster_id}: {self.claimed_shards}")
		for shard_id in self.claimed_shards:
			key = f"{self.prefix}:shard:lease:{shard_id}"
			try:
				await self.redis.eval(RELEASE_LEASE_LUA, 1, key, self.cluster_id.encode("utf-8"))
			except (aioredis.RedisError, OSError):
				logger.exception(f"Failed to release lease on shard {shard_id}")
		self.claimed_shards.clear()

	async def close(self) -> None:
		self._running = False
		if self._heartbeat_task and not self._heartbeat_task.done():
			self._heartbeat_task.cancel()
			with contextlib.suppress(asyncio.CancelledError):
				await self._heartbeat_task

		with contextlib.suppress(Exception):
			await self.redis.aclose()
