"""Wire models shared by the fm01 bot, API and dashboard.

TypeScript types are generated from the API's OpenAPI schema into ``shared/schemas/ts/``. Never edit those by hand.
"""

from api.bear_trap import (
	BEAR_TRAP_SETTING,
	BearTrap,
	BearTrapChannel,
	BearTrapKicks,
	BearTrapMessage,
	BearTrapState,
	GuildBearTrap,
)
from api.dashboard import DashboardUser, ManagedGuild, SessionExchange, SessionGrant
from api.economy import (
	AddMoneyRequest,
	Amount,
	Balance,
	LeaderboardEntry,
	MoveRequest,
	RemoveMoneyRequest,
	TransferRequest,
	Wallet,
)
from api.errors import ErrorBody, ErrorCode
from api.events import EVENTS_CHANNEL, INVALIDATE_SETTING, InvalidateSetting
from api.settings import (
	LOCALE_SETTING,
	PREFIX_SETTING,
	GuildLocale,
	GuildPrefix,
	LocaleCode,
	LocaleOverride,
	Prefix,
	PrefixText,
)
from api.snowflake import Snowflake
from api.status import (
	HEALTH_KEY,
	SHARDS_PER_CLUSTER_KEY,
	SHARDS_TOTAL_KEY,
	ClusterDay,
	ClusterHistory,
	ClusterState,
	ClusterStatus,
	ShardDay,
	ShardHealth,
	ShardHistory,
	ShardState,
	ShardStatus,
	Status,
	StatusHistory,
)

__all__ = (
	"BEAR_TRAP_SETTING",
	"EVENTS_CHANNEL",
	"HEALTH_KEY",
	"INVALIDATE_SETTING",
	"LOCALE_SETTING",
	"PREFIX_SETTING",
	"SHARDS_PER_CLUSTER_KEY",
	"SHARDS_TOTAL_KEY",
	"AddMoneyRequest",
	"Amount",
	"Balance",
	"BearTrap",
	"BearTrapChannel",
	"BearTrapKicks",
	"BearTrapMessage",
	"BearTrapState",
	"ClusterDay",
	"ClusterHistory",
	"ClusterState",
	"ClusterStatus",
	"DashboardUser",
	"ErrorBody",
	"ErrorCode",
	"GuildBearTrap",
	"GuildLocale",
	"GuildPrefix",
	"InvalidateSetting",
	"LeaderboardEntry",
	"LocaleCode",
	"LocaleOverride",
	"ManagedGuild",
	"MoveRequest",
	"Prefix",
	"PrefixText",
	"RemoveMoneyRequest",
	"SessionExchange",
	"SessionGrant",
	"ShardDay",
	"ShardHealth",
	"ShardHistory",
	"ShardState",
	"ShardStatus",
	"Snowflake",
	"Status",
	"StatusHistory",
	"TransferRequest",
	"Wallet",
)
