"""The Discord REST calls the dashboard needs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from api import DashboardUser, ErrorCode

from app.errors import ApiError

__all__ = ("REQUIRED_SCOPES", "DiscordClient", "OAuthTokenSet")

REQUIRED_SCOPES = frozenset({"identify", "guilds"})


@dataclass(frozen=True, slots=True)
class OAuthTokenSet:
	"""A user's Discord OAuth2 tokens."""

	access_token: str
	refresh_token: str
	expires_at: datetime
	scopes: frozenset[str]


class DiscordClient:
	"""Calls Discord as the bot or as a signed-in user.

	Every method raises ``discord_unavailable`` if Discord fails.

	Args:
		http: The shared HTTP client.
		base_url: Discord's REST base URL.
		client_id: The OAuth2 application ID.
		client_secret: The OAuth2 client secret.
		bot_token: The bot's token.
	"""

	def __init__(self, http: httpx.AsyncClient, base_url: str, client_id: str, client_secret: str, bot_token: str):
		self._http = http
		self._base = base_url.rstrip("/")
		self._client_id = client_id
		self._client_secret = client_secret
		self._bot_token = bot_token

	async def exchange_code(self, code: str, redirect_uri: str) -> OAuthTokenSet:
		"""Trade an OAuth2 authorization code for the user's tokens.

		Args:
			code: The code Discord gave the dashboard.
			redirect_uri: The redirect URI the code was issued for.

		Returns:
			The user's tokens.

		Raises:
			ApiError: ``unauthorized`` if the code is bad, expired or already used.
		"""
		return await self._token({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri})

	async def refresh(self, refresh_token: str) -> OAuthTokenSet:
		"""Get new tokens with a refresh token.

		Args:
			refresh_token: The refresh token.

		Raises:
			ApiError: ``unauthorized`` if the refresh token is no longer valid.
		"""
		return await self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})

	async def revoke(self, token: str) -> None:
		"""Revoke a token at Discord. Ignores failures.

		Args:
			token: The access or refresh token.
		"""
		try:
			await self._http.post(
				f"{self._base}/oauth2/token/revoke",
				data={"token": token},
				auth=(self._client_id, self._client_secret),
			)
		except httpx.HTTPError:
			pass

	async def current_user(self, access_token: str) -> DashboardUser:
		"""Get the profile of an access token's user.

		Returns:
			The user's profile.

		Raises:
			ApiError: ``unauthorized`` if Discord rejects the token.
		"""
		data = await self._get("/users/@me", f"Bearer {access_token}", user_call=True)
		return DashboardUser(
			id=data["id"], username=data["username"], global_name=data.get("global_name"), avatar=data.get("avatar")
		)

	async def current_user_guilds(self, access_token: str) -> list[dict[str, Any]]:
		"""List the guilds of an access token's user.

		Args:
			access_token: The user's access token.

		Returns:
			Discord's guild objects, each with ``id``, ``name``, ``icon``, ``owner`` and ``permissions``.

		Raises:
			ApiError: ``unauthorized`` if Discord rejects the token.
		"""
		return await self._get("/users/@me/guilds", f"Bearer {access_token}", user_call=True)

	async def bot_in_guild(self, guild_id: int) -> bool:
		"""Check whether the bot is a member of a guild.

		Returns:
			Whether the bot is a member of the guild.

		Raises:
			ApiError: ``discord_unavailable`` if Discord fails.
		"""
		try:
			await self._get(f"/guilds/{guild_id}", f"Bot {self._bot_token}", user_call=False)
		except ApiError as exc:
			# Discord answers 403 (Missing Access) for a guild the bot isn't in, and 404 for an unknown guild.
			if exc.code in (ErrorCode.FORBIDDEN, ErrorCode.NOT_FOUND):
				return False
			raise
		return True

	async def guild_channel(self, guild_id: int, channel_id: int) -> dict[str, Any] | None:
		"""Look up a channel as the bot, if it belongs to a guild.

		Args:
			guild_id: The guild the channel must belong to.
			channel_id: The channel.

		Returns:
			Discord's channel object, or ``None`` if the bot can't see the channel or it belongs to another guild.

		Raises:
			ApiError: ``discord_unavailable`` if Discord fails.
		"""
		try:
			channel = await self._get(f"/channels/{channel_id}", f"Bot {self._bot_token}", user_call=False)
		except ApiError as exc:
			if exc.code in (ErrorCode.FORBIDDEN, ErrorCode.NOT_FOUND):
				return None
			raise
		return channel if str(channel.get("guild_id")) == str(guild_id) else None

	async def guild_emoji(self, guild_id: int, emoji_id: int) -> dict[str, Any] | None:
		"""Look up a custom emoji of a guild as the bot.

		Args:
			guild_id: The guild.
			emoji_id: The emoji.

		Returns:
			Discord's emoji object, or ``None`` if the guild has no such emoji.

		Raises:
			ApiError: ``discord_unavailable`` if Discord fails.
		"""
		try:
			return await self._get(f"/guilds/{guild_id}/emojis/{emoji_id}", f"Bot {self._bot_token}", user_call=False)
		except ApiError as exc:
			if exc.code in (ErrorCode.FORBIDDEN, ErrorCode.NOT_FOUND):
				return None
			raise

	async def _token(self, form: dict[str, str]) -> OAuthTokenSet:
		"""Call the OAuth2 token endpoint.

		Args:
			form: The token request body: ``grant_type`` and the fields that grant needs.

		Returns:
			The tokens Discord returned.

		Raises:
			ApiError: ``unauthorized`` if Discord answers 400 or 401.
		"""
		try:
			response = await self._http.post(
				f"{self._base}/oauth2/token", data=form, auth=(self._client_id, self._client_secret)
			)
		except httpx.HTTPError as exc:
			raise ApiError(ErrorCode.DISCORD_UNAVAILABLE, "Discord could not be reached") from exc
		if response.status_code in (400, 401):
			raise ApiError(ErrorCode.UNAUTHORIZED, "Discord rejected the authorization")
		if response.is_error:
			raise ApiError(ErrorCode.DISCORD_UNAVAILABLE, f"Discord answered {response.status_code}")
		data = response.json()
		return OAuthTokenSet(
			access_token=data["access_token"],
			refresh_token=data["refresh_token"],
			expires_at=datetime.now(UTC) + timedelta(seconds=int(data["expires_in"])),
			scopes=frozenset(str(data.get("scope", "")).split()),
		)

	async def _get(self, path: str, authorization: str, *, user_call: bool) -> Any:
		"""Send a GET request to Discord.

		Args:
			path: The path under the base URL.
			authorization: The ``Authorization`` header value.
			user_call: Whether the call uses a user's token instead of the bot's.

		Returns:
			The JSON body.

		Raises:
			ApiError: ``unauthorized`` on a 401 for user calls. ``forbidden`` on a 403 and ``not_found`` on a 404 for
				bot calls.
		"""
		try:
			response = await self._http.get(f"{self._base}{path}", headers={"Authorization": authorization})
		except httpx.HTTPError as exc:
			raise ApiError(ErrorCode.DISCORD_UNAVAILABLE, "Discord could not be reached") from exc
		if response.status_code == 401 and user_call:
			raise ApiError(ErrorCode.UNAUTHORIZED, "Discord no longer accepts this sign-in")
		if response.status_code == 403 and not user_call:
			raise ApiError(ErrorCode.FORBIDDEN, "Discord denied the bot access")
		if response.status_code == 404 and not user_call:
			raise ApiError(ErrorCode.NOT_FOUND)
		if response.is_error:
			raise ApiError(ErrorCode.DISCORD_UNAVAILABLE, f"Discord answered {response.status_code}")
		return response.json()
