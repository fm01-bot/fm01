"""The blacklist: the Internal API that keeps it, and the Dashboard API refusing blacklisted users and guilds."""

from __future__ import annotations

import pytest
from app.dashboard.access import MANAGE_GUILD

pytestmark = pytest.mark.db

OWNER = 11
USER_ID = 1234567890123456789
GUILD, OTHER = 100, 200
REDIRECT = "https://dashboard.example/callback"


@pytest.fixture
def discord(api):
	fake = api.discord
	fake.codes["good-code"] = "access-1"
	fake.users["access-1"] = {"id": str(USER_ID), "username": "alice", "global_name": None, "avatar": None}
	fake.guilds["access-1"] = [
		{"id": str(GUILD), "name": "Guild", "icon": None, "owner": True, "permissions": "0"},
		{"id": str(OTHER), "name": "Other", "icon": None, "owner": False, "permissions": str(MANAGE_GUILD)},
	]
	fake.bot_guilds = {GUILD, OTHER}
	return fake


async def sign_in(api) -> dict[str, str]:
	response = await api.client.post("/dashboard/auth/exchange", json={"code": "good-code", "redirect_uri": REDIRECT})
	assert response.status_code == 200, response.text
	return {"Authorization": f"Bearer {response.json()['token']}"}


async def blacklist(api, kind: str, target_id: int, reason: str | None = None):
	return await api.client.put(
		f"/internal/blacklist/{kind}/{target_id}",
		json={"created_by": str(OWNER), "reason": reason},
		headers=api.internal,
	)


async def test_add_list_and_remove_announce_each_change(api, events):
	added = await blacklist(api, "user", USER_ID, "spam")
	assert added.status_code == 200, added.text
	assert added.json()["reason"] == "spam"
	await blacklist(api, "guild", GUILD)

	entries = (await api.client.get("/internal/blacklist", headers=api.internal)).json()
	assert [(e["kind"], e["target_id"], e["reason"], e["created_by"]) for e in entries] == [
		("user", str(USER_ID), "spam", str(OWNER)),
		("guild", str(GUILD), None, str(OWNER)),
	]

	removed = await api.client.delete(f"/internal/blacklist/user/{USER_ID}", headers=api.internal)
	assert removed.status_code == 204
	again = await api.client.delete(f"/internal/blacklist/user/{USER_ID}", headers=api.internal)
	assert again.json()["code"] == "not_found"

	assert await events.drain() == [
		{"type": "BLACKLIST_CHANGED", "kind": "user", "target_id": str(USER_ID), "blacklisted": True},
		{"type": "BLACKLIST_CHANGED", "kind": "guild", "target_id": str(GUILD), "blacklisted": True},
		{"type": "BLACKLIST_CHANGED", "kind": "user", "target_id": str(USER_ID), "blacklisted": False},
	]


async def test_blacklisting_again_replaces_the_reason(api):
	await blacklist(api, "user", USER_ID, "spam")
	await blacklist(api, "user", USER_ID, "abuse")

	entries = (await api.client.get("/internal/blacklist", headers=api.internal)).json()
	assert [e["reason"] for e in entries] == ["abuse"]


async def test_unknown_kind_is_invalid(api):
	response = await blacklist(api, "channel", 1)
	assert response.json()["code"] == "invalid_request"


async def test_blacklisted_user_cannot_sign_in(api, discord):
	await blacklist(api, "user", USER_ID)

	response = await api.client.post("/dashboard/auth/exchange", json={"code": "good-code", "redirect_uri": REDIRECT})

	assert response.status_code == 403
	assert response.json()["code"] == "blacklisted"
	assert "access-1" in discord.revoked
	assert await api.db.fetchval("SELECT count(*) FROM dashboard_sessions") == 0


async def test_signed_in_user_is_refused_once_blacklisted_but_may_sign_out(api, discord):
	auth = await sign_in(api)
	await blacklist(api, "user", USER_ID)

	for response in (
		await api.client.get("/dashboard/me", headers=auth),
		await api.client.get("/dashboard/guilds", headers=auth),
		await api.client.get(f"/dashboard/guilds/{GUILD}/settings/prefix", headers=auth),
	):
		assert response.status_code == 403
		assert response.json()["code"] == "blacklisted"

	assert (await api.client.post("/dashboard/auth/logout", headers=auth)).status_code == 204

	await api.client.delete(f"/internal/blacklist/user/{USER_ID}", headers=api.internal)
	assert (await api.client.get("/dashboard/me", headers=auth)).status_code == 401  # signed out for good


async def test_blacklisted_guild_is_hidden_and_cannot_be_configured(api, discord):
	auth = await sign_in(api)
	await blacklist(api, "guild", GUILD)

	guilds = (await api.client.get("/dashboard/guilds", headers=auth)).json()
	assert [guild["id"] for guild in guilds] == [str(OTHER)]

	response = await api.client.get(f"/dashboard/guilds/{GUILD}/settings/prefix", headers=auth)
	assert response.status_code == 403
	assert response.json()["code"] == "blacklisted"
	assert (await api.client.get(f"/dashboard/guilds/{OTHER}/settings/prefix", headers=auth)).status_code == 200


async def test_non_manager_is_not_told_a_guild_is_blacklisted(api, discord):
	auth = await sign_in(api)
	await blacklist(api, "guild", 999)

	response = await api.client.get("/dashboard/guilds/999/settings/prefix", headers=auth)
	assert response.json()["code"] == "forbidden"
