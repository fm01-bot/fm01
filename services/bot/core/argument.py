import inspect
import types
import typing
from dataclasses import dataclass, field
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from core import slash_localization

__all__ = ("Argument", "Choice")


@dataclass(slots=True)
class Choice:
	value: str
	label: str | None
	"""The localized choice name, or None when it says nothing beyond ``value``."""


@dataclass(slots=True)
class Argument:
	"""What a text command parameter accepts, as ``?!help <command>`` shows it.

	Attributes:
		minimum: The smallest value, or the shortest length when ``length`` is set.
		maximum: The largest value, or the longest length when ``length`` is set.
		length: Whether ``minimum`` and ``maximum`` bound a string's length rather than a number.
		greedy: Whether the parameter takes as many values as parse (``commands.Greedy``).
		rest: Whether the parameter takes the rest of the message (keyword-only).
	"""

	name: str
	description: str | None
	required: bool
	default: str | None = None
	choices: list[Choice] = field(default_factory=list)
	minimum: int | float | None = None
	maximum: int | float | None = None
	length: bool = False
	greedy: bool = False
	rest: bool = False

	@classmethod
	def from_param(cls, param: commands.Parameter, command: commands.Command, locale: str) -> "Argument":
		"""Describe ``param`` of ``command`` with its name and description localized for ``locale``.

		Choices come from a ``Literal`` annotation; their labels come from the slash command's
		``app_commands.choices`` when it has them.
		"""
		base = getattr(command, "l10n_key", None)
		name = description = None
		if base:
			name = slash_localization.lookup(slash_localization.command_key(base, "args", param.name, "name"), locale)
			description = slash_localization.lookup(
				slash_localization.command_key(base, "args", param.name, "desc"), locale
			)

		argument = cls(
			name=name or param.displayed_name or param.name,
			description=description or None,
			required=param.required,
			default=_displayed_default(param),
			rest=param.kind is inspect.Parameter.KEYWORD_ONLY,
		)
		argument._read_annotation(param.annotation)
		if argument.choices:
			labels = _choice_labels(command, param.name, locale)
			for choice in argument.choices:
				label = labels.get(choice.value)
				choice.label = label if label and label != choice.value else None
		return argument

	def _read_annotation(self, annotation: Any) -> None:
		annotation = _unwrap_optional(annotation)
		if isinstance(annotation, commands.Greedy):
			self.greedy = True
			annotation = _unwrap_optional(annotation.converter)

		if typing.get_origin(annotation) is typing.Literal:
			self.choices = [Choice(value=str(value), label=None) for value in typing.get_args(annotation)]
		# Range is typing.Annotated to type checkers; at runtime Range[...] returns an instance of this class.
		elif isinstance(annotation, commands.Range):  # ty:ignore[invalid-argument-type]
			self.minimum, self.maximum = annotation.min, annotation.max
			self.length = annotation.annotation is str
		elif isinstance(annotation, app_commands.transformers.RangeTransformer):
			self.minimum, self.maximum = annotation.min_value, annotation.max_value
			self.length = annotation.type is discord.AppCommandOptionType.string


def _unwrap_optional(annotation: Any) -> Any:
	"""Return the single non-None member of ``X | None``, or ``annotation`` unchanged."""
	if typing.get_origin(annotation) in (typing.Union, types.UnionType):
		members = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
		if len(members) == 1:
			return members[0]
	return annotation


def _displayed_default(param: commands.Parameter) -> str | None:
	"""The default worth showing: None when there is none, it is None, or it is computed (``commands.Author``)."""
	if param.required or param.default is None or isinstance(param.default, commands.Parameter):
		return None
	displayed = param.displayed_default
	return displayed if displayed else None


def _choice_labels(command: commands.Command, param_name: str, locale: str) -> dict[str, str]:
	"""Map each choice value of ``command``'s slash parameter ``param_name`` to its localized name."""
	app_params = getattr(getattr(command, "app_command", None), "_params", None)
	app_param = app_params.get(param_name) if isinstance(app_params, dict) else None
	if app_param is None:
		return {}
	labels: dict[str, str] = {}
	for choice in app_param.choices:
		labels[str(choice.value)] = slash_localization.lookup(choice.name, locale) or choice.name
	return labels
