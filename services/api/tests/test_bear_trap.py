"""Bear trap: the bot's Internal API operations and the guild manager's Dashboard API."""

from __future__ import annotations

import asyncio

import pytest
from app.dashboard.access import BAN_MEMBERS, MANAGE_GUILD

pytestmark = pytest.mark.db

GUILD, OTHER_GUILD = 200, 300
TEXT, VOICE, ELSEWHERE = 2001, 2002, 3001
URL = f"/internal/guilds/{GUILD}/settings/bear-trap"


@pytest.fixture
def discord(api):
	fake = api.discord
	fake.codes["code"] = "access"
	fake.users["access"] = {"id": "1", "username": "alice", "global_name": None, "avatar": None}
	fake.guilds["access"] = [
		{
			"id": str(GUILD),
			"name": "Managed",
			"icon": None,
			"owner": False,
			"permissions": str(MANAGE_GUILD | BAN_MEMBERS),
		},
	]
	fake.bot_guilds = {GUILD, OTHER_GUILD}
	fake.channels = {
		TEXT: {"id": str(TEXT), "guild_id": str(GUILD), "type": 0},
		VOICE: {"id": str(VOICE), "guild_id": str(GUILD), "type": 2},
		ELSEWHERE: {"id": str(ELSEWHERE), "guild_id": str(OTHER_GUILD), "type": 0},
	}
	return fake


async def sign_in(api) -> dict[str, str]:
	response = await api.client.post(
		"/dashboard/auth/exchange", json={"code": "code", "redirect_uri": "https://dashboard.example/callback"}
	)
	assert response.status_code == 200, response.text
	return {"Authorization": f"Bearer {response.json()['token']}"}


async def test_a_guild_without_a_trap_is_off_with_no_kicks(api):
	response = await api.client.get(URL, headers=api.internal)

	assert response.json() == {"channel_id": None, "kicks": 0, "message_channel_id": None, "message_id": None}


async def test_setting_the_channel_persists_and_announces_with_the_origin(api, events):
	response = await api.client.put(
		URL, json={"channel_id": str(TEXT)}, headers={**api.internal, "X-Fm01-Origin": "instance-a"}
	)

	assert response.json()["channel_id"] == str(TEXT)
	assert await events.drain() == [
		{"type": "INVALIDATE_SETTING", "key": "bear_trap", "guild_id": str(GUILD), "origin": "instance-a"}
	]


async def test_all_lists_traps_that_are_on_or_still_have_a_message(api):
	await api.client.put(URL, json={"channel_id": str(TEXT)}, headers=api.internal)
	await api.client.put(
		f"/internal/guilds/{OTHER_GUILD}/settings/bear-trap/message",
		json={"message_channel_id": str(ELSEWHERE), "message_id": "9"},
		headers=api.internal,
	)
	await api.client.post("/internal/guilds/400/settings/bear-trap/kicks", headers=api.internal)

	traps = (await api.client.get("/internal/settings/bear-trap", headers=api.internal)).json()

	assert sorted((t["guild_id"], t["channel_id"], t["message_id"]) for t in traps) == [
		(str(GUILD), str(TEXT), None),
		(str(OTHER_GUILD), None, "9"),
	]


async def test_the_message_is_recorded_and_cleared(api):
	message_url = f"{URL}/message"
	await api.client.put(URL, json={"channel_id": str(TEXT)}, headers=api.internal)

	posted = await api.client.put(
		message_url, json={"message_channel_id": str(TEXT), "message_id": "55"}, headers=api.internal
	)
	cleared = await api.client.put(
		message_url, json={"message_channel_id": None, "message_id": None}, headers=api.internal
	)

	assert posted.json() == {"channel_id": str(TEXT), "kicks": 0, "message_channel_id": str(TEXT), "message_id": "55"}
	assert cleared.json()["message_id"] is None
	assert cleared.json()["channel_id"] == str(TEXT)


async def test_concurrent_kicks_are_all_counted(api):
	responses = await asyncio.gather(*(api.client.post(f"{URL}/kicks", headers=api.internal) for _ in range(10)))

	assert sorted(r.json()["kicks"] for r in responses) == list(range(1, 11))


async def test_kicks_survive_moving_and_turning_off_the_trap(api):
	await api.client.put(URL, json={"channel_id": str(TEXT)}, headers=api.internal)
	await api.client.post(f"{URL}/kicks", headers=api.internal)
	await api.client.put(URL, json={"channel_id": None}, headers=api.internal)
	await api.client.put(URL, json={"channel_id": "2003"}, headers=api.internal)

	assert (await api.client.get(URL, headers=api.internal)).json()["kicks"] == 1


async def test_manager_sets_a_text_channel_and_the_bot_is_told(api, discord, events):
	auth = await sign_in(api)

	response = await api.client.put(
		f"/dashboard/guilds/{GUILD}/settings/bear-trap", json={"channel_id": str(TEXT)}, headers=auth
	)

	assert response.json() == {"channel_id": str(TEXT), "kicks": 0}
	assert await events.drain() == [
		{"type": "INVALIDATE_SETTING", "key": "bear_trap", "guild_id": str(GUILD), "origin": None}
	]
	assert (await api.client.get(f"/dashboard/guilds/{GUILD}/settings/bear-trap", headers=auth)).json() == {
		"channel_id": str(TEXT),
		"kicks": 0,
	}


@pytest.mark.parametrize("channel", [VOICE, ELSEWHERE, 404])
async def test_manager_cannot_set_a_channel_that_is_not_a_text_channel_in_the_guild(api, discord, events, channel):
	auth = await sign_in(api)

	response = await api.client.put(
		f"/dashboard/guilds/{GUILD}/settings/bear-trap", json={"channel_id": str(channel)}, headers=auth
	)

	assert response.status_code == 422
	assert response.json()["code"] == "invalid_channel"
	assert await events.drain() == []


async def test_manager_turns_the_trap_off_without_a_channel_lookup(api, discord):
	auth = await sign_in(api)
	discord.calls.clear()

	response = await api.client.put(
		f"/dashboard/guilds/{GUILD}/settings/bear-trap", json={"channel_id": None}, headers=auth
	)

	assert response.json() == {"channel_id": None, "kicks": 0}
	assert not any(call.startswith("GET /channels/") for call in discord.calls)


async def test_manage_server_alone_cannot_set_the_trap(api, discord, events):
	discord.guilds["access"][0]["permissions"] = str(MANAGE_GUILD)
	auth = await sign_in(api)

	response = await api.client.put(
		f"/dashboard/guilds/{GUILD}/settings/bear-trap", json={"channel_id": str(TEXT)}, headers=auth
	)

	assert response.status_code == 403
	assert await events.drain() == []
	assert (await api.client.get(f"/dashboard/guilds/{GUILD}/settings/bear-trap", headers=auth)).status_code == 200
