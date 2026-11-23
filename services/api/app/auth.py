"""Authentication for the Internal API and the Dashboard API."""

from __future__ import annotations

import hmac
from typing import Annotated

from api import ErrorCode, Snowflake
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.dashboard.access import BAN_MEMBERS
from app.dashboard.sessions import Session
from app.errors import ApiError
from app.state import AppState, get_state

__all__ = (
	"AnySession",
	"BanManagedGuildId",
	"CurrentSession",
	"ManagedGuildId",
	"Origin",
	"State",
	"require_internal",
)

State = Annotated[AppState, Depends(get_state)]

_bearer = HTTPBearer(auto_error=False)
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def _token(credentials: HTTPAuthorizationCredentials | None) -> str:
	"""Get the bearer token from the credentials.

	Args:
		credentials: The parsed ``Authorization`` header, if any.

	Returns:
		The bearer token.

	Raises:
		ApiError: ``unauthorized`` if there is no token.
	"""
	if credentials is None or not credentials.credentials:
		raise ApiError(ErrorCode.UNAUTHORIZED, "missing bearer token")
	return credentials.credentials


async def require_internal(state: State, credentials: Credentials) -> None:
	"""Allow only callers with ``API_INTERNAL_TOKEN``.

	Args:
		state: The app state.
		credentials: The parsed ``Authorization`` header, if any.

	Raises:
		ApiError: ``unauthorized`` if the token is missing or wrong.
	"""
	if not hmac.compare_digest(_token(credentials).encode(), state.config.internal_token.encode()):
		raise ApiError(ErrorCode.UNAUTHORIZED, "invalid internal token")


Origin = Annotated[
	str | None,
	Header(
		alias="X-Fm01-Origin",
		description="The calling bot instance's ID. Change events from this request carry it, so that instance ignores them.",
	),
]


async def any_session(state: State, credentials: Credentials) -> Session:
	"""Get the dashboard session of the bearer token.

	Args:
		state: The app state.
		credentials: The parsed ``Authorization`` header, if any.

	Returns:
		The session.

	Raises:
		ApiError: ``unauthorized`` if the token is missing, unknown or expired.
	"""
	session = await state.sessions.get(_token(credentials))
	if session is None:
		raise ApiError(ErrorCode.UNAUTHORIZED, "invalid or expired session")
	return session


AnySession = Annotated[Session, Depends(any_session)]
"""The caller's session, for routes a blacklisted user may still call (signing out)."""


async def current_session(state: State, session: AnySession) -> Session:
	"""Get the dashboard session of the bearer token, unless its user is blacklisted.

	Args:
		state: The app state.
		session: The session of the bearer token.

	Returns:
		The session.

	Raises:
		ApiError: ``unauthorized`` if the token is missing, unknown or expired. ``blacklisted`` if the user is.
	"""
	if await state.blacklist.is_blacklisted("user", session.user.id):
		raise ApiError(ErrorCode.BLACKLISTED, "you are blacklisted")
	return session


CurrentSession = Annotated[Session, Depends(current_session)]


async def managed_guild_id(guild_id: Snowflake, state: State, session: CurrentSession) -> int:
	"""Check that the session's user is a guild manager of the guild.

	Args:
		guild_id: The ``guild_id`` path parameter.
		state: The app state.
		session: The caller's dashboard session.

	Returns:
		The guild ID.

	Raises:
		ApiError: ``forbidden``, ``blacklisted`` or ``not_found``. See `GuildAccess.require_manager`.
	"""
	await state.access.require_manager(session, guild_id)
	return guild_id


ManagedGuildId = Annotated[int, Depends(managed_guild_id)]


async def ban_managed_guild_id(guild_id: Snowflake, state: State, session: CurrentSession) -> int:
	"""Check that the session's user is a guild manager of the guild who may also ban members in it.

	For settings that make the bot remove members (the bear trap soft-bans), so Manage Server alone can't.

	Args:
		guild_id: The ``guild_id`` path parameter.
		state: The app state.
		session: The caller's dashboard session.

	Returns:
		The guild ID.

	Raises:
		ApiError: ``forbidden``, ``blacklisted`` or ``not_found``. See `GuildAccess.require_manager`.
	"""
	await state.access.require_manager(session, guild_id, BAN_MEMBERS)
	return guild_id


BanManagedGuildId = Annotated[int, Depends(ban_managed_guild_id)]
