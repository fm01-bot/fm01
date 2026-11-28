"""The API client against a stand-in Internal API: requests on the wire, and errors mapped back to exceptions."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from core.api import ApiClient, ApiError, ApiUnavailable, InsufficientFunds, SuggestionClosed, SuggestionsDisabled

from api import Balance, Prefix, Vote

BIG = 1234567890123456789  # loses precision as a JavaScript number


class StandIn:
	"""Records requests and answers with whatever the test queued."""

	def __init__(self) -> None:
		self.requests: list[dict[str, Any]] = []
		self.status = 200
		self.body: Any = {}

	async def handle(self, request: web.Request) -> web.Response:
		self.requests.append(
			{
				"method": request.method,
				"path": request.path,
				"query": dict(request.query),
				"headers": dict(request.headers),
				"json": await request.json() if request.can_read_body else None,
			}
		)
		if self.status == 204:
			return web.Response(status=204)
		return web.Response(status=self.status, text=json.dumps(self.body), content_type="application/json")


@pytest.fixture
async def stand_in() -> AsyncIterator[tuple[StandIn, ApiClient]]:
	fake = StandIn()
	app = web.Application()
	app.router.add_route("*", "/{tail:.*}", fake.handle)
	server = TestServer(app)
	await server.start_server()
	client = ApiClient(str(server.make_url("")), "secret", "instance-a")
	try:
		yield fake, client
	finally:
		await client.close()
		await server.close()


async def test_add_money_sends_snowflakes_as_strings_with_token_and_origin(stand_in):
	fake, client = stand_in
	fake.body = {"cash": 50, "bank": 0}

	balance = await client.economy.add_money(7, BIG, 50, "bank")

	assert balance == Balance(cash=50)
	request = fake.requests[0]
	assert (request["method"], request["path"]) == ("POST", "/internal/guilds/7/economy/add-money")
	assert request["json"] == {"user_id": str(BIG), "amount": 50, "wallet": "bank"}
	assert request["headers"]["Authorization"] == "Bearer secret"
	assert request["headers"]["X-Fm01-Origin"] == "instance-a"


async def test_snowflakes_in_responses_become_ints(stand_in):
	fake, client = stand_in
	fake.body = [{"user_id": str(BIG), "cash": 1, "bank": 2}]

	(entry,) = await client.economy.leaderboard(7, limit=5)

	assert entry.user_id == BIG
	assert fake.requests[0]["query"] == {"limit": "5"}


async def test_insufficient_funds_is_raised_as_the_cogs_exception(stand_in):
	fake, client = stand_in
	fake.status, fake.body = 409, {"code": "insufficient_funds", "message": "insufficient funds"}

	with pytest.raises(InsufficientFunds):
		await client.economy.remove_money(7, 1, 10)


async def test_self_transfer_is_refused_without_a_request(stand_in):
	fake, client = stand_in

	with pytest.raises(ValueError):
		await client.economy.transfer(7, 1, 1, 10)
	assert fake.requests == []


async def test_server_errors_and_garbage_are_unavailable(stand_in):
	fake, client = stand_in
	fake.status = 503
	with pytest.raises(ApiUnavailable):
		await client.economy.balance(7, 1)

	fake.status, fake.body = 200, {"unexpected": True, "cash": "lots"}
	with pytest.raises(ApiUnavailable):
		await client.economy.balance(7, 1)


async def test_other_refusals_keep_their_code(stand_in):
	fake, client = stand_in
	fake.status, fake.body = 404, {"code": "not_found", "message": "nope"}

	with pytest.raises(ApiError) as exc:
		await client.settings.prefix(7)
	assert exc.value.code == "not_found"


async def test_unreachable_api_is_unavailable():
	client = ApiClient("http://127.0.0.1:9", "secret", "instance-a", timeout=2)
	try:
		with pytest.raises(ApiUnavailable):
			await client.settings.prefix(7)
	finally:
		await client.close()


async def test_settings_round_trip(stand_in):
	fake, client = stand_in
	fake.body = {"prefix": "!", "mention": False}
	await client.settings.set_prefix(7, Prefix(prefix="!", mention=False))
	assert fake.requests[-1]["json"] == {"prefix": "!", "mention": False}

	fake.body = [{"guild_id": "1", "locale": "hu"}, {"guild_id": str(BIG), "locale": "de"}]
	assert await client.settings.all_locales() == {1: "hu", BIG: "de"}

	fake.status = 204
	await client.economy.transfer(7, 1, 2, 3)
	assert fake.requests[-1]["path"] == "/internal/guilds/7/economy/transfer"


async def test_suggestions_disabled_is_raised_as_the_cogs_exception(stand_in):
	fake, client = stand_in
	fake.status, fake.body = 409, {"code": "suggestions_disabled", "message": "suggestions disabled"}

	with pytest.raises(SuggestionsDisabled):
		await client.suggestions.create(7, BIG, "More emoji")

	request = fake.requests[0]
	assert (request["method"], request["path"]) == ("POST", "/internal/guilds/7/suggestions")
	assert request["json"] == {"author_id": str(BIG), "content": "More emoji"}


async def test_a_closed_suggestion_is_raised_as_the_cogs_exception(stand_in):
	fake, client = stand_in
	fake.status, fake.body = 409, {"code": "suggestion_closed", "message": "suggestion closed"}

	with pytest.raises(SuggestionClosed):
		await client.suggestions.vote(7, 3, BIG, Vote.UP)

	assert fake.requests[0]["json"] == {"user_id": str(BIG), "vote": "up"}


async def test_an_unknown_suggestion_is_none(stand_in):
	fake, client = stand_in
	fake.status, fake.body = 404, {"code": "not_found", "message": "no such suggestion"}

	assert await client.suggestions.get(7, 3) is None
	assert await client.suggestions.vote(7, 3, BIG, Vote.UP) is None
