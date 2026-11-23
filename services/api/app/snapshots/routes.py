"""Snapshot routes for the Internal API."""

from __future__ import annotations

from api import ErrorCode, Snapshot, SnapshotCreate, Snowflake
from fastapi import APIRouter

from app.auth import State
from app.errors import ApiError

__all__ = ("internal",)

internal = APIRouter(tags=["snapshots"])


@internal.post("/guilds/{guild_id}/snapshots", status_code=201)
async def internal_create_snapshot(guild_id: Snowflake, body: SnapshotCreate, state: State) -> Snapshot:
	"""Save a snapshot of a guild under a new random code.

	\f
	Args:
		guild_id: The guild.
		body: The snapshot.
		state: The app state.

	Returns:
		The saved snapshot, with its code.
	"""
	return await state.snapshots.create(guild_id, body)


@internal.get("/snapshots/{code}")
async def internal_snapshot(code: str, state: State) -> Snapshot:
	"""Get a snapshot by its code, ignoring case.

	\f
	Args:
		code: The snapshot's code.
		state: The app state.

	Returns:
		The snapshot.

	Raises:
		ApiError: ``not_found`` if there is no snapshot with that code.
	"""
	snapshot = await state.snapshots.get(code)
	if snapshot is None:
		raise ApiError(ErrorCode.NOT_FOUND, "no such snapshot")
	return snapshot
