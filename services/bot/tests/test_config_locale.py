from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from cogs.config import Config
from core.settings import GuildSettings, locale_override_setting
from helpers.cli_parser import CLIParseError, CLIParser
from helpers.custom_response import CustomResponse


@pytest.fixture
def mock_ctx():
	ctx = MagicMock()
	ctx.guild = MagicMock()
	ctx.guild.id = 12345
	ctx.guild.preferred_locale = discord.Locale.american_english
	ctx.bot = MagicMock()
	ctx.bot.event_bus = MagicMock()
	ctx.bot.event_bus.publish = AsyncMock()
	ctx.bot.api = MagicMock()
	ctx.bot.api.settings.locale = AsyncMock(return_value=None)
	ctx.bot.api.settings.set_locale = AsyncMock()
	ctx.bot.settings = GuildSettings(ctx.bot.event_bus)
	ctx.bot.locale_override = locale_override_setting(ctx.bot.settings, ctx.bot.api)
	ctx.bot.locale_cache = ctx.bot.locale_override.cache
	ctx.send = AsyncMock()
	return ctx


@pytest.mark.asyncio
async def test_config_locale_view_default_no_override(mock_ctx):
	config_cog = Config(mock_ctx.bot)
	mock_ctx.bot.api.settings.locale.return_value = None

	tokens = CLIParser.split_args("locale")
	node, opts = config_cog.parser.parse(tokens)
	assert node.callback is not None
	await node.callback(mock_ctx, **opts)

	mock_ctx.send.assert_called_once()
	call_content = mock_ctx.send.call_args.kwargs.get("content", "")
	assert "Locale: en-US" in call_content


@pytest.mark.asyncio
async def test_config_locale_view_with_cached_override(mock_ctx):
	config_cog = Config(mock_ctx.bot)
	mock_ctx.bot.locale_override.remember(12345, "hu")

	tokens = CLIParser.split_args("locale")
	node, opts = config_cog.parser.parse(tokens)
	assert node.callback is not None
	await node.callback(mock_ctx, **opts)

	mock_ctx.send.assert_called_once()
	call_content = mock_ctx.send.call_args.kwargs.get("content", "")
	assert "Locale: hu (override)" in call_content
	assert "Server: en-US" in call_content


@pytest.mark.asyncio
async def test_config_locale_view_fallback_to_api(mock_ctx):
	config_cog = Config(mock_ctx.bot)
	mock_ctx.bot.api.settings.locale.return_value = "hu"

	tokens = CLIParser.split_args("locale")
	node, opts = config_cog.parser.parse(tokens)
	assert node.callback is not None
	await node.callback(mock_ctx, **opts)

	assert mock_ctx.bot.locale_cache.get(12345) == "hu"
	mock_ctx.send.assert_called_once()
	call_content = mock_ctx.send.call_args.kwargs.get("content", "")
	assert "Locale: hu (override)" in call_content


@pytest.mark.asyncio
async def test_config_locale_set_option(mock_ctx):
	config_cog = Config(mock_ctx.bot)

	tokens = CLIParser.split_args("locale --locale hu")
	node, opts = config_cog.parser.parse(tokens)
	assert node.callback is not None
	await node.callback(mock_ctx, **opts)

	mock_ctx.bot.api.settings.set_locale.assert_awaited_once_with(12345, "hu")
	assert mock_ctx.bot.locale_cache[12345] == "hu"
	mock_ctx.bot.event_bus.publish.assert_not_called()  # the API announces the change

	# Verify response message
	mock_ctx.send.assert_called_once()
	call_content = mock_ctx.send.call_args.kwargs.get("content", "")
	assert "[+] Locale set to hu" in call_content


@pytest.mark.asyncio
async def test_config_locale_set_positional(mock_ctx):
	config_cog = Config(mock_ctx.bot)

	tokens = CLIParser.split_args("locale hu")
	node, opts = config_cog.parser.parse(tokens)
	assert node.callback is not None
	await node.callback(mock_ctx, **opts)

	assert mock_ctx.bot.locale_cache[12345] == "hu"
	call_content = mock_ctx.send.call_args.kwargs.get("content", "")
	assert "[+] Locale set to hu" in call_content


@pytest.mark.asyncio
async def test_config_locale_clear_default(mock_ctx):
	config_cog = Config(mock_ctx.bot)
	mock_ctx.bot.locale_override.remember(12345, "hu")

	tokens = CLIParser.split_args("locale --default")
	node, opts = config_cog.parser.parse(tokens)
	assert node.callback is not None
	await node.callback(mock_ctx, **opts)

	mock_ctx.bot.api.settings.set_locale.assert_awaited_once_with(12345, None)
	assert mock_ctx.bot.locale_cache[12345] is None
	mock_ctx.bot.event_bus.publish.assert_not_called()

	# Verify response message
	call_content = mock_ctx.send.call_args.kwargs.get("content", "")
	assert "[+] Locale override cleared. Using server locale (en-US)" in call_content


@pytest.mark.asyncio
async def test_config_locale_invalid_code(mock_ctx):
	config_cog = Config(mock_ctx.bot)

	tokens = CLIParser.split_args("locale --locale en-US")
	node, opts = config_cog.parser.parse(tokens)
	assert node.callback is not None

	with pytest.raises(CLIParseError, match="Locales use two letter country codes"):
		await node.callback(mock_ctx, **opts)


@pytest.mark.asyncio
async def test_config_locale_dm_error(mock_ctx):
	mock_ctx.guild = None
	config_cog = Config(mock_ctx.bot)

	tokens = CLIParser.split_args("locale")
	node, opts = config_cog.parser.parse(tokens)
	assert node.callback is not None

	with pytest.raises(CLIParseError, match="This command can only be used in a server"):
		await node.callback(mock_ctx, **opts)


@pytest.mark.asyncio
async def test_custom_response_respects_locale_cache():
	bot = MagicMock()
	bot.debug = False
	bot.config.emojis = {"check": "✅", "x": "❌"}
	bot.locale_cache = {12345: "hu"}

	cr = CustomResponse(bot)
	cr.update_localizations(
		{
			"en": {"test": {"greeting": "Hello"}},
			"hu": {"test": {"greeting": "Szia"}},
		}
	)

	guild = MagicMock(spec=discord.Guild)
	guild.id = 12345
	guild.preferred_locale = "en"

	ctx = MagicMock()
	ctx.guild = guild
	ctx.author = MagicMock(spec=discord.Member)
	ctx.author.guild = guild
	ctx.author.id = 1
	ctx.author.name = "testuser"
	ctx.author.roles = []
	ctx.author.display_avatar.url = ""

	res = await cr.get_message("test.greeting", ctx)
	assert str(res) == "Szia"
