"""The stores and clients a running API holds."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import asyncpg
import httpx
import redis.asyncio as aioredis
from cryptography.fernet import Fernet
from fastapi import Request

from app.bear_trap.store import BearTrapStore
from app.config import Settings
from app.dashboard.access import GuildAccess
from app.dashboard.discord import DiscordClient
from app.dashboard.sessions import SessionStore
from app.db import create_pool
from app.economy.store import Ledger
from app.events import Announcer
from app.ratelimit import RateLimiter
from app.settings.store import GuildSettingsStore
from app.status.store import StatusStore

__all__ = ("AppState", "build_state", "get_state")


@dataclass(frozen=True, slots=True)
class AppState:
	"""The stores and clients routes use, through the `State` dependency.

	Attributes:
		config: The configuration.
		ledger: The Ledger.
		guild_settings: The guild settings store.
		bear_traps: The bear trap store.
		discord: The Discord client.
		sessions: The dashboard session store.
		access: The guild manager checks.
		status: The status store.
		rate_limiter: Per-IP limits for the Public API.
	"""

	config: Settings
	ledger: Ledger
	guild_settings: GuildSettingsStore
	bear_traps: BearTrapStore
	discord: DiscordClient
	sessions: SessionStore
	access: GuildAccess
	status: StatusStore
	rate_limiter: RateLimiter


@asynccontextmanager
async def build_state(config: Settings) -> AsyncGenerator[AppState]:
	"""Open the database pool, Redis and the HTTP client, and close them on exit.

	Args:
		config: The configuration.

	Yields:
		The app state.
	"""
	pool = await create_pool(config.database_url)
	redis = aioredis.from_url(config.redis_url)
	http = httpx.AsyncClient(timeout=10)
	try:
		yield assemble(config, pool, redis, http)
	finally:
		await http.aclose()
		await redis.aclose()
		await pool.close()


def assemble(config: Settings, pool: asyncpg.Pool, redis: aioredis.Redis, http: httpx.AsyncClient) -> AppState:
	"""Build the app state on open connections.

	Args:
		config: The configuration.
		pool: The database pool.
		redis: The Redis client.
		http: The HTTP client for Discord.

	Returns:
		The app state.
	"""
	discord = DiscordClient(
		http,
		config.discord_api_url,
		config.discord_client_id or "",
		config.discord_client_secret or "",
		config.discord_bot_token,
	)
	# Without dashboard sign-in no session can be created, so a throwaway key is as good as any.
	announcer = Announcer(redis)
	sessions = SessionStore(pool, config.session_key or Fernet.generate_key().decode(), config.session_ttl)
	return AppState(
		config=config,
		ledger=Ledger(pool),
		guild_settings=GuildSettingsStore(pool, announcer),
		bear_traps=BearTrapStore(pool, announcer),
		discord=discord,
		sessions=sessions,
		access=GuildAccess(discord, sessions, redis, config.permission_ttl),
		status=StatusStore(pool, redis, config.status_sample_interval),
		rate_limiter=RateLimiter(redis),
	)


def get_state(request: Request) -> AppState:
	"""Get the running app's state.

	Args:
		request: The current request.

	Returns:
		The app state.
	"""
	return request.app.state.fm01
