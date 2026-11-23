"""GuildSettings: caching and cross-instance invalidation, with a shared in-process event bus.

Settings run against `FakeApi`, which behaves like the Internal API: it persists writes and announces them itself,
echoing the writer's origin.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from core.clustering import LocalEventBus
from core.settings import EVENTS_CHANNEL, GuildSetting, GuildSettings, Prefix

GUILD = 42


class FakeApi:
	"""Remote setting storage shared by every instance, announcing each write on the bus like the API does."""

	def __init__(self, bus: LocalEventBus) -> None:
		self.bus = bus
		self.values: dict[str, dict[int, Any]] = {"prefix": {}, "locale": {}, "mod.retention": {}}
		self.defaults: dict[str, Any] = {"prefix": ("?!", True), "locale": None, "mod.retention": "keep"}
		self.loads = 0

	async def write(self, key: str, guild_id: int, value: Any, origin: str | None) -> None:
		self.values[key][guild_id] = value
		await self.bus.publish(
			EVENTS_CHANNEL, {"type": "INVALIDATE_SETTING", "key": key, "guild_id": str(guild_id), "origin": origin}
		)

	def remote(self, settings: GuildSettings, key: str, *, preloaded: bool = True) -> GuildSetting[Any]:
		async def load(guild_id: int) -> Any:
			self.loads += 1
			return self.values[key].get(guild_id, self.defaults[key])

		async def save(guild_id: int, value: Any) -> None:
			await self.write(key, guild_id, value, settings.origin)

		async def load_all() -> dict[int, Any]:
			return dict(self.values[key])

		return settings.add_remote(key, load, save, load_all=load_all if preloaded else None)


class Instance:
	"""One bot process: its own caches, sharing the API and the event bus with the others."""

	def __init__(self, bus: LocalEventBus, api: FakeApi) -> None:
		self.settings = GuildSettings(bus)
		self.prefix: GuildSetting[Prefix] = api.remote(self.settings, "prefix")
		self.locale: GuildSetting[str | None] = api.remote(self.settings, "locale")
		self.retention: GuildSetting[str] = api.remote(self.settings, "mod.retention", preloaded=False)


async def settle() -> None:
	"""Let LocalEventBus deliver (it dispatches in tasks) and the handlers finish their queries."""
	for _ in range(20):
		await asyncio.sleep(0.01)


@pytest.fixture
def bus() -> LocalEventBus:
	return LocalEventBus()


@pytest.fixture
def api(bus: LocalEventBus) -> FakeApi:
	return FakeApi(bus)


@pytest.fixture
async def instances(bus: LocalEventBus, api: FakeApi) -> tuple[Instance, Instance]:
	a, b = Instance(bus, api), Instance(bus, api)
	for instance in (a, b):

		async def handler(event: dict, settings: GuildSettings = instance.settings) -> None:
			await settings.handle_event(event)

		await bus.subscribe(EVENTS_CHANNEL, handler)
	return a, b


async def test_remote_set_updates_the_writer_and_leaves_announcing_to_the_api(instances, api, bus):
	a, _ = instances
	published: list[dict] = []

	async def record(event: dict) -> None:
		published.append(event)

	await bus.subscribe(EVENTS_CHANNEL, record)

	await a.prefix.set(GUILD, ("!", False))
	await settle()

	assert a.prefix.cache[GUILD] == ("!", False)
	assert api.values["prefix"][GUILD] == ("!", False)
	assert len(published) == 1  # the API's announcement only; the bot didn't announce again


async def test_preloaded_remote_setting_is_reloaded_on_other_instances(instances):
	a, b = instances
	await a.settings.preload()
	await b.settings.preload()
	assert GUILD not in b.locale.cache

	await a.locale.set(GUILD, "hu")
	await settle()
	assert b.locale.cache[GUILD] == "hu"  # synchronous readers see it without a get()

	await a.locale.set(GUILD, None)
	await settle()
	assert b.locale.cache[GUILD] is None


async def test_dashboard_change_reaches_every_instance(instances, api):
	a, b = instances
	await a.settings.preload()
	await b.settings.preload()

	await api.write("prefix", GUILD, ("$", True), origin=None)
	await settle()

	assert a.prefix.cache[GUILD] == ("$", True)
	assert b.prefix.cache[GUILD] == ("$", True)


async def test_writer_skips_the_echo_of_its_own_remote_write(instances, api):
	a, b = instances
	await b.settings.preload()
	await a.prefix.set(GUILD, ("!", True))
	api.values["prefix"][GUILD] = ("?", True)  # changed behind everyone's back before the echo arrives
	await settle()

	# Had the writer handled the API's echo of its own write, it would have reloaded and seen "?".
	assert a.prefix.cache[GUILD] == ("!", True)
	assert b.prefix.cache[GUILD] == ("?", True)


async def test_lazy_setting_is_dropped_on_other_instances_and_reloaded_on_next_get(instances):
	a, b = instances
	assert await b.retention.get(GUILD) == "keep"

	await a.retention.set(GUILD, "delete")
	await settle()

	assert GUILD not in b.retention.cache
	assert await b.retention.get(GUILD) == "delete"


async def test_preload_reads_every_guild(instances, api):
	a, _ = instances
	api.values["prefix"] = {1: ("!", True), 2: ("$", False)}

	await a.settings.preload()

	assert a.prefix.cache == {1: ("!", True), 2: ("$", False)}


async def test_forget_guild_drops_every_setting(instances):
	a, _ = instances
	await a.prefix.get(GUILD)
	await a.retention.get(GUILD)

	a.settings.forget_guild(GUILD)

	assert GUILD not in a.prefix.cache
	assert GUILD not in a.retention.cache


async def test_registering_a_key_twice_returns_the_same_setting(instances, api):
	a, _ = instances
	assert api.remote(a.settings, "mod.retention") is a.retention


async def test_a_setting_without_a_saver_refuses_set(instances):
	a, _ = instances

	async def load(guild_id: int) -> bool:
		return True

	setting = a.settings.add_remote("test.ops", load, None)

	assert await setting.get(GUILD) is True
	with pytest.raises(TypeError):
		await setting.set(GUILD, False)
