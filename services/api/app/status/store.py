"""The status store: current shard and cluster statuses from Redis, and their history in PostgreSQL."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import asyncpg
import redis.asyncio as aioredis
from api import (
	HEALTH_KEY,
	SHARDS_PER_CLUSTER_KEY,
	SHARDS_TOTAL_KEY,
	ClusterDay,
	ClusterHistory,
	ClusterState,
	ShardDay,
	ShardHealth,
	ShardHistory,
	ShardState,
	ShardStatus,
	Status,
	StatusHistory,
)
from pydantic import ValidationError

from app.status.history import CLUSTER_RANK, SHARD_RANK, combine, days, shard_timeline, split_days
from app.status.rules import blocks, cluster_status, shard_status

__all__ = ("HISTORY_DAYS", "StatusStore")

HISTORY_DAYS = 90
"""How many days of history are kept and served."""
STATUS_TTL = 10.0
"""Seconds the current status is cached."""
HISTORY_TTL = 300.0
"""Seconds a history response is cached."""

logger = logging.getLogger(__name__)


class _Cache[T]:
	"""Keeps computed values for a while, per key."""

	def __init__(self, ttl: float) -> None:
		self._ttl = ttl
		self._entries: dict[object, tuple[float, T]] = {}

	async def get(self, key: object, compute: Callable[[], Awaitable[T]]) -> T:
		"""Get a value, computing it if it's missing or too old.

		Args:
			key: The value's key.
			compute: Computes the value.

		Returns:
			The value.
		"""
		now = time.monotonic()
		entry = self._entries.get(key)
		if entry is not None and now - entry[0] < self._ttl:
			return entry[1]
		value = await compute()
		self._entries[key] = (now, value)
		return value


class StatusStore:
	"""Reads shard health from Redis, records status changes, and builds the status history.

	Only one API process may run the sampler: it keeps the last recorded statuses in memory.

	Args:
		db: The database pool.
		redis: The Redis client the bot reports shard health to.
		sample_interval: How often the sampler runs. History counts this long after each sample as recorded.
	"""

	def __init__(self, db: asyncpg.Pool, redis: aioredis.Redis, sample_interval: timedelta) -> None:
		self._db = db
		self._redis = redis
		self._interval = sample_interval
		self._run_id: int | None = None
		self._recorded: dict[int, ShardStatus] | None = None
		self._status_cache: _Cache[Status] = _Cache(STATUS_TTL)
		self._history_cache: _Cache[StatusHistory] = _Cache(HISTORY_TTL)

	async def _layout(self) -> tuple[int, int]:
		"""Read the shard count and status block size the bot last reported.

		Returns:
			The shard count (0 if no bot ever started) and the block size (the shard count if unreported).
		"""
		total, size = await self._redis.mget(SHARDS_TOTAL_KEY, SHARDS_PER_CLUSTER_KEY)
		total = int(total) if total else 0
		return total, int(size) if size else total

	async def _health(self) -> dict[int, ShardHealth]:
		"""Read every shard's latest report.

		Returns:
			Shard ID -> report. Reports that don't parse are left out.
		"""
		reports: dict[int, ShardHealth] = {}
		for raw in (await self._redis.hgetall(HEALTH_KEY)).values():
			try:
				health = ShardHealth.model_validate_json(raw)
			except ValidationError:
				continue
			reports[health.shard_id] = health
		return reports

	async def current(self, now: datetime) -> Status:
		"""Work out the current status from the shards' reports.

		Args:
			now: The current time.

		Returns:
			Every status block and its shards, in order, and the overall status.
		"""
		(total, size), health = await asyncio.gather(self._layout(), self._health())
		clusters = []
		for index, block in enumerate(blocks(total, size)):
			shards = []
			for shard_id in block:
				report = health.get(shard_id)
				shards.append(
					ShardState(
						id=shard_id,
						status=shard_status(report, now),
						latency_ms=report.latency_ms if report else None,
						guild_count=report.guild_count if report else None,
					)
				)
			clusters.append(ClusterState(id=index, status=cluster_status(s.status for s in shards), shards=shards))
		overall = cluster_status(shard.status for cluster in clusters for shard in cluster.shards)
		return Status(status=overall, checked_at=now, clusters=clusters)

	async def cached_status(self) -> Status:
		"""Get the current status, cached for 10 seconds.

		Returns:
			The current status.
		"""
		return await self._status_cache.get(None, lambda: self.current(datetime.now(UTC)))

	async def sample(self, now: datetime) -> None:
		"""Record every shard whose status changed since the last sample, and extend the current sampler run.

		Args:
			now: The current time.
		"""
		current = await self.current(now)
		if self._recorded is None:
			rows = await self._db.fetch(
				"SELECT DISTINCT ON (shard_id) shard_id, status FROM shard_status_changes "
				"ORDER BY shard_id, changed_at DESC"
			)
			self._recorded = {row["shard_id"]: ShardStatus(row["status"]) for row in rows}
		changed = [
			(shard.id, now, str(shard.status))
			for cluster in current.clusters
			for shard in cluster.shards
			if self._recorded.get(shard.id) != shard.status
		]
		async with self._db.acquire() as conn, conn.transaction():
			if changed:
				await conn.executemany(
					"INSERT INTO shard_status_changes (shard_id, changed_at, status) VALUES ($1, $2, $3) "
					"ON CONFLICT (shard_id, changed_at) DO UPDATE SET status = EXCLUDED.status",
					changed,
				)
			if self._run_id is None:
				self._run_id = await conn.fetchval(
					"INSERT INTO status_sampler_runs (started_at, last_sample_at) VALUES ($1, $1) RETURNING id", now
				)
			else:
				await conn.execute(
					"UPDATE status_sampler_runs SET last_sample_at = $2 WHERE id = $1", self._run_id, now
				)
		self._recorded.update((shard_id, ShardStatus(status)) for shard_id, _, status in changed)

	async def prune(self, now: datetime) -> None:
		"""Delete history older than 90 days, keeping each shard's last change before the cutoff.

		Args:
			now: The current time.
		"""
		cutoff = now - timedelta(days=HISTORY_DAYS + 1)
		async with self._db.acquire() as conn, conn.transaction():
			await conn.execute(
				"DELETE FROM shard_status_changes c WHERE c.changed_at < ("
				"SELECT max(l.changed_at) FROM shard_status_changes l WHERE l.shard_id = c.shard_id AND l.changed_at <= $1)",
				cutoff,
			)
			await conn.execute("DELETE FROM status_sampler_runs WHERE last_sample_at < $1", cutoff)

	async def run_sampler(self) -> None:
		"""Sample every interval and prune once a day, until cancelled. Failures are logged and retried next time."""
		pruned_on = None
		while True:
			now = datetime.now(UTC)
			try:
				await self.sample(now)
				if pruned_on != now.date():
					await self.prune(now)
					pruned_on = now.date()
			except (asyncpg.PostgresError, OSError, aioredis.RedisError):
				logger.exception("Status sampling failed")
			await asyncio.sleep(self._interval.total_seconds())

	async def _coverage(self, start: datetime, now: datetime) -> list[tuple[datetime, datetime]]:
		"""Read when the sampler was recording.

		Args:
			start: The earliest time needed.
			now: The current time.

		Returns:
			Each run from its start to one interval after its last sample, cut short by the next run and by now.
		"""
		rows = await self._db.fetch(
			"SELECT started_at, last_sample_at FROM status_sampler_runs WHERE last_sample_at >= $1 ORDER BY started_at",
			start - self._interval,
		)
		coverage = []
		for index, row in enumerate(rows):
			end = min(row["last_sample_at"] + self._interval, now)
			if index + 1 < len(rows):
				end = min(end, rows[index + 1]["started_at"])
			if end > row["started_at"]:
				coverage.append((row["started_at"], end))
		return coverage

	async def history(self, day_count: int, now: datetime) -> StatusHistory:
		"""Build the daily history of every shard, status block and the whole bot.

		Args:
			day_count: How many days, today included.
			now: The current time.

		Returns:
			The history, grouped by today's status blocks.
		"""
		day_intervals = days(day_count, now)
		window = (day_intervals[0][0], now)
		total, size = await self._layout()
		rows = await self._db.fetch(
			"SELECT shard_id, changed_at, status FROM shard_status_changes WHERE changed_at >= $1 AND changed_at < $2 "
			"UNION ALL (SELECT DISTINCT ON (shard_id) shard_id, changed_at, status FROM shard_status_changes "
			"WHERE changed_at < $1 ORDER BY shard_id, changed_at DESC) "
			"ORDER BY changed_at",
			window[0],
			now,
		)
		changes: dict[int, list[tuple[datetime, ShardStatus]]] = defaultdict(list)
		for row in rows:
			changes[row["shard_id"]].append((row["changed_at"], ShardStatus(row["status"])))
		coverage = await self._coverage(window[0], now)

		timelines = {shard_id: shard_timeline(changes[shard_id], coverage, window) for shard_id in range(total)}
		clusters = []
		for index, block in enumerate(blocks(total, size)):
			block_timeline = combine([timelines[shard_id] for shard_id in block], window)
			shards = [
				ShardHistory(id=shard_id, days=split_days(timelines[shard_id], day_intervals, SHARD_RANK, ShardDay))
				for shard_id in block
			]
			clusters.append(
				ClusterHistory(
					id=index, days=split_days(block_timeline, day_intervals, CLUSTER_RANK, ClusterDay), shards=shards
				)
			)
		overall = combine(list(timelines.values()), window)
		return StatusHistory(overall=split_days(overall, day_intervals, CLUSTER_RANK, ClusterDay), clusters=clusters)

	async def cached_history(self, day_count: int) -> StatusHistory:
		"""Get the daily history, cached for 5 minutes per day count.

		Args:
			day_count: How many days, today included.

		Returns:
			The history.
		"""
		return await self._history_cache.get(day_count, lambda: self.history(day_count, datetime.now(UTC)))
