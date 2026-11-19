import re

__all__ = ("DISCORD_INVITE", "DISCORD_MESSAGE_URL", "DISCORD_TEMPLATE", "SNOWFLAKE", "TIME", "URL_REGEX")

DISCORD_INVITE = re.compile(
	r"(?:https?://)?(?:www\.)?(?:discord\.(?:gg|io|me|li)|discord(?:app)?\.com/invite)/[a-zA-Z0-9-]+"
)
DISCORD_TEMPLATE = re.compile(r"(?:https?://)?discord\.new/([a-zA-Z0-9]+)")
DISCORD_MESSAGE_URL = re.compile(
	r"(?:https?://)?(?:www\.)?discord(?:app)?\.com/channels/(\d{17,19})/(\d{17,19})/(\d{17,19})"
)
SNOWFLAKE = re.compile(r"(\d{15,20})/?$")
"""The trailing snowflake of a bare ID or a link, e.g. a message link."""
TIME = re.compile(
	r"(\d+)(years|year|yrs|yr|y|months|month|mos|mo|weeks|week|wks|wk|w|days|day|dys|dy|d|hours|hour|hrs|hr|h|minutes|mins|min|mns|mn|m|seconds|secs|sec|scs|sc|s)"
)
URL_REGEX = re.compile(
	# Bounded domain labels keep a message like "a.a.a.…" linear instead of quadratic in its length.
	r"(?:https?://[^\s<>\"]+|www\.[^\s<>\"]+|\b(?:[a-z0-9-]{1,63}\.){1,16}[a-z]{2,63}\b(?:/[^\s<>\"]*)?)",
	re.IGNORECASE,
)
