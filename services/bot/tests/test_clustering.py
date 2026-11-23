from __future__ import annotations

import asyncio
from typing import cast
from unittest.mock import MagicMock

import discord
import pytest
import redis.asyncio as aioredis
from core.clustering import (
	ClusterConfig,
	InMemoryMessageBuffer,
	InMemoryStateStore,
	LocalEventBus,
	RedisShardCoordinator,
	StandaloneCoordinator,
)
from core.clustering.coordinator import CLAIM_BLOCK_LUA
from core.clustering.message_buffer import serialize_message


@pytest.mark.asyncio
async def test_in_memory_state_store():
	store = InMemoryStateStore()

	guild_data = {"id": 12345, "name": "Test Guild", "member_count": 50}
	channels_data = [{"id": 111, "name": "general", "type": "text"}]
	roles_data = [{"id": 222, "name": "Admin", "permissions": 8}]

	await store.set_guild(12345, guild_data)
	await store.set_channels(12345, channels_data)
	await store.set_roles(12345, roles_data)

	assert await store.get_guild(12345) == guild_data
	assert await store.get_channels(12345) == channels_data
	assert await store.get_roles(12345) == roles_data
	assert await store.is_bot_guild(12345) is True
	assert await store.is_bot_guild(99999) is False

	await store.remove_guild(12345)
	assert await store.get_guild(12345) is None
	assert await store.get_channels(12345) is None
	assert await store.get_roles(12345) is None
	assert await store.is_bot_guild(12345) is False

	await store.close()


@pytest.mark.asyncio
async def test_local_event_bus():
	bus = LocalEventBus()
	received: list[dict] = []

	async def handler(event: dict):
		received.append(event)

	await bus.subscribe("fm01:events", handler)
	await bus.publish("fm01:events", {"type": "INVALIDATE_PREFIX", "guild_id": 123})

	# Give event loop a moment to dispatch
	await asyncio.sleep(0.05)

	assert len(received) == 1
	assert received[0] == {"type": "INVALIDATE_PREFIX", "guild_id": 123}

	await bus.close()


@pytest.mark.asyncio
async def test_in_memory_message_buffer():
	buffer = InMemoryMessageBuffer(maxsize=3)

	mock_msg1 = MagicMock(spec=discord.Message)
	mock_msg1.id = 101
	mock_msg1.channel.id = 1
	mock_msg1.guild.id = 10
	mock_msg1.author.id = 55
	mock_msg1.author.__str__.return_value = "User1"
	mock_msg1.author.display_avatar.url = "http://avatar1"
	mock_msg1.content = "Hello world"
	mock_msg1.attachments = []
	mock_msg1.created_at = None

	mock_msg2 = MagicMock(spec=discord.Message)
	mock_msg2.id = 102
	mock_msg2.channel.id = 1
	mock_msg2.guild.id = 10
	mock_msg2.author.id = 56
	mock_msg2.author.__str__.return_value = "User2"
	mock_msg2.author.display_avatar.url = "http://avatar2"
	mock_msg2.content = "Second message"
	mock_msg2.attachments = []
	mock_msg2.created_at = None

	buffer.enqueue_message(mock_msg1)
	buffer.enqueue_message(mock_msg2)

	cached1 = await buffer.get_message(1, 101)
	assert cached1 is not None
	assert cached1["content"] == "Hello world"
	assert cached1["author_id"] == 55

	cached2 = await buffer.get_message(1, 102)
	assert cached2 is not None
	assert cached2["content"] == "Second message"

	assert await buffer.get_message(1, 999) is None

	await buffer.close()


def test_serialize_message():
	mock_msg = MagicMock(spec=discord.Message)
	mock_msg.id = 123456
	mock_msg.channel.id = 789
	mock_msg.guild.id = 456
	mock_msg.author.id = 111
	mock_msg.author.__str__.return_value = "TestUser#0000"
	mock_msg.author.display_avatar.url = "http://avatar"
	mock_msg.content = "Test content"
	attachment = MagicMock()
	attachment.url = "http://attachment.png"
	mock_msg.attachments = [attachment]
	mock_msg.created_at = None

	data = serialize_message(mock_msg)
	assert data["id"] == 123456
	assert data["channel_id"] == 789
	assert data["guild_id"] == 456
	assert data["author_id"] == 111
	assert data["content"] == "Test content"
	assert data["attachment_urls"] == ["http://attachment.png"]


def test_cluster_config_from_env(monkeypatch):
	monkeypatch.setenv("BOT_MODE", "clustered")
	monkeypatch.setenv("SHARD_COUNT", "64")
	monkeypatch.setenv("SHARDS_PER_CLUSTER", "8")
	monkeypatch.setenv("CLUSTER_ID", "test-cluster-1")
	monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
	monkeypatch.setenv("REDIS_MSG_URL", "redis://localhost:6379/1")
	monkeypatch.setenv("DISCORD_PROXY_URL", "http://proxy:3000/api/v10")

	cfg = ClusterConfig.from_env()
	assert cfg.is_clustered is True
	assert cfg.shard_count == 64
	assert cfg.shards_per_cluster == 8
	assert cfg.cluster_id == "test-cluster-1"
	assert cfg.discord_proxy_url == "http://proxy:3000/api/v10"


def test_cluster_config_hostname_fallback(monkeypatch):
	monkeypatch.delenv("CLUSTER_ID", raising=False)
	monkeypatch.setenv("HOSTNAME", "container-node-42")
	cfg = ClusterConfig.from_env()
	assert cfg.cluster_id == "cluster-container-node-42"


@pytest.mark.asyncio
async def test_standalone_coordinator():
	coordinator = StandaloneCoordinator()
	assert await coordinator.acquire_shards(64, 16) is None
	await coordinator.start_heartbeat()
	await coordinator.release_shards()
	await coordinator.close()


class _FakeLeaseRedis:
	"""Implements the Redis calls `RedisShardCoordinator` makes, without expiry."""

	def __init__(self) -> None:
		self.data: dict[str, bytes] = {}

	async def set(self, key: str, value, nx: bool = False, ex: int | None = None) -> bool:
		if nx and key in self.data:
			return False
		self.data[key] = value if isinstance(value, bytes) else str(value).encode()
		return True

	async def get(self, key: str) -> bytes | None:
		return self.data.get(key)

	async def mget(self, keys: list[str]) -> list[bytes | None]:
		return [self.data.get(key) for key in keys]

	async def expire(self, key: str, ttl: int) -> bool:
		return key in self.data

	async def eval(self, script: str, numkeys: int, *args):
		assert script == CLAIM_BLOCK_LUA
		keys, (owner, _ttl) = list(args[:numkeys]), args[numkeys:]
		if any(self.data.get(key, owner) != owner for key in keys):
			return 0
		for key in keys:
			self.data[key] = owner
		return 1


@pytest.mark.asyncio
async def test_redis_coordinator_reports_unclaimed_shards(caplog):
	redis = _FakeLeaseRedis()
	first = RedisShardCoordinator(cast(aioredis.Redis, redis), cluster_id="cluster-a")
	assert await first.acquire_shards(2, 1) == [0]  # block 0
	assert await first.unclaimed_shards() == [1]

	with caplog.at_level("WARNING", logger="core.clustering.coordinator"):
		await first._check_unclaimed_shards()
		await first._check_unclaimed_shards()
	assert len([r for r in caplog.records if "not claimed by any cluster" in r.message]) == 1

	second = RedisShardCoordinator(cast(aioredis.Redis, redis), cluster_id="cluster-b")
	assert await second.acquire_shards(2, 1) == [1]
	assert await first.unclaimed_shards() == []


@pytest.mark.asyncio
async def test_redis_coordinator_claims_whole_blocks():
	redis = _FakeLeaseRedis()
	redis.data["fm01:shard:lease:1"] = b"cluster-z"  # a stray lease inside block 0
	first = RedisShardCoordinator(cast(aioredis.Redis, redis), cluster_id="cluster-a")
	assert await first.acquire_shards(5, 2) == [2, 3]
	second = RedisShardCoordinator(cast(aioredis.Redis, redis), cluster_id="cluster-b")
	assert await second.acquire_shards(5, 2) == [4]  # the last block is smaller
	third = RedisShardCoordinator(cast(aioredis.Redis, redis), cluster_id="cluster-c")
	with pytest.raises(RuntimeError, match="no free shards"):
		await third.acquire_shards(5, 2)
	assert "fm01:shard:lease:0" not in redis.data  # a block is claimed whole or not at all

	restarted = RedisShardCoordinator(cast(aioredis.Redis, redis), cluster_id="cluster-a")
	assert await restarted.acquire_shards(5, 2) == [2, 3]  # its own leases count as free


class _FakePubSub:
	"""Mimics redis-py's PubSub: ``listen()`` ends as soon as nothing is subscribed."""

	def __init__(self) -> None:
		self.channels: set[str] = set()
		self.queue: asyncio.Queue[dict] = asyncio.Queue()

	@property
	def subscribed(self) -> bool:
		return bool(self.channels)

	async def subscribe(self, *channels: str) -> None:
		self.channels.update(channels)

	async def listen(self):
		while self.subscribed:
			yield await self.queue.get()

	async def unsubscribe(self) -> None:
		self.channels.clear()

	async def aclose(self) -> None:
		pass


@pytest.mark.asyncio
async def test_redis_bus_delivers_messages_on_channels_subscribed_after_start():
	from core.clustering import RedisPubSubBus

	pubsub = _FakePubSub()
	redis = MagicMock()
	redis.pubsub.return_value = pubsub
	bus = RedisPubSubBus(redis)
	received: asyncio.Queue[dict] = asyncio.Queue()

	async def handler(message: dict) -> None:
		await received.put(message)

	await bus.start()  # the bot starts the bus before it subscribes
	await asyncio.sleep(0)
	await bus.subscribe("fm01:events", handler)
	await pubsub.queue.put({"type": "message", "channel": b"fm01:events", "data": b'{"type": "PING"}'})

	assert await asyncio.wait_for(received.get(), timeout=1) == {"type": "PING"}
	await bus.close()
