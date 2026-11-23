"""Signing in to the dashboard and choosing a guild."""

from datetime import datetime

from pydantic import BaseModel

from api.snowflake import Snowflake

__all__ = ("DashboardUser", "ManagedGuild", "SessionExchange", "SessionGrant")


class SessionExchange(BaseModel):
	"""The Discord OAuth2 authorization code the dashboard received, to trade for a dashboard session."""

	code: str
	redirect_uri: str
	"""The redirect URI the code was issued for. Discord requires it again."""


class DashboardUser(BaseModel):
	"""A signed-in user's Discord profile."""

	id: Snowflake
	username: str
	global_name: str | None = None
	avatar: str | None = None
	"""Discord avatar hash. ``None`` for the default avatar."""


class SessionGrant(BaseModel):
	"""A new dashboard session."""

	token: str
	"""The dashboard session token. Send it as ``Authorization: Bearer <token>`` and keep it out of the browser."""
	expires_at: datetime
	user: DashboardUser


class ManagedGuild(BaseModel):
	"""A guild the signed-in user is a guild manager of."""

	id: Snowflake
	name: str
	icon: str | None = None
	"""Discord icon hash."""
