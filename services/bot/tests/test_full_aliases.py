from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cogs.help import HelpCommand
from core.bot import Bot
from core.command import format_aliases
from core.config import Config
from core.hybrid import FullAliasCommand, group
from discord.ext import commands


class Cases(commands.Cog):
	def __init__(self) -> None:
		self.calls: list[str] = []

	@group(permissions=["administrator"], l10n_key="caseinfo", name="case", aliases=["caseinfo"])
	async def case(self, ctx, case_id: str):
		self.calls.append("group")

	@case.command(name="list", l10n_key="caselist", full_aliases=["cl", "cases"])
	@commands.cooldown(1, 60)
	async def list_cases(self, ctx):
		self.calls.append("list")


@pytest.fixture
def bot():
	cfg = Config(
		debug=False,
		owner_ids=[123],
		modules=["*"],
		emojis={},
		log_channel_id=999,
		allowed_contexts={"guild": True, "dm_channel": True, "private_channel": True},
		allowed_installs={"guild": True, "user": True},
		allowed_mentions={"everyone": False, "roles": False, "users": False},
	)
	with patch("core.bot.update_slash_localizations"):
		return Bot(config=cfg)


@pytest.mark.asyncio
async def test_full_aliases_run_the_subcommand_without_its_group(bot):
	cog = Cases()
	await bot.add_cog(cog)

	target = bot.get_command("case list")
	for name in ("cl", "cases"):
		alias = bot.get_command(name)
		assert isinstance(alias, FullAliasCommand)
		assert alias.target is target
		assert alias.parent is None
		assert alias.hidden
		assert alias.app_command is None
		assert alias.cog is cog

	await bot.get_command("cl")(MagicMock())
	assert cog.calls == ["list"]


@pytest.mark.asyncio
async def test_full_aliases_keep_group_checks_and_share_cooldowns(bot):
	await bot.add_cog(Cases())

	group_command = bot.get_command("case")
	target = bot.get_command("case list")
	alias = bot.get_command("cl")
	assert alias.checks == group_command.checks + target.checks
	assert alias._buckets is target._buckets


@pytest.mark.asyncio
async def test_full_aliases_are_text_only(bot):
	await bot.add_cog(Cases())

	assert bot.tree.get_command("cl") is None
	assert bot.tree.get_command("cases") is None


@pytest.mark.asyncio
async def test_removing_the_cog_removes_its_full_aliases(bot):
	await bot.add_cog(Cases())
	await bot.remove_cog("Cases")

	assert bot.get_command("cl") is None
	assert bot.get_command("cases") is None


@pytest.mark.asyncio
async def test_conflicting_full_alias_rolls_back_registration(bot):
	@commands.command(name="cases")
	async def cases(ctx):
		pass

	bot.add_command(cases)

	with pytest.raises(commands.CommandRegistrationError):
		await bot.add_cog(Cases())

	assert bot.get_command("case") is None
	assert bot.get_command("cl") is None
	assert bot.get_command("cases") is cases


@pytest.mark.asyncio
async def test_aliases_field_lists_full_aliases(bot):
	await bot.add_cog(Cases())

	assert format_aliases(bot.get_command("case list")) == "cl, cases, caselist"
	assert format_aliases(bot.get_command("case")) == "caseinfo"


@pytest.mark.asyncio
async def test_help_for_a_full_alias_describes_its_subcommand(bot):
	await bot.add_cog(Cases())
	help_command = HelpCommand()
	help_command.context = MagicMock()
	help_command.context.send = AsyncMock()
	help_command.get_command_obj = MagicMock(return_value="described")
	help_command.format_arguments = AsyncMock(return_value="arguments")

	await help_command.send_command_help(bot.get_command("cl"))

	help_command.get_command_obj.assert_called_once_with(bot.get_command("case list"))
	help_command.format_arguments.assert_awaited_once_with(bot.get_command("case list"))
	help_command.context.send.assert_awaited_once_with("help.command", command="described", arguments="arguments")


@pytest.mark.asyncio
async def test_group_aliases_resolve_to_the_group(bot):
	await bot.add_cog(Cases())

	assert bot.get_command("caseinfo") is bot.get_command("case")
	assert bot.get_command("caseinfo list") is bot.get_command("case list")
	assert bot.tree.get_command("caseinfo") is None
	assert format_aliases(bot.get_command("case")) == "caseinfo"


@pytest.mark.asyncio
async def test_subcommands_get_their_qualified_name_as_a_default_full_alias(bot):
	await bot.add_cog(Cases())

	alias = bot.get_command("caselist")
	assert isinstance(alias, FullAliasCommand)
	assert alias.target is bot.get_command("case list")
	assert alias.implicit
	assert not bot.get_command("cl").implicit


@pytest.mark.asyncio
async def test_default_full_alias_yields_to_an_existing_command(bot):
	@commands.command(name="caselist")
	async def caselist(ctx):
		pass

	bot.add_command(caselist)
	await bot.add_cog(Cases())

	assert bot.get_command("caselist") is caselist
	assert isinstance(bot.get_command("cl"), FullAliasCommand)


@pytest.mark.asyncio
async def test_a_later_command_evicts_a_default_full_alias(bot):
	await bot.add_cog(Cases())

	@commands.command(name="caselist")
	async def caselist(ctx):
		pass

	bot.add_command(caselist)
	assert bot.get_command("caselist") is caselist


@pytest.mark.asyncio
async def test_groups_with_a_fallback_get_a_name_plus_fallback_alias(bot):
	class Snapshots(commands.Cog):
		@group(name="snap", fallback="create")
		async def snap(self, ctx):
			pass

	await bot.add_cog(Snapshots())
	assert bot.get_command("snapcreate") is bot.get_command("snap")
