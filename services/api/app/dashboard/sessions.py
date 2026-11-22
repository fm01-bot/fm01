"""The dashboard session store.

A session token is ``<id>.<secret>``. The secret is stored only as a salted SHA-256 hash. The Discord tokens are
stored Fernet-encrypted.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import asyncpg
from api import DashboardUser
from cryptography.fernet import Fernet, InvalidToken

from app.dashboard.discord import OAuthTokenSet

__all__ = ("Session", "SessionStore")


@dataclass(frozen=True, slots=True)
class Session:
	"""A signed-in dashboard user.

	Attributes:
		id: The public half of the session token.
		user: The user's Discord profile at sign-in.
		discord: The user's Discord tokens, decrypted.
		expires_at: When the session ends.
	"""

	id: str
	user: DashboardUser
	discord: OAuthTokenSet
	expires_at: datetime


def _hash(salt: str, secret: str) -> str:
	"""Hash a session token's secret with its salt.

	Args:
		salt: The session's salt, in hex.
		secret: The secret half of the session token.

	Returns:
		The SHA-256 hash, in hex.
	"""
	return hashlib.sha256(bytes.fromhex(salt) + secret.encode()).hexdigest()


class SessionStore:
	"""Creates, reads and ends dashboard sessions.

	Args:
		db: The database pool.
		key: The Fernet key the Discord tokens are encrypted with.
		ttl: How long a new session lasts.
	"""

	def __init__(self, db: asyncpg.Pool, key: str, ttl: timedelta) -> None:
		self._db = db
		self._fernet = Fernet(key.encode())
		self._ttl = ttl

	async def create(self, user: DashboardUser, tokens: OAuthTokenSet) -> tuple[str, datetime]:
		"""Open a session for a user. Also deletes expired sessions.

		Args:
			user: The user's Discord profile.
			tokens: The user's Discord tokens.

		Returns:
			The session token (``<id>.<secret>``) and its expiry. The token can't be recovered later.
		"""
		session_id, secret, salt = secrets.token_urlsafe(16), secrets.token_urlsafe(32), secrets.token_hex(16)
		expires_at = datetime.now(UTC) + self._ttl
		async with self._db.acquire() as conn, conn.transaction():
			await conn.execute("DELETE FROM dashboard_sessions WHERE expires_at < now()")
			await conn.execute(
				"INSERT INTO dashboard_sessions "
				"(id, token_salt, token_hash, user_id, user_profile, access_token, refresh_token, discord_expires_at, "
				"scopes, expires_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
				session_id,
				salt,
				_hash(salt, secret),
				user.id,
				user.model_dump(mode="json"),
				self._encrypt(tokens.access_token),
				self._encrypt(tokens.refresh_token),
				tokens.expires_at,
				sorted(tokens.scopes),
				expires_at,
			)
		return f"{session_id}.{secret}", expires_at

	async def get(self, token: str) -> Session | None:
		"""Look up a session by its token.

		Args:
			token: The session token.

		Returns:
			The session. ``None`` if the token is malformed, unknown, expired or encrypted with an old key.
		"""
		session_id, _, secret = token.partition(".")
		if not secret:
			return None
		row = await self._db.fetchrow(
			"SELECT * FROM dashboard_sessions WHERE id = $1 AND expires_at > now()", session_id
		)
		if row is None or not hmac.compare_digest(_hash(row["token_salt"], secret), row["token_hash"]):
			return None
		try:
			tokens = OAuthTokenSet(
				access_token=self._decrypt(row["access_token"]),
				refresh_token=self._decrypt(row["refresh_token"]),
				expires_at=row["discord_expires_at"],
				scopes=frozenset(row["scopes"]),
			)
		except InvalidToken:
			return None
		return Session(
			id=row["id"],
			user=DashboardUser.model_validate(row["user_profile"]),
			discord=tokens,
			expires_at=row["expires_at"],
		)

	async def discord_tokens(self, session_id: str) -> OAuthTokenSet | None:
		"""Read a session's current Discord tokens, e.g. after another request refreshed them.

		Args:
			session_id: The session.

		Returns:
			The tokens. ``None`` if the session ended or was encrypted with an old key.
		"""
		row = await self._db.fetchrow(
			"SELECT access_token, refresh_token, discord_expires_at, scopes FROM dashboard_sessions "
			"WHERE id = $1 AND expires_at > now()",
			session_id,
		)
		if row is None:
			return None
		try:
			return OAuthTokenSet(
				access_token=self._decrypt(row["access_token"]),
				refresh_token=self._decrypt(row["refresh_token"]),
				expires_at=row["discord_expires_at"],
				scopes=frozenset(row["scopes"]),
			)
		except InvalidToken:
			return None

	async def update_tokens(self, session_id: str, tokens: OAuthTokenSet) -> None:
		"""Replace a session's Discord tokens.

		Args:
			session_id: The session.
			tokens: The refreshed tokens.
		"""
		await self._db.execute(
			"UPDATE dashboard_sessions SET access_token = $2, refresh_token = $3, discord_expires_at = $4, scopes = $5 "
			"WHERE id = $1",
			session_id,
			self._encrypt(tokens.access_token),
			self._encrypt(tokens.refresh_token),
			tokens.expires_at,
			sorted(tokens.scopes),
		)

	async def revoke(self, session_id: str) -> None:
		"""End a session.

		Args:
			session_id: The session.
		"""
		await self._db.execute("DELETE FROM dashboard_sessions WHERE id = $1", session_id)

	def _encrypt(self, value: str) -> str:
		"""Encrypt a value with the session key.

		Args:
			value: The plaintext.

		Returns:
			The Fernet token.
		"""
		return self._fernet.encrypt(value.encode()).decode()

	def _decrypt(self, value: str) -> str:
		"""Decrypt a value with the session key.

		Args:
			value: The Fernet token.

		Returns:
			The plaintext.

		Raises:
			InvalidToken: The value wasn't encrypted with this key.
		"""
		return self._fernet.decrypt(value.encode()).decode()
