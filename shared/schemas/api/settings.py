"""Guild settings."""

from typing import Annotated

from pydantic import BaseModel, Field

from api.snowflake import Snowflake

__all__ = (
	"LOCALE_SETTING",
	"PREFIX_SETTING",
	"GuildLocale",
	"GuildPrefix",
	"LocaleCode",
	"LocaleOverride",
	"Prefix",
	"PrefixText",
)

# Setting keys, as the bot registers them on its GuildSettings and as INVALIDATE_SETTING events name them.
PREFIX_SETTING = "prefix"
LOCALE_SETTING = "locale"

PrefixText = Annotated[str, Field(min_length=1, max_length=10)]
"""A command prefix, 1 to 10 characters."""
LocaleCode = Annotated[str, Field(pattern="^[a-z]{2}$")]
"""A two-letter language code. Regional variants share one (``en-US`` and ``en-GB`` are both ``en``)."""


class Prefix(BaseModel):
	"""A guild's command prefix and whether mentioning the bot also works as a prefix."""

	prefix: PrefixText = "?!"
	mention: bool = True


class GuildPrefix(Prefix):
	"""A guild's prefix, with the guild's ID."""

	guild_id: Snowflake


class LocaleOverride(BaseModel):
	"""A guild's chosen bot language. ``None`` means it follows the members' and the guild's Discord locales."""

	locale: LocaleCode | None = None


class GuildLocale(LocaleOverride):
	"""A guild's locale override, with the guild's ID."""

	guild_id: Snowflake
