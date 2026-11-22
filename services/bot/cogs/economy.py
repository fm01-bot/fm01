import logging
import random
from typing import Literal

import discord
from args import Role, User
from core import Bot, Context, command, group
from core.api import InsufficientFunds
from core.cooldowns import shared_cooldown
from discord import app_commands
from discord.ext import commands
from helpers import custom_response, random_helper

logger = logging.getLogger(__name__)


class ShopItem:
	def __init__(self, name: str, price: int, description: str, role: discord.Role | None):
		"""Create a new shop item.

		Args:
			name: The name of the item.
			price: The price of the item.
			description: The description of the item.
			role: The role that is given to the user when they buy the item.

		"""
		self._name = name
		self._price = price
		self._description = description
		self._raw_role: discord.Role | None = role
		self._role: Role | None = Role.from_role(role) if role else None

	@property
	def name(self) -> str:
		"""The name of the item."""
		return self._name

	@property
	def price(self) -> int:
		"""The price of the item."""
		return self._price

	@property
	def description(self) -> str:
		"""The description of the item."""
		return self._description

	@property
	def role(self) -> Role | None:
		"""The role that is given to the user when they buy the item."""
		return self._role

	@property
	def raw_role(self) -> discord.Role | None:
		"""The discord.Role object associated with the item."""
		return self._raw_role

	def __str__(self) -> str:
		return self.name

	def __int__(self) -> int:
		return self.price


@app_commands.guild_only()
@commands.guild_only()
class Economy(commands.GroupCog, name="Economy", group_name="economy"):
	def __init__(self, client: Bot):
		self.client = client
		self.ledger = client.api.economy
		self.custom_response = client.custom_response

	@command(user=False)
	async def leaderboard(self, ctx: commands.Context):
		assert ctx.guild is not None
		entries = await self.ledger.leaderboard(ctx.guild.id, limit=10)
		leaderboard = []
		for number, entry in enumerate(entries, start=1):
			cached_user = self.client.get_user(entry.user_id)
			leaderboard.append(
				{
					"user": User.from_user(cached_user) if cached_user else None,
					"number": number,
					"cash": entry.cash,
					"bank": entry.bank,
				}
			)
		(message,) = await self.custom_response.get_list("leaderboard", ctx, leaderboard)
		await ctx.send(**message)

	@command(user=False)
	@shared_cooldown(3600)
	async def work(self, ctx: Context):
		assert ctx.guild is not None
		amount: int = random.randint(300, 1500)
		await self.ledger.add_money(ctx.guild.id, ctx.author.id, amount)

		await ctx.send("work", amount=amount)

	@command(user=False)
	@shared_cooldown(3600)
	async def crime(self, ctx: Context):
		assert ctx.guild is not None
		amount = random.randint(500, 2000)
		await self.ledger.add_money(ctx.guild.id, ctx.author.id, amount)

		await ctx.send("crime", amount=amount)

	@command(user=False)
	@shared_cooldown(86400)
	async def daily(self, ctx: Context):
		assert ctx.guild is not None
		amount = 5000
		await self.ledger.add_money(ctx.guild.id, ctx.author.id, amount)

		await ctx.send("allowance", amount=amount)

	@command(user=False)
	@app_commands.choices(
		account=[
			app_commands.Choice(name="global-cash", value="cash"),
			app_commands.Choice(name="global-bank", value="bank"),
		]
	)
	@app_commands.checks.has_permissions(administrator=True)
	@commands.has_permissions(administrator=True)
	async def addmoney(
		self,
		ctx: Context,
		member: discord.Member,
		amount: commands.Range[int, 1],
		account: Literal["cash", "bank"] = "cash",
	):
		assert ctx.guild is not None
		await self.ledger.add_money(ctx.guild.id, member.id, amount, account)
		await ctx.send("addmoney.success", amount=amount, member=member)

	@command(user=False)
	@app_commands.choices(
		account=[
			app_commands.Choice(name="global-cash", value="cash"),
			app_commands.Choice(name="global-bank", value="bank"),
		]
	)
	@app_commands.checks.has_permissions(administrator=True)
	@commands.has_permissions(administrator=True)
	async def removemoney(
		self,
		ctx: Context,
		member: discord.Member,
		amount: discord.app_commands.Range[int, 1],
		account: Literal["cash", "bank"] = "cash",
	):
		assert ctx.guild is not None
		try:
			await self.ledger.remove_money(ctx.guild.id, member.id, amount, account)
		except InsufficientFunds:
			await ctx.send("removemoney.errors.balance")
			return
		await ctx.send("removemoney.success", amount=amount, member=member)

	@command(user=False)
	@shared_cooldown(3600)
	async def luck(self, ctx: Context):
		assert ctx.guild is not None
		minimum_balance = 1000
		if (await self.ledger.balance(ctx.guild.id, ctx.author.id)).cash < minimum_balance:
			await ctx.send("luck.errors.balance", amount=minimum_balance)
			return

		amount = random.randint(200, 1000)
		if random_helper.randbool():
			await self.ledger.add_money(ctx.guild.id, ctx.author.id, amount)
			await ctx.send("luck.win", amount=amount)
			return
		try:
			await self.ledger.remove_money(ctx.guild.id, ctx.author.id, amount)
		except InsufficientFunds:
			await ctx.send("luck.errors.balance", amount=minimum_balance)
			return
		await ctx.send("luck.lose", amount=amount)

	@command(user=False)
	async def pay(self, ctx: Context, member: discord.Member, amount: discord.app_commands.Range[int, 1]):
		assert ctx.guild is not None
		if member == ctx.author:
			await ctx.send("pay.errors.self")
			return
		try:
			await self.ledger.transfer(ctx.guild.id, ctx.author.id, member.id, amount)
		except InsufficientFunds:
			await ctx.send("pay.errors.balance")
			return

		await ctx.send("pay.success", amount=amount, member=member)

	@command(user=False, aliases=["bal"])
	async def balance(self, ctx: Context, member: discord.Member | None):
		assert ctx.guild is not None
		target_member = member or (ctx.author if isinstance(ctx.author, discord.Member) else None)
		if not target_member:
			raise commands.BadArgument
		bal = await self.ledger.balance(ctx.guild.id, target_member.id)

		await ctx.send(
			"balance", member=target_member, cash=bal.cash, bank=bal.bank, debt=-bal.bank if bal.in_debt else None
		)

	@command(user=False)
	@shared_cooldown(3600)
	async def slots(self, ctx: Context, bet: int):
		assert ctx.guild is not None
		if bet <= 0:
			await ctx.send("slots.errors.balance")
			return

		try:
			await self.ledger.remove_money(ctx.guild.id, ctx.author.id, bet)
		except InsufficientFunds:
			await ctx.send("slots.errors.balance")
			return

		slots_choices = ["🍇", "🍉", "🍊", "🍋"]
		results = [random.choice(slots_choices) for _ in range(3)]

		if results.count(results[0]) == len(results):
			payout = bet * 2
			await self.ledger.add_money(ctx.guild.id, ctx.author.id, payout)
			await ctx.send("slots.win", results=" ".join(results), amount=payout)
		else:
			bal = await self.ledger.balance(ctx.guild.id, ctx.author.id)
			await ctx.send("slots.lose", results=" ".join(results), amount=bet, debt=-bal.bank if bal.in_debt else None)

	@command(user=False)
	async def deposit(self, ctx: Context, amount: discord.app_commands.Range[int, 1] | None = None):
		assert ctx.guild is not None
		if amount is None:  # everything in the cash wallet
			amount = (await self.ledger.balance(ctx.guild.id, ctx.author.id))["cash"]
		if amount < 1:
			await ctx.send("deposit.errors.invalid_amount")
			return
		try:
			await self.ledger.move(ctx.guild.id, ctx.author.id, amount, "cash", "bank")
		except InsufficientFunds:
			await ctx.send("deposit.errors.balance")
			return

		await ctx.send("deposit.success", amount=amount)

	@command(user=False)
	async def withdraw(self, ctx: Context, amount: discord.app_commands.Range[int, 1] | None = None):
		assert ctx.guild is not None
		if amount is None:  # everything in the bank wallet
			amount = (await self.ledger.balance(ctx.guild.id, ctx.author.id))["bank"]
		if amount < 1:
			await ctx.send("withdraw.errors.invalid_amount")
			return
		try:
			await self.ledger.move(ctx.guild.id, ctx.author.id, amount, "bank", "cash")
		except InsufficientFunds:
			await ctx.send("withdraw.errors.balance")
			return

		await ctx.send("withdraw.success", amount=amount)


class Shop(commands.Cog, name="Shop"):
	def __init__(self, client):
		self.client: Bot = client
		self.ledger = client.api.economy
		self.custom_response = custom_response.CustomResponse(client, name="shop")

	@group(user=False)
	async def shop(self, ctx: Context):
		assert ctx.guild is not None
		row = await self.client.db.fetch("SELECT * FROM shop WHERE guild_id = $1", ctx.guild.id)
		if not row:
			await ctx.send("shop.list.empty")
			return

		items = [
			{"item": ShopItem(i["item_name"], i["item_price"], i["item_description"], role)}
			for i in row
			if (role := ctx.guild.get_role(i["role"]))
		]
		(message,) = await self.custom_response.get_list("shop.list.show", ctx, items)
		await ctx.send(**message)

	@shop.command()
	async def buy(self, ctx: Context, item_name: str):
		assert ctx.guild is not None
		assert isinstance(ctx.author, discord.Member)
		row = await self.client.db.fetchrow(
			"SELECT * FROM shop WHERE guild_id = $1 AND LOWER(item_name) = $2", ctx.guild.id, item_name.lower()
		)
		if not row:
			await ctx.send("shop.buy.errors.not_found")
			return

		role = ctx.guild.get_role(row["role"])
		item = ShopItem(row["item_name"], row["item_price"], row["item_description"], role)
		if not item.raw_role:
			await ctx.send("shop.buy.errors.role_not_found")
			return

		try:
			await self.ledger.remove_money(ctx.guild.id, ctx.author.id, item.price)
		except InsufficientFunds:
			await ctx.send("shop.buy.errors.balance")
			return

		try:
			await ctx.author.add_roles(item.raw_role)
		except discord.HTTPException:
			try:
				await self.ledger.add_money(ctx.guild.id, ctx.author.id, item.price)
			except Exception:
				logger.exception(f"Refund of {item.price} to {ctx.author.id} in {ctx.guild.id} failed")
			await ctx.send("shop.buy.errors.role_failed", item=item)
			return

		await ctx.send("shop.buy.success", item=item)

	@shop.command()
	@app_commands.checks.has_permissions(manage_guild=True, manage_roles=True)
	@commands.has_permissions(manage_guild=True, manage_roles=True)
	async def set_item(self, ctx: Context, item_name: str, price: int, description: str, role: discord.Role):
		assert ctx.guild is not None
		assert isinstance(ctx.author, discord.Member)
		row = await self.client.db.fetchrow(
			"SELECT * FROM shop WHERE guild_id = $1 AND LOWER(item_name) = $2", ctx.guild.id, item_name.lower()
		)
		if row:
			await ctx.send("shop.set.errors.already_item")
			return

		items = await self.client.db.fetch("SELECT * FROM shop WHERE guild_id = $1", ctx.guild.id)
		if len(items) + 1 >= 10:
			await ctx.send("shop.set.errors.limit")
			return

		if ctx.author.top_role.position <= role.position:
			await ctx.send("shop.set.errors.role_higher")
			return

		await self.client.db.execute(
			"INSERT INTO shop(item_name, item_description, item_price, role, guild_id, creator_id) VALUES($1, $2, $3, $4, $5, $6)",
			item_name,
			description,
			price,
			role.id,
			ctx.guild.id,
			ctx.author.id,
		)

		item = ShopItem(item_name, price, description, role)
		await ctx.send("shop.set.success", item=item)

	@shop.command()
	@app_commands.checks.has_permissions(manage_guild=True)
	@commands.has_permissions(manage_guild=True)
	async def remove_item(self, ctx: Context, item_name: str):
		assert ctx.guild is not None
		assert isinstance(ctx.author, discord.Member)
		row = await self.client.db.fetchrow(
			"SELECT * FROM shop WHERE guild_id = $1 AND LOWER(item_name) = $2", ctx.guild.id, item_name.lower()
		)
		if not row:
			await ctx.send("shop.remove.errors.not_found")
			return

		role = ctx.guild.get_role(row["role"])
		item = ShopItem(row["item_name"], row["item_price"], row["item_description"], role)
		if item.raw_role and ctx.author.top_role.position <= item.raw_role.position:
			await ctx.send("shop.remove.errors.role_higher")
			return

		await self.client.db.execute(
			"DELETE FROM shop WHERE guild_id = $1 AND LOWER(item_name) = $2", ctx.guild.id, item.name.lower()
		)
		await ctx.send("shop.remove.success", item=item)


async def setup(client: Bot):
	await client.add_cog(Economy(client))
	await client.add_cog(Shop(client))
