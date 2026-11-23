"""The PostgreSQL connection pool."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, cast

import asyncpg

__all__ = ("create_pool", "init_connection", "snowflake", "upsert")


async def init_connection(connection: asyncpg.Connection) -> None:
	"""Set up ``json`` and ``jsonb`` codecs on a new connection.

	Args:
		connection: The new connection.
	"""
	await connection.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
	await connection.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def create_pool(dsn: str, *, min_size: int = 2, max_size: int = 20) -> asyncpg.Pool:
	"""Open a connection pool with JSON codecs.

	Args:
		dsn: The PostgreSQL DSN.
		min_size: The fewest connections to keep open.
		max_size: The most connections to open.

	Returns:
		The pool.
	"""
	pool = await asyncpg.create_pool(
		dsn, min_size=min_size, max_size=max_size, init=init_connection, max_inactive_connection_lifetime=120
	)
	assert pool is not None
	return pool


def snowflake(value: Any) -> int | None:
	"""Convert a ``numeric`` snowflake column to an ``int``.

	Args:
		value: The column value.

	Returns:
		The snowflake, or ``None`` for ``NULL``.
	"""
	return None if value is None else int(value)


async def upsert(
	db: asyncpg.Pool | asyncpg.Connection, table: str, keys: Mapping[str, Any], fields: Mapping[str, Any]
) -> Mapping[str, Any]:
	"""Insert a row, or change some of its columns if it exists. New rows take column defaults for the rest.

	Args:
		db: The pool or connection to run on.
		table: The table. Never user input.
		keys: The conflict columns (a unique constraint) and their values. Never user input as column names.
		fields: The columns to write and their values.

	Returns:
		The row as stored.
	"""
	columns = [*keys, *fields]
	placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))
	changed = fields or {next(iter(keys)): None}  # an update that changes nothing still returns the row
	assignments = ", ".join(f"{column} = EXCLUDED.{column}" for column in changed)
	row = await db.fetchrow(
		f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
		f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {assignments} RETURNING *",
		*keys.values(),
		*fields.values(),
	)
	assert row is not None
	return cast("Mapping[str, Any]", row)
