"""Discord IDs on the wire."""

from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer, WithJsonSchema

__all__ = ("Snowflake",)


def _parse(value: Any) -> int:
	"""Parse a snowflake from an ``int`` or a string of digits.

	Args:
		value: The raw value.

	Returns:
		The snowflake.

	Raises:
		ValueError: The value isn't a non-negative integer below 2**64.
	"""
	if isinstance(value, bool):
		raise ValueError("a snowflake is not a boolean")  # noqa: TRY004 - Pydantic reports only ValueError as invalid input
	if isinstance(value, int):
		parsed = value
	elif isinstance(value, str) and value.isdecimal() and value.isascii():
		parsed = int(value)
	else:
		raise ValueError("a snowflake is a non-negative integer or a string of digits")
	if not 0 <= parsed < 2**64:
		raise ValueError("a snowflake fits in 64 bits")
	return parsed


Snowflake = Annotated[
	int,
	BeforeValidator(_parse),
	PlainSerializer(str, return_type=str),
	WithJsonSchema({"type": "string", "pattern": "^[0-9]{1,20}$", "examples": ["1234567890123456789"]}),
]
"""A Discord ID: an ``int`` in Python, always a string in JSON (JavaScript numbers lose precision on them)."""
