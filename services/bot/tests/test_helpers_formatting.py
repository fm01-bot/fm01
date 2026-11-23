from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import discord
import pytest
from helpers.formatting import MAX_SPEC_NUMBER, SafeFormatter, StrictFormatter


def _bot() -> MagicMock:
	bot = MagicMock(spec=discord.Client)
	bot.http = SimpleNamespace(token="secret-token")
	return bot


def test_public_fields_and_small_specs_format():
	member = SimpleNamespace(name="alice", id=7)
	assert SafeFormatter().format("{member.name} {member.id:>3}", member=member) == "alice   7"


@pytest.mark.parametrize(
	"template",
	["{member._secret}", "{member[_secret]}", "{_secret}", "{member.inner._secret}"],
)
def test_private_names_stay_as_typed(template: str):
	member = SimpleNamespace(_secret="secret-token", inner=SimpleNamespace(_secret="secret-token"))
	assert SafeFormatter().format(template, member=member, _secret="secret-token") == template


def test_paths_through_a_client_are_refused():
	case = SimpleNamespace(bot=_bot())
	assert SafeFormatter().format("{case.bot.http.token}", case=case) == "{case.bot.http.token}"
	with pytest.raises(KeyError):
		StrictFormatter().format("{case.bot.http.token}", case=case)


@pytest.mark.parametrize("spec", [f">{MAX_SPEC_NUMBER + 1}", "0>2000000000", ".999999", ">{width}"])
def test_large_format_specs_are_ignored(spec: str):
	result = SafeFormatter().format(f"{{member.id:{spec}}}", member=SimpleNamespace(id=7), width=10**9)
	assert result == "7"


def test_bad_index_stays_as_typed():
	assert SafeFormatter().format("{member[0]}", member=SimpleNamespace()) == "{member[0]}"


def test_unknown_fields_with_a_path_stay_as_typed():
	assert SafeFormatter().format("Welcome {nickname[0]}") == "Welcome {nickname[0]}"
	assert SafeFormatter().format("{nickname.upper}") == "{nickname.upper}"


def test_strict_formatter_raises_on_missing_fields():
	with pytest.raises(KeyError):
		StrictFormatter().format("{missing}")
