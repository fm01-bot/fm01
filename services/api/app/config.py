"""Runtime configuration, read from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta

__all__ = ("Settings",)


def _required(name: str) -> str:
	"""Read an environment variable that must be set.

	Args:
		name: The variable's name.

	Returns:
		The value, stripped.

	Raises:
		RuntimeError: The variable is unset or empty.
	"""
	value = os.getenv(name, "").strip()
	if not value:
		raise RuntimeError(f"{name} must be set")
	return value


def _optional(name: str) -> str | None:
	"""Read an optional environment variable.

	Args:
		name: The variable's name.

	Returns:
		The value, stripped. ``None`` if unset or empty.
	"""
	return os.getenv(name, "").strip() or None


@dataclass(frozen=True, slots=True)
class Settings:
	"""Everything the API reads from the environment.

	Attributes:
		database_url: PostgreSQL DSN.
		redis_url: Redis URL, for the event bus and short-lived caches.
		internal_token: The secret the bot sends to the Internal API.
		discord_bot_token: Bot token, used to check whether the bot is in a guild.
		discord_client_id: OAuth2 application ID, for the dashboard sign-in. ``None`` disables signing in.
		discord_client_secret: OAuth2 client secret. Only the API holds it.
		session_key: Fernet key encrypting the Discord tokens stored with dashboard sessions.
		discord_api_url: Discord REST base URL.
		session_ttl: How long a dashboard session lasts.
		permission_ttl: How long a guild manager check is cached.
		status_sampler: Whether this process records status history. Only one API process may.
		status_sample_interval: How often status history is sampled.
	"""

	database_url: str
	redis_url: str
	internal_token: str
	discord_bot_token: str
	discord_client_id: str | None = None
	discord_client_secret: str | None = None
	session_key: str | None = None
	discord_api_url: str = "https://discord.com/api/v10"
	session_ttl: timedelta = field(default=timedelta(days=30))
	permission_ttl: timedelta = field(default=timedelta(seconds=60))
	status_sampler: bool = True
	status_sample_interval: timedelta = field(default=timedelta(seconds=30))

	@property
	def dashboard_enabled(self) -> bool:
		"""Whether dashboard sign-in is configured (OAuth2 client ID, client secret and session key)."""
		return bool(self.discord_client_id and self.discord_client_secret and self.session_key)

	@classmethod
	def from_env(cls) -> Settings:
		"""Read the configuration from the environment.

		Returns:
			The configuration. The database DSN is ``DATABASE_URL``, or built from the ``DB_*`` variables.

		Raises:
			RuntimeError: A required variable isn't set.
		"""
		database_url = os.getenv("DATABASE_URL") or (
			f"postgresql://{_required('DB_USER')}:{_required('DB_PASSWORD')}"
			f"@{_required('DB_HOST')}:{os.getenv('DB_PORT', '5432')}/{_required('DB_NAME')}"
		)
		return cls(
			database_url=database_url,
			redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
			internal_token=_required("API_INTERNAL_TOKEN"),
			discord_bot_token=_required("TOKEN"),
			discord_client_id=_optional("DISCORD_CLIENT_ID"),
			discord_client_secret=_optional("DISCORD_CLIENT_SECRET"),
			session_key=_optional("SESSION_ENCRYPTION_KEY"),
			discord_api_url=os.getenv("DISCORD_API_URL", "https://discord.com/api/v10").rstrip("/"),
		)
