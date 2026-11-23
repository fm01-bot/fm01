from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from cogs.config import Config
from core.settings import GuildSettings
from helpers.cli_parser import CLIParseError, CLIParser
from tests.fake_api import FakeCases


@pytest.fixture
def mock_ctx():
	ctx = MagicMock()
	ctx.guild = MagicMock()
	ctx.guild.id = 12345
	ctx.bot = MagicMock()
	ctx.bot.api.cases = FakeCases()
	ctx.bot.settings = GuildSettings(ctx.bot.event_bus)
	ctx.send = AsyncMock()
	return ctx


@pytest.mark.asyncio
async def test_config_mod_view_default(mock_ctx):
	config_cog = Config(mock_ctx.bot)

	tokens = CLIParser.split_args("mod")
	node, opts = config_cog.parser.parse(tokens)
	assert node.callback is not None
	await node.callback(mock_ctx, **opts)

	mock_ctx.send.assert_called_once()
	call_content = mock_ctx.send.call_args.kwargs.get("content", "")
	assert "Moderation case retention: keep" in call_content


@pytest.mark.asyncio
async def test_config_mod_set_delete(mock_ctx):
	config_cog = Config(mock_ctx.bot)

	tokens = CLIParser.split_args("mod --retention delete")
	node, opts = config_cog.parser.parse(tokens)
	assert node.callback is not None
	await node.callback(mock_ctx, **opts)

	# Stored through the API, which tells the other instances; cached here at once
	assert mock_ctx.bot.api.cases.retentions[12345] == "delete"
	assert mock_ctx.bot.settings["mod.retention"].cache[12345] == "delete"
	call_content = mock_ctx.send.call_args.kwargs.get("content", "")
	assert "Moderation case retention set to delete" in call_content


@pytest.mark.asyncio
async def test_config_mod_invalid_retention(mock_ctx):
	config_cog = Config(mock_ctx.bot)

	tokens = CLIParser.split_args("mod --retention purge")
	node, opts = config_cog.parser.parse(tokens)
	assert node.callback is not None

	with pytest.raises(CLIParseError, match="must be either 'keep' or 'delete'"):
		await node.callback(mock_ctx, **opts)
