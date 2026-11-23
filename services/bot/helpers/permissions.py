"""Permission checks against a channel other than the one a command ran in."""

from __future__ import annotations

import discord
from discord.ext import commands

__all__ = ("require_channel_permissions",)


def require_channel_permissions(
	member: discord.Member | discord.User, channel: discord.abc.GuildChannel | discord.Thread, *permissions: str
) -> None:
	"""Check that a member holds permissions in a channel, for commands that act on a channel they name.

	Command permission checks look at the channel the command ran in, so without this, Manage Messages in one channel
	would be enough to post in or edit another.

	Args:
		member: The command's author.
		channel: The channel the command acts on.
		*permissions: Permission names, e.g. ``"manage_messages"``.

	Raises:
		commands.MissingPermissions: The member lacks some of them there, or isn't a member of its guild.
	"""
	if not isinstance(member, discord.Member) or member.guild != channel.guild:
		raise commands.MissingPermissions(list(permissions))
	granted = channel.permissions_for(member)
	if missing := [permission for permission in permissions if not getattr(granted, permission)]:
		raise commands.MissingPermissions(missing)
