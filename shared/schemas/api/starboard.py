"""Starboards: channels that repost messages once enough members react with an emoji."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from api.snowflake import Snowflake

__all__ = (
	"MAX_STARBOARDS",
	"STARBOARD_SETTING",
	"ChannelMode",
	"ClearStars",
	"GuildStarboards",
	"MessageIds",
	"StarChange",
	"StarResult",
	"StarSeed",
	"Starboard",
	"StarboardBlock",
	"StarboardConfig",
	"StarboardEmoji",
	"StarboardEntry",
	"StarboardName",
	"StarboardPost",
	"StarboardUpdate",
	"StarredMessage",
)

STARBOARD_SETTING = "starboard"
"""The setting key the bot registers and INVALIDATE_SETTING events name. Covers every board of a guild."""

MAX_STARBOARDS = 5
"""How many boards a guild may have."""

StarboardName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,32}$")]
"""A board's name, unique in its guild: lowercase letters, digits, ``-`` and ``_``, up to 32 characters."""

StarboardEmoji = Annotated[str, StringConstraints(pattern=r"^(\d{15,21}|[0-9#*]️?⃣|[^\x00-\x7F]{1,16})$")]
"""A unicode emoji, or a custom emoji's ID (a snowflake as a string)."""

ChannelMode = Literal["blocklist", "allowlist"]
"""``blocklist``: watch every channel except ``channel_ids``. ``allowlist``: watch only ``channel_ids``."""

Threshold = Annotated[int, Field(ge=1, le=100)]
MaxAgeDays = Annotated[int, Field(ge=1, le=3650)]
ChannelIds = Annotated[list[Snowflake], Field(max_length=100)]
MessageIdList = Annotated[list[Snowflake], Field(max_length=100)]


class StarboardConfig(BaseModel):
	"""How a board behaves. Board channels and NSFW channels are never watched, whatever the channel filter says."""

	channel_id: Snowflake
	"""The channel starred messages are posted in."""
	emoji: StarboardEmoji = "⭐"
	threshold: Threshold = 3
	"""How many members must star a message. Boards sharing an emoji (tiers) need different thresholds."""
	enabled: bool = True
	"""Off boards keep their posts and entries. The bot turns a board off when it can't post or its emoji is gone."""
	channel_mode: ChannelMode = "blocklist"
	channel_ids: ChannelIds = []
	"""The channels ``channel_mode`` lists. A thread follows its parent channel."""
	max_age_days: MaxAgeDays | None = None
	"""Messages older than this are not posted. ``None`` means no limit."""


class Starboard(StarboardConfig):
	"""A board."""

	name: StarboardName


class StarboardUpdate(BaseModel):
	"""Changes to a board. Fields left out keep their value; ``max_age_days: null`` removes the limit."""

	name: StarboardName | None = None
	channel_id: Snowflake | None = None
	emoji: StarboardEmoji | None = None
	threshold: Threshold | None = None
	enabled: bool | None = None
	channel_mode: ChannelMode | None = None
	channel_ids: ChannelIds | None = None
	max_age_days: MaxAgeDays | None = None


class GuildStarboards(BaseModel):
	"""Every board of a guild."""

	guild_id: Snowflake
	boards: list[Starboard]


class StarboardEntry(BaseModel):
	"""A message on one board: its post there, if any, and whether a moderator blocked it."""

	board: StarboardName
	message_id: Snowflake
	"""The original message."""
	post_channel_id: Snowflake | None = None
	post_id: Snowflake | None = None
	blocked: bool = False
	"""Set when someone other than the bot deleted the post. A blocked message is never posted on the board again."""


class StarboardBlock(BaseModel):
	"""A message blocked from a board."""

	message_id: Snowflake


class StarChange(BaseModel):
	"""A member added or removed a star. ``message_id`` may be the original or one of its posts."""

	message_id: Snowflake
	emoji: StarboardEmoji
	user_id: Snowflake
	starred: bool
	"""``True`` for a reaction added, ``False`` for one removed."""


class StarSeed(BaseModel):
	"""Everyone who starred a message with an emoji, read from Discord the first time the API sees the message."""

	message_id: Snowflake
	channel_id: Snowflake
	author_id: Snowflake
	emoji: StarboardEmoji
	user_ids: Annotated[list[Snowflake], Field(max_length=10_000)]


class StarredMessage(BaseModel):
	"""A message's stars with one emoji, and its entries on the boards that use the emoji."""

	message_id: Snowflake
	"""The original message."""
	channel_id: Snowflake
	author_id: Snowflake
	emoji: StarboardEmoji
	count: int
	"""Unique members who starred the original or any of its posts, the author excluded."""
	entries: list[StarboardEntry]
	"""Only boards the message has an entry on. A board without one has no post and no block."""


class StarResult(BaseModel):
	"""The outcome of a star change. ``message`` is ``None`` when the API has never seen the message: the bot then
	seeds it (an original) or ignores the change (a message in a board channel that isn't a post)."""

	message: StarredMessage | None = None


class StarboardPost(BaseModel):
	"""The post the bot made for a message on a board. ``None`` fields record that it removed the post."""

	board: StarboardName
	message_id: Snowflake
	post_channel_id: Snowflake | None = None
	post_id: Snowflake | None = None


class MessageIds(BaseModel):
	"""Messages that were deleted."""

	message_ids: MessageIdList


class ClearStars(BaseModel):
	"""Reactions removed from a message all at once. ``emoji: null`` means every emoji."""

	emoji: StarboardEmoji | None = None
