"""Shared fixtures: a throwaway PostgreSQL 16 database for the migration tests."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import asyncpg
import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def postgres_dsn() -> Iterator[str]:
	"""Start a PostgreSQL 16 container and yield its asyncpg-style DSN.

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
		yield container.get_connection_url().replace("postgresql://", "postgresql+asyncpg://", 1)
	finally:
		container.stop()


@pytest.fixture
def alembic(postgres_dsn: str):
	"""Return a callable that runs ``alembic <args>`` against the test database."""

	def run(*args: str) -> subprocess.CompletedProcess[str]:
		return subprocess.run(
			[sys.executable, "-m", "alembic", "-x", f"url={postgres_dsn}", *args],
			cwd=MIGRATIONS_DIR,
			check=True,
			capture_output=True,
			text=True,
		)

	return run


@pytest.fixture
def query(postgres_dsn: str):
	"""Return a callable that runs a read-only query and returns its rows as tuples."""

	def run(sql: str) -> list[tuple]:
		async def fetch() -> list[tuple]:
			conn = await asyncpg.connect(postgres_dsn.replace("postgresql+asyncpg://", "postgresql://", 1))
			try:
				return [tuple(row) for row in await conn.fetch(sql)]
			finally:
				await conn.close()

		return asyncio.run(fetch())

	return run
