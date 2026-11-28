"""Suggestions: posting, voting and deciding through the cog, with the API faked and the real localized messages."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from cogs.config import Config
from cogs.suggestions import Suggestions, SuggestionVoteButton, missing_permissions
from core import Bot
from core.settings import GuildSettings
from helpers.cli_parser import CLIParseError, CLIParser
from helpers.custom_response import CustomResponse
from tests.fake_api import FakeSuggestions

from api import SuggestionConfig, Vote

GUILD, CHANNEL, MESSAGE, AUTHOR, MODERATOR = 100, 200, 300, 7, 5
ALL_PERMISSIONS = discord.Permissions(view_channel=True, send_messages=True, embed_links=True)


@pytest.fixture
def channel() -> MagicMock:
	channel = MagicMock(spec=discord.TextChannel)
	channel.id = CHANNEL
	channel.name = "suggestions"
	channel.is_news.return_value = False
	channel.permissions_for.return_value = ALL_PERMISSIONS
	channel.send = AsyncMock(return_value=SimpleNamespace(id=MESSAGE, jump_url="https://discord.test/jump"))
	channel.get_partial_message.return_value.edit = AsyncMock()
	return channel


@pytest.fixture
def guild(channel) -> MagicMock:
	guild = MagicMock(spec=discord.Guild)
	guild.id = GUILD
	guild.preferred_locale = discord.Locale.american_english
	guild.get_channel.side_effect = lambda channel_id: channel if channel_id == CHANNEL else None
	guild.channels = [channel]
	guild.threads = []
	return guild


@pytest.fixture
def cog(guild) -> Suggestions:
	bot = MagicMock()
	bot.debug = False
	bot.locale_cache = None
	bot.settings = GuildSettings(bot.event_bus)
	bot.api.suggestions = FakeSuggestions()
	bot.custom_response = CustomResponse(bot)
	return Suggestions(bot)


@pytest.fixture
def api(cog) -> FakeSuggestions:
	return cog.bot.api.suggestions


def enable(api: FakeSuggestions, **config) -> None:
	api.configs[GUILD] = SuggestionConfig(channel_id=CHANNEL, **config)


def make_ctx(guild, author_id: int = AUTHOR) -> MagicMock:
	ctx = MagicMock()
	ctx.guild = guild
	ctx.author.id = author_id
	ctx.send = AsyncMock()
	return ctx


def make_interaction(user_id: int) -> MagicMock:
	interaction = MagicMock(spec=discord.Interaction)
	interaction.guild_id = GUILD
	user = MagicMock(spec=discord.User)
	user.id = user_id
	user.name = user.global_name = user.display_name = "voter"
	user.discriminator = "0"
	user.bot = False
	user.accent_color = None
	user.display_avatar.url = "https://cdn.example.com/avatar.png"
	user.avatar_decoration = None
	user.banner = None
	user.created_at = None
	user.mention = f"<@{user_id}>"
	interaction.user = user
	interaction.locale = discord.Locale.american_english
	interaction.response = MagicMock()
	interaction.response.edit_message = AsyncMock()
	interaction.response.send_message = AsyncMock()
	return interaction


def buttons(view: discord.ui.View) -> list[discord.ui.Button]:
	"""The vote buttons a suggestion's view shows."""
	items = [child.item for child in view.children if isinstance(child, SuggestionVoteButton)]
	assert len(items) == len(view.children)
	return items


def counts(view: discord.ui.View) -> tuple[str | None, str | None]:
	up, down = buttons(view)
	return up.label, down.label


async def suggest(cog: Suggestions, ctx, content: str = "More emoji") -> None:
	await cog.suggest.callback(cog, ctx, content=content)


async def posted_view(channel: MagicMock) -> discord.ui.View:
	return channel.send.call_args.kwargs["view"]


# Posting


async def test_suggest_posts_the_embed_with_vote_buttons_and_records_the_message(cog, api, guild, channel):
	enable(api)
	ctx = make_ctx(guild)

	await suggest(cog, ctx)

	kwargs = channel.send.call_args.kwargs
	embed = kwargs["embeds"][0]
	assert embed.title == "Suggestion #1"
	assert embed.description == "More emoji"
	assert f"<@{AUTHOR}>" in [field.value for field in embed.fields]
	assert counts(kwargs["view"]) == ("0", "0")
	assert [button.custom_id for button in buttons(kwargs["view"])] == ["suggestion:1:up", "suggestion:1:down"]
	stored = await api.get(GUILD, 1)
	assert stored is not None
	assert (stored.channel_id, stored.message_id) == (CHANNEL, MESSAGE)
	ctx.send.assert_awaited_once_with("suggestions.suggest.success", url="https://discord.test/jump")


async def test_suggestions_are_numbered_in_order(cog, api, guild, channel):
	enable(api)

	await suggest(cog, make_ctx(guild))
	await suggest(cog, make_ctx(guild), "Another")

	assert channel.send.call_args.kwargs["embeds"][0].title == "Suggestion #2"


async def test_suggest_says_so_when_suggestions_are_off(cog, api, guild, channel):
	ctx = make_ctx(guild)

	await suggest(cog, ctx)

	ctx.send.assert_awaited_once_with("suggestions.errors.disabled")
	channel.send.assert_not_awaited()


async def test_suggest_says_so_when_the_channel_is_gone(cog, api, guild, channel):
	api.configs[GUILD] = SuggestionConfig(channel_id=999)
	ctx = make_ctx(guild)

	await suggest(cog, ctx)

	ctx.send.assert_awaited_once_with("suggestions.errors.disabled")


async def test_suggest_does_not_create_a_suggestion_the_bot_cannot_post(cog, api, guild, channel):
	enable(api)
	channel.permissions_for.return_value = discord.Permissions(view_channel=True)
	ctx = make_ctx(guild)

	await suggest(cog, ctx)

	ctx.send.assert_awaited_once_with("suggestions.errors.cannot_post")
	assert api.suggestions == {}


async def test_suggest_reports_a_failed_post(cog, api, guild, channel):
	enable(api)
	channel.send.side_effect = discord.Forbidden(MagicMock(status=403, reason="x"), "x")
	ctx = make_ctx(guild)

	await suggest(cog, ctx)

	ctx.send.assert_awaited_once_with("suggestions.errors.cannot_post")


async def test_suggest_opens_a_thread_when_threads_are_on(cog, api, guild, channel):
	enable(api, threads=True)
	message = channel.send.return_value
	message.create_thread = AsyncMock()

	await suggest(cog, make_ctx(guild))

	message.create_thread.assert_awaited_once_with(name="Suggestion #1")


async def test_suggest_opens_no_thread_when_threads_are_off(cog, api, guild, channel):
	enable(api)
	message = channel.send.return_value
	message.create_thread = AsyncMock()

	await suggest(cog, make_ctx(guild))

	message.create_thread.assert_not_awaited()


async def test_a_failed_thread_does_not_fail_the_suggestion(cog, api, guild, channel):
	enable(api, threads=True)
	channel.send.return_value.create_thread = AsyncMock(
		side_effect=discord.Forbidden(MagicMock(status=403, reason="x"), "x")
	)
	ctx = make_ctx(guild)

	await suggest(cog, ctx)

	ctx.send.assert_awaited_once_with("suggestions.suggest.success", url="https://discord.test/jump")


# Voting


async def test_votes_update_the_counts_on_the_buttons(cog, api, guild):
	enable(api)
	await suggest(cog, make_ctx(guild))
	shown = []

	for user, vote in [(1, Vote.UP), (2, Vote.DOWN), (3, Vote.UP)]:
		interaction = make_interaction(user)
		await cog.handle_vote(interaction, 1, vote)
		shown.append(counts(interaction.response.edit_message.call_args.kwargs["view"]))

	assert shown == [("1", "0"), ("1", "1"), ("2", "1")]


async def test_voting_the_same_way_twice_takes_the_vote_back_and_the_other_way_switches_it(cog, api, guild):
	enable(api)
	await suggest(cog, make_ctx(guild))
	shown = []

	for vote in [Vote.UP, Vote.UP, Vote.UP, Vote.DOWN]:
		interaction = make_interaction(1)
		await cog.handle_vote(interaction, 1, vote)
		shown.append(counts(interaction.response.edit_message.call_args.kwargs["view"]))

	assert shown == [("1", "0"), ("0", "0"), ("1", "0"), ("0", "1")]


async def test_voting_on_an_unknown_suggestion_answers_with_an_error(cog, api):
	interaction = make_interaction(1)

	await cog.handle_vote(interaction, 9, Vote.UP)

	interaction.response.edit_message.assert_not_awaited()
	sent = interaction.response.send_message.call_args.kwargs
	assert "no suggestion #9" in sent["content"]
	assert sent["ephemeral"] is True


async def test_the_vote_button_reaches_the_cog():
	cog = MagicMock(spec=Suggestions)
	cog.handle_vote = AsyncMock()
	interaction = MagicMock()
	interaction.client = MagicMock(spec=Bot)
	interaction.client.get_cog.return_value = cog

	await SuggestionVoteButton(4, Vote.DOWN).callback(interaction)

	cog.handle_vote.assert_awaited_once_with(interaction, 4, Vote.DOWN)


@pytest.mark.parametrize(
	("custom_id", "number", "vote"), [("suggestion:12:up", 12, Vote.UP), ("suggestion:3:down", 3, Vote.DOWN)]
)
async def test_the_button_is_rebuilt_from_its_custom_id_after_a_restart(custom_id, number, vote):
	match = SuggestionVoteButton.__discord_ui_compiled_template__.fullmatch(custom_id)
	assert match is not None

	button = await SuggestionVoteButton.from_custom_id(MagicMock(), MagicMock(), match)

	assert (button.number, button.vote) == (number, vote)


# Deciding


async def test_approving_records_the_decision_and_re_renders_the_message_with_disabled_buttons(
	cog, api, guild, channel
):
	enable(api)
	await suggest(cog, make_ctx(guild))
	await cog.handle_vote(make_interaction(1), 1, Vote.UP)
	ctx = make_ctx(guild, MODERATOR)

	await cog.approve.callback(cog, ctx, 1, reason="Good idea")

	decided = await api.get(GUILD, 1)
	assert decided is not None
	assert decided.decision is not None
	assert (decided.decision.status, decided.decision.moderator_id, decided.decision.reason) == (
		"approved",
		MODERATOR,
		"Good idea",
	)
	channel.get_partial_message.assert_called_with(MESSAGE)
	edit = channel.get_partial_message.return_value.edit.call_args.kwargs
	fields = {field.name: field.value for field in edit["embeds"][0].fields}
	assert fields["Status"] == "✅ Approved"
	assert fields["Reason"] == "Good idea"
	assert fields["Approved by"] == f"<@{MODERATOR}>"
	assert [button.disabled for button in buttons(edit["view"])] == [True, True]
	assert counts(edit["view"]) == ("1", "0")
	ctx.send.assert_awaited_once_with("suggestions.decision.approved", number=1)


async def test_denying_without_a_reason_shows_no_reason_field(cog, api, guild, channel):
	enable(api)
	await suggest(cog, make_ctx(guild))

	await cog.deny.callback(cog, make_ctx(guild, MODERATOR), 1, reason=None)

	embed = channel.get_partial_message.return_value.edit.call_args.kwargs["embeds"][0]
	assert "Reason" not in [field.name for field in embed.fields]
	assert {field.name: field.value for field in embed.fields}["Status"] == "❌ Denied"


async def test_a_decided_suggestion_refuses_votes_with_an_error(cog, api, guild):
	enable(api)
	await suggest(cog, make_ctx(guild))
	await cog.deny.callback(cog, make_ctx(guild, MODERATOR), 1, reason=None)
	interaction = make_interaction(1)

	await cog.handle_vote(interaction, 1, Vote.UP)

	interaction.response.edit_message.assert_not_awaited()
	sent = interaction.response.send_message.call_args.kwargs
	assert "Suggestion #1 is decided" in sent["content"]
	assert sent["ephemeral"] is True
	assert (await api.get(GUILD, 1)).up == 0  # type: ignore[union-attr]


async def test_deciding_an_unknown_suggestion_says_so(cog, guild):
	ctx = make_ctx(guild, MODERATOR)

	await cog.approve.callback(cog, ctx, 9, reason=None)

	ctx.send.assert_awaited_once_with("suggestions.errors.not_found", number=9)


async def test_a_vanished_message_does_not_fail_the_decision(cog, api, guild, channel):
	enable(api)
	await suggest(cog, make_ctx(guild))
	channel.get_partial_message.return_value.edit.side_effect = discord.NotFound(MagicMock(status=404, reason="x"), "x")
	ctx = make_ctx(guild, MODERATOR)

	await cog.approve.callback(cog, ctx, 1, reason=None)

	ctx.send.assert_awaited_once_with("suggestions.decision.approved", number=1)


def test_missing_permissions_names_what_the_bot_lacks(channel):
	channel.permissions_for.return_value = discord.Permissions(view_channel=True)

	assert missing_permissions(channel) == ["send_messages", "embed_links"]


# ?!config suggestions


def config_ctx(cog, guild, channel) -> MagicMock:
	ctx = make_ctx(guild)
	ctx.bot.get_cog.return_value = cog
	return ctx


async def run(ctx, line: str):
	node, opts = Config(ctx.bot).parser.parse(CLIParser.split_args(line))
	assert node.callback is not None
	return await node.callback(ctx, **opts)


async def test_config_channel_turns_suggestions_on_and_keeps_threads(cog, api, guild, channel):
	api.configs[GUILD] = SuggestionConfig(threads=True)

	await run(config_ctx(cog, guild, channel), "suggestions channel #suggestions")

	assert api.configs[GUILD] == SuggestionConfig(channel_id=CHANNEL, threads=True)


async def test_config_channel_refuses_a_channel_the_bot_cannot_post_in(cog, api, guild, channel):
	channel.permissions_for.return_value = discord.Permissions(view_channel=True)

	with pytest.raises(CLIParseError, match="send_messages, embed_links"):
		await run(config_ctx(cog, guild, channel), "suggestions channel #suggestions")

	assert GUILD not in api.configs


async def test_config_off_turns_suggestions_off(cog, api, guild, channel):
	enable(api, threads=True)

	await run(config_ctx(cog, guild, channel), "suggestions off")

	assert api.configs[GUILD] == SuggestionConfig(channel_id=None, threads=True)


@pytest.mark.parametrize(("state", "expected"), [("on", True), ("off", False)])
async def test_config_threads_switches_threads(cog, api, guild, channel, state, expected):
	enable(api, threads=not expected)

	await run(config_ctx(cog, guild, channel), f"suggestions threads {state}")

	assert api.configs[GUILD] == SuggestionConfig(channel_id=CHANNEL, threads=expected)


async def test_config_threads_needs_on_or_off(cog, api, guild, channel):
	with pytest.raises(CLIParseError):
		await run(config_ctx(cog, guild, channel), "suggestions threads maybe")


async def test_config_status_shows_the_channel_and_threads(cog, api, guild, channel):
	enable(api, threads=True)
	ctx = config_ctx(cog, guild, channel)

	await run(ctx, "suggestions")

	shown = ctx.send.call_args.kwargs["content"]
	assert "Suggestions: on in #suggestions" in shown
	assert "Threads: on" in shown
