"""The Ledger: the only code that changes ``economy`` balances."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
from api import Balance, ErrorCode, LeaderboardEntry, Wallet

from app.errors import ApiError

__all__ = ("Ledger",)


class Ledger:
	"""Reads and changes members' balances.

	Each write is one transaction with the accounts row-locked, and creates missing accounts. Cash never goes
	negative. Only ``remove_money(..., wallet="bank")`` can make the bank negative (debt). Added money pays off debt first.

	Args:
		db: The database pool.
	"""

	def __init__(self, db: asyncpg.Pool) -> None:
		self._db = db

	async def balance(self, guild_id: int, user_id: int) -> Balance:
		"""Get a member's balance.

		Args:
			guild_id: The guild the account belongs to.
			user_id: The member.

		Returns:
			The balance. All zero if the member has no account.
		"""
		row = await self._db.fetchrow(
			"SELECT cash, bank FROM economy WHERE guild_id = $1 AND user_id = $2", guild_id, user_id
		)
		return Balance(cash=int(row["cash"]), bank=int(row["bank"])) if row else Balance()

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
		async with self._accounts(guild_id, user_id) as (conn, (bal,)):
			return await self._write(conn, guild_id, user_id, _added(bal, amount, wallet))

	async def remove_money(self, guild_id: int, user_id: int, amount: int, wallet: Wallet = "cash") -> Balance:
		"""Take money from a member's wallet.

		Args:
			guild_id: The guild the account belongs to.
			user_id: The member to charge.
			amount: How much to take. Positive.
			wallet: The wallet the money comes from. The bank may go negative.

		Returns:
			The new balance.

		Raises:
			ApiError: ``insufficient_funds`` if ``wallet`` is ``"cash"`` and the member holds less than ``amount``.
		"""
		async with self._accounts(guild_id, user_id) as (conn, (bal,)):
			if wallet == "cash" and bal.cash < amount:
				raise ApiError(ErrorCode.INSUFFICIENT_FUNDS)
			return await self._write(conn, guild_id, user_id, _removed(bal, amount, wallet))

	async def move(self, guild_id: int, user_id: int, amount: int, source: Wallet, target: Wallet) -> Balance:
		"""Move money between a member's own wallets (deposit or withdraw).

		Args:
			guild_id: The guild the account belongs to.
			user_id: The member.
			amount: How much to move. Positive.
			source: The wallet the money leaves.
			target: The wallet the money reaches. Pays off debt first.

		Returns:
			The new balance.

		Raises:
			ApiError: ``insufficient_funds`` if ``source`` holds less than ``amount``.
		"""
		async with self._accounts(guild_id, user_id) as (conn, (bal,)):
			if bal[source] < amount:
				raise ApiError(ErrorCode.INSUFFICIENT_FUNDS)
			return await self._write(conn, guild_id, user_id, _added(_removed(bal, amount, source), amount, target))

	async def transfer(self, guild_id: int, sender_id: int, recipient_id: int, amount: int) -> None:
		"""Give cash from one member to another. If it fails, neither balance changes.

		Args:
			guild_id: The guild both accounts belong to.
			sender_id: The member who pays.
			recipient_id: The member who receives. Pays off their debt first.
			amount: How much cash to give. Positive.

		Raises:
			ApiError: ``same_account`` if the sender is the recipient. ``insufficient_funds`` if the sender is short.
		"""
		if sender_id == recipient_id:
			raise ApiError(ErrorCode.SAME_ACCOUNT, "cannot transfer to the same account")
		async with self._accounts(guild_id, sender_id, recipient_id) as (conn, (sender, recipient)):
			if sender.cash < amount:
				raise ApiError(ErrorCode.INSUFFICIENT_FUNDS)
			await self._write(conn, guild_id, sender_id, _removed(sender, amount, "cash"))
			await self._write(conn, guild_id, recipient_id, _added(recipient, amount, "cash"))

	async def leaderboard(self, guild_id: int, limit: int) -> list[LeaderboardEntry]:
		"""List a guild's richest members.

		Args:
			guild_id: The guild.
			limit: The most members to return.

		Returns:
			Members ordered by cash plus bank, richest first.
		"""
		rows = await self._db.fetch(
			"SELECT user_id, cash, bank FROM economy WHERE guild_id = $1 ORDER BY cash + bank DESC LIMIT $2",
			guild_id,
			limit,
		)
		return [LeaderboardEntry(user_id=int(r["user_id"]), cash=int(r["cash"]), bank=int(r["bank"])) for r in rows]

	@asynccontextmanager
	async def _accounts(
		self, guild_id: int, *user_ids: int
	) -> AsyncGenerator[tuple[asyncpg.Connection, list[Balance]], None]:
		"""Open a transaction with the members' accounts created and locked.

		Locks rows in ID order to avoid deadlocks.

		Args:
			guild_id: The guild the accounts belong to.
			*user_ids: The members.

		Yields:
			The connection, and the balances in the order of ``user_ids``.
		"""
		async with self._db.acquire() as conn, conn.transaction():
			for user_id in sorted(user_ids):
				await conn.execute(
					"INSERT INTO economy (guild_id, user_id) VALUES ($1, $2) ON CONFLICT (guild_id, user_id) DO NOTHING",
					guild_id,
					user_id,
				)
			rows = await conn.fetch(
				"SELECT user_id, cash, bank FROM economy WHERE guild_id = $1 AND user_id = ANY($2::numeric[]) "
				"ORDER BY user_id FOR UPDATE",
				guild_id,
				list(user_ids),
			)
			by_user = {int(r["user_id"]): Balance(cash=int(r["cash"]), bank=int(r["bank"])) for r in rows}
			yield conn, [by_user[user_id] for user_id in user_ids]

	@staticmethod
	async def _write(conn: asyncpg.Connection, guild_id: int, user_id: int, bal: Balance) -> Balance:
		"""Store a member's balance.

		Args:
			conn: The connection holding the transaction.
			guild_id: The guild the account belongs to.
			user_id: The member.
			bal: The new balance.

		Returns:
			The stored balance.
		"""
		await conn.execute(
			"UPDATE economy SET cash = $1, bank = $2 WHERE guild_id = $3 AND user_id = $4",
			bal.cash,
			bal.bank,
			guild_id,
			user_id,
		)
		return bal


def _added(bal: Balance, amount: int, wallet: Wallet) -> Balance:
	"""Add money to a balance, paying off debt first.

	Args:
		bal: The current balance.
		amount: How much to add.
		wallet: The wallet the money goes to.

	Returns:
		The new balance.
	"""
	repaid = min(amount, -bal.bank) if bal.in_debt else 0
	bank, rest = bal.bank + repaid, amount - repaid
	if wallet == "cash":
		return Balance(cash=bal.cash + rest, bank=bank)
	return Balance(cash=bal.cash, bank=bank + rest)


def _removed(bal: Balance, amount: int, wallet: Wallet) -> Balance:
	"""Take money from a balance. Doesn't check that the wallet holds it.

	Args:
		bal: The current balance.
		amount: How much to take.
		wallet: The wallet the money comes from.

	Returns:
		The new balance.
	"""
	if wallet == "cash":
		return Balance(cash=bal.cash - amount, bank=bal.bank)
	return Balance(cash=bal.cash, bank=bal.bank - amount)
