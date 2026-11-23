"""Media alerts: the bot's Internal API operations."""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.db

GUILD = 100
URL = f"/internal/guilds/{GUILD}/alerts"


async def add(api, account: str = "creator", channel: int = 1, **fields) -> dict:
	body = {"platform": "YouTube", "channel_account": account, "target_channel_id": str(channel), **fields}
	response = await api.client.post(URL, json=body, headers=api.internal)
	assert response.status_code == 201, response.text
	return response.json()


async def test_adding_lowercases_the_platform_and_re_adding_enables_again(api):
	alert = await add(api, account_id="UC1")
	await api.client.put(f"{URL}/{alert['id']}/enabled", json={"enabled": False}, headers=api.internal)

	again = await add(api, account_id="UC2", account_name="Creator")

	assert alert["platform"] == "youtube"
	assert again["id"] == alert["id"]
	assert again["enabled"] is True
	assert again["account_id"] == "UC2"
	assert (await api.client.get(URL, headers=api.internal)).json() == [again]


async def test_a_guild_has_at_most_five_alerts(api):
	results = await asyncio.gather(
		*(
			api.client.post(
				URL,
				json={"platform": "twitch", "channel_account": f"c{i}", "target_channel_id": "1"},
				headers=api.internal,
			)
			for i in range(7)
		)
	)

	assert sorted(r.status_code for r in results) == [201] * 5 + [409] * 2


async def test_removing_by_id_and_by_account(api):
	first = await add(api, account="Creator")
	await add(api, account="other", account_id="creator", channel=2)
	await add(api, account="third", channel=3)

	by_account = await api.client.delete(
		URL, params={"platform": "YOUTUBE", "account": "CREATOR"}, headers=api.internal
	)
	by_id = await api.client.delete(f"{URL}/{first['id']}", headers=api.internal)

	assert by_account.json() == {"removed": 2}
	assert by_id.status_code == 404
	assert [a["channel_account"] for a in (await api.client.get(URL, headers=api.internal)).json()] == ["third"]


async def test_polling_lists_accounts_and_subscribers_and_records_media(api):
	alert = await add(api, account="creator", account_id="UC1")
	await add(api, account="creator", account_id="UC1", channel=2)
	disabled = await add(api, account="quiet", channel=3)
	await api.client.put(f"{URL}/{disabled['id']}/enabled", json={"enabled": False}, headers=api.internal)

	accounts = (await api.client.get("/internal/alerts/accounts", headers=api.internal)).json()
	subscribers = (
		await api.client.get(
			"/internal/alerts/subscribers",
			params={"platform": "youtube", "channel_account": "x", "account_id": "UC1"},
			headers=api.internal,
		)
	).json()
	await api.client.put(f"/internal/alerts/{alert['id']}/last-media", json={"media_id": "v1"}, headers=api.internal)
	await api.client.post(
		"/internal/alerts/baseline",
		json={"platform": "youtube", "channel_account": "creator", "account_id": "UC1", "media_id": "offline"},
		headers=api.internal,
	)

	stored = {
		a["target_channel_id"]: a["last_media_id"] for a in (await api.client.get(URL, headers=api.internal)).json()
	}
	assert accounts == [
		{"platform": "youtube", "channel_account": "creator", "account_id": "UC1", "account_name": None}
	]
	assert len(subscribers) == 2
	assert stored == {"1": "v1", "2": "offline", "3": None}


async def test_alerts_belong_to_their_guild(api):
	alert = await add(api)

	assert (await api.client.get(f"/internal/guilds/999/alerts/{alert['id']}", headers=api.internal)).status_code == 404
	assert (
		await api.client.put(
			f"/internal/guilds/999/alerts/{alert['id']}/enabled", json={"enabled": False}, headers=api.internal
		)
	).status_code == 404
