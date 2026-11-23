"""The shop store."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import asyncpg
from api import MAX_SHOP_ITEMS, ErrorCode, ShopItem

from app.errors import ApiError

__all__ = ("ShopStore",)

_COLUMNS = "item_name, item_description, item_price, role, creator_id"


def _item(row: Mapping[str, Any]) -> ShopItem:
	"""Build a shop item from a ``shop`` row.

	Args:
		row: The row.

	Returns:
		The item.
	"""
	return ShopItem(
		name=row["item_name"],
		description=row["item_description"],
		price=int(row["item_price"]),
		role_id=int(row["role"]),
		creator_id=int(row["creator_id"]),
	)


class ShopStore:
	"""Reads and writes guilds' shops.

	Args:
		db: The database pool.
	"""

	def __init__(self, db: asyncpg.Pool) -> None:
		self._db = db

	async def items(self, guild_id: int) -> list[ShopItem]:
		"""List a guild's shop.

		Args:
			guild_id: The guild.

		Returns:
			The items, oldest first.
		"""
		rows = await self._db.fetch(f"SELECT {_COLUMNS} FROM shop WHERE guild_id = $1 ORDER BY id", guild_id)
		return [_item(row) for row in rows]

	async def get(self, guild_id: int, name: str) -> ShopItem | None:
		"""Get an item.

		Args:
			guild_id: The guild.
			name: The item's name, ignoring case.

		Returns:
			The item, or ``None`` if the shop has none with that name.
		"""
		row = await self._db.fetchrow(
			f"SELECT {_COLUMNS} FROM shop WHERE guild_id = $1 AND lower(item_name) = lower($2) ORDER BY id LIMIT 1",
			guild_id,
			name,
		)
		return _item(row) if row else None

	async def add(self, guild_id: int, item: ShopItem) -> ShopItem:
		"""Add an item to a guild's shop.

		Args:
			guild_id: The guild.
			item: The item.

		Returns:
			The stored item.

		Raises:
			ApiError: ``shop_item_taken`` if an item has that name, ``shop_limit`` if the shop is full.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			# Serialize additions per guild, so two at once can't both pass the checks.
			await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('shop:' || $1::text, 0))", str(guild_id))
			names = [
				row["item_name"].lower()
				for row in await conn.fetch("SELECT item_name FROM shop WHERE guild_id = $1", guild_id)
			]
			if item.name.lower() in names:
				raise ApiError(ErrorCode.SHOP_ITEM_TAKEN)
			if len(names) >= MAX_SHOP_ITEMS:
				raise ApiError(ErrorCode.SHOP_LIMIT)
			await conn.execute(
				"INSERT INTO shop (guild_id, item_name, item_description, item_price, role, creator_id) "
				"VALUES ($1, $2, $3, $4, $5, $6)",
				guild_id,
				item.name,
				item.description,
				item.price,
				item.role_id,
				item.creator_id,
			)
		return item

	async def remove(self, guild_id: int, name: str) -> bool:
		"""Remove an item from a guild's shop.

		Args:
			guild_id: The guild.
			name: The item's name, ignoring case.

		Returns:
			Whether there was such an item.
		"""
		status = await self._db.execute(
			"DELETE FROM shop WHERE guild_id = $1 AND lower(item_name) = lower($2)", guild_id, name
		)
		return status != "DELETE 0"
