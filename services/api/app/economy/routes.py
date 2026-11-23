"""Internal API routes for the Ledger."""

from __future__ import annotations

from typing import Annotated

from api import AddMoneyRequest, Balance, LeaderboardEntry, MoveRequest, RemoveMoneyRequest, Snowflake, TransferRequest
from fastapi import APIRouter, Query, status

from app.auth import State

__all__ = ("internal",)

internal = APIRouter(prefix="/guilds/{guild_id}/economy", tags=["economy"])


@internal.get("/accounts/{user_id}")
async def balance(guild_id: Snowflake, user_id: Snowflake, state: State) -> Balance:
	"""Get a member's balance.

	\f
	Args:
		guild_id: The guild.
		user_id: The member.
		state: The app state.

	Returns:
		The balance. All zero if the member has no account.
	"""
	return await state.ledger.balance(guild_id, user_id)


@internal.post("/add-money")
async def add_money(guild_id: Snowflake, body: AddMoneyRequest, state: State) -> Balance:
	"""Add money to a member's wallet, paying off debt first.

	\f
	Args:
		guild_id: The guild.
		body: The member, amount and wallet.
		state: The app state.

	Returns:
		The new balance.
	"""
	return await state.ledger.add_money(guild_id, body.user_id, body.amount, body.wallet)


@internal.post("/remove-money")
async def remove_money(guild_id: Snowflake, body: RemoveMoneyRequest, state: State) -> Balance:
	"""Take money from a member's wallet. The bank may go negative.

	\f
	Args:
		guild_id: The guild.
		body: The member, amount and wallet.
		state: The app state.

	Returns:
		The new balance.

	Raises:
		ApiError: ``insufficient_funds`` if the member holds less cash than the amount.
	"""
	return await state.ledger.remove_money(guild_id, body.user_id, body.amount, body.wallet)


@internal.post("/move")
async def move(guild_id: Snowflake, body: MoveRequest, state: State) -> Balance:
	"""Move money between a member's cash and bank.

	\f
	Args:
		guild_id: The guild.
		body: The member, amount, source and target wallets.
		state: The app state.

	Returns:
		The new balance.

	Raises:
		ApiError: ``insufficient_funds`` if the source holds less than the amount.
	"""
	return await state.ledger.move(guild_id, body.user_id, body.amount, body.source, body.target)


@internal.post("/transfer", status_code=status.HTTP_204_NO_CONTENT)
async def transfer(guild_id: Snowflake, body: TransferRequest, state: State) -> None:
	"""Give cash from one member to another. If it fails, neither balance changes.

	\f
	Args:
		guild_id: The guild.
		body: The sender, recipient and amount.
		state: The app state.

	Raises:
		ApiError: ``same_account`` if the sender is the recipient. ``insufficient_funds`` if the sender is short.
	"""
	await state.ledger.transfer(guild_id, body.sender_id, body.recipient_id, body.amount)


@internal.get("/leaderboard")
async def leaderboard(
	guild_id: Snowflake, state: State, limit: Annotated[int, Query(ge=1, le=100)] = 10
) -> list[LeaderboardEntry]:
	"""List the guild's richest members.

	\f
	Args:
		guild_id: The guild.
		state: The app state.
		limit: The most members to return.

	Returns:
		Members by cash plus bank, richest first.
	"""
	return await state.ledger.leaderboard(guild_id, limit)
