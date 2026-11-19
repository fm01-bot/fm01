"""The status rules, the history timelines, and the Public API status routes."""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta

import fakeredis
import pytest
from api import (
	HEALTH_KEY,
	SHARDS_PER_CLUSTER_KEY,
	SHARDS_TOTAL_KEY,
	ClusterDay,
	ClusterStatus,
	ShardDay,
	ShardHealth,
	ShardStatus,
)
from app.errors import ApiError
from app.ratelimit import RateLimiter
from app.status.history import CLUSTER_RANK, NO_DATA, SHARD_RANK, Segment, combine, days, shard_timeline, split_days
from app.status.rules import blocks, cluster_status, shard_status
from app.status.store import StatusStore
from tests.conftest import Api

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
O, L, U = ShardStatus.OPERATIONAL, ShardStatus.LAGGING, ShardStatus.UNRESPONSIVE


def health(shard_id: int = 0, at: datetime = NOW, **facts) -> ShardHealth:
	values = {"latency_ms": 40.0, "guild_count": 10, "ready": True, "closed": False, "ratelimited": False} | facts
	return ShardHealth(shard_id=shard_id, cluster_id="cluster-x", updated_at=at, **values)


@pytest.mark.parametrize(
	("report", "expected"),
	[
		(None, U),
		(health(), O),
		(health(latency_ms=None), O),
		(health(at=NOW - timedelta(seconds=31)), U),
		(health(at=NOW - timedelta(seconds=30)), O),
		(health(closed=True), U),
		(health(latency_ms=10_000), U),
		(health(latency_ms=1_000), L),
		(health(ready=False), L),
		(health(ratelimited=True), L),
	],
)
def test_shard_status(report: ShardHealth | None, expected: ShardStatus) -> None:
	assert shard_status(report, NOW) is expected


@pytest.mark.parametrize(
	("statuses", "expected"),
	[
		([O, O, O, O], ClusterStatus.OPERATIONAL),
		([O, O, O, L], ClusterStatus.PARTIALLY_OPERATIONAL),
		([O, O, L, U], ClusterStatus.PARTIALLY_UNRESPONSIVE),
		([O, O, O, U], ClusterStatus.PARTIALLY_UNRESPONSIVE),
		([O, L, L, L], ClusterStatus.UNRESPONSIVE),
		([O, O, L, L], ClusterStatus.PARTIALLY_OPERATIONAL),
		([U], ClusterStatus.UNRESPONSIVE),
		([], ClusterStatus.UNRESPONSIVE),
	],
)
def test_cluster_status(statuses: list[ShardStatus], expected: ClusterStatus) -> None:
	assert cluster_status(statuses) is expected


def test_blocks() -> None:
	assert blocks(5, 2) == [range(2), range(2, 4), range(4, 5)]
	assert blocks(4, 0) == [range(4)]
	assert blocks(0, 16) == []


def test_shard_timeline_fills_gaps_with_no_data() -> None:
	t = [NOW + timedelta(hours=h) for h in range(6)]
	changes = [(t[0] - timedelta(days=1), O), (t[2], L)]
	coverage = [(t[0], t[3]), (t[4], t[5])]
	assert shard_timeline(changes, coverage, (t[0], t[5])) == [
		Segment(t[0], t[2], "operational"),
		Segment(t[2], t[3], "lagging"),
		Segment(t[3], t[4], NO_DATA),
		Segment(t[4], t[5], "lagging"),
	]


def test_shard_timeline_without_changes_is_no_data() -> None:
	window = (NOW, NOW + timedelta(hours=1))
	assert shard_timeline([], [window], window) == [Segment(*window, NO_DATA)]


def test_combine_applies_the_cluster_rule_and_skips_shards_without_data() -> None:
	t = [NOW + timedelta(hours=h) for h in range(3)]
	a = [Segment(t[0], t[1], "operational"), Segment(t[1], t[2], "unresponsive")]
	b = [Segment(t[0], t[2], "operational")]
	c = [Segment(t[0], t[2], NO_DATA)]
	assert combine([a, b, c], (t[0], t[2])) == [
		Segment(t[0], t[1], "operational"),
		Segment(t[1], t[2], "partially_unresponsive"),  # one of the two shards with data; c is left out
	]
	assert combine([c], (t[0], t[2])) == [Segment(t[0], t[2], NO_DATA)]


def test_days_end_now() -> None:
	assert days(2, NOW) == [
		(datetime(2026, 11, 18, tzinfo=UTC), datetime(2026, 11, 19, tzinfo=UTC)),
		(datetime(2026, 11, 19, tzinfo=UTC), NOW),
	]


def test_split_days_measures_fractions_and_the_worst_status() -> None:
	day = days(1, NOW)
	start = day[0][0]
	timeline = [
		Segment(start, start + timedelta(hours=3), NO_DATA),
		Segment(start + timedelta(hours=3), start + timedelta(hours=9), "operational"),
		Segment(start + timedelta(hours=9), NOW, "lagging"),
	]
	(entry,) = split_days(timeline, day, SHARD_RANK, ShardDay)
	assert entry == ShardDay(
		date=date(2026, 11, 19), worst=L, operational=0.5, lagging=0.25, unresponsive=0.0, no_data=0.25
	)
	(empty,) = split_days([Segment(start, NOW, NO_DATA)], day, CLUSTER_RANK, ClusterDay)
	assert empty.worst == NO_DATA and empty.no_data == 1.0


async def report(api: Api, total: int, size: int, *reports: ShardHealth) -> None:
	await api.redis.mset({SHARDS_TOTAL_KEY: total, SHARDS_PER_CLUSTER_KEY: size})
	if reports:
		await api.redis.hset(HEALTH_KEY, mapping={str(r.shard_id): r.model_dump_json() for r in reports})


async def test_status_groups_shards_into_blocks(api: Api) -> None:
	now = datetime.now(UTC)
	await report(
		api,
		4,
		2,
		health(0, now),
		health(1, now, latency_ms=1500),
		health(2, now, closed=True),
		health(3, now - timedelta(minutes=5)),
	)

	response = await api.client.get("/public/status")

	assert response.status_code == 200
	body = response.json()
	assert body["status"] == "unresponsive"  # 3 of 4 shards are lagging or unresponsive
	assert [(c["id"], c["status"]) for c in body["clusters"]] == [(0, "partially_operational"), (1, "unresponsive")]
	assert body["clusters"][0]["shards"][1] == {"id": 1, "status": "lagging", "latency_ms": 1500.0, "guild_count": 10}
	assert "cluster_id" not in body["clusters"][0]["shards"][0]


async def test_status_without_a_bot_has_no_clusters(api: Api) -> None:
	body = (await api.client.get("/public/status")).json()
	assert body["status"] == "unresponsive"
	assert body["clusters"] == []


async def test_status_lists_shards_that_never_reported(api: Api) -> None:
	await report(api, 2, 16, health(0, datetime.now(UTC)))
	shards = (await api.client.get("/public/status")).json()["clusters"][0]["shards"]
	assert shards[1] == {"id": 1, "status": "unresponsive", "latency_ms": None, "guild_count": None}


async def test_status_is_rate_limited_per_ip(api: Api) -> None:
	# Fill this window and the next, so the test can't straddle a window boundary.
	window = int(time.time() // 60)
	for w in (window, window + 1):
		await api.redis.set(f"fm01:ratelimit:status:127.0.0.1:{w}", 60)

	response = await api.client.get("/public/status")

	assert response.status_code == 429
	assert response.json()["code"] == "rate_limited"
	assert 1 <= int(response.headers["Retry-After"]) <= 60


async def test_rate_limiter_counts_per_window_and_scope() -> None:
	redis = fakeredis.FakeAsyncRedis()
	now = [120.0]
	limiter = RateLimiter(redis, clock=lambda: now[0])
	await limiter.hit("a", "1.2.3.4", 2)
	await limiter.hit("a", "1.2.3.4", 2)
	await limiter.hit("b", "1.2.3.4", 2)
	await limiter.hit("a", "5.6.7.8", 2)
	now[0] = 150.0
	with pytest.raises(ApiError) as error:
		await limiter.hit("a", "1.2.3.4", 2)
	assert error.value.headers == {"Retry-After": "30"}
	now[0] = 180.0
	await limiter.hit("a", "1.2.3.4", 2)
	await redis.aclose()


async def test_history_records_changes_and_gaps(api: Api) -> None:
	store = StatusStore(api.db, api.redis, timedelta(seconds=30))
	day_start = datetime(2026, 11, 19, tzinfo=UTC)
	await report(api, 2, 1)

	async def sample(at: datetime, *reports: ShardHealth) -> None:
		await api.redis.hset(HEALTH_KEY, mapping={str(r.shard_id): r.model_dump_json() for r in reports})
		await store.sample(at)

	# 00:00 to 06:00 both fine; shard 1 lags from 06:00; the API is down 09:00 to 12:00 (new store = new run).
	for minutes in range(0, 9 * 60, 1):
		at = day_start + timedelta(minutes=minutes)
		lagging = minutes >= 6 * 60
		await sample(at, health(0, at), health(1, at, ready=not lagging))
	restarted = StatusStore(api.db, api.redis, timedelta(seconds=30))
	at = day_start + timedelta(hours=12)
	await api.redis.hset(
		HEALTH_KEY, mapping={"0": health(0, at).model_dump_json(), "1": health(1, at).model_dump_json()}
	)
	await restarted.sample(at)

	assert await api.db.fetchval("SELECT count(*) FROM shard_status_changes") == 4  # 2 first samples, 1 lag, 1 recovery

	history = await restarted.history(1, day_start + timedelta(hours=12, seconds=30))
	shard1 = history.clusters[1].shards[0].days[0]
	day = 12 * 3600 + 30
	assert shard1.worst is L
	assert shard1.operational == pytest.approx((6 * 3600 + 30) / day, abs=1e-5)
	assert shard1.lagging == pytest.approx((3 * 3600 - 30) / day, abs=1e-5)
	assert shard1.no_data == pytest.approx((3 * 3600 + 30) / day, abs=1e-5)
	assert history.clusters[1].days[0].worst is ClusterStatus.UNRESPONSIVE  # its only shard lags
	assert history.overall[0].worst is ClusterStatus.PARTIALLY_OPERATIONAL


async def test_prune_keeps_the_last_change_before_the_cutoff(api: Api) -> None:
	store = StatusStore(api.db, api.redis, timedelta(seconds=30))
	await api.db.executemany(
		"INSERT INTO shard_status_changes (shard_id, changed_at, status) VALUES (0, $1, $2)",
		[(NOW - timedelta(days=120), "lagging"), (NOW - timedelta(days=100), "operational"), (NOW, "lagging")],
	)
	await store.prune(NOW)
	rows = await api.db.fetch("SELECT changed_at FROM shard_status_changes ORDER BY changed_at")
	assert [row["changed_at"] for row in rows] == [NOW - timedelta(days=100), NOW]


async def test_history_route_validates_days(api: Api) -> None:
	assert (await api.client.get("/public/status/history?days=91")).status_code == 422
	response = await api.client.get("/public/status/history?days=3")
	assert response.status_code == 200
	assert len(response.json()["overall"]) == 3
