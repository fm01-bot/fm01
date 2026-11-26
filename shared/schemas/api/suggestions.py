"""Suggestions: members propose ideas in a channel and the server votes on them."""

from enum import StrEnum

from pydantic import BaseModel, Field

from api.snowflake import Snowflake

__all__ = (
	"MAX_SUGGESTION_LENGTH",
	"MAX_SUGGESTION_REASON_LENGTH",
	"SUGGESTIONS_SETTING",
	"CastVote",
	"Decide",
	"DecisionStatus",
	"NewSuggestion",
	"Suggestion",
	"SuggestionConfig",
	"SuggestionDecision",
	"SuggestionMessage",
	"Vote",
	"VoteResult",
)

SUGGESTIONS_SETTING = "suggestions"
"""The setting key the bot registers and INVALIDATE_SETTING events name."""

MAX_SUGGESTION_LENGTH = 1000
"""The most characters a suggestion may have."""

MAX_SUGGESTION_REASON_LENGTH = 500
"""The most characters a decision's reason may have."""


class Vote(StrEnum):
	"""A member's opinion on a suggestion."""

	UP = "up"
	DOWN = "down"


class DecisionStatus(StrEnum):
	"""What a moderator decided about a suggestion."""

	APPROVED = "approved"
	DENIED = "denied"


class SuggestionConfig(BaseModel):
	"""A guild's suggestions setting. Without a channel, suggestions are off."""

	channel_id: Snowflake | None = None
	threads: bool = False
	"""Whether the bot opens a thread under each suggestion for discussion."""


class SuggestionDecision(BaseModel):
	"""A moderator's decision on a suggestion."""

	status: DecisionStatus
	moderator_id: Snowflake
	reason: str | None = None


class Suggestion(BaseModel):
	"""A suggestion with its vote counts. It is open until it has a decision."""

	number: int
	"""The suggestion's number in its guild, counting from 1."""
	author_id: Snowflake
	content: str
	channel_id: Snowflake | None = None
	"""Where the bot posted the suggestion. ``None`` until it records the message."""
	message_id: Snowflake | None = None
	up: int
	down: int
	decision: SuggestionDecision | None = None


class NewSuggestion(BaseModel):
	"""A suggestion to create."""

	author_id: Snowflake
	content: str = Field(min_length=1, max_length=MAX_SUGGESTION_LENGTH)


class SuggestionMessage(BaseModel):
	"""The message the bot posted for a suggestion."""

	channel_id: Snowflake
	message_id: Snowflake


class CastVote(BaseModel):
	"""A member's vote. Casting the same vote again takes it back; the opposite vote replaces it."""

	user_id: Snowflake
	vote: Vote


class VoteResult(BaseModel):
	"""A suggestion's counts after a vote."""

	up: int
	down: int
	vote: Vote | None = None
	"""The voter's vote after the call. ``None`` if they took it back."""


class Decide(BaseModel):
	"""A moderator's decision to record. Deciding again overwrites the earlier decision."""

	moderator_id: Snowflake
	status: DecisionStatus
	reason: str | None = Field(default=None, max_length=MAX_SUGGESTION_REASON_LENGTH)
