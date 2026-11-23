"""AutoMod: the bot's message filters (phrases, links, invites, spam, mentions, line count)."""

from typing import Any

from pydantic import BaseModel

__all__ = ("AUTOMOD_SETTING", "AutoModConfig")

AUTOMOD_SETTING = "automod"
"""The setting key the bot registers and INVALIDATE_SETTING events name."""


class AutoModConfig(BaseModel):
	"""A guild's AutoMod configuration. Off with no settings if the guild never configured it."""

	enabled: bool = False
	settings: dict[str, Any] = {}
	"""Rules, bypasses and actions. The bot fills in defaults for missing parts, so the API stores it as given."""
