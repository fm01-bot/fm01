"""The Ledger: members' money in a guild."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.snowflake import Snowflake

__all__ = (
	"AddMoneyRequest",
	"Amount",
	"Balance",
	"LeaderboardEntry",
	"MoveRequest",
	"RemoveMoneyRequest",
	"TransferRequest",
	"Wallet",
)

Wallet = Literal["cash", "bank"]
"""Where a member keeps money."""
Amount = Annotated[int, Field(gt=0, lt=2**63)]
"""A positive amount of money that fits in PostgreSQL's ``bigint``."""


class Balance(BaseModel):
	"""A member's money in one guild. ``bank`` is negative while the member is in debt."""

	model_config = ConfigDict(frozen=True)

	cash: int = 0
	bank: int = 0

	@property
	def in_debt(self) -> bool:
		"""Whether the bank is negative."""
		return self.bank < 0

	def __getitem__(self, wallet: Wallet) -> int:
		"""Get the money in one wallet.

		Args:
			wallet: The wallet.

		Returns:
			The amount. Negative for a bank in debt.
		"""
		return self.cash if wallet == "cash" else self.bank


class AddMoneyRequest(BaseModel):
	"""Add money to a member's wallet. Any debt is paid off first."""

	user_id: Snowflake
	amount: Amount
	wallet: Wallet = "cash"


class RemoveMoneyRequest(BaseModel):
	"""Take money from a member's wallet. Cash can't go negative. The bank can, which records debt."""

	user_id: Snowflake
	amount: Amount
	wallet: Wallet = "cash"


class MoveRequest(BaseModel):
	"""Move money between a member's own wallets. The source must hold the amount."""

	user_id: Snowflake
	amount: Amount
	source: Wallet
	target: Wallet


class TransferRequest(BaseModel):
	"""Move cash from one member to another. If it fails, neither balance changes."""

	sender_id: Snowflake
	recipient_id: Snowflake
	amount: Amount


class LeaderboardEntry(BaseModel):
	"""One member on a guild's leaderboard."""

	user_id: Snowflake
	cash: int
	bank: int
