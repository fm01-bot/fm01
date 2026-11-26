from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.ext import commands, tasks
from helpers.alert_providers import get_provider

from api import MediaAlert

if TYPE_CHECKING:
	from args.media import Media
	from core.bot import Bot

logger = logging.getLogger(__name__)

# Baseline stored for live-only platforms (Twitch) when the alert's first check finds the account offline,
# so the next stream differs from the baseline and is announced.
OFFLINE_BASELINE = "offline"


class Alerts(commands.Cog, name="Alerts"):
	"""Social media upload and live stream alert monitoring system."""

	def __init__(self, client: Bot) -> None:
		self.client = client
		self.session: aiohttp.ClientSession | None = None

	async def cog_load(self) -> None:
		if not self.poll_loop.is_running():
			self.poll_loop.start()

	async def cog_unload(self) -> None:
		self.poll_loop.cancel()
		if self.session and not self.session.closed:
			await self.session.close()

	async def get_session(self) -> aiohttp.ClientSession:
		if self.session is None or self.session.closed:
			self.session = aiohttp.ClientSession()
		return self.session

	@tasks.loop(minutes=2)
	async def poll_loop(self) -> None:
		"""Periodically checks tracked channels across all platforms."""
		try:
			session = await self.get_session()
			for row in await self.client.api.alerts.accounts():
				try:
					await self.check_account(
						session=session,
						platform=row.platform,
						channel_account=row.channel_account,
						account_id=row.account_id or row.channel_account,
						account_name=row.account_name,
					)
				except Exception as e:  # noqa: BLE001
					logger.warning(f"Error checking {row.platform} account {row.channel_account}: {e}")
		except Exception as e:  # noqa: BLE001
			logger.error(f"Unhandled error in alert polling loop: {e}")

	@poll_loop.before_loop
	async def before_poll_loop(self) -> None:
		await self.client.wait_until_ready()

	async def check_account(
		self,
		session: aiohttp.ClientSession,
		platform: str,
		channel_account: str,
		account_id: str,
		account_name: str | None = None,
	) -> None:
		"""Fetches latest media for an account and dispatches alerts to subscribed guilds."""
		provider = get_provider(platform)
		if not provider:
			return

		media = await provider.fetch_latest(
			session=session,
			account_id=account_id,
			account_name=account_name,
			bot=self.client,
		)
		if not media:
			if provider.live_only:
				await self.client.api.alerts.set_baseline(platform, channel_account, account_id, OFFLINE_BASELINE)
			return

		alerts = await self.client.api.alerts.subscribers(platform, channel_account, account_id)

		for alert_row in alerts:
			last_id = alert_row.last_media_id
			if last_id == media.id:
				continue

			if last_id is None:
				# The first check only records a baseline, so older uploads are not announced.
				await self.client.api.alerts.set_last_media(alert_row.id, media.id)
				continue

			if await self.dispatch_alert(alert_row, media):
				await self.client.api.alerts.set_last_media(alert_row.id, media.id)

	async def dispatch_alert(self, alert_row: MediaAlert, media: Media) -> bool:
		"""Sends the alert for `media` to the alert's channel. Returns whether it was sent."""
		guild_id = alert_row.guild_id
		channel_id = alert_row.target_channel_id

		guild = self.client.get_guild(guild_id)
		if not guild:
			return False

		channel = guild.get_channel(channel_id)
		if not channel or not isinstance(channel, discord.abc.Messageable):
			return False

		try:
			localized_payload = await self.client.custom_response.get_message(
				f"alerts.{media.platform}",
				guild,
				media=media,
				convert_embeds=True,
				convert_components=True,
			)
			if isinstance(localized_payload, dict):
				content = localized_payload.get("content")
				embeds = localized_payload.get("embeds", [])
				view = localized_payload.get("view")
				await channel.send(content=content, embeds=embeds, view=view)
				return True
			if isinstance(localized_payload, str):
				await channel.send(content=localized_payload)
				return True
		except Exception as e:  # noqa: BLE001
			logger.debug(f"Failed to load localized alert message for {media.platform}: {e}")

		try:
			fallback_content = f"**{media.author.name}** posted an update!\n**{media.title}**\n{media.url}"
			await channel.send(content=fallback_content)
			return True
		except (discord.Forbidden, discord.HTTPException) as e:
			logger.warning(f"Could not send alert to channel {channel_id} in guild {guild_id}: {e}")
			return False


async def setup(client: Bot) -> None:
	await client.add_cog(Alerts(client))
