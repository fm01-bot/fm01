"""The Case module: moderation cases, their lifecycle, and their expiry.

Commands talk to `CaseStore`. It owns every query against ``cases``, turns rows into the right `Case` subclass,
applies the guild's retention policy when a case is closed, and keeps the expiry schedule in step with the table.
The `Case` subclasses only carry data and the Discord side effects of opening and closing a case.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from collections.abc import Callable, Sequence
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Protocol

import discord
from args import FormatDateTime, Guild, Member, User
from discord.utils import MISSING
from helpers import custom_response
from helpers.scheduler import ExpiryScheduler

from api import RETENTION_SETTING, CaseCreate, CaseRecord, CaseUpdate

if TYPE_CHECKING:
	from core import Bot
	from core.api import ApiClient
	from core.settings import GuildSetting, GuildSettings

__all__ = (
	"Ban",
	"Case",
	"CaseExpirationManager",
	"CaseStatus",
	"CaseStore",
	"CaseType",
	"CloseOutcome",
	"Kick",
	"Mute",
	"Retention",
	"Softban",
	"Warn",
	"retention_setting",
)

logger = logging.getLogger(__name__)

type Retention = Literal["keep", "delete"]
type CaseStatus = Literal["active", "expired", "all"]
type CloseOutcome = Literal["deleted", "deactivated"]


class CaseType(Enum):
	WARN = 1
	MUTE = 2
	KICK = 3
	BAN = 4
	SOFTBAN = 5


class Case:
	"""A moderation case. Subclasses override the hooks to perform the case's Discord side effects."""

	def __init__(
		self,
		_type: CaseType,
		_id: int,
		bot: Bot,
		guild: discord.Guild,
		user: discord.Member | discord.User,
		moderator: discord.User | discord.Member,
		created: datetime.datetime = MISSING,
		reason: str | None = None,
		expires: datetime.datetime | None = None,
		message: str | None = None,
		active: bool = True,
	):
		if created is MISSING or not created:
			created = datetime.datetime.now(tz=datetime.UTC)
		elif created.tzinfo is None:
			created = created.replace(tzinfo=datetime.UTC)
		if expires and expires.tzinfo is None:
			expires = expires.replace(tzinfo=datetime.UTC)
		self.bot: Bot = bot
		self.type: CaseType = _type
		self.id: int = _id
		self._guild: discord.Guild = guild
		self._user: discord.Member | discord.User = user
		self.reason: str | None = reason
		self._moderator: discord.User | discord.Member = moderator
		self.expires: datetime.datetime | None = expires
		self.message: str | None = message
		self.active: bool = active
		self._created: datetime.datetime = created

	def __repr__(self) -> str:
		return (
			f"{type(self).__name__}(id={self.id} user={self._user} reason={self.reason} moderator={self._moderator} "
			f"expires={self.expires} message={self.message} active={self.active})"
		)

	def __eq__(self, other: object) -> bool:
		return isinstance(other, Case) and self.id == other.id

	def __hash__(self) -> int:
		return hash(self.id)

	def __int__(self) -> int:
		return self.id

	@property
	def length(self) -> str | None:
		"""The expiry as a relative Discord timestamp, if the case expires."""
		return discord.utils.format_dt(self.expires, "R") if self.expires else None

	@property
	def status(self) -> str:
		"""Returns the status text: 'Active', 'Expired', or 'Inactive'."""
		if not self.active:
			return "Inactive"
		if self.expires and self.expires <= datetime.datetime.now(tz=datetime.UTC):
			return "Expired"
		return "Active"

	@property
	def created(self) -> FormatDateTime:
		"""The creation date of the case."""
		return FormatDateTime(self._created, "R")

	@property
	def guild(self) -> Guild:
		return Guild.from_guild(self._guild)

	@property
	def user(self) -> User:
		return User.from_user(self._user) if isinstance(self._user, discord.User) else Member.from_member(self._user)

	@property
	def moderator(self) -> User:
		return User.from_user(self._moderator)

	@staticmethod
	def generate_id(message: discord.Message) -> int:
		"""Generate a case ID from a message."""
		return message.id

	async def before_creation(self) -> None:
		"""Called before the case is written. The default implementation does nothing."""

	async def after_creation(self) -> None:
		"""Called after the case is written. Raising here rolls the case back."""

	async def before_deletion(self) -> None:
		"""Called before an active case is closed (deleted or deactivated)."""

	async def after_deletion(self) -> None:
		"""Called after an active case is closed (deleted or deactivated)."""

	async def _audit_reason(self, key: str) -> str | None:
		"""The localized audit-log reason for this case's Discord action."""
		text = await custom_response.CustomResponse(self.bot, "mod").get_message(
			key, self._guild, moderator=self._moderator, case=self
		)
		return text if isinstance(text, str) else None

	async def _notify(self, key: str, **kwargs: Any) -> None:
		message = await custom_response.CustomResponse(self.bot, "mod").get_message(key, self._guild, **kwargs)
		try:
			if isinstance(message, dict):
				await self._user.send(**message)
		except discord.Forbidden:
			pass


class Warn(Case):
	def __init__(
		self,
		_id: int,
		bot: Bot,
		guild: discord.Guild,
		user: discord.Member | discord.User,
		moderator: discord.User | discord.Member,
		reason: str | None = None,
		expires: datetime.datetime | None = None,
		message: str | None = None,
		created: datetime.datetime = MISSING,
		active: bool = True,
	):
		super().__init__(
			CaseType.WARN, _id, bot, guild, user, moderator, created, reason, expires, message, active=active
		)

	async def after_creation(self) -> None:
		"""Notifies the user about the warning."""
		await self._notify("mod.warn.notify", warn=self)

	async def after_deletion(self) -> None:
		"""Notifies the user about the removal of the warning."""
		await self._notify("mod.warn.unwarned", warn=self)


class Kick(Case):
	def __init__(
		self,
		_id: int,
		bot: Bot,
		guild: discord.Guild,
		user: discord.Member | discord.User,
		moderator: discord.User | discord.Member,
		reason: str | None = None,
		message: str | None = None,
		created: datetime.datetime = MISSING,
		expires: datetime.datetime | None = None,
		active: bool = True,
	):
		super().__init__(
			CaseType.KICK, _id, bot, guild, user, moderator, created, reason, expires, message, active=active
		)

	async def before_creation(self) -> None:
		"""Notifies the user about the kick."""
		await self._notify("mod.kick.notify", kick=self)

	async def after_creation(self) -> None:
		"""Kicks the user."""
		if isinstance(self._user, discord.Member):
			await self._user.kick(reason=await self._audit_reason("mod.kick.reason"))


SOFTBAN_DELETE_SECONDS = 3600
"""How far back a softban deletes the user's messages."""


class Softban(Case):
	"""A kick that also deletes the user's recent messages: a ban, lifted at once."""

	audit_reason_key = "mod.softban.reason"
	"""The localization key of the audit-log reason for the ban and unban."""

	def __init__(
		self,
		_id: int,
		bot: Bot,
		guild: discord.Guild,
		user: discord.Member | discord.User,
		moderator: discord.User | discord.Member,
		reason: str | None = None,
		message: str | None = None,
		created: datetime.datetime = MISSING,
		expires: datetime.datetime | None = None,
		active: bool = True,
	):
		super().__init__(
			CaseType.SOFTBAN, _id, bot, guild, user, moderator, created, reason, expires, message, active=active
		)

	async def before_creation(self) -> None:
		"""Notifies the user about the softban. The ban ends their last shared server, so this comes first."""
		await self._notify("mod.softban.notify", softban=self)

	async def after_creation(self) -> None:
		"""Bans the user, deleting their recent messages, and unbans them.

		A failed unban is logged instead of raised: the ban already happened, so the case stays.
		"""
		reason = await self._audit_reason(self.audit_reason_key)
		user = discord.Object(self._user.id)
		await self._guild.ban(user, reason=reason, delete_message_seconds=SOFTBAN_DELETE_SECONDS)
		try:
			await self._guild.unban(user, reason=reason)
		except discord.HTTPException:
			logger.exception(f"Softban {self.id} banned {self._user.id} in {self._guild.id} but failed to unban")


class Mute(Case):
	def __init__(
		self,
		_id: int,
		bot: Bot,
		guild: discord.Guild,
		user: discord.Member | discord.User,
		moderator: discord.User | discord.Member,
		expires: datetime.datetime | None,
		reason: str | None = None,
		message: str | None = None,
		created: datetime.datetime = MISSING,
		active: bool = True,
	):
		super().__init__(
			CaseType.MUTE, _id, bot, guild, user, moderator, created, reason, expires, message, active=active
		)

	async def before_creation(self) -> None:
		"""Times the member out until the case expires (Discord caps timeouts at 28 days)."""
		reason = await self._audit_reason("mod.mute.reason")
		if isinstance(self._user, discord.Member) and self.expires is not None:
			now = datetime.datetime.now(tz=datetime.UTC)
			expires_utc = min(self.expires.astimezone(datetime.UTC), now + datetime.timedelta(days=28))
			if expires_utc <= now:
				return
			await self._user.timeout(expires_utc, reason=reason)

	async def after_creation(self) -> None:
		"""Notifies the user about the mute."""
		await self._notify("mod.mute.notify", mute=self)

	async def before_deletion(self) -> None:
		"""Removes the member's timeout, if they still have one."""
		member = self._guild.get_member(self._user.id)
		if member and member.timed_out_until:
			await member.edit(timed_out_until=None, reason=self.reason)

	async def after_deletion(self) -> None:
		"""Notifies the user about the unmute."""
		await self._notify("mod.unmute.notify", mute=self)


class Ban(Case):
	def __init__(
		self,
		_id: int,
		bot: Bot,
		guild: discord.Guild,
		user: discord.Member | discord.User,
		moderator: discord.User | discord.Member,
		reason: str | None = None,
		expires: datetime.datetime | None = None,
		message: str | None = None,
		created: datetime.datetime = MISSING,
		active: bool = True,
	):
		super().__init__(
			CaseType.BAN, _id, bot, guild, user, moderator, created, reason, expires, message, active=active
		)

	async def before_creation(self) -> None:
		"""Notifies the user about the ban."""
		await self._notify("mod.ban.notify", ban=self)

	async def after_creation(self) -> None:
		"""Bans the user."""
		reason = await self._audit_reason("mod.ban.reason")
		await self._guild.ban(self._user, reason=reason, delete_message_days=0)  # type: ignore

	async def before_deletion(self) -> None:
		"""Unbans the user."""
		try:
			await self._guild.unban(self._user, reason=await self._audit_reason("mod.unban.case_reason"))  # type: ignore
		except discord.NotFound:
			pass

	async def after_deletion(self) -> None:
		"""Notifies the user about the unban, if they share a server with the bot."""
		if self._guild.get_member(self._user.id):
			await self._notify("mod.unban.notify", ban=self)


CASE_CLASSES: dict[CaseType, Callable[..., Case]] = {
	CaseType.WARN: Warn,
	CaseType.MUTE: Mute,
	CaseType.KICK: Kick,
	CaseType.BAN: Ban,
	CaseType.SOFTBAN: Softban,
}


class CaseScheduler(Protocol):
	"""What `CaseStore` needs from an expiry scheduler."""

	def schedule_at(self, key: int, guild_id: int, expires: datetime.datetime) -> None: ...
	def cancel(self, key: int) -> None: ...
	def start(self) -> None: ...
	def stop(self) -> None: ...


def retention_setting(settings: GuildSettings, api: ApiClient) -> GuildSetting[Retention]:
	"""Register the guild's case retention policy, stored behind the API.

	Args:
		settings: The registry to add it to.
		api: The API client it loads and saves through.

	Returns:
		The setting. ``keep`` for guilds that never set one.
	"""
	return settings.add_remote(RETENTION_SETTING, api.cases.retention, api.cases.set_retention)


class CaseStore:
	"""Reads, opens, closes, edits and expires moderation cases through the API.

	The API applies the guild's retention when a case is closed.

	Args:
		bot: The bot, used to resolve guilds and users from stored IDs and to reach the API.
		scheduler: Expiry scheduler. Defaults to a `CaseExpirationManager` that expires cases through this store.
	"""

	def __init__(self, bot: Bot, scheduler: CaseScheduler | None = None) -> None:
		self._bot = bot
		self._api = bot.api.cases
		self._scheduler: CaseScheduler = scheduler or CaseExpirationManager(bot, self)

	def start(self) -> None:
		"""Start expiring cases."""
		self._scheduler.start()

	def stop(self) -> None:
		"""Stop expiring cases."""
		self._scheduler.stop()

	async def get(self, guild: discord.Guild, case_id: int) -> Case | None:
		"""Return the case with ``case_id`` in ``guild``, or ``None``."""
		record = await self._api.get(guild.id, case_id)
		return await self._from_record(record, guild) if record else None

	async def active(
		self, guild: discord.Guild, user: discord.Member | discord.User, case_type: CaseType
	) -> list[Case]:
		"""Return the user's active cases of one type in ``guild``, oldest first."""
		records = await self._api.for_user(guild.id, user.id, "open", case_type.value)
		return await self._from_records(records, guild, user)

	async def for_user(
		self, guild: discord.Guild, user: discord.Member | discord.User, status: CaseStatus = "all"
	) -> list[Case]:
		"""Return the user's cases in ``guild``, newest first.

		Args:
			guild: The guild.
			user: The user the cases are about.
			status: ``"active"`` (active and not past expiry), ``"expired"`` (inactive or past expiry), or ``"all"``.
		"""
		records = await self._api.for_user(guild.id, user.id, status)
		return await self._from_records(list(reversed(records)), guild, user)

	async def open(self, case: Case) -> Case | None:
		"""Record a new case and perform its side effects.

		Returns:
			The case, or ``None`` if the target is no longer in the guild (bans may target non-members).

		Raises:
			Exception: Whatever ``after_creation`` raised; the case is removed again first.
		"""
		if case.type != CaseType.BAN and case._guild.get_member(case._user.id) is None:
			return None

		await case.before_creation()
		await self._api.create(
			case._guild.id,
			CaseCreate(
				case_id=case.id,
				type=case.type.value,
				user_id=case._user.id,
				moderator_id=case._moderator.id,
				reason=case.reason,
				expires=case.expires,
				message=case.message,
				active=case.active,
				created=case._created,
			),
		)
		try:
			await case.after_creation()
		except Exception:
			await self._api.delete(case._guild.id, case.id)
			raise

		if case.active and case.expires:
			self._scheduler.schedule_at(case.id, case._guild.id, case.expires)
		return case

	async def close(self, case: Case) -> CloseOutcome:
		"""Close a case according to the guild's retention policy.

		Runs the case's deletion hooks only if it was still active, so closing twice never repeats an unban,
		unmute or DM.
		"""
		self._scheduler.cancel(case.id)
		was_active = case.active
		if was_active:
			await case.before_deletion()
		outcome = (await self._api.close(case._guild.id, case.id)).outcome
		case.active = False
		if was_active:
			await case.after_deletion()
		return outcome

	async def delete(self, case: Case) -> None:
		"""Delete a case regardless of the retention policy, running its deletion hooks if it was active."""
		self._scheduler.cancel(case.id)
		if case.active:
			await case.before_deletion()
		await self._api.delete(case._guild.id, case.id)
		if case.active:
			case.active = False
			await case.after_deletion()

	async def edit(
		self,
		case: Case,
		*,
		reason: str | None = MISSING,
		expires: datetime.datetime | None = MISSING,
		message: str | None = MISSING,
	) -> Case:
		"""Change a case's reason, expiry or message. Omitted fields keep their value; the expiry is rescheduled."""
		if reason is not MISSING:
			case.reason = reason
		if expires is not MISSING:
			case.expires = expires
		if message is not MISSING:
			case.message = message
		await self._api.update(
			case._guild.id, case.id, CaseUpdate(reason=case.reason, expires=case.expires, message=case.message)
		)
		self._scheduler.cancel(case.id)
		if case.active and case.expires:
			self._scheduler.schedule_at(case.id, case._guild.id, case.expires)
		return case

	async def pending(self) -> list[tuple[int, int, datetime.datetime]]:
		"""Return ``(case_id, guild_id, expires)`` for every active case that expires."""
		return [(case.case_id, case.guild_id, case.expires) for case in await self._api.pending()]

	async def expire(self, case_id: int) -> None:
		"""Close an expired case. Cases from guilds the bot has left are deleted outright."""
		record = await self._api.find(case_id)
		if record is None or not record.active:
			return
		guild = self._bot.get_guild(record.guild_id)
		if guild is None:
			await self._api.delete(record.guild_id, case_id)
			return
		await self.close(await self._from_record(record, guild))

	async def _from_record(
		self, record: CaseRecord, guild: discord.Guild, user: discord.Member | discord.User | None = None
	) -> Case:
		(case,) = await self._from_records([record], guild, user)
		return case

	async def _from_records(
		self, records: Sequence[CaseRecord], guild: discord.Guild, user: discord.Member | discord.User | None = None
	) -> list[Case]:
		"""Build the `Case` subclass for each record, resolving every distinct user once (cache, then the API)."""
		ids = {record.moderator_id for record in records}
		if user is None:
			ids |= {record.user_id for record in records}
		users = await self._resolve_users(ids)
		return [
			CASE_CLASSES[CaseType(record.type)](
				_id=record.case_id,
				bot=self._bot,
				guild=guild,
				user=user or users[record.user_id],
				moderator=users[record.moderator_id],
				reason=record.reason,
				expires=record.expires,
				message=record.message,
				created=record.created,
				active=record.active,
			)
			for record in records
		]

	async def _resolve_users(self, user_ids: set[int]) -> dict[int, discord.User]:
		resolved = {uid: cached for uid in user_ids if (cached := self._bot.get_user(uid)) is not None}
		missing = [uid for uid in user_ids if uid not in resolved]
		if missing:
			limit = asyncio.Semaphore(5)

			async def fetch(uid: int) -> discord.User:
				async with limit:
					return await self._bot.fetch_user(uid)

			resolved.update(zip(missing, await asyncio.gather(*(fetch(uid) for uid in missing)), strict=True))
		return resolved


class CaseExpirationManager(ExpiryScheduler[int]):
	"""Shard-aware scheduler that expires cases through a `CaseStore`."""

	def __init__(self, bot: Bot, store: CaseStore) -> None:
		super().__init__(bot)
		self._store = store

	async def fetch_pending(self) -> list[tuple[int, int, datetime.datetime]]:
		"""Return every active case that has an expiry date."""
		return await self._store.pending()

	async def process_expired(self, key: int, guild_id: int) -> None:
		"""Close the expired case."""
		await self._store.expire(key)
