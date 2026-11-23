"""The shop: roles members buy with economy cash."""

from pydantic import BaseModel

from api.snowflake import Snowflake

__all__ = ("MAX_SHOP_ITEMS", "ShopItem")

MAX_SHOP_ITEMS = 9
"""The most items one guild's shop may hold."""


class ShopItem(BaseModel):
	"""An item in a guild's shop. Names are unique per guild, ignoring case."""

	name: str
	description: str
	price: int
	role_id: Snowflake
	"""The role a buyer gets."""
	creator_id: Snowflake
