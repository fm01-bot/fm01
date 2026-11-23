"""Shop routes for the Internal API."""

from __future__ import annotations

from typing import Annotated

from api import ErrorCode, ShopItem, Snowflake
from fastapi import APIRouter, Query, Response

from app.auth import State
from app.errors import ApiError

__all__ = ("internal",)

internal = APIRouter(prefix="/guilds/{guild_id}/shop", tags=["shop"])


@internal.get("")
async def internal_shop(guild_id: Snowflake, state: State) -> list[ShopItem]:
	"""List a guild's shop, oldest item first.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The items.
	"""
	return await state.shop.items(guild_id)


@internal.post("", status_code=201)
async def internal_add_shop_item(guild_id: Snowflake, body: ShopItem, state: State) -> ShopItem:
	"""Add an item to a guild's shop.

	\f
	Args:
		guild_id: The guild.
		body: The item.
		state: The app state.

	Returns:
		The stored item.
	"""
	return await state.shop.add(guild_id, body)


@internal.get("/item")
async def internal_shop_item(guild_id: Snowflake, name: Annotated[str, Query()], state: State) -> ShopItem:
	"""Get an item by its name, ignoring case.

	\f
	Args:
		guild_id: The guild.
		name: The item's name.
		state: The app state.

	Returns:
		The item.

	Raises:
		ApiError: ``not_found`` if the shop has no item with that name.
	"""
	item = await state.shop.get(guild_id, name)
	if item is None:
		raise ApiError(ErrorCode.NOT_FOUND, "no such item")
	return item


@internal.delete("/item", status_code=204)
async def internal_remove_shop_item(guild_id: Snowflake, name: Annotated[str, Query()], state: State) -> Response:
	"""Remove an item from a guild's shop, by its name ignoring case.

	\f
	Args:
		guild_id: The guild.
		name: The item's name.
		state: The app state.

	Returns:
		An empty response.

	Raises:
		ApiError: ``not_found`` if the shop has no item with that name.
	"""
	if not await state.shop.remove(guild_id, name):
		raise ApiError(ErrorCode.NOT_FOUND, "no such item")
	return Response(status_code=204)
