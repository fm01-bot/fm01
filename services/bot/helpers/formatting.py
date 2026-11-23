"""``str.format`` for message templates, which guild admins write (join and leave messages) or will write (dashboard).

Plain ``str.format`` follows any attribute or index path and honours any padding, so a template could read the bot's
token (``{x.bot.http.token}``) or allocate gigabytes (``{member.id:>2000000000}``). These formatters refuse private
names and paths through the bot's clients, and ignore format specs with numbers above `MAX_SPEC_NUMBER`.
"""

from __future__ import annotations

import re
import string
from collections.abc import Mapping, Sequence
from typing import Any

import aiohttp
import discord
import discord.gateway
import discord.http
from discord.ext import localization

__all__ = ("MAX_SPEC_NUMBER", "SafeFormatter", "StrictFormatter")

MAX_SPEC_NUMBER = 256
"""The largest width or precision a format spec may ask for."""

_PRIVATE = re.compile(r"(?:^|[.\[])_")
_SPEC_NUMBER = re.compile(r"\d+")
_FIRST = re.compile(r"[.\[]")
_FIELD_PART = re.compile(r"\.([^.\[]+)|\[([^\]]+)\]")
_OPAQUE: tuple[type, ...] = (
	discord.Client,
	discord.VoiceProtocol,
	discord.http.HTTPClient,
	discord.gateway.DiscordWebSocket,
	aiohttp.ClientSession,
)
"""Objects a template may print but never look inside: every path to a secret goes through one of them."""


class RefusedFieldError(LookupError):
	"""A template asked for a private name or a path through a client."""


def _split(field_name: str) -> tuple[str | int, list[tuple[bool, str | int]]]:
	"""Split a field name like ``string.Formatter`` does: ``a.b[0]`` is ``a``, then attribute ``b``, then index ``0``.

	Args:
		field_name: The field name.

	Returns:
		The first name (an ``int`` if it is digits: a positional argument), and each following
		``(is_attribute, key)``. Digit index keys are ``int``.

	Raises:
		ValueError: The field name is malformed.
	"""
	first = _FIRST.split(field_name, maxsplit=1)[0]
	rest = field_name[len(first) :]
	parts: list[tuple[bool, str | int]] = []
	position = 0
	for match in _FIELD_PART.finditer(rest):
		if match.start() != position:
			raise ValueError(field_name)
		attribute, index = match.groups()
		parts.append((True, attribute) if attribute is not None else (False, int(index) if index.isdigit() else index))
		position = match.end()
	if position != len(rest):
		raise ValueError(field_name)
	return int(first) if first.isdigit() else first, parts


def _bounded(format_spec: str) -> str:
	"""Drop a format spec that asks for more than `MAX_SPEC_NUMBER` characters of width or precision.

	Args:
		format_spec: The spec after the ``:``.

	Returns:
		The spec, or ``""`` if it is too large.
	"""
	return "" if any(int(n) > MAX_SPEC_NUMBER for n in _SPEC_NUMBER.findall(format_spec)) else format_spec


class _Guarded(string.Formatter):
	def _resolve(self, field_name: str, args: Sequence[Any], kwargs: Mapping[str, Any]) -> tuple[Any, Any]:
		"""Look up a field like ``string.Formatter.get_field``, refusing private names and paths through clients.

		Raises:
			RefusedFieldError: The field is private or passes through a client.
		"""
		if _PRIVATE.search(field_name):
			raise RefusedFieldError(field_name)
		first, rest = _split(field_name)
		obj = self.get_value(first, args, kwargs)
		for is_attr, key in rest:
			if isinstance(obj, _OPAQUE):
				raise RefusedFieldError(field_name)
			obj = getattr(obj, str(key)) if is_attr else obj[key]
		return obj, first

	def format_field(self, value: Any, format_spec: str) -> Any:
		return super().format_field(value, _bounded(format_spec))


class SafeFormatter(_Guarded, localization.CustomFormatter):
	"""Formats templates, leaving unknown, private and refused fields as typed (``{field}``)."""

	def get_field(self, field_name: str, args: Sequence[Any], kwargs: Mapping[str, Any]) -> tuple[Any, Any]:
		try:
			return self._resolve(field_name, args, kwargs)
		except (LookupError, AttributeError, TypeError, ValueError):
			return f"{{{field_name}}}", field_name


class StrictFormatter(_Guarded):
	"""Formats templates like ``str.format`` (missing fields raise ``KeyError``), refusing the same fields."""

	def get_field(self, field_name: str, args: Sequence[Any], kwargs: Mapping[str, Any]) -> tuple[Any, Any]:
		try:
			return self._resolve(field_name, args, kwargs)
		except RefusedFieldError as exc:
			raise KeyError(field_name) from exc
