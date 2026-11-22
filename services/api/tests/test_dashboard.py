"""Dashboard API: signing in with Discord, sessions, and the guild manager check."""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from app.dashboard.access import ADMINISTRATOR, MANAGE_GUILD, is_guild_manager

pytestmark = pytest.mark.db

USER_ID = 1234567890123456789
OWNED, MANAGED, MEMBER, NO_BOT = 100, 200, 300, 400
REDIRECT = "https://dashboard.example/callback"


@pytest.fixture
def discord(api):
	fake = api.discord
	fake.codes["good-code"] = "access-1"
	fake.users["access-1"] = {"id": str(USER_ID), "username": "alice", "global_name": "Alice", "avatar": None}
	fake.guilds["access-1"] = [
		{"id": str(OWNED), "name": "Owned", "icon": None, "owner": True, "permissions": "0"},
		{"id": str(MANAGED), "name": "Managed", "icon": "abc", "owner": False, "permissions": str(MANAGE_GUILD)},
		{"id": str(MEMBER), "name": "Member", "icon": None, "owner": False, "permissions": "1024"},
		{"id": str(NO_BOT), "name": "No bot", "icon": None, "owner": False, "permissions": str(ADMINISTRATOR)},
	]
	fake.bot_guilds = {OWNED, MANAGED, MEMBER}
	return fake


async def sign_in(api) -> dict[str, str]:
	response = await api.client.post("/dashboard/auth/exchange", json={"code": "good-code", "redirect_uri": REDIRECT})
	assert response.status_code == 200, response.text
	return {"Authorization": f"Bearer {response.json()['token']}"}


def test_guild_manager_rule():
	assert is_guild_manager({"owner": True, "permissions": "0"})
	assert is_guild_manager({"owner": False, "permissions": str(ADMINISTRATOR)})
	assert is_guild_manager({"owner": False, "permissions": str(MANAGE_GUILD | 1024)})
	assert not is_guild_manager({"owner": False, "permissions": "1024"})


async def test_exchange_creates_a_session_storing_only_the_salted_hash(api, discord):
	response = await api.client.post("/dashboard/auth/exchange", json={"code": "good-code", "redirect_uri": REDIRECT})

	body = response.json()
	assert body["user"] == {"id": str(USER_ID), "username": "alice", "global_name": "Alice", "avatar": None}
	assert datetime.fromisoformat(body["expires_at"]) > datetime.now(UTC) + timedelta(days=29)
	session_id, secret = body["token"].split(".")
	row = await api.db.fetchrow("SELECT * FROM dashboard_sessions")
	assert row["id"] == session_id
	assert row["token_hash"] == hashlib.sha256(bytes.fromhex(row["token_salt"]) + secret.encode()).hexdigest()
	assert secret not in "".join(str(value) for value in row.values())
	assert "access-1" not in row["access_token"]  # encrypted


async def test_wrong_secret_for_a_real_session_is_unauthorized(api, discord):
	auth = await sign_in(api)
	session_id = auth["Authorization"].removeprefix("Bearer ").split(".")[0]

	for token in (f"{session_id}.wrong", session_id, f"{session_id}."):
		response = await api.client.get("/dashboard/me", headers={"Authorization": f"Bearer {token}"})
		assert response.status_code == 401


async def test_bad_code_is_unauthorized(api, discord):
	response = await api.client.post("/dashboard/auth/exchange", json={"code": "nope", "redirect_uri": REDIRECT})
	assert response.status_code == 401


async def test_missing_guilds_scope_is_refused_and_revoked(api, discord):
	discord.scope = "identify"

	response = await api.client.post("/dashboard/auth/exchange", json={"code": "good-code", "redirect_uri": REDIRECT})

	assert response.status_code == 403
	assert discord.revoked == ["access-1"]
	assert await api.db.fetchval("SELECT count(*) FROM dashboard_sessions") == 0


async def test_me_and_logout(api, discord):
	auth = await sign_in(api)

	assert (await api.client.get("/dashboard/me", headers=auth)).json()["username"] == "alice"
	assert (await api.client.post("/dashboard/auth/logout", headers=auth)).status_code == 204
	assert (await api.client.get("/dashboard/me", headers=auth)).status_code == 401


async def test_expired_sessions_are_rejected(api, discord):
	auth = await sign_in(api)
	await api.db.execute("UPDATE dashboard_sessions SET expires_at = now() - interval '1 second'")

	assert (await api.client.get("/dashboard/me", headers=auth)).status_code == 401


async def test_guilds_lists_only_managed_guilds(api, discord):
	auth = await sign_in(api)

	guilds = (await api.client.get("/dashboard/guilds", headers=auth)).json()

	assert [g["id"] for g in guilds] == [str(OWNED), str(MANAGED), str(NO_BOT)]


async def test_manager_changes_prefix_and_the_bot_is_told(api, discord, events):
	auth = await sign_in(api)

	response = await api.client.put(
		f"/dashboard/guilds/{MANAGED}/settings/prefix", json={"prefix": "$", "mention": True}, headers=auth
	)

	assert response.json() == {"prefix": "$", "mention": True}
	assert await api.db.fetchval("SELECT prefix FROM guilds WHERE guild_id = $1", MANAGED) == "$"
	assert await events.drain() == [
		{"type": "INVALIDATE_SETTING", "key": "prefix", "guild_id": str(MANAGED), "origin": None}
	]


async def test_non_manager_is_forbidden(api, discord):
	auth = await sign_in(api)

	response = await api.client.put(f"/dashboard/guilds/{MEMBER}/settings/locale", json={"locale": "hu"}, headers=auth)

	assert response.status_code == 403
	assert response.json()["code"] == "forbidden"


async def test_guild_without_the_bot_is_not_found(api, discord):
	auth = await sign_in(api)

	response = await api.client.get(f"/dashboard/guilds/{NO_BOT}/settings/locale", headers=auth)

	assert response.status_code == 404


async def test_manager_check_is_cached(api, discord):
	auth = await sign_in(api)
	for _ in range(3):
		await api.client.get(f"/dashboard/guilds/{OWNED}/settings/prefix", headers=auth)

	assert discord.calls.count("GET /users/@me/guilds") == 1
	assert discord.calls.count(f"GET /guilds/{OWNED}") == 1


async def test_expired_discord_token_is_refreshed(api, discord):
	auth = await sign_in(api)
	await api.db.execute("UPDATE dashboard_sessions SET discord_expires_at = now() - interval '1 second'")

	response = await api.client.get("/dashboard/guilds", headers=auth)

	assert response.status_code == 200
	assert "POST /oauth2/token" in discord.calls[2:]
	assert await api.db.fetchval("SELECT discord_expires_at > now() FROM dashboard_sessions")


async def test_concurrent_requests_refresh_the_discord_token_once(api, discord):
	auth = await sign_in(api)
	await api.db.execute("UPDATE dashboard_sessions SET discord_expires_at = now() - interval '1 second'")

	responses = await asyncio.gather(*(api.client.get("/dashboard/guilds", headers=auth) for _ in range(3)))

	assert [response.status_code for response in responses] == [200, 200, 200]
	# Discord rotates refresh tokens, so a second refresh with the old one would fail and end the session.
	assert discord.calls.count("POST /oauth2/token") == 2  # the sign-in, then one refresh


async def test_dashboard_routes_need_a_session(api):
	response = await api.client.get(f"/dashboard/guilds/{OWNED}/settings/prefix")
	assert response.status_code == 401


async def test_sign_in_is_off_without_oauth_credentials(api, discord):
	app_state = api.client._transport.app.state.fm01  # type: ignore[attr-defined]
	object.__setattr__(app_state, "config", dataclasses.replace(app_state.config, discord_client_secret=None))

	response = await api.client.post("/dashboard/auth/exchange", json={"code": "good-code", "redirect_uri": REDIRECT})

	assert response.status_code == 404
	assert discord.calls == []
