"""Support tickets: the bot's Internal API operations."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.db

GUILD = 100
CHANNEL, USER, STAFF = 2001, 10, 20


async def open_ticket(api, channel: int = CHANNEL, user: int = USER) -> dict:
	response = await api.client.post(
		f"/internal/guilds/{GUILD}/tickets",
		json={"channel_id": str(channel), "user_id": str(user), "title": "help", "description": "it broke"},
		headers=api.internal,
	)
	assert response.status_code == 201, response.text
	return response.json()


async def count(api, user: int = USER) -> int:
	response = await api.client.get(
		f"/internal/guilds/{GUILD}/tickets/open-count", params={"user_id": user}, headers=api.internal
	)
	return response.json()["count"]


async def test_an_opened_ticket_is_found_by_its_channel_and_counted(api):
	ticket = await open_ticket(api)
	await open_ticket(api, channel=2002)

	found = await api.client.get(f"/internal/channels/{CHANNEL}/ticket", headers=api.internal)

	assert found.json() == ticket
	assert ticket["archived"] is False
	assert await count(api) == 2


async def test_archiving_and_reopening(api):
	ticket = await open_ticket(api)
	base = f"/internal/guilds/{GUILD}/tickets/{ticket['id']}"

	archived = await api.client.post(f"{base}/archive", headers=api.internal)
	reopened = await api.client.post(f"{base}/reopen", headers=api.internal)
	elsewhere = await api.client.post(f"/internal/guilds/999/tickets/{ticket['id']}/archive", headers=api.internal)

	assert archived.json()["archived"] is True
	assert reopened.json()["archived"] is False
	assert elsewhere.status_code == 404


async def test_closing_records_who_and_frees_the_channel(api):
	ticket = await open_ticket(api)

	closed = await api.client.post(
		f"/internal/guilds/{GUILD}/tickets/{ticket['id']}/close", json={"closed_by": str(STAFF)}, headers=api.internal
	)

	assert closed.json()["closed"] is True
	assert closed.json()["archived"] is True
	assert closed.json()["closed_by"] == str(STAFF)
	assert closed.json()["closed_at"] is not None
	assert (await api.client.get(f"/internal/channels/{CHANNEL}/ticket", headers=api.internal)).status_code == 404
	assert await count(api) == 0


async def test_deleting_the_channel_closes_its_ticket(api):
	await open_ticket(api)

	response = await api.client.post(f"/internal/channels/{CHANNEL}/deleted", headers=api.internal)

	assert response.status_code == 204
	assert await count(api) == 0
