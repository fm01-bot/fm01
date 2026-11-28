"""Suggestions: numbering, voting, decisions and the guild setting, through the Internal and Dashboard APIs."""

from __future__ import annotations

import asyncio

import pytest
from app.dashboard.access import MANAGE_GUILD

pytestmark = pytest.mark.db

GUILD, OTHER_GUILD = 200, 300
TEXT, VOICE, ELSEWHERE = 2001, 2002, 3001
CONFIG_URL = f"/internal/guilds/{GUILD}/settings/suggestions"
SUGGESTIONS_URL = f"/internal/guilds/{GUILD}/suggestions"


@pytest.fixture
def discord(api):
	fake = api.discord
	fake.codes["code"] = "access"
	fake.users["access"] = {"id": "1", "username": "alice", "global_name": None, "avatar": None}
	fake.guilds["access"] = [
		{"id": str(GUILD), "name": "Managed", "icon": None, "owner": False, "permissions": str(MANAGE_GUILD)},
		{"id": str(OTHER_GUILD), "name": "Other", "icon": None, "owner": False, "permissions": "0"},
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


async def enable(api, guild: int = GUILD) -> None:
	response = await api.client.put(
		f"/internal/guilds/{guild}/settings/suggestions", json={"channel_id": str(TEXT)}, headers=api.internal
	)
	assert response.status_code == 200, response.text


async def suggest(api, content: str = "More emoji", guild: int = GUILD) -> dict:
	response = await api.client.post(
		f"/internal/guilds/{guild}/suggestions", json={"author_id": "7", "content": content}, headers=api.internal
	)
	assert response.status_code == 200, response.text
	return response.json()


async def vote(api, user: int, vote: str, number: int = 1):
	return await api.client.post(
		f"{SUGGESTIONS_URL}/{number}/votes", json={"user_id": str(user), "vote": vote}, headers=api.internal
	)


async def decide(api, status: str = "approved", number: int = 1, **extra):
	return await api.client.post(
		f"{SUGGESTIONS_URL}/{number}/decision",
		json={"moderator_id": "5", "status": status, **extra},
		headers=api.internal,
	)


async def test_a_guild_without_the_setting_has_suggestions_off(api):
	response = await api.client.get(CONFIG_URL, headers=api.internal)

	assert response.json() == {"channel_id": None, "threads": False}


async def test_setting_the_config_persists_and_announces_with_the_origin(api, events):
	response = await api.client.put(
		CONFIG_URL,
		json={"channel_id": str(TEXT), "threads": True},
		headers={**api.internal, "X-Fm01-Origin": "instance-a"},
	)

	assert response.json() == {"channel_id": str(TEXT), "threads": True}
	assert (await api.client.get(CONFIG_URL, headers=api.internal)).json() == {"channel_id": str(TEXT), "threads": True}
	assert await events.drain() == [
		{"type": "INVALIDATE_SETTING", "key": "suggestions", "guild_id": str(GUILD), "origin": "instance-a"}
	]


async def test_suggestions_are_refused_while_the_guild_has_no_channel(api):
	response = await api.client.post(SUGGESTIONS_URL, json={"author_id": "7", "content": "Hi"}, headers=api.internal)

	assert response.status_code == 409
	assert response.json()["code"] == "suggestions_disabled"


async def test_suggestions_are_refused_after_the_channel_is_turned_off(api):
	await enable(api)
	await api.client.put(CONFIG_URL, json={"channel_id": None}, headers=api.internal)

	response = await api.client.post(SUGGESTIONS_URL, json={"author_id": "7", "content": "Hi"}, headers=api.internal)

	assert response.json()["code"] == "suggestions_disabled"


async def test_suggestions_are_numbered_per_guild_from_one(api):
	await enable(api)
	await enable(api, OTHER_GUILD)

	numbers = [(await suggest(api))["number"] for _ in range(3)]
	other = (await suggest(api, guild=OTHER_GUILD))["number"]

	assert numbers == [1, 2, 3]
	assert other == 1


async def test_numbering_continues_after_the_setting_changes(api):
	await enable(api)
	await suggest(api)
	await api.client.put(CONFIG_URL, json={"channel_id": None}, headers=api.internal)
	await api.client.put(CONFIG_URL, json={"channel_id": str(TEXT), "threads": True}, headers=api.internal)

	assert (await suggest(api))["number"] == 2


async def test_concurrent_suggestions_get_distinct_numbers(api):
	await enable(api)

	created = await asyncio.gather(*(suggest(api, f"idea {i}") for i in range(10)))

	assert sorted(s["number"] for s in created) == list(range(1, 11))


async def test_a_new_suggestion_is_open_with_no_votes_and_no_message(api):
	await enable(api)

	created = await suggest(api, "More emoji")
	fetched = (await api.client.get(f"{SUGGESTIONS_URL}/1", headers=api.internal)).json()

	expected = {
		"number": 1,
		"author_id": "7",
		"content": "More emoji",
		"channel_id": None,
		"message_id": None,
		"up": 0,
		"down": 0,
		"decision": None,
	}
	assert created == expected
	assert fetched == expected


@pytest.mark.parametrize("content", ["", "x" * 1001])
async def test_content_must_be_between_1_and_1000_characters(api, content):
	await enable(api)

	response = await api.client.post(SUGGESTIONS_URL, json={"author_id": "7", "content": content}, headers=api.internal)

	assert response.status_code == 422
	assert response.json()["code"] == "invalid_request"


async def test_an_unknown_suggestion_is_not_found(api):
	await enable(api)

	responses = [
		await api.client.get(f"{SUGGESTIONS_URL}/9", headers=api.internal),
		await vote(api, 1, "up", number=9),
		await decide(api, number=9),
		await api.client.put(
			f"{SUGGESTIONS_URL}/9/message", json={"channel_id": "1", "message_id": "2"}, headers=api.internal
		),
	]

	assert [(r.status_code, r.json()["code"]) for r in responses] == [(404, "not_found")] * 4


async def test_suggestions_belong_to_their_guild(api):
	await enable(api)
	await enable(api, OTHER_GUILD)
	await suggest(api)

	response = await api.client.get(f"/internal/guilds/{OTHER_GUILD}/suggestions/1", headers=api.internal)

	assert response.status_code == 404


async def test_the_posted_message_is_recorded(api):
	await enable(api)
	await suggest(api)

	await api.client.put(
		f"{SUGGESTIONS_URL}/1/message", json={"channel_id": str(TEXT), "message_id": "55"}, headers=api.internal
	)

	fetched = (await api.client.get(f"{SUGGESTIONS_URL}/1", headers=api.internal)).json()
	assert (fetched["channel_id"], fetched["message_id"]) == (str(TEXT), "55")


async def test_votes_are_counted_per_member(api):
	await enable(api)
	await suggest(api)

	await vote(api, 1, "up")
	await vote(api, 2, "up")
	result = await vote(api, 3, "down")

	assert result.json() == {"up": 2, "down": 1, "vote": "down"}
	fetched = (await api.client.get(f"{SUGGESTIONS_URL}/1", headers=api.internal)).json()
	assert (fetched["up"], fetched["down"]) == (2, 1)


async def test_voting_the_same_way_again_takes_the_vote_back(api):
	await enable(api)
	await suggest(api)
	await vote(api, 1, "up")

	result = await vote(api, 1, "up")

	assert result.json() == {"up": 0, "down": 0, "vote": None}


async def test_voting_the_other_way_switches_the_vote(api):
	await enable(api)
	await suggest(api)
	await vote(api, 1, "up")

	result = await vote(api, 1, "down")

	assert result.json() == {"up": 0, "down": 1, "vote": "down"}


async def test_concurrent_votes_are_all_counted(api):
	await enable(api)
	await suggest(api)

	await asyncio.gather(*(vote(api, user, "up") for user in range(1, 11)))

	assert (await api.client.get(f"{SUGGESTIONS_URL}/1", headers=api.internal)).json()["up"] == 10


async def test_deciding_records_the_decision_and_keeps_the_votes(api):
	await enable(api)
	await suggest(api)
	await vote(api, 1, "up")

	response = await decide(api, reason="Good idea")

	assert response.json()["decision"] == {"status": "approved", "moderator_id": "5", "reason": "Good idea"}
	assert response.json()["up"] == 1


async def test_deciding_again_overwrites_the_decision(api):
	await enable(api)
	await suggest(api)
	await decide(api, reason="Good idea")

	again = await api.client.post(
		f"{SUGGESTIONS_URL}/1/decision", json={"moderator_id": "6", "status": "denied"}, headers=api.internal
	)

	assert again.json()["decision"] == {"status": "denied", "moderator_id": "6", "reason": None}


async def test_a_reason_over_500_characters_is_refused(api):
	await enable(api)
	await suggest(api)

	response = await decide(api, "denied", reason="x" * 501)

	assert response.status_code == 422


@pytest.mark.parametrize("status", ["approved", "denied"])
async def test_a_decided_suggestion_takes_no_votes(api, status):
	await enable(api)
	await suggest(api)
	await vote(api, 1, "up")
	await decide(api, status)

	response = await vote(api, 2, "down")

	assert response.status_code == 409
	assert response.json()["code"] == "suggestion_closed"
	assert (await api.client.get(f"{SUGGESTIONS_URL}/1", headers=api.internal)).json()["down"] == 0


async def test_manager_sets_a_text_channel_and_the_bot_is_told(api, discord, events):
	auth = await sign_in(api)
	url = f"/dashboard/guilds/{GUILD}/settings/suggestions"

	response = await api.client.put(url, json={"channel_id": str(TEXT), "threads": True}, headers=auth)

	assert response.json() == {"channel_id": str(TEXT), "threads": True}
	assert (await api.client.get(url, headers=auth)).json() == {"channel_id": str(TEXT), "threads": True}
	assert await events.drain() == [
		{"type": "INVALIDATE_SETTING", "key": "suggestions", "guild_id": str(GUILD), "origin": None}
	]


@pytest.mark.parametrize("channel", [VOICE, ELSEWHERE, 404])
async def test_manager_cannot_set_a_channel_that_is_not_a_text_channel_in_the_guild(api, discord, events, channel):
	auth = await sign_in(api)

	response = await api.client.put(
		f"/dashboard/guilds/{GUILD}/settings/suggestions", json={"channel_id": str(channel)}, headers=auth
	)

	assert response.status_code == 422
	assert response.json()["code"] == "invalid_channel"
	assert await events.drain() == []


async def test_the_dashboard_setting_needs_a_session_and_guild_management(api, discord):
	auth = await sign_in(api)
	own = f"/dashboard/guilds/{GUILD}/settings/suggestions"
	other = f"/dashboard/guilds/{OTHER_GUILD}/settings/suggestions"

	anonymous = await api.client.get(own)
	not_a_manager = await api.client.put(other, json={"channel_id": None}, headers=auth)

	assert anonymous.status_code == 401
	assert not_a_manager.status_code == 403
