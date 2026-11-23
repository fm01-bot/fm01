"""The media alert store."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import asyncpg
from api import MAX_ALERTS, AlertAccount, AlertBaseline, AlertCreate, ErrorCode, MediaAlert

from app.errors import ApiError

__all__ = ("AlertStore",)

_COLUMNS = (
	"id, guild_id, platform, channel_account, account_id, account_name, target_channel_id, is_enabled, "
	"last_media_id, last_media_time, created_at"
)


def _alert(row: Mapping[str, Any]) -> MediaAlert:
	"""Build an alert from a ``media_alerts`` row.

	Args:
		row: The row.

	Returns:
		The alert.
	"""
	return MediaAlert(
		id=row["id"],
		guild_id=int(row["guild_id"]),
		platform=row["platform"],
		channel_account=row["channel_account"],
		account_id=row["account_id"],
		account_name=row["account_name"],
		target_channel_id=int(row["target_channel_id"]),
		enabled=row["is_enabled"],
		last_media_id=row["last_media_id"],
		last_media_time=row["last_media_time"],
		created_at=row["created_at"],
	)


class AlertStore:
	"""Reads and writes guilds' media alerts.

	Args:
		db: The database pool.
	"""

	def __init__(self, db: asyncpg.Pool) -> None:
		self._db = db

	async def accounts(self) -> list[AlertAccount]:
		"""List the accounts that at least one enabled alert follows.

		Returns:
			Each account once.
		"""
		rows = await self._db.fetch(
			"SELECT DISTINCT platform, channel_account, account_id, account_name FROM media_alerts WHERE is_enabled"
		)
		return [AlertAccount(**dict(row)) for row in rows]

	async def subscribers(self, platform: str, channel_account: str, account_id: str) -> list[MediaAlert]:
		"""List the enabled alerts that follow an account.

		Args:
			platform: The platform.
			channel_account: Matches alerts with this ``channel_account``.
			account_id: Also matches alerts with this ``account_id``.

		Returns:
			The alerts.
		"""
		rows = await self._db.fetch(
			f"SELECT {_COLUMNS} FROM media_alerts WHERE is_enabled AND platform = $1 "
			"AND (channel_account = $2 OR account_id = $3) ORDER BY id",
			platform,
			channel_account,
			account_id,
		)
		return [_alert(row) for row in rows]

	async def for_guild(self, guild_id: int) -> list[MediaAlert]:
		"""List a guild's alerts.

		Args:
			guild_id: The guild.

		Returns:
			The alerts, oldest first.
		"""
		rows = await self._db.fetch(f"SELECT {_COLUMNS} FROM media_alerts WHERE guild_id = $1 ORDER BY id", guild_id)
		return [_alert(row) for row in rows]

	async def get(self, guild_id: int, alert_id: int) -> MediaAlert | None:
		"""Get an alert.

		Args:
			guild_id: The guild.
			alert_id: The alert.

		Returns:
			The alert, or ``None`` if the guild has no such alert.
		"""
		row = await self._db.fetchrow(
			f"SELECT {_COLUMNS} FROM media_alerts WHERE id = $1 AND guild_id = $2", alert_id, guild_id
		)
		return _alert(row) if row else None

	async def add(self, guild_id: int, alert: AlertCreate) -> MediaAlert:
		"""Add an alert, or enable it again and update its account if the guild has it.

		Args:
			guild_id: The guild.
			alert: The alert.

		Returns:
			The stored alert.

		Raises:
			ApiError: ``alert_limit`` if the guild has the most alerts it may.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			# Serialize additions per guild, so two at once can't both pass the limit.
			await conn.execute(
				"SELECT pg_advisory_xact_lock(hashtextextended('alerts:' || $1::text, 0))", str(guild_id)
			)
			if await conn.fetchval("SELECT count(*) FROM media_alerts WHERE guild_id = $1", guild_id) >= MAX_ALERTS:
				raise ApiError(ErrorCode.ALERT_LIMIT)
			row = await conn.fetchrow(
				"INSERT INTO media_alerts (guild_id, platform, channel_account, account_id, account_name, "
				"target_channel_id, is_enabled) VALUES ($1, $2, $3, $4, $5, $6, true) "
				"ON CONFLICT (guild_id, platform, channel_account, target_channel_id) DO UPDATE SET "
				"account_id = EXCLUDED.account_id, account_name = EXCLUDED.account_name, is_enabled = true "
				f"RETURNING {_COLUMNS}",
				guild_id,
				alert.platform.lower(),
				alert.channel_account,
				alert.account_id,
				alert.account_name,
				alert.target_channel_id,
			)
		assert row is not None
		return _alert(row)

	async def remove(self, guild_id: int, alert_id: int) -> bool:
		"""Remove an alert.

		Args:
			guild_id: The guild.
			alert_id: The alert.

		Returns:
			Whether the guild had such an alert.
		"""
		status = await self._db.execute("DELETE FROM media_alerts WHERE id = $1 AND guild_id = $2", alert_id, guild_id)
		return status != "DELETE 0"

	async def remove_account(self, guild_id: int, platform: str, account: str) -> int:
		"""Remove a guild's alerts that follow an account.

		Args:
			guild_id: The guild.
			platform: The platform.
			account: Matches the alerts' ``channel_account`` or ``account_id``, ignoring case.

		Returns:
			How many alerts were removed.
		"""
		status = await self._db.execute(
			"DELETE FROM media_alerts WHERE guild_id = $1 AND platform = $2 "
			"AND (lower(channel_account) = lower($3) OR lower(account_id) = lower($3))",
			guild_id,
			platform.lower(),
			account,
		)
		return int(status.split()[-1])

	async def set_enabled(self, guild_id: int, alert_id: int, enabled: bool) -> MediaAlert | None:
		"""Turn an alert on or off.

		Args:
			guild_id: The guild.
			alert_id: The alert.
			enabled: Whether it is on.

		Returns:
			The stored alert, or ``None`` if the guild has no such alert.
		"""
		row = await self._db.fetchrow(
			f"UPDATE media_alerts SET is_enabled = $3 WHERE id = $1 AND guild_id = $2 RETURNING {_COLUMNS}",
			alert_id,
			guild_id,
			enabled,
		)
		return _alert(row) if row else None

	async def set_last_media(self, alert_id: int, media_id: str) -> None:
		"""Record the newest upload an alert has seen.

		Args:
			alert_id: The alert.
			media_id: The upload.
		"""
		await self._db.execute(
			"UPDATE media_alerts SET last_media_id = $2, last_media_time = now() WHERE id = $1", alert_id, media_id
		)

	async def set_baseline(self, baseline: AlertBaseline) -> None:
		"""Set a baseline on every enabled alert on an account that has none yet.

		Args:
			baseline: The account and the media ID to record.
		"""
		await self._db.execute(
			"UPDATE media_alerts SET last_media_id = $1, last_media_time = now() WHERE is_enabled AND platform = $2 "
			"AND (channel_account = $3 OR account_id = $4) AND last_media_id IS NULL",
			baseline.media_id,
			baseline.platform,
			baseline.channel_account,
			baseline.account_id,
		)
