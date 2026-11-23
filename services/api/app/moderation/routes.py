"""Moderation case and case retention routes for the Internal API."""

from __future__ import annotations

from typing import Annotated

from api import (
	CaseClosed,
	CaseCreate,
	CaseFilter,
	CaseRecord,
	CaseRetention,
	CaseUpdate,
	ErrorCode,
	PendingCase,
	Snowflake,
)
from fastapi import APIRouter, Query, Response

from app.auth import Origin, State
from app.errors import ApiError

__all__ = ("internal",)

internal = APIRouter(tags=["moderation"])


@internal.get("/guilds/{guild_id}/settings/case-retention")
async def internal_case_retention(guild_id: Snowflake, state: State) -> CaseRetention:
	"""Get a guild's case retention. `keep` if the guild never set one.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The retention.
	"""
	return CaseRetention(retention=await state.cases.retention(guild_id))


@internal.put("/guilds/{guild_id}/settings/case-retention")
async def internal_set_case_retention(
	guild_id: Snowflake, body: CaseRetention, state: State, origin: Origin = None
) -> CaseRetention:
	"""Set a guild's case retention.

	\f
	Args:
		guild_id: The guild.
		body: The retention.
		state: The app state.
		origin: The calling bot instance.

	Returns:
		The stored retention.
	"""
	await state.cases.set_retention(guild_id, body.retention, origin)
	return body


@internal.get("/cases/pending")
async def internal_pending_cases(state: State) -> list[PendingCase]:
	"""List every open case that expires.

	\f
	Args:
		state: The app state.

	Returns:
		The cases, with their guild and expiry.
	"""
	return await state.cases.pending()


@internal.get("/cases/{case_id}")
async def internal_case_anywhere(case_id: Snowflake, state: State) -> CaseRecord:
	"""Get a case in any guild, e.g. to expire it.

	\f
	Args:
		case_id: The case.
		state: The app state.

	Returns:
		The case.

	Raises:
		ApiError: ``not_found`` if there is no such case.
	"""
	case = await state.cases.get(case_id)
	if case is None:
		raise ApiError(ErrorCode.NOT_FOUND, "no such case")
	return case


@internal.get("/guilds/{guild_id}/cases")
async def internal_user_cases(
	guild_id: Snowflake,
	state: State,
	user_id: Annotated[Snowflake, Query()],
	which: CaseFilter = "all",
	type: Annotated[int | None, Query(ge=1, le=5)] = None,
) -> list[CaseRecord]:
	"""List a user's cases in a guild, oldest first.

	\f
	Args:
		guild_id: The guild.
		state: The app state.
		user_id: The user the cases are about.
		which: Which cases. See `CaseFilter`.
		type: Only cases of this type.

	Returns:
		The cases.
	"""
	return await state.cases.for_user(guild_id, user_id, which, type)


@internal.post("/guilds/{guild_id}/cases", status_code=201)
async def internal_create_case(guild_id: Snowflake, body: CaseCreate, state: State) -> CaseRecord:
	"""Record a new case. The bot performs its Discord effect and deletes the case again if that fails.

	\f
	Args:
		guild_id: The guild.
		body: The case.
		state: The app state.

	Returns:
		The stored case.
	"""
	return await state.cases.create(guild_id, body)


@internal.get("/guilds/{guild_id}/cases/{case_id}")
async def internal_case(guild_id: Snowflake, case_id: Snowflake, state: State) -> CaseRecord:
	"""Get a case in a guild.

	\f
	Args:
		guild_id: The guild.
		case_id: The case.
		state: The app state.

	Returns:
		The case.

	Raises:
		ApiError: ``not_found`` if the guild has no such case.
	"""
	case = await state.cases.get(case_id, guild_id)
	if case is None:
		raise ApiError(ErrorCode.NOT_FOUND, "no such case")
	return case


@internal.put("/guilds/{guild_id}/cases/{case_id}")
async def internal_update_case(guild_id: Snowflake, case_id: Snowflake, body: CaseUpdate, state: State) -> CaseRecord:
	"""Set a case's reason, expiry and message.

	\f
	Args:
		guild_id: The guild.
		case_id: The case.
		body: The new values.
		state: The app state.

	Returns:
		The stored case.
	"""
	return await state.cases.update(guild_id, case_id, body)


@internal.post("/guilds/{guild_id}/cases/{case_id}/close")
async def internal_close_case(guild_id: Snowflake, case_id: Snowflake, state: State) -> CaseClosed:
	"""Close a case following the guild's retention: delete it or mark it inactive.

	\f
	Args:
		guild_id: The guild.
		case_id: The case.
		state: The app state.

	Returns:
		What closing did.
	"""
	return await state.cases.close(guild_id, case_id)


@internal.delete("/guilds/{guild_id}/cases/{case_id}", status_code=204)
async def internal_delete_case(guild_id: Snowflake, case_id: Snowflake, state: State) -> Response:
	"""Delete a case regardless of retention. Deleting a case that doesn't exist does nothing.

	\f
	Args:
		guild_id: The guild.
		case_id: The case.
		state: The app state.

	Returns:
		An empty response.
	"""
	await state.cases.delete(guild_id, case_id)
	return Response(status_code=204)
