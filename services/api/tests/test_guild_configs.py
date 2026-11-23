"""Guild configurations behind the Internal API: join/leave messages, AutoMod, logging, tickets, case retention."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.db

GUILD = 100
ORIGIN = {"X-Fm01-Origin": "instance-a"}


def event(key: str) -> dict[str, str]:
	return {"type": "INVALIDATE_SETTING", "key": key, "guild_id": str(GUILD), "origin": "instance-a"}


async def test_an_unconfigured_greeting_is_null(api):
	response = await api.client.get(f"/internal/guilds/{GUILD}/settings/greetings/join", headers=api.internal)

	assert response.status_code == 200
	assert response.json() is None


async def test_a_new_greeting_starts_on_and_falls_back_to_the_given_channel(api, events):
	url = f"/internal/guilds/{GUILD}/settings/greetings/leave"

	created = await api.client.patch(
		url, json={"message": "bye {member}", "fallback_channel_id": "7"}, headers={**api.internal, **ORIGIN}
	)

	assert created.json() == {"enabled": True, "channel_id": "7", "message": "bye {member}"}
	assert await events.drain() == [event("leave")]


async def test_greeting_changes_keep_unset_fields_and_the_fallback_never_overrides(api):
	url = f"/internal/guilds/{GUILD}/settings/greetings/join"
	await api.client.patch(url, json={"channel_id": "5", "message": "hi"}, headers=api.internal)

	disabled = await api.client.patch(url, json={"enabled": False, "fallback_channel_id": "9"}, headers=api.internal)
	moved = await api.client.patch(url, json={"enabled": True, "channel_id": "6"}, headers=api.internal)

	assert disabled.json() == {"enabled": False, "channel_id": "5", "message": "hi"}
	assert moved.json() == {"enabled": True, "channel_id": "6", "message": "hi"}
	leave = await api.client.get(f"/internal/guilds/{GUILD}/settings/greetings/leave", headers=api.internal)
	assert leave.json() is None


async def test_an_unknown_greeting_kind_is_rejected(api):
	response = await api.client.get(f"/internal/guilds/{GUILD}/settings/greetings/hello", headers=api.internal)

	assert response.status_code == 422


async def test_automod_defaults_off_and_round_trips(api, events):
	url = f"/internal/guilds/{GUILD}/settings/automod"
	assert (await api.client.get(url, headers=api.internal)).json() == {"enabled": False, "settings": {}}

	body = {"enabled": True, "settings": {"rules": {"link": {"enabled": True, "allowlist": ["example.com"]}}}}
	await api.client.put(url, json=body, headers={**api.internal, **ORIGIN})

	assert (await api.client.get(url, headers=api.internal)).json() == body
	assert await events.drain() == [event("automod")]


async def test_log_configs_are_stored_listed_and_deleted(api, events):
	url = f"/internal/guilds/{GUILD}/settings/log"
	assert (await api.client.get(url, headers=api.internal)).json() is None
	body = {
		"enabled": True,
		"channel_id": "10",
		"channels": {"on_message_delete": "11"},
		"modules": ["on_message_edit", "on_message_delete"],
		"webhook_url": None,
	}

	await api.client.put(url, json=body, headers={**api.internal, **ORIGIN})
	listed = (await api.client.get("/internal/settings/log", headers=api.internal)).json()
	deleted = await api.client.delete(url, headers={**api.internal, **ORIGIN})

	assert listed == [{**body, "guild_id": str(GUILD), "modules": ["on_message_delete", "on_message_edit"]}]
	assert deleted.status_code == 204
	assert (await api.client.get(url, headers=api.internal)).json() is None
	assert await events.drain() == [event("log"), event("log")]


async def test_log_channels_written_by_the_bot_as_numbers_still_load(api):
	await api.db.execute(
		"INSERT INTO log (guild_id, is_on, channel, channels) VALUES ($1, true, 1, $2)",
		GUILD,
		{"on_member_join": 123456789012345678, "on_member_remove": None},
	)

	config = (await api.client.get(f"/internal/guilds/{GUILD}/settings/log", headers=api.internal)).json()

	assert config["channels"] == {"on_member_join": "123456789012345678"}
	assert config["modules"] == ["*"]


async def test_ticket_config_changes_only_the_given_fields_and_null_clears(api, events):
	url = f"/internal/guilds/{GUILD}/settings/tickets"
	assert (await api.client.get(url, headers=api.internal)).json() is None

	first = await api.client.patch(url, json={"category_id": "3", "max_tickets": 2}, headers={**api.internal, **ORIGIN})
	cleared = await api.client.patch(url, json={"category_id": None, "enabled": None}, headers=api.internal)

	assert first.json()["category_id"] == "3"
	assert first.json()["max_tickets"] == 2
	assert first.json()["enabled"] is True
	assert cleared.json()["category_id"] is None
	assert cleared.json()["enabled"] is True
	assert cleared.json()["max_tickets"] == 2
	assert (await events.drain())[0] == event("ticket")


async def test_ticket_lengths_may_not_cross(api):
	url = f"/internal/guilds/{GUILD}/settings/tickets"

	response = await api.client.patch(url, json={"topic_min_length": 500}, headers=api.internal)

	assert response.status_code == 422
	assert response.json()["code"] == "invalid_request"
	assert (await api.client.get(url, headers=api.internal)).json() is None


async def test_case_retention_defaults_to_keep_and_is_announced(api, events):
	url = f"/internal/guilds/{GUILD}/settings/case-retention"
	assert (await api.client.get(url, headers=api.internal)).json() == {"retention": "keep"}

	await api.client.put(url, json={"retention": "delete"}, headers={**api.internal, **ORIGIN})

	assert (await api.client.get(url, headers=api.internal)).json() == {"retention": "delete"}
	assert await events.drain() == [event("mod.retention")]
	invalid = await api.client.put(url, json={"retention": "forever"}, headers=api.internal)
	assert invalid.status_code == 422
