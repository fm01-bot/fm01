"""The utility download command: cobalt responses, error mapping and the upload limit, with cobalt mocked."""

from __future__ import annotations

from typing import Self
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from cogs.utility import Cobalt, CobaltError, FileTooLarge, Media, Utility, error_key, upload_limit
from core.hybrid import HybridCommand


class _Response:
	def __init__(self, data: object = None, chunks: list[bytes] | None = None, length: int | None = None) -> None:
		self.data = data
		self.content_length = length
		self.content = MagicMock()
		self.content.iter_chunked = lambda _size: _iterate(chunks or [])

	async def __aenter__(self) -> Self:
		return self

	async def __aexit__(self, *_: object) -> None:
		pass

	async def json(self, content_type: str | None = None) -> object:
		return self.data

	def raise_for_status(self) -> None:
		pass


async def _iterate(chunks: list[bytes]):
	for chunk in chunks:
		yield chunk


def _cobalt(post: object = None, get: _Response | None = None) -> Cobalt:
	cobalt = Cobalt("http://cobalt:9000", "key")
	session = MagicMock(closed=False)
	session.post = MagicMock(return_value=_Response(post))
	session.get = MagicMock(return_value=get)
	cobalt.session = session
	return cobalt


def test_command_is_custom_hybrid_and_installable_everywhere():
	assert isinstance(Utility.download, HybridCommand)
	assert Utility.download.guild and Utility.download.user
	app = Utility.download.app_command
	assert app is not None
	assert app.allowed_installs is not None and app.allowed_installs.guild and app.allowed_installs.user


def test_api_key_header():
	assert Cobalt("http://cobalt:9000", "abc").headers["Authorization"] == "Api-Key abc"
	assert "Authorization" not in Cobalt("http://cobalt:9000").headers


@pytest.mark.parametrize(("audio", "mode"), [(False, "auto"), (True, "audio")])
async def test_resolve_sends_download_mode(audio, mode):
	cobalt = _cobalt({"status": "tunnel", "url": "http://cobalt:9000/tunnel?id=1", "filename": "a.mp4"})

	assert await cobalt.resolve("https://example.com/v", audio) == [Media("http://cobalt:9000/tunnel?id=1", "a.mp4")]
	session = cobalt.session
	assert isinstance(session, MagicMock)
	payload = session.post.call_args.kwargs["json"]
	assert payload["downloadMode"] == mode and payload["alwaysProxy"] is True


async def test_resolve_picker_names_items_and_caps_count():
	items = [{"type": "photo", "url": f"u{i}"} for i in range(12)]
	cobalt = _cobalt({"status": "picker", "picker": items})

	media = await cobalt.resolve("https://example.com/p", False)

	assert len(media) == 10
	assert media[0] == Media("u0", "photo1.jpg")


async def test_resolve_picker_audio_uses_background_track():
	cobalt = _cobalt({"status": "picker", "picker": [], "audio": "a", "audioFilename": "a.mp3"})

	assert await cobalt.resolve("https://example.com/p", True) == [Media("a", "a.mp3")]


async def test_resolve_raises_cobalt_error():
	cobalt = _cobalt({"status": "error", "error": {"code": "error.api.link.invalid"}})

	with pytest.raises(CobaltError) as error:
		await cobalt.resolve("nope", False)
	assert error.value.code == "error.api.link.invalid"


async def test_fetch_stops_past_limit():
	cobalt = _cobalt(get=_Response(chunks=[b"x" * 6, b"x" * 6]))

	with pytest.raises(FileTooLarge):
		await cobalt.fetch(Media("u", "f"), 10)


async def test_fetch_rejects_declared_length_past_limit():
	cobalt = _cobalt(get=_Response(chunks=[b"x"], length=11))

	with pytest.raises(FileTooLarge):
		await cobalt.fetch(Media("u", "f"), 10)


async def test_fetch_rejects_empty_tunnel():
	cobalt = _cobalt(get=_Response(chunks=[]))

	with pytest.raises(CobaltError):
		await cobalt.fetch(Media("u", "f"), 10)


@pytest.mark.parametrize(
	("code", "key"),
	[
		("error.api.link.invalid", "download.errors.unsupported"),
		("error.api.service.unsupported", "download.errors.unsupported"),
		("error.api.content.video.unavailable", "download.errors.content"),
		("error.api.fetch.fail", "download.errors.content"),
		("error.api.rate_exceeded", "download.errors.failed"),
	],
)
def test_error_key(code, key):
	assert error_key(code) == key


def test_upload_limit_prefers_interaction():
	ctx = MagicMock()
	ctx.interaction.filesize_limit = 123
	assert upload_limit(ctx) == 123
	ctx.interaction = None
	ctx.guild.filesize_limit = 456
	assert upload_limit(ctx) == 456
	ctx.guild = None
	assert upload_limit(ctx) == 10 * 1024 * 1024


@pytest.fixture
def ctx() -> MagicMock:
	ctx = MagicMock(interaction=None, guild=None)
	ctx.send = AsyncMock()
	ctx.defer = AsyncMock()
	return ctx


def _cog(cobalt: MagicMock | None) -> Utility:
	cog = Utility(MagicMock())
	cog.cobalt = cobalt
	return cog


async def test_download_uploads_files(ctx):
	cobalt = MagicMock()
	cobalt.resolve = AsyncMock(return_value=[Media("u", "a.mp3")])
	cobalt.fetch = AsyncMock(return_value=b"data")
	cog = _cog(cobalt)

	await cog.download.callback(cog, ctx, "https://example.com/s", True)

	cobalt.resolve.assert_awaited_once_with("https://example.com/s", True)
	ctx.defer.assert_awaited_once()
	key = ctx.send.await_args.args[0]
	files = ctx.send.await_args.kwargs["files"]
	assert key == "download.success" and files[0].filename == "a.mp3"


async def test_download_without_instance(ctx):
	cog = _cog(None)

	await cog.download.callback(cog, ctx, "https://example.com/s", False)

	ctx.send.assert_awaited_once_with("download.errors.unavailable")
	ctx.defer.assert_not_awaited()


@pytest.mark.parametrize(
	("error", "key"),
	[
		(CobaltError("error.api.link.invalid"), "download.errors.unsupported"),
		(aiohttp.ClientConnectionError(), "download.errors.unavailable"),
	],
)
async def test_download_reports_errors(ctx, error, key):
	cobalt = MagicMock()
	cobalt.resolve = AsyncMock(side_effect=error)
	cog = _cog(cobalt)

	await cog.download.callback(cog, ctx, "https://example.com/s", False)

	ctx.send.assert_awaited_once_with(key)


async def test_download_reports_too_large(ctx):
	cobalt = MagicMock()
	cobalt.resolve = AsyncMock(return_value=[Media("u", "v.mp4")])
	cobalt.fetch = AsyncMock(side_effect=FileTooLarge)
	cog = _cog(cobalt)

	await cog.download.callback(cog, ctx, "https://example.com/s", False)

	ctx.send.assert_awaited_once_with("download.errors.too_large", limit=10.0)
