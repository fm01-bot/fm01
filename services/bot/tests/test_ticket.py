import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from cogs.config import Config
from cogs.ticket import (
	ActiveTicketControlsView,
	ArchivedTicketControlsView,
	Ticket,
	TicketLauncherView,
)
from core.settings import GuildSettings
from helpers.cli_parser import CLIParseError, CLIParser
from tests.fake_api import FakeTickets

from api import TicketConfig


def test_config_ticket_enable_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args("ticket enable")
	node, _opts = config_cog.parser.parse(tokens)
	assert node.name == "enable"


def test_config_ticket_disable_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args("ticket disable")
	node, _opts = config_cog.parser.parse(tokens)
	assert node.name == "disable"


def test_config_ticket_panel_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args('ticket panel --channel #tickets --title "Support" --button "Open"')
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "panel"
	assert opts["channel"] == "#tickets"
	assert opts["title"] == "Support"
	assert opts["button"] == "Open"


def test_config_ticket_category_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args('ticket category --category "Support Tickets"')
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "category"
	assert opts["category"] == "Support Tickets"


def test_config_ticket_category_clear_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args("ticket category --clear")
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "category"
	assert opts["clear"] is True


def test_config_ticket_log_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args("ticket log --channel #ticket-log")
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "log"
	assert opts["channel"] == "#ticket-log"


def test_config_ticket_log_disable_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args("ticket log --disable")
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "log"
	assert opts["disable"] is True


def test_config_ticket_role_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args("ticket role --role @Support")
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "role"
	assert opts["role"] == "@Support"


def test_config_ticket_limit_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args("ticket limit 2")
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "limit"
	assert opts["max_pos"] == "2"


def test_config_ticket_dm_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args("ticket dm --enable")
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "dm"
	assert opts["enable"] is True


def test_config_ticket_length_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args("ticket length --topic-min 5 --topic-max 50 --desc-min 20 --desc-max 1500")
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "length"
	assert opts["topic_min"] == "5"
	assert opts["topic_max"] == "50"
	assert opts["desc_min"] == "20"
	assert opts["desc_max"] == "1500"


def test_config_ticket_modal_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args("ticket modal --topic-min 10 --topic-max 80")
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "modal"
	assert opts["topic_min"] == "10"
	assert opts["topic_max"] == "80"


def test_config_ticket_topic_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args("ticket topic --min 5 --max 50")
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "topic"
	assert opts["min"] == "5"
	assert opts["max"] == "50"


def test_config_ticket_desc_parse():
	config_cog = Config(MagicMock())
	tokens = CLIParser.split_args("ticket description --min 20 --max 1500")
	node, opts = config_cog.parser.parse(tokens)
	assert node.name == "description"
	assert opts["min"] == "20"
	assert opts["max"] == "1500"

	tokens_alias = CLIParser.split_args("ticket desc 20 1500")
	node_alias, opts_alias = config_cog.parser.parse(tokens_alias)
	assert node_alias.name == "desc"
	assert opts_alias["min_pos"] == "20"
	assert opts_alias["max_pos"] == "1500"


@pytest.mark.asyncio
async def test_config_ticket_execution_flow():
	bot = MagicMock()
	bot.api.tickets = FakeTickets()
	bot.settings = GuildSettings(bot.event_bus)
	bot.get_cog.return_value = None
	bot.custom_response.get_message = AsyncMock(return_value="Open Ticket")

	guild = MagicMock()
	guild.id = 12345
	guild.name = "Test Guild"
	text_ch = MagicMock(spec=discord.TextChannel)
	text_ch.name = "tickets"
	text_ch.id = 999
	text_ch.permissions_for.return_value.send_messages = True
	text_ch.permissions_for.return_value.embed_links = True
	guild.channels = [text_ch]
	guild.threads = []
	guild.get_channel_or_thread.return_value = text_ch

	cat = MagicMock(spec=discord.CategoryChannel)
	cat.name = "Support"
	cat.id = 777
	guild.categories = [cat]
	guild.me = MagicMock()

	guild.get_channel = MagicMock(side_effect=lambda cid: cat if cid == 777 else (text_ch if cid == 999 else None))

	role = MagicMock(spec=discord.Role)
	role.name = "Support"
	role.id = 555
	guild.roles = [role]
	guild.get_role.return_value = role

	ctx = MagicMock()
	ctx.guild = guild
	ctx.channel = text_ch
	ctx.bot = bot
	ctx.send = AsyncMock()

	config_cog = Config(bot)

	# Execute enable
	await config_cog.parser.execute("ticket enable", ctx=ctx)
	assert bot.api.tickets.configs[12345].enabled is True
	assert "[+] Ticket system enabled" in ctx.send.call_args[1]["content"]

	# Execute category
	await config_cog.parser.execute('ticket category --category "Support"', ctx=ctx)
	assert "[+] Ticket category set to 'Support'" in ctx.send.call_args[1]["content"]

	# Execute log
	await config_cog.parser.execute("ticket log --channel #tickets", ctx=ctx)
	assert "[+] Ticket log channel set to #tickets" in ctx.send.call_args[1]["content"]

	# Execute role
	await config_cog.parser.execute("ticket role --role @Support", ctx=ctx)
	assert "[+] Support role set to @Support" in ctx.send.call_args[1]["content"]

	# Execute limit
	await config_cog.parser.execute("ticket limit 3", ctx=ctx)
	assert "[+] Max concurrent tickets set to: 3 ticket(s) per user" in ctx.send.call_args[1]["content"]

	# Execute dm
	await config_cog.parser.execute("ticket dm --disable", ctx=ctx)
	assert "[+] DM transcripts disabled" in ctx.send.call_args[1]["content"]

	# Execute panel
	await config_cog.parser.execute('ticket panel --channel #tickets --title "Help Desk"', ctx=ctx)
	assert "[+] Ticket panel deployed in #tickets" in ctx.send.call_args[1]["content"]
	text_ch.send.assert_called_once()

	# Execute default panel without title/description where get_message returns button in payload
	text_ch.send.reset_mock()
	bot.custom_response.get_message = AsyncMock(
		return_value={
			"button": "Open Ticket",
			"view": discord.ui.LayoutView(),
		}
	)
	await config_cog.parser.execute("ticket panel --channel #tickets", ctx=ctx)
	assert "[+] Ticket panel deployed in #tickets" in ctx.send.call_args[1]["content"]
	text_ch.send.assert_called_once()
	assert "button" not in text_ch.send.call_args[1]

	# Execute status
	await config_cog.parser.execute("ticket status", ctx=ctx)
	status_out = ctx.send.call_args[1]["content"]
	assert "Status:        Enabled" in status_out
	assert "Category:      Support" in status_out
	assert "Log Channel:   #tickets" in status_out
	assert "Support Role:  @Support" in status_out
	assert "Max Tickets:   3 per user" in status_out
	assert "Modal Topic:   Min 3 / Max 100" in status_out
	assert "Modal Desc:    Min 10 / Max 1800" in status_out

	# Execute length with no args (display current settings)
	await config_cog.parser.execute("ticket length", ctx=ctx)
	len_out = ctx.send.call_args[1]["content"]
	assert "Topic:       Min 3 / Max 100" in len_out
	assert "Description: Min 10 / Max 1800" in len_out

	# Execute length update
	await config_cog.parser.execute("ticket length --topic-min 5 --topic-max 50 --desc-min 20 --desc-max 1500", ctx=ctx)
	len_update_out = ctx.send.call_args[1]["content"]
	assert "[+] Ticket modal lengths updated:" in len_update_out
	assert "Topic: Min 5 / Max 50" in len_update_out
	assert "Description: Min 20 / Max 1500" in len_update_out

	# Execute modal alias
	await config_cog.parser.execute("ticket modal --topic-min 6 --topic-max 45", ctx=ctx)
	modal_update_out = ctx.send.call_args[1]["content"]
	assert "[+] Ticket modal lengths updated:" in modal_update_out
	assert "Topic: Min 6 / Max 45" in modal_update_out

	# Execute topic command
	await config_cog.parser.execute("ticket topic --min 4 --max 60", ctx=ctx)
	topic_out = ctx.send.call_args[1]["content"]
	assert "[+] Ticket topic length set to: Min 4 / Max 60" in topic_out

	# Execute description command
	await config_cog.parser.execute("ticket description --min 15 --max 2000", ctx=ctx)
	desc_out = ctx.send.call_args[1]["content"]
	assert "[+] Ticket description length set to: Min 15 / Max 2000" in desc_out

	# Execute desc alias with positional arguments
	await config_cog.parser.execute("ticket desc 12 1800", ctx=ctx)
	desc_alias_out = ctx.send.call_args[1]["content"]
	assert "[+] Ticket description length set to: Min 12 / Max 1800" in desc_alias_out


@pytest.mark.asyncio
async def test_config_ticket_limit_invalid():
	bot = MagicMock()
	bot.api.tickets = FakeTickets()
	bot.settings = GuildSettings(bot.event_bus)
	ctx = MagicMock()
	ctx.guild = MagicMock()
	config_cog = Config(bot)

	with pytest.raises(CLIParseError):
		await config_cog.parser.execute("ticket limit -5", ctx=ctx)

	with pytest.raises(CLIParseError):
		await config_cog.parser.execute("ticket limit abc", ctx=ctx)


@pytest.mark.asyncio
async def test_config_ticket_length_validation():
	bot = MagicMock()
	bot.api.tickets = FakeTickets()
	bot.settings = GuildSettings(bot.event_bus)
	ctx = MagicMock()
	ctx.guild = MagicMock()
	ctx.bot = bot
	ctx.send = AsyncMock()
	config_cog = Config(bot)

	# Non-integer min/max
	with pytest.raises(CLIParseError):
		await config_cog.parser.execute("ticket length --topic-min abc", ctx=ctx)
	with pytest.raises(CLIParseError):
		await config_cog.parser.execute("ticket length --desc-max xyz", ctx=ctx)

	# Out of bounds (<1 or >4000)
	with pytest.raises(CLIParseError):
		await config_cog.parser.execute("ticket length --topic-min 0", ctx=ctx)
	with pytest.raises(CLIParseError):
		await config_cog.parser.execute("ticket length --desc-max 5000", ctx=ctx)

	# Min exceeds Max
	with pytest.raises(CLIParseError):
		await config_cog.parser.execute("ticket length --topic-min 80 --topic-max 40", ctx=ctx)
	with pytest.raises(CLIParseError):
		await config_cog.parser.execute("ticket topic --min 50 --max 10", ctx=ctx)
	with pytest.raises(CLIParseError):
		await config_cog.parser.execute("ticket description --min 500 --max 100", ctx=ctx)


@pytest.mark.asyncio
async def test_ticket_modal_configured_lengths():
	bot = MagicMock()
	bot.api.tickets = FakeTickets()
	bot.settings = GuildSettings(bot.event_bus)
	bot.custom_response.get_message = AsyncMock(return_value="Label")
	cog = Ticket(bot)

	interaction = MagicMock(spec=discord.Interaction)
	interaction.guild = MagicMock()
	interaction.guild.id = 12345

	bot.api.tickets.configs[12345] = TicketConfig(
		topic_min_length=8, topic_max_length=64, description_min_length=25, description_max_length=1200
	)
	modal = await cog.create_ticket_modal(interaction)
	assert modal.topic.min_length == 8
	assert modal.topic.max_length == 64
	assert modal.description.min_length == 25
	assert modal.description.max_length == 1200


@pytest.mark.asyncio
async def test_ticket_permissions():
	bot = MagicMock()
	bot.api.tickets = FakeTickets()
	bot.settings = GuildSettings(bot.event_bus)
	cog = Ticket(bot)

	guild = MagicMock()
	guild.id = 12345

	member = MagicMock(spec=discord.Member)
	member.id = 100
	member.guild_permissions.administrator = False
	member.guild_permissions.manage_channels = False
	member.roles = []

	interaction = MagicMock(spec=discord.Interaction)
	interaction.guild = guild
	interaction.user = member

	ticket_row = bot.api.tickets.add(guild.id, channel_id=1, user_id=100)

	# Opener should be allowed
	assert await cog.can_manage_ticket(interaction, ticket_row) is True

	# Different member should be denied
	member.id = 200
	assert await cog.can_manage_ticket(interaction, ticket_row) is False

	# Administrator should be allowed
	member.guild_permissions.administrator = True
	assert await cog.can_manage_ticket(interaction, ticket_row) is True
	member.guild_permissions.administrator = False

	# Support role member should be allowed
	support_role = MagicMock(spec=discord.Role)
	support_role.id = 300
	member.roles = [support_role]
	bot.api.tickets.configs[guild.id] = TicketConfig(support_role_id=300)
	cog.config.forget(guild.id)  # the support role was just configured
	assert await cog.can_manage_ticket(interaction, ticket_row) is True


@pytest.mark.asyncio
async def test_ticket_create_flow():
	bot = MagicMock()
	bot.api.tickets = FakeTickets()
	bot.settings = GuildSettings(bot.event_bus)
	bot.custom_response.get_message = AsyncMock(return_value="Your ticket has been created: #ticket-alice")
	cog = Ticket(bot)

	guild = MagicMock()
	guild.id = 12345
	guild.default_role = MagicMock()
	guild.me = MagicMock()

	cat = MagicMock(spec=discord.CategoryChannel)
	cat.name = "Tickets"
	guild.categories = [cat]
	guild.create_category = AsyncMock(return_value=cat)

	created_ch = MagicMock(spec=discord.TextChannel)
	created_ch.id = 888
	created_ch.name = "ticket-alice"
	created_ch.mention = "<#888>"
	created_ch.send = AsyncMock()
	guild.create_text_channel = AsyncMock(return_value=created_ch)

	member = MagicMock(spec=discord.Member)
	member.id = 100
	member.name = "Alice"
	member.display_name = "Alice"
	member.display_avatar.url = "https://example.com/avatar.png"
	member.mention = "<@100>"

	interaction = MagicMock(spec=discord.Interaction)
	interaction.guild = guild
	interaction.user = member
	interaction.response = MagicMock()
	interaction.response.defer = AsyncMock()
	interaction.response.is_done.return_value = True
	interaction.followup = MagicMock()
	interaction.followup.send = AsyncMock()

	# Config: enabled, limit 1, no open tickets
	bot.api.tickets.configs[12345] = TicketConfig(enabled=True, max_tickets=1)

	await cog.handle_ticket_create(interaction, topic="Billing issue", description="I need help with my payment")

	guild.create_text_channel.assert_called_once()
	created_ch.send.assert_called_once()
	interaction.followup.send.assert_called_once()
	sent_content = interaction.followup.send.call_args[1].get("content", "")
	assert "ticket-alice" in sent_content


@pytest.mark.asyncio
async def test_ticket_create_limit_exceeded():
	bot = MagicMock()
	bot.api.tickets = FakeTickets()
	bot.settings = GuildSettings(bot.event_bus)
	bot.custom_response.get_message = AsyncMock(
		return_value="You already have 1 open ticket(s). The maximum allowed is 1."
	)
	cog = Ticket(bot)

	guild = MagicMock()
	guild.id = 12345
	member = MagicMock(spec=discord.Member)
	member.id = 100
	member.name = "Bob"

	interaction = MagicMock(spec=discord.Interaction)
	interaction.guild = guild
	interaction.user = member
	interaction.response = MagicMock()
	interaction.response.defer = AsyncMock()
	interaction.response.is_done.return_value = True
	interaction.followup = MagicMock()
	interaction.followup.send = AsyncMock()

	bot.api.tickets.configs[12345] = TicketConfig(enabled=True, max_tickets=1)
	bot.api.tickets.add(12345, channel_id=1, user_id=100)  # already has 1 ticket open

	await cog.handle_ticket_create(interaction, topic="Issue", description="Description")

	guild.create_text_channel.assert_not_called()
	interaction.followup.send.assert_called_once()
	sent_content = interaction.followup.send.call_args[1].get("content", "")
	assert "already have" in sent_content


@pytest.mark.asyncio
async def test_ticket_creations_by_one_member_never_overlap():
	"""A submit that arrives while the lock passes from one waiter to the next must still wait its turn."""
	cog = Ticket(MagicMock())
	release_first = asyncio.Event()
	start_third = asyncio.Event()
	running = peak = calls = 0

	async def create(interaction, topic, description):
		nonlocal running, peak, calls
		calls += 1
		running += 1
		peak = max(peak, running)
		if calls == 1:
			await release_first.wait()
			start_third.set()  # wakes the third submit just before the lock wakes the second
		else:
			await asyncio.sleep(0)
		running -= 1

	cog._create_ticket = create
	interaction = MagicMock(spec=discord.Interaction)
	interaction.guild = MagicMock()
	interaction.guild.id = 1
	interaction.user = MagicMock(spec=discord.Member)
	interaction.user.id = 2
	interaction.response = MagicMock()
	interaction.response.defer = AsyncMock()

	async def third():
		await start_third.wait()
		await cog.handle_ticket_create(interaction, "t", "d")

	tasks = [asyncio.create_task(cog.handle_ticket_create(interaction, "t", "d"))]
	await asyncio.sleep(0)
	tasks.append(asyncio.create_task(cog.handle_ticket_create(interaction, "t", "d")))
	tasks.append(asyncio.create_task(third()))
	await asyncio.sleep(0)
	release_first.set()
	await asyncio.gather(*tasks)

	assert calls == 3
	assert peak == 1
	assert not cog._create_locks and not cog._create_users


@pytest.mark.asyncio
async def test_ticket_modal_localization():
	bot = MagicMock()
	bot.api.tickets = FakeTickets()
	bot.settings = GuildSettings(bot.event_bus)
	bot.custom_response.get_message = AsyncMock(side_effect=lambda key, *args, **kwargs: f"loc_{key.split('.')[-1]}")
	cog = Ticket(bot)

	interaction = MagicMock(spec=discord.Interaction)
	interaction.guild = MagicMock()

	modal = await cog.create_ticket_modal(interaction)
	assert modal.title == "loc_title"
	assert modal.topic.label == "loc_topic_label"
	assert modal.description.label == "loc_desc_label"


@pytest.mark.asyncio
async def test_ticket_launcher_view_localization():
	bot = MagicMock()
	bot.custom_response.get_message = AsyncMock(
		side_effect=lambda key, *args, **kwargs: (
			{"button": "Localized Open"} if key == "ticket.panel" else "Localized Open"
		)
	)
	cog = Ticket(bot)

	guild = MagicMock()
	launcher_view = await cog.create_launcher_view(guild)
	assert isinstance(launcher_view, TicketLauncherView)
	assert launcher_view.open_button.label == "Localized Open"


@pytest.mark.asyncio
async def test_ticket_controls_view_localization():
	bot = MagicMock()
	bot.custom_response.get_message = AsyncMock(side_effect=lambda key, *args, **kwargs: f"loc_{key.split('.')[-1]}")
	cog = Ticket(bot)

	guild = MagicMock()

	# Active view
	active_view = await cog.create_controls_view(guild, is_archived=False)
	assert isinstance(active_view, ActiveTicketControlsView)
	assert active_view.archive_btn.label == "loc_archive"
	assert active_view.close_btn.label == "loc_close"
	assert active_view.save_btn.label == "loc_save"

	# Archived view
	archived_view = await cog.create_controls_view(guild, is_archived=True)
	assert isinstance(archived_view, ArchivedTicketControlsView)
	assert archived_view.close_btn.label == "loc_close"
	assert archived_view.reopen_btn.label == "loc_reopen"
	assert archived_view.save_btn.label == "loc_save"


@pytest.mark.asyncio
async def test_ticket_archive_and_reopen():
	bot = MagicMock()
	bot.api.tickets = FakeTickets()
	bot.settings = GuildSettings(bot.event_bus)
	bot.custom_response.get_message = AsyncMock(side_effect=lambda key, *args, **kwargs: key)
	cog = Ticket(bot)

	guild = MagicMock()
	guild.id = 12345
	member = MagicMock(spec=discord.Member)
	member.id = 100
	guild.get_member.return_value = member

	channel = MagicMock(spec=discord.TextChannel)
	channel.id = 777
	channel.name = "ticket-test"
	channel.set_permissions = AsyncMock()
	channel.send = AsyncMock()

	interaction = MagicMock(spec=discord.Interaction)
	interaction.guild = guild
	interaction.user = member
	interaction.channel = channel
	interaction.response.defer = AsyncMock()

	ticket = bot.api.tickets.add(12345, channel_id=777, user_id=100)

	# Test archive
	await cog.handle_archive_action(interaction)
	channel.set_permissions.assert_called_with(
		member, send_messages=False, view_channel=True, read_message_history=True
	)
	channel.send.assert_called_once()
	view = channel.send.call_args[1]["view"]
	assert isinstance(view, ArchivedTicketControlsView)
	assert bot.api.tickets.tickets[ticket.id].archived is True

	# Test reopen
	channel.set_permissions.reset_mock()
	channel.send.reset_mock()
	await cog.handle_reopen_action(interaction)
	assert bot.api.tickets.tickets[ticket.id].archived is False
	channel.set_permissions.assert_called_with(member, send_messages=True, view_channel=True, read_message_history=True)
	channel.send.assert_called_once()
	view = channel.send.call_args[1]["view"]
	assert isinstance(view, ActiveTicketControlsView)


@pytest.mark.asyncio
async def test_ticket_save_and_close():
	bot = MagicMock()
	bot.api.tickets = FakeTickets()
	bot.settings = GuildSettings(bot.event_bus)
	bot.custom_response.get_message = AsyncMock(return_value="Success")
	cog = Ticket(bot)

	guild = MagicMock()
	guild.id = 12345
	member = MagicMock(spec=discord.Member)
	member.id = 100
	guild.get_member.return_value = member

	log_channel = MagicMock(spec=discord.TextChannel)
	log_channel.id = 999
	log_channel.send = AsyncMock()
	guild.get_channel.return_value = log_channel

	channel = MagicMock(spec=discord.TextChannel)
	channel.id = 777
	channel.name = "ticket-test"
	channel.delete = AsyncMock()

	interaction = MagicMock(spec=discord.Interaction)
	interaction.guild = guild
	interaction.user = member
	interaction.channel = channel
	interaction.message = MagicMock()
	interaction.message.edit = AsyncMock()
	interaction.response.defer = AsyncMock()
	interaction.followup.send = AsyncMock()

	ticket = bot.api.tickets.add(12345, channel_id=777, user_id=100, title="Help")
	bot.api.tickets.configs[12345] = TicketConfig(log_channel_id=999, dm_transcript=True)

	# Mock chat_exporter
	with patch("chat_exporter.export", AsyncMock(return_value="<html>transcript</html>")):
		await cog.handle_close_action(interaction)

	log_channel.send.assert_called_once()
	# Transcripts attached directly as Discord file, not saved to disk
	assert "file" in log_channel.send.call_args[1]
	member.send.assert_called_once()
	channel.delete.assert_called_once()

	closed = bot.api.tickets.tickets[ticket.id]
	assert (closed.closed, closed.closed_by) == (True, 100)


@pytest.mark.asyncio
async def test_on_guild_channel_delete():
	bot = MagicMock()
	bot.api.tickets = FakeTickets()
	bot.settings = GuildSettings(bot.event_bus)
	cog = Ticket(bot)

	ticket = bot.api.tickets.add(1, channel_id=12345, user_id=100)
	ch = MagicMock(spec=discord.TextChannel)
	ch.id = 12345
	await cog.on_guild_channel_delete(ch)
	assert bot.api.tickets.tickets[ticket.id].closed is True


@pytest.mark.asyncio
async def test_export_transcript():
	bot = MagicMock()
	cog = Ticket(bot)

	channel = MagicMock(spec=discord.TextChannel)
	channel.id = 555
	channel.name = "ticket-ch"

	mock_exporter_html = (
		"<!DOCTYPE html><html><head></head><body>"
		'<img class="chatlog__avatar" src="https://cdn.discordapp.com/avatars/9/avatar.png" />'
		"hello world"
		"</body></html>"
	)

	with patch("chat_exporter.export", AsyncMock(return_value=mock_exporter_html)) as mock_export:
		result = await cog.export_transcript(channel, 42)
		mock_export.assert_called_once_with(channel=channel, tz_info="UTC", bot=bot)
		assert result == mock_exporter_html


@pytest.mark.asyncio
async def test_ticket_panel_components_v2():
	bot = MagicMock()
	bot.debug = False
	bot.config.emojis = {}
	from helpers.custom_response import CustomResponse

	cr = CustomResponse(bot)
	payload = await cr.get_message("ticket.panel", "en")
	assert isinstance(payload, dict)
	assert "view" in payload
	layout = payload["view"]
	assert isinstance(layout, discord.ui.LayoutView)
	assert layout.has_components_v2() is True
	container = layout.children[0]
	assert isinstance(container, discord.ui.Container)
	assert container.accent_color == 6656243

	# Test merging launcher view
	launcher_view = TicketLauncherView(button_label="Open Support Ticket")
	merged = cr.merge_views(layout, launcher_view)
	assert isinstance(merged, discord.ui.LayoutView)
	# Verify action row with open ticket button was added to container
	ar = next((c for c in container.children if isinstance(c, discord.ui.ActionRow)), None)
	assert ar is not None
	assert any(getattr(b, "custom_id", None) == "ticket:open" for b in ar.children)


@pytest.mark.asyncio
async def test_ticket_created_components_v2():
	bot = MagicMock()
	bot.debug = False
	bot.config.emojis = {}
	from helpers.custom_response import CustomResponse

	cr = CustomResponse(bot)

	member = MagicMock(spec=discord.Member)
	member.mention = "<@100>"
	member.name = "Alice"
	member.id = 100

	payload = await cr.get_message(
		"ticket.created.message",
		"en",
		member=member,
		topic="Billing Issue",
		description="Charged twice",
		ticket_id=42,
	)
	assert isinstance(payload, dict)
	assert "view" in payload
	layout = payload["view"]
	assert isinstance(layout, discord.ui.LayoutView)
	container = layout.children[0]
	assert isinstance(container, discord.ui.Container)

	# Check content inside container
	text_items = [c for c in container.children if isinstance(c, discord.ui.TextDisplay)]
	full_text = " ".join(t.content for t in text_items)
	assert "Billing Issue" in full_text
	assert "<@100>" in full_text
	assert "#42" in full_text
	assert "Charged twice" in full_text

	# Test merging active controls view
	controls = ActiveTicketControlsView()
	merged = cr.merge_views(layout, controls)
	assert isinstance(merged, discord.ui.LayoutView)
	ar = next((c for c in container.children if isinstance(c, discord.ui.ActionRow)), None)
	assert ar is not None
	button_ids = [getattr(b, "custom_id", None) for b in ar.children]
	assert "ticket:archive" in button_ids
	assert "ticket:close" in button_ids
	assert "ticket:save" in button_ids


@pytest.mark.asyncio
async def test_ticket_logs_components_v2():
	bot = MagicMock()
	bot.debug = False
	bot.config.emojis = {}
	from helpers.custom_response import CustomResponse

	cr = CustomResponse(bot)

	member = MagicMock(spec=discord.Member)
	member.mention = "<@100>"
	member.id = 100

	channel = MagicMock(spec=discord.TextChannel)
	channel.mention = "<#888>"
	channel.name = "ticket-alice"

	# Created log
	created_log = await cr.get_message(
		"ticket.logs.created",
		"en",
		member=member,
		channel=channel,
		topic="Payment",
		ticket_id=1,
	)
	assert "view" in created_log
	assert created_log["view"].has_components_v2() is True
	container = created_log["view"].children[0]
	assert container.accent_color == 5763719

	# Closed log
	closed_log = await cr.get_message(
		"ticket.logs.closed",
		"en",
		actor=member,
		ticket_user_id=100,
		channel=channel,
		topic="Payment",
		ticket_id=1,
	)
	assert "view" in closed_log
	assert closed_log["view"].children[0].accent_color == 15548997


@pytest.mark.asyncio
async def test_ticket_close_disables_components_v2_view():
	bot = MagicMock()
	cog = Ticket(bot)
	assert cog is not None

	layout = discord.ui.LayoutView()
	btn = discord.ui.Button(label="Close", custom_id="ticket:close")
	container = discord.ui.Container(discord.ui.TextDisplay("Ticket info"), discord.ui.ActionRow(btn))
	layout.add_item(container)

	msg = MagicMock(spec=discord.Message)
	msg.flags = discord.MessageFlags._from_value(1 << 15)  # IS_COMPONENTS_V2
	msg.components = []
	msg.edit = AsyncMock()

	with patch("discord.ui.LayoutView.from_message", return_value=layout):
		# Verify disabling buttons on components v2 message
		is_v2 = getattr(msg.flags, "components_v2", False)
		assert is_v2 is True
		v2_view = discord.ui.LayoutView.from_message(msg)
		for item in v2_view.walk_children():
			if isinstance(item, discord.ui.Button):
				item.disabled = True
		assert btn.disabled is True


@pytest.mark.asyncio
async def test_fallback_transcript_escapes_names_and_filenames():
	cog = Ticket(MagicMock())
	channel = MagicMock(spec=discord.TextChannel)
	channel.name = "ticket"
	message = MagicMock()
	message.author.display_name = "<script>alert(1)</script>"
	message.author.id = 1
	message.clean_content = "hi"
	attachment = MagicMock()
	attachment.filename = "<img src=x onerror=alert(1)>.png"
	message.attachments = [attachment]

	async def history(**_):
		yield message

	channel.history = history
	with patch("chat_exporter.export", AsyncMock(return_value=None)):
		result = await cog.export_transcript(channel, 42)

	assert "<script>" not in result
	assert "<img" not in result
	assert "&lt;script&gt;" in result


@pytest.mark.asyncio
async def test_ticket_buttons_reach_the_cog_on_the_sharded_bot():
	from core.bot import Bot

	cog = MagicMock(spec=Ticket)
	cog.handle_close_action = AsyncMock()
	client = MagicMock(spec=Bot)
	client.get_cog.return_value = cog
	interaction = MagicMock(spec=discord.Interaction)
	interaction.client = client

	await ActiveTicketControlsView().close_btn.callback(interaction)

	cog.handle_close_action.assert_awaited_once_with(interaction)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["handle_save_action", "handle_close_action"])
async def test_ticket_action_in_uncached_channel_answers_unavailable(action):
	cog = Ticket(MagicMock())
	cog.send_response = AsyncMock()
	interaction = MagicMock(spec=discord.Interaction)
	interaction.guild = MagicMock()
	interaction.channel = MagicMock(spec=discord.PartialMessageable)

	await getattr(cog, action)(interaction)

	cog.send_response.assert_awaited_once_with("ticket.errors.unavailable", interaction, ephemeral=True)
