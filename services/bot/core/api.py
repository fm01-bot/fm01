"""The API client: the bot's typed wrapper around the Internal API.

Error codes become `InsufficientFunds` or `ValueError`. Transport failures become `ApiUnavailable`.
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

import aiohttp
from pydantic import BaseModel, TypeAdapter, ValidationError

from api import (
	AddMoneyRequest,
	Balance,
	BearTrapChannel,
	BearTrapKicks,
	BearTrapMessage,
	BearTrapState,
	ClearStars,
	ErrorBody,
	ErrorCode,
	GuildBearTrap,
	GuildLocale,
	GuildPrefix,
	GuildStarboards,
	LeaderboardEntry,
	LocaleOverride,
	MessageIds,
	MoveRequest,
	Prefix,
	RemoveMoneyRequest,
	Starboard,
	StarboardEntry,
	StarboardPost,
	StarboardUpdate,
	StarChange,
	StarredMessage,
	StarResult,
	StarSeed,
	TransferRequest,
	Wallet,
)

__all__ = (
	"ApiClient",
	"ApiError",
	"ApiUnavailable",
	"BearTrapApi",
	"EconomyApi",
	"InsufficientFunds",
	"SettingsApi",
	"StarboardApi",
)

logger = logging.getLogger(__name__)

M = TypeVar("M")

ORIGIN_HEADER = "X-Fm01-Origin"


class ApiUnavailable(Exception):
	"""The API couldn't be reached or failed. The operation's outcome is unknown."""


class ApiError(Exception):
	"""The API refused the request for a reason the caller didn't expect.

	Args:
		status: The HTTP status.
		body: The error the API returned.
	"""

	def __init__(self, status: int, body: ErrorBody) -> None:
		super().__init__(f"{status} {body.code}: {body.message}")
		self.status = status
		self.code = body.code
		self.message = body.message


class InsufficientFunds(Exception):
	"""The wallet doesn't hold enough money for the operation."""


class ApiClient:
	"""One HTTP session to the Internal API, shared by every cog.

	Args:
		base_url: The API's base URL, e.g. ``http://api:8000``.
		token: ``API_INTERNAL_TOKEN``.
		origin: This bot instance's ID, sent as ``X-Fm01-Origin``.
		timeout: Seconds before a request counts as failed.
	"""

	def __init__(self, base_url: str, token: str, origin: str, *, timeout: float = 10) -> None:
		self._base = base_url.rstrip("/") + "/internal"
		self._headers = {"Authorization": f"Bearer {token}", ORIGIN_HEADER: origin}
		self._timeout = aiohttp.ClientTimeout(total=timeout)
		self._session: aiohttp.ClientSession | None = None
		self.economy = EconomyApi(self)
		self.settings = SettingsApi(self)
		self.bear_trap = BearTrapApi(self)
		self.starboard = StarboardApi(self)

	async def close(self) -> None:
		"""Close the HTTP session. The next request opens a new one."""
		if self._session and not self._session.closed:
			await self._session.close()

	async def request(
		self, method: str, path: str, result: type[M], *, body: BaseModel | None = None, **params: Any
	) -> M:
		"""Send one request and parse the response.

		Args:
			method: The HTTP method.
			path: The path under ``/internal``.
			result: The type to parse the response as.
			body: The JSON body, if any.
			**params: Query parameters.

		Returns:
			The parsed response.

		Raises:
			ApiUnavailable: The API couldn't be reached, failed (5xx), or answered with something unparsable.
			InsufficientFunds: The API answered ``insufficient_funds``.
			ValueError: The API answered ``same_account`` or ``invalid_request``.
			ApiError: Any other refusal.
		"""
		data = await self.send(method, path, body=body, **params)
		try:
			return TypeAdapter(result).validate_json(data)
		except ValidationError as exc:
			raise ApiUnavailable(f"{method} {path}: unexpected response") from exc

	async def send(
		self, method: str, path: str, *, body: BaseModel | None = None, exclude_unset: bool = False, **params: Any
	) -> bytes:
		"""Send one request without parsing the response.

		Args:
			method: The HTTP method.
			path: The path under ``/internal``.
			body: The JSON body, if any.
			exclude_unset: Leave fields out of ``body`` that weren't set, for partial updates (``PATCH``).
			**params: Query parameters.

		Returns:
			The raw response body.

		Raises:
			ApiUnavailable: The API couldn't be reached or failed (5xx).
			InsufficientFunds: The API answered ``insufficient_funds``.
			ValueError: The API answered ``same_account`` or ``invalid_request``.
			ApiError: Any other refusal.
		"""
		if self._session is None or self._session.closed:
			self._session = aiohttp.ClientSession(headers=self._headers, timeout=self._timeout)
		payload = body.model_dump(mode="json", exclude_unset=exclude_unset) if body is not None else None
		try:
			async with self._session.request(method, self._base + path, json=payload, params=params or None) as resp:
				data = await resp.read()
				status = resp.status
		except (aiohttp.ClientError, TimeoutError) as exc:
			raise ApiUnavailable(f"{method} {path}: {exc!r}") from exc

		if status >= 500:
			raise ApiUnavailable(f"{method} {path}: HTTP {status}")
		if status >= 400:
			raise _refusal(status, data, f"{method} {path}")
		return data


def _refusal(status: int, data: bytes, what: str) -> Exception:
	"""Map a 4xx response to an exception.

	Args:
		status: The HTTP status.
		data: The response body.
		what: The method and path, for messages.

	Returns:
		The exception to raise. See `ApiClient.send`.
	"""
	try:
		body = ErrorBody.model_validate_json(data)
	except ValidationError:
		return ApiUnavailable(f"{what}: HTTP {status} without an error body")
	match body.code:
		case ErrorCode.INSUFFICIENT_FUNDS:
			return InsufficientFunds()
		case ErrorCode.SAME_ACCOUNT | ErrorCode.INVALID_REQUEST:
			return ValueError(body.message)
		case ErrorCode.UNAUTHORIZED:
			logger.error("The API rejected API_INTERNAL_TOKEN")
			return ApiUnavailable(f"{what}: {body.message}")
		case _:
			return ApiError(status, body)


class EconomyApi:
	"""The Ledger's operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def balance(self, guild_id: int, user_id: int) -> Balance:
		"""Get a member's balance.

		Args:
			guild_id: The guild the account belongs to.
			user_id: The member.

		Returns:
			The balance. All zero if the member has no account.
		"""
		return await self._client.request("GET", f"/guilds/{guild_id}/economy/accounts/{user_id}", Balance)

	async def add_money(self, guild_id: int, user_id: int, amount: int, wallet: Wallet = "cash") -> Balance:
		"""Add money to a member's wallet, paying off debt first.

		Args:
			guild_id: The guild the account belongs to.
			user_id: The member to pay.
			amount: How much to add. Positive.
			wallet: The wallet the money goes to.

		Returns:
			The new balance.
		"""
		body = AddMoneyRequest(user_id=user_id, amount=amount, wallet=wallet)
		return await self._client.request("POST", f"/guilds/{guild_id}/economy/add-money", Balance, body=body)

	async def remove_money(self, guild_id: int, user_id: int, amount: int, wallet: Wallet = "cash") -> Balance:
		"""Take money from a member's account.

		Args:
			guild_id: The guild the account belongs to.
			user_id: The member to charge.
			amount: How much to take. Positive.
			wallet: The wallet the money comes from. The bank may go negative.

		Returns:
			The new balance.

		Raises:
			InsufficientFunds: ``wallet`` is ``"cash"`` and the member holds less than ``amount``.
		"""
		body = RemoveMoneyRequest(user_id=user_id, amount=amount, wallet=wallet)
		return await self._client.request("POST", f"/guilds/{guild_id}/economy/remove-money", Balance, body=body)

	async def move(self, guild_id: int, user_id: int, amount: int, source: Wallet, target: Wallet) -> Balance:
		"""Move money between a member's own wallets (deposit or withdraw).

		Args:
			guild_id: The guild the account belongs to.
			user_id: The member.
			amount: How much to move. Positive.
			source: The wallet the money leaves.
			target: The wallet the money reaches.

		Returns:
			The new balance.

		Raises:
			InsufficientFunds: ``source`` holds less than ``amount``.
		"""
		body = MoveRequest(user_id=user_id, amount=amount, source=source, target=target)
		return await self._client.request("POST", f"/guilds/{guild_id}/economy/move", Balance, body=body)

	async def transfer(self, guild_id: int, sender_id: int, recipient_id: int, amount: int) -> None:
		"""Give cash from one member to another. If it fails, neither balance changes.

		Args:
			guild_id: The guild both accounts belong to.
			sender_id: The member who pays.
			recipient_id: The member who receives.
			amount: How much cash to give. Positive.

		Raises:
			ValueError: The sender is the recipient.
			InsufficientFunds: The sender holds less cash than ``amount``.
		"""
		if sender_id == recipient_id:
			raise ValueError("cannot transfer to the same account")
		body = TransferRequest(sender_id=sender_id, recipient_id=recipient_id, amount=amount)
		await self._client.send("POST", f"/guilds/{guild_id}/economy/transfer", body=body)

	async def leaderboard(self, guild_id: int, limit: int = 10) -> list[LeaderboardEntry]:
		"""List a guild's richest members.

		Args:
			guild_id: The guild.
			limit: The most members to return, up to 100.

		Returns:
			Members by cash plus bank, richest first.
		"""
		return await self._client.request(
			"GET", f"/guilds/{guild_id}/economy/leaderboard", list[LeaderboardEntry], limit=limit
		)


class SettingsApi:
	"""Guild settings operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def prefix(self, guild_id: int) -> Prefix:
		"""Get a guild's prefix.

		Args:
			guild_id: The guild.

		Returns:
			The prefix. The default prefix for a new guild.
		"""
		return await self._client.request("GET", f"/guilds/{guild_id}/settings/prefix", Prefix)

	async def set_prefix(self, guild_id: int, value: Prefix) -> None:
		"""Set a guild's prefix.

		Args:
			guild_id: The guild.
			value: The new prefix.
		"""
		await self._client.send("PUT", f"/guilds/{guild_id}/settings/prefix", body=value)

	async def all_prefixes(self) -> list[GuildPrefix]:
		"""List every guild's prefix.

		Returns:
			The prefix of every guild the API knows.
		"""
		return await self._client.request("GET", "/settings/prefix", list[GuildPrefix])

	async def locale(self, guild_id: int) -> str | None:
		"""Get a guild's locale override.

		Args:
			guild_id: The guild.

		Returns:
			The locale. ``None`` if there is no override.
		"""
		return (await self._client.request("GET", f"/guilds/{guild_id}/settings/locale", LocaleOverride)).locale

	async def set_locale(self, guild_id: int, locale: str | None) -> None:
		"""Set a guild's locale override.

		Args:
			guild_id: The guild.
			locale: The locale. ``None`` removes the override.
		"""
		body = LocaleOverride(locale=locale)
		await self._client.send("PUT", f"/guilds/{guild_id}/settings/locale", body=body)

	async def all_locales(self) -> dict[int, str | None]:
		"""List every guild's locale override.

		Returns:
			The locale of every guild with an override, by guild ID.
		"""
		entries = await self._client.request("GET", "/settings/locale", list[GuildLocale])
		return {entry.guild_id: entry.locale for entry in entries}


class BearTrapApi:
	"""Bear trap operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def get(self, guild_id: int) -> BearTrapState:
		"""Get a guild's bear trap.

		Args:
			guild_id: The guild.

		Returns:
			The trap. Off with no kicks if the guild never set one.
		"""
		return await self._client.request("GET", f"/guilds/{guild_id}/settings/bear-trap", BearTrapState)

	async def all(self) -> dict[int, BearTrapState]:
		"""List every guild whose trap is on or still has a message posted.

		Returns:
			The traps, by guild ID.
		"""
		entries = await self._client.request("GET", "/settings/bear-trap", list[GuildBearTrap])
		return {
			entry.guild_id: BearTrapState.model_validate(entry.model_dump(exclude={"guild_id"})) for entry in entries
		}

	async def set_channel(self, guild_id: int, channel_id: int | None) -> BearTrapState:
		"""Set a guild's bear trap channel.

		Args:
			guild_id: The guild.
			channel_id: The channel. ``None`` turns the trap off.

		Returns:
			The stored trap.
		"""
		body = BearTrapChannel(channel_id=channel_id)
		return await self._client.request("PUT", f"/guilds/{guild_id}/settings/bear-trap", BearTrapState, body=body)

	async def set_message(self, guild_id: int, channel_id: int | None, message_id: int | None) -> BearTrapState:
		"""Record the trap message the bot posted.

		Args:
			guild_id: The guild.
			channel_id: The message's channel. ``None`` with ``message_id`` records that there is no message.
			message_id: The message.

		Returns:
			The stored trap.
		"""
		body = BearTrapMessage(message_channel_id=channel_id, message_id=message_id)
		return await self._client.request(
			"PUT", f"/guilds/{guild_id}/settings/bear-trap/message", BearTrapState, body=body
		)

	async def add_kick(self, guild_id: int) -> int:
		"""Count one more member the trap soft-banned.

		Args:
			guild_id: The guild.

		Returns:
			The new count.
		"""
		return (await self._client.request("POST", f"/guilds/{guild_id}/settings/bear-trap/kicks", BearTrapKicks)).kicks


class StarboardApi:
	"""Starboard operations: boards, stars and the bot's posts. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def boards(self, guild_id: int) -> list[Starboard]:
		"""List a guild's boards.

		Args:
			guild_id: The guild.

		Returns:
			The boards, by name.
		"""
		return await self._client.request("GET", f"/guilds/{guild_id}/settings/starboards", list[Starboard])

	async def all(self) -> dict[int, list[Starboard]]:
		"""List the boards of every guild that has any.

		Returns:
			The boards, by guild ID.
		"""
		entries = await self._client.request("GET", "/settings/starboards", list[GuildStarboards])
		return {entry.guild_id: entry.boards for entry in entries}

	async def create(self, guild_id: int, board: Starboard) -> Starboard:
		"""Add a board to a guild.

		Args:
			guild_id: The guild.
			board: The board.

		Returns:
			The stored board.

		Raises:
			ApiError: ``starboard_limit``, ``starboard_name_taken`` or ``starboard_tier_taken``.
		"""
		return await self._client.request("POST", f"/guilds/{guild_id}/settings/starboards", Starboard, body=board)

	async def update(self, guild_id: int, name: str, changes: StarboardUpdate) -> Starboard:
		"""Change a board. Fields not set on ``changes`` keep their value.

		Args:
			guild_id: The guild.
			name: The board.
			changes: The changes.

		Returns:
			The stored board.

		Raises:
			ApiError: ``not_found``, ``starboard_name_taken`` or ``starboard_tier_taken``.
		"""
		path = f"/guilds/{guild_id}/settings/starboards/{name}"
		data = await self._client.send("PATCH", path, body=changes, exclude_unset=True)
		return Starboard.model_validate_json(data)

	async def delete(self, guild_id: int, name: str) -> None:
		"""Remove a board with its entries and blocks.

		Args:
			guild_id: The guild.
			name: The board.

		Raises:
			ApiError: ``not_found`` if the guild has no such board.
		"""
		await self._client.send("DELETE", f"/guilds/{guild_id}/settings/starboards/{name}")

	async def star(
		self, guild_id: int, message_id: int, emoji: str, user_id: int, starred: bool
	) -> StarredMessage | None:
		"""Add or remove one member's star on a message, or on one of its posts.

		Args:
			guild_id: The guild.
			message_id: The message reacted to.
			emoji: The board emoji.
			user_id: The member.
			starred: Whether the reaction was added.

		Returns:
			The original's stars and entries, or ``None`` if the API has never seen the message.
		"""
		body = StarChange(message_id=message_id, emoji=emoji, user_id=user_id, starred=starred)
		return (
			await self._client.request("POST", f"/guilds/{guild_id}/starboard/stars", StarResult, body=body)
		).message

	async def seed(self, guild_id: int, seed: StarSeed) -> StarredMessage:
		"""Record everyone who starred a message with an emoji, as read from Discord.

		Args:
			guild_id: The guild.
			seed: The message and its starrers.

		Returns:
			The message's stars and entries.
		"""
		return await self._client.request("POST", f"/guilds/{guild_id}/starboard/seeds", StarredMessage, body=seed)

	async def set_post(self, guild_id: int, post: StarboardPost) -> StarboardEntry:
		"""Record the post the bot made for a message on a board, or that it removed it.

		Args:
			guild_id: The guild.
			post: The post. ``None`` fields record that there is none.

		Returns:
			The message's entry on the board.
		"""
		return await self._client.request("PUT", f"/guilds/{guild_id}/starboard/posts", StarboardEntry, body=post)

	async def posts_deleted(self, guild_id: int, post_ids: list[int]) -> list[StarboardEntry]:
		"""Block the messages whose posts someone other than the bot deleted.

		Args:
			guild_id: The guild.
			post_ids: Messages deleted in board channels, at most 100.

		Returns:
			The entries now blocked.
		"""
		body = MessageIds(message_ids=post_ids)
		return await self._client.request(
			"POST", f"/guilds/{guild_id}/starboard/posts/deleted", list[StarboardEntry], body=body
		)

	async def messages_deleted(self, guild_id: int, message_ids: list[int]) -> list[StarboardEntry]:
		"""Forget deleted originals.

		Args:
			guild_id: The guild.
			message_ids: The deleted messages, at most 100.

		Returns:
			The entries that had a post, which the caller deletes.
		"""
		body = MessageIds(message_ids=message_ids)
		return await self._client.request(
			"POST", f"/guilds/{guild_id}/starboard/messages/deleted", list[StarboardEntry], body=body
		)

	async def clear(self, guild_id: int, message_id: int, emoji: str | None) -> list[StarboardEntry]:
		"""Forget a message's stars after its reactions were cleared.

		Args:
			guild_id: The guild.
			message_id: The original.
			emoji: The emoji cleared. ``None`` for all of them.

		Returns:
			The entries that had a post, which the caller deletes.
		"""
		return await self._client.request(
			"POST",
			f"/guilds/{guild_id}/starboard/messages/{message_id}/clear",
			list[StarboardEntry],
			body=ClearStars(emoji=emoji),
		)
