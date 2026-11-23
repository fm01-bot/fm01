"""Guild settings: cached per-guild values that stay in step across bot instances.

Each setting is a `GuildSetting` registered on `GuildSettings` (``Bot.settings``) with `GuildSettings.add_remote`.
Callers read with `GuildSetting.get` (or `GuildSetting.cache` for synchronous hot paths) and write with
`GuildSetting.set`, or through the setting's own API operations followed by `GuildSetting.remember`. Every setting lives
behind the Internal API: the API persists it and announces every change as an ``INVALIDATE_SETTING`` event on the event
bus, whoever asked for it (this bot or the dashboard); every other instance reloads that guild's value. Callers never
touch caches or the event bus themselves.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from types import MappingProxyType
from typing import Any

from api import EVENTS_CHANNEL, INVALIDATE_SETTING, LOCALE_SETTING, PREFIX_SETTING
from api import Prefix as PrefixModel
from core.api import ApiClient
from core.clustering.interfaces import EventBus

__all__ = (
	"EVENTS_CHANNEL",
	"INVALIDATE_SETTING",
	"GuildSetting",
	"GuildSettings",
	"Prefix",
	"locale_override_setting",
	"prefix_setting",
)

logger = logging.getLogger(__name__)

type RemoteLoader[T] = Callable[[int], Awaitable[T]]
type RemoteSaver[T] = Callable[[int, T], Awaitable[None]]
type RemoteBulkLoader[T] = Callable[[], Awaitable[Mapping[int, T]]]
type ChangeHook[T] = Callable[[int, T | None], None]


class GuildSetting[T]:
	"""One per-guild setting with a cache. Create these through `GuildSettings.add_remote`.

	A setting with ``load_all`` is *preloaded*: every guild's value is cached at startup, so `cache` can be read
	synchronously, and invalidations reload the value immediately. Other settings load lazily on first `get`, and
	invalidations drop the cached value.

	``on_change`` is called with ``(guild_id, value)`` whenever the cached value changes, and with
	``(guild_id, None)`` when it is dropped. Use it to keep derived state (an index, a set of guild IDs) in step.
	"""

	def __init__(
		self,
		registry: GuildSettings,
		key: str,
		load: RemoteLoader[T],
		save: RemoteSaver[T] | None,
		load_all: RemoteBulkLoader[T] | None,
		on_change: ChangeHook[T] | None,
	) -> None:
		self.key = key
		self._registry = registry
		self._load = load
		self._save = save
		self._load_all = load_all
		self._on_change = on_change
		self._cache: dict[int, T] = {}
		self.cache: Mapping[int, T] = MappingProxyType(self._cache)
		"""Read-only live view of the cached values. Complete only for preloaded settings."""

	@property
	def preloaded(self) -> bool:
		"""Whether every guild's value is kept in `cache`."""
		return self._load_all is not None

	async def get(self, guild_id: int) -> T:
		"""Return the guild's value, loading it if it isn't cached."""
		if guild_id not in self._cache:
			self._store(guild_id, await self._load(guild_id))
		return self._cache[guild_id]

	async def set(self, guild_id: int, value: T) -> None:
		"""Persist the guild's value through the API, which tells the other instances to reload it."""
		if self._save is None:
			raise TypeError(
				f"Guild setting {self.key!r} has no single value to save; write it through its own operations"
			)
		await self._save(guild_id, value)
		self._store(guild_id, value)

	def remember(self, guild_id: int, value: T) -> None:
		"""Cache a value that is already persisted (e.g. a row just read elsewhere) without announcing it."""
		self._store(guild_id, value)

	def forget(self, guild_id: int) -> None:
		"""Drop the guild's cached value, e.g. when the bot leaves the guild."""
		self._drop(guild_id)

	async def refresh(self, guild_id: int) -> None:
		"""Bring the guild's cached value up to date after another instance changed it."""
		if self.preloaded:
			self._store(guild_id, await self._load(guild_id))
		else:
			self._drop(guild_id)

	async def preload(self) -> None:
		"""Cache every guild's value. Does nothing for lazily loaded settings."""
		if self._load_all is None:
			return
		values = await self._load_all()
		for guild_id in self._cache.keys() - values.keys():
			self._drop(guild_id)
		for guild_id, value in values.items():
			self._store(guild_id, value)

	def _store(self, guild_id: int, value: T) -> None:
		self._cache[guild_id] = value
		if self._on_change is not None:
			self._on_change(guild_id, value)

	def _drop(self, guild_id: int) -> None:
		self._cache.pop(guild_id, None)
		if self._on_change is not None:
			self._on_change(guild_id, None)


class GuildSettings:
	"""Registry of `GuildSetting`s, kept in step with the API's ``INVALIDATE_SETTING`` events.

	Args:
		event_bus: The bus that carries ``INVALIDATE_SETTING`` events from the API.
		origin: This instance's ID. Events it caused through the API carry it and are skipped here.
	"""

	def __init__(self, event_bus: EventBus, origin: str | None = None) -> None:
		self._event_bus = event_bus
		self._settings: dict[str, GuildSetting[Any]] = {}
		self.origin = origin or uuid.uuid4().hex

	def add_remote[T](
		self,
		key: str,
		load: RemoteLoader[T],
		save: RemoteSaver[T] | None,
		*,
		load_all: RemoteBulkLoader[T] | None = None,
		on_change: ChangeHook[T] | None = None,
	) -> GuildSetting[T]:
		"""Register a setting stored behind the Internal API. The API announces its changes, so `set` doesn't.

		Args:
			key: Unique name. Must match the key the API announces (constants in the ``api`` package).
			load: Reads one guild's value through the API client.
			save: Writes one guild's value through the API client. ``None`` for settings changed through their own
				API operations (such as starboards, one board at a time); callers `remember` what the API returns.
			load_all: Reads every guild's value. Makes the setting preloaded.
			on_change: Called when a cached value changes or is dropped (see `GuildSetting`).

		Returns:
			GuildSetting: The registered setting. Registering an existing key returns the existing setting.
		"""
		if key in self._settings:
			return self._settings[key]
		setting = GuildSetting(self, key, load, save, load_all, on_change)
		self._settings[key] = setting
		return setting

	def __getitem__(self, key: str) -> GuildSetting[Any]:
		return self._settings[key]

	async def preload(self) -> None:
		"""Preload every preloaded setting."""
		for setting in self._settings.values():
			try:
				await setting.preload()
			except Exception:
				logger.exception(f"Failed to preload guild setting {setting.key!r}")

	def forget_guild(self, guild_id: int) -> None:
		"""Drop every cached value for a guild."""
		for setting in self._settings.values():
			setting.forget(guild_id)

	async def handle_event(self, event: Mapping[str, Any]) -> bool:
		"""Apply an ``INVALIDATE_SETTING`` event from another instance.

		Returns:
			bool: Whether the event was a setting invalidation (handled or deliberately ignored).
		"""
		if event.get("type") != INVALIDATE_SETTING:
			return False
		if event.get("origin") == self.origin:
			return True
		setting = self._settings.get(str(event.get("key")))
		guild_id = event.get("guild_id")
		if setting is None or guild_id is None:
			return True
		await setting.refresh(int(guild_id))
		return True


# Settings owned by the bot core, stored behind the Internal API. Feature settings are registered by their cogs.

type Prefix = tuple[str, bool]
"""A guild's command prefix and whether mentioning the bot also works as a prefix."""


def prefix_setting(settings: GuildSettings, api: ApiClient) -> GuildSetting[Prefix]:
	"""Register the prefix setting, stored behind the API and preloaded.

	Args:
		settings: The registry to add it to.
		api: The API client it loads and saves through.
	"""

	async def load(guild_id: int) -> Prefix:
		value = await api.settings.prefix(guild_id)
		return value.prefix, value.mention

	async def save(guild_id: int, value: Prefix) -> None:
		await api.settings.set_prefix(guild_id, PrefixModel(prefix=value[0], mention=value[1]))

	async def load_all() -> dict[int, Prefix]:
		return {entry.guild_id: (entry.prefix, entry.mention) for entry in await api.settings.all_prefixes()}

	return settings.add_remote(PREFIX_SETTING, load, save, load_all=load_all)


def locale_override_setting(settings: GuildSettings, api: ApiClient) -> GuildSetting[str | None]:
	"""Register the locale override setting, stored behind the API and preloaded.

	A ``None`` value means the guild follows Discord locales.

	Args:
		settings: The registry to add it to.
		api: The API client it loads and saves through.
	"""
	return settings.add_remote(
		LOCALE_SETTING, api.settings.locale, api.settings.set_locale, load_all=api.settings.all_locales
	)
