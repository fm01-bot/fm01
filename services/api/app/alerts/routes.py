"""Media alert routes for the Internal API."""

from __future__ import annotations

from typing import Annotated

from api import (
	AlertAccount,
	AlertBaseline,
	AlertCreate,
	AlertEnabled,
	AlertMedia,
	ErrorCode,
	MediaAlert,
	RemovedAlerts,
	Snowflake,
)
from fastapi import APIRouter, Query, Response

from app.auth import State
from app.errors import ApiError

__all__ = ("internal",)

internal = APIRouter(tags=["alerts"])


@internal.get("/alerts/accounts")
async def internal_alert_accounts(state: State) -> list[AlertAccount]:
	"""List the accounts that at least one enabled alert follows, each once.

	\f
	Args:
		state: The app state.

	Returns:
		The accounts.
	"""
	return await state.alerts.accounts()


@internal.get("/alerts/subscribers")
async def internal_alert_subscribers(
	platform: Annotated[str, Query()],
	channel_account: Annotated[str, Query()],
	account_id: Annotated[str, Query()],
	state: State,
) -> list[MediaAlert]:
	"""List the enabled alerts that follow an account, by its `channel_account` or its `account_id`.

	\f
	Args:
		platform: The platform.
		channel_account: Matches alerts with this ``channel_account``.
		account_id: Also matches alerts with this ``account_id``.
		state: The app state.

	Returns:
		The alerts.
	"""
	return await state.alerts.subscribers(platform, channel_account, account_id)


@internal.post("/alerts/baseline", status_code=204)
async def internal_alert_baseline(body: AlertBaseline, state: State) -> Response:
	"""Set a baseline on every enabled alert on an account that has none yet.

	\f
	Args:
		body: The account and the media ID to record.
		state: The app state.

	Returns:
		An empty response.
	"""
	await state.alerts.set_baseline(body)
	return Response(status_code=204)


@internal.put("/alerts/{alert_id}/last-media", status_code=204)
async def internal_alert_last_media(alert_id: int, body: AlertMedia, state: State) -> Response:
	"""Record the newest upload an alert has seen.

	\f
	Args:
		alert_id: The alert.
		body: The upload.
		state: The app state.

	Returns:
		An empty response.
	"""
	await state.alerts.set_last_media(alert_id, body.media_id)
	return Response(status_code=204)


@internal.get("/guilds/{guild_id}/alerts")
async def internal_guild_alerts(guild_id: Snowflake, state: State) -> list[MediaAlert]:
	"""List a guild's alerts, oldest first.

	\f
	Args:
		guild_id: The guild.
		state: The app state.

	Returns:
		The alerts.
	"""
	return await state.alerts.for_guild(guild_id)


@internal.post("/guilds/{guild_id}/alerts", status_code=201)
async def internal_add_alert(guild_id: Snowflake, body: AlertCreate, state: State) -> MediaAlert:
	"""Add an alert, or enable it again and update its account if the guild has it.

	\f
	Args:
		guild_id: The guild.
		body: The alert.
		state: The app state.

	Returns:
		The stored alert.
	"""
	return await state.alerts.add(guild_id, body)


@internal.delete("/guilds/{guild_id}/alerts")
async def internal_remove_account_alerts(
	guild_id: Snowflake,
	platform: Annotated[str, Query()],
	account: Annotated[str, Query()],
	state: State,
) -> RemovedAlerts:
	"""Remove a guild's alerts that follow an account, by `channel_account` or `account_id`, ignoring case.

	\f
	Args:
		guild_id: The guild.
		platform: The platform.
		account: The account.
		state: The app state.

	Returns:
		How many alerts were removed.
	"""
	return RemovedAlerts(removed=await state.alerts.remove_account(guild_id, platform, account))


@internal.get("/guilds/{guild_id}/alerts/{alert_id}")
async def internal_alert(guild_id: Snowflake, alert_id: int, state: State) -> MediaAlert:
	"""Get an alert.

	\f
	Args:
		guild_id: The guild.
		alert_id: The alert.
		state: The app state.

	Returns:
		The alert.

	Raises:
		ApiError: ``not_found`` if the guild has no such alert.
	"""
	alert = await state.alerts.get(guild_id, alert_id)
	if alert is None:
		raise ApiError(ErrorCode.NOT_FOUND, "no such alert")
	return alert


@internal.delete("/guilds/{guild_id}/alerts/{alert_id}", status_code=204)
async def internal_remove_alert(guild_id: Snowflake, alert_id: int, state: State) -> Response:
	"""Remove an alert.

	\f
	Args:
		guild_id: The guild.
		alert_id: The alert.
		state: The app state.

	Returns:
		An empty response.

	Raises:
		ApiError: ``not_found`` if the guild has no such alert.
	"""
	if not await state.alerts.remove(guild_id, alert_id):
		raise ApiError(ErrorCode.NOT_FOUND, "no such alert")
	return Response(status_code=204)


@internal.put("/guilds/{guild_id}/alerts/{alert_id}/enabled")
async def internal_set_alert_enabled(
	guild_id: Snowflake, alert_id: int, body: AlertEnabled, state: State
) -> MediaAlert:
	"""Turn an alert on or off.

	\f
	Args:
		guild_id: The guild.
		alert_id: The alert.
		body: Whether it is on.
		state: The app state.

	Returns:
		The stored alert.

	Raises:
		ApiError: ``not_found`` if the guild has no such alert.
	"""
	alert = await state.alerts.set_enabled(guild_id, alert_id, body.enabled)
	if alert is None:
		raise ApiError(ErrorCode.NOT_FOUND, "no such alert")
	return alert
