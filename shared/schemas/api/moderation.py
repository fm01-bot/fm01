"""Moderation cases and the guild's case retention."""

import datetime
from typing import Literal

from pydantic import BaseModel, Field

from api.snowflake import Snowflake

__all__ = (
	"RETENTION_SETTING",
	"CaseClosed",
	"CaseCreate",
	"CaseFilter",
	"CaseRecord",
	"CaseRetention",
	"CaseUpdate",
	"PendingCase",
	"Retention",
)

RETENTION_SETTING = "mod.retention"
"""The setting key the bot registers and INVALIDATE_SETTING events name."""

Retention = Literal["keep", "delete"]
"""What closing a case does: mark it inactive (``keep``) or remove it (``delete``)."""

CaseFilter = Literal["open", "active", "expired", "all"]
"""Which of a user's cases to list.

``open``: still in force (``active``), regardless of expiry. ``active``: open and not past expiry. ``expired``:
closed, or open but past expiry. ``all``: every case.
"""


class CaseRetention(BaseModel):
	"""A guild's case retention."""

	retention: Retention = "keep"


class CaseCreate(BaseModel):
	"""A new case."""

	case_id: Snowflake
	"""The ID of the message that triggered the case."""
	type: int = Field(ge=1, le=5)
	"""1 warn, 2 mute, 3 kick, 4 ban, 5 softban."""
	user_id: Snowflake
	moderator_id: Snowflake
	reason: str | None = None
	expires: datetime.datetime | None = None
	message: str | None = None
	active: bool = True
	created: datetime.datetime


class CaseRecord(CaseCreate):
	"""A stored case."""

	guild_id: Snowflake


class CaseUpdate(BaseModel):
	"""A case's new reason, expiry and message. Every field is written, ``None`` included."""

	reason: str | None = None
	expires: datetime.datetime | None = None
	message: str | None = None


class CaseClosed(BaseModel):
	"""What closing a case did, following the guild's retention."""

	outcome: Literal["deleted", "deactivated"]


class PendingCase(BaseModel):
	"""An open case that expires."""

	case_id: Snowflake
	guild_id: Snowflake
	expires: datetime.datetime
