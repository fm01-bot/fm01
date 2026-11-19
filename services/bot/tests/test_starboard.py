"""Starboards: which stars count, when boards post, update and take down, and what a post looks like."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from cogs import starboard as module
from cogs.starboard import Starboards, emoji_key, is_nsfw, missing_permissions, wants_post, watches

from api import Starboard, StarboardEntry, StarboardPost, StarboardUpdate, StarredMessage

GUILD, SOURCE, BOARD_CHANNEL, TIER_CHANNEL, NSFW = 1, 10, 20, 21, 30
MESSAGE, POST, AUTHOR, MEMBER = 900, 950, 5, 6
NOW = discord.utils.snowflake_time(MESSAGE) + datetime.timedelta(hours=1)


def board(**overrides: Any) -> Starboard:
	fields: dict[str, Any] = {"name": "starboard", "channel_id": BOARD_CHANNEL, "threshold": 2, **overrides}
	return Starboard.model_validate(fields)


def starred(count: int, *entries: StarboardEntry, emoji: str = "⭐") -> StarredMessage:
	return StarredMessage(
		message_id=MESSAGE, channel_id=SOURCE, author_id=AUTHOR, emoji=emoji, count=count, entries=list(entries)
	)


def entry(name: str = "starboard", **overrides: Any) -> StarboardEntry:
	return StarboardEntry.model_validate({"board": name, "message_id": MESSAGE, **overrides})


def text_channel(channel_id: int, *, nsfw: bool = False) -> MagicMock:
	channel = MagicMock(spec=discord.TextChannel)
	channel.id = channel_id
	channel.is_nsfw.return_value = nsfw
	channel.send = AsyncMock(return_value=SimpleNamespace(id=POST))
	channel.permissions_for.return_value = discord.Permissions(view_channel=True, send_messages=True, embed_links=True)
	partial = MagicMock()
	partial.delete = AsyncMock()
	partial.edit = AsyncMock()
	channel.get_partial_message.return_value = partial
	return channel


def thread(parent_id: int) -> MagicMock:
	channel = MagicMock(spec=discord.Thread)
	channel.id = 99
	channel.parent_id = parent_id
	channel.is_nsfw.return_value = False
	return channel


def fake(**attributes: Any) -> Any:
	return SimpleNamespace(**attributes)


@pytest.fixture
def channels():
	return {cid: text_channel(cid) for cid in (SOURCE, BOARD_CHANNEL, TIER_CHANNEL)} | {
		NSFW: text_channel(NSFW, nsfw=True)
	}


@pytest.fixture
def guild(channels):
	guild = MagicMock(spec=discord.Guild)
	guild.id = GUILD
	guild.get_channel.side_effect = channels.get
	guild.get_channel_or_thread.side_effect = channels.get
	return guild


@pytest.fixture
def cog(guild, monkeypatch):
	monkeypatch.setattr(discord.utils, "utcnow", lambda: NOW)
	bot = MagicMock()
	bot.get_guild.return_value = guild
	bot.api.starboard = AsyncMock()
	cog = Starboards(bot)
	cog.setting = fake(cache={GUILD: [board()]}, remember=MagicMock())
	cog.render = AsyncMock(return_value={"content": "⭐ 2"})
	cog._schedule_edit = MagicMock()
	return cog


def reaction(*, channel_id: int = SOURCE, message_id: int = MESSAGE, emoji: str = "⭐", bot: bool = False):
	member = MagicMock(spec=discord.Member)
	member.bot = bot
	return SimpleNamespace(
		guild_id=GUILD,
		channel_id=channel_id,
		message_id=message_id,
		user_id=MEMBER,
		emoji=discord.PartialEmoji.from_str(emoji),
		member=member,
	)


def original(channel: MagicMock, *, reactors: list[Any] | None = None) -> MagicMock:
	message = MagicMock(spec=discord.Message)
	message.id = MESSAGE
	message.channel = channel
	message.author = SimpleNamespace(id=AUTHOR)
	users = reactors or []

	async def iterate(limit: int):
		for user in users:
			yield user

	message.reactions = [SimpleNamespace(emoji="⭐", users=iterate)]
	channel.fetch_message = AsyncMock(return_value=message)
	return message


# Pure rules


def test_emoji_keys_are_custom_ids_or_the_unicode_emoji():
	assert emoji_key(discord.PartialEmoji.from_str("<:party:123456789012345678>")) == "123456789012345678"
	assert emoji_key(discord.PartialEmoji.from_str("⭐")) == "⭐"
	assert emoji_key("💀") == "💀"


def test_nsfw_is_read_from_the_channel(channels):
	assert is_nsfw(channels[NSFW]) is True
	assert is_nsfw(channels[SOURCE]) is False
	assert is_nsfw(object()) is False


@pytest.mark.parametrize(
	("mode", "listed", "expected"),
	[("blocklist", [], True), ("blocklist", [SOURCE], False), ("allowlist", [], False), ("allowlist", [SOURCE], True)],
)
def test_channel_filter(channels, mode, listed, expected):
	assert watches(board(channel_mode=mode, channel_ids=listed), channels[SOURCE]) is expected


def test_a_thread_follows_its_parent_channel():
	assert watches(board(channel_mode="blocklist", channel_ids=[SOURCE]), thread(SOURCE)) is False
	assert watches(board(channel_mode="allowlist", channel_ids=[SOURCE]), thread(SOURCE)) is True


@pytest.mark.parametrize(
	("overrides", "count", "blocked", "expected"),
	[
		({}, 2, False, True),
		({}, 1, False, False),
		({"enabled": False}, 5, False, False),
		({}, 5, True, False),
		({"channel_mode": "allowlist"}, 5, False, False),
	],
)
def test_wants_post(channels, overrides, count, blocked, expected):
	result = wants_post(board(**overrides), starred(count), entry(blocked=blocked), channels[SOURCE], NOW)

	assert result is expected


def test_messages_older_than_the_age_limit_are_not_posted(channels):
	limited = board(max_age_days=1)

	assert wants_post(limited, starred(5), None, channels[SOURCE], NOW) is True
	assert wants_post(limited, starred(5), None, channels[SOURCE], NOW + datetime.timedelta(days=2)) is False


def test_missing_permissions(channels):
	channel = channels[BOARD_CHANNEL]
	channel.permissions_for.return_value = discord.Permissions(view_channel=True)

	assert missing_permissions(channel) == ["send_messages", "embed_links"]


# Counting stars


async def test_a_star_that_reaches_the_threshold_posts_and_records_the_post(cog, channels):
	cog.bot.api.starboard.star.return_value = starred(2)
	original(channels[SOURCE])

	await cog.on_raw_reaction_add(reaction())

	cog.bot.api.starboard.star.assert_awaited_once_with(GUILD, MESSAGE, "⭐", MEMBER, True)
	channels[BOARD_CHANNEL].send.assert_awaited_once()
	cog.bot.api.starboard.set_post.assert_awaited_once_with(
		GUILD, StarboardPost(board="starboard", message_id=MESSAGE, post_channel_id=BOARD_CHANNEL, post_id=POST)
	)


async def test_a_star_below_the_threshold_posts_nothing(cog, channels):
	cog.bot.api.starboard.star.return_value = starred(1)

	await cog.on_raw_reaction_add(reaction())

	channels[BOARD_CHANNEL].send.assert_not_awaited()


@pytest.mark.parametrize(
	"payload",
	[reaction(bot=True), reaction(emoji="💀"), reaction(channel_id=NSFW)],
	ids=["bot", "other-emoji", "nsfw"],
)
async def test_ignored_stars_never_reach_the_api(cog, payload):
	await cog.on_raw_reaction_add(payload)

	cog.bot.api.starboard.star.assert_not_awaited()


async def test_a_channel_no_board_watches_is_ignored(cog):
	cog.setting.cache[GUILD] = [board(channel_mode="allowlist", channel_ids=[TIER_CHANNEL])]

	await cog.on_raw_reaction_add(reaction())

	cog.bot.api.starboard.star.assert_not_awaited()


async def test_an_unseen_message_is_seeded_from_its_reactors_without_bots(cog, channels):
	cog.bot.api.starboard.star.return_value = None
	cog.bot.api.starboard.seed.return_value = starred(1)
	original(channels[SOURCE], reactors=[SimpleNamespace(id=1, bot=False), SimpleNamespace(id=2, bot=True)])

	await cog.on_raw_reaction_add(reaction())

	seed = cog.bot.api.starboard.seed.await_args.args[1]
	assert (seed.message_id, seed.channel_id, seed.author_id, seed.user_ids) == (MESSAGE, SOURCE, AUTHOR, [1])


async def test_a_star_on_a_message_in_a_board_channel_that_is_not_a_post_is_dropped(cog):
	cog.bot.api.starboard.star.return_value = None

	await cog.on_raw_reaction_add(reaction(channel_id=BOARD_CHANNEL, message_id=POST))

	cog.bot.api.starboard.seed.assert_not_awaited()


async def test_a_star_on_a_post_updates_the_count_of_its_original(cog, channels):
	cog.bot.api.starboard.star.return_value = starred(3, entry(post_channel_id=BOARD_CHANNEL, post_id=POST))

	await cog.on_raw_reaction_add(reaction(channel_id=BOARD_CHANNEL, message_id=POST))

	cog._schedule_edit.assert_called_once()
	channels[BOARD_CHANNEL].send.assert_not_awaited()


async def test_dropping_below_the_threshold_records_the_removal_before_deleting(cog, channels):
	posted = entry(post_channel_id=BOARD_CHANNEL, post_id=POST)
	cog.bot.api.starboard.star.return_value = starred(1, posted)
	order: list[str] = []
	cog.bot.api.starboard.set_post.side_effect = lambda *a: order.append("api")
	channels[BOARD_CHANNEL].get_partial_message.return_value.delete.side_effect = lambda: order.append("discord")

	await cog.on_raw_reaction_remove(reaction())

	cog.bot.api.starboard.set_post.assert_awaited_once_with(GUILD, StarboardPost(board="starboard", message_id=MESSAGE))
	assert order == ["api", "discord"]


async def test_tiers_post_independently(cog, channels):
	cog.setting.cache[GUILD] = [board(), board(name="hall-of-fame", channel_id=TIER_CHANNEL, threshold=5)]
	cog.bot.api.starboard.star.return_value = starred(5, entry(post_channel_id=BOARD_CHANNEL, post_id=POST))
	original(channels[SOURCE])

	await cog.on_raw_reaction_add(reaction())

	channels[TIER_CHANNEL].send.assert_awaited_once()
	channels[BOARD_CHANNEL].send.assert_not_awaited()
	cog._schedule_edit.assert_called_once()


async def test_a_blocked_message_is_not_posted_again(cog, channels):
	cog.bot.api.starboard.star.return_value = starred(10, entry(blocked=True))

	await cog.on_raw_reaction_add(reaction())

	channels[BOARD_CHANNEL].send.assert_not_awaited()


async def test_a_board_it_cannot_post_on_is_turned_off(cog, channels):
	cog.bot.api.starboard.star.return_value = starred(2)
	original(channels[SOURCE])
	channels[BOARD_CHANNEL].send.side_effect = discord.Forbidden(MagicMock(status=403, reason="x"), "x")

	await cog.on_raw_reaction_add(reaction())

	cog.bot.api.starboard.update.assert_awaited_once_with(GUILD, "starboard", StarboardUpdate(enabled=False))
	cog.bot.api.starboard.set_post.assert_not_awaited()


async def test_an_original_deleted_before_posting_is_forgotten(cog, channels):
	cog.bot.api.starboard.star.return_value = starred(2)
	cog.bot.api.starboard.messages_deleted.return_value = []
	channels[SOURCE].fetch_message = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404, reason="x"), "x"))

	await cog.on_raw_reaction_add(reaction(channel_id=BOARD_CHANNEL, message_id=POST))

	cog.bot.api.starboard.messages_deleted.assert_awaited_once_with(GUILD, [MESSAGE])


# Edits


async def test_a_burst_of_stars_edits_each_post_once_with_the_newest_count(cog, channels, monkeypatch):
	monkeypatch.setattr(module, "EDIT_DELAY", 0)
	cog = Starboards(cog.bot)
	cog.setting = fake(cache={GUILD: [board()]})
	cog.responses = MagicMock()
	cog.responses.get_message = AsyncMock(side_effect=lambda key, guild, **kw: f"{kw['emoji']} {kw['count']}")
	cog._spawn = MagicMock()
	posted = entry(post_channel_id=BOARD_CHANNEL, post_id=POST)

	cog._schedule_edit(GUILD, starred(3, posted))
	cog._schedule_edit(GUILD, starred(4, posted))
	await cog._spawn.call_args.args[0]

	assert cog._spawn.call_count == 1
	channels[BOARD_CHANNEL].get_partial_message.return_value.edit.assert_awaited_once_with(content="⭐ 4")


# Deletions, clears and broken boards


async def test_a_post_deleted_in_a_board_channel_is_reported_as_a_block(cog):
	await cog.on_raw_message_delete(SimpleNamespace(guild_id=GUILD, channel_id=BOARD_CHANNEL, message_id=POST))

	cog.bot.api.starboard.posts_deleted.assert_awaited_once_with(GUILD, [POST])
	cog.bot.api.starboard.messages_deleted.assert_not_awaited()


async def test_a_deleted_original_takes_its_posts_down(cog, channels):
	cog.bot.api.starboard.messages_deleted.return_value = [entry(post_channel_id=BOARD_CHANNEL, post_id=POST)]

	await cog.on_raw_message_delete(SimpleNamespace(guild_id=GUILD, channel_id=SOURCE, message_id=MESSAGE))

	channels[BOARD_CHANNEL].get_partial_message.assert_called_once_with(POST)
	channels[BOARD_CHANNEL].get_partial_message.return_value.delete.assert_awaited_once()


async def test_bulk_deletes_are_sent_in_batches_of_100(cog):
	cog.bot.api.starboard.messages_deleted.return_value = []

	await cog.on_raw_bulk_message_delete(
		SimpleNamespace(guild_id=GUILD, channel_id=SOURCE, message_ids=set(range(1, 151)))
	)

	assert [len(call.args[1]) for call in cog.bot.api.starboard.messages_deleted.await_args_list] == [100, 50]


async def test_deletions_in_guilds_without_boards_are_ignored(cog):
	await cog.on_raw_message_delete(SimpleNamespace(guild_id=2, channel_id=SOURCE, message_id=MESSAGE))

	cog.bot.api.starboard.messages_deleted.assert_not_awaited()


async def test_clearing_an_originals_reactions_takes_its_posts_down(cog, channels):
	cog.bot.api.starboard.clear.return_value = [entry(post_channel_id=BOARD_CHANNEL, post_id=POST)]

	await cog.on_raw_reaction_clear_emoji(
		SimpleNamespace(guild_id=GUILD, channel_id=SOURCE, message_id=MESSAGE, emoji=discord.PartialEmoji(name="⭐"))
	)

	cog.bot.api.starboard.clear.assert_awaited_once_with(GUILD, MESSAGE, "⭐")
	channels[BOARD_CHANNEL].get_partial_message.return_value.delete.assert_awaited_once()


async def test_clearing_a_posts_reactions_does_nothing(cog):
	await cog.on_raw_reaction_clear(SimpleNamespace(guild_id=GUILD, channel_id=BOARD_CHANNEL, message_id=POST))

	cog.bot.api.starboard.clear.assert_not_awaited()


async def test_deleting_a_board_channel_turns_the_board_off(cog, guild, channels):
	channel = channels[BOARD_CHANNEL]
	channel.guild = guild

	await cog.on_guild_channel_delete(channel)

	cog.bot.api.starboard.update.assert_awaited_once_with(GUILD, "starboard", StarboardUpdate(enabled=False))


async def test_deleting_a_board_emoji_turns_the_board_off(cog, guild):
	cog.setting.cache[GUILD] = [board(emoji="123456789012345678"), board(name="stars", threshold=9)]

	await cog.on_guild_emojis_update(guild, [], [SimpleNamespace(id=1)])

	cog.bot.api.starboard.update.assert_awaited_once_with(GUILD, "starboard", StarboardUpdate(enabled=False))


# What a post looks like


def message(channel: Any, *, content: str = "hello", attachments=(), embeds=(), reference=None) -> MagicMock:
	msg = MagicMock(spec=discord.Message)
	msg.id = MESSAGE
	msg.channel = channel
	msg.author = SimpleNamespace(id=AUTHOR)
	msg.content = content
	msg.jump_url = f"https://discord.com/channels/{GUILD}/{SOURCE}/{MESSAGE}"
	msg.created_at = NOW
	msg.attachments = list(attachments)
	msg.embeds = list(embeds)
	msg.reference = reference
	return msg


def attachment(name: str, content_type: str) -> SimpleNamespace:
	return SimpleNamespace(filename=name, url=f"https://cdn.example/{name}", content_type=content_type)


@pytest.fixture
def renderer(cog):
	cog = Starboards(cog.bot)
	cog.responses = MagicMock()
	cog.responses.convert_embeds = lambda data: {"embeds": [discord.Embed.from_dict(e) for e in data["embeds"]]}

	async def get_message(key, guild, **kwargs):
		if key == "starboard.post.content":
			return f"{kwargs['emoji']} {kwargs['count']} {kwargs['channel']}"
		if key == "starboard.post.jump":
			return "Jump"
		return {"embeds": [{"title": key, "description": kwargs.get("content") or "", "footer": {"text": ""}}]}

	cog.responses.get_message = get_message
	return cog


async def test_a_post_shows_the_reply_the_original_and_its_embeds_in_order(renderer, guild, channels):
	replied = message(channels[SOURCE], content="question")
	rich = discord.Embed(title="link preview")
	preview = discord.Embed.from_dict({"type": "image", "thumbnail": {"url": "https://img.example/a.png"}})
	video = discord.Embed.from_dict({"type": "video", "video": {"url": "https://v.example/a.mp4"}})
	starred_message = message(
		channels[SOURCE],
		embeds=[rich, preview, video],
		reference=SimpleNamespace(resolved=replied),
		attachments=[attachment("a.png", "image/png"), attachment("b.txt", "text/plain")],
	)

	kwargs = await renderer.render(guild, starred(2), starred_message)

	assert kwargs["content"] == f"⭐ 2 <#{SOURCE}>"
	assert [e.title for e in kwargs["embeds"]] == [
		"starboard.post.reply",
		"starboard.post.message",
		"link preview",
		None,
	]
	assert kwargs["embeds"][1].image.url == "https://cdn.example/a.png"
	assert kwargs["embeds"][3].image.url == "https://img.example/a.png"
	assert kwargs["embeds"][0].footer.text is None  # empty strings are dropped
	assert kwargs["view"].children[0].url == starred_message.jump_url


async def test_a_post_has_at_most_ten_embeds(renderer, guild, channels):
	starred_message = message(channels[SOURCE], embeds=[discord.Embed(title=str(i)) for i in range(12)])

	kwargs = await renderer.render(guild, starred(2), starred_message)

	assert len(kwargs["embeds"]) == 10


async def test_a_custom_emoji_is_shown_as_an_emoji_animated_if_it_is(renderer, guild):
	guild.get_emoji.side_effect = lambda emoji_id: "<a:party:1>" if emoji_id == 111111111111111111 else None

	animated = await renderer.content(guild, starred(4, emoji="111111111111111111"))
	unknown = await renderer.content(guild, starred(4, emoji="123456789012345678"))

	assert animated.startswith("<a:party:1> 4")
	assert unknown.startswith("<:e:123456789012345678> 4")
