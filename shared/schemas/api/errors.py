"""The error body every API failure returns."""

from enum import StrEnum

from pydantic import BaseModel

__all__ = ("ErrorBody", "ErrorCode")


class ErrorCode(StrEnum):
	"""Why a request failed. Clients branch on this, never on the message."""

	INVALID_REQUEST = "invalid_request"
	UNAUTHORIZED = "unauthorized"
	"""No credentials, or credentials that are wrong or expired."""
	FORBIDDEN = "forbidden"
	"""Valid credentials that don't allow this, e.g. a signed-in user who isn't a guild manager."""
	NOT_FOUND = "not_found"
	INSUFFICIENT_FUNDS = "insufficient_funds"
	"""The wallet doesn't hold enough money for the Ledger operation."""
	SAME_ACCOUNT = "same_account"
	"""A Ledger transfer from a member to themselves."""
	INVALID_CHANNEL = "invalid_channel"
	"""The channel doesn't exist in the guild or isn't the kind of channel the setting needs."""
	INVALID_EMOJI = "invalid_emoji"
	"""The emoji isn't a unicode emoji or a custom emoji of the guild."""
	STARBOARD_LIMIT = "starboard_limit"
	"""The guild already has the most boards it may have."""
	STARBOARD_NAME_TAKEN = "starboard_name_taken"
	"""Another board in the guild has that name."""
	STARBOARD_TIER_TAKEN = "starboard_tier_taken"
	"""Another board in the guild has that emoji and threshold."""
	RATE_LIMITED = "rate_limited"
	"""Too many requests from the caller's IP. ``Retry-After`` says when to try again."""
	DISCORD_UNAVAILABLE = "discord_unavailable"
	"""Discord's API failed or rate limited a request the API made on the caller's behalf."""


class ErrorBody(BaseModel):
	"""What the API returns when a request fails."""

	code: ErrorCode
	message: str
	"""A human-readable detail, for logs. Not localized and not stable."""
