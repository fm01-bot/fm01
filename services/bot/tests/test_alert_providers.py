from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from helpers.alert_providers import (
	AccountNotFoundError,
	AlertSourceError,
	FeedUnavailableError,
	ProviderNotConfiguredError,
	TikTokProvider,
	TwitchProvider,
	YouTubeProvider,
	get_provider,
)

YOUTUBE_SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="http://www.youtube.com/feeds/videos.xml?channel_id=UC1234567890abcdefghijk"/>
  <id>yt:channel:UC1234567890abcdefghijk</id>
  <yt:channelId>UC1234567890abcdefghijk</yt:channelId>
  <title>Cool Channel</title>
  <author>
    <name>Cool Channel</name>
    <uri>https://www.youtube.com/channel/UC1234567890abcdefghijk</uri>
  </author>
  <published>2026-10-01T00:00:00+00:00</published>
  <entry>
    <id>yt:video:dQw4w9WgXcQ</id>
    <yt:videoId>dQw4w9WgXcQ</yt:videoId>
    <yt:channelId>UC1234567890abcdefghijk</yt:channelId>
    <title>Never Gonna Give You Up</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=dQw4w9WgXcQ"/>
    <author>
      <name>Cool Channel</name>
      <uri>https://www.youtube.com/channel/UC1234567890abcdefghijk</uri>
    </author>
    <published>2026-11-01T14:00:00+00:00</published>
    <updated>2026-11-01T14:05:00+00:00</updated>
    <media:group>
      <media:title>Never Gonna Give You Up</media:title>
      <media:description>Music video description</media:description>
      <media:thumbnail url="https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg" width="480" height="360"/>
    </media:group>
  </entry>
</feed>
"""

RSS_SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Popular Creator</title>
    <link>https://www.tiktok.com/@creator</link>
    <description>TikTok posts by creator</description>
    <item>
      <title>Funny Dance Video</title>
      <link>https://www.tiktok.com/@creator/video/987654321</link>
      <guid>https://www.tiktok.com/@creator/video/987654321</guid>
      <pubDate>2026-11-01T12:00:00+00:00</pubDate>
      <description>Check this out #fyp</description>
    </item>
  </channel>
</rss>
"""


@pytest.mark.asyncio
async def test_youtube_provider_fetch_latest():
	provider = YouTubeProvider()
	session = MagicMock()
	resp = MagicMock()
	resp.status = 200
	resp.text = AsyncMock(return_value=YOUTUBE_SAMPLE_FEED)

	# Mock async context manager for session.get
	session.get.return_value.__aenter__ = AsyncMock(return_value=resp)
	session.get.return_value.__aexit__ = AsyncMock(return_value=None)

	media = await provider.fetch_latest(session, "UC1234567890abcdefghijk", "Cool Channel")
	assert media is not None
	assert media.id == "dQw4w9WgXcQ"
	assert media.title == "Never Gonna Give You Up"
	assert media.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
	assert media.author.name == "Cool Channel"
	assert media.author.url == "https://www.youtube.com/channel/UC1234567890abcdefghijk"
	assert media.thumbnail == "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
	assert media.description == "Music video description"
	assert media.platform == "youtube"


@pytest.mark.asyncio
async def test_youtube_provider_resolve_channel_handle():
	provider = YouTubeProvider()
	session = MagicMock()
	resp = MagicMock()
	resp.status = 200
	html_content = """
	<html>
	  <head>
	    <meta property="og:title" content="Rick Astley Official">
	    <meta itemprop="identifier" content="UCuAXFkgsw1L7xaCfnd5JJOw">
	  </head>
	</html>
	"""
	resp.text = AsyncMock(return_value=html_content)
	session.get.return_value.__aenter__ = AsyncMock(return_value=resp)
	session.get.return_value.__aexit__ = AsyncMock(return_value=None)

	cid, title = await provider.resolve_channel(session, "@RickAstleyYT")
	assert cid == "UCuAXFkgsw1L7xaCfnd5JJOw"
	assert title == "Rick Astley Official"
	assert session.get.call_args.kwargs["headers"]["Cookie"] == "SOCS=CAI"


@pytest.mark.asyncio
async def test_twitch_provider_fetch_live_stream(monkeypatch: pytest.MonkeyPatch):
	provider = TwitchProvider()
	provider._access_token = "mock_token"
	provider._token_expires_at = datetime.datetime.now(datetime.UTC).timestamp() + 3600

	monkeypatch.setenv("TWITCH_CLIENT_ID", "mock_client_id")
	monkeypatch.setenv("TWITCH_CLIENT_SECRET", "mock_client_secret")

	session = MagicMock()
	resp = MagicMock()
	resp.status = 200
	resp.json = AsyncMock(
		return_value={
			"data": [
				{
					"id": "41234567890",
					"user_id": "123456",
					"user_login": "ninja",
					"user_name": "Ninja",
					"game_name": "Fortnite",
					"title": "Chasing Victory Royales!",
					"thumbnail_url": "https://static-cdn.jtvnw.net/previews-ttv/live_user_ninja-{width}x{height}.jpg",
					"started_at": "2026-11-01T13:30:00Z",
				}
			]
		}
	)

	session.get.return_value.__aenter__ = AsyncMock(return_value=resp)
	session.get.return_value.__aexit__ = AsyncMock(return_value=None)

	media = await provider.fetch_latest(session, "ninja")
	assert media is not None
	assert media.id == "stream_41234567890"
	assert "Ninja" in media.author.name
	assert "Chasing Victory Royales!" in media.title
	assert "[Fortnite]" in media.title
	assert media.url == "https://twitch.tv/ninja"
	assert media.platform == "twitch"
	assert "1280x720" in media.thumbnail


@pytest.mark.asyncio
async def test_twitch_provider_stream_offline(monkeypatch: pytest.MonkeyPatch):
	provider = TwitchProvider()
	provider._access_token = "mock_token"
	provider._token_expires_at = datetime.datetime.now(datetime.UTC).timestamp() + 3600

	monkeypatch.setenv("TWITCH_CLIENT_ID", "mock_client_id")
	monkeypatch.setenv("TWITCH_CLIENT_SECRET", "mock_client_secret")

	session = MagicMock()
	resp = MagicMock()
	resp.status = 200
	resp.json = AsyncMock(return_value={"data": []})

	session.get.return_value.__aenter__ = AsyncMock(return_value=resp)
	session.get.return_value.__aexit__ = AsyncMock(return_value=None)

	media = await provider.fetch_latest(session, "ninja")
	assert media is None


@pytest.mark.asyncio
async def test_generic_rss_provider_tiktok():
	tiktok = TikTokProvider()
	assert tiktok.platform == "tiktok"

	session = MagicMock()
	resp = MagicMock()
	resp.status = 200
	resp.text = AsyncMock(return_value=RSS_SAMPLE_FEED)

	session.get.return_value.__aenter__ = AsyncMock(return_value=resp)
	session.get.return_value.__aexit__ = AsyncMock(return_value=None)

	media = await tiktok.fetch_latest(session, "creator")
	assert media is not None
	assert media.id == "https://www.tiktok.com/@creator/video/987654321"
	assert media.title == "Funny Dance Video"
	assert media.author.name == "Popular Creator"
	assert media.author.url == "https://www.{self.platform}.com/@creator".replace("{self.platform}", "tiktok")
	assert media.platform == "tiktok"


RSSHUB_TIKTOK_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>dominik (@unphunny) | TikTok</title>
    <link>https://www.tiktok.com/@unphunny</link>
    <image><url>https://p16.tiktokcdn.com/avatar.jpeg?a=1&amp;b=2</url></image>
    <item>
      <title>ok #fyp</title>
      <description><![CDATA[<video controls="" poster="https://p16.tiktokcdn.com/poster.jpeg?x=1&amp;y=2"><source src=""></video>]]></description>
      <link>https://www.tiktok.com/@unphunny/video/1</link>
      <guid isPermaLink="false">https://www.tiktok.com/@unphunny/video/1</guid>
      <pubDate>Sat, 07 Nov 2026 18:29:50 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


@pytest.mark.asyncio
async def test_generic_rss_provider_extracts_thumbnail_from_html_description():
	session = _mock_session(200, RSSHUB_TIKTOK_FEED)

	media = await TikTokProvider().fetch_latest(session, "unphunny")

	assert media is not None
	assert media.thumbnail == "https://p16.tiktokcdn.com/poster.jpeg?x=1&y=2"
	assert media.description == ""
	assert media.author.avatar_url == "https://p16.tiktokcdn.com/avatar.jpeg?a=1&b=2"


@pytest.mark.asyncio
async def test_generic_rss_provider_strips_html_from_description():
	feed = RSSHUB_TIKTOK_FEED.replace(
		'<video controls="" poster="https://p16.tiktokcdn.com/poster.jpeg?x=1&amp;y=2"><source src=""></video>',
		'<p>Line one &amp; more</p><img src="https://example.com/a.jpg"><br>Line two',
	)
	session = _mock_session(200, feed)

	media = await TikTokProvider().fetch_latest(session, "unphunny")

	assert media is not None
	assert media.description == "Line one & more\nLine two"
	assert media.thumbnail == "https://example.com/a.jpg"


def _mock_session(status: int, text: str = "") -> MagicMock:
	session = MagicMock()
	resp = MagicMock()
	resp.status = status
	resp.text = AsyncMock(return_value=text)
	session.get.return_value.__aenter__ = AsyncMock(return_value=resp)
	session.get.return_value.__aexit__ = AsyncMock(return_value=None)
	return session


@pytest.mark.asyncio
async def test_generic_rss_provider_fetch_latest_logs_blocked_feed(caplog: pytest.LogCaptureFixture):
	session = _mock_session(403, "Due to cost considerations ...")

	with caplog.at_level("WARNING", logger="helpers.alert_providers"):
		media = await TikTokProvider().fetch_latest(session, "creator")

	assert media is None
	assert "HTTP 403" in caplog.text


@pytest.mark.asyncio
async def test_generic_rss_provider_resolve_channel_rejects_blocked_feed():
	session = _mock_session(403)

	with pytest.raises(FeedUnavailableError) as exc_info:
		await TikTokProvider().resolve_channel(session, "https://www.tiktok.com/@creator")

	assert exc_info.value.reason == "HTTP 403"
	assert exc_info.value.feed_url.endswith("/tiktok/user/creator")


@pytest.mark.asyncio
async def test_generic_rss_provider_resolve_channel_accepts_reachable_feed():
	session = _mock_session(200, RSS_SAMPLE_FEED)

	assert await TikTokProvider().resolve_channel(session, "@creator") == ("creator", "creator")


@pytest.mark.asyncio
async def test_generic_rss_provider_parses_rfc822_pub_date():
	feed = RSS_SAMPLE_FEED.replace("2026-11-01T12:00:00+00:00", "Sun, 01 Nov 2026 12:00:00 GMT")
	session = _mock_session(200, feed)

	media = await TikTokProvider().fetch_latest(session, "creator")

	assert media is not None
	assert media._published_at == datetime.datetime(2026, 11, 1, 12, tzinfo=datetime.UTC)


def test_get_provider_registry():
	assert isinstance(get_provider("youtube"), YouTubeProvider)
	assert isinstance(get_provider("YOUTUBE"), YouTubeProvider)
	assert isinstance(get_provider("twitch"), TwitchProvider)
	assert isinstance(get_provider("tiktok"), TikTokProvider)
	assert get_provider("instagram") is None
	assert get_provider("unknown_platform") is None


@pytest.mark.asyncio
async def test_twitch_resolve_without_credentials_raises(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.delenv("TWITCH_CLIENT_ID", raising=False)
	monkeypatch.delenv("TWITCH_CLIENT_SECRET", raising=False)
	session = MagicMock()

	with pytest.raises(ProviderNotConfiguredError):
		await TwitchProvider().resolve_channel(session, "playhubstreams")
	session.get.assert_not_called()


def _twitch_with_token(monkeypatch: pytest.MonkeyPatch) -> TwitchProvider:
	monkeypatch.setenv("TWITCH_CLIENT_ID", "id")
	monkeypatch.setenv("TWITCH_CLIENT_SECRET", "secret")
	provider = TwitchProvider()
	provider._access_token = "token"
	provider._token_expires_at = datetime.datetime.now(datetime.UTC).timestamp() + 3600
	return provider


@pytest.mark.asyncio
async def test_twitch_resolve_unknown_user_raises(monkeypatch: pytest.MonkeyPatch):
	provider = _twitch_with_token(monkeypatch)
	session = _mock_session(200)
	session.get.return_value.__aenter__.return_value.json = AsyncMock(return_value={"data": []})

	with pytest.raises(AccountNotFoundError):
		await provider.resolve_channel(session, "https://twitch.tv/NoSuchUser")


@pytest.mark.asyncio
async def test_twitch_resolve_returns_user_id(monkeypatch: pytest.MonkeyPatch):
	provider = _twitch_with_token(monkeypatch)
	session = _mock_session(200)
	session.get.return_value.__aenter__.return_value.json = AsyncMock(
		return_value={"data": [{"id": "123", "display_name": "PlayHubStreams"}]}
	)

	assert await provider.resolve_channel(session, "@PlayHubStreams") == ("123", "PlayHubStreams")
	assert session.get.call_args.args[0].endswith("users?login=playhubstreams")


@pytest.mark.asyncio
async def test_twitch_fetch_api_error_raises_and_drops_token_on_401(monkeypatch: pytest.MonkeyPatch):
	provider = _twitch_with_token(monkeypatch)
	session = _mock_session(401)

	with pytest.raises(AlertSourceError, match="HTTP 401"):
		await provider.fetch_latest(session, "123")
	assert provider._access_token is None


def _response(status: int = 200, text: str = "", json: object = None) -> MagicMock:
	resp = MagicMock()
	resp.status = status
	resp.text = AsyncMock(return_value=text)
	resp.json = AsyncMock(return_value=json)
	ctx = MagicMock()
	ctx.__aenter__ = AsyncMock(return_value=resp)
	ctx.__aexit__ = AsyncMock(return_value=None)
	return ctx


@pytest.mark.asyncio
async def test_youtube_fetch_latest_reads_and_caches_channel_avatar():
	provider = YouTubeProvider()
	page = '<meta property="og:image" content="https://yt3.googleusercontent.com/avatar=s900">'
	session = MagicMock()
	session.get.side_effect = [
		_response(text=YOUTUBE_SAMPLE_FEED),
		_response(text=page),
		_response(text=YOUTUBE_SAMPLE_FEED),
	]

	first = await provider.fetch_latest(session, "UC1234567890abcdefghijk")
	second = await provider.fetch_latest(session, "UC1234567890abcdefghijk")

	assert first is not None and second is not None
	assert first.author.avatar_url == second.author.avatar_url == "https://yt3.googleusercontent.com/avatar=s900"
	assert session.get.call_count == 3  # channel page fetched once
	assert session.get.call_args_list[1].args[0] == "https://www.youtube.com/channel/UC1234567890abcdefghijk"


@pytest.mark.asyncio
async def test_youtube_fetch_latest_survives_avatar_failure():
	session = MagicMock()
	session.get.side_effect = [_response(text=YOUTUBE_SAMPLE_FEED), _response(status=429)]

	media = await YouTubeProvider().fetch_latest(session, "UC1234567890abcdefghijk")

	assert media is not None
	assert media.author.avatar_url == ""


@pytest.mark.asyncio
async def test_twitch_fetch_latest_reads_profile_image(monkeypatch: pytest.MonkeyPatch):
	provider = _twitch_with_token(monkeypatch)
	stream = {"id": "1", "user_id": "123", "user_login": "streamer", "user_name": "Streamer", "title": "Live"}
	session = MagicMock()
	session.get.side_effect = [
		_response(json={"data": [stream]}),
		_response(json={"data": [{"id": "123", "profile_image_url": "https://static-cdn.jtvnw.net/p.png"}]}),
	]

	media = await provider.fetch_latest(session, "123")

	assert media is not None
	assert media.author.avatar_url == "https://static-cdn.jtvnw.net/p.png"
	assert session.get.call_args_list[1].args[0].endswith("users?id=123")


@pytest.mark.asyncio
@pytest.mark.parametrize("account", ["..", "a/b", "../../twitter/user/x", "a?b=c", "a%2fb"])
async def test_generic_rss_provider_refuses_account_names_that_change_the_route(account: str):
	session = _mock_session(200, RSS_SAMPLE_FEED)

	with pytest.raises(AccountNotFoundError):
		await TikTokProvider().resolve_channel(session, account)
	session.get.assert_not_called()


@pytest.mark.asyncio
async def test_twitch_resolve_refuses_malformed_logins(monkeypatch: pytest.MonkeyPatch):
	provider = _twitch_with_token(monkeypatch)
	session = _mock_session(200)

	with pytest.raises(AccountNotFoundError):
		await provider.resolve_channel(session, "someone&login=other")
	session.get.assert_not_called()
