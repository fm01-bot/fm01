from __future__ import annotations

import math
import re

import aiohttp
import yarl
from discord import utils
from discord.gateway import DiscordWebSocket

__all__ = (
	"configure_gateway_proxy",
	"fetch_proxy_shard_count",
	"fetch_proxy_shard_latency",
	"metrics_url",
	"parse_shard_latency",
	"shard_count_url",
)

_SHARD_LATENCY_LINE = re.compile(r'^gateway_shard_latency\{(?:[^}]*,)?shard="(?P<shard>\d+)"[^}]*\}\s+(?P<value>\S+)')


def configure_gateway_proxy(gateway_url: str) -> None:
	"""Point every gateway connection discord.py opens at the gateway proxy.

	discord.py connects to ``DiscordWebSocket.DEFAULT_GATEWAY`` on startup when a shard count is set, and falls back to it
	whenever a session is invalidated, so replacing it keeps re-identifies behind the proxy as well.

	Args:
		gateway_url: The proxy's WebSocket URL, e.g. ``ws://gateway-proxy:7878``.

	Raises:
		RuntimeError: The installed discord.py negotiates a transport compression the proxy cannot produce.
	"""
	compression = getattr(utils._ActiveDecompressionContext, "COMPRESSION_TYPE", None)
	if compression != "zlib-stream":
		raise RuntimeError(
			f"discord.py uses {compression} gateway compression, but the gateway proxy only speaks zlib-stream"
		)
	DiscordWebSocket.DEFAULT_GATEWAY = yarl.URL(gateway_url)


def _http_url(gateway_url: str, path: str) -> str:
	url = yarl.URL(gateway_url)
	scheme = {"ws": "http", "wss": "https"}.get(url.scheme, url.scheme)
	return str(url.with_scheme(scheme).with_path(path).with_query(None))


def shard_count_url(gateway_url: str) -> str:
	"""Build the URL of the proxy's ``/shard-count`` endpoint from its WebSocket URL.

	Args:
		gateway_url: The proxy's WebSocket URL (``ws://`` or ``wss://``).

	Returns:
		str: The HTTP(S) URL that returns the proxy's shard count as plain text.
	"""
	return _http_url(gateway_url, "/shard-count")


def metrics_url(gateway_url: str) -> str:
	"""Build the URL of the proxy's Prometheus ``/metrics`` endpoint from its WebSocket URL.

	Args:
		gateway_url: The proxy's WebSocket URL (``ws://`` or ``wss://``).

	Returns:
		str: The HTTP(S) URL that returns the proxy's metrics in Prometheus text format.
	"""
	return _http_url(gateway_url, "/metrics")


def parse_shard_latency(metrics: str, shard_id: int) -> float | None:
	"""Read one shard's Discord heartbeat latency from the proxy's Prometheus metrics.

	The proxy answers client heartbeats itself, so discord.py's own latency only covers the hop to the proxy. The
	``gateway_shard_latency`` gauge holds the proxy's latest heartbeat round trip to Discord for each shard.

	Args:
		metrics: The body of the proxy's ``/metrics`` response.
		shard_id: The shard to read.

	Returns:
		float | None: The latency in seconds, or ``None`` if the shard has no finite sample.
	"""
	for line in metrics.splitlines():
		match = _SHARD_LATENCY_LINE.match(line)
		if match is None or int(match["shard"]) != shard_id:
			continue
		try:
			latency = float(match["value"])
		except ValueError:
			return None
		return latency if math.isfinite(latency) else None
	return None


async def fetch_proxy_shard_count(session: aiohttp.ClientSession, gateway_url: str) -> int:
	"""Ask the gateway proxy how many shards it runs.

	Args:
		session: The HTTP session to use.
		gateway_url: The proxy's WebSocket URL.

	Returns:
		int: The proxy's total shard count.
	"""
	async with session.get(shard_count_url(gateway_url), timeout=aiohttp.ClientTimeout(total=10)) as response:
		response.raise_for_status()
		return int(await response.text())


async def fetch_proxy_shard_latency(session: aiohttp.ClientSession, gateway_url: str, shard_id: int) -> float | None:
	"""Ask the gateway proxy for one shard's heartbeat latency to Discord.

	Args:
		session: The HTTP session to use.
		gateway_url: The proxy's WebSocket URL.
		shard_id: The shard to read.

	Returns:
		float | None: The latency in seconds, or ``None`` if the proxy has no sample for the shard yet.
	"""
	async with session.get(metrics_url(gateway_url), timeout=aiohttp.ClientTimeout(total=3)) as response:
		response.raise_for_status()
		return parse_shard_latency(await response.text(), shard_id)
