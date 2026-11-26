"""Suggestions: members post ideas to a channel and the server votes on them with buttons.

The setting, the suggestions, their votes and their decisions live behind the API (`SuggestionsApi`). The vote buttons
are `DynamicItem`s whose custom ID carries the suggestion's number, so they keep working after a restart and any bot
instance can handle a click.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord
from core import Bot, Context, command, group
from core.api import ApiClient, SuggestionClosed, SuggestionsDisabled
from core.context import VALID_SEND_KWARGS
from core.settings import GuildSetting, GuildSettings
from discord.ext import commands

from api import (
	MAX_SUGGESTION_LENGTH,
	MAX_SUGGESTION_REASON_LENGTH,
	SUGGESTIONS_SETTING,
	DecisionStatus,
	Suggestion,
	SuggestionConfig,
	Vote,
)

__all__ = (
	"REQUIRED_PERMISSIONS",
	"SuggestionVoteButton",
	"Suggestions",
	"missing_permissions",
	"suggestion_view",
	"suggestions_setting",
)

logger = logging.getLogger(__name__)

REQUIRED_PERMISSIONS = ("view_channel", "send_messages", "embed_links")
"""Permissions the bot needs in the suggestions channel to post suggestions."""

THREAD_NAME_LENGTH = 100
"""Discord's longest thread name."""

VOTE_EMOJI = {Vote.UP: "👍", Vote.DOWN: "👎"}
VOTE_STYLE = {Vote.UP: discord.ButtonStyle.success, Vote.DOWN: discord.ButtonStyle.danger}


def suggestions_setting(settings: GuildSettings, api: ApiClient) -> GuildSetting[SuggestionConfig]:
	"""Register the suggestions setting, stored behind the API and loaded on first use.

	Args:
		settings: The registry to add it to.
		api: The API client it loads and saves through.

	Returns:
		The setting. A guild that never configured suggestions has the default, which is off.
	"""
	return settings.add_remote(SUGGESTIONS_SETTING, api.suggestions.config, api.suggestions.set_config)


def missing_permissions(channel: discord.TextChannel) -> list[str]:
	"""List the permissions the bot lacks to post suggestions in a channel.

	Args:
		channel: The suggestions channel.

	Returns:
		The missing `REQUIRED_PERMISSIONS`.
	"""
	permissions = channel.permissions_for(channel.guild.me)
	return [name for name in REQUIRED_PERMISSIONS if not getattr(permissions, name)]


class SuggestionVoteButton(
	discord.ui.DynamicItem[discord.ui.Button], template=r"suggestion:(?P<number>\d+):(?P<vote>up|down)"
):
	"""A suggestion's up or down button, showing how many members voted that way.

	Args:
		number: The suggestion's number in its guild.
		vote: The vote the button casts.
		count: How many members voted that way.
		disabled: Whether voting is closed.
	"""

	def __init__(self, number: int, vote: Vote, count: int = 0, *, disabled: bool = False) -> None:
		super().__init__(
			discord.ui.Button(
				style=VOTE_STYLE[vote],
				emoji=VOTE_EMOJI[vote],
				label=str(count),
				custom_id=f"suggestion:{number}:{vote.value}",
				disabled=disabled,
			)
		)
		self.number = number
		self.vote = vote

	@classmethod
	async def from_custom_id(
		cls, interaction: discord.Interaction, item: discord.ui.Item[Any], match: re.Match[str], /
	) -> SuggestionVoteButton:
		return cls(int(match["number"]), Vote(match["vote"]))

	async def callback(self, interaction: discord.Interaction) -> None:
		client = interaction.client
		cog = client.get_cog("Suggestions") if isinstance(client, Bot) else None
		if isinstance(cog, Suggestions):
			await cog.handle_vote(interaction, self.number, self.vote)


def suggestion_view(number: int, up: int, down: int, *, closed: bool = False) -> discord.ui.View:
	"""Build a suggestion's vote buttons.

	Args:
		number: The suggestion's number in its guild.
		up: How many members voted up.
		down: How many members voted down.
		closed: Whether the suggestion is decided, so the buttons are disabled.

	Returns:
		The view. The caller stops it once sent: the dynamic items handle the clicks.
	"""
	view = discord.ui.View(timeout=None)
	view.add_item(SuggestionVoteButton(number, Vote.UP, up, disabled=closed))
	view.add_item(SuggestionVoteButton(number, Vote.DOWN, down, disabled=closed))
	return view


def _send_kwargs(payload: Any) -> dict[str, Any]:
	if isinstance(payload, dict):
		return {k: v for k, v in payload.items() if k in VALID_SEND_KWARGS}
	return {"content": str(payload)}


class Suggestions(commands.Cog, name="Suggestions"):
	def __init__(self, bot: Bot) -> None:
		self.bot = bot
		self.setting = suggestions_setting(bot.settings, bot.api)

	async def cog_load(self) -> None:
		self.bot.add_dynamic_items(SuggestionVoteButton)

	async def cog_unload(self) -> None:
		self.bot.remove_dynamic_items(SuggestionVoteButton)

	async def _layout(self, guild: discord.Guild, suggestion: Suggestion) -> dict[str, Any]:
		"""Render a suggestion's embed and vote buttons.

		Args:
			guild: The guild, for its locale.
			suggestion: The suggestion.

		Returns:
			The keyword arguments to send or edit the suggestion's message with.
		"""
		decision = suggestion.decision
		payload = await self.bot.custom_response.get_message(
			f"suggestions.message.{decision.status.value if decision else 'open'}",
			guild,
			number=suggestion.number,
			content=suggestion.content,
			author_id=suggestion.author_id,
			moderator_id=decision.moderator_id if decision else None,
			reason=decision.reason if decision else None,
		)
		kwargs = _send_kwargs(payload)
		kwargs["view"] = suggestion_view(suggestion.number, suggestion.up, suggestion.down, closed=decision is not None)
		return kwargs

	async def _open_thread(self, guild: discord.Guild, message: discord.Message, number: int) -> None:
		name = await self.bot.custom_response.get_message("suggestions.thread_name", guild, number=number)
		try:
			await message.create_thread(name=str(name)[:THREAD_NAME_LENGTH])
		except discord.HTTPException:
			logger.warning(f"Couldn't open a thread for suggestion {number} in {guild.id}", exc_info=True)

	@command(user=False)
	async def suggest(self, ctx: Context, *, content: commands.Range[str, 1, MAX_SUGGESTION_LENGTH]) -> None:
		assert ctx.guild is not None
		config = await self.setting.get(ctx.guild.id)
		channel = ctx.guild.get_channel(config.channel_id) if config.channel_id else None
		if channel is None:
			await ctx.send("suggestions.errors.disabled")
			return
		if not isinstance(channel, discord.TextChannel) or missing_permissions(channel):
			await ctx.send("suggestions.errors.cannot_post")
			return

		try:
			suggestion = await self.bot.api.suggestions.create(ctx.guild.id, ctx.author.id, content)
		except SuggestionsDisabled:
			await ctx.send("suggestions.errors.disabled")
			return

		kwargs = await self._layout(ctx.guild, suggestion)
		try:
			message = await channel.send(**kwargs)
		except discord.HTTPException:
			logger.warning(f"Couldn't post suggestion {suggestion.number} in {ctx.guild.id}", exc_info=True)
			await ctx.send("suggestions.errors.cannot_post")
			return
		finally:
			kwargs["view"].stop()

		await self.bot.api.suggestions.set_message(ctx.guild.id, suggestion.number, channel.id, message.id)
		if config.threads:
			await self._open_thread(ctx.guild, message, suggestion.number)
		await ctx.send("suggestions.suggest.success", url=message.jump_url)

	async def handle_vote(self, interaction: discord.Interaction, number: int, vote: Vote) -> None:
		"""Count a member's click on a vote button and show the new counts.

		Args:
			interaction: The button click.
			number: The suggestion's number in the guild.
			vote: The button's vote.
		"""
		if interaction.guild_id is None:
			return
		try:
			result = await self.bot.api.suggestions.vote(interaction.guild_id, number, interaction.user.id, vote)
		except SuggestionClosed:
			await self._respond(interaction, "suggestions.errors.closed", number=number)
			return
		if result is None:
			await self._respond(interaction, "suggestions.errors.not_found", number=number)
			return
		view = suggestion_view(number, result.up, result.down)
		try:
			await interaction.response.edit_message(view=view)
		finally:
			view.stop()

	async def _respond(self, interaction: discord.Interaction, key: str, **kwargs: Any) -> None:
		payload = _send_kwargs(await self.bot.custom_response.get_message(key, interaction, **kwargs))
		payload.setdefault("ephemeral", True)
		await interaction.response.send_message(**payload)

	@group(user=False, fallback=None, permissions=["manage_guild"], invoke_without_command=True)
	async def suggestion(self, ctx: Context) -> None:
		await ctx.send_help(ctx.command)

	@suggestion.command(l10n_key="suggestionapprove", user=False, permissions=["manage_guild"])
	async def approve(
		self,
		ctx: Context,
		number: commands.Range[int, 1],
		*,
		reason: commands.Range[str, 1, MAX_SUGGESTION_REASON_LENGTH] | None = None,
	) -> None:
		await self._decide(ctx, number, DecisionStatus.APPROVED, reason)

	@suggestion.command(l10n_key="suggestiondeny", user=False, permissions=["manage_guild"])
	async def deny(
		self,
		ctx: Context,
		number: commands.Range[int, 1],
		*,
		reason: commands.Range[str, 1, MAX_SUGGESTION_REASON_LENGTH] | None = None,
	) -> None:
		await self._decide(ctx, number, DecisionStatus.DENIED, reason)

	async def _decide(self, ctx: Context, number: int, status: DecisionStatus, reason: str | None) -> None:
		assert ctx.guild is not None
		suggestion = await self.bot.api.suggestions.decide(ctx.guild.id, number, ctx.author.id, status, reason)
		if suggestion is None:
			await ctx.send("suggestions.errors.not_found", number=number)
			return
		await self._update_message(ctx.guild, suggestion)
		await ctx.send(f"suggestions.decision.{status.value}", number=number)

	async def _update_message(self, guild: discord.Guild, suggestion: Suggestion) -> None:
		"""Re-render a suggestion's posted message, if it has one."""
		channel = guild.get_channel(suggestion.channel_id) if suggestion.channel_id else None
		if not isinstance(channel, discord.TextChannel) or suggestion.message_id is None:
			return
		kwargs = await self._layout(guild, suggestion)
		try:
			await channel.get_partial_message(suggestion.message_id).edit(
				embeds=kwargs["embeds"], view=kwargs["view"], allowed_mentions=kwargs.get("allowed_mentions")
			)
		except discord.HTTPException:
			logger.warning(
				f"Couldn't update the message of suggestion {suggestion.number} in {guild.id}", exc_info=True
			)
		finally:
			kwargs["view"].stop()


async def setup(bot: Bot) -> None:
	await bot.add_cog(Suggestions(bot))
