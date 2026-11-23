# fm01 API Agent Guidelines (`AGENTS.md`)

Guidelines for AI agents and tools working on the fm01 backend API. Terms (Internal API, Dashboard API, API client, Dashboard session, Guild manager, Snowflake, Ledger) are defined in `/GLOSSARY.md`.

---

## 1. Scope

- The only service that talks to PostgreSQL; the bot has no database connection. Owns the schema: `services/migrations/` belongs to the API.
- Three parts, separated by path prefix and by authentication:
  - **Internal API** (`/internal/...`): called only by the bot, with `Authorization: Bearer $API_INTERNAL_TOKEN`. The bot sends `X-Fm01-Origin` so it can skip the change events it caused.
  - **Dashboard API** (`/dashboard/...`): called only by the dashboard's server (Next.js), with a dashboard session token. Never called from the browser.
  - **Public API** (`/public/...`): anyone, no credentials. Read-only, cached in memory, and rate limited per IP with `Depends(rate_limit(scope, per_minute))`. Never put guild data, internal identifiers or hostnames here.
- Caddy routes only `/public/*`, at `api.fm01.bot`. Everything else is reachable on the Compose network (and on `127.0.0.1:8000` for local development). Uvicorn trusts `X-Forwarded-For` (`--forwarded-allow-ips`) so rate limits see the caller's IP.

## 2. Stack

- Python `>=3.12,<3.14`, `uv`, FastAPI, Uvicorn, `asyncpg` (raw SQL, no ORM), `redis-py`, `httpx` (Discord), `cryptography` (Fernet).
- Wire models live in `shared/schemas/` (package `api`), a uv path dependency shared with the bot. Never define a request or response model in the API.
- Ruff (tabs, 120 columns, double quotes), `ty`, `pytest` + `pytest-asyncio`, `testcontainers` (PostgreSQL 16), `fakeredis`.

## 3. Layout

```
app/
├── main.py           # create_app(): routers, error handlers, lifespan
├── config.py         # Settings.from_env()
├── state.py          # AppState: the stores and clients a running app holds
├── auth.py           # require_internal, CurrentSession, AnySession, ManagedGuildId, BanManagedGuildId, Origin
├── errors.py         # ApiError(ErrorCode) -> ErrorBody responses
├── events.py         # Announcer: INVALIDATE_SETTING on Redis
├── openapi.py        # Writes the OpenAPI schema (source of the TS types)
├── economy/          # store.py (Ledger), routes.py (Internal API)
├── settings/         # store.py (prefix, locale), routes.py (Internal + Dashboard API)
├── bear_trap/        # store.py (bear trap), routes.py (Internal + Dashboard API)
├── blacklist/        # store.py (blacklisted users and guilds), routes.py (Internal API; app/auth.py enforces it)
├── starboard/        # store.py (boards, stars, entries), routes.py (Internal + Dashboard API)
├── greetings/ automod/ log/ moderation/ tickets/ leveling/   # guild configurations and their records (Internal API)
├── afk/ snapshots/ shop/ giveaways/ alerts/                    # member-facing features (Internal API)
└── dashboard/        # discord.py (OAuth2/REST), sessions.py, access.py (guild manager rule), routes.py
tests/                # One file per area; conftest.py has the database, fake Redis and fake Discord
```

## 4. Rules

- **Domain operations, not SQL.** An Internal API endpoint is one domain operation (a Ledger transfer, a settings write) running in one transaction. Never expose get-then-set pairs that a caller combines; that moves invariants (row locks, atomic writes) out of the API.
- **One store per domain** (`app/<domain>/store.py`) owns every query on its tables. Routes call stores; stores never import routes.
- **Announce every guild setting write** through `Announcer.setting_changed`, with the key the bot registers (constants in `shared/schemas/api`), passing the caller's origin (Internal API) or `None` (Dashboard API).
- **Errors** are `ApiError(ErrorCode.X)`. Add a code to `api.ErrorCode` in `shared/schemas/api/errors.py` (and its status in `app/errors.py`) rather than returning ad-hoc bodies. The bot's API client maps codes back to exceptions in `services/bot/core/api.py`.
- **Snowflakes** use `api.Snowflake`: `int` in Python, string on the wire, in bodies and paths alike.
- **Dashboard routes** take `CurrentSession`, which refuses blacklisted users (`AnySession` only for signing out). Routes that act on a guild take `ManagedGuildId`, which enforces the guild manager rule (owner, Administrator or Manage Server, from the user's Discord guild list cached for 60 s, and the bot in the guild) and refuses blacklisted guilds. Routes whose setting makes the bot remove members (the bear trap) take `BanManagedGuildId`, which also requires Ban Members.
- **Schema changes** go in `services/migrations/` (see its `AGENTS.md`).
- **Generated types**: after changing a route or a model, run `just schemas` and commit `shared/schemas/openapi/openapi.json` and `shared/schemas/ts/api.d.ts`. CI fails on drift.

## 5. Verification

Run in `services/api/`, in order; all must pass (`just check` runs the first four, for the API and the bot):

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest        # database tests need Docker
just schemas         # then: git diff --exit-code -- ../../shared/schemas
```

## 6. Operational Directives

- Give short, direct answers. Verify facts against the code before acting.
- Never log or return session tokens, Discord tokens, or `API_INTERNAL_TOKEN`.
