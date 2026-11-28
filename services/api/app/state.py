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

from app.afk.store import AfkStore
from app.alerts.store import AlertStore
from app.automod.store import AutoModStore
from app.bear_trap.store import BearTrapStore
from app.blacklist.store import BlacklistStore
from app.config import Settings
from app.dashboard.access import GuildAccess
from app.dashboard.discord import DiscordClient
from app.dashboard.sessions import SessionStore
from app.db import create_pool
from app.economy.store import Ledger
from app.events import Announcer
from app.giveaways.store import GiveawayStore
from app.greetings.store import GreetingStore
from app.leveling.store import LevelStore
from app.log.store import LogStore
from app.moderation.store import CaseStore
from app.ratelimit import RateLimiter
from app.settings.store import GuildSettingsStore
from app.shop.store import ShopStore
from app.snapshots.store import SnapshotStore
from app.starboard.store import StarboardStore
from app.status.store import StatusStore
from app.suggestions.store import SuggestionStore
from app.tickets.store import TicketStore

__all__ = ("AppState", "build_state", "get_state")


@dataclass(frozen=True, slots=True)
class AppState:
	"""The stores and clients routes use, through the `State` dependency.

	Attributes:
		config: The configuration.
		ledger: The Ledger.
		guild_settings: The guild settings store.
		bear_traps: The bear trap store.
		starboards: The starboard store.
		greetings: The join and leave message store.
		automod: The AutoMod configuration store.
		log: The log configuration store.
		cases: The moderation case store.
		tickets: The support ticket store.
		levels: The leveling store.
		afk: The AFK store.
		snapshots: The snapshot store.
		shop: The shop store.
		giveaways: The giveaway store.
		alerts: The media alert store.
		suggestions: The suggestion store.
		blacklist: The blacklist store.
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
	starboards: StarboardStore
	suggestions: SuggestionStore
	greetings: GreetingStore
	automod: AutoModStore
	log: LogStore
	cases: CaseStore
	tickets: TicketStore
	levels: LevelStore
	afk: AfkStore
	snapshots: SnapshotStore
	shop: ShopStore
	giveaways: GiveawayStore
	alerts: AlertStore
	blacklist: BlacklistStore
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
	blacklist = BlacklistStore(pool, announcer)
	sessions = SessionStore(pool, config.session_key or Fernet.generate_key().decode(), config.session_ttl)
	return AppState(
		config=config,
		ledger=Ledger(pool),
		guild_settings=GuildSettingsStore(pool, announcer),
		bear_traps=BearTrapStore(pool, announcer),
		starboards=StarboardStore(pool, announcer),
		suggestions=SuggestionStore(pool, announcer),
		greetings=GreetingStore(pool, announcer),
		automod=AutoModStore(pool, announcer),
		log=LogStore(pool, announcer),
		cases=CaseStore(pool, announcer),
		tickets=TicketStore(pool, announcer),
		levels=LevelStore(pool, announcer),
		afk=AfkStore(pool),
		snapshots=SnapshotStore(pool),
		shop=ShopStore(pool),
		giveaways=GiveawayStore(pool),
		alerts=AlertStore(pool),
		blacklist=blacklist,
		discord=discord,
		sessions=sessions,
		access=GuildAccess(discord, sessions, blacklist, redis, config.permission_ttl),
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
