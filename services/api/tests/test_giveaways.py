"""Giveaways: the bot's Internal API operations."""

from __future__ import annotations

import asyncio
import datetime

import pytest

pytestmark = pytest.mark.db

GUILD, CHANNEL, HOST = 100, 2001, 10
ENDS = (datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(hours=1)).isoformat()


async def start(api, **fields) -> dict:
	body = {"channel_id": str(CHANNEL), "host_id": str(HOST), "prize": "nitro", "winner_count": 1, "ends_at": ENDS}
	response = await api.client.post(
		f"/internal/guilds/{GUILD}/giveaways", json={**body, **fields}, headers=api.internal
	)
	assert response.status_code == 201, response.text
	return response.json()


async def test_starting_posting_and_finding_a_giveaway(api):
	giveaway = await start(api, required_messages=5)
	posted = await api.client.put(
		f"/internal/giveaways/{giveaway['id']}/message", json={"message_id": "555"}, headers=api.internal
	)

	by_message = await api.client.get(
		f"/internal/channels/{CHANNEL}/giveaway", params={"status": "active", "message_id": "555"}, headers=api.internal
	)
	latest = await api.client.get(
		f"/internal/channels/{CHANNEL}/giveaway", params={"status": "active"}, headers=api.internal
	)
	ended = await api.client.get(
		f"/internal/channels/{CHANNEL}/giveaway", params={"status": "ended"}, headers=api.internal
	)
	active = (await api.client.get("/internal/giveaways/active", headers=api.internal)).json()

	assert giveaway["status"] == "active"
	assert giveaway["message_id"] is None
	assert posted.json()["message_id"] == "555"
	assert by_message.json()["id"] == giveaway["id"]
	assert latest.json()["id"] == giveaway["id"]
	assert ended.status_code == 404
	assert [g["id"] for g in active] == [giveaway["id"]]


async def test_a_guild_runs_at_most_25_active_giveaways(api):
	results = await asyncio.gather(
		*(
			api.client.post(
				f"/internal/guilds/{GUILD}/giveaways",
				json={"channel_id": "1", "host_id": "1", "prize": "x", "winner_count": 1, "ends_at": ENDS},
				headers=api.internal,
			)
			for _ in range(27)
		)
	)

	assert sorted(r.status_code for r in results) == [201] * 25 + [409] * 2
	assert {r.json()["code"] for r in results if r.status_code == 409} == {"giveaway_limit"}


async def test_ending_and_cancelling_happen_once(api):
	first, second = await start(api), await start(api)

	ended = await api.client.post(f"/internal/giveaways/{first['id']}/end", headers=api.internal)
	again = await api.client.post(f"/internal/giveaways/{first['id']}/cancel", headers=api.internal)
	cancelled = await api.client.post(f"/internal/giveaways/{second['id']}/cancel", headers=api.internal)

	assert ended.json()["status"] == "ended"
	assert ended.json()["ended_at"] is not None
	assert again.status_code == 404
	assert cancelled.json()["status"] == "cancelled"


async def test_entries_winners_and_rerolls(api):
	giveaway = await start(api)
	base = f"/internal/giveaways/{giveaway['id']}/entries"

	joined = [await api.client.put(f"{base}/{user}", headers=api.internal) for user in (1, 2, 1)]
	left = await api.client.delete(f"{base}/2", headers=api.internal)
	not_entered = await api.client.delete(f"{base}/2", headers=api.internal)
	await api.client.put(f"{base}/3", headers=api.internal)
	await api.client.post(
		f"/internal/giveaways/{giveaway['id']}/winners", json={"user_ids": ["1"]}, headers=api.internal
	)

	assert [r.json()["changed"] for r in joined] == [True, True, False]
	assert left.json() == {"changed": True}
	assert not_entered.json() == {"changed": False}
	assert (await api.client.get(f"{base}/count", headers=api.internal)).json() == {"count": 2}
	assert (await api.client.get(base, headers=api.internal)).json() == {"user_ids": ["3"]}
	assert (await api.client.get(f"{base}/1", headers=api.internal)).json() == {"entered": True, "messages": 0}
	assert (await api.client.get(f"{base}/2", headers=api.internal)).json() == {"entered": False, "messages": 0}


async def test_message_counts_add_up_and_skip_unknown_giveaways(api):
	giveaway = await start(api, required_messages=3)
	gid = giveaway["id"]
	batch = [
		{"giveaway_id": gid, "user_id": "1", "count": 2},
		{"giveaway_id": gid, "user_id": "1", "count": 1},
		{"giveaway_id": 999, "user_id": "1", "count": 4},
	]

	first = await api.client.post("/internal/giveaways/message-counts", json=batch, headers=api.internal)
	await api.client.post("/internal/giveaways/message-counts", json=batch[:1], headers=api.internal)

	assert first.status_code == 204
	assert (await api.client.get(f"/internal/giveaways/{gid}/message-counts", headers=api.internal)).json() == [
		{"giveaway_id": gid, "user_id": "1", "count": 5}
	]
	assert (await api.client.get(f"/internal/giveaways/{gid}/entries/1", headers=api.internal)).json()["messages"] == 5


async def test_purge_drops_old_entries_of_finished_giveaways_only(api):
	old, fresh = await start(api), await start(api)
	for giveaway in (old, fresh):
		await api.client.put(f"/internal/giveaways/{giveaway['id']}/entries/1", headers=api.internal)
		await api.client.post(f"/internal/giveaways/{giveaway['id']}/end", headers=api.internal)
	await api.db.execute("UPDATE giveaways SET ended_at = now() - interval '31 days' WHERE id = $1", old["id"])

	await api.client.post("/internal/giveaways/purge", headers=api.internal)

	assert (await api.client.get(f"/internal/giveaways/{old['id']}/entries/count", headers=api.internal)).json() == {
		"count": 0
	}
	assert (await api.client.get(f"/internal/giveaways/{fresh['id']}/entries/count", headers=api.internal)).json() == {
		"count": 1
	}


async def test_deleting_a_giveaway(api):
	giveaway = await start(api)

	await api.client.delete(f"/internal/giveaways/{giveaway['id']}", headers=api.internal)

	assert (await api.client.get(f"/internal/giveaways/{giveaway['id']}", headers=api.internal)).status_code == 404
