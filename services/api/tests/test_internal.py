"""Internal API: the service token, and guild settings writes announcing invalidations."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.db

GUILD = 42


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic x"}])
async def test_internal_routes_need_the_service_token(api, headers):
	response = await api.client.get("/internal/settings/prefix", headers=headers)

	assert response.status_code == 401
	assert response.json()["code"] == "unauthorized"


async def test_dashboard_session_is_not_a_service_token(api):
	response = await api.client.get("/internal/settings/prefix", headers={"Authorization": "Bearer some-session"})
	assert response.status_code == 401


async def test_loading_a_prefix_creates_the_guild_row_with_defaults(api):
	response = await api.client.get(f"/internal/guilds/{GUILD}/settings/prefix", headers=api.internal)

	assert response.json() == {"prefix": "?!", "mention": True}
	assert await api.db.fetchval("SELECT count(*) FROM guilds WHERE guild_id = $1", GUILD) == 1


async def test_writing_a_prefix_persists_and_announces_with_the_origin(api, events):
	response = await api.client.put(
		f"/internal/guilds/{GUILD}/settings/prefix",
		json={"prefix": "!", "mention": False},
		headers={**api.internal, "X-Fm01-Origin": "instance-a"},
	)

	assert response.json() == {"prefix": "!", "mention": False}
	all_prefixes = await api.client.get("/internal/settings/prefix", headers=api.internal)
	assert all_prefixes.json() == [{"guild_id": str(GUILD), "prefix": "!", "mention": False}]
	assert await events.drain() == [
		{"type": "INVALIDATE_SETTING", "key": "prefix", "guild_id": str(GUILD), "origin": "instance-a"}
	]


async def test_prefixes_longer_than_ten_characters_are_rejected(api):
	response = await api.client.put(
		f"/internal/guilds/{GUILD}/settings/prefix", json={"prefix": "x" * 11, "mention": True}, headers=api.internal
	)
	assert response.status_code == 422


async def test_locale_override_set_and_cleared(api, events):
	url = f"/internal/guilds/{GUILD}/settings/locale"

	await api.client.put(url, json={"locale": "hu"}, headers=api.internal)
	assert (await api.client.get(url, headers=api.internal)).json() == {"locale": "hu"}
	assert (await api.client.get("/internal/settings/locale", headers=api.internal)).json() == [
		{"guild_id": str(GUILD), "locale": "hu"}
	]

	await api.client.put(url, json={"locale": None}, headers=api.internal)
	assert (await api.client.get(url, headers=api.internal)).json() == {"locale": None}
	assert [e["key"] for e in await events.drain()] == ["locale", "locale"]


async def test_locale_must_be_a_two_letter_code(api):
	response = await api.client.put(
		f"/internal/guilds/{GUILD}/settings/locale", json={"locale": "en-US"}, headers=api.internal
	)
	assert response.status_code == 422


async def test_snowflake_path_parameters_must_be_digits(api):
	response = await api.client.get("/internal/guilds/abc/settings/prefix", headers=api.internal)
	assert response.status_code == 422
	assert response.json()["code"] == "invalid_request"
