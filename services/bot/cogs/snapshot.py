import asyncio
from typing import Any
from uuid import UUID

import aiohttp
import discord
from core import Bot, Context, group
from discord.ext import commands
from discord.utils import MISSING

from api import SnapshotCreate


def _json_keys(value: Any) -> Any:
	"""Turn a payload's integer keys (role and channel IDs) into strings, as JSON stores them.

	Args:
		value: The payload, or a part of it.

	Returns:
		The same data with string keys.
	"""
	if isinstance(value, dict):
		return {str(key): _json_keys(item) for key, item in value.items()}
	if isinstance(value, list):
		return [_json_keys(item) for item in value]
	return value


class Snapshot(commands.Cog, name="Snapshots"):
	def __init__(self, client: Bot):
		self.client = client
		self.custom_response = client.custom_response

	@staticmethod
	async def save(ctx: Context) -> dict:
		"""Creates a snapshot of the server.

		Args:
			ctx (Context): The context to get the guild data from.

		Returns:
			dict: The payload of the snapshot.

		"""
		assert ctx.guild is not None
		payload = {"roles": {}, "channels": {}}

		for x in ctx.guild.roles:
			icon_data = None
			if x.display_icon:
				if isinstance(x.display_icon, discord.Asset):
					icon_data = {"type": "asset", "url": x.display_icon.url}
				elif isinstance(x.display_icon, str):
					icon_data = {"type": "unicode", "value": x.display_icon}

			payload["roles"][x.id] = {
				"perms": x.permissions.value,
				"color": x.color.value,
				"hoist": x.hoist,
				"managable": x.managed,
				"position": x.position,
				"name": x.name,
				"display_icon": icon_data,
			}

		for x in ctx.guild.channels:
			payload["channels"][x.id] = {
				"position": x.position,
				"type": str(x.type),
				"category": x.category.name if x.category else None,
				"name": x.name,
				"bitrate": getattr(x, "bitrate", None),
				"slowmode": getattr(x, "slowmode_delay", None),
				"nsfw": x.is_nsfw() if hasattr(x, "is_nsfw") else None,
				"user_limit": getattr(x, "user_limit", None),
				"topic": getattr(x, "topic", None),
				"permission_sync": getattr(x, "permissions_synced", None),
				"default_auto_archive_duration": getattr(x, "default_auto_archive_duration", 0),
				"rtc_region": getattr(x, "rtc_region", None),
			}
			payload["channels"][x.id]["overwrites"] = {}
			for y in x.overwrites:
				payload["channels"][x.id]["overwrites"][y.id] = {
					"allow": x.overwrites[y].pair()[0].value,
					"deny": x.overwrites[y].pair()[1].value,
					"role": getattr(y, "name", str(y.id)),
				}

		return payload

	async def create_snapshot(self, ctx: Context) -> UUID:
		"""Save a snapshot of the guild through the API.

		Args:
			ctx: The context to get the guild data from.

		Returns:
			The code to restore it with.
		"""
		assert ctx.guild is not None
		payload = await self.save(ctx)
		name = await self.custom_response("snapshot.strings.server_snapshot", ctx)
		snapshot = await self.client.api.snapshots.create(
			ctx.guild.id,
			SnapshotCreate(name=str(name), author_id=ctx.author.id, payload=_json_keys(payload)),
		)
		return UUID(snapshot.code)

	async def get_snapshot(self, code: str | UUID) -> dict | None:
		"""Get a snapshot's payload.

		Args:
			code: The snapshot's code.

		Returns:
			The payload, or ``None`` if there is no snapshot with that code.
		"""
		snapshot = await self.client.api.snapshots.get(str(code))
		return snapshot.payload if snapshot else None

	async def delete_all_channels(self, ctx: Context):
		assert ctx.guild is not None
		"""Deletes all channels in the server.

		Args:
			ctx (Context): The context to get the guild data from.

		"""
		for x in ctx.guild.channels:
			try:
				await x.delete(reason=await self.custom_response("snapshot.strings.save_load_reason", ctx))
			except (discord.Forbidden, discord.NotFound, discord.HTTPException):
				continue
			await asyncio.sleep(0.5)

	async def delete_all_roles(self, ctx: Context):
		assert ctx.guild is not None
		"""Deletes every role in the server that the author outranks (every role, for the owner).

		Args:
			ctx (Context): The context to get the guild data from.

		"""
		author = ctx.author
		for x in ctx.guild.roles:
			# Only the owner may delete roles that aren't below their own top role.
			if author.id != ctx.guild.owner_id and (not isinstance(author, discord.Member) or x >= author.top_role):
				continue
			try:
				await x.delete(reason=await self.custom_response("snapshot.strings.save_load_reason", ctx))
			except (discord.Forbidden, discord.NotFound, discord.HTTPException):
				continue
			await asyncio.sleep(0.5)

	async def load_snapshot(self, ctx: Context, payload: dict):
		assert ctx.guild is not None
		for x in sorted(payload["roles"], key=lambda r: payload["roles"][r]["position"], reverse=True):
			perms = discord.Permissions(permissions=int(payload["roles"][x]["perms"]))
			color = (
				discord.Colour(int(payload["roles"][x]["color"]))
				if payload["roles"][x]["color"]
				else discord.Colour.default()
			)
			if payload["roles"][x]["name"] != "@everyone":
				dicon = None
				icon_val = payload["roles"][x].get("display_icon")
				if isinstance(icon_val, dict):
					if icon_val.get("type") == "unicode":
						dicon = icon_val.get("value")
					elif (
						icon_val.get("type") == "asset"
						and icon_val.get("url")
						and "ROLE_ICONS" in ctx.guild.features
						and self.client.session
						and not self.client.session.closed
					):
						try:
							async with self.client.session.get(icon_val["url"]) as resp:
								if resp.status == 200:
									dicon = await resp.read()
						except (aiohttp.ClientError, TimeoutError):
							dicon = None
				elif isinstance(icon_val, str):
					dicon = icon_val
				role = await ctx.guild.create_role(
					name=payload["roles"][x]["name"],
					permissions=perms,
					colour=color,
					hoist=bool(payload["roles"][x]["hoist"]),
					reason=await self.custom_response("snapshot.strings.save_load_reason", ctx),
					display_icon=dicon
					if ("ROLE_ICONS" in ctx.guild.features or isinstance(dicon, str)) and dicon
					else MISSING,
				)
				await asyncio.sleep(0.5)
		for y in sorted(payload["channels"], key=lambda x: payload["channels"][x]["type"]):
			x = payload["channels"][y]
			if x["type"] == "text" or x["type"] == "news":
				try:
					cat = discord.utils.get(ctx.guild.categories, name=x["category"])
					overwrites: dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite] = {}
					for z in x["overwrites"]:
						role = discord.utils.get(ctx.guild.roles, name=x["overwrites"][z]["role"])
						if role:
							overwrites[role] = discord.PermissionOverwrite.from_pair(
								discord.Permissions(x["overwrites"][z]["allow"]),
								discord.Permissions(x["overwrites"][z]["deny"]),
							)
					await ctx.guild.create_text_channel(
						name=x["name"],
						category=cat if cat else None,
						position=int(x["position"]),
						reason=await self.custom_response("snapshot.strings.save_load_reason", ctx),
						slowmode_delay=int(x["slowmode"]) if x.get("slowmode") else MISSING,
						topic=x["topic"] if x.get("topic") else MISSING,
						nsfw=bool(x.get("nsfw", False)),
						overwrites=overwrites,
						news=x["type"] == "news",
						default_auto_archive_duration=x.get("default_auto_archive_duration", MISSING),
					)
					await asyncio.sleep(0.5)
				except (discord.Forbidden, discord.HTTPException):
					continue
			elif x["type"] == "voice":
				try:
					cat = discord.utils.get(ctx.guild.categories, name=x["category"])
					overwrites: dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite] = {}
					for z in x["overwrites"]:
						role = discord.utils.get(ctx.guild.roles, name=x["overwrites"][z]["role"])
						if role:
							overwrites[role] = discord.PermissionOverwrite.from_pair(
								discord.Permissions(x["overwrites"][z]["allow"]),
								discord.Permissions(x["overwrites"][z]["deny"]),
							)
					await ctx.guild.create_voice_channel(
						name=x["name"],
						category=cat if cat else None,
						position=int(x["position"]),
						reason=await self.custom_response("snapshot.strings.save_load_reason", ctx),
						bitrate=int(x["bitrate"]) if x.get("bitrate") else MISSING,
						user_limit=int(x["user_limit"]) if x.get("user_limit") else MISSING,
						overwrites=overwrites,
						rtc_region=x.get("rtc_region"),
					)
					await asyncio.sleep(0.5)
				except (discord.Forbidden, discord.HTTPException):
					continue
			elif x["type"] == "stage_voice":
				try:
					cat = discord.utils.get(ctx.guild.categories, name=x["category"])
					overwrites: dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite] = {}
					for z in x["overwrites"]:
						role = discord.utils.get(ctx.guild.roles, name=x["overwrites"][z]["role"])
						if role:
							overwrites[role] = discord.PermissionOverwrite.from_pair(
								discord.Permissions(x["overwrites"][z]["allow"]),
								discord.Permissions(x["overwrites"][z]["deny"]),
							)
					await ctx.guild.create_stage_channel(
						name=x["name"],
						category=cat if cat else None,
						position=int(x["position"]),
						reason=await self.custom_response("snapshot.strings.save_load_reason", ctx),
						overwrites=overwrites,
					)
					await asyncio.sleep(0.5)
				except (discord.Forbidden, discord.HTTPException):
					continue
			elif x["type"] == "category":
				try:
					overwrites: dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite] = {}
					for z in x["overwrites"]:
						role = discord.utils.get(ctx.guild.roles, name=x["overwrites"][z]["role"])
						if role:
							overwrites[role] = discord.PermissionOverwrite.from_pair(
								discord.Permissions(x["overwrites"][z]["allow"]),
								discord.Permissions(x["overwrites"][z]["deny"]),
							)
					await ctx.guild.create_category(
						name=x["name"],
						position=int(x["position"]),
						reason=await self.custom_response("snapshot.strings.save_load_reason", ctx),
						overwrites=overwrites,
					)
					await asyncio.sleep(0.5)
				except (discord.Forbidden, discord.HTTPException):
					continue
			elif x["type"] == "forum":
				try:
					overwrites: dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite] = {}
					for z in x["overwrites"]:
						role = discord.utils.get(ctx.guild.roles, name=x["overwrites"][z]["role"])
						if role:
							overwrites[role] = discord.PermissionOverwrite.from_pair(
								discord.Permissions(x["overwrites"][z]["allow"]),
								discord.Permissions(x["overwrites"][z]["deny"]),
							)
					cat = discord.utils.get(ctx.guild.categories, name=x["category"])
					await ctx.guild.create_forum(
						name=x["name"],
						category=cat if cat else None,
						position=int(x["position"]),
						reason=await self.custom_response("snapshot.strings.save_load_reason", ctx),
						nsfw=bool(x.get("nsfw", False)),
						topic=x["topic"] if x.get("topic") else MISSING,
						default_thread_slowmode_delay=int(x["slowmode"]) if x.get("slowmode") else MISSING,
						overwrites=overwrites,
						default_auto_archive_duration=x.get("default_auto_archive_duration", MISSING),
					)
					await asyncio.sleep(0.5)
				except (discord.Forbidden, discord.HTTPException):
					continue

	@group(permissions=["administrator"], user=False, aliases=["ss", "save", "backup"])
	async def snapshot(self, ctx: Context):
		assert ctx.guild is not None
		await ctx.defer()  # slow: reads every role and channel
		code = await self.create_snapshot(ctx)

		await ctx.send("snapshot.create", code=code)

	@snapshot.command(
		l10n_key="ss_load", permissions=["administrator"], full_aliases=["restore", "ssload", "ssrestore"]
	)
	async def load(self, ctx: Context, code: str):
		assert ctx.guild is not None
		await ctx.defer()  # slow: recreates roles and channels
		payload = await self.get_snapshot(code)
		if not payload:
			await ctx.send("snapshot.not_found")
			return

		if not isinstance(payload, dict) or "roles" not in payload or "channels" not in payload:
			await ctx.send("snapshot.not_found")
			return

		old = await self.create_snapshot(ctx)
		current_channel_id = ctx.channel.id if ctx.channel else None

		try:
			# Delete other channels first
			for x in list(ctx.guild.channels):
				if x.id != current_channel_id:
					try:
						await x.delete(reason=await self.custom_response("snapshot.strings.save_load_reason", ctx))
					except (discord.Forbidden, discord.NotFound, discord.HTTPException):
						continue
					await asyncio.sleep(0.5)

			await self.delete_all_roles(ctx)
			await self.load_snapshot(ctx, payload)

			if current_channel_id:
				old_ch = ctx.guild.get_channel(current_channel_id)
				if old_ch:
					try:
						await old_ch.delete(reason=await self.custom_response("snapshot.strings.save_load_reason", ctx))
					except (discord.Forbidden, discord.NotFound, discord.HTTPException):
						pass

		except Exception as e:
			self.client.logger.exception("Snapshot loading encountered an error")
			if ctx.guild.owner:
				try:
					payload = await self.custom_response.get_message(
						"snapshot.restore_failed", ctx.guild, code=code, error=str(e), backup=old
					)
					if isinstance(payload, dict):
						await ctx.guild.owner.send(**payload)
				except (discord.Forbidden, discord.HTTPException):
					pass
			return

		if ctx.guild.owner_id != ctx.author.id and ctx.guild.owner:  # prevent griefs by sending the code to the owner
			alert = await self.custom_response("snapshot.owner_alert", ctx, code=old)
			alert.pop("reply", None)
			alert.pop("ephemeral", None)
			alert.pop("delete_after", None)
			try:
				await ctx.guild.owner.send(**alert)
			except (discord.Forbidden, discord.HTTPException):
				pass

		try:
			await ctx.send("snapshot.load")
		except (discord.NotFound, discord.HTTPException):
			pass


async def setup(client: Bot):
	await client.add_cog(Snapshot(client))
