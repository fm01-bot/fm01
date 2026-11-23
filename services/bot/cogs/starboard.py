"""Starboards: once enough members react to a message with a board's emoji, the bot reposts it in the board's channel.

Boards, the stars on each message and the bot's posts live behind the API (`StarboardApi`); boards are the
``starboard`` guild setting. Stars belong to a message and an emoji, so boards that share an emoji (tiers) share one
count, and stars on any of the message's posts count too. Each tier posts on its own once the count reaches its
threshold, and takes its post down when the count drops below it again.

Whenever the bot removes a post itself, it tells the API first. So a post that disappears while the API still knows
it was deleted by someone else, and that blocks the message on that board.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from collections import defaultdict
from collections.abc import Awaitable, Iterable
from typing import Any

import discord
from core import Bot
from core.api import ApiClient, ApiUnavailable
from core.settings import GuildSetting, GuildSettings
from discord.ext import commands
from helpers.custom_response import CustomResponse

from api import STARBOARD_SETTING, Starboard, StarboardEntry, StarboardPost, StarboardUpdate, StarredMessage, StarSeed

__all__ = (
	"EDIT_DELAY",
	"REQUIRED_PERMISSIONS",
	"Starboards",
	"emoji_key",
	"is_nsfw",
	"missing_permissions",
	"starboard_setting",
	"wants_post",
	"watches",
)

logger = logging.getLogger(__name__)

EDIT_DELAY = 3.0
"""Seconds to wait before editing a post's count, so a burst of stars edits it once."""
SEED_LIMIT = 10_000
"""The most reactors read from Discord when seeding a message."""
MAX_EMBEDS = 10
DELETE_BATCH = 100
"""The most message IDs the API takes in one deletion call."""

REQUIRED_PERMISSIONS = ("view_channel", "send_messages", "embed_links")
"""Permissions the bot needs in a board's channel to post there."""

type BoardKey = tuple[int, str]
"""A guild and an emoji: the stars of every board with that emoji are counted together."""
type EditKey = tuple[int, int, str]
"""A guild, an original message and an emoji."""


def emoji_key(emoji: discord.PartialEmoji | discord.Emoji | str) -> str:
	"""Turn an emoji into the form boards store it in.

	Args:
		emoji: A reaction's emoji.

	Returns:
		A custom emoji's ID as a string, or the unicode emoji itself.
	"""
	if isinstance(emoji, str):
		return emoji
	return str(emoji.id) if emoji.id else str(emoji.name)


def display_emoji(guild: discord.Guild, key: str) -> str:
	"""Render a board's emoji in a message.

	Args:
		guild: The guild the custom emoji belongs to.
		key: The board's emoji, as `emoji_key` gives it.

	Returns:
		The emoji as Discord renders it in text, animated if it is.
	"""
	if not key.isdigit():
		return key
	emoji = guild.get_emoji(int(key))
	return str(emoji) if emoji is not None else f"<:e:{key}>"


def starboard_setting(settings: GuildSettings, api: ApiClient) -> GuildSetting[list[Starboard]]:
	"""Register the starboard setting: a guild's boards, stored behind the API and preloaded for reaction events.

	Boards are written one at a time through `StarboardApi`, never with `GuildSetting.set`. Writers `remember` the
	guild's boards afterwards.

	Args:
		settings: The registry to add it to.
		api: The API client it loads through.

	Returns:
		The setting.
	"""
	return settings.add_remote(STARBOARD_SETTING, api.starboard.boards, None, load_all=api.starboard.all)


def is_nsfw(channel: object) -> bool:
	"""Check whether a channel, or a thread's parent, is age-restricted. Messages there are never starred.

	Args:
		channel: The channel.

	Returns:
		Whether it is age-restricted.
	"""
	check = getattr(channel, "is_nsfw", None)
	return bool(check()) if callable(check) else False


def watches(board: Starboard, channel: discord.abc.GuildChannel | discord.Thread) -> bool:
	"""Check whether a board's channel filter lets messages from a channel through. A thread follows its parent.

	Args:
		board: The board.
		channel: The channel the message was sent in.

	Returns:
		Whether the board watches the channel. Board channels are excluded elsewhere.
	"""
	ids = {channel.id}
	if isinstance(channel, discord.Thread):
		ids.add(channel.parent_id)
	listed = bool(ids & set(board.channel_ids))
	return listed if board.channel_mode == "allowlist" else not listed


def wants_post(
	board: Starboard,
	message: StarredMessage,
	entry: StarboardEntry | None,
	channel: discord.abc.GuildChannel | discord.Thread,
	now: datetime.datetime | None = None,
) -> bool:
	"""Check whether a message belongs on a board right now.

	Args:
		board: The board.
		message: The message's stars with the board's emoji.
		entry: The message's entry on the board, if any.
		channel: The channel the message was sent in.
		now: The current time. Defaults to now.

	Returns:
		Whether the board is on, the message is not blocked there, has enough stars, comes from a channel the board
		watches, and isn't older than the board's age limit.
	"""
	if not board.enabled or (entry is not None and entry.blocked) or message.count < board.threshold:
		return False
	if not watches(board, channel):
		return False
	if board.max_age_days is not None:
		age = (now or discord.utils.utcnow()) - discord.utils.snowflake_time(message.message_id)
		if age > datetime.timedelta(days=board.max_age_days):
			return False
	return True


def missing_permissions(channel: discord.TextChannel) -> list[str]:
	"""List the permissions the bot lacks to post in a board channel.

	Args:
		channel: The board's channel.

	Returns:
		The missing `REQUIRED_PERMISSIONS`.
	"""
	permissions = channel.permissions_for(channel.guild.me)
	return [name for name in REQUIRED_PERMISSIONS if not getattr(permissions, name)]


def _without_empty(data: Any) -> Any:
	"""Drop empty strings, and the dicts and lists they leave empty, from a localized embed.

	Args:
		data: The localized payload.

	Returns:
		The payload without empty values, which Discord would reject.
	"""
	if isinstance(data, dict):
		cleaned = {key: _without_empty(value) for key, value in data.items()}
		return {key: value for key, value in cleaned.items() if value not in ("", {}, [])}
	if isinstance(data, list):
		cleaned = [_without_empty(item) for item in data]
		return [item for item in cleaned if item not in ("", {}, [])]
	return data


def _image(message: discord.Message) -> discord.Attachment | None:
	"""Find the attachment to show as a post's image.

	Args:
		message: The original.

	Returns:
		Its first image attachment, if any.
	"""
	for attachment in message.attachments:
		if (attachment.content_type or "").startswith("image/"):
			return attachment
	return None


def _copy_embed(embed: discord.Embed) -> discord.Embed | None:
	"""Copy one of the original's embeds into a form a bot may send.

	Image and GIF link previews become embeds showing the image. Bots can't send videos, so those are dropped.

	Args:
		embed: The embed.

	Returns:
		The copy, or ``None`` if nothing of it can be shown.
	"""
	if embed.type in ("image", "gifv"):
		url = embed.thumbnail.url or embed.url
		return discord.Embed().set_image(url=url) if url else None
	data = embed.to_dict()
	for key in ("type", "video", "provider"):
		data.pop(key, None)
	copy = discord.Embed.from_dict(data)
	if not any((copy.title, copy.description, copy.fields, copy.image.url, copy.thumbnail.url, copy.author.name)):
		return None
	return copy


class Starboards(commands.Cog, name="Starboard"):
	def __init__(self, bot: Bot) -> None:
		self.bot = bot
		self.setting = starboard_setting(bot.settings, bot.api)
		self.responses = CustomResponse(bot, "starboard")
		self._locks: defaultdict[BoardKey, asyncio.Lock] = defaultdict(asyncio.Lock)
		self._edits: dict[EditKey, StarredMessage] = {}
		self._background: set[asyncio.Task[Any]] = set()

	async def cog_unload(self) -> None:
		for task in self._background:
			task.cancel()

	def _spawn(self, coro: Awaitable[Any]) -> None:
		async def runner() -> None:
			try:
				await coro
			except Exception:
				logger.exception("Starboard background task failed")

		task = asyncio.create_task(runner())
		self._background.add(task)
		task.add_done_callback(self._background.discard)

	def boards(self, guild_id: int, emoji: str | None = None) -> list[Starboard]:
		"""A guild's boards, from the preloaded setting.

		Args:
			guild_id: The guild.
			emoji: Only boards with this emoji.

		Returns:
			The boards.
		"""
		boards = self.setting.cache.get(guild_id, [])
		return [board for board in boards if emoji is None or board.emoji == emoji]

	def _board_channels(self, guild_id: int) -> set[int]:
		return {board.channel_id for board in self.boards(guild_id)}

	async def reload(self, guild_id: int) -> list[Starboard]:
		"""Reload a guild's boards after this instance changed them through the API.

		Args:
			guild_id: The guild.

		Returns:
			The boards.
		"""
		boards = await self.bot.api.starboard.boards(guild_id)
		self.setting.remember(guild_id, boards)
		return boards

	# Stars

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
		if payload.member is not None and payload.member.bot:
			return
		await self._star(payload, starred=True)

	@commands.Cog.listener()
	async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
		await self._star(payload, starred=False)

	async def _star(self, payload: discord.RawReactionActionEvent, *, starred: bool) -> None:
		"""Count a star added or removed, then bring the message's posts in line with its new count."""
		if payload.guild_id is None:
			return
		emoji = emoji_key(payload.emoji)
		boards = self.boards(payload.guild_id, emoji)
		guild = self.bot.get_guild(payload.guild_id)
		if not boards or guild is None:
			return
		channel = guild.get_channel_or_thread(payload.channel_id)
		if channel is None:
			return
		on_post = payload.channel_id in self._board_channels(guild.id)
		if not on_post and (is_nsfw(channel) or not any(watches(board, channel) for board in boards)):
			return

		async with self._locks[(guild.id, emoji)]:
			try:
				api = self.bot.api.starboard
				message = await api.star(guild.id, payload.message_id, emoji, payload.user_id, starred)
				original = None
				if message is None:
					if on_post:
						return  # a message in a board channel that isn't a post
					original = await self._fetch(channel, payload.message_id)
					if original is None:
						return
					message = await self._seed(guild.id, original, emoji)
				await self._sync(guild, message, original)
			except ApiUnavailable:
				logger.warning(f"Couldn't count a star on {payload.message_id} in {guild.id}", exc_info=True)

	async def _fetch(self, channel: object, message_id: int) -> discord.Message | None:
		"""Fetch an original message. ``None`` if it's gone or the bot can't read it."""
		if not isinstance(channel, discord.abc.Messageable):
			return None
		try:
			return await channel.fetch_message(message_id)
		except discord.HTTPException:
			return None

	async def _seed(self, guild_id: int, original: discord.Message, emoji: str) -> StarredMessage:
		"""Tell the API everyone who starred a message it has never seen, bots left out."""
		user_ids: list[int] = []
		for reaction in original.reactions:
			if emoji_key(reaction.emoji) == emoji:
				user_ids = [user.id async for user in reaction.users(limit=SEED_LIMIT) if not user.bot]
		seed = StarSeed(
			message_id=original.id,
			channel_id=original.channel.id,
			author_id=original.author.id,
			emoji=emoji,
			user_ids=user_ids,
		)
		return await self.bot.api.starboard.seed(guild_id, seed)

	async def _sync(self, guild: discord.Guild, message: StarredMessage, original: discord.Message | None) -> None:
		"""Post, update or take down the message on each board with its emoji. Call with the emoji's lock held."""
		source = guild.get_channel_or_thread(message.channel_id)
		entries = {entry.board: entry for entry in message.entries}
		for board in self.boards(guild.id, message.emoji):
			entry = entries.get(board.name)
			posted = entry is not None and entry.post_id is not None
			wanted = source is not None and not is_nsfw(source) and wants_post(board, message, entry, source)
			if wanted and not posted:
				if original is None:
					original = await self._fetch(source, message.message_id)
					if original is None:
						await self.forget(guild, [message.message_id])
						return
				await self._post(guild, board, message, original)
			elif wanted:
				self._schedule_edit(guild.id, message)
			elif posted and entry is not None:
				await self._take_down(guild, entry)

	# Posts

	async def content(self, guild: discord.Guild, message: StarredMessage) -> str:
		"""Render a post's text: the emoji, the count and the original's channel.

		Args:
			guild: The guild, for its locale.
			message: The original's stars.

		Returns:
			The text.
		"""
		return str(
			await self.responses.get_message(
				"starboard.post.content",
				guild,
				emoji=display_emoji(guild, message.emoji),
				count=message.count,
				channel=f"<#{message.channel_id}>",
			)
		)

	async def _embed(self, key: str, guild: discord.Guild, message: discord.Message) -> discord.Embed:
		"""Render one of a post's embeds from its localized template."""
		payload = await self.responses.get_message(
			key,
			guild,
			convert_embeds=False,
			convert_components=False,
			author=message.author,
			content=message.content or None,
			jump=message.jump_url,
			timestamp=message.created_at.isoformat(),
			attachments="\n".join(
				f"[{attachment.filename}]({attachment.url})"
				for attachment in message.attachments
				if attachment != _image(message)
			)
			or None,
		)
		embeds = self.responses.convert_embeds(_without_empty(payload)).get("embeds") or [discord.Embed()]
		embed = embeds[0]
		if (image := _image(message)) is not None:
			embed.set_image(url=image.url)
		return embed

	async def render(self, guild: discord.Guild, message: StarredMessage, original: discord.Message) -> dict[str, Any]:
		"""Render a post: the text, then the replied-to message, the original and the original's own embeds.

		Args:
			guild: The guild, for its locale.
			message: The original's stars.
			original: The original.

		Returns:
			Keyword arguments for ``send``.
		"""
		embeds: list[discord.Embed] = []
		replied = original.reference.resolved if original.reference else None
		if isinstance(replied, discord.Message):
			embeds.append(await self._embed("starboard.post.reply", guild, replied))
		embeds.append(await self._embed("starboard.post.message", guild, original))
		for embed in original.embeds:
			if len(embeds) >= MAX_EMBEDS:
				break
			if (copy := _copy_embed(embed)) is not None:
				embeds.append(copy)
		label = str(await self.responses.get_message("starboard.post.jump", guild))
		view = discord.ui.View(timeout=None)
		view.add_item(discord.ui.Button(style=discord.ButtonStyle.link, label=label, url=original.jump_url))
		return {
			"content": await self.content(guild, message),
			"embeds": embeds,
			"view": view,
			"allowed_mentions": discord.AllowedMentions.none(),
		}

	async def _post(
		self, guild: discord.Guild, board: Starboard, message: StarredMessage, original: discord.Message
	) -> None:
		"""Post a message on a board and record the post. Turns the board off if it can't post there."""
		channel = guild.get_channel(board.channel_id)
		if not isinstance(channel, discord.TextChannel) or missing_permissions(channel):
			await self.disable(guild.id, board.name, f"can't post in channel {board.channel_id}")
			return
		try:
			post = await channel.send(**await self.render(guild, message, original))
		except (discord.Forbidden, discord.NotFound):
			await self.disable(guild.id, board.name, f"can't post in channel {board.channel_id}")
			return
		except discord.HTTPException:
			logger.warning(f"Failed to post {original.id} on board {board.name!r} in {guild.id}", exc_info=True)
			return
		record = StarboardPost(
			board=board.name, message_id=message.message_id, post_channel_id=channel.id, post_id=post.id
		)
		try:
			await self.bot.api.starboard.set_post(guild.id, record)
		except ApiUnavailable:
			# Unrecorded, the post would never be updated or taken down. The next star posts it again.
			await self._delete(guild, channel.id, post.id)
			raise

	async def _take_down(self, guild: discord.Guild, entry: StarboardEntry) -> None:
		"""Remove a post: record its removal first, so deleting it doesn't count as a moderator's block."""
		await self.bot.api.starboard.set_post(guild.id, StarboardPost(board=entry.board, message_id=entry.message_id))
		await self._delete(guild, entry.post_channel_id, entry.post_id)

	async def _delete(self, guild: discord.Guild, channel_id: int | None, message_id: int | None) -> None:
		channel = guild.get_channel(channel_id or 0)
		if not isinstance(channel, discord.TextChannel) or message_id is None:
			return
		try:
			await channel.get_partial_message(message_id).delete()
		except discord.HTTPException:
			pass  # already gone

	async def _delete_posts(self, guild: discord.Guild, entries: Iterable[StarboardEntry]) -> None:
		"""Delete posts the API already forgot."""
		for entry in entries:
			await self._delete(guild, entry.post_channel_id, entry.post_id)

	def _schedule_edit(self, guild_id: int, message: StarredMessage) -> None:
		key = (guild_id, message.message_id, message.emoji)
		first = key not in self._edits
		self._edits[key] = message  # the edit uses the newest count
		if first:
			self._spawn(self._edit_later(key))

	async def _edit_later(self, key: EditKey) -> None:
		"""After `EDIT_DELAY`, edit every post of a message to show its newest count."""
		try:
			await asyncio.sleep(EDIT_DELAY)
		finally:
			# Stars from now on schedule another edit, so none is lost while this one runs.
			message = self._edits.pop(key, None)
		guild = self.bot.get_guild(key[0])
		if message is None or guild is None:
			return
		content = await self.content(guild, message)
		for entry in message.entries:
			channel = guild.get_channel(entry.post_channel_id or 0)
			if not isinstance(channel, discord.TextChannel) or entry.post_id is None:
				continue
			try:
				await channel.get_partial_message(entry.post_id).edit(content=content)
			except discord.NotFound:
				pass  # deleted meanwhile; the delete event handles it
			except discord.HTTPException:
				logger.warning(f"Failed to update starboard post {entry.post_id} in {guild.id}", exc_info=True)

	async def disable(self, guild_id: int, name: str, why: str) -> None:
		"""Turn a board off. Its configuration, entries and posts stay.

		Args:
			guild_id: The guild.
			name: The board.
			why: What went wrong, for the log.
		"""
		logger.warning(f"Turning off starboard {name!r} in {guild_id}: {why}")
		try:
			await self.bot.api.starboard.update(guild_id, name, StarboardUpdate(enabled=False))
			await self.reload(guild_id)
		except ApiUnavailable:
			logger.warning(f"Couldn't turn off starboard {name!r} in {guild_id}", exc_info=True)

	# Deletions and cleared reactions

	async def forget(self, guild: discord.Guild, message_ids: list[int]) -> None:
		"""Forget deleted originals and delete their posts.

		Args:
			guild: The guild.
			message_ids: The deleted messages.
		"""
		for start in range(0, len(message_ids), DELETE_BATCH):
			entries = await self.bot.api.starboard.messages_deleted(guild.id, message_ids[start : start + DELETE_BATCH])
			await self._delete_posts(guild, entries)

	@commands.Cog.listener()
	async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
		await self._deleted(payload.guild_id, payload.channel_id, [payload.message_id])

	@commands.Cog.listener()
	async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent) -> None:
		await self._deleted(payload.guild_id, payload.channel_id, sorted(payload.message_ids))

	async def _deleted(self, guild_id: int | None, channel_id: int, message_ids: list[int]) -> None:
		"""Block posts someone deleted, or forget deleted originals and take their posts down."""
		if guild_id is None or not self.boards(guild_id):
			return
		guild = self.bot.get_guild(guild_id)
		if guild is None:
			return
		try:
			if channel_id in self._board_channels(guild_id):
				for start in range(0, len(message_ids), DELETE_BATCH):
					await self.bot.api.starboard.posts_deleted(guild_id, message_ids[start : start + DELETE_BATCH])
			else:
				await self.forget(guild, message_ids)
		except ApiUnavailable:
			logger.warning(f"Couldn't handle deleted messages in {guild_id}", exc_info=True)

	@commands.Cog.listener()
	async def on_raw_reaction_clear(self, payload: discord.RawReactionClearEvent) -> None:
		await self._cleared(payload.guild_id, payload.channel_id, payload.message_id, None)

	@commands.Cog.listener()
	async def on_raw_reaction_clear_emoji(self, payload: discord.RawReactionClearEmojiEvent) -> None:
		emoji = emoji_key(payload.emoji)
		if payload.guild_id is not None and self.boards(payload.guild_id, emoji):
			await self._cleared(payload.guild_id, payload.channel_id, payload.message_id, emoji)

	async def _cleared(self, guild_id: int | None, channel_id: int, message_id: int, emoji: str | None) -> None:
		"""Take down the posts of an original whose reactions were cleared. Clearing a post's reactions does nothing."""
		if guild_id is None or not self.boards(guild_id) or channel_id in self._board_channels(guild_id):
			return
		guild = self.bot.get_guild(guild_id)
		if guild is None:
			return
		try:
			await self._delete_posts(guild, await self.bot.api.starboard.clear(guild_id, message_id, emoji))
		except ApiUnavailable:
			logger.warning(f"Couldn't clear the stars of {message_id} in {guild_id}", exc_info=True)

	# Boards that can't work any more

	@commands.Cog.listener()
	async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
		for board in self.boards(channel.guild.id):
			if board.enabled and board.channel_id == channel.id:
				await self.disable(channel.guild.id, board.name, f"channel {channel.id} was deleted")

	@commands.Cog.listener()
	async def on_guild_emojis_update(
		self, guild: discord.Guild, before: list[discord.Emoji], after: list[discord.Emoji]
	) -> None:
		remaining = {str(emoji.id) for emoji in after}
		for board in self.boards(guild.id):
			if board.enabled and board.emoji.isdigit() and board.emoji not in remaining:
				await self.disable(guild.id, board.name, f"emoji {board.emoji} was deleted")


async def setup(bot: Bot) -> None:
	await bot.add_cog(Starboards(bot))
