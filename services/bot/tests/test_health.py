from __future__ import annotations

import datetime
from typing import Self, cast

import discord
import pytest
import redis.asyncio as aioredis
from core.clustering import HealthReporter, shard_health

from api import HEALTH_KEY, SHARDS_PER_CLUSTER_KEY, SHARDS_TOTAL_KEY, ShardHealth

NOW = datetime.datetime(2026, 11, 19, 12, tzinfo=datetime.UTC)


class _FakeShard:
	def __init__(self, latency: float, closed: bool = False, ratelimited: bool = False) -> None:
		self.id = 3
		self.latency = latency
		self._closed = closed
		self._ratelimited = ratelimited

	def is_closed(self) -> bool:
		return self._closed

	def is_ws_ratelimited(self) -> bool:
		return self._ratelimited


def _health(shard: _FakeShard, ready: bool = True) -> ShardHealth:
	return shard_health(cast(discord.ShardInfo, shard), "cluster-a", 7, ready, NOW)


def test_shard_health_reports_raw_facts():
	assert _health(_FakeShard(0.0421, ratelimited=True)) == ShardHealth(
		shard_id=3,
		cluster_id="cluster-a",
		latency_ms=42.1,
		guild_count=7,
		ready=True,
		closed=False,
		ratelimited=True,
		updated_at=NOW,
	)


def test_shard_health_without_a_heartbeat_has_no_latency():
	assert _health(_FakeShard(float("inf"))).latency_ms is None


def test_closed_shard_is_neither_ready_nor_ratelimited():
	health = _health(_FakeShard(0.05, closed=True, ratelimited=True))
	assert (health.closed, health.ready, health.ratelimited) == (True, False, False)


class _FakePipeline:
	def __init__(self, data: dict) -> None:
		self.data = data

	async def __aenter__(self) -> Self:
		return self

	async def __aexit__(self, *_) -> None:
		pass

	def mset(self, mapping: dict) -> None:
		self.data.update(mapping)

	def hset(self, key: str, mapping: dict) -> None:
		self.data.setdefault(key, {}).update(mapping)

	async def execute(self) -> None:
		pass


class _FakeRedis:
	def __init__(self) -> None:
		self.data: dict = {}

	def pipeline(self, transaction: bool = True) -> _FakePipeline:
		return _FakePipeline(self.data)


@pytest.mark.asyncio
async def test_reporter_writes_layout_and_reports():
	redis = _FakeRedis()
	reporter = HealthReporter(cast(aioredis.Redis, redis))
	health = _health(_FakeShard(0.05))
	await reporter.report(8, 4, [health])
	assert redis.data[SHARDS_TOTAL_KEY] == 8
	assert redis.data[SHARDS_PER_CLUSTER_KEY] == 4
	assert ShardHealth.model_validate_json(redis.data[HEALTH_KEY]["3"]) == health
