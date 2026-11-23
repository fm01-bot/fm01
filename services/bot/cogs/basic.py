from time import perf_counter

import aiohttp
from core import Bot, Context
from core.clustering import fetch_proxy_shard_latency
from core.hybrid import command
from discord.ext import commands


class Basic(commands.Cog, name="Basic"):
	def __init__(self, client: Bot):
		self.client = client

	async def gateway_latency(self, shard_id: int) -> tuple[float, float | None]:
		"""Measure the Discord gateway latency of one shard.

		Behind the gateway proxy, discord.py's latency only covers the hop to the proxy, because the proxy answers
		heartbeats itself. The proxy's own heartbeat round trip to Discord is read from its metrics instead.

		Args:
			shard_id: The shard to measure.

		Returns:
			tuple[float, float | None]: The latency to Discord in seconds, and the latency to the gateway proxy in
			seconds (``None`` when the bot connects to Discord directly or the proxy has no sample for the shard).
		"""
		shard = self.client.get_shard(shard_id)
		local_latency = shard.latency if shard is not None else self.client.latency
		gateway_url = self.client.cluster_config.gateway_url
		if not gateway_url or self.client.session is None:
			return local_latency, None

		try:
			proxy_latency = await fetch_proxy_shard_latency(self.client.session, gateway_url, shard_id)
		except (aiohttp.ClientError, TimeoutError, ValueError):
			self.client.logger.warning("Could not read shard latency from the gateway proxy", exc_info=True)
			return local_latency, None
		if proxy_latency is None:
			return local_latency, None
		return proxy_latency, local_latency

	@command()
	async def ping(self, ctx: Context):
		# API round trip (the API holds the database)
		database_start = perf_counter()
		await self.client.api.ping()
		database = perf_counter() - database_start

		# Discord routes DMs to shard 0.
		shard_id = ctx.guild.shard_id if ctx.guild else 0
		latency, proxy_latency = await self.gateway_latency(shard_id)
		shard_count = self.client.shard_count or 1
		cluster_config = self.client.cluster_config

		await ctx.send(
			"ping",
			latency=float(latency),
			proxy=proxy_latency,
			db=float(database),
			cluster=cluster_config.cluster_id if cluster_config.is_clustered else None,
			shard=shard_id if ctx.guild and shard_count > 1 else None,
			shard_count=shard_count,
		)


async def setup(client: Bot):
	await client.add_cog(Basic(client))
