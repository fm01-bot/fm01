"""The status page: shard health the bot reports, and the shard and cluster statuses the Public API derives from it."""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

__all__ = (
	"HEALTH_KEY",
	"SHARDS_PER_CLUSTER_KEY",
	"SHARDS_TOTAL_KEY",
	"ClusterDay",
	"ClusterHistory",
	"ClusterState",
	"ClusterStatus",
	"ShardDay",
	"ShardHealth",
	"ShardHistory",
	"ShardState",
	"ShardStatus",
	"Status",
	"StatusHistory",
)

SHARDS_TOTAL_KEY = "fm01:shards:total"
"""Redis key holding the bot's shard count."""
SHARDS_PER_CLUSTER_KEY = "fm01:shards:per_cluster"
"""Redis key holding the size of a status block."""
HEALTH_KEY = "fm01:shards:health"
"""Redis hash of shard ID -> `ShardHealth` JSON."""


class ShardHealth(BaseModel):
	"""What a bot process reports about one of its shards, every 10 seconds. Raw facts; the API decides the status."""

	shard_id: int
	cluster_id: str
	"""The reporting process. Internal: never published."""
	latency_ms: float | None
	"""Gateway heartbeat round trip. ``None`` before the first heartbeat is acknowledged."""
	guild_count: int
	ready: bool
	"""Whether the shard received READY (or resumed) and hasn't disconnected since."""
	closed: bool
	"""Whether the shard's gateway socket is closed."""
	ratelimited: bool
	"""Whether the shard is held back by the gateway's send rate limit."""
	updated_at: datetime


class ShardStatus(StrEnum):
	"""How a shard is doing."""

	OPERATIONAL = "operational"
	LAGGING = "lagging"
	"""Slow heartbeats, not ready, or gateway rate limited."""
	UNRESPONSIVE = "unresponsive"
	"""No recent report, a closed socket, or heartbeats past the timeout."""


class ClusterStatus(StrEnum):
	"""How a status block of shards, or the whole bot, is doing."""

	OPERATIONAL = "operational"
	PARTIALLY_OPERATIONAL = "partially_operational"
	"""Some shards are lagging."""
	PARTIALLY_UNRESPONSIVE = "partially_unresponsive"
	"""Some shards are unresponsive."""
	UNRESPONSIVE = "unresponsive"
	"""Every shard is unresponsive, or more than half are lagging or unresponsive."""


class ShardState(BaseModel):
	"""A shard on the status page."""

	id: int
	status: ShardStatus
	latency_ms: float | None
	guild_count: int | None
	"""``None`` if the shard never reported."""


class ClusterState(BaseModel):
	"""A status block on the status page."""

	id: int
	"""The block's position: block ``n`` holds shards ``n * size`` up to ``(n + 1) * size - 1``."""
	status: ClusterStatus
	shards: list[ShardState]


class Status(BaseModel):
	"""The bot's current status."""

	status: ClusterStatus
	"""Overall: the cluster rule applied to every shard."""
	checked_at: datetime
	clusters: list[ClusterState]


class ShardDay(BaseModel):
	"""One UTC day of a shard's history. Fractions cover the day, or its elapsed part for today, and sum to 1."""

	date: date
	worst: ShardStatus | Literal["no_data"]
	"""The worst status the shard had that day. ``no_data`` only if nothing was recorded all day."""
	operational: float
	lagging: float
	unresponsive: float
	no_data: float
	"""Time nothing was recorded, e.g. while the API was down."""


class ClusterDay(BaseModel):
	"""One UTC day of a status block's (or the whole bot's) history. Fractions sum to 1."""

	date: date
	worst: ClusterStatus | Literal["no_data"]
	operational: float
	partially_operational: float
	partially_unresponsive: float
	unresponsive: float
	no_data: float


class ShardHistory(BaseModel):
	"""A shard's daily history, oldest day first."""

	id: int
	days: list[ShardDay]


class ClusterHistory(BaseModel):
	"""A status block's daily history, oldest day first."""

	id: int
	days: list[ClusterDay]
	shards: list[ShardHistory]


class StatusHistory(BaseModel):
	"""The bot's daily history, oldest day first. Blocks are today's layout."""

	overall: list[ClusterDay]
	clusters: list[ClusterHistory]
