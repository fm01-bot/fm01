"""The status rules: shard health to shard status, shard statuses to a cluster status, and the status block layout."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

from api import ClusterStatus, ShardHealth, ShardStatus

__all__ = (
	"LAGGING_LATENCY_MS",
	"STALE_AFTER",
	"UNRESPONSIVE_LATENCY_MS",
	"blocks",
	"cluster_status",
	"shard_status",
)

STALE_AFTER = timedelta(seconds=30)
"""A shard with no report for longer than this (three missed 10-second reports) is unresponsive."""
UNRESPONSIVE_LATENCY_MS = 10_000
"""Heartbeat latency at which a shard counts as unresponsive."""
LAGGING_LATENCY_MS = 1_000
"""Heartbeat latency at which a shard counts as lagging."""


def shard_status(health: ShardHealth | None, now: datetime) -> ShardStatus:
	"""Decide a shard's status from its latest report.

	Args:
		health: The shard's latest report. ``None`` if it never reported.
		now: The current time.

	Returns:
		Unresponsive without a report in the last 30 s, with a closed socket, or at 10 s latency or more. Lagging at 1 s
		latency or more, when not ready, or when gateway rate limited. Operational otherwise.
	"""
	if health is None or now - health.updated_at > STALE_AFTER or health.closed:
		return ShardStatus.UNRESPONSIVE
	if health.latency_ms is not None and health.latency_ms >= UNRESPONSIVE_LATENCY_MS:
		return ShardStatus.UNRESPONSIVE
	if (
		not health.ready
		or health.ratelimited
		or (health.latency_ms is not None and health.latency_ms >= LAGGING_LATENCY_MS)
	):
		return ShardStatus.LAGGING
	return ShardStatus.OPERATIONAL


def cluster_status(statuses: Iterable[ShardStatus]) -> ClusterStatus:
	"""Decide the status of a group of shards: a status block, or every shard for the overall status.

	Args:
		statuses: The shards' statuses.

	Returns:
		Unresponsive if every shard is unresponsive or more than half are lagging or unresponsive (so an empty group is
		unresponsive). Otherwise partially unresponsive if any shard is unresponsive, partially operational if any is
		lagging, and operational if none is.
	"""
	statuses = list(statuses)
	unresponsive = statuses.count(ShardStatus.UNRESPONSIVE)
	lagging = statuses.count(ShardStatus.LAGGING)
	if unresponsive == len(statuses) or (unresponsive + lagging) * 2 > len(statuses):
		return ClusterStatus.UNRESPONSIVE
	if unresponsive:
		return ClusterStatus.PARTIALLY_UNRESPONSIVE
	if lagging:
		return ClusterStatus.PARTIALLY_OPERATIONAL
	return ClusterStatus.OPERATIONAL


def blocks(total: int, size: int) -> list[range]:
	"""Split the shards into status blocks.

	Args:
		total: The shard count.
		size: Shards per block. Values below 1 count as one block of every shard.

	Returns:
		Block ``n`` holds shards ``n * size`` up to ``(n + 1) * size - 1``; the last block may be smaller.
	"""
	if size < 1:
		size = max(total, 1)
	return [range(start, min(start + size, total)) for start in range(0, total, size)]
