"""Blacklist routes for the Internal API. The Dashboard API enforces the blacklist in `app.auth`."""

from __future__ import annotations

from api import BlacklistAdd, BlacklistEntry, BlacklistKind, ErrorCode, Snowflake
from fastapi import APIRouter, Response

from app.auth import State
from app.errors import ApiError

__all__ = ("internal",)

internal = APIRouter(prefix="/blacklist", tags=["blacklist"])


@internal.get("")
async def internal_blacklist(state: State) -> list[BlacklistEntry]:
	"""List every blacklisted user and guild, oldest first.

	\f
	Args:
		state: The app state.

	Returns:
		The entries.
	"""
	return await state.blacklist.entries()


@internal.put("/{kind}/{target_id}")
async def internal_blacklist_add(
	kind: BlacklistKind, target_id: Snowflake, body: BlacklistAdd, state: State
) -> BlacklistEntry:
	"""Blacklist a user or guild. Blacklisting it again replaces the reason and who added it.

	\f
	Args:
		kind: Whether the target is a user or a guild.
		target_id: The user or guild.
		body: Who blacklists it, and why.
		state: The app state.

	Returns:
		The entry.
	"""
	return await state.blacklist.add(kind, target_id, body)


@internal.delete("/{kind}/{target_id}", status_code=204)
async def internal_blacklist_remove(kind: BlacklistKind, target_id: Snowflake, state: State) -> Response:
	"""Take a user or guild off the blacklist.

	\f
	Args:
		kind: Whether the target is a user or a guild.
		target_id: The user or guild.
		state: The app state.

	Returns:
		An empty response.

	Raises:
		ApiError: ``not_found`` if it wasn't blacklisted.
	"""
	if not await state.blacklist.remove(kind, target_id):
		raise ApiError(ErrorCode.NOT_FOUND, f"{kind} {target_id} is not blacklisted")
	return Response(status_code=204)
