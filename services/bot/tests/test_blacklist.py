"""The blacklist cache, the global check that enforces it, and how the bot answers a blacklisted command."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.blacklist import Blacklist, Blacklisted
from core.bot import Bot
from core.config import Config
from core.context import Context

from api import BlacklistEntry, BlacklistKind

OWNER, USER, OTHER_USER = 1, 2, 3
GUILD, OTHER_GUILD = 100, 200


class FakeBlacklistApi:
	"""`BlacklistApi` over a dict, like the Internal API."""

	def __init__(self) -> None:
		self.entries_by_target: dict[tuple[BlacklistKind, int], BlacklistEntry] = {}
		self.fail = False

	async def entries(self) -> list[BlacklistEntry]:
		if self.fail:
			raise RuntimeError("API down")
		return list(self.entries_by_target.values())

	async def add(self, kind: BlacklistKind, target_id: int, created_by: int, reason: str | None) -> BlacklistEntry:
		entry = BlacklistEntry(
			kind=kind,
			target_id=target_id,
			created_by=created_by,
			reason=reason,
			created_at=datetime.datetime.now(datetime.UTC),
		)
		self.entries_by_target[kind, target_id] = entry
		return entry

	async def remove(self, kind: BlacklistKind, target_id: int) -> bool:
		return self.entries_by_target.pop((kind, target_id), None) is not None


@pytest.fixture
def api() -> FakeBlacklistApi:
	return FakeBlacklistApi()


@pytest.fixture
def blacklist(api: FakeBlacklistApi) -> Blacklist:
	return Blacklist(SimpleNamespace(blacklist=api))  # ty: ignore[invalid-argument-type]


def context(user_id: int, guild_id: int | None) -> MagicMock:
	ctx = MagicMock()
	ctx.author.id = user_id
	ctx.guild = None if guild_id is None else SimpleNamespace(id=guild_id)
	ctx.bot.is_owner = AsyncMock(side_effect=lambda user: user.id == OWNER)
	return ctx


async def test_check_refuses_blacklisted_users_everywhere(blacklist):
	await blacklist.add("user", USER, OWNER, "spam")

	for guild_id in (GUILD, None):
		with pytest.raises(Blacklisted):
			await blacklist.check(context(USER, guild_id))
	assert await blacklist.check(context(OTHER_USER, GUILD))


async def test_check_refuses_everyone_in_a_blacklisted_guild_but_owners(blacklist):
	await blacklist.add("guild", GUILD, OWNER, None)

	with pytest.raises(Blacklisted):
		await blacklist.check(context(USER, GUILD))
	assert await blacklist.check(context(USER, OTHER_GUILD))
	assert await blacklist.check(context(USER, None))
	assert await blacklist.check(context(OWNER, GUILD))


async def test_check_loads_the_blacklist_first(api, blacklist):
	await api.add("user", USER, OWNER, None)

	with pytest.raises(Blacklisted):
		await blacklist.check(context(USER, GUILD))
	assert blacklist.loaded


async def test_failed_load_blocks_nobody_and_is_retried(api, blacklist):
	await api.add("user", USER, OWNER, None)
	api.fail = True

	assert await blacklist.check(context(USER, GUILD))
	assert not blacklist.loaded

	api.fail = False
	with pytest.raises(Blacklisted):
		await blacklist.check(context(USER, GUILD))


async def test_remove_unblocks_and_reports_whether_it_was_blacklisted(blacklist):
	await blacklist.add("user", USER, OWNER, None)

	assert await blacklist.remove("user", USER)
	assert not await blacklist.remove("user", USER)
	assert ("user", USER) not in blacklist


async def test_events_from_other_instances_update_the_cache(blacklist):
	added = {"type": "BLACKLIST_CHANGED", "kind": "guild", "target_id": str(GUILD), "blacklisted": True}
	removed = added | {"blacklisted": False}

	assert blacklist.handle_event(added)
	assert ("guild", GUILD) in blacklist
	assert blacklist.handle_event(removed)
	assert ("guild", GUILD) not in blacklist
	assert not blacklist.handle_event({"type": "INVALIDATE_SETTING", "key": "prefix", "guild_id": "1"})


@pytest.fixture
def bot() -> Bot:
	config = Config(
		debug=False,
		owner_ids=[OWNER],
		modules=[],
		log_channel_id=0,
		allowed_contexts={"guild": True, "dm_channel": True, "private_channel": True},
		allowed_installs={"guild": True, "user": True},
		allowed_mentions={"everyone": False, "roles": False, "users": False},
		emojis={},
	)
	return Bot(config=config)


def test_bot_checks_the_blacklist_before_every_command(bot):
	assert bot.blacklist.check in bot._checks


async def test_blacklisted_text_command_gets_no_answer(bot):
	ctx = MagicMock(spec=Context)
	ctx.command = None
	ctx.interaction = None
	ctx.send = AsyncMock()
	ctx.reply = AsyncMock()

	await bot.handle_error(ctx, Blacklisted())

	ctx.send.assert_not_called()
	ctx.reply.assert_not_called()


async def test_blacklisted_slash_command_is_answered(bot):
	ctx = MagicMock(spec=Context)
	ctx.command = None
	ctx.interaction = MagicMock()
	ctx.send = AsyncMock()

	await bot.handle_error(ctx, Blacklisted())

	ctx.send.assert_awaited_once_with("errors.blacklisted")
