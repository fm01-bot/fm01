"""Starboards: board configuration, counting stars, and the entries the bot keeps for its posts."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from app.dashboard.access import MANAGE_GUILD

pytestmark = pytest.mark.db

GUILD, OTHER_GUILD = 200, 300
TEXT, VOICE, ELSEWHERE, OTHER_TEXT = 2001, 2002, 3001, 2003
EMOJI = 123456789012345678
BOARDS = f"/internal/guilds/{GUILD}/settings/starboards"
STARS = f"/internal/guilds/{GUILD}/starboard"
MESSAGE, AUTHOR, POST = 7000, 50, 8000


def board(name: str = "starboard", **overrides) -> dict:
	return {"name": name, "channel_id": str(TEXT), **overrides}


@pytest.fixture
def discord(api):
	fake = api.discord
	fake.codes["code"] = "access"
	fake.users["access"] = {"id": "1", "username": "alice", "global_name": None, "avatar": None}
	fake.guilds["access"] = [
		{"id": str(GUILD), "name": "Managed", "icon": None, "owner": False, "permissions": str(MANAGE_GUILD)},
	]
	fake.bot_guilds = {GUILD, OTHER_GUILD}
	fake.channels = {
		TEXT: {"id": str(TEXT), "guild_id": str(GUILD), "type": 0},
		VOICE: {"id": str(VOICE), "guild_id": str(GUILD), "type": 2},
		ELSEWHERE: {"id": str(ELSEWHERE), "guild_id": str(OTHER_GUILD), "type": 0},
	}
	fake.emojis = {GUILD: {EMOJI}}
	return fake


async def sign_in(api) -> dict[str, str]:
	response = await api.client.post(
		"/dashboard/auth/exchange", json={"code": "code", "redirect_uri": "https://dashboard.example/callback"}
	)
	assert response.status_code == 200, response.text
	return {"Authorization": f"Bearer {response.json()['token']}"}


async def create(api, **overrides) -> dict:
	response = await api.client.post(BOARDS, json=board(**overrides), headers=api.internal)
	assert response.status_code == 201, response.text
	return response.json()


async def seed(api, user_ids, *, message=MESSAGE, emoji="⭐") -> dict:
	body = {
		"message_id": str(message),
		"channel_id": str(OTHER_TEXT),
		"author_id": str(AUTHOR),
		"emoji": emoji,
		"user_ids": [str(u) for u in user_ids],
	}
	response = await api.client.post(f"{STARS}/seeds", json=body, headers=api.internal)
	assert response.status_code == 200, response.text
	return response.json()


async def star(api, user_id, *, message=MESSAGE, starred=True, emoji="⭐") -> Any:
	body = {"message_id": str(message), "emoji": emoji, "user_id": str(user_id), "starred": starred}
	response = await api.client.post(f"{STARS}/stars", json=body, headers=api.internal)
	assert response.status_code == 200, response.text
	return response.json()["message"]


async def post(api, name="starboard", *, message=MESSAGE, post_id=POST) -> dict:
	body = {
		"board": name,
		"message_id": str(message),
		"post_channel_id": str(TEXT) if post_id else None,
		"post_id": str(post_id) if post_id else None,
	}
	response = await api.client.put(f"{STARS}/posts", json=body, headers=api.internal)
	assert response.status_code == 200, response.text
	return response.json()


async def test_a_board_gets_defaults_and_is_announced_with_the_origin(api, events):
	response = await api.client.post(BOARDS, json=board(), headers={**api.internal, "X-Fm01-Origin": "instance-a"})

	assert response.json() == {
		"name": "starboard",
		"channel_id": str(TEXT),
		"emoji": "⭐",
		"threshold": 3,
		"enabled": True,
		"channel_mode": "blocklist",
		"channel_ids": [],
		"max_age_days": None,
	}
	assert await events.drain() == [
		{"type": "INVALIDATE_SETTING", "key": "starboard", "guild_id": str(GUILD), "origin": "instance-a"}
	]


async def test_all_groups_boards_by_guild(api):
	await create(api, name="b")
	await create(api, name="a", threshold=10)
	await api.client.post(
		f"/internal/guilds/{OTHER_GUILD}/settings/starboards", json=board(name="x"), headers=api.internal
	)

	guilds = (await api.client.get("/internal/settings/starboards", headers=api.internal)).json()

	assert {g["guild_id"]: [b["name"] for b in g["boards"]] for g in guilds} == {
		str(GUILD): ["a", "b"],
		str(OTHER_GUILD): ["x"],
	}


async def test_a_guild_can_have_at_most_five_boards_even_when_created_at_once(api):
	responses = await asyncio.gather(
		*(api.client.post(BOARDS, json=board(name=f"b{i}", threshold=i + 1), headers=api.internal) for i in range(7))
	)

	assert sorted(r.status_code for r in responses) == [201] * 5 + [409] * 2
	assert {r.json()["code"] for r in responses if r.status_code == 409} == {"starboard_limit"}


async def test_names_are_unique_per_guild(api):
	await create(api)

	response = await api.client.post(BOARDS, json=board(threshold=9), headers=api.internal)

	assert response.status_code == 409
	assert response.json()["code"] == "starboard_name_taken"


async def test_tiers_share_an_emoji_but_not_a_threshold(api):
	await create(api, name="starboard", threshold=3)
	await create(api, name="hall-of-fame", threshold=10)

	response = await api.client.post(BOARDS, json=board(name="again", threshold=10), headers=api.internal)

	assert response.status_code == 409
	assert response.json()["code"] == "starboard_tier_taken"


@pytest.mark.parametrize(
	"overrides",
	[{"name": "Has Caps"}, {"name": "x" * 33}, {"threshold": 0}, {"threshold": 101}, {"emoji": "star"}, {"emoji": ""}],
)
async def test_invalid_boards_are_rejected(api, overrides):
	response = await api.client.post(BOARDS, json=board(**overrides), headers=api.internal)

	assert response.status_code == 422
	assert response.json()["code"] == "invalid_request"


async def test_an_update_changes_only_the_fields_given(api):
	await create(api, max_age_days=7, channel_ids=[str(OTHER_TEXT)])

	renamed = await api.client.patch(
		f"{BOARDS}/starboard", json={"name": "stars", "threshold": 5, "enabled": None}, headers=api.internal
	)
	cleared = await api.client.patch(f"{BOARDS}/stars", json={"max_age_days": None}, headers=api.internal)

	assert renamed.json()["name"] == "stars"
	assert renamed.json()["threshold"] == 5
	assert renamed.json()["enabled"] is True
	assert renamed.json()["max_age_days"] == 7
	assert cleared.json()["max_age_days"] is None
	assert cleared.json()["channel_ids"] == [str(OTHER_TEXT)]


async def test_updating_or_deleting_an_unknown_board_is_not_found(api):
	patched = await api.client.patch(f"{BOARDS}/nope", json={"threshold": 5}, headers=api.internal)
	deleted = await api.client.delete(f"{BOARDS}/nope", headers=api.internal)

	assert patched.status_code == deleted.status_code == 404


async def test_a_star_on_a_message_never_seeded_returns_nothing(api):
	await create(api)

	assert await star(api, 1) is None


async def test_seeding_counts_unique_members_without_the_author(api):
	await create(api)

	message = await seed(api, [1, 2, AUTHOR, 2])

	assert message["count"] == 2
	assert message["entries"] == []


async def test_stars_are_added_and_removed_once_per_member(api):
	await create(api)
	await seed(api, [1])

	await star(api, 2)
	await star(api, 2)
	await star(api, AUTHOR)
	after_remove = await star(api, 1, starred=False)

	assert after_remove["count"] == 1


async def test_a_star_on_a_post_counts_for_the_original_once_per_member(api):
	await create(api, threshold=1)
	await seed(api, [1])
	await post(api)

	via_post = await star(api, 1, message=POST)
	new_member = await star(api, 2, message=POST)

	assert via_post["message_id"] == str(MESSAGE)
	assert via_post["count"] == 1
	assert new_member["count"] == 2
	assert new_member["entries"] == [
		{
			"board": "starboard",
			"message_id": str(MESSAGE),
			"post_channel_id": str(TEXT),
			"post_id": str(POST),
			"blocked": False,
		}
	]


async def test_tiers_share_one_count_and_list_each_entry(api):
	await create(api, name="starboard", threshold=1)
	await create(api, name="hall-of-fame", threshold=2)
	await seed(api, [1, 2])
	await post(api, "starboard", post_id=POST)
	await post(api, "hall-of-fame", post_id=POST + 1)

	message = await star(api, 3, message=POST + 1)

	assert message["count"] == 3
	assert [e["board"] for e in message["entries"]] == ["hall-of-fame", "starboard"]


async def test_a_star_with_another_emoji_on_a_post_is_not_a_post(api):
	await create(api, threshold=1)
	await create(api, name="skulls", emoji="💀", threshold=1)
	await seed(api, [1])
	await post(api)

	assert await star(api, 2, message=POST, emoji="💀") is None


async def test_a_deleted_post_blocks_its_message_on_that_board_only(api):
	await create(api, name="starboard", threshold=1)
	await create(api, name="hall-of-fame", threshold=2)
	await seed(api, [1, 2])
	await post(api, "starboard", post_id=POST)
	await post(api, "hall-of-fame", post_id=POST + 1)

	response = await api.client.post(
		f"{STARS}/posts/deleted", json={"message_ids": [str(POST), "999"]}, headers=api.internal
	)
	message = await star(api, 3)

	assert response.json() == [
		{"board": "starboard", "message_id": str(MESSAGE), "post_channel_id": None, "post_id": None, "blocked": True}
	]
	assert {e["board"]: e["blocked"] for e in message["entries"]} == {"starboard": True, "hall-of-fame": False}


async def test_a_post_the_bot_removed_first_does_not_block(api):
	await create(api, threshold=1)
	await seed(api, [1])
	await post(api)
	await post(api, post_id=None)

	response = await api.client.post(f"{STARS}/posts/deleted", json={"message_ids": [str(POST)]}, headers=api.internal)

	assert response.json() == []


async def test_a_deleted_original_is_forgotten_and_its_posts_returned(api):
	await create(api, threshold=1)
	await seed(api, [1])
	await post(api)

	response = await api.client.post(
		f"{STARS}/messages/deleted", json={"message_ids": [str(MESSAGE)]}, headers=api.internal
	)

	assert [e["post_id"] for e in response.json()] == [str(POST)]
	assert await star(api, 2) is None
	assert await api.db.fetchval("SELECT count(*) FROM starboard_entries") == 0


async def test_clearing_reactions_takes_posts_down_and_keeps_blocks(api):
	await create(api, name="starboard", threshold=1)
	await create(api, name="skulls", emoji="💀", threshold=1)
	await seed(api, [1])
	await seed(api, [1], emoji="💀")
	await post(api, "starboard")
	await post(api, "skulls", post_id=POST + 1)
	await api.client.post(f"{STARS}/posts/deleted", json={"message_ids": [str(POST + 1)]}, headers=api.internal)

	response = await api.client.post(f"{STARS}/messages/{MESSAGE}/clear", json={"emoji": "⭐"}, headers=api.internal)
	skulls = await star(api, 2, emoji="💀")

	assert [e["post_id"] for e in response.json()] == [str(POST)]
	assert await star(api, 2) is None  # seeded again on the next star
	assert skulls["count"] == 2
	assert skulls["entries"][0]["blocked"] is True


async def test_deleting_a_board_drops_stars_no_board_uses_any_more(api):
	await create(api, name="starboard", threshold=1)
	await create(api, name="hall-of-fame", threshold=2)
	await create(api, name="skulls", emoji="💀")
	await seed(api, [1])
	await seed(api, [1], emoji="💀")

	await api.client.delete(f"{BOARDS}/starboard", headers=api.internal)
	still_used = await star(api, 2)
	await api.client.delete(f"{BOARDS}/skulls", headers=api.internal)

	assert still_used["count"] == 2
	assert await api.db.fetchval("SELECT count(*) FROM starboard_messages WHERE emoji = '💀'") == 0


async def test_changing_a_board_emoji_drops_the_old_emoji_stars(api):
	await create(api)
	await seed(api, [1])

	await api.client.patch(f"{BOARDS}/starboard", json={"emoji": "💀"}, headers=api.internal)

	assert await api.db.fetchval("SELECT count(*) FROM starboard_messages") == 0


async def test_manager_creates_a_board_with_a_guild_emoji_and_the_bot_is_told(api, discord, events):
	auth = await sign_in(api)

	response = await api.client.post(
		f"/dashboard/guilds/{GUILD}/settings/starboards", json=board(emoji=str(EMOJI)), headers=auth
	)

	assert response.status_code == 201
	assert response.json()["emoji"] == str(EMOJI)
	assert await events.drain() == [
		{"type": "INVALIDATE_SETTING", "key": "starboard", "guild_id": str(GUILD), "origin": None}
	]


@pytest.mark.parametrize(
	("overrides", "code"),
	[
		({"channel_id": str(VOICE)}, "invalid_channel"),
		({"channel_id": str(ELSEWHERE)}, "invalid_channel"),
		({"channel_id": "404"}, "invalid_channel"),
		({"emoji": "987654321098765432"}, "invalid_emoji"),
	],
)
async def test_manager_cannot_use_a_channel_or_emoji_the_guild_does_not_have(api, discord, events, overrides, code):
	auth = await sign_in(api)

	response = await api.client.post(
		f"/dashboard/guilds/{GUILD}/settings/starboards", json=board(**overrides), headers=auth
	)

	assert response.status_code == 422
	assert response.json()["code"] == code
	assert await events.drain() == []


async def test_manager_updates_and_deletes_a_board(api, discord):
	auth = await sign_in(api)
	url = f"/dashboard/guilds/{GUILD}/settings/starboards"
	await api.client.post(url, json=board(), headers=auth)
	discord.calls.clear()

	patched = await api.client.patch(f"{url}/starboard", json={"threshold": 7}, headers=auth)
	deleted = await api.client.delete(f"{url}/starboard", headers=auth)

	assert patched.json()["threshold"] == 7
	assert not any(call.startswith("GET /channels/") for call in discord.calls)
	assert deleted.status_code == 204
	assert (await api.client.get(url, headers=auth)).json() == []


async def test_manager_lists_and_lifts_blocks(api, discord):
	auth = await sign_in(api)
	url = f"/dashboard/guilds/{GUILD}/settings/starboards/starboard/blocks"
	await create(api, threshold=1)
	await seed(api, [1])
	await post(api)
	await api.client.post(f"{STARS}/posts/deleted", json={"message_ids": [str(POST)]}, headers=api.internal)

	listed = await api.client.get(url, headers=auth)
	lifted = await api.client.delete(f"{url}/{MESSAGE}", headers=auth)
	message = await star(api, 2)

	assert listed.json() == [{"message_id": str(MESSAGE)}]
	assert lifted.status_code == 204
	assert message["entries"][0]["blocked"] is False
	assert (await api.client.get(url, headers=auth)).json() == []


async def test_blocks_of_an_unknown_board_are_not_found(api, discord):
	auth = await sign_in(api)

	response = await api.client.get(f"/dashboard/guilds/{GUILD}/settings/starboards/nope/blocks", headers=auth)

	assert response.status_code == 404
