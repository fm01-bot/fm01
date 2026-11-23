"""Snapshot capture/storage, and how the Logging cog decides where (and whether) to send a log."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from cogs.log import LogConfig, Logging
from cogs.snapshot import Snapshot
from core.clustering import LocalEventBus
from core.settings import GuildSettings

from api import Snapshot as ApiSnapshot


def _role(role_id: int, name: str, position: int) -> MagicMock:
	role = MagicMock(spec=discord.Role)
	role.id, role.name, role.position = role_id, name, position
	role.permissions = discord.Permissions(8)
	role.color = discord.Color(0x123456)
	role.hoist = role.managed = False
	role.display_icon = None
	return role


def _text_channel(channel_id: int, name: str, overwrite_target: MagicMock) -> MagicMock:
	channel = MagicMock(spec=discord.TextChannel)
	channel.id, channel.name, channel.position = channel_id, name, 0
	channel.type = discord.ChannelType.text
	channel.category = None
	channel.slowmode_delay, channel.topic = 5, "hello"
	channel.permissions_synced, channel.default_auto_archive_duration = True, 1440
	channel.is_nsfw.return_value = False
	channel.overwrites = {overwrite_target: discord.PermissionOverwrite(send_messages=False)}
	return channel


def _snapshot_ctx() -> MagicMock:
	everyone = _role(1, "@everyone", 0)
	ctx = MagicMock()
	ctx.guild.id = 42
	ctx.guild.roles = [everyone, _role(2, "Mods", 1)]
	ctx.guild.channels = [_text_channel(10, "general", everyone)]
	ctx.author.id = 7
	return ctx


async def test_save_captures_roles_channels_and_overwrites():
	payload = await Snapshot.save(_snapshot_ctx())

	assert set(payload["roles"]) == {1, 2}
	assert payload["roles"][2] == {
		"perms": 8,
		"color": 0x123456,
		"hoist": False,
		"managable": False,
		"position": 1,
		"name": "Mods",
		"display_icon": None,
	}
	channel = payload["channels"][10]
	assert (channel["name"], channel["type"], channel["slowmode"], channel["topic"]) == ("general", "text", 5, "hello")
	allow, deny = discord.PermissionOverwrite(send_messages=False).pair()
	assert channel["overwrites"][1] == {"allow": allow.value, "deny": deny.value, "role": "@everyone"}


async def test_create_sends_the_payload_with_json_keys_and_returns_the_code():
	bot = MagicMock()
	bot.custom_response = AsyncMock(return_value="Server snapshot")
	code = "0b1c7d3e-8f00-4a6b-9c1d-2e3f4a5b6c7d"
	bot.api.snapshots.create = AsyncMock(
		side_effect=lambda guild_id, snapshot: ApiSnapshot(
			code=code, guild_id=guild_id, date=datetime.datetime.now(tz=datetime.UTC), **snapshot.model_dump()
		)
	)
	cog = Snapshot(bot)

	created = await cog.create_snapshot(_snapshot_ctx())

	assert str(created) == code
	assert bot.api.snapshots.create.await_args is not None
	guild_id, sent = bot.api.snapshots.create.await_args.args
	assert guild_id == 42
	assert (sent.name, sent.author_id) == ("Server snapshot", 7)
	assert sent.payload["roles"]["2"]["name"] == "Mods"  # role IDs become JSON object keys
	assert sent.payload["channels"]["10"]["overwrites"]["1"]["role"] == "@everyone"


async def test_get_returns_the_payload_or_none():
	bot = MagicMock()
	payload = {"roles": {}, "channels": {}}
	stored = ApiSnapshot(code="abc", guild_id=1, name="x", author_id=2, date=datetime.datetime.now(), payload=payload)
	bot.api.snapshots.get = AsyncMock(side_effect=lambda code: stored if code == "abc" else None)
	cog = Snapshot(bot)

	assert await cog.get_snapshot("abc") == payload
	assert await cog.get_snapshot("nope") is None


# --- Logging ---------------------------------------------------------------

GUILD = 5


@pytest.fixture
def log_cog() -> Logging:
	api = SimpleNamespace(log=SimpleNamespace(get=AsyncMock(return_value=None)))
	bot = SimpleNamespace(
		api=api,
		settings=GuildSettings(LocalEventBus()),
		message_logging_guilds=set(),
		custom_response=MagicMock(),
		session=None,
		user=None,
	)
	cog = Logging(cast(Any, bot))
	cog.custom_response = MagicMock()
	cog.custom_response.get_message = AsyncMock(return_value={"content": "logged"})
	return cog


def _guild(*channels: MagicMock) -> MagicMock:
	guild = MagicMock(spec=discord.Guild)
	guild.id = GUILD
	by_id = {c.id: c for c in channels}
	guild.get_channel_or_thread = MagicMock(side_effect=by_id.get)
	return guild


def _channel(channel_id: int) -> MagicMock:
	channel = MagicMock(spec=discord.TextChannel)
	channel.id = channel_id
	channel.send = AsyncMock()
	return channel


async def test_send_skips_guilds_without_logging_or_with_the_module_off(log_cog):
	default = _channel(1)
	guild = _guild(default)

	await log_cog._send(guild, "on_member_join", "log.on_member_join.join")  # no configuration at all
	log_cog.config.setting.remember(
		GUILD, LogConfig(GUILD, is_on=True, channel_id=1, modules=frozenset({"on_member_remove"}))
	)
	await log_cog._send(guild, "on_member_join", "log.on_member_join.join")

	default.send.assert_not_awaited()


async def test_send_uses_the_per_event_channel_over_the_default(log_cog):
	default, joins = _channel(1), _channel(2)
	log_cog.config.setting.remember(GUILD, LogConfig(GUILD, is_on=True, channel_id=1, channels={"on_member_join": 2}))

	await log_cog._send(_guild(default, joins), "on_member_join", "log.on_member_join.join")

	joins.send.assert_awaited_once_with(content="logged")
	default.send.assert_not_awaited()


async def test_on_member_join_logs_with_the_member(log_cog):
	default = _channel(1)
	log_cog.config.setting.remember(GUILD, LogConfig(GUILD, is_on=True, channel_id=1))
	member = MagicMock(spec=discord.Member)
	member.guild = _guild(default)

	await log_cog.on_member_join(member)

	key = log_cog.custom_response.get_message.call_args.args[0]
	assert key == "log.on_member_join.join"
	assert log_cog.custom_response.get_message.call_args.kwargs["member"] is member
	default.send.assert_awaited_once()
