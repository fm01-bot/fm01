from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from args.media import Media
from cogs.alerts import OFFLINE_BASELINE, Alerts
from tests.fake_api import alert


@pytest.fixture
def mock_bot():
	bot = MagicMock()
	bot.api.alerts = MagicMock()
	bot.wait_until_ready = AsyncMock()
	bot.config = MagicMock()
	bot.config.emojis = {"check": "✅", "x": "❌"}
	bot.custom_response = MagicMock()
	bot.custom_response.convert_embeds = MagicMock(side_effect=lambda x: x)
	bot.custom_response.convert_components = MagicMock(side_effect=lambda x: x)
	bot.custom_response.get_message = AsyncMock(
		return_value={
			"content": None,
			"embeds": [
				discord.Embed(
					title="Epic Video",
					url="https://youtube.com/watch?v=abc1234",
					description="Cool description",
				)
			],
		}
	)
	return bot


@pytest.fixture
def alerts_cog(mock_bot):
	return Alerts(mock_bot)


@pytest.mark.asyncio
async def test_dispatch_alert_localized_embed(alerts_cog, mock_bot):
	guild = MagicMock(spec=discord.Guild)
	guild.id = 123
	guild.name = "My Server"
	guild.preferred_locale = "en"
	guild.members = []
	guild.channels = []
	guild.roles = []

	channel = MagicMock(spec=discord.TextChannel)
	channel.id = 999
	channel.name = "media-alerts"
	channel.guild = guild
	channel.send = AsyncMock()
	guild.get_channel = MagicMock(return_value=channel)
	mock_bot.get_guild = MagicMock(return_value=guild)

	media = Media.create(
		url="https://youtube.com/watch?v=abc1234",
		title="Epic Video",
		author_name="GamerPro",
		author_url="https://youtube.com/@GamerPro",
		media_id="abc1234",
		platform="youtube",
	)

	alert_row = alert(id=1, guild_id=123, target_channel_id=999)

	sent = await alerts_cog.dispatch_alert(alert_row, media)
	assert sent is True
	mock_bot.custom_response.get_message.assert_called_once_with(
		"alerts.youtube",
		guild,
		media=media,
		convert_embeds=True,
		convert_components=True,
	)
	channel.send.assert_called_once()
	kwargs = channel.send.call_args[1]
	assert len(kwargs["embeds"]) == 1
	assert kwargs["embeds"][0].title == "Epic Video"


@pytest.mark.asyncio
async def test_dispatch_alert_fallback(alerts_cog, mock_bot):
	guild = MagicMock(spec=discord.Guild)
	guild.id = 123
	guild.name = "My Server"
	guild.preferred_locale = "en"
	guild.members = []
	guild.channels = []
	guild.roles = []

	channel = MagicMock(spec=discord.TextChannel)
	channel.id = 999
	channel.name = "general"
	channel.guild = guild
	channel.send = AsyncMock()
	guild.get_channel = MagicMock(return_value=channel)
	mock_bot.get_guild = MagicMock(return_value=guild)

	# Simulate localization retrieval throwing an exception
	mock_bot.custom_response.get_message = AsyncMock(side_effect=RuntimeError("Localization error"))

	media = Media.create(
		url="https://twitch.tv/streamer",
		title="Live Stream",
		author_name="Streamer",
		author_url="https://twitch.tv/streamer",
		media_id="stream_111",
		platform="twitch",
	)

	alert_row = alert(id=3, guild_id=123, target_channel_id=999)

	sent = await alerts_cog.dispatch_alert(alert_row, media)
	assert sent is True
	channel.send.assert_called_once()
	sent_content = channel.send.call_args[1]["content"]
	assert "**Streamer** posted an update!" in sent_content
	assert "https://twitch.tv/streamer" in sent_content


@pytest.mark.asyncio
async def test_check_account_records_offline_baseline_for_live_only(alerts_cog, mock_bot, monkeypatch):
	provider = MagicMock(live_only=True)
	provider.fetch_latest = AsyncMock(return_value=None)
	monkeypatch.setattr("cogs.alerts.get_provider", lambda _platform: provider)
	mock_bot.api.alerts.set_baseline = AsyncMock()

	await alerts_cog.check_account(MagicMock(), "twitch", "streamer", "123")

	mock_bot.api.alerts.set_baseline.assert_awaited_once_with("twitch", "streamer", "123", OFFLINE_BASELINE)


@pytest.mark.asyncio
async def test_check_account_skips_baseline_when_upload_feed_is_empty(alerts_cog, mock_bot, monkeypatch):
	provider = MagicMock(live_only=False)
	provider.fetch_latest = AsyncMock(return_value=None)
	monkeypatch.setattr("cogs.alerts.get_provider", lambda _platform: provider)
	mock_bot.api.alerts.set_baseline = AsyncMock()

	await alerts_cog.check_account(MagicMock(), "youtube", "@creator", "UC1")

	mock_bot.api.alerts.set_baseline.assert_not_called()


@pytest.mark.asyncio
async def test_check_account_announces_stream_after_offline_baseline(alerts_cog, mock_bot, monkeypatch):
	media = Media.create(
		url="https://twitch.tv/streamer",
		title="Live!",
		author_name="Streamer",
		author_url="https://twitch.tv/streamer",
		media_id="stream_1",
		platform="twitch",
	)
	provider = MagicMock(live_only=True)
	provider.fetch_latest = AsyncMock(return_value=media)
	monkeypatch.setattr("cogs.alerts.get_provider", lambda _platform: provider)
	mock_bot.api.alerts.subscribers = AsyncMock(return_value=[alert(id=1, last_media_id=OFFLINE_BASELINE)])
	mock_bot.api.alerts.set_last_media = AsyncMock()
	alerts_cog.dispatch_alert = AsyncMock(return_value=True)

	await alerts_cog.check_account(MagicMock(), "twitch", "streamer", "123")

	alerts_cog.dispatch_alert.assert_awaited_once()
	mock_bot.api.alerts.set_last_media.assert_awaited_once_with(1, "stream_1")
