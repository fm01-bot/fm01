"""CaseStore against an in-memory API that behaves like the Internal API. Discord objects are faked."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from cogs.mod import Ban, CaseStore, CaseType, Kick, Mute, Warn
from tests.fake_api import FakeCases

from api import CaseCreate

GUILD_ID = 1 << 22
NOW = datetime.datetime.now(tz=datetime.UTC)


class FakeScheduler:
	"""Records what the store asked to schedule."""

	def __init__(self) -> None:
		self.scheduled: dict[int, datetime.datetime] = {}

	def schedule_at(self, key: int, guild_id: int, expires: datetime.datetime) -> None:
		self.scheduled[key] = expires

	def cancel(self, key: int) -> None:
		self.scheduled.pop(key, None)

	def start(self) -> None: ...
	def stop(self) -> None: ...


def make_user(user_id: int) -> MagicMock:
	user = MagicMock(spec=discord.Member)
	user.id = user_id
	user.send = AsyncMock()
	user.timed_out_until = None
	user.edit = AsyncMock()
	return user


@pytest.fixture
def world() -> dict[str, Any]:
	moderator = make_user(1)
	target = make_user(2)
	other = make_user(3)
	users = {u.id: u for u in (moderator, target, other)}

	guild = MagicMock(spec=discord.Guild)
	guild.id = GUILD_ID
	guild.get_member = MagicMock(side_effect=users.get)
	guild.ban = AsyncMock()
	guild.unban = AsyncMock()

	bot = MagicMock()
	bot.api.cases = FakeCases()
	bot.get_guild = MagicMock(side_effect=lambda gid: guild if gid == GUILD_ID else None)
	bot.get_user = MagicMock(side_effect=users.get)
	return {"bot": bot, "guild": guild, "moderator": moderator, "target": target, "other": other}


@pytest.fixture(autouse=True)
def silent_notifications():
	"""DM notifications render localization; these tests only care about the database and Discord calls."""
	with patch("cogs.mod.cases.custom_response.CustomResponse") as response_cls:
		response_cls.return_value.get_message = AsyncMock(return_value=None)
		response_cls.return_value.side_effect = AsyncMock(return_value=None)
		yield


@pytest.fixture
def scheduler() -> FakeScheduler:
	return FakeScheduler()


@pytest.fixture
def api(world: dict[str, Any]) -> FakeCases:
	return world["bot"].api.cases


@pytest.fixture
def store(world: dict[str, Any], scheduler: FakeScheduler) -> CaseStore:
	return CaseStore(world["bot"], scheduler)


def warn(world: dict[str, Any], case_id: int, user: Any = None, **kwargs: Any) -> Warn:
	return Warn(case_id, world["bot"], world["guild"], user or world["target"], world["moderator"], **kwargs)


def ban(world: dict[str, Any], case_id: int, user: Any = None, **kwargs: Any) -> Ban:
	return Ban(case_id, world["bot"], world["guild"], user or world["target"], world["moderator"], **kwargs)


def mute(world: dict[str, Any], case_id: int, expires: datetime.datetime, user: Any = None) -> Mute:
	return Mute(case_id, world["bot"], world["guild"], user or world["target"], world["moderator"], expires)


async def test_get_returns_the_matching_subclass(store, world):
	await store.open(warn(world, 10, reason="spam"))
	await store.open(ban(world, 11))
	await store.open(Kick(12, world["bot"], world["guild"], world["target"], world["moderator"]))

	assert type(await store.get(world["guild"], 10)) is Warn
	assert type(await store.get(world["guild"], 11)) is Ban
	assert type(await store.get(world["guild"], 12)) is Kick
	assert (await store.get(world["guild"], 10)).reason == "spam"
	assert await store.get(world["guild"], 999) is None


async def test_active_only_returns_active_cases_of_that_type_for_that_user(store, world):
	await store.open(warn(world, 20))
	await store.open(ban(world, 21))
	await store.open(ban(world, 22, user=world["other"]))
	closed = await store.open(ban(world, 23))
	await store.close(closed)

	bans = await store.active(world["guild"], world["target"], CaseType.BAN)

	assert [case.id for case in bans] == [21]


async def test_closing_bans_leaves_other_case_types_alone(store, world, api):
	"""Regression: unban used to deactivate every case the user had."""
	await store.open(warn(world, 30))
	await store.open(mute(world, 31, NOW + datetime.timedelta(hours=1)))
	await store.open(ban(world, 32))

	for case in await store.active(world["guild"], world["target"], CaseType.BAN):
		await store.close(case)

	rows = {case_id: case.active for case_id, case in api.cases.items()}
	assert rows == {30: True, 31: True, 32: False}
	world["guild"].unban.assert_awaited_once()


async def test_close_reports_what_the_api_did_under_retention(store, world, api):
	await store.open(warn(world, 40))
	assert await store.close(await store.get(world["guild"], 40)) == "deactivated"
	assert api.cases[40].active is False

	await api.set_retention(GUILD_ID, "delete")
	await store.open(warn(world, 41))
	assert await store.close(await store.get(world["guild"], 41)) == "deleted"
	assert 41 not in api.cases


async def test_closing_an_inactive_case_does_not_repeat_side_effects(store, world):
	case = await store.open(ban(world, 50))
	await store.close(case)
	world["guild"].unban.reset_mock()

	await store.close(await store.get(world["guild"], 50))

	world["guild"].unban.assert_not_awaited()


async def test_open_schedules_expiry_and_close_cancels_it(store, world, scheduler):
	expires = NOW + datetime.timedelta(hours=2)
	case = await store.open(warn(world, 60, expires=expires))
	assert scheduler.scheduled == {60: expires}

	await store.close(case)
	assert scheduler.scheduled == {}


async def test_edit_persists_and_reschedules(store, world, scheduler, api):
	case = await store.open(warn(world, 70, reason="old", expires=NOW + datetime.timedelta(hours=1)))
	new_expiry = NOW + datetime.timedelta(days=1)

	await store.edit(case, reason="new", expires=new_expiry)

	assert api.cases[70].reason == "new"
	assert api.cases[70].expires == new_expiry
	assert scheduler.scheduled == {70: new_expiry}


async def test_open_skips_non_members_except_for_bans(store, world, api):
	stranger = make_user(404)

	assert await store.open(warn(world, 80, user=stranger)) is None
	assert await store.open(ban(world, 81, user=stranger)) is not None
	assert list(api.cases) == [81]


async def test_failed_side_effect_rolls_the_case_back(store, world, api):
	world["guild"].ban.side_effect = discord.HTTPException(MagicMock(status=403), "missing permissions")

	with pytest.raises(discord.HTTPException):
		await store.open(ban(world, 90))

	assert api.cases == {}


async def test_for_user_filters_by_status(store, world):
	await store.open(warn(world, 100))
	await store.open(warn(world, 101, expires=NOW - datetime.timedelta(minutes=1)))
	await store.close(await store.open(warn(world, 102)))

	async def ids(status):
		return sorted(case.id for case in await store.for_user(world["guild"], world["target"], status))

	assert await ids("active") == [100]
	assert await ids("expired") == [101, 102]
	assert await ids("all") == [100, 101, 102]


async def test_expire_closes_due_case_and_drops_cases_of_left_guilds(store, world, api):
	await store.open(warn(world, 110, expires=NOW + datetime.timedelta(minutes=1)))
	await api.create(
		999 << 22,
		CaseCreate(case_id=111, type=CaseType.WARN.value, user_id=2, moderator_id=1, expires=NOW, created=NOW),
	)

	assert sorted(key for key, _, _ in await store.pending()) == [110, 111]
	await store.expire(110)
	await store.expire(111)

	assert api.cases[110].active is False
	assert 111 not in api.cases


async def test_listing_fetches_each_uncached_user_once(store, world):
	"""Cases whose moderator isn't cached cost one API call per distinct moderator, not one per case."""
	absent_mod = make_user(77)
	for case_id in range(200, 206):
		await store.open(Warn(case_id, world["bot"], world["guild"], world["target"], absent_mod))
	world["bot"].get_user = MagicMock(side_effect=lambda uid: world["target"] if uid == world["target"].id else None)
	world["bot"].fetch_user = AsyncMock(return_value=absent_mod)

	cases = await store.for_user(world["guild"], world["target"])

	assert len(cases) == 6
	assert all(case._moderator is absent_mod for case in cases)
	world["bot"].fetch_user.assert_awaited_once_with(77)
