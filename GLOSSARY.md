# Glossary

The words this repository (bot, API, website and dashboard) uses for its own concepts, and the decisions that shape it. Use these terms in code, issues and PRs.

## Terms

**Case**: one moderation action against a user in a guild: a warn, mute, kick or ban. Stored as a row in `cases`, identified by `case_id` (the ID of the message that triggered it). Represented by `Case` and its subclasses `Warn`, `Mute`, `Kick` and `Ban` in `cogs/mod/cases.py`.

**Active case**: a case that is still in force (`cases.active = true`). Closing a case makes it inactive or deletes it, depending on retention. An active case past its `expires` is *expired* until the scheduler closes it.

**Opening a case**: recording a new case and performing its Discord effect (timeout, kick, ban, DM). If the effect fails, the case is removed again.

**Closing a case**: ending an active case, either by hand (`unmute`, `unban`, `case remove`) or when it expires. Undoes the Discord effect (lifts the timeout or ban) and DMs the user. Closing an already inactive case has no side effects.

**Retention**: a guild's choice of what closing a case does: `keep` (mark it inactive, the default) or `delete` (remove the row). Stored in `mod_config.case_retention`. `case delete` always deletes, regardless of retention.

**Softban**: a case that bans a user with the last hour of their messages deleted and unbans them at once: a kick that also cleans up. `Softban` in `cogs/mod/cases.py`. A failed unban is logged, not rolled back, because the ban already happened.

**Case store**: `CaseStore` in `cogs/mod/cases.py`, the only code that reads or writes `cases`. Commands and AutoMod open, close, edit and look up cases through it.

**Guild setting**: a per-guild configuration value (prefix, locale override, case retention, ...) behind a `GuildSetting` in `core/settings.py`. Read with `get` (or `cache` on hot synchronous paths), write with `set`; code that writes with targeted SQL calls `changed` afterwards instead. Writing persists it and announces an `INVALIDATE_SETTING` event so other bot instances reload it (for settings that live behind the API, the API announces); callers never touch caches or the event bus. Settings with a meaningful default row (prefix, retention) create it from the column defaults on first load; feature settings (log, AutoMod, join/leave, leveling) treat a missing row as "not configured".

**Preloaded setting**: a guild setting whose values for every guild are loaded at startup (prefix, locale override), so synchronous code can read `cache`. Other settings load on first use.

**Locale override**: a guild's chosen bot language (`guild_locale_overrides`), set with `?!config locale`. It takes precedence over the user's Discord client locale and the guild's preferred locale; see `core/locale.py`.

**Log configuration**: a guild's event logging setup (`log` table, `LogConfig`, `LogSettings` in `cogs/log.py`): on/off, default channel, per-event channels, webhook and enabled modules. `modules = {'*'}` (the column default) means every module, including ones added later.

**Message buffering**: the bot keeps recent message content for guilds whose log configuration has message deletion or edit logging on (`Bot.message_logging_guilds`), so deleted and edited messages can be logged. Maintained automatically from the log configuration.

**Ledger**: the only code that changes `economy` balances, in the API (`services/api/app/economy/store.py`); the bot reaches it as `bot.api.economy`. Each operation (`add_money`, `remove_money`, `move`, `transfer`) is one transaction over row-locked accounts. Cash never goes negative; the bank goes negative only as **debt** (admin removals), and money added while in debt pays it off first. A **Balance** is a member's `cash` and `bank` in one guild.

**Bear trap**: a honeypot channel (`?!config beartrap`, Dashboard API `settings/bear-trap`). The bot posts the localized **trap message** there, with a disabled button counting the **kicks**. Anyone who posts in the channel, except bots, the owner, managers and members the bot can't ban, gets a DM to secure their account (with an invite back) and is soft-banned. Because it removes members, setting it needs Administrator (`?!config`) or, on the dashboard, Ban Members on top of being a guild manager. Stored behind the API as the `bear_trap` guild setting (`bear_trap` table). The kick count survives moving or turning off the trap. Whoever changes the channel, the bot instance that owns the guild's shard **reconciles** the trap message: posts, moves or deletes it. If it can't post, it turns the trap off.

**Starboard**: a channel the bot reposts messages to once enough members react with the board's emoji (`?!config starboard`, Dashboard API `settings/starboards`). A guild has up to 5 **boards**, each with a unique name, a channel, an emoji (unicode, or a custom emoji's ID), a threshold, an optional maximum message age, and a channel filter (a blocklist by default, or an allowlist; a thread follows its parent). Board channels and NSFW channels are never watched. Stored behind the API as the `starboard` guild setting (`starboards` table). The bot turns a board off when it can't post in its channel or its emoji is deleted.

**Star**: a member's reaction with a board emoji. Stars belong to a message and an emoji (`starboard_stars`), not to a board, so boards sharing an emoji are **tiers** (⭐ 3 and ⭐ 10) with one count, and stars on the message's posts count too. The count is unique members, bots and the author excluded. The first time the API sees a message, the bot **seeds** it by reading its reactors from Discord once; after that it reports each added and removed star.

**Starboard entry**: a message on one board (`starboard_entries`): its **post** there, if any, and whether it is **blocked**. Each tier posts on its own once the count reaches its threshold and takes the post down below it. The bot records a post's removal with the API before deleting it, so a post that disappears while the API still knows it was deleted by someone else, and that blocks the message on that board until a guild manager unblocks it from the dashboard. Edits to a board only change what happens at the next star; edits to the original are not synced.

**List message**: a localized embed rendered with `CustomResponse.get_list`. Its first field is the **row template** (repeated per row), the remaining fields are the **empty state**, and `{page}`/`{pages}` work in the title, description and footer. Cogs pass rows, never edit rendered embeds. Optional parts of a message use a placeholder that is `None` when absent: the formatter drops that line, and a field left empty is dropped.

**Command key (`l10n_key`)**: the base under which a command's slash localization lives in `slash_localization/*.l10n.json`: `<key>-name`, `<key>-desc`, `<key>-usage`, `<key>-fallback` (a group's own callback, run as a subcommand) and `<key>-args-<param>-name|desc|<choice>`. It defaults to the command's name, and every subcommand has its own key, so subcommands with the same name are translated separately. The exception is `GroupCog` group names (`admin`, `economy`, `mod`, `voice`): discord.py builds those groups, so they use a top-level string. Built by `command_key` and read with `lookup` in `core/slash_localization.py`. `tests/test_slash_keys.py` fails when a key is missing. Groups need no description, because Discord never shows it.

**Internal API**: the part of the API only the bot calls. Its operations are domain operations (a Ledger transfer, opening a case, loading a guild setting), never raw table access. Not reachable from outside the deployment.

**Dashboard API**: the part of the API a signed-in dashboard user calls, through the dashboard's server, never from the browser. It covers everything a guild manager can configure (what `?!config` configures today).

**API client**: the bot's typed wrapper around the Internal API (e.g. `await api.economy.balance(guild_id, user_id)`). Cogs call it; they never build requests themselves.

**Dashboard session**: proof that a dashboard user signed in with Discord. Issued by the API after the Discord OAuth2 exchange, tied to one Discord user, revocable. The API never trusts a Discord user ID it is merely told.

**Guild manager**: a user who may change a guild's configuration from the dashboard: its owner, or a member with Administrator or Manage Server, in a guild the bot is in.

**Public API**: the part of the API anyone may call, without credentials, under `/public` (served by Caddy at `api.fm01.bot`, which forwards nothing else). Read-only, cached, and rate limited per IP (`app/ratelimit.py`). Today it serves the status page: `GET /public/status` and `GET /public/status/history`.

**Shard health**: the raw facts a bot process reports about each of its shards every 10 seconds (`ShardHealth`: heartbeat latency, ready, socket closed, gateway rate limited, guild count), in the Redis hash `fm01:shards:health`. Written by `HealthReporter` in `core/clustering/health.py`, in standalone mode too. The bot never decides a status; the API does.

**Shard status**: what the status page says about a shard, decided by the API from its shard health (`app/status/rules.py`). `unresponsive`: no report for over 30 seconds, a closed socket, or heartbeat latency of 10 seconds or more. `lagging`: latency of 1 second or more, not ready, or gateway rate limited. `operational` otherwise.

**Cluster status**: what the status page says about a status block, and (over every shard) about the whole bot. `unresponsive` if every shard is unresponsive or more than half are lagging or unresponsive; else `partially_unresponsive` if any shard is unresponsive; else `partially_operational` if any is lagging; else `operational`.

**Status block**: a fixed group of `SHARDS_PER_CLUSTER` consecutive shards: block `n` holds shards `n * size` up to `(n + 1) * size - 1`. The status page's "clusters" are status blocks, not processes, so history stays comparable across restarts. A clustered bot process leases one whole free block (`RedisShardCoordinator`); `SHARD_IDS` overrides that. A standalone bot is one block of every shard.

**Snowflake**: a Discord ID. Always a string on the wire (JavaScript numbers lose precision on them), an integer inside Python.

## Decisions

**Config commands are temporary.** The `?!config` command tree (`cogs/config_subcommands/`) exists only until the dashboard covers everything it configures; then it is deleted. Fix bugs there and move its writes onto the API client when their tables move, but don't put architecture work into it (localizing its strings, restructuring, new tests).

**Cache invalidation uses Redis pub/sub.** The API, as the only writer, announces every guild setting change (whether the bot or a dashboard user asked for it) as an `INVALIDATE_SETTING` event on the existing Redis event bus, with one payload shape defined in `shared/`. Bot instances reload the value; the instance that asked for the change updates its own cache at once. Every bot, standalone included, listens on Redis for this. Until all settings move to the API, settings the bot still writes itself are announced by the bot. Postgres `LISTEN/NOTIFY` triggers were considered and rejected: with a single writer, announcing from the writer is enough.

**Deploys restart the bot behind a gateway proxy.** Production runs [gateway-proxy](https://github.com/Gelbpunkt/gateway-proxy) (upstream image, pinned by digest, no fork for now), which keeps the shard connections open and replays a synthetic `READY` and `GUILD_CREATE`s from its cache when the bot connects, so a deploy sends no IDENTIFY. Resuming the old sessions from a fresh process was rejected: Discord sends no `READY` or `GUILD_CREATE` after a RESUME, so the new process starts with an empty cache. nirn-proxy was rejected because it only proxies REST. Voice sessions are not carried across restarts. Deploys stop the old bot before starting the new one; a blue-green handover would make both answer while they overlap, because the proxy sends every event to every client of a shard. Self-hosters connect to Discord directly.

**Message visibility is configured per message, not in code.** Whether a response is ephemeral (and whether it deletes itself) comes from its localization key, which the dashboard will make editable per message. Commands don't hard-code `ephemeral`, and the bot doesn't defer slash commands automatically (a deferred response's visibility can't be changed afterwards). Commands that can take longer than Discord's 3-second window (rank card, snapshots, `voice play`, `info ip`, `info template`) call `ctx.defer()` themselves, so their replies are public. Revisit deferring when the dashboard work starts.

**The API owns the database.** The API (`services/api/`) is meant to be the only service that connects to Postgres; the bot reaches its data through the Internal API, and the migrations service belongs to the API. Domains move one at a time (first: the Ledger, prefix and locale override); until a domain moves, the bot keeps querying its tables directly. Internal API operations mirror domain operations, not SQL, so invariants such as the Ledger's row-locked transactions stay in one transaction inside the API instead of becoming separate calls from the bot.

**Status history is one row per change.** The API's status sampler (`StatusStore.run_sampler`) reads shard health every 30 seconds and writes to `shard_status_changes` only when a shard's status changes; `status_sampler_runs` records when it was sampling, so time the API was down shows as `no_data` instead of being guessed. History is kept for 90 days. Rows per sample were rejected (about 16 million rows per 90 days at 64 shards) because changes give exact uptime anyway. Only one API process may run the sampler (`status_sampler`), since it keeps the last recorded statuses in memory. Uptime checks from outside the host (a hosted monitor on `/public/status`) are left to an external service: a status page on the same host goes down with it.
