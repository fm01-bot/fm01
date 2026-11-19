from __future__ import annotations

import abc
import datetime
import email.utils
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import aiohttp
from args.media import Media

if TYPE_CHECKING:
	from core.bot import Bot

logger = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = ("youtube", "twitch", "tiktok")

# XML Namespaces for YouTube Atom feeds
YT_NAMESPACES = {
	"atom": "http://www.w3.org/2005/Atom",
	"yt": "http://www.youtube.com/xml/schemas/2015",
	"media": "http://search.yahoo.com/mrss/",
}


TWITCH_LOGIN = re.compile(r"[a-z0-9_]{1,25}")
"""A Twitch login name."""
RSS_ACCOUNT = re.compile(r"(?!\.+$)[A-Za-z0-9._-]{1,64}")
"""An account name an RSSHub route accepts as its last path segment: no slashes, queries or dot segments."""


class AlertSourceError(Exception):
	"""Raised when a platform cannot be queried for an account."""

	def __init__(self, reason: str) -> None:
		super().__init__(reason)
		self.reason = reason


class FeedUnavailableError(AlertSourceError):
	"""Raised when an RSS feed cannot be downloaded or parsed."""

	def __init__(self, feed_url: str, reason: str) -> None:
		super().__init__(reason)
		self.feed_url = feed_url

	def __str__(self) -> str:
		return f"{self.feed_url}: {self.reason}"


class ProviderNotConfiguredError(AlertSourceError):
	"""Raised when a platform needs credentials that the bot was not given."""


class AccountNotFoundError(AlertSourceError):
	"""Raised when the platform reports that the account does not exist."""


class _FeedHTMLParser(HTMLParser):
	"""Splits an RSS item's HTML description into visible text and its first image."""

	def __init__(self) -> None:
		super().__init__()
		self.parts: list[str] = []
		self.image: str | None = None

	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		if self.image is None:
			attr = {"img": "src", "video": "poster"}.get(tag)
			value = dict(attrs).get(attr) if attr else None
			if value:
				self.image = value
		if tag in ("br", "p", "div"):
			self.parts.append("\n")

	def handle_data(self, data: str) -> None:
		self.parts.append(data)


def _parse_feed_html(raw: str) -> tuple[str | None, str | None]:
	"""Returns ``(text, image_url)`` from an RSS description that may contain HTML (RSSHub's always does)."""
	parser = _FeedHTMLParser()
	parser.feed(raw)
	parser.close()
	text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
	text = re.sub(r"\s*\n\s*", "\n", text).strip()
	return text or None, parser.image


class _AvatarCache:
	"""Remembers creator avatar URLs so polling does not refetch them on every check."""

	TTL_SECONDS = 24 * 60 * 60

	def __init__(self) -> None:
		self._entries: dict[str, tuple[float, str]] = {}

	def get(self, key: str) -> str | None:
		entry = self._entries.get(key)
		if entry is None or time.monotonic() - entry[0] > self.TTL_SECONDS:
			return None
		return entry[1]

	def set(self, key: str, url: str) -> None:
		self._entries[key] = (time.monotonic(), url)


def _parse_rss_date(raw: str) -> datetime.datetime | None:
	"""Parses an RSS ``pubDate`` (RFC 822, as RSSHub emits) or ISO 8601 timestamp."""
	try:
		return email.utils.parsedate_to_datetime(raw)
	except (TypeError, ValueError):
		pass
	try:
		return datetime.datetime.fromisoformat(raw)
	except ValueError:
		return None


class AlertProvider(abc.ABC):
	"""Abstract base class for all social media alert providers."""

	platform: str
	display_name: str
	# Live-only platforms report "nothing" while the account is offline, which is a valid baseline.
	live_only: bool = False

	@abc.abstractmethod
	async def resolve_channel(
		self,
		session: aiohttp.ClientSession,
		channel_input: str,
		bot: Bot | None = None,
	) -> tuple[str, str]:
		"""Resolves a user-provided handle or URL to an internal account ID and display name.

		Args:
			session: Shared aiohttp ClientSession.
			channel_input: User-entered channel name, handle, or URL.
			bot: Bot instance if needed for credentials.

		Returns:
			tuple[str, str]: (account_id, account_name)

		Raises:
			AlertSourceError: The account cannot be verified, so alerts for it would never fire.

		"""
		...

	@abc.abstractmethod
	async def fetch_latest(
		self,
		session: aiohttp.ClientSession,
		account_id: str,
		account_name: str | None = None,
		bot: Bot | None = None,
	) -> Media | None:
		"""Fetches the latest media upload or live stream for the account.

		Args:
			session: Shared aiohttp ClientSession.
			account_id: The resolved account ID.
			account_name: The display name if known.
			bot: Bot instance if needed for credentials.

		Returns:
			Media | None: The latest media object or None if no media found.

		"""
		...


YT_PAGE_HEADERS = {
	"User-Agent": "Mozilla/5.0 (compatible; fm01-bot/1.0; +https://github.com)",
	# Skips the EU cookie-consent interstitial, which contains no channel metadata.
	"Cookie": "SOCS=CAI",
}


class YouTubeProvider(AlertProvider):
	"""YouTube alert provider using Atom/RSS feeds and handle resolution."""

	platform = "youtube"
	display_name = "YouTube"

	def __init__(self) -> None:
		self._avatars = _AvatarCache()

	async def _get_avatar(self, session: aiohttp.ClientSession, channel_url: str) -> str | None:
		"""Reads the channel avatar from the channel page; ``None`` if it cannot be loaded."""
		if cached := self._avatars.get(channel_url):
			return cached
		try:
			async with session.get(
				channel_url, headers=YT_PAGE_HEADERS, timeout=aiohttp.ClientTimeout(total=8)
			) as resp:
				if resp.status != 200:
					logger.debug(f"YouTube channel page returned {resp.status} for {channel_url}")
					return None
				html = await resp.text()
		except (aiohttp.ClientError, TimeoutError, OSError) as e:
			logger.debug(f"Failed to load YouTube channel page {channel_url}: {e}")
			return None
		match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
		if not match:
			return None
		self._avatars.set(channel_url, match.group(1))
		return match.group(1)

	async def resolve_channel(
		self,
		session: aiohttp.ClientSession,
		channel_input: str,
		bot: Bot | None = None,
	) -> tuple[str, str]:
		cleaned = channel_input.strip()
		# Extract from YouTube URLs if provided
		url_match = re.search(r"youtube\.com/(?:channel/|@|c/)?([^/?#]+)", cleaned)
		candidate = url_match.group(1) if url_match else cleaned
		candidate = candidate.lstrip("@")

		# If already a standard YouTube channel ID (starts with UC and 24 chars long)
		if candidate.startswith("UC") and len(candidate) == 24:
			# Attempt to fetch feed to get real channel name
			feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={candidate}"
			try:
				async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
					if resp.status == 200:
						xml_text = await resp.text()
						root = ET.fromstring(xml_text)
						title_el = root.find("atom:title", YT_NAMESPACES)
						name = title_el.text.strip() if title_el is not None and title_el.text else candidate
						return candidate, name
			except (aiohttp.ClientError, ET.ParseError, TimeoutError, OSError) as e:
				logger.debug(f"Failed to fetch YouTube feed for {candidate}: {e}")
			return candidate, candidate

		# Otherwise resolve handle or username
		handle_url = f"https://www.youtube.com/@{candidate}"
		try:
			async with session.get(handle_url, headers=YT_PAGE_HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as resp:
				if resp.status == 200:
					html = await resp.text()
					# Search for channelId in page metadata
					cid_match = re.search(r'"externalId":"(UC[a-zA-Z0-9_-]{22})"', html)
					if not cid_match:
						cid_match = re.search(r'itemprop="identifier"\s+content="(UC[a-zA-Z0-9_-]{22})"', html)
					if not cid_match:
						cid_match = re.search(r"channel/(UC[a-zA-Z0-9_-]{22})", html)
					if cid_match:
						cid = cid_match.group(1)
						# Extract channel title
						title_match = re.search(r'<meta property="og:title" content="([^"]+)">', html)
						title = title_match.group(1) if title_match else candidate
						return cid, title
		except (aiohttp.ClientError, TimeoutError, OSError) as e:
			logger.debug(f"Failed to resolve YouTube handle @{candidate}: {e}")

		# Fallback to candidate as account ID
		return candidate, candidate

	async def fetch_latest(
		self,
		session: aiohttp.ClientSession,
		account_id: str,
		account_name: str | None = None,
		bot: Bot | None = None,
	) -> Media | None:
		if account_id.startswith("UC") and len(account_id) == 24:
			feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={account_id}"
		else:
			feed_url = f"https://www.youtube.com/feeds/videos.xml?user={account_id}"

		try:
			async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
				if resp.status != 200:
					logger.debug(f"YouTube feed returned status {resp.status} for {account_id}")
					return None
				content = await resp.text()
				root = ET.fromstring(content)
		except (aiohttp.ClientError, ET.ParseError, TimeoutError, OSError) as e:
			logger.debug(f"Error fetching YouTube feed for {account_id}: {e}")
			return None

		entry = root.find("atom:entry", YT_NAMESPACES)
		if entry is None:
			return None

		video_id_el = entry.find("yt:videoId", YT_NAMESPACES)
		title_el = entry.find("atom:title", YT_NAMESPACES)
		link_el = entry.find("atom:link[@rel='alternate']", YT_NAMESPACES)
		published_el = entry.find("atom:published", YT_NAMESPACES)

		if video_id_el is None or video_id_el.text is None:
			return None

		video_id = video_id_el.text.strip()
		title = title_el.text.strip() if title_el is not None and title_el.text else "New Video"
		href = link_el.attrib.get("href") if link_el is not None else None
		video_url: str = href if href else f"https://www.youtube.com/watch?v={video_id}"

		# Channel details
		author_el = root.find("atom:author", YT_NAMESPACES)
		author_name_el = author_el.find("atom:name", YT_NAMESPACES) if author_el is not None else None
		author_uri_el = author_el.find("atom:uri", YT_NAMESPACES) if author_el is not None else None

		channel_name = (
			author_name_el.text.strip()
			if author_name_el is not None and author_name_el.text
			else (account_name or account_id)
		)
		channel_url = (
			author_uri_el.text.strip()
			if author_uri_el is not None and author_uri_el.text
			else f"https://www.youtube.com/channel/{account_id}"
		)

		# Media description & thumbnail
		media_group = entry.find("media:group", YT_NAMESPACES)
		description: str | None = None
		thumbnail: str | None = None
		if media_group is not None:
			desc_el = media_group.find("media:description", YT_NAMESPACES)
			if desc_el is not None and desc_el.text:
				description = desc_el.text.strip()
			thumb_el = media_group.find("media:thumbnail", YT_NAMESPACES)
			if thumb_el is not None and "url" in thumb_el.attrib:
				thumbnail = thumb_el.attrib["url"]

		if not thumbnail:
			thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

		published_at: datetime.datetime | None = None
		if published_el is not None and published_el.text:
			try:
				published_at = datetime.datetime.fromisoformat(published_el.text)
			except ValueError:
				published_at = None

		return Media.create(
			url=video_url,
			title=title,
			author_name=channel_name,
			author_url=channel_url,
			author_id=account_id,
			author_avatar_url=await self._get_avatar(session, channel_url),
			media_id=video_id,
			platform="youtube",
			thumbnail=thumbnail,
			description=description,
			published_at=published_at,
		)


class TwitchProvider(AlertProvider):
	"""Twitch alert provider using Twitch Helix API for live stream alerts."""

	platform = "twitch"
	display_name = "Twitch"

	def __init__(self) -> None:
		self._access_token: str | None = None
		self._avatars = _AvatarCache()
		self._token_expires_at: float = 0.0

	live_only = True

	@staticmethod
	def _get_credentials() -> tuple[str, str]:
		client_id = os.getenv("TWITCH_CLIENT_ID")
		client_secret = os.getenv("TWITCH_CLIENT_SECRET")
		if not client_id or not client_secret:
			raise ProviderNotConfiguredError("TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET are not set")
		return client_id, client_secret

	async def _get_app_token(self, session: aiohttp.ClientSession) -> str:
		client_id, client_secret = self._get_credentials()

		now = datetime.datetime.now(datetime.UTC).timestamp()
		if self._access_token and now < (self._token_expires_at - 60):
			return self._access_token

		token_url = "https://id.twitch.tv/oauth2/token"
		params = {
			"client_id": client_id,
			"client_secret": client_secret,
			"grant_type": "client_credentials",
		}
		try:
			async with session.post(token_url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
				if resp.status != 200:
					raise AlertSourceError(f"Twitch OAuth token request failed: HTTP {resp.status}")
				data = await resp.json()
		except (aiohttp.ClientError, TimeoutError, OSError) as e:
			raise AlertSourceError(f"Twitch OAuth token request failed: {type(e).__name__}") from e

		token = data.get("access_token")
		if not token:
			raise AlertSourceError("Twitch OAuth token response had no access_token")
		self._access_token = token
		self._token_expires_at = now + float(data.get("expires_in", 3600))
		return token

	async def _helix_get(self, session: aiohttp.ClientSession, path: str) -> list[dict[str, Any]]:
		"""Calls a Helix endpoint and returns its ``data`` list."""
		client_id, _ = self._get_credentials()
		token = await self._get_app_token(session)
		headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
		try:
			async with session.get(
				f"https://api.twitch.tv/helix/{path}", headers=headers, timeout=aiohttp.ClientTimeout(total=8)
			) as resp:
				if resp.status == 401:
					# Token revoked or expired early: fetch a new one next time.
					self._access_token = None
				if resp.status != 200:
					raise AlertSourceError(f"Twitch API returned HTTP {resp.status}")
				res = await resp.json()
		except (aiohttp.ClientError, TimeoutError, OSError) as e:
			raise AlertSourceError(f"Twitch API request failed: {type(e).__name__}") from e
		return res.get("data", [])

	async def _get_avatar(self, session: aiohttp.ClientSession, user_id: str) -> str | None:
		"""Reads the user's profile image; ``None`` if it cannot be loaded."""
		if cached := self._avatars.get(user_id):
			return cached
		try:
			users = await self._helix_get(session, f"users?id={user_id}")
		except AlertSourceError as e:
			logger.debug(f"Failed to load Twitch avatar for {user_id}: {e}")
			return None
		url = users[0].get("profile_image_url") if users else None
		if url:
			self._avatars.set(user_id, url)
		return url or None

	async def resolve_channel(
		self,
		session: aiohttp.ClientSession,
		channel_input: str,
		bot: Bot | None = None,
	) -> tuple[str, str]:
		cleaned = channel_input.strip()
		url_match = re.search(r"twitch\.tv/([^/?#]+)", cleaned)
		login = (url_match.group(1) if url_match else cleaned).lstrip("@").lower()
		if not TWITCH_LOGIN.fullmatch(login):
			raise AccountNotFoundError(f"no Twitch user named {login}")

		users = await self._helix_get(session, f"users?login={login}")
		if not users:
			raise AccountNotFoundError(f"no Twitch user named {login}")
		return users[0]["id"], users[0]["display_name"]

	async def fetch_latest(
		self,
		session: aiohttp.ClientSession,
		account_id: str,
		account_name: str | None = None,
		bot: Bot | None = None,
	) -> Media | None:
		"""Returns the current stream, or ``None`` while offline.

		Raises:
			AlertSourceError: Twitch could not be queried, so the offline state is unknown.

		"""
		# account_id could be numeric user_id or login name
		param_key = "user_id" if account_id.isdigit() else "user_login"
		data = await self._helix_get(session, f"streams?{param_key}={quote(account_id.lower(), safe='')}")

		if not data:
			return None

		stream = data[0]
		stream_id = str(stream.get("id", ""))
		user_login = stream.get("user_login", account_id)
		display_name = stream.get("user_name", account_name or user_login)
		title = stream.get("title", f"{display_name} is live!")
		game_name = stream.get("game_name", "")
		if game_name and game_name not in title:
			title = f"{title} [{game_name}]"

		raw_thumb = stream.get("thumbnail_url", "")
		thumbnail = raw_thumb.replace("{width}", "1280").replace("{height}", "720") if raw_thumb else None

		started_at_raw = stream.get("started_at")
		published_at: datetime.datetime | None = None
		if started_at_raw:
			try:
				published_at = datetime.datetime.fromisoformat(started_at_raw)
			except ValueError:
				published_at = None

		stream_url = f"https://twitch.tv/{user_login}"
		user_id = str(stream.get("user_id", account_id))
		return Media.create(
			url=stream_url,
			title=title,
			author_name=display_name,
			author_url=stream_url,
			author_id=user_id,
			author_avatar_url=await self._get_avatar(session, user_id) if user_id.isdigit() else None,
			media_id=f"stream_{stream_id}",
			platform="twitch",
			thumbnail=thumbnail,
			description=game_name,
			published_at=published_at,
		)


class GenericRSSProvider(AlertProvider):
	"""Pluggable RSSHub-based alert provider for platforms like TikTok."""

	def __init__(self, platform: str, display_name: str, path_prefix: str) -> None:
		self.platform = platform
		self.display_name = display_name
		self.path_prefix = path_prefix

	@staticmethod
	def _get_base_url() -> str:
		return (os.getenv("RSSHUB_URL") or "https://rsshub.app").rstrip("/")

	async def _fetch_feed(self, session: aiohttp.ClientSession, account_id: str) -> ET.Element:
		"""Downloads and parses the account's RSS feed.

		Raises:
			FeedUnavailableError: The feed could not be downloaded or parsed.

		"""
		if not RSS_ACCOUNT.fullmatch(account_id):
			raise FeedUnavailableError(f"{self._get_base_url()}/{self.path_prefix}/", "invalid account name")
		feed_url = f"{self._get_base_url()}/{self.path_prefix}/{quote(account_id, safe='')}"
		try:
			async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
				if resp.status != 200:
					raise FeedUnavailableError(feed_url, f"HTTP {resp.status}")
				xml_text = await resp.text()
			return ET.fromstring(xml_text)
		except ET.ParseError as e:
			raise FeedUnavailableError(feed_url, f"invalid XML ({e})") from e
		except (aiohttp.ClientError, TimeoutError, OSError) as e:
			raise FeedUnavailableError(feed_url, type(e).__name__) from e

	async def resolve_channel(
		self,
		session: aiohttp.ClientSession,
		channel_input: str,
		bot: Bot | None = None,
	) -> tuple[str, str]:
		cleaned = channel_input.strip()
		handle_match = re.search(r"(?:com|app)/(?:@|p/)?([^/?#]+)", cleaned)
		candidate = handle_match.group(1) if handle_match else cleaned
		candidate = candidate.lstrip("@")
		if not RSS_ACCOUNT.fullmatch(candidate):
			raise AccountNotFoundError(f"no {self.display_name} account named {candidate}")
		# Fail on add rather than silently never alerting.
		await self._fetch_feed(session, candidate)
		return candidate, candidate

	async def fetch_latest(
		self,
		session: aiohttp.ClientSession,
		account_id: str,
		account_name: str | None = None,
		bot: Bot | None = None,
	) -> Media | None:
		try:
			root = await self._fetch_feed(session, account_id)
		except FeedUnavailableError as e:
			logger.warning(f"{self.display_name} feed unavailable for {account_id}: {e}")
			return None

		# Handle RSS 2.0 channel/item structure
		channel = root.find("channel")
		if channel is None:
			return None

		items = channel.findall("item")
		if not items:
			return None

		item = items[0]
		title_el = item.find("title")
		link_el = item.find("link")
		guid_el = item.find("guid")
		pub_date_el = item.find("pubDate")
		desc_el = item.find("description")

		media_id = guid_el.text.strip() if guid_el is not None and guid_el.text else ""
		url = link_el.text.strip() if link_el is not None and link_el.text else ""
		if not media_id and url:
			media_id = url
		if not media_id:
			return None

		title = title_el.text.strip() if title_el is not None and title_el.text else f"New {self.display_name} Post"
		author_title_el = channel.find("title")
		author_name = (
			author_title_el.text.strip()
			if author_title_el is not None and author_title_el.text
			else (account_name or account_id)
		)

		published_at: datetime.datetime | None = None
		if pub_date_el is not None and pub_date_el.text:
			published_at = _parse_rss_date(pub_date_el.text)

		desc_text, thumbnail = _parse_feed_html(desc_el.text) if desc_el is not None and desc_el.text else (None, None)
		avatar_url = channel.findtext("image/url")
		author_url = (
			f"https://www.{self.platform}.com/@{account_id}"
			if self.platform == "tiktok"
			else f"https://www.{self.platform}.com/{account_id}"
		)

		return Media.create(
			url=url,
			title=title,
			author_name=author_name,
			author_url=author_url,
			author_id=account_id,
			author_avatar_url=avatar_url.strip() if avatar_url else None,
			media_id=media_id,
			platform=self.platform,
			thumbnail=thumbnail,
			description=desc_text,
			published_at=published_at,
		)


class TikTokProvider(GenericRSSProvider):
	"""TikTok alert provider."""

	def __init__(self) -> None:
		super().__init__(platform="tiktok", display_name="TikTok", path_prefix="tiktok/user")


# Registry instance dictionary
ALERT_PROVIDERS: dict[str, AlertProvider] = {
	"youtube": YouTubeProvider(),
	"twitch": TwitchProvider(),
	"tiktok": TikTokProvider(),
}


def get_provider(platform: str) -> AlertProvider | None:
	"""Fetches the registered alert provider for the platform name."""
	return ALERT_PROVIDERS.get(platform.lower().strip())
