"""AFK, snapshots and the shop: the bot's Internal API operations."""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.db

GUILD = 100
USER = 10


async def toggle(api, message: str = "brb", nick: str = "alice") -> dict:
	response = await api.client.post(
		f"/internal/guilds/{GUILD}/afk/{USER}/toggle",
		json={"message": message, "previous_nick": nick},
		headers=api.internal,
	)
	assert response.status_code == 200, response.text
	return response.json()


async def test_afk_toggles_and_restores_the_recorded_nickname(api):
	away = await toggle(api, nick="alice")
	listed = (await api.client.get("/internal/afk", headers=api.internal)).json()
	back = await toggle(api, nick="[AFK] alice")
	again = await toggle(api, message="lunch", nick="alice2")

	assert away == {"away": True, "previous_nick": "alice"}
	assert listed == [{"guild_id": str(GUILD), "user_id": str(USER), "message": "brb", "previous_nick": "alice"}]
	assert back == {"away": False, "previous_nick": "alice"}
	assert again == {"away": True, "previous_nick": "alice2"}


async def test_concurrent_toggles_keep_one_row(api):
	await asyncio.gather(*(toggle(api) for _ in range(6)))

	assert await api.db.fetchval("SELECT count(*) FROM afk") == 1


async def test_coming_back_by_writing(api):
	await toggle(api)

	response = await api.client.delete(f"/internal/guilds/{GUILD}/afk/{USER}", headers=api.internal)

	assert response.status_code == 204
	assert (await api.client.get("/internal/afk", headers=api.internal)).json() == []


async def test_snapshots_get_a_code_and_load_ignoring_case(api):
	payload = {"roles": {"1": {"name": "@everyone"}}, "channels": {}}

	created = await api.client.post(
		f"/internal/guilds/{GUILD}/snapshots",
		json={"name": "Server snapshot", "author_id": str(USER), "payload": payload},
		headers=api.internal,
	)
	code = created.json()["code"]
	loaded = await api.client.get(f"/internal/snapshots/{code.upper()}", headers=api.internal)
	missing = await api.client.get("/internal/snapshots/nope", headers=api.internal)

	assert created.status_code == 201
	assert loaded.json()["payload"] == payload
	assert loaded.json()["guild_id"] == str(GUILD)
	assert missing.status_code == 404


async def test_snapshots_stored_as_json_strings_still_load(api):
	await api.db.execute(
		"INSERT INTO snapshots (guild_id, name, payload, author_id, date, code) VALUES ($1, 'x', $2, 1, now(), 'abc')",
		GUILD,
		'{"roles": {}, "channels": {}}',
	)

	loaded = await api.client.get("/internal/snapshots/abc", headers=api.internal)

	assert loaded.json()["payload"] == {"roles": {}, "channels": {}}


def item(name: str, role: int = 5) -> dict:
	return {"name": name, "description": "a role", "price": 100, "role_id": str(role), "creator_id": str(USER)}


async def test_shop_items_are_unique_ignoring_case_and_found_ignoring_case(api):
	url = f"/internal/guilds/{GUILD}/shop"
	added = await api.client.post(url, json=item("VIP"), headers=api.internal)
	taken = await api.client.post(url, json=item("vip"), headers=api.internal)

	found = await api.client.get(f"{url}/item", params={"name": "vIp"}, headers=api.internal)

	assert added.status_code == 201
	assert taken.json()["code"] == "shop_item_taken"
	assert found.json() == item("VIP")


async def test_the_shop_holds_at_most_nine_items(api):
	url = f"/internal/guilds/{GUILD}/shop"
	results = await asyncio.gather(
		*(api.client.post(url, json=item(f"item {i}"), headers=api.internal) for i in range(12))
	)

	assert sorted(r.status_code for r in results) == [201] * 9 + [409] * 3
	assert len((await api.client.get(url, headers=api.internal)).json()) == 9


async def test_removing_a_shop_item(api):
	url = f"/internal/guilds/{GUILD}/shop"
	await api.client.post(url, json=item("a/b"), headers=api.internal)

	removed = await api.client.delete(f"{url}/item", params={"name": "A/B"}, headers=api.internal)
	again = await api.client.delete(f"{url}/item", params={"name": "a/b"}, headers=api.internal)

	assert removed.status_code == 204
	assert again.status_code == 404
