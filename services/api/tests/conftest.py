"""Fixtures: a throwaway PostgreSQL 16 database, fake Redis, a fake Discord, and an API client wired to them."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import asyncpg
import fakeredis
import httpx
import pytest
from app.config import Settings
from app.db import create_pool
from app.main import create_app
from app.state import AppState, assemble
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT.parent / "migrations"
INTERNAL_TOKEN = "internal-test-token"


@pytest.fixture(scope="session")
def postgres_dsn() -> Iterator[str]:
	"""Start a PostgreSQL 16 container, migrate it to head, and yield its DSN.

	Skips when Docker is unavailable, unless ``REQUIRE_DB_TESTS`` is set (as in CI), in which case it fails.
	"""
	try:
		from testcontainers.community.postgres import PostgresContainer

		container = PostgresContainer("postgres:16-alpine", driver=None)
		container.start()
	except Exception as exc:
		if os.getenv("REQUIRE_DB_TESTS"):
			raise
		pytest.skip(f"Docker unavailable for database tests: {exc}")

	try:
		dsn = container.get_connection_url()
		subprocess.run(
			[sys.executable, "-m", "alembic", "-x", f"url={dsn.replace('postgresql://', 'postgresql+asyncpg://', 1)}"]
			+ ["upgrade", "head"],
			cwd=MIGRATIONS_DIR,
			check=True,
			capture_output=True,
		)
		yield dsn
	finally:
		container.stop()


@pytest.fixture
async def db(postgres_dsn: str) -> AsyncIterator[asyncpg.Pool]:
	"""A connection pool to an empty, fully migrated database."""
	pool = await create_pool(postgres_dsn, min_size=1, max_size=8)
	tables = await pool.fetch(
		"SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
	)
	if tables:
		names = ", ".join(f'"{row["tablename"]}"' for row in tables)
		await pool.execute(f"TRUNCATE {names} RESTART IDENTITY CASCADE")
	try:
		yield pool
	finally:
		await pool.close()


@dataclass
class FakeDiscord:
	"""Just enough of Discord's REST API for the dashboard: OAuth2, the current user, guild and channel lookups."""

	codes: dict[str, str] = field(default_factory=dict)
	"""Authorization code -> access token it grants."""
	users: dict[str, dict[str, Any]] = field(default_factory=dict)
	"""Access token -> user object."""
	guilds: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
	"""Access token -> ``/users/@me/guilds`` entries."""
	bot_guilds: set[int] = field(default_factory=set)
	channels: dict[int, dict[str, Any]] = field(default_factory=dict)
	"""Channel ID -> channel object the bot can see."""
	emojis: dict[int, set[int]] = field(default_factory=dict)
	"""Guild ID -> IDs of its custom emojis."""
	scope: str = "identify guilds"
	calls: list[str] = field(default_factory=list)
	revoked: list[str] = field(default_factory=list)

	def handler(self, request: httpx.Request) -> httpx.Response:
		path = request.url.path.removeprefix("/api/v10")
		self.calls.append(f"{request.method} {path}")
		if path == "/oauth2/token":
			form = dict(httpx.QueryParams(request.content.decode()))
			if form["grant_type"] == "authorization_code":
				access = self.codes.get(form["code"])
			else:
				access = form["refresh_token"].removeprefix("refresh-")
			if access is None:
				return httpx.Response(400, json={"error": "invalid_grant"})
			return httpx.Response(
				200,
				json={
					"access_token": access,
					"refresh_token": f"refresh-{access}",
					"expires_in": 604800,
					"scope": self.scope,
				},
			)
		if path == "/oauth2/token/revoke":
			self.revoked.append(dict(httpx.QueryParams(request.content.decode()))["token"])
			return httpx.Response(200, json={})
		auth = request.headers.get("Authorization", "")
		if path == "/users/@me":
			user = self.users.get(auth.removeprefix("Bearer "))
			return httpx.Response(200, json=user) if user else httpx.Response(401, json={})
		if path == "/users/@me/guilds":
			guilds = self.guilds.get(auth.removeprefix("Bearer "))
			return httpx.Response(200, json=guilds) if guilds is not None else httpx.Response(401, json={})
		if path.startswith("/channels/") and auth.startswith("Bot "):
			channel = self.channels.get(int(path.removeprefix("/channels/")))
			return httpx.Response(200, json=channel) if channel else httpx.Response(404, json={})
		if path.startswith("/guilds/") and "/emojis/" in path and auth.startswith("Bot "):
			guild, emoji = path.removeprefix("/guilds/").split("/emojis/")
			if int(emoji) in self.emojis.get(int(guild), set()):
				return httpx.Response(200, json={"id": emoji})
			return httpx.Response(404, json={})
		if path.startswith("/guilds/") and auth.startswith("Bot "):
			guild_id = int(path.removeprefix("/guilds/"))
			if guild_id in self.bot_guilds:
				return httpx.Response(200, json={"id": str(guild_id)})
			return httpx.Response(403, json={})
		return httpx.Response(404, json={})


@dataclass
class Api:
	client: httpx.AsyncClient
	db: asyncpg.Pool
	redis: fakeredis.FakeAsyncRedis
	discord: FakeDiscord

	@property
	def internal(self) -> dict[str, str]:
		return {"Authorization": f"Bearer {INTERNAL_TOKEN}"}


@pytest.fixture
async def api(db: asyncpg.Pool) -> AsyncIterator[Api]:
	redis = fakeredis.FakeAsyncRedis()
	discord = FakeDiscord()
	config = Settings(
		database_url="unused",
		redis_url="unused",
		internal_token=INTERNAL_TOKEN,
		discord_client_id="client-id",
		discord_client_secret="client-secret",
		discord_bot_token="bot-token",
		session_key=Fernet.generate_key().decode(),
		status_sampler=False,  # tests sample by hand
	)

	@asynccontextmanager
	async def state(cfg: Settings) -> AsyncGenerator[AppState]:
		async with httpx.AsyncClient(transport=httpx.MockTransport(discord.handler)) as http:
			yield assemble(cfg, db, redis, http)

	app = create_app(config, state)
	async with app.router.lifespan_context(app):
		transport = httpx.ASGITransport(app=app)
		async with httpx.AsyncClient(transport=transport, base_url="http://api") as client:
			yield Api(client, db, redis, discord)
	await redis.aclose()


class EventLog:
	"""Messages published on the event bus during a test."""

	def __init__(self, pubsub) -> None:
		self._pubsub = pubsub

	async def drain(self) -> list[dict[str, Any]]:
		"""Every message published since the last drain, decoded."""
		received = []
		while (message := await self._pubsub.get_message(timeout=0.05)) is not None:
			received.append(json.loads(message["data"]))
		return received


@pytest.fixture
async def events(api: Api) -> AsyncIterator[EventLog]:
	pubsub = api.redis.pubsub()
	await pubsub.subscribe("fm01:events")
	await pubsub.get_message(timeout=1)  # the subscribe confirmation
	yield EventLog(pubsub)
	await pubsub.aclose()
