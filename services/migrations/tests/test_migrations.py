"""Tests for the migration chain itself: one head, complete revisions, and a clean upgrade/downgrade round trip."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def script() -> ScriptDirectory:
	config = Config(str(MIGRATIONS_DIR / "alembic.ini"))
	config.set_main_option("script_location", str(MIGRATIONS_DIR / "migrations"))
	return ScriptDirectory.from_config(config)


def test_chain_has_a_single_head(script: ScriptDirectory) -> None:
	assert len(script.get_heads()) == 1


def test_every_revision_defines_upgrade_and_downgrade(script: ScriptDirectory) -> None:
	for revision in script.walk_revisions():
		module = revision.module
		assert callable(getattr(module, "upgrade", None)), f"{revision.revision} has no upgrade()"
		assert callable(getattr(module, "downgrade", None)), f"{revision.revision} has no downgrade()"


def test_upgrade_reaches_head(
	script: ScriptDirectory, alembic: Callable[..., object], query: Callable[[str], list[tuple]]
) -> None:
	alembic("upgrade", "head")

	(version,) = query("SELECT version_num FROM alembic_version")[0]
	assert version == script.get_current_head()


def test_downgrade_to_base_removes_all_schema_and_upgrade_restores_it(
	script: ScriptDirectory, alembic: Callable[..., object], query: Callable[[str], list[tuple]]
) -> None:
	alembic("upgrade", "head")
	alembic("downgrade", "base")

	leftover = query("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'")
	assert leftover == []

	alembic("upgrade", "head")
	(version,) = query("SELECT version_num FROM alembic_version")[0]
	assert version == script.get_current_head()
