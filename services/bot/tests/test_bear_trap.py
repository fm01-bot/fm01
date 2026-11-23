"""The bear trap: who it catches, the softban it opens, and keeping its message in step with the API."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from cogs import bear_trap as module
from cogs.bear_trap import BearTrap, BearTrapSoftban, is_exempt, missing_permissions, needs_reconcile
from cogs.mod.cases import SOFTBAN_DELETE_SECONDS, CaseType, Softban

from api import BearTrapState

GUILD, TRAP, OTHER = 1, 10, 20


def http_error(status: int) -> discord.HTTPException:
	cls = {403: discord.Forbidden, 404: discord.NotFound}.get(status, discord.HTTPException)
	return cls(MagicMock(status=status, reason="x"), "x")


class FakeSetting:
	"""The bear trap guild setting, without the API behind it."""

	def __init__(self, **traps: BearTrapState) -> None:
		self.cache: dict[int, BearTrapState] = {GUILD: traps["trap"]} if "trap" in traps else {}

	async def get(self, guild_id: int) -> BearTrapState:
		return self.cache.get(guild_id, BearTrapState())

	def remember(self, guild_id: int, value: BearTrapState) -> None:
		self.cache[guild_id] = value


def fake_setting(**traps: BearTrapState) -> Any:
	return FakeSetting(**traps)


@pytest.fixture
def guild():
	guild = MagicMock(spec=discord.Guild)
	guild.id = GUILD
	guild.owner_id = 1000
	guild.me = SimpleNamespace(top_role=10)
	return guild


@pytest.fixture
def cog(guild, monkeypatch):
	monkeypatch.setattr(module, "is_guild_on_shard", lambda bot, guild_id: True)
	bot = MagicMock()
	bot.wait_until_ready = AsyncMock()
	bot.get_guild.return_value = guild
	bot.api.bear_trap = AsyncMock()
	cog = BearTrap(bot)
	cog.setting = fake_setting(trap=BearTrapState(channel_id=TRAP, message_channel_id=TRAP, message_id=500, kicks=4))
	cog.cases = MagicMock()
	cog.cases.open = AsyncMock(side_effect=lambda case: case)
	cog.responses = MagicMock()
	cog.responses.get_message = AsyncMock(return_value="Posted in the bear trap channel")
	cog._invite = AsyncMock(return_value="https://discord.gg/abc")
	return cog


def make_member(guild, **overrides) -> MagicMock:
	member = MagicMock(spec=discord.Member)
	member.id = overrides.get("id", 42)
	member.guild = guild
	member.bot = overrides.get("bot", False)
	member.top_role = overrides.get("top_role", 1)
	member.guild_permissions = discord.Permissions(**overrides.get("permissions", {}))
	return member


def make_message(guild, member, *, channel_id: int = TRAP, **overrides) -> MagicMock:
	message = MagicMock(spec=discord.Message)
	message.id = overrides.get("id", 900)
	message.guild = guild
	message.channel = SimpleNamespace(id=channel_id)
	message.author = member
	message.webhook_id = overrides.get("webhook_id")
	message.type = overrides.get("type", discord.MessageType.default)
	message.delete = AsyncMock()
	return message


@pytest.mark.parametrize(
	("trap", "expected"),
	[
		(BearTrapState(), False),
		(BearTrapState(channel_id=TRAP), True),
		(BearTrapState(channel_id=TRAP, message_channel_id=TRAP, message_id=5), False),
		(BearTrapState(channel_id=OTHER, message_channel_id=TRAP, message_id=5), True),
		(BearTrapState(message_channel_id=TRAP, message_id=5), True),
	],
)
def test_needs_reconcile(trap, expected):
	assert needs_reconcile(trap) is expected


@pytest.mark.parametrize(
	("overrides", "exempt"),
	[
		({}, False),
		({"bot": True}, True),
		({"id": 1000}, True),
		({"permissions": {"administrator": True}}, True),
		({"permissions": {"manage_guild": True}}, True),
		({"permissions": {"manage_messages": True, "ban_members": True}}, False),
		({"top_role": 10}, True),
		({"top_role": 11}, True),
	],
)
def test_who_is_exempt(guild, overrides, exempt):
	assert is_exempt(make_member(guild, **overrides)) is exempt


def test_missing_permissions_splits_required_and_optional(guild):
	channel = MagicMock(spec=discord.TextChannel)
	channel.guild = guild
	channel.permissions_for.return_value = discord.Permissions(view_channel=True, send_messages=True)

	required, optional = missing_permissions(channel)

	assert required == ["read_message_history", "manage_messages", "ban_members"]
	assert optional == ["create_instant_invite"]


async def test_a_member_who_posts_is_softbanned_with_an_invite_and_counted(cog, guild):
	cog.bot.api.bear_trap.add_kick.return_value = 5
	cog._schedule_counter_update = MagicMock()
	message = make_message(guild, make_member(guild))

	await cog.on_message(message)

	message.delete.assert_awaited_once()
	(case,) = cog.cases.open.await_args.args
	assert isinstance(case, BearTrapSoftban)
	assert case.type is CaseType.SOFTBAN
	assert (case.id, case.invite, case.reason) == (900, "https://discord.gg/abc", "Posted in the bear trap channel")
	assert cog.setting.cache[GUILD].kicks == 5
	cog._schedule_counter_update.assert_called_once_with(GUILD)


@pytest.mark.parametrize(
	"message_overrides",
	[
		{"channel_id": OTHER},
		{"webhook_id": 7},
		{"type": discord.MessageType.new_member},
		{"type": discord.MessageType.thread_created},
	],
)
async def test_messages_that_are_not_a_member_posting_in_the_trap_are_ignored(cog, guild, message_overrides):
	message = make_message(guild, make_member(guild), **message_overrides)

	await cog.on_message(message)

	message.delete.assert_not_awaited()
	cog.cases.open.assert_not_awaited()


async def test_exempt_members_keep_their_message(cog, guild):
	message = make_message(guild, make_member(guild, permissions={"administrator": True}))

	await cog.on_message(message)

	message.delete.assert_not_awaited()
	cog.cases.open.assert_not_awaited()


async def test_nothing_happens_when_the_trap_is_off(cog, guild):
	cog.setting = fake_setting()
	message = make_message(guild, make_member(guild))

	await cog.on_message(message)

	cog.cases.open.assert_not_awaited()


async def test_a_burst_of_messages_softbans_once(cog, guild):
	cog.bot.api.bear_trap.add_kick.return_value = 5
	cog._schedule_counter_update = MagicMock()
	release = asyncio.Event()

	async def slow_open(case):
		await release.wait()
		return case

	cog.cases.open = AsyncMock(side_effect=slow_open)
	member = make_member(guild)
	first, second = make_message(guild, member, id=1), make_message(guild, member, id=2)

	task = asyncio.create_task(cog.on_message(first))
	await asyncio.sleep(0)
	await cog.on_message(second)
	release.set()
	await task

	second.delete.assert_awaited_once()
	assert cog.cases.open.await_count == 1
	cog.bot.api.bear_trap.add_kick.assert_awaited_once()


async def test_a_failed_softban_is_not_counted(cog, guild):
	cog.cases.open = AsyncMock(side_effect=http_error(403))
	message = make_message(guild, make_member(guild))

	await cog.on_message(message)

	message.delete.assert_awaited_once()
	cog.bot.api.bear_trap.add_kick.assert_not_awaited()


async def test_a_member_who_left_before_the_ban_is_not_counted(cog, guild):
	cog.cases.open = AsyncMock(return_value=None)

	await cog.on_message(make_message(guild, make_member(guild)))

	cog.bot.api.bear_trap.add_kick.assert_not_awaited()


def make_softban(guild, cls=Softban, **kwargs) -> Softban:
	case = cls(900, MagicMock(), guild, make_member(guild), guild.me, "reason", **kwargs)
	case._audit_reason = AsyncMock(return_value="audit")
	case._notify = AsyncMock()
	return case


async def test_softban_bans_with_message_deletion_then_unbans(guild):
	case = make_softban(guild)

	await case.after_creation()

	(user,), kwargs = guild.ban.await_args
	assert user.id == 42
	assert kwargs == {"reason": "audit", "delete_message_seconds": SOFTBAN_DELETE_SECONDS}
	assert guild.unban.await_args.args[0].id == 42


async def test_softban_keeps_the_case_when_the_unban_fails(guild):
	guild.unban.side_effect = http_error(500)

	await make_softban(guild).after_creation()  # doesn't raise, so the case isn't rolled back


async def test_bear_trap_softban_dms_the_notice_with_the_invite(guild):
	case = make_softban(guild, BearTrapSoftban, invite="https://discord.gg/abc")
	case._notify = notify = AsyncMock()
	case._audit_reason = audit_reason = AsyncMock(return_value="audit")

	await case.before_creation()
	await case.after_creation()

	notify.assert_awaited_once_with("bear_trap.notify", softban=case, invite="https://discord.gg/abc")
	audit_reason.assert_awaited_with("bear_trap.reason")


def make_channel(channel_id: int, *, sent_id: int = 777) -> MagicMock:
	channel = MagicMock(spec=discord.TextChannel)
	channel.id = channel_id
	channel.send = AsyncMock(return_value=SimpleNamespace(id=sent_id, channel=SimpleNamespace(id=channel_id)))
	channel.fetch_message = AsyncMock()
	partial = MagicMock()
	partial.delete = AsyncMock()
	partial.edit = AsyncMock()
	channel.get_partial_message.return_value = partial
	return channel


@pytest.fixture
def channels(guild, monkeypatch):
	monkeypatch.setattr(module, "missing_permissions", lambda channel: ([], []))
	found = {TRAP: make_channel(TRAP), OTHER: make_channel(OTHER, sent_id=888)}
	guild.get_channel.side_effect = found.get
	return found


def api_records_messages(cog) -> None:
	async def set_message(guild_id, channel_id, message_id):
		trap = cog.setting.cache[guild_id]
		return trap.model_copy(update={"message_channel_id": channel_id, "message_id": message_id})

	cog.bot.api.bear_trap.set_message = AsyncMock(side_effect=set_message)


async def test_reconcile_posts_the_message_when_the_trap_is_set(cog, channels):
	cog.setting = fake_setting(trap=BearTrapState(channel_id=TRAP, kicks=4))
	api_records_messages(cog)

	assert await cog.reconcile(GUILD)

	channels[TRAP].send.assert_awaited_once()
	cog.bot.api.bear_trap.set_message.assert_awaited_once_with(GUILD, TRAP, 777)
	assert cog.setting.cache[GUILD].message_id == 777


async def test_reconcile_moves_the_message_to_the_new_channel(cog, channels):
	cog.setting = fake_setting(trap=BearTrapState(channel_id=OTHER, message_channel_id=TRAP, message_id=500))
	api_records_messages(cog)

	assert await cog.reconcile(GUILD)

	channels[TRAP].get_partial_message.assert_called_once_with(500)
	channels[TRAP].get_partial_message.return_value.delete.assert_awaited_once()
	channels[OTHER].send.assert_awaited_once()
	assert cog.setting.cache[GUILD].message_id == 888


async def test_reconcile_deletes_the_message_when_the_trap_is_turned_off(cog, channels):
	cog.setting = fake_setting(trap=BearTrapState(message_channel_id=TRAP, message_id=500))
	api_records_messages(cog)

	assert await cog.reconcile(GUILD)

	channels[TRAP].get_partial_message.return_value.delete.assert_awaited_once()
	cog.bot.api.bear_trap.set_message.assert_awaited_once_with(GUILD, None, None)
	channels[TRAP].send.assert_not_awaited()


async def test_reconcile_reposts_a_message_deleted_by_hand_when_verifying(cog, channels):
	api_records_messages(cog)
	channels[TRAP].fetch_message.side_effect = http_error(404)

	assert await cog.reconcile(GUILD, verify=True)

	channels[TRAP].send.assert_awaited_once()
	assert cog.setting.cache[GUILD].message_id == 777


async def test_reconcile_leaves_a_message_in_place(cog, channels):
	assert await cog.reconcile(GUILD, verify=True)

	channels[TRAP].send.assert_not_awaited()
	cog.bot.api.bear_trap.set_message.assert_not_awaited()


async def test_reconcile_turns_the_trap_off_when_it_cannot_post(cog, channels):
	cog.setting = fake_setting(trap=BearTrapState(channel_id=TRAP))
	channels[TRAP].send.side_effect = http_error(403)
	cog.bot.api.bear_trap.set_channel.return_value = BearTrapState()

	assert not await cog.reconcile(GUILD)

	cog.bot.api.bear_trap.set_channel.assert_awaited_once_with(GUILD, None)
	assert cog.setting.cache[GUILD].channel_id is None


async def test_reconcile_skips_guilds_on_other_instances(cog, channels, monkeypatch):
	monkeypatch.setattr(module, "is_guild_on_shard", lambda bot, guild_id: False)
	cog.setting = fake_setting(trap=BearTrapState(channel_id=TRAP))

	assert not await cog.reconcile(GUILD)

	channels[TRAP].send.assert_not_awaited()


async def test_counter_update_edits_the_message_once(cog, channels, monkeypatch):
	monkeypatch.setattr(module, "COUNTER_DELAY", 0)
	cog._layout = AsyncMock(return_value={})

	cog._schedule_counter_update(GUILD)
	cog._schedule_counter_update(GUILD)
	await asyncio.gather(*cog._background)

	channels[TRAP].get_partial_message.return_value.edit.assert_awaited_once()


async def test_counter_update_forgets_a_message_deleted_by_hand(cog, channels, monkeypatch):
	monkeypatch.setattr(module, "COUNTER_DELAY", 0)
	cog._layout = AsyncMock(return_value={})
	api_records_messages(cog)
	channels[TRAP].get_partial_message.return_value.edit.side_effect = http_error(404)

	await cog._update_counter(GUILD)

	cog.bot.api.bear_trap.set_message.assert_awaited_once_with(GUILD, None, None)


@pytest.fixture
def responses():
	from helpers.custom_response import CustomResponse

	bot = MagicMock()
	bot.debug = False
	return CustomResponse(bot)


async def test_the_trap_message_shows_the_count_on_a_disabled_button(responses):
	payload = await responses.get_message("bear_trap.message", "en", guild=SimpleNamespace(id=GUILD), kicks=7)

	buttons = [item for item in payload["view"].walk_children() if isinstance(item, discord.ui.Button)]
	assert [(b.label, b.disabled) for b in buttons] == [("🐻 7 caught", True)]
	assert payload["allowed_mentions"].to_dict() == discord.AllowedMentions.none().to_dict()


@pytest.mark.parametrize(("invite", "shown"), [("https://discord.gg/abc", True), (None, False)])
async def test_the_notice_drops_the_rejoin_line_without_an_invite(responses, invite, shown):
	payload = await responses.get_message("bear_trap.notify", "en", guild="Server", invite=invite)

	description = payload["embeds"][0].description
	assert "Change your Discord password" in description
	assert ("rejoin" in description) is shown
