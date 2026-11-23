"""Moderation cases: the bot's Internal API operations."""

from __future__ import annotations

import datetime

import pytest

pytestmark = pytest.mark.db

GUILD, OTHER_GUILD = 100, 200
USER, MOD = 10, 20
NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def case(case_id: int, **fields) -> dict:
	return {
		"case_id": str(case_id),
		"type": 1,
		"user_id": str(USER),
		"moderator_id": str(MOD),
		"reason": "spam",
		"expires": None,
		"message": None,
		"active": True,
		"created": NOW.isoformat(),
		**fields,
	}


async def create(api, case_id: int, guild: int = GUILD, **fields) -> dict:
	response = await api.client.post(
		f"/internal/guilds/{guild}/cases", json=case(case_id, **fields), headers=api.internal
	)
	assert response.status_code == 201, response.text
	return response.json()


async def test_a_case_is_stored_and_found_only_in_its_guild(api):
	stored = await create(api, 1)

	found = await api.client.get(f"/internal/guilds/{GUILD}/cases/1", headers=api.internal)
	elsewhere = await api.client.get(f"/internal/guilds/{OTHER_GUILD}/cases/1", headers=api.internal)
	anywhere = await api.client.get("/internal/cases/1", headers=api.internal)

	assert stored["guild_id"] == str(GUILD)
	assert found.json() == stored
	assert elsewhere.status_code == 404
	assert anywhere.json() == stored


async def test_user_cases_are_filtered_and_oldest_first(api):
	past = (datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=1)).isoformat()
	future = (datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(hours=1)).isoformat()
	await create(api, 1, created=(NOW - datetime.timedelta(days=2)).isoformat(), type=2, expires=past)
	await create(api, 2, created=(NOW - datetime.timedelta(days=1)).isoformat(), type=2, expires=future)
	await create(api, 3, active=False)
	await create(api, 4, user_id="99")

	async def ids(**params) -> list[str]:
		response = await api.client.get(
			f"/internal/guilds/{GUILD}/cases", params={"user_id": USER, **params}, headers=api.internal
		)
		return [c["case_id"] for c in response.json()]

	assert await ids() == ["1", "2", "3"]
	assert await ids(which="open") == ["1", "2"]
	assert await ids(which="active") == ["2"]
	assert await ids(which="expired") == ["1", "3"]
	assert await ids(which="open", type=2) == ["1", "2"]
	assert await ids(type=1) == ["3"]


async def test_closing_follows_retention(api):
	await create(api, 1)
	await create(api, 2)

	kept = await api.client.post(f"/internal/guilds/{GUILD}/cases/1/close", headers=api.internal)
	await api.client.put(
		f"/internal/guilds/{GUILD}/settings/case-retention", json={"retention": "delete"}, headers=api.internal
	)
	deleted = await api.client.post(f"/internal/guilds/{GUILD}/cases/2/close", headers=api.internal)

	assert kept.json() == {"outcome": "deactivated"}
	assert deleted.json() == {"outcome": "deleted"}
	assert (await api.client.get(f"/internal/guilds/{GUILD}/cases/1", headers=api.internal)).json()["active"] is False
	assert (await api.client.get(f"/internal/guilds/{GUILD}/cases/2", headers=api.internal)).status_code == 404


async def test_editing_writes_every_field(api):
	await create(api, 1, message="hello")
	expires = (NOW + datetime.timedelta(days=1)).isoformat().replace("+00:00", "Z")

	edited = await api.client.put(
		f"/internal/guilds/{GUILD}/cases/1", json={"reason": "new", "expires": expires}, headers=api.internal
	)
	missing = await api.client.put(f"/internal/guilds/{GUILD}/cases/9", json={}, headers=api.internal)

	assert edited.json()["reason"] == "new"
	assert edited.json()["message"] is None
	assert datetime.datetime.fromisoformat(edited.json()["expires"]) == NOW + datetime.timedelta(days=1)
	assert missing.status_code == 404


async def test_deleting_ignores_retention_and_missing_cases(api):
	await create(api, 1)

	first = await api.client.delete(f"/internal/guilds/{GUILD}/cases/1", headers=api.internal)
	again = await api.client.delete(f"/internal/guilds/{GUILD}/cases/1", headers=api.internal)

	assert (first.status_code, again.status_code) == (204, 204)
	assert (await api.client.get("/internal/cases/1", headers=api.internal)).status_code == 404


async def test_pending_lists_open_cases_that_expire(api):
	expires = (NOW + datetime.timedelta(hours=1)).isoformat()
	await create(api, 1, expires=expires)
	await create(api, 2, expires=expires, active=False)
	await create(api, 3, guild=OTHER_GUILD)
	await create(api, 4, guild=OTHER_GUILD, expires=expires)

	pending = (await api.client.get("/internal/cases/pending", headers=api.internal)).json()

	assert sorted((p["case_id"], p["guild_id"]) for p in pending) == [("1", str(GUILD)), ("4", str(OTHER_GUILD))]
