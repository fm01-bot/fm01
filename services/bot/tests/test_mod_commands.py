"""Moderation and Cases commands, with the Case module replaced by a double (it has its own database tests)."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from cogs.mod import Cases, CaseStore, CaseType, Moderation, Mute, Warn, _purge_check
from discord.ext import commands


@pytest.fixture
def mock_bot():
	bot = MagicMock()
	bot.db = AsyncMock()
	return bot


@pytest.fixture
def store():
	return MagicMock(spec=CaseStore)


@pytest.fixture
def mod_cog(mock_bot, store):
	return Moderation(mock_bot, store)


@pytest.fixture
def cases_cog(mock_bot, store):
	return Cases(mock_bot, store)


@pytest.fixture
def mock_ctx(mock_bot):
	ctx = MagicMock()
	ctx.guild = MagicMock()
	ctx.guild.id = 12345
	ctx.guild.unban = AsyncMock()
	ctx.author = MagicMock(spec=discord.Member)
	ctx.author.id = 999
	ctx.author.guild_permissions.moderate_members = True
	ctx.send = AsyncMock()
	ctx.bot = mock_bot
	return ctx


def make_warn(mock_bot, mock_ctx, case_id: int = 123, **kwargs) -> Warn:
	return Warn(case_id, mock_bot, mock_ctx.guild, mock_ctx.author, mock_ctx.author, **kwargs)


def make_member(timed_out: bool) -> MagicMock:
	member = MagicMock(spec=discord.Member)
	member.id = 42
	member.edit = AsyncMock()
	member.timed_out_until = datetime.datetime.now(tz=datetime.UTC) if timed_out else None
	return member


async def test_case_delete(cases_cog, store, mock_bot, mock_ctx):
	case = make_warn(mock_bot, mock_ctx)
	store.get.return_value = case

	await cases_cog.delete.callback(cases_cog, mock_ctx, "123")

	store.delete.assert_awaited_once_with(case)
	mock_ctx.send.assert_awaited_once_with("mod.delete.response", case=case)


@pytest.mark.parametrize(
	("outcome", "key"), [("deactivated", "mod.remove.response"), ("deleted", "mod.delete.response")]
)
async def test_case_remove_reports_the_retention_outcome(cases_cog, store, mock_bot, mock_ctx, outcome, key):
	case = make_warn(mock_bot, mock_ctx)
	store.get.return_value = case
	store.close.return_value = outcome

	await cases_cog.remove.callback(cases_cog, mock_ctx, "123")

	store.close.assert_awaited_once_with(case)
	mock_ctx.send.assert_awaited_once_with(key, case=case)


async def test_case_remove_unknown_case(cases_cog, store, mock_ctx):
	store.get.return_value = None

	await cases_cog.remove.callback(cases_cog, mock_ctx, "123")

	store.close.assert_not_awaited()
	mock_ctx.send.assert_awaited_once_with("mod.remove.errors.not_found", case_id=123)


async def test_case_edit_expires(cases_cog, store, mock_bot, mock_ctx):
	case = make_warn(mock_bot, mock_ctx, reason="Initial")
	store.get.return_value = case

	await cases_cog.edit.callback(cases_cog, mock_ctx, "123", "expires", new_value="1h")

	(edited,), kwargs = store.edit.await_args
	assert edited is case
	assert set(kwargs) == {"expires"}
	assert kwargs["expires"] > datetime.datetime.now(tz=datetime.UTC)
	mock_ctx.send.assert_awaited_once_with("mod.edit.response", case=case)


async def test_case_edit_rejects_invalid_time(cases_cog, store, mock_bot, mock_ctx):
	store.get.return_value = make_warn(mock_bot, mock_ctx)

	await cases_cog.edit.callback(cases_cog, mock_ctx, "123", "expires", new_value="soon")

	store.edit.assert_not_awaited()
	mock_ctx.send.assert_awaited_once_with("mod.edit.errors.invalid_time", case_id=123)


async def test_case_list_permissions(cases_cog, mock_ctx):
	mock_ctx.author.id = 111
	mock_ctx.author.guild_permissions.moderate_members = False
	target_user = MagicMock(spec=discord.Member)
	target_user.id = 222

	with pytest.raises(commands.MissingPermissions):
		await cases_cog.list.callback(cases_cog, mock_ctx, user=target_user)


@pytest.mark.parametrize(("is_moderator", "status"), [(True, "all"), (False, "active")])
async def test_case_list_default_filter(cases_cog, store, mock_ctx, is_moderator, status):
	cases_cog.custom_response.get_message = AsyncMock(
		return_value={"embeds": [discord.Embed.from_dict({"fields": [{"name": "{case.id}", "value": "x"}]})]}
	)
	store.for_user.return_value = []
	mock_ctx.author.guild_permissions.moderate_members = is_moderator

	await cases_cog.list.callback(cases_cog, mock_ctx)

	store.for_user.assert_awaited_once_with(mock_ctx.guild, mock_ctx.author, status)


async def test_case_list_paginates(cases_cog, store, mock_bot, mock_ctx):
	cases_cog.custom_response.get_message = AsyncMock(
		return_value={
			"embeds": [discord.Embed.from_dict({"fields": [{"name": "{case.id}", "value": "{case.reason}"}]})]
		}
	)
	store.for_user.return_value = [make_warn(mock_bot, mock_ctx, i, reason=f"Reason {i}") for i in range(1, 8)]

	await cases_cog.list.callback(cases_cog, mock_ctx)

	send_kwargs = mock_ctx.send.call_args.kwargs
	assert len(send_kwargs["view"].pages) == 2


async def test_unban_closes_active_bans(mod_cog, store, mock_bot, mock_ctx):
	user = MagicMock(spec=discord.User)
	ban_case = MagicMock()
	store.active.return_value = [ban_case]

	await mod_cog.unban.callback(mod_cog, mock_ctx, user)

	store.active.assert_awaited_once_with(mock_ctx.guild, user, CaseType.BAN)
	store.close.assert_awaited_once_with(ban_case)
	mock_ctx.guild.unban.assert_not_awaited()
	mock_ctx.send.assert_awaited_once_with("mod.unban.response", user=user)


async def test_unban_without_case_unbans_directly(mod_cog, store, mock_ctx):
	user = MagicMock(spec=discord.User)
	store.active.return_value = []

	await mod_cog.unban.callback(mod_cog, mock_ctx, user)

	mock_ctx.guild.unban.assert_awaited_once()


@pytest.mark.parametrize(
	("has_case", "timed_out", "key"),
	[
		(True, True, "mod.unmute.response"),
		(True, False, "mod.unmute.timeout_already_removed"),
		(False, True, "mod.unmute.no_case"),
		(False, False, "mod.unmute.errors.not_muted"),
	],
)
async def test_unmute(mod_cog, store, mock_ctx, has_case, timed_out, key):
	member = make_member(timed_out)
	mute_case = MagicMock(spec=Mute)
	store.active.return_value = [mute_case] if has_case else []

	await mod_cog.unmute.callback(mod_cog, mock_ctx, member)

	store.active.assert_awaited_once_with(mock_ctx.guild, member, CaseType.MUTE)
	if has_case:
		store.close.assert_awaited_once_with(mute_case)
	# Without a case the command lifts the timeout itself; with one, Mute.before_deletion does it.
	assert member.edit.await_count == (1 if timed_out and not has_case else 0)
	mock_ctx.send.assert_awaited_once_with(key, member=member, user=member)


def make_message(
	author_id: int = 1,
	bot: bool = False,
	content: str = "",
	pinned: bool = False,
	attachments: bool = False,
	embeds: bool = False,
	components_v2: bool = False,
) -> MagicMock:
	message = MagicMock(spec=discord.Message)
	message.author.id = author_id
	message.author.bot = bot
	message.content = content
	message.pinned = pinned
	message.attachments = [MagicMock()] if attachments else []
	message.embeds = [MagicMock()] if embeds else []
	message.flags.components_v2 = components_v2
	return message


@pytest.mark.parametrize(
	("filter", "message", "deleted"),
	[
		(None, make_message(), True),
		(None, make_message(pinned=True), False),
		("bots", make_message(bot=True), True),
		("bots", make_message(), False),
		("humans", make_message(), True),
		("humans", make_message(bot=True), False),
		("links", make_message(content="see https://example.com"), True),
		("links", make_message(content="no link here"), False),
		("attachments", make_message(attachments=True), True),
		("attachments", make_message(), False),
		("embeds", make_message(embeds=True), True),
		("embeds", make_message(components_v2=True), True),
		("embeds", make_message(), False),
	],
)
def test_purge_check_filters(filter, message, deleted):
	assert _purge_check(None, filter, None)(message) is deleted


def test_purge_check_user_and_contains():
	check = _purge_check(MagicMock(id=7), None, "SPAM")

	assert check(make_message(author_id=7, content="buy spam now"))
	assert not check(make_message(author_id=8, content="buy spam now"))
	assert not check(make_message(author_id=7, content="hello"))


def make_purge_ctx(mock_ctx, history: list[MagicMock], interaction: bool) -> MagicMock:
	async def scan(**kwargs):
		for message in history:
			yield message

	mock_ctx.channel = MagicMock(spec=discord.TextChannel)
	mock_ctx.channel.history = MagicMock(side_effect=scan)
	mock_ctx.channel.delete_messages = AsyncMock()
	mock_ctx.defer = AsyncMock()
	mock_ctx.interaction = MagicMock(id=555) if interaction else None
	mock_ctx.message.delete = AsyncMock()
	return mock_ctx


async def test_purge_deletes_amount_matching_messages_not_amount_scanned(mod_cog, mock_ctx):
	mod_cog.custom_response = AsyncMock(return_value="reason")
	mine = [make_message(author_id=7) for _ in range(3)]
	history = [make_message(author_id=8), mine[0], make_message(author_id=8), mine[1], mine[2]]
	ctx = make_purge_ctx(mock_ctx, history, interaction=False)

	await mod_cog.purge.callback(mod_cog, ctx, 2, MagicMock(id=7))

	ctx.channel.delete_messages.assert_awaited_once_with(mine[:2], reason="reason")
	assert ctx.channel.history.call_args.kwargs["before"] is ctx.message
	assert ctx.channel.history.call_args.kwargs["oldest_first"] is False
	ctx.message.delete.assert_awaited_once()
	ctx.send.assert_awaited_once_with("mod.purge.response", channel=ctx.channel, count=2)


async def test_purge_bulk_deletes_in_chunks_of_100(mod_cog, mock_ctx):
	mod_cog.custom_response = AsyncMock(return_value="reason")
	ctx = make_purge_ctx(mock_ctx, [make_message() for _ in range(250)], interaction=False)

	await mod_cog.purge.callback(mod_cog, ctx, 250)

	assert [len(call.args[0]) for call in ctx.channel.delete_messages.await_args_list] == [100, 100, 50]


async def test_purge_slash_scans_from_before_the_interaction(mod_cog, mock_ctx):
	mod_cog.custom_response = AsyncMock(return_value="reason")
	ctx = make_purge_ctx(mock_ctx, [make_message(pinned=True)], interaction=True)

	await mod_cog.purge.callback(mod_cog, ctx, 10)

	ctx.defer.assert_awaited_once()
	assert ctx.channel.history.call_args.kwargs["before"].id == 555
	ctx.channel.delete_messages.assert_not_awaited()
	ctx.message.delete.assert_not_awaited()
	ctx.send.assert_awaited_once_with("mod.purge.none", channel=ctx.channel)


async def test_purge_rejects_unpurgeable_channels(mod_cog, mock_ctx):
	mock_ctx.channel = MagicMock(spec=discord.DMChannel)

	with pytest.raises(commands.BadArgument):
		await mod_cog.purge.callback(mod_cog, mock_ctx, 10)


def _hierarchy_ctx(mock_ctx, *, author_role: int, bot_role: int, owner_id: int = 1) -> MagicMock:
	mock_ctx.guild.owner_id = owner_id
	mock_ctx.author.top_role = author_role
	mock_ctx.me = MagicMock(spec=discord.Member)
	mock_ctx.guild.me = mock_ctx.me
	mock_ctx.me.top_role = bot_role
	return mock_ctx


def _target(mock_ctx, role: int, *, administrator: bool = False) -> MagicMock:
	member = MagicMock(spec=discord.Member)
	member.id = 42
	member.guild = mock_ctx.guild
	member.top_role = role
	member.guild_permissions.administrator = administrator
	return member


@pytest.mark.parametrize(
	("author_role", "target_role", "bot_role", "owner_id", "key"),
	[
		(5, 5, 10, 1, "mod.kick.errors.hierarchy"),
		(5, 7, 10, 1, "mod.kick.errors.hierarchy"),
		(9, 5, 3, 1, "mod.kick.errors.bot_hierarchy"),
		(1, 5, 10, 999, None),  # the owner may kick anyone below the bot
		(9, 5, 10, 42, "mod.kick.errors.hierarchy"),  # nobody kicks the owner
	],
)
async def test_kick_checks_the_role_hierarchy(
	mod_cog, store, mock_ctx, author_role, target_role, bot_role, owner_id, key
):
	ctx = _hierarchy_ctx(mock_ctx, author_role=author_role, bot_role=bot_role, owner_id=owner_id)
	member = _target(ctx, target_role)

	await mod_cog.kick.callback(mod_cog, ctx, member, reason="r")

	if key is None:
		store.open.assert_awaited_once()
	else:
		store.open.assert_not_awaited()
		ctx.send.assert_awaited_once_with(key)


async def test_ban_checks_the_hierarchy_of_members(mod_cog, store, mock_ctx):
	ctx = _hierarchy_ctx(mock_ctx, author_role=5, bot_role=10)
	member = _target(ctx, 7)
	ctx.guild.get_member.return_value = member
	user = MagicMock(spec=discord.User)
	user.id = member.id

	await mod_cog.ban.callback(mod_cog, ctx, user, None, reason="r")

	store.open.assert_not_awaited()
	ctx.send.assert_awaited_once_with("mod.ban.errors.hierarchy")


async def test_mute_refuses_administrators(mod_cog, store, mock_ctx):
	ctx = _hierarchy_ctx(mock_ctx, author_role=9, bot_role=10)
	member = _target(ctx, 5, administrator=True)

	await mod_cog.mute.callback(mod_cog, ctx, member, "1h")

	store.open.assert_not_awaited()
	ctx.send.assert_awaited_once_with("mod.mute.errors.administrator")


@pytest.mark.parametrize("command", ["remove", "delete", "edit"])
async def test_closing_a_ban_case_needs_ban_members(cases_cog, store, mock_bot, mock_ctx, command):
	mock_ctx.author.guild_permissions.ban_members = False
	case = make_warn(mock_bot, mock_ctx)
	case.type = CaseType.BAN
	store.get.return_value = case
	args = ("123", "expires") if command == "edit" else ("123",)
	kwargs = {"new_value": "1s"} if command == "edit" else {}

	with pytest.raises(commands.MissingPermissions):
		await getattr(cases_cog, command).callback(cases_cog, mock_ctx, *args, **kwargs)

	store.close.assert_not_awaited()
	store.delete.assert_not_awaited()
	store.edit.assert_not_awaited()
