"""The Ledger, against real PostgreSQL, through the Internal API."""

from __future__ import annotations

import asyncio

import pytest
from api import Balance, ErrorCode
from app.economy.store import Ledger
from app.errors import ApiError

pytestmark = pytest.mark.db

GUILD = 1
ALICE, BOB = 10, 20
BIG = 1234567890123456789  # above 2**53: loses precision as a JavaScript number


@pytest.fixture
def ledger(db) -> Ledger:
	return Ledger(db)


async def test_new_members_have_nothing_and_no_row(ledger, db):
	assert await ledger.balance(GUILD, ALICE) == Balance()
	assert await db.fetchval("SELECT count(*) FROM economy") == 0


async def test_add_money_pays_off_debt_first(ledger):
	await ledger.remove_money(GUILD, ALICE, 300, "bank")  # admin removal into debt
	assert (await ledger.balance(GUILD, ALICE)).in_debt

	assert await ledger.add_money(GUILD, ALICE, 500) == Balance(cash=200, bank=0)


async def test_cash_never_goes_negative(ledger):
	await ledger.add_money(GUILD, ALICE, 100)

	with pytest.raises(ApiError) as exc:
		await ledger.remove_money(GUILD, ALICE, 101)
	assert exc.value.code is ErrorCode.INSUFFICIENT_FUNDS
	assert await ledger.balance(GUILD, ALICE) == Balance(cash=100)


async def test_move_between_wallets_is_all_or_nothing(ledger):
	await ledger.add_money(GUILD, ALICE, 100)

	assert await ledger.move(GUILD, ALICE, 60, "cash", "bank") == Balance(cash=40, bank=60)
	with pytest.raises(ApiError):
		await ledger.move(GUILD, ALICE, 61, "bank", "cash")
	assert await ledger.balance(GUILD, ALICE) == Balance(cash=40, bank=60)


async def test_transfer_moves_cash_and_creates_the_recipient(ledger):
	await ledger.add_money(GUILD, ALICE, 100)

	await ledger.transfer(GUILD, ALICE, BOB, 70)

	assert await ledger.balance(GUILD, ALICE) == Balance(cash=30)
	assert await ledger.balance(GUILD, BOB) == Balance(cash=70)
	with pytest.raises(ApiError) as exc:
		await ledger.transfer(GUILD, ALICE, ALICE, 1)
	assert exc.value.code is ErrorCode.SAME_ACCOUNT


async def test_concurrent_operations_lose_no_money(ledger, db):
	"""Opposing transfers and first-time additions racing each other: no deadlock, no lost update, one row each."""
	await ledger.add_money(GUILD, ALICE, 1000)
	await ledger.add_money(GUILD, BOB, 1000)

	await asyncio.gather(
		*(ledger.transfer(GUILD, ALICE, BOB, 10) for _ in range(20)),
		*(ledger.transfer(GUILD, BOB, ALICE, 5) for _ in range(20)),
		*(ledger.add_money(GUILD, 30, 1) for _ in range(20)),
	)

	assert await ledger.balance(GUILD, ALICE) == Balance(cash=900)
	assert await ledger.balance(GUILD, BOB) == Balance(cash=1100)
	assert await ledger.balance(GUILD, 30) == Balance(cash=20)
	assert await db.fetchval("SELECT count(*) FROM economy") == 3


async def test_http_operations_and_snowflakes_as_strings(api):
	response = await api.client.post(
		f"/internal/guilds/{GUILD}/economy/add-money", json={"user_id": str(BIG), "amount": 50}, headers=api.internal
	)
	assert response.status_code == 200
	assert response.json() == {"cash": 50, "bank": 0}

	board = await api.client.get(f"/internal/guilds/{GUILD}/economy/leaderboard", headers=api.internal)
	assert board.json() == [{"user_id": str(BIG), "cash": 50, "bank": 0}]

	balance = await api.client.get(f"/internal/guilds/{GUILD}/economy/accounts/{BIG}", headers=api.internal)
	assert balance.json() == {"cash": 50, "bank": 0}


async def test_http_errors_carry_a_code(api):
	response = await api.client.post(
		f"/internal/guilds/{GUILD}/economy/remove-money", json={"user_id": "10", "amount": 1}, headers=api.internal
	)
	assert response.status_code == 409
	assert response.json()["code"] == "insufficient_funds"

	invalid = await api.client.post(
		f"/internal/guilds/{GUILD}/economy/add-money", json={"user_id": "10", "amount": 0}, headers=api.internal
	)
	assert invalid.status_code == 422
	assert invalid.json()["code"] == "invalid_request"

	transfer = await api.client.post(
		f"/internal/guilds/{GUILD}/economy/transfer",
		json={"sender_id": "10", "recipient_id": "10", "amount": 1},
		headers=api.internal,
	)
	assert transfer.json()["code"] == "same_account"
