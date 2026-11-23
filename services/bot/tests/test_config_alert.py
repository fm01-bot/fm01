from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from cogs.config import Config
from helpers.cli_parser import CLIParseError, CLIParser
from tests.fake_api import alert


@pytest.fixture
def config_cog():
	mock_bot = MagicMock()
	mock_bot.api.alerts = MagicMock()
	mock_bot.config = MagicMock()
	mock_bot.get_cog = MagicMock(return_value=None)
	return Config(mock_bot)


def test_cli_parsing_alert_add(config_cog):
	tokens = CLIParser.split_args("alert add youtube @TechGuy #alerts")
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "add"
	assert opts["platform"] == "youtube"
	assert opts["account"] == "@TechGuy"
	assert opts["channel_pos"] == "#alerts"


def test_cli_parsing_alert_remove(config_cog):
	tokens = CLIParser.split_args("alert remove 3")
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "remove"
	assert opts["target"] == "3"

	tokens2 = CLIParser.split_args("alert remove youtube @TechGuy")
	node2, opts2 = config_cog.parser.parse(tokens2)
	assert node2.name == "remove"
	assert opts2["target"] == "youtube"
	assert opts2["account"] == "@TechGuy"


def test_cli_parsing_alert_list(config_cog):
	tokens = CLIParser.split_args("alert list")
	node, _opts = config_cog.parser.parse(tokens)
	assert node.name == "list"


def test_cli_parsing_alert_enable_disable(config_cog):
	node_en, opts_en = config_cog.parser.parse(["alert", "enable", "2"])
	assert node_en.name == "enable"
	assert opts_en["target"] == "2"

	node_dis, opts_dis = config_cog.parser.parse(["alert", "disable", "2"])
	assert node_dis.name == "disable"
	assert opts_dis["target"] == "2"


@pytest.mark.asyncio
async def test_alert_add_execution(config_cog):
	ctx = MagicMock()
	ctx.bot = config_cog.client
	ctx.guild = MagicMock()
	ctx.guild.id = 123
	ctx.channel = MagicMock(spec=discord.TextChannel)
	ctx.channel.id = 555
	ctx.channel.name = "general"
	ctx.guild.channels = [ctx.channel]
	ctx.guild.threads = []
	ctx.guild.get_channel = MagicMock(return_value=ctx.channel)
	ctx.guild.get_channel_or_thread = MagicMock(return_value=ctx.channel)
	ctx.send = AsyncMock()

	# Under limit (currently 1 alert)
	ctx.bot.api.alerts.for_guild = AsyncMock(return_value=[alert()])
	ctx.bot.api.alerts.add = AsyncMock(return_value=alert(id=7))

	await config_cog.parser.execute("alert add youtube @CoolGuy #general", ctx=ctx)
	ctx.send.assert_called_once()
	assert "Alert #7 successfully added" in ctx.send.call_args[1]["content"]


@pytest.mark.asyncio
async def test_alert_add_limit_reached(config_cog):
	ctx = MagicMock()
	ctx.bot = config_cog.client
	ctx.guild = MagicMock()
	ctx.guild.id = 123
	ctx.channel = MagicMock(spec=discord.TextChannel)
	ctx.channel.id = 555
	ctx.channel.name = "general"

	# Already at 5 limit
	ctx.bot.api.alerts.for_guild = AsyncMock(return_value=[alert(id=i) for i in range(5)])

	with pytest.raises(CLIParseError, match="maximum limit of 5"):
		await config_cog.parser.execute("alert add youtube @CoolGuy", ctx=ctx)


@pytest.mark.asyncio
async def test_alert_add_unsupported_platform(config_cog):
	ctx = MagicMock()
	ctx.guild = MagicMock()

	with pytest.raises(CLIParseError, match="Unsupported platform"):
		await config_cog.parser.execute("alert add myspace @User", ctx=ctx)


@pytest.mark.asyncio
async def test_alert_remove_execution(config_cog):
	ctx = MagicMock()
	ctx.bot = config_cog.client
	ctx.guild = MagicMock()
	ctx.guild.id = 123
	ctx.send = AsyncMock()
	ctx.bot.api.alerts.remove = AsyncMock(return_value=True)

	await config_cog.parser.execute("alert remove 10", ctx=ctx)
	ctx.bot.api.alerts.remove.assert_awaited_once_with(123, 10)
	ctx.send.assert_called_once()
	assert "Alert #10 removed" in ctx.send.call_args[1]["content"]


@pytest.mark.asyncio
async def test_alert_list_execution(config_cog):
	ctx = MagicMock()
	ctx.bot = config_cog.client
	ctx.guild = MagicMock()
	ctx.guild.id = 123
	target_channel = MagicMock()
	target_channel.name = "alerts"
	ctx.guild.get_channel = MagicMock(return_value=target_channel)
	ctx.send = AsyncMock()

	ctx.bot.api.alerts.for_guild = AsyncMock(
		return_value=[
			alert(id=1, platform="youtube", channel_account="@creator", account_name="Creator", enabled=True),
			alert(id=2, platform="twitch", channel_account="streamer", account_name="Streamer", enabled=False),
		]
	)

	await config_cog.parser.execute("alert list", ctx=ctx)
	ctx.send.assert_called_once()
	content = ctx.send.call_args[1]["content"]
	assert "Configured Social Media Alerts (2/5)" in content
	assert "#1 [YOUTUBE] Creator -> #alerts [Active]" in content
	assert "#2 [TWITCH] Streamer -> #alerts [Disabled]" in content


@pytest.mark.asyncio
async def test_alert_enable_disable_execution(config_cog):
	ctx = MagicMock()
	ctx.bot = config_cog.client
	ctx.guild = MagicMock()
	ctx.guild.id = 123
	ctx.send = AsyncMock()
	ctx.bot.api.alerts.set_enabled = AsyncMock(return_value=True)

	await config_cog.parser.execute("alert enable 1", ctx=ctx)
	assert "Alert #1 enabled" in ctx.send.call_args[1]["content"]
	ctx.bot.api.alerts.set_enabled.assert_awaited_with(123, 1, True)

	await config_cog.parser.execute("alert disable 1", ctx=ctx)
	assert "Alert #1 disabled" in ctx.send.call_args[1]["content"]
	ctx.bot.api.alerts.set_enabled.assert_awaited_with(123, 1, False)


@pytest.mark.asyncio
async def test_alert_add_twitch_without_credentials_fails(config_cog, monkeypatch):
	monkeypatch.delenv("TWITCH_CLIENT_ID", raising=False)
	monkeypatch.delenv("TWITCH_CLIENT_SECRET", raising=False)
	ctx = MagicMock()
	ctx.bot = config_cog.client
	ctx.guild = MagicMock()
	ctx.guild.id = 123
	ctx.channel = MagicMock(spec=discord.TextChannel)
	ctx.bot.api.alerts.for_guild = AsyncMock(return_value=[])
	ctx.bot.api.alerts.add = AsyncMock()

	with pytest.raises(CLIParseError, match="Twitch alerts are not configured"):
		await config_cog.parser.execute("alert add twitch playhubstreams", ctx=ctx)
	ctx.bot.api.alerts.add.assert_not_called()
