"""The API client: the bot's typed wrapper around the Internal API.

Error codes become `InsufficientFunds` or `ValueError`. Transport failures become `ApiUnavailable`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Sequence
from typing import Any, Literal, TypeVar

import aiohttp
from pydantic import BaseModel, RootModel, TypeAdapter, ValidationError

from api import (
	AddMoneyRequest,
	AfkMember,
	AfkToggle,
	AfkToggled,
	AlertAccount,
	AlertBaseline,
	AlertCreate,
	AlertEnabled,
	AlertMedia,
	AutoModConfig,
	Balance,
	BearTrapChannel,
	BearTrapKicks,
	BearTrapMessage,
	BearTrapState,
	BlacklistAdd,
	BlacklistEntry,
	BlacklistKind,
	CaseClosed,
	CaseCreate,
	CaseFilter,
	CaseRecord,
	CaseRetention,
	CaseUpdate,
	ClearStars,
	ErrorBody,
	ErrorCode,
	GiveawayCreate,
	GiveawayEntrants,
	GiveawayEntry,
	GiveawayEntryChange,
	GiveawayEntryCount,
	GiveawayMessage,
	GiveawayRecord,
	GiveawayStatus,
	GiveawayWinners,
	GreetingConfig,
	GreetingKind,
	GreetingUpdate,
	GuildBearTrap,
	GuildLocale,
	GuildLogConfig,
	GuildPrefix,
	GuildStarboards,
	Leaderboard,
	LeaderboardEntry,
	LevelConfig,
	LevelConfigUpdate,
	LevelOverrides,
	LevelOverrideUpdate,
	LevelReward,
	LocaleOverride,
	LogConfig,
	MediaAlert,
	MemberLevel,
	MessageCount,
	MessageIds,
	MoveRequest,
	OpenTicketCount,
	PendingCase,
	Prefix,
	RemovedAlerts,
	RemoveMoneyRequest,
	Retention,
	ShopItem,
	Snapshot,
	SnapshotCreate,
	Starboard,
	StarboardEntry,
	StarboardPost,
	StarboardUpdate,
	StarChange,
	StarredMessage,
	StarResult,
	StarSeed,
	Ticket,
	TicketClose,
	TicketConfig,
	TicketConfigUpdate,
	TicketOpen,
	TransferRequest,
	UserIds,
	Wallet,
	XpAward,
	XpResult,
)

__all__ = (
	"AfkApi",
	"AlertsApi",
	"ApiClient",
	"ApiError",
	"ApiUnavailable",
	"AutoModApi",
	"BearTrapApi",
	"BlacklistApi",
	"CasesApi",
	"EconomyApi",
	"GiveawaysApi",
	"GreetingsApi",
	"InsufficientFunds",
	"LevelsApi",
	"LogApi",
	"SettingsApi",
	"ShopApi",
	"SnapshotsApi",
	"StarboardApi",
	"TicketsApi",
)

logger = logging.getLogger(__name__)

M = TypeVar("M")

ORIGIN_HEADER = "X-Fm01-Origin"

SNAPSHOT_CODE = re.compile(r"[0-9A-Za-z-]{1,64}")
"""What a snapshot code can look like. Anything else can't be one, so it isn't sent."""


class MessageCounts(RootModel[list[MessageCount]]):
	"""A batch of giveaway message counts, as one request body."""


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
		self.greetings = GreetingsApi(self)
		self.automod = AutoModApi(self)
		self.log = LogApi(self)
		self.cases = CasesApi(self)
		self.tickets = TicketsApi(self)
		self.levels = LevelsApi(self)
		self.afk = AfkApi(self)
		self.snapshots = SnapshotsApi(self)
		self.shop = ShopApi(self)
		self.giveaways = GiveawaysApi(self)
		self.alerts = AlertsApi(self)
		self.blacklist = BlacklistApi(self)

	async def ping(self) -> None:
		"""Check that the API is up, e.g. to time a round trip.

		Raises:
			ApiUnavailable: The API couldn't be reached or isn't healthy.
		"""
		session = self._open()
		url = self._base.removesuffix("/internal") + "/health"
		try:
			async with session.get(url) as resp:
				status = resp.status
		except (aiohttp.ClientError, TimeoutError) as exc:
			raise ApiUnavailable(f"GET /health: {exc!r}") from exc
		if status != 200:
			raise ApiUnavailable(f"GET /health: HTTP {status}")

	def _open(self) -> aiohttp.ClientSession:
		"""Get the HTTP session, opening a new one if there is none.

		Returns:
			The session.
		"""
		if self._session is None or self._session.closed:
			self._session = aiohttp.ClientSession(headers=self._headers, timeout=self._timeout)
		return self._session

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
		session = self._open()
		payload = body.model_dump(mode="json", exclude_unset=exclude_unset) if body is not None else None
		try:
			async with session.request(method, self._base + path, json=payload, params=params or None) as resp:
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


async def _or_none[M](request: Awaitable[M]) -> M | None:
	"""Await a request, turning ``not_found`` into ``None``.

	Args:
		request: The request.

	Returns:
		The result, or ``None`` if the API answered ``not_found``.

	Raises:
		ApiError: Any other refusal.
	"""
	try:
		return await request
	except ApiError as exc:
		if exc.code is ErrorCode.NOT_FOUND:
			return None
		raise


class GreetingsApi:
	"""Join and leave message operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def get(self, kind: GreetingKind, guild_id: int) -> GreetingConfig | None:
		"""Get a guild's join or leave configuration.

		Args:
			kind: Join or leave messages.
			guild_id: The guild.

		Returns:
			The configuration, or ``None`` if the guild never configured it.
		"""
		return await self._client.request(
			"GET",
			f"/guilds/{guild_id}/settings/greetings/{kind}",
			GreetingConfig | None,  # ty: ignore[invalid-argument-type]
		)

	async def update(self, kind: GreetingKind, guild_id: int, changes: GreetingUpdate) -> GreetingConfig:
		"""Change a guild's join or leave configuration, creating it (on) if it doesn't exist.

		Args:
			kind: Join or leave messages.
			guild_id: The guild.
			changes: The changes. ``None`` fields keep their value.

		Returns:
			The stored configuration.
		"""
		return await self._client.request(
			"PATCH", f"/guilds/{guild_id}/settings/greetings/{kind}", GreetingConfig, body=changes
		)


class AutoModApi:
	"""AutoMod configuration operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def get(self, guild_id: int) -> AutoModConfig:
		"""Get a guild's AutoMod configuration.

		Args:
			guild_id: The guild.

		Returns:
			The configuration. Off with no settings if the guild never configured AutoMod.
		"""
		return await self._client.request("GET", f"/guilds/{guild_id}/settings/automod", AutoModConfig)

	async def set(self, guild_id: int, config: AutoModConfig) -> None:
		"""Replace a guild's AutoMod configuration.

		Args:
			guild_id: The guild.
			config: The configuration.
		"""
		await self._client.send("PUT", f"/guilds/{guild_id}/settings/automod", body=config)


class LogApi:
	"""Log configuration operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def get(self, guild_id: int) -> LogConfig | None:
		"""Get a guild's log configuration.

		Args:
			guild_id: The guild.

		Returns:
			The configuration, or ``None`` if the guild never configured logging.
		"""
		return await self._client.request(
			"GET",
			f"/guilds/{guild_id}/settings/log",
			LogConfig | None,  # ty: ignore[invalid-argument-type]
		)

	async def all(self) -> list[GuildLogConfig]:
		"""List every guild's log configuration.

		Returns:
			The configurations of every guild that configured logging.
		"""
		return await self._client.request("GET", "/settings/log", list[GuildLogConfig])

	async def set(self, guild_id: int, config: LogConfig) -> None:
		"""Replace a guild's log configuration.

		Args:
			guild_id: The guild.
			config: The configuration.
		"""
		await self._client.send("PUT", f"/guilds/{guild_id}/settings/log", body=config)

	async def delete(self, guild_id: int) -> None:
		"""Remove a guild's log configuration.

		Args:
			guild_id: The guild.
		"""
		await self._client.send("DELETE", f"/guilds/{guild_id}/settings/log")


class CasesApi:
	"""Moderation case and case retention operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def retention(self, guild_id: int) -> Retention:
		"""Get a guild's case retention.

		Args:
			guild_id: The guild.

		Returns:
			The retention. ``keep`` if the guild never set one.
		"""
		path = f"/guilds/{guild_id}/settings/case-retention"
		return (await self._client.request("GET", path, CaseRetention)).retention

	async def set_retention(self, guild_id: int, retention: Retention) -> None:
		"""Set a guild's case retention.

		Args:
			guild_id: The guild.
			retention: The retention.
		"""
		body = CaseRetention(retention=retention)
		await self._client.send("PUT", f"/guilds/{guild_id}/settings/case-retention", body=body)

	async def get(self, guild_id: int, case_id: int) -> CaseRecord | None:
		"""Get a case in a guild.

		Args:
			guild_id: The guild.
			case_id: The case.

		Returns:
			The case, or ``None`` if the guild has no such case.
		"""
		return await _or_none(self._client.request("GET", f"/guilds/{guild_id}/cases/{case_id}", CaseRecord))

	async def find(self, case_id: int) -> CaseRecord | None:
		"""Get a case in any guild.

		Args:
			case_id: The case.

		Returns:
			The case, or ``None`` if there is none.
		"""
		return await _or_none(self._client.request("GET", f"/cases/{case_id}", CaseRecord))

	async def for_user(
		self, guild_id: int, user_id: int, which: CaseFilter = "all", case_type: int | None = None
	) -> list[CaseRecord]:
		"""List a user's cases in a guild, oldest first.

		Args:
			guild_id: The guild.
			user_id: The user the cases are about.
			which: Which cases. See `CaseFilter`.
			case_type: Only cases of this type.

		Returns:
			The cases.
		"""
		params: dict[str, Any] = {"user_id": user_id, "which": which}
		if case_type is not None:
			params["type"] = case_type
		return await self._client.request("GET", f"/guilds/{guild_id}/cases", list[CaseRecord], **params)

	async def create(self, guild_id: int, case: CaseCreate) -> CaseRecord:
		"""Record a new case.

		Args:
			guild_id: The guild.
			case: The case.

		Returns:
			The stored case.
		"""
		return await self._client.request("POST", f"/guilds/{guild_id}/cases", CaseRecord, body=case)

	async def update(self, guild_id: int, case_id: int, changes: CaseUpdate) -> None:
		"""Set a case's reason, expiry and message.

		Args:
			guild_id: The guild.
			case_id: The case.
			changes: The new values.
		"""
		await self._client.send("PUT", f"/guilds/{guild_id}/cases/{case_id}", body=changes)

	async def close(self, guild_id: int, case_id: int) -> CaseClosed:
		"""Close a case following the guild's retention.

		Args:
			guild_id: The guild.
			case_id: The case.

		Returns:
			Whether the case was deleted or marked inactive.
		"""
		return await self._client.request("POST", f"/guilds/{guild_id}/cases/{case_id}/close", CaseClosed)

	async def delete(self, guild_id: int, case_id: int) -> None:
		"""Delete a case regardless of retention.

		Args:
			guild_id: The guild.
			case_id: The case.
		"""
		await self._client.send("DELETE", f"/guilds/{guild_id}/cases/{case_id}")

	async def pending(self) -> list[PendingCase]:
		"""List every open case that expires.

		Returns:
			The cases, with their guild and expiry.
		"""
		return await self._client.request("GET", "/cases/pending", list[PendingCase])


class TicketsApi:
	"""Support ticket and ticket configuration operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def config(self, guild_id: int) -> TicketConfig | None:
		"""Get a guild's ticket configuration.

		Args:
			guild_id: The guild.

		Returns:
			The configuration, or ``None`` if the guild never configured tickets.
		"""
		return await self._client.request(
			"GET",
			f"/guilds/{guild_id}/settings/tickets",
			TicketConfig | None,  # ty: ignore[invalid-argument-type]
		)

	async def update_config(self, guild_id: int, changes: TicketConfigUpdate) -> TicketConfig:
		"""Change a guild's ticket configuration. Only the fields set on ``changes`` are written.

		Args:
			guild_id: The guild.
			changes: The changes. ``None`` clears a channel or role.

		Returns:
			The stored configuration.

		Raises:
			ValueError: A minimum length would exceed its maximum.
		"""
		path = f"/guilds/{guild_id}/settings/tickets"
		return TicketConfig.model_validate_json(
			await self._client.send("PATCH", path, body=changes, exclude_unset=True)
		)

	async def open(self, guild_id: int, ticket: TicketOpen) -> Ticket:
		"""Record a ticket the bot opened a channel for.

		Args:
			guild_id: The guild.
			ticket: The ticket.

		Returns:
			The stored ticket.
		"""
		return await self._client.request("POST", f"/guilds/{guild_id}/tickets", Ticket, body=ticket)

	async def in_channel(self, channel_id: int) -> Ticket | None:
		"""Get the open ticket of a channel.

		Args:
			channel_id: The channel.

		Returns:
			The ticket, or ``None`` if the channel has no open ticket.
		"""
		return await _or_none(self._client.request("GET", f"/channels/{channel_id}/ticket", Ticket))

	async def open_count(self, guild_id: int, user_id: int) -> int:
		"""Count a member's open tickets.

		Args:
			guild_id: The guild.
			user_id: The member.

		Returns:
			The count.
		"""
		path = f"/guilds/{guild_id}/tickets/open-count"
		return (await self._client.request("GET", path, OpenTicketCount, user_id=user_id)).count

	async def archive(self, guild_id: int, ticket_id: int) -> None:
		"""Archive a ticket.

		Args:
			guild_id: The guild.
			ticket_id: The ticket.
		"""
		await self._client.send("POST", f"/guilds/{guild_id}/tickets/{ticket_id}/archive")

	async def reopen(self, guild_id: int, ticket_id: int) -> None:
		"""Reopen an archived ticket.

		Args:
			guild_id: The guild.
			ticket_id: The ticket.
		"""
		await self._client.send("POST", f"/guilds/{guild_id}/tickets/{ticket_id}/reopen")

	async def close(self, guild_id: int, ticket_id: int, closed_by: int) -> None:
		"""Close a ticket.

		Args:
			guild_id: The guild.
			ticket_id: The ticket.
			closed_by: Who closed it.
		"""
		body = TicketClose(closed_by=closed_by)
		await self._client.send("POST", f"/guilds/{guild_id}/tickets/{ticket_id}/close", body=body)

	async def channel_deleted(self, channel_id: int) -> None:
		"""Close the open tickets of a deleted channel.

		Args:
			channel_id: The deleted channel.
		"""
		await self._client.send("POST", f"/channels/{channel_id}/deleted")


class LevelsApi:
	"""Leveling operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def config(self, guild_id: int) -> LevelConfig:
		"""Get a guild's leveling configuration.

		Args:
			guild_id: The guild.

		Returns:
			The configuration. The defaults if the guild never configured leveling.
		"""
		return await self._client.request("GET", f"/guilds/{guild_id}/settings/leveling", LevelConfig)

	async def update_config(self, guild_id: int, changes: LevelConfigUpdate) -> LevelConfig:
		"""Change a guild's leveling configuration. Only the fields set on ``changes`` are written.

		Args:
			guild_id: The guild.
			changes: The changes. ``None`` clears the channel or message.

		Returns:
			The stored configuration.
		"""
		path = f"/guilds/{guild_id}/settings/leveling"
		return LevelConfig.model_validate_json(await self._client.send("PATCH", path, body=changes, exclude_unset=True))

	async def rewards(self, guild_id: int) -> list[LevelReward]:
		"""List a guild's role rewards.

		Args:
			guild_id: The guild.

		Returns:
			The rewards, lowest level first.
		"""
		return await self._client.request("GET", f"/guilds/{guild_id}/settings/leveling/rewards", list[LevelReward])

	async def add_reward(self, guild_id: int, level: int, role_id: int) -> None:
		"""Add a role reward. Adding one that exists does nothing.

		Args:
			guild_id: The guild.
			level: The level.
			role_id: The role.
		"""
		body = LevelReward(level=level, role_id=role_id)
		await self._client.send("POST", f"/guilds/{guild_id}/settings/leveling/rewards", body=body)

	async def remove_rewards(self, guild_id: int, level: int, role_id: int | None = None) -> None:
		"""Remove a level's role rewards.

		Args:
			guild_id: The guild.
			level: The level.
			role_id: Only this role's reward. ``None`` for every reward of the level.
		"""
		path = f"/guilds/{guild_id}/settings/leveling/rewards/{level}"
		if role_id is None:
			await self._client.send("DELETE", path)
		else:
			await self._client.send("DELETE", path, role_id=role_id)

	async def overrides(self, guild_id: int) -> LevelOverrides:
		"""List a guild's channel and role XP overrides.

		Args:
			guild_id: The guild.

		Returns:
			The overrides.
		"""
		return await self._client.request("GET", f"/guilds/{guild_id}/settings/leveling/overrides", LevelOverrides)

	async def update_override(
		self, guild_id: int, kind: Literal["channel", "role"], target_id: int, changes: LevelOverrideUpdate
	) -> None:
		"""Change a channel's or role's XP override.

		Args:
			guild_id: The guild.
			kind: A channel or a role override.
			target_id: The channel or role.
			changes: The changes. ``None`` fields keep their value.
		"""
		path = f"/guilds/{guild_id}/settings/leveling/overrides/{kind}/{target_id}"
		await self._client.send("PATCH", path, body=changes)

	async def award(self, guild_id: int, user_id: int, amount: int) -> XpResult:
		"""Give a member XP and update their level.

		Args:
			guild_id: The guild.
			user_id: The member.
			amount: The XP. Positive.

		Returns:
			The member's new XP and level, and the level they had before.
		"""
		body = XpAward(amount=amount)
		return await self._client.request("POST", f"/guilds/{guild_id}/levels/{user_id}/xp", XpResult, body=body)

	async def member(self, guild_id: int, user_id: int) -> MemberLevel:
		"""Get a member's XP, level and rank.

		Args:
			guild_id: The guild.
			user_id: The member.

		Returns:
			The member's level. All zero, without a rank, if they have no XP.
		"""
		return await self._client.request("GET", f"/guilds/{guild_id}/levels/{user_id}", MemberLevel)

	async def members(self, guild_id: int, user_ids: Sequence[int]) -> dict[int, MemberLevel]:
		"""Get several members' XP and level.

		Args:
			guild_id: The guild.
			user_ids: The members.

		Returns:
			The members that have XP, by user ID.
		"""
		body = UserIds(user_ids=list(user_ids))
		entries = await self._client.request("POST", f"/guilds/{guild_id}/levels/lookup", list[MemberLevel], body=body)
		return {entry.user_id: entry for entry in entries}

	async def leaderboard(self, guild_id: int, offset: int = 0, limit: int = 10) -> Leaderboard:
		"""List one page of a guild's members by XP, most first.

		Args:
			guild_id: The guild.
			offset: How many members to skip.
			limit: The most members to return, up to 100.

		Returns:
			The page, and how many members have XP.
		"""
		path = f"/guilds/{guild_id}/levels/leaderboard"
		return await self._client.request("GET", path, Leaderboard, offset=offset, limit=limit)


class AfkApi:
	"""AFK operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def away(self) -> list[AfkMember]:
		"""List every member who is away, in every guild.

		Returns:
			The members, with their reason and previous nickname.
		"""
		return await self._client.request("GET", "/afk", list[AfkMember])

	async def toggle(self, guild_id: int, user_id: int, message: str, nick: str) -> AfkToggled:
		"""Make a member away, or back if they are away.

		Args:
			guild_id: The guild.
			user_id: The member.
			message: The reason, recorded if they become away.
			nick: Their current nickname, recorded if they become away.

		Returns:
			Whether they are now away, and the nickname to restore if they're back.
		"""
		body = AfkToggle(message=message, previous_nick=nick)
		return await self._client.request("POST", f"/guilds/{guild_id}/afk/{user_id}/toggle", AfkToggled, body=body)

	async def back(self, guild_id: int, user_id: int) -> None:
		"""Mark a member as back.

		Args:
			guild_id: The guild.
			user_id: The member.
		"""
		await self._client.send("DELETE", f"/guilds/{guild_id}/afk/{user_id}")


class SnapshotsApi:
	"""Snapshot operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def create(self, guild_id: int, snapshot: SnapshotCreate) -> Snapshot:
		"""Save a snapshot of a guild under a new random code.

		Args:
			guild_id: The guild.
			snapshot: The snapshot.

		Returns:
			The saved snapshot, with its code.
		"""
		return await self._client.request("POST", f"/guilds/{guild_id}/snapshots", Snapshot, body=snapshot)

	async def get(self, code: str) -> Snapshot | None:
		"""Get a snapshot by its code, ignoring case.

		Args:
			code: The code.

		Returns:
			The snapshot, or ``None`` if there is none with that code.
		"""
		if not SNAPSHOT_CODE.fullmatch(code):
			return None
		return await _or_none(self._client.request("GET", f"/snapshots/{code}", Snapshot))


class ShopApi:
	"""Shop operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def items(self, guild_id: int) -> list[ShopItem]:
		"""List a guild's shop.

		Args:
			guild_id: The guild.

		Returns:
			The items, oldest first.
		"""
		return await self._client.request("GET", f"/guilds/{guild_id}/shop", list[ShopItem])

	async def get(self, guild_id: int, name: str) -> ShopItem | None:
		"""Get an item by its name, ignoring case.

		Args:
			guild_id: The guild.
			name: The item's name.

		Returns:
			The item, or ``None`` if the shop has none with that name.
		"""
		return await _or_none(self._client.request("GET", f"/guilds/{guild_id}/shop/item", ShopItem, name=name))

	async def add(self, guild_id: int, item: ShopItem) -> None:
		"""Add an item to a guild's shop.

		Args:
			guild_id: The guild.
			item: The item.

		Raises:
			ApiError: ``shop_item_taken`` or ``shop_limit``.
		"""
		await self._client.send("POST", f"/guilds/{guild_id}/shop", body=item)

	async def remove(self, guild_id: int, name: str) -> bool:
		"""Remove an item from a guild's shop.

		Args:
			guild_id: The guild.
			name: The item's name, ignoring case.

		Returns:
			Whether there was such an item.
		"""
		removed = await _or_none(self._client.send("DELETE", f"/guilds/{guild_id}/shop/item", name=name))
		return removed is not None


class GiveawaysApi:
	"""Giveaway operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def active(self) -> list[GiveawayRecord]:
		"""List every active giveaway, in every guild.

		Returns:
			The giveaways.
		"""
		return await self._client.request("GET", "/giveaways/active", list[GiveawayRecord])

	async def get(self, giveaway_id: int) -> GiveawayRecord | None:
		"""Get a giveaway.

		Args:
			giveaway_id: The giveaway.

		Returns:
			The giveaway, or ``None`` if there is none.
		"""
		return await _or_none(self._client.request("GET", f"/giveaways/{giveaway_id}", GiveawayRecord))

	async def find(
		self, channel_id: int, status: GiveawayStatus, message_id: int | None = None
	) -> GiveawayRecord | None:
		"""Find a channel's giveaway with a status: the one with the message, else the newest.

		Args:
			channel_id: The channel.
			status: The status it must have.
			message_id: Its message. ``None`` for the newest.

		Returns:
			The giveaway, or ``None`` if none matches.
		"""
		params: dict[str, Any] = {"status": status}
		if message_id is not None:
			params["message_id"] = message_id
		return await _or_none(self._client.request("GET", f"/channels/{channel_id}/giveaway", GiveawayRecord, **params))

	async def create(self, guild_id: int, giveaway: GiveawayCreate) -> GiveawayRecord:
		"""Start a giveaway.

		Args:
			guild_id: The guild.
			giveaway: The giveaway.

		Returns:
			The stored giveaway.

		Raises:
			ApiError: ``giveaway_limit`` if the guild runs the most active giveaways it may.
		"""
		return await self._client.request("POST", f"/guilds/{guild_id}/giveaways", GiveawayRecord, body=giveaway)

	async def set_message(self, giveaway_id: int, message_id: int) -> GiveawayRecord | None:
		"""Record the message the bot posted for a giveaway.

		Args:
			giveaway_id: The giveaway.
			message_id: The message.

		Returns:
			The stored giveaway, or ``None`` if it no longer exists.
		"""
		body = GiveawayMessage(message_id=message_id)
		return await _or_none(
			self._client.request("PUT", f"/giveaways/{giveaway_id}/message", GiveawayRecord, body=body)
		)

	async def delete(self, giveaway_id: int) -> None:
		"""Delete a giveaway with its entries.

		Args:
			giveaway_id: The giveaway.
		"""
		await self._client.send("DELETE", f"/giveaways/{giveaway_id}")

	async def end(self, giveaway_id: int) -> GiveawayRecord | None:
		"""End an active giveaway.

		Args:
			giveaway_id: The giveaway.

		Returns:
			The ended giveaway, or ``None`` if it wasn't active.
		"""
		return await _or_none(self._client.request("POST", f"/giveaways/{giveaway_id}/end", GiveawayRecord))

	async def cancel(self, giveaway_id: int) -> GiveawayRecord | None:
		"""Cancel an active giveaway.

		Args:
			giveaway_id: The giveaway.

		Returns:
			The cancelled giveaway, or ``None`` if it wasn't active.
		"""
		return await _or_none(self._client.request("POST", f"/giveaways/{giveaway_id}/cancel", GiveawayRecord))

	async def entry(self, giveaway_id: int, user_id: int) -> GiveawayEntry:
		"""Get a member's entry in a giveaway.

		Args:
			giveaway_id: The giveaway.
			user_id: The member.

		Returns:
			Whether they entered, and their stored message count.
		"""
		return await self._client.request("GET", f"/giveaways/{giveaway_id}/entries/{user_id}", GiveawayEntry)

	async def enter(self, giveaway_id: int, user_id: int) -> bool:
		"""Enter a member into a giveaway.

		Args:
			giveaway_id: The giveaway.
			user_id: The member.

		Returns:
			Whether they were newly entered.
		"""
		path = f"/giveaways/{giveaway_id}/entries/{user_id}"
		return (await self._client.request("PUT", path, GiveawayEntryChange)).changed

	async def leave(self, giveaway_id: int, user_id: int) -> bool:
		"""Remove a member's entry from a giveaway.

		Args:
			giveaway_id: The giveaway.
			user_id: The member.

		Returns:
			Whether they had entered.
		"""
		path = f"/giveaways/{giveaway_id}/entries/{user_id}"
		return (await self._client.request("DELETE", path, GiveawayEntryChange)).changed

	async def entry_count(self, giveaway_id: int) -> int:
		"""Count a giveaway's entries.

		Args:
			giveaway_id: The giveaway.

		Returns:
			How many members entered.
		"""
		return (await self._client.request("GET", f"/giveaways/{giveaway_id}/entries/count", GiveawayEntryCount)).count

	async def entrants(self, giveaway_id: int) -> list[int]:
		"""List the members who entered a giveaway and haven't won it.

		Args:
			giveaway_id: The giveaway.

		Returns:
			The members.
		"""
		return (await self._client.request("GET", f"/giveaways/{giveaway_id}/entries", GiveawayEntrants)).user_ids

	async def mark_winners(self, giveaway_id: int, user_ids: Sequence[int]) -> None:
		"""Record that members won a giveaway.

		Args:
			giveaway_id: The giveaway.
			user_ids: The winners, at most 100.
		"""
		body = GiveawayWinners(user_ids=list(user_ids))
		await self._client.send("POST", f"/giveaways/{giveaway_id}/winners", body=body)

	async def add_message_counts(self, counts: Sequence[tuple[int, int, int]]) -> None:
		"""Add messages members sent to their counts.

		Args:
			counts: ``(giveaway_id, user_id, count)`` per giveaway and member.
		"""
		body = MessageCounts([MessageCount(giveaway_id=g, user_id=u, count=c) for g, u, c in counts])
		await self._client.send("POST", "/giveaways/message-counts", body=body)

	async def message_counts(self, giveaway_id: int) -> dict[int, int]:
		"""Get the message counts of a giveaway's members.

		Args:
			giveaway_id: The giveaway.

		Returns:
			Messages sent since it started, by user ID.
		"""
		counts = await self._client.request("GET", f"/giveaways/{giveaway_id}/message-counts", list[MessageCount])
		return {count.user_id: count.count for count in counts}

	async def purge(self) -> None:
		"""Delete the entries and message counts of giveaways that finished more than 30 days ago."""
		await self._client.send("POST", "/giveaways/purge")


class AlertsApi:
	"""Media alert operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def accounts(self) -> list[AlertAccount]:
		"""List the accounts that at least one enabled alert follows, each once.

		Returns:
			The accounts.
		"""
		return await self._client.request("GET", "/alerts/accounts", list[AlertAccount])

	async def subscribers(self, platform: str, channel_account: str, account_id: str) -> list[MediaAlert]:
		"""List the enabled alerts that follow an account.

		Args:
			platform: The platform.
			channel_account: Matches alerts with this ``channel_account``.
			account_id: Also matches alerts with this ``account_id``.

		Returns:
			The alerts.
		"""
		return await self._client.request(
			"GET",
			"/alerts/subscribers",
			list[MediaAlert],
			platform=platform,
			channel_account=channel_account,
			account_id=account_id,
		)

	async def set_baseline(self, platform: str, channel_account: str, account_id: str, media_id: str) -> None:
		"""Set a baseline on every enabled alert on an account that has none yet.

		Args:
			platform: The platform.
			channel_account: Matches alerts with this ``channel_account``.
			account_id: Also matches alerts with this ``account_id``.
			media_id: The media ID to record.
		"""
		body = AlertBaseline(
			platform=platform, channel_account=channel_account, account_id=account_id, media_id=media_id
		)
		await self._client.send("POST", "/alerts/baseline", body=body)

	async def set_last_media(self, alert_id: int, media_id: str) -> None:
		"""Record the newest upload an alert has seen.

		Args:
			alert_id: The alert.
			media_id: The upload.
		"""
		await self._client.send("PUT", f"/alerts/{alert_id}/last-media", body=AlertMedia(media_id=media_id))

	async def for_guild(self, guild_id: int) -> list[MediaAlert]:
		"""List a guild's alerts, oldest first.

		Args:
			guild_id: The guild.

		Returns:
			The alerts.
		"""
		return await self._client.request("GET", f"/guilds/{guild_id}/alerts", list[MediaAlert])

	async def get(self, guild_id: int, alert_id: int) -> MediaAlert | None:
		"""Get an alert.

		Args:
			guild_id: The guild.
			alert_id: The alert.

		Returns:
			The alert, or ``None`` if the guild has no such alert.
		"""
		return await _or_none(self._client.request("GET", f"/guilds/{guild_id}/alerts/{alert_id}", MediaAlert))

	async def add(self, guild_id: int, alert: AlertCreate) -> MediaAlert:
		"""Add an alert, or enable it again and update its account if the guild has it.

		Args:
			guild_id: The guild.
			alert: The alert.

		Returns:
			The stored alert.

		Raises:
			ApiError: ``alert_limit`` if the guild has the most alerts it may.
		"""
		return await self._client.request("POST", f"/guilds/{guild_id}/alerts", MediaAlert, body=alert)

	async def remove(self, guild_id: int, alert_id: int) -> bool:
		"""Remove an alert.

		Args:
			guild_id: The guild.
			alert_id: The alert.

		Returns:
			Whether the guild had such an alert.
		"""
		return await _or_none(self._client.send("DELETE", f"/guilds/{guild_id}/alerts/{alert_id}")) is not None

	async def remove_account(self, guild_id: int, platform: str, account: str) -> int:
		"""Remove a guild's alerts that follow an account, ignoring case.

		Args:
			guild_id: The guild.
			platform: The platform.
			account: Matches the alerts' ``channel_account`` or ``account_id``.

		Returns:
			How many alerts were removed.
		"""
		path = f"/guilds/{guild_id}/alerts"
		return (await self._client.request("DELETE", path, RemovedAlerts, platform=platform, account=account)).removed

	async def set_enabled(self, guild_id: int, alert_id: int, enabled: bool) -> bool:
		"""Turn an alert on or off.

		Args:
			guild_id: The guild.
			alert_id: The alert.
			enabled: Whether it is on.

		Returns:
			Whether the guild had such an alert.
		"""
		path = f"/guilds/{guild_id}/alerts/{alert_id}/enabled"
		body = AlertEnabled(enabled=enabled)
		return await _or_none(self._client.request("PUT", path, MediaAlert, body=body)) is not None


class BlacklistApi:
	"""Blacklist operations. Every method can also raise `ApiUnavailable`.

	Args:
		client: The API client.
	"""

	def __init__(self, client: ApiClient) -> None:
		self._client = client

	async def entries(self) -> list[BlacklistEntry]:
		"""List every blacklisted user and guild, oldest first.

		Returns:
			The entries.
		"""
		return await self._client.request("GET", "/blacklist", list[BlacklistEntry])

	async def add(self, kind: BlacklistKind, target_id: int, created_by: int, reason: str | None) -> BlacklistEntry:
		"""Blacklist a user or guild. Blacklisting it again replaces the reason and who added it.

		Args:
			kind: Whether the target is a user or a guild.
			target_id: The user or guild.
			created_by: The bot owner adding it.
			reason: Why, if given.

		Returns:
			The entry.
		"""
		body = BlacklistAdd(created_by=created_by, reason=reason)
		return await self._client.request("PUT", f"/blacklist/{kind}/{target_id}", BlacklistEntry, body=body)

	async def remove(self, kind: BlacklistKind, target_id: int) -> bool:
		"""Take a user or guild off the blacklist.

		Args:
			kind: Whether the target is a user or a guild.
			target_id: The user or guild.

		Returns:
			Whether it was blacklisted.
		"""
		return await _or_none(self._client.send("DELETE", f"/blacklist/{kind}/{target_id}")) is not None
