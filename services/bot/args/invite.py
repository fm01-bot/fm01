import datetime
from dataclasses import dataclass, field

import discord

from args.channel import Channel, convert_to_custom_channel
from args.format_date_time import FormatDateTime
from args.user import User


@dataclass(slots=True)
class Invite:
	code: str
	"""The invite's code."""
	url: str
	"""The invite's URL."""
	_inviter: discord.User | None = field(repr=False)
	_created_at: datetime.datetime | None = field(repr=False)
	_max_age: int | None = field(repr=False)
	max_uses: int | None
	"""The maximum number of uses for the invite."""
	temporary: bool | None
	"""Whether the invite is temporary."""
	_channel: discord.abc.GuildChannel | None
	uses: int | None
	"""The number of times the invite has been used."""

	@classmethod
	def from_invite(cls, invite: discord.Invite):
		return cls(
			code=invite.code,
			url=invite.url,
			_inviter=invite.inviter,
			_created_at=invite.created_at,
			_max_age=invite.max_age,
			max_uses=invite.max_uses,
			temporary=invite.temporary,
			_channel=invite.channel,  # type: ignore
			uses=invite.uses,
		)

	@property
	def max_age(self) -> FormatDateTime | None:
		"""When the invite expires, as a relative timestamp. ``None`` if it never does."""
		if not self._max_age or not self._created_at:
			return None
		return FormatDateTime(self._created_at + datetime.timedelta(seconds=self._max_age), "R")

	expires = max_age

	@property
	def inviter(self) -> User | None:
		"""The user who created the invite."""
		return User.from_user(self._inviter) if self._inviter else None

	author = inviter

	@property
	def created_at(self) -> FormatDateTime | None:
		"""The date the invite was created as a Discord timestamp. This is not available in ``on_invite_delete`` events."""
		return FormatDateTime(self._created_at, "f") if self._created_at else None

	created = created_at

	@property
	def channel(self) -> Channel | None:
		"""The channel the invite is for."""
		return convert_to_custom_channel(self._channel)

	def __str__(self) -> str:
		return self.code
