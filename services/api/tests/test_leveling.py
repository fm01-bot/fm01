"""Leveling: XP, levels, configuration, role rewards and XP overrides."""

from __future__ import annotations

import asyncio

import pytest
from api import level_from_total_xp

pytestmark = pytest.mark.db

GUILD = 100
BASE = f"/internal/guilds/{GUILD}"


async def award(api, user: int, amount: int) -> dict:
	response = await api.client.post(f"{BASE}/levels/{user}/xp", json={"amount": amount}, headers=api.internal)
	assert response.status_code == 200, response.text
	return response.json()


def test_level_math():
	assert level_from_total_xp(0).level == 0
	assert level_from_total_xp(99).level == 0
	assert level_from_total_xp(100).level == 1
	assert level_from_total_xp(255).level == 2
	assert level_from_total_xp(254) == (1, 154, 155, 1)


async def test_awards_accumulate_and_report_level_ups(api):
	first = await award(api, 1, 60)
	second = await award(api, 1, 60)

	assert first == {"xp": 60, "level": 0, "previous_level": 0}
	assert second == {"xp": 120, "level": 1, "previous_level": 0}


async def test_concurrent_awards_all_count(api):
	await asyncio.gather(*(award(api, 1, 10) for _ in range(20)))

	member = (await api.client.get(f"{BASE}/levels/1", headers=api.internal)).json()

	assert member == {"user_id": "1", "xp": 200, "level": 1, "rank": 1}


async def test_rank_counts_members_with_more_xp(api):
	await award(api, 1, 500)
	await award(api, 2, 100)
	await award(api, 3, 100)

	assert (await api.client.get(f"{BASE}/levels/2", headers=api.internal)).json()["rank"] == 2
	assert (await api.client.get(f"{BASE}/levels/9", headers=api.internal)).json() == {
		"user_id": "9",
		"xp": 0,
		"level": 0,
		"rank": None,
	}


async def test_leaderboard_pages_by_xp(api):
	for user, xp in ((1, 50), (2, 300), (3, 150)):
		await award(api, user, xp)

	page = (
		await api.client.get(f"{BASE}/levels/leaderboard", params={"offset": 1, "limit": 1}, headers=api.internal)
	).json()

	assert page == {"total": 3, "entries": [{"user_id": "3", "xp": 150, "level": 1, "rank": 2}]}


async def test_lookup_returns_members_with_xp(api):
	await award(api, 1, 120)

	found = await api.client.post(f"{BASE}/levels/lookup", json={"user_ids": ["1", "2"]}, headers=api.internal)

	assert found.json() == [{"user_id": "1", "xp": 120, "level": 1, "rank": None}]


async def test_config_defaults_and_partial_updates(api, events):
	url = f"{BASE}/settings/leveling"
	defaults = (await api.client.get(url, headers=api.internal)).json()

	changed = await api.client.patch(
		url, json={"min_xp": 5, "message_mode": "channel", "message_channel_id": "7"}, headers=api.internal
	)
	cleared = await api.client.patch(url, json={"message_channel_id": None, "enabled": None}, headers=api.internal)

	assert defaults["enabled"] is True
	assert defaults["min_xp"] == 15
	assert changed.json()["min_xp"] == 5
	assert changed.json()["max_xp"] == 25
	assert changed.json()["message_channel_id"] == "7"
	assert cleared.json()["message_channel_id"] is None
	assert cleared.json()["enabled"] is True
	assert [e["key"] for e in await events.drain()] == ["level.config", "level.config"]


async def test_rewards_are_added_once_and_removed_by_level_or_role(api, events):
	url = f"{BASE}/settings/leveling/rewards"
	for level, role in ((5, 50), (5, 51), (5, 51), (2, 20)):
		await api.client.post(url, json={"level": level, "role_id": str(role)}, headers=api.internal)

	listed = (await api.client.get(url, headers=api.internal)).json()
	await api.client.delete(f"{url}/5", params={"role_id": "50"}, headers=api.internal)
	after_one = (await api.client.get(url, headers=api.internal)).json()
	await api.client.delete(f"{url}/5", headers=api.internal)
	after_all = (await api.client.get(url, headers=api.internal)).json()

	assert listed == [
		{"level": 2, "role_id": "20"},
		{"level": 5, "role_id": "50"},
		{"level": 5, "role_id": "51"},
	]
	assert after_one == [{"level": 2, "role_id": "20"}, {"level": 5, "role_id": "51"}]
	assert after_all == [{"level": 2, "role_id": "20"}]
	assert {e["key"] for e in await events.drain()} == {"level.rewards"}


async def test_overrides_keep_the_other_field(api):
	url = f"{BASE}/settings/leveling/overrides"

	ignored = await api.client.patch(f"{url}/channel/5", json={"ignored": True}, headers=api.internal)
	boosted = await api.client.patch(f"{url}/channel/5", json={"multiplier": 2.5}, headers=api.internal)
	await api.client.patch(f"{url}/role/6", json={"multiplier": 0.5}, headers=api.internal)

	assert ignored.json() == {"id": "5", "multiplier": 1.0, "ignored": True}
	assert boosted.json() == {"id": "5", "multiplier": 2.5, "ignored": True}
	assert (await api.client.get(url, headers=api.internal)).json() == {
		"channels": [{"id": "5", "multiplier": 2.5, "ignored": True}],
		"roles": [{"id": "6", "multiplier": 0.5, "ignored": False}],
	}
