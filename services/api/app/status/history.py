"""Status history as timelines: when each status held, and how much of each UTC day it covered."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from itertools import pairwise

from api import ClusterStatus, ShardStatus

from app.status.rules import cluster_status

__all__ = ("CLUSTER_RANK", "NO_DATA", "SHARD_RANK", "Segment", "combine", "days", "shard_timeline", "split_days")

NO_DATA = "no_data"
"""The status of time nothing was recorded."""

type Interval = tuple[datetime, datetime]


@dataclass(frozen=True, slots=True)
class Segment:
	"""A stretch of time with one status, from ``start`` (inclusive) to ``end`` (exclusive)."""

	start: datetime
	end: datetime
	status: str


def _merge(segments: list[Segment]) -> list[Segment]:
	"""Join neighbouring segments with the same status.

	Args:
		segments: Contiguous segments, in order.

	Returns:
		The same timeline, with no two neighbours sharing a status.
	"""
	merged: list[Segment] = []
	for segment in segments:
		if merged and merged[-1].status == segment.status:
			merged[-1] = Segment(merged[-1].start, segment.end, segment.status)
		else:
			merged.append(segment)
	return merged


def shard_timeline(
	changes: Sequence[tuple[datetime, ShardStatus]], coverage: Sequence[Interval], window: Interval
) -> list[Segment]:
	"""Build a shard's timeline from its status changes.

	Args:
		changes: The shard's status changes, oldest first. Include the last one before the window.
		coverage: When the sampler was recording.
		window: The time to cover.

	Returns:
		Contiguous segments filling the window. Time outside the coverage, or before the shard's first change, is
		``no_data``.
	"""
	start, end = window
	times = [changed_at for changed_at, _ in changes]
	points = {start, end}
	points.update(t for t in times if start < t < end)
	points.update(p for interval in coverage for p in interval if start < p < end)
	ordered = sorted(points)
	segments = []
	for a, b in pairwise(ordered):
		index = bisect_right(times, a) - 1
		covered = any(c_start <= a < c_end for c_start, c_end in coverage)
		status = str(changes[index][1]) if covered and index >= 0 else NO_DATA
		segments.append(Segment(a, b, status))
	return _merge(segments)


def _status_at(timeline: list[Segment], starts: list[datetime], at: datetime) -> str:
	"""Look up the status a timeline has at a moment.

	Args:
		timeline: Contiguous segments.
		starts: The segments' start times.
		at: The moment, inside the timeline.

	Returns:
		The status of the segment holding the moment.
	"""
	return timeline[bisect_right(starts, at) - 1].status


def combine(timelines: Sequence[list[Segment]], window: Interval) -> list[Segment]:
	"""Build a group's timeline from its shards' timelines, with the cluster rule.

	Args:
		timelines: The shards' timelines, each filling the window.
		window: The time they cover.

	Returns:
		Contiguous segments filling the window. Shards without data are left out of the rule; time when no shard has
		data is ``no_data``.
	"""
	start, end = window
	starts = [[segment.start for segment in timeline] for timeline in timelines]
	ordered = sorted({start, end} | {s for shard_starts in starts for s in shard_starts if start < s < end})
	segments = []
	for a, b in pairwise(ordered):
		statuses = [
			_status_at(timeline, shard_starts, a) for timeline, shard_starts in zip(timelines, starts, strict=True)
		]
		known = [ShardStatus(status) for status in statuses if status != NO_DATA]
		segments.append(Segment(a, b, str(cluster_status(known)) if known else NO_DATA))
	return _merge(segments)


def days(count: int, now: datetime) -> list[Interval]:
	"""List the last UTC days, today included.

	Args:
		count: How many days.
		now: The current time. Today ends here.

	Returns:
		Each day's start and end, oldest first.
	"""
	today = datetime.combine(now.astimezone(UTC).date(), time(), UTC)
	result = [(today - timedelta(days=n), today - timedelta(days=n - 1)) for n in range(count - 1, 0, -1)]
	return [*result, (today, now)]


def split_days[T](
	timeline: list[Segment], day_intervals: Sequence[Interval], rank: Sequence[str], build: Callable[..., T]
) -> list[T]:
	"""Measure how much of each day a timeline spent in each status.

	Args:
		timeline: Contiguous segments covering every day.
		day_intervals: The days, from `days`.
		rank: Every status, ``no_data`` included, least severe first.
		build: Builds a day entry from ``date``, ``worst`` and one fraction per status (keyword arguments).

	Returns:
		One entry per day. ``worst`` is the most severe status with any time, ``no_data`` only if nothing else had any.
	"""
	result = []
	for day_start, day_end in day_intervals:
		spent = dict.fromkeys(rank, 0.0)
		for segment in timeline:
			overlap = (min(segment.end, day_end) - max(segment.start, day_start)).total_seconds()
			if overlap > 0:
				spent[segment.status] += overlap
		length = (day_end - day_start).total_seconds()
		if length <= 0:
			fractions = {status: 0.0 for status in rank} | {NO_DATA: 1.0}
		else:
			fractions = {status: round(seconds / length, 6) for status, seconds in spent.items()}
		worst = next((status for status in reversed(rank) if status != NO_DATA and spent[status] > 0), NO_DATA)
		result.append(build(date=day_start.date(), worst=worst, **fractions))
	return result


SHARD_RANK = (NO_DATA, *(str(status) for status in ShardStatus))
"""Shard statuses, least severe first."""
CLUSTER_RANK = (NO_DATA, *(str(status) for status in ClusterStatus))
"""Cluster statuses, least severe first."""
