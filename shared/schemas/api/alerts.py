"""Media alerts: posts in a guild channel when a followed account uploads or goes live."""

import datetime

from pydantic import BaseModel, Field

from api.snowflake import Snowflake

__all__ = (
	"MAX_ALERTS",
	"AlertAccount",
	"AlertBaseline",
	"AlertCreate",
	"AlertEnabled",
	"AlertMedia",
	"MediaAlert",
	"RemovedAlerts",
)

MAX_ALERTS = 5
"""The most alerts one guild may have."""


class AlertAccount(BaseModel):
	"""An account on a platform that at least one enabled alert follows."""

	platform: str
	channel_account: str
	"""The account as the guild entered it (a handle, a URL or an ID)."""
	account_id: str | None = None
	"""The platform's ID for the account, if the bot resolved one."""
	account_name: str | None = None


class AlertCreate(AlertAccount):
	"""An alert to add. Adding one that exists again enables it and updates the account."""

	platform: str = Field(min_length=1, max_length=32)
	channel_account: str = Field(min_length=1, max_length=256)
	target_channel_id: Snowflake


class MediaAlert(AlertAccount):
	"""A stored alert."""

	id: int
	guild_id: Snowflake
	target_channel_id: Snowflake
	enabled: bool = True
	last_media_id: str | None = None
	"""The newest upload the alert has seen. ``None`` until the bot set a baseline."""
	last_media_time: datetime.datetime | None = None
	created_at: datetime.datetime


class AlertEnabled(BaseModel):
	"""Whether an alert is on."""

	enabled: bool


class AlertMedia(BaseModel):
	"""The newest upload an alert has seen."""

	media_id: str


class AlertBaseline(BaseModel):
	"""A baseline for every enabled alert on an account that has none yet, so older uploads aren't announced."""

	platform: str
	channel_account: str
	account_id: str
	"""Alerts match if either their ``channel_account`` or their ``account_id`` matches."""
	media_id: str


class RemovedAlerts(BaseModel):
	"""How many alerts a removal deleted."""

	removed: int
