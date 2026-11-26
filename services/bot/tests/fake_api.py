"""In-memory stand-ins for parts of the API client, behaving like the Internal API they wrap."""

from __future__ import annotations

import datetime

from core.api import SuggestionClosed, SuggestionsDisabled
from core.clustering.interfaces import EventBus

from api import (
	EVENTS_CHANNEL,
	LOG_SETTING,
	AutoModConfig,
	CaseClosed,
	CaseCreate,
	CaseFilter,
	CaseRecord,
	CaseUpdate,
	DecisionStatus,
	GreetingConfig,
	GreetingUpdate,
	GuildLogConfig,
	InvalidateSetting,
	LogConfig,
	MediaAlert,
	PendingCase,
	Retention,
	Suggestion,
	SuggestionConfig,
	SuggestionDecision,
	Ticket,
	TicketConfig,
	TicketConfigUpdate,
	TicketOpen,
	Vote,
	VoteResult,
)


class FakeCases:
	"""`CasesApi` over a dict: cases by ID, retention by guild. The API applies retention when closing."""

	def __init__(self) -> None:
		self.cases: dict[int, CaseRecord] = {}
		self.retentions: dict[int, Retention] = {}

	async def retention(self, guild_id: int) -> Retention:
		return self.retentions.get(guild_id, "keep")

	async def set_retention(self, guild_id: int, retention: Retention) -> None:
		self.retentions[guild_id] = retention

	async def get(self, guild_id: int, case_id: int) -> CaseRecord | None:
		case = self.cases.get(case_id)
		return case if case is not None and case.guild_id == guild_id else None

	async def find(self, case_id: int) -> CaseRecord | None:
		return self.cases.get(case_id)

	async def for_user(
		self, guild_id: int, user_id: int, which: CaseFilter = "all", case_type: int | None = None
	) -> list[CaseRecord]:
		now = datetime.datetime.now(tz=datetime.UTC)

		def matches(case: CaseRecord) -> bool:
			past = case.expires is not None and case.expires <= now
			return {
				"open": case.active,
				"active": case.active and not past,
				"expired": not case.active or past,
				"all": True,
			}[which]

		found = [
			case
			for case in self.cases.values()
			if case.guild_id == guild_id
			and case.user_id == user_id
			and (case_type is None or case.type == case_type)
			and matches(case)
		]
		return sorted(found, key=lambda case: (case.created, case.case_id))

	async def create(self, guild_id: int, case: CaseCreate) -> CaseRecord:
		record = CaseRecord(guild_id=guild_id, **case.model_dump())
		self.cases[case.case_id] = record
		return record

	async def update(self, guild_id: int, case_id: int, changes: CaseUpdate) -> None:
		if (case := await self.get(guild_id, case_id)) is not None:
			self.cases[case_id] = case.model_copy(update=changes.model_dump())

	async def close(self, guild_id: int, case_id: int) -> CaseClosed:
		if self.retentions.get(guild_id) == "delete":
			self.cases.pop(case_id, None)
			return CaseClosed(outcome="deleted")
		if (case := await self.get(guild_id, case_id)) is not None:
			self.cases[case_id] = case.model_copy(update={"active": False})
		return CaseClosed(outcome="deactivated")

	async def delete(self, guild_id: int, case_id: int) -> None:
		if await self.get(guild_id, case_id) is not None:
			del self.cases[case_id]

	async def pending(self) -> list[PendingCase]:
		return [
			PendingCase(case_id=case.case_id, guild_id=case.guild_id, expires=case.expires)
			for case in self.cases.values()
			if case.active and case.expires is not None
		]


class FakeLogStore:
	"""Log configurations shared by every instance's `FakeLog`, announced on the bus like the API does."""

	def __init__(self, bus: EventBus) -> None:
		self.bus = bus
		self.configs: dict[int, LogConfig] = {}

	async def announce(self, guild_id: int, origin: str) -> None:
		event = InvalidateSetting(key=LOG_SETTING, guild_id=guild_id, origin=origin)
		await self.bus.publish(EVENTS_CHANNEL, event.model_dump(mode="json"))


class FakeLog:
	"""`LogApi` for one bot instance: writes carry that instance's origin.

	Args:
		store: The shared storage.
		origin: The instance's ID, as ``X-Fm01-Origin`` would carry it.
	"""

	def __init__(self, store: FakeLogStore, origin: str) -> None:
		self._store = store
		self._origin = origin

	async def get(self, guild_id: int) -> LogConfig | None:
		return self._store.configs.get(guild_id)

	async def all(self) -> list[GuildLogConfig]:
		return [GuildLogConfig(guild_id=g, **c.model_dump()) for g, c in self._store.configs.items()]

	async def set(self, guild_id: int, config: LogConfig) -> None:
		self._store.configs[guild_id] = config.model_copy(update={"modules": sorted(set(config.modules))})
		await self._store.announce(guild_id, self._origin)

	async def delete(self, guild_id: int) -> None:
		self._store.configs.pop(guild_id, None)
		await self._store.announce(guild_id, self._origin)


class FakeAutoMod:
	"""`AutoModApi` over a dict."""

	def __init__(self) -> None:
		self.configs: dict[int, AutoModConfig] = {}

	async def get(self, guild_id: int) -> AutoModConfig:
		return self.configs.get(guild_id, AutoModConfig())

	async def set(self, guild_id: int, config: AutoModConfig) -> None:
		self.configs[guild_id] = config.model_copy(deep=True)


class FakeTickets:
	"""`TicketsApi` over dicts: configurations by guild, tickets by ID."""

	def __init__(self) -> None:
		self.configs: dict[int, TicketConfig] = {}
		self.tickets: dict[int, Ticket] = {}

	async def config(self, guild_id: int) -> TicketConfig | None:
		return self.configs.get(guild_id)

	async def update_config(self, guild_id: int, changes: TicketConfigUpdate) -> TicketConfig:
		fields = {
			k: v
			for k, v in changes.model_dump(exclude_unset=True).items()
			if v is not None or k in ("category_id", "log_channel_id", "support_role_id")
		}
		config = self.configs.get(guild_id, TicketConfig()).model_copy(update=fields)
		if config.topic_min_length > config.topic_max_length:
			raise ValueError("the topic's minimum length exceeds its maximum")
		if config.description_min_length > config.description_max_length:
			raise ValueError("the description's minimum length exceeds its maximum")
		self.configs[guild_id] = config
		return config

	def add(self, guild_id: int, channel_id: int, user_id: int, title: str = "Help", description: str = "") -> Ticket:
		ticket = Ticket(
			id=len(self.tickets) + 1,
			guild_id=guild_id,
			channel_id=channel_id,
			user_id=user_id,
			title=title,
			description=description,
			created_at=datetime.datetime.now(tz=datetime.UTC),
		)
		self.tickets[ticket.id] = ticket
		return ticket

	async def open(self, guild_id: int, ticket: TicketOpen) -> Ticket:
		return self.add(guild_id, ticket.channel_id, ticket.user_id, ticket.title, description=ticket.description)

	async def in_channel(self, channel_id: int) -> Ticket | None:
		return next((t for t in self.tickets.values() if t.channel_id == channel_id and not t.closed), None)

	async def open_count(self, guild_id: int, user_id: int) -> int:
		return sum(t.guild_id == guild_id and t.user_id == user_id and not t.closed for t in self.tickets.values())

	def _update(self, ticket_id: int, **fields: object) -> None:
		self.tickets[ticket_id] = self.tickets[ticket_id].model_copy(update=fields)

	async def archive(self, guild_id: int, ticket_id: int) -> None:
		self._update(ticket_id, archived=True)

	async def reopen(self, guild_id: int, ticket_id: int) -> None:
		self._update(ticket_id, archived=False)

	async def close(self, guild_id: int, ticket_id: int, closed_by: int) -> None:
		now = datetime.datetime.now(tz=datetime.UTC)
		self._update(ticket_id, closed=True, archived=True, closed_at=now, closed_by=closed_by)

	async def channel_deleted(self, channel_id: int) -> None:
		for ticket in list(self.tickets.values()):
			if ticket.channel_id == channel_id and not ticket.closed:
				self._update(ticket.id, closed=True, archived=True, closed_at=datetime.datetime.now(tz=datetime.UTC))


class FakeGreetings:
	"""`GreetingsApi` over a dict keyed by kind and guild."""

	def __init__(self) -> None:
		self.configs: dict[tuple[str, int], GreetingConfig] = {}

	async def get(self, kind: str, guild_id: int) -> GreetingConfig | None:
		return self.configs.get((kind, guild_id))

	async def update(self, kind: str, guild_id: int, changes: GreetingUpdate) -> GreetingConfig:
		current = self.configs.get((kind, guild_id))
		base = current or GreetingConfig()
		config = GreetingConfig(
			enabled=base.enabled if changes.enabled is None else changes.enabled,
			channel_id=changes.channel_id or base.channel_id or changes.fallback_channel_id,
			message=changes.message or base.message,
		)
		self.configs[(kind, guild_id)] = config
		return config


def alert(**fields: object) -> MediaAlert:
	"""A stored media alert, with defaults for the fields a test doesn't care about."""
	values: dict[str, object] = {
		"id": 1,
		"guild_id": 123,
		"platform": "youtube",
		"channel_account": "@creator",
		"target_channel_id": 999,
		"created_at": datetime.datetime.now(tz=datetime.UTC),
	}
	return MediaAlert.model_validate(values | fields)


class FakeSuggestions:
	"""`SuggestionsApi` over dicts, with the API's numbering, toggling votes and closing decisions."""

	def __init__(self) -> None:
		self.configs: dict[int, SuggestionConfig] = {}
		self.suggestions: dict[tuple[int, int], Suggestion] = {}
		self.votes: dict[tuple[int, int], dict[int, Vote]] = {}

	async def config(self, guild_id: int) -> SuggestionConfig:
		return self.configs.get(guild_id, SuggestionConfig())

	async def set_config(self, guild_id: int, config: SuggestionConfig) -> None:
		self.configs[guild_id] = config

	def _counted(self, guild_id: int, suggestion: Suggestion) -> Suggestion:
		votes = self.votes.get((guild_id, suggestion.number), {}).values()
		up = sum(vote is Vote.UP for vote in votes)
		return suggestion.model_copy(update={"up": up, "down": len(votes) - up})

	async def create(self, guild_id: int, author_id: int, content: str) -> Suggestion:
		if (await self.config(guild_id)).channel_id is None:
			raise SuggestionsDisabled
		number = 1 + sum(guild == guild_id for guild, _ in self.suggestions)
		suggestion = Suggestion(number=number, author_id=author_id, content=content, up=0, down=0)
		self.suggestions[(guild_id, number)] = suggestion
		return suggestion

	async def get(self, guild_id: int, number: int) -> Suggestion | None:
		suggestion = self.suggestions.get((guild_id, number))
		return None if suggestion is None else self._counted(guild_id, suggestion)

	async def set_message(self, guild_id: int, number: int, channel_id: int, message_id: int) -> Suggestion | None:
		if (guild_id, number) not in self.suggestions:
			return None
		self.suggestions[(guild_id, number)] = self.suggestions[(guild_id, number)].model_copy(
			update={"channel_id": channel_id, "message_id": message_id}
		)
		return await self.get(guild_id, number)

	async def vote(self, guild_id: int, number: int, user_id: int, vote: Vote) -> VoteResult | None:
		suggestion = self.suggestions.get((guild_id, number))
		if suggestion is None:
			return None
		if suggestion.decision is not None:
			raise SuggestionClosed
		votes = self.votes.setdefault((guild_id, number), {})
		if votes.get(user_id) is vote:
			del votes[user_id]
		else:
			votes[user_id] = vote
		counted = self._counted(guild_id, suggestion)
		return VoteResult(up=counted.up, down=counted.down, vote=votes.get(user_id))

	async def decide(
		self, guild_id: int, number: int, moderator_id: int, status: DecisionStatus, reason: str | None
	) -> Suggestion | None:
		suggestion = self.suggestions.get((guild_id, number))
		if suggestion is None:
			return None
		decision = SuggestionDecision(status=status, moderator_id=moderator_id, reason=reason)
		self.suggestions[(guild_id, number)] = suggestion.model_copy(update={"decision": decision})
		return await self.get(guild_id, number)
