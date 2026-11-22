"""``?!config starboard``: parsing boards into API calls and API refusals into readable errors."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from cogs.config import Config
from cogs.starboard import Starboards
from core.api import ApiError
from helpers.cli_parser import CLIParseError, CLIParser

from api import ErrorBody, ErrorCode, Starboard, StarboardUpdate

GUILD, BOARD_CHANNEL, OTHER = 12345, 20, 30
EMOJI = 123456789012345678


def text_channel(channel_id: int, name: str) -> MagicMock:
	channel = MagicMock(spec=discord.TextChannel)
	channel.id = channel_id
	channel.name = name
	channel.is_news.return_value = False
	channel.permissions_for.return_value = discord.Permissions(view_channel=True, send_messages=True, embed_links=True)
	return channel


@pytest.fixture
def ctx():
	channels = {BOARD_CHANNEL: text_channel(BOARD_CHANNEL, "starboard"), OTHER: text_channel(OTHER, "memes")}
	ctx = MagicMock()
	ctx.guild.id = GUILD
	ctx.guild.channels = list(channels.values())
	ctx.guild.threads = []
	ctx.guild.get_channel.side_effect = channels.get
	ctx.guild.get_channel_or_thread.side_effect = channels.get
	ctx.guild.get_emoji.side_effect = lambda emoji_id: SimpleNamespace(name="party") if emoji_id == EMOJI else None
	ctx.bot.api.starboard = AsyncMock()
	ctx.bot.api.starboard.boards.return_value = [Starboard(name="stars", channel_id=BOARD_CHANNEL)]
	ctx.bot.api.starboard.create.side_effect = lambda guild_id, board: board
	ctx.bot.api.starboard.update.return_value = Starboard(name="stars", channel_id=BOARD_CHANNEL, enabled=False)
	cog = Starboards(ctx.bot)
	cog.setting = fake(cache={}, remember=MagicMock(), get=AsyncMock(return_value=[]))
	ctx.bot.get_cog.return_value = cog
	ctx.send = AsyncMock()
	return ctx


def fake(**attributes: Any) -> Any:
	return SimpleNamespace(**attributes)


async def run(ctx, line: str):
	node, opts = Config(ctx.bot).parser.parse(CLIParser.split_args(line))
	assert node.callback is not None
	return await node.callback(ctx, **opts)


async def test_create_sends_the_board_with_a_custom_emoji_id(ctx):
	await run(ctx, f"starboard create Stars #starboard -e <:party:{EMOJI}> -t 5 -a 7")

	ctx.bot.api.starboard.create.assert_awaited_once_with(
		GUILD, Starboard(name="stars", channel_id=BOARD_CHANNEL, emoji=str(EMOJI), threshold=5, max_age_days=7)
	)
	assert "[+] stars [on] :party: x5 -> #starboard" in ctx.send.call_args.kwargs["content"]


async def test_create_refuses_an_emoji_from_another_server(ctx):
	with pytest.raises(CLIParseError, match="not an emoji of this server"):
		await run(ctx, "starboard create stars #starboard -e <:other:987654321098765432>")


async def test_create_refuses_a_channel_the_bot_cannot_post_in(ctx):
	ctx.guild.get_channel(BOARD_CHANNEL).permissions_for.return_value = discord.Permissions(view_channel=True)

	with pytest.raises(CLIParseError, match="send_messages, embed_links"):
		await run(ctx, "starboard create stars #starboard")


@pytest.mark.parametrize(
	("code", "text"),
	[
		(ErrorCode.STARBOARD_LIMIT, "at most 5"),
		(ErrorCode.STARBOARD_NAME_TAKEN, "already has that name"),
		(ErrorCode.STARBOARD_TIER_TAKEN, "emoji with that threshold"),
	],
)
async def test_api_refusals_become_readable_errors(ctx, code, text):
	ctx.bot.api.starboard.create.side_effect = ApiError(409, ErrorBody(code=code, message="x"))

	with pytest.raises(CLIParseError, match=text):
		await run(ctx, "starboard create stars #starboard")


async def test_edit_sends_only_what_changed(ctx):
	await run(ctx, "starboard edit stars --enabled off --mode allowlist --channels '#memes' --max-age off")

	ctx.bot.api.starboard.update.assert_awaited_once()
	changes = ctx.bot.api.starboard.update.await_args.args[2]
	assert changes == StarboardUpdate(enabled=False, channel_mode="allowlist", channel_ids=[OTHER], max_age_days=None)
	assert changes.model_fields_set == {"enabled", "channel_mode", "channel_ids", "max_age_days"}


async def test_edit_without_changes_is_refused(ctx):
	with pytest.raises(CLIParseError, match="Nothing to change"):
		await run(ctx, "starboard edit stars")


async def test_delete_removes_the_board_and_reloads(ctx):
	await run(ctx, "starboard delete stars")

	ctx.bot.api.starboard.delete.assert_awaited_once_with(GUILD, "stars")
	ctx.bot.get_cog.return_value.setting.remember.assert_called_once()
