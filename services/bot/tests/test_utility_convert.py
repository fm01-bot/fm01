"""The convert command: distance and weight math, and money through mocked Coinbase rates."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from cogs.utility import Unit, UnknownUnitError, Utility, convert_amount, physical_unit

# Units per 1 USD, as Coinbase quotes them.
RATES = {"USD": 1.0, "EUR": 0.5, "HUF": 400.0, "BTC": 0.00001, "ETH": 0.0005}
FIAT = {"USD", "EUR", "HUF"}


def _money(code: str) -> Unit:
	code = code.upper()
	if code not in RATES:
		raise UnknownUnitError(code)
	return Unit("currency" if code in FIAT else "crypto", code, RATES[code])


@pytest.fixture
def ctx() -> MagicMock:
	ctx = MagicMock()
	ctx.send = AsyncMock()
	return ctx


@pytest.fixture
def cog() -> Utility:
	cog = Utility(MagicMock())
	cog.rates.unit = AsyncMock(side_effect=_money)
	return cog


@pytest.mark.parametrize(
	("amount", "unit", "to", "expected"),
	[
		(1, "km", "m", 1000),
		(1, "mi", "km", 1.609344),
		(12, "inch", "ft", 1),
		(3, "FT", "yd", 1),
		(1, "kg", "lb", 2.2046226218),
		(16, "oz", "lb", 1),
		(1, "t", "kg", 1000),
		(1, "ton", "lb", 2000),
	],
)
def test_physical_conversions(amount, unit, to, expected):
	source, target = physical_unit(unit), physical_unit(to)
	assert source and target
	assert convert_amount(amount, source, target) == pytest.approx(expected)


def test_physical_unit_rejects_currencies():
	assert physical_unit("EUR") is None


async def test_converts_distance(cog, ctx):
	await cog.convert.callback(cog, ctx, 5, "km", "m")

	ctx.send.assert_awaited_once_with("convert.distance", amount=5, unit="km", result=pytest.approx(5000), to="m")
	cog.rates.unit.assert_not_awaited()


async def test_converts_weight(cog, ctx):
	await cog.convert.callback(cog, ctx, 2, "KG", "g")

	ctx.send.assert_awaited_once_with("convert.weight", amount=2, unit="kg", result=pytest.approx(2000), to="g")


async def test_converts_currency_through_usd(cog, ctx):
	await cog.convert.callback(cog, ctx, 10, "eur", "huf")

	ctx.send.assert_awaited_once_with("convert.currency", amount=10, unit="EUR", result=pytest.approx(8000), to="HUF")


@pytest.mark.parametrize(("unit", "to", "expected"), [("btc", "usd", 100_000), ("usd", "btc", 0.00001)])
async def test_crypto_on_either_side_uses_crypto_response(cog, ctx, unit, to, expected):
	await cog.convert.callback(cog, ctx, 1, unit, to)

	assert ctx.send.call_args.args == ("convert.crypto",)
	assert ctx.send.call_args.kwargs["result"] == pytest.approx(expected)


@pytest.mark.parametrize(("unit", "to"), [("km", "kg"), ("lb", "mi"), ("m", "EUR"), ("BTC", "g")])
async def test_rejects_incompatible_units(cog, ctx, unit, to):
	await cog.convert.callback(cog, ctx, 1, unit, to)

	assert ctx.send.call_args.args == ("convert.errors.incompatible",)


async def test_rejects_unknown_unit(cog, ctx):
	await cog.convert.callback(cog, ctx, 1, "parsec", "m")

	ctx.send.assert_awaited_once_with("convert.errors.unknown_unit", unit="PARSEC")


async def test_reports_unavailable_rates(cog, ctx):
	cog.rates.unit = AsyncMock(side_effect=aiohttp.ClientError())

	await cog.convert.callback(cog, ctx, 1, "EUR", "USD")

	ctx.send.assert_awaited_once_with("convert.errors.unavailable")
