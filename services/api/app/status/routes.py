"""Status routes for the Public API."""

from __future__ import annotations

from typing import Annotated

from api import Status, StatusHistory
from fastapi import APIRouter, Depends, Query

from app.auth import State
from app.ratelimit import rate_limit
from app.status.store import HISTORY_DAYS

__all__ = ("public",)

public = APIRouter(prefix="/status", tags=["status"])


@public.get("", dependencies=[Depends(rate_limit("status", 60))])
async def status(state: State) -> Status:
	"""Get the bot's current status: overall, per status block, and per shard.

	Updated at most every 10 seconds. Limited to 60 requests per minute per IP.

	\f
	Args:
		state: The app state.

	Returns:
		The current status.
	"""
	return await state.status.cached_status()


@public.get("/history", dependencies=[Depends(rate_limit("status_history", 10))])
async def status_history(
	state: State, days: Annotated[int, Query(ge=1, le=HISTORY_DAYS)] = HISTORY_DAYS
) -> StatusHistory:
	"""Get the bot's daily status history, overall, per status block and per shard. Days are UTC; today is partial.

	Updated at most every 5 minutes. Limited to 10 requests per minute per IP.

	\f
	Args:
		state: The app state.
		days: How many days, today included.

	Returns:
		The history.
	"""
	return await state.status.cached_history(days)
