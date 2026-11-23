"""Dashboard API routes for sign-in and the signed-in user."""

from __future__ import annotations

from api import DashboardUser, ErrorCode, ManagedGuild, SessionExchange, SessionGrant
from fastapi import APIRouter, status

from app.auth import AnySession, CurrentSession, State
from app.dashboard.discord import REQUIRED_SCOPES
from app.errors import ApiError

__all__ = ("router",)

router = APIRouter(tags=["account"])


@router.post("/auth/exchange")
async def exchange(body: SessionExchange, state: State) -> SessionGrant:
	"""Trade a Discord OAuth2 code for a dashboard session.

	Keep the returned token on the dashboard's server, never in the browser.

	\f
	Args:
		body: The OAuth2 code and its redirect URI.
		state: The app state.

	Returns:
		The session token, its expiry and the user.

	Raises:
		ApiError: ``not_found`` if sign-in isn't configured. ``unauthorized`` if Discord rejects the code.
			``forbidden`` if the ``identify`` or ``guilds`` scope is missing. ``blacklisted`` if the user is.
	"""
	if not state.config.dashboard_enabled:
		raise ApiError(ErrorCode.NOT_FOUND, "dashboard sign-in is not configured")
	tokens = await state.discord.exchange_code(body.code, body.redirect_uri)
	if missing := REQUIRED_SCOPES - tokens.scopes:
		await state.discord.revoke(tokens.access_token)
		raise ApiError(ErrorCode.FORBIDDEN, f"missing OAuth2 scopes: {', '.join(sorted(missing))}")
	user = await state.discord.current_user(tokens.access_token)
	if await state.blacklist.is_blacklisted("user", user.id):
		await state.discord.revoke(tokens.access_token)
		raise ApiError(ErrorCode.BLACKLISTED, "you are blacklisted")
	token, expires_at = await state.sessions.create(user, tokens)
	return SessionGrant(token=token, expires_at=expires_at, user=user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(session: AnySession, state: State) -> None:
	"""Sign out and revoke the user's Discord tokens. Blacklisted users may too.

	\f
	Args:
		session: The caller's dashboard session.
		state: The app state.
	"""
	await state.sessions.revoke(session.id)
	await state.discord.revoke(session.discord.refresh_token)


@router.get("/me")
async def me(session: CurrentSession) -> DashboardUser:
	"""Get the signed-in user's Discord profile, as of sign-in.

	\f
	Args:
		session: The caller's dashboard session.

	Returns:
		The user's profile.
	"""
	return session.user


@router.get("/guilds")
async def guilds(session: CurrentSession, state: State) -> list[ManagedGuild]:
	"""List the guilds the signed-in user manages, with or without the bot.

	\f
	Args:
		session: The caller's dashboard session.
		state: The app state.

	Returns:
		The managed guilds.

	Raises:
		ApiError: ``unauthorized`` if Discord rejects the user's tokens. ``discord_unavailable`` if Discord fails.
	"""
	return await state.access.managed_guilds(session)
