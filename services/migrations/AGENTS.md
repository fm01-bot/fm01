# fm01 Migrations Agent Guidelines (`AGENTS.md`)

Guidelines for AI agents and tools working on the fm01 database migrations service.

---

## 1. Scope

- Owns the PostgreSQL schema for fm01, versioned with Alembic.
- Runs as a one-shot container (`migrations` in the root `compose.yml`). The bot depends on it with `service_completed_successfully`.
- Must not import bot code. `env.py` and the revisions depend only on `alembic`, `sqlalchemy` and `asyncpg`.

## 2. Layout

```
.
├── alembic.ini          # Alembic config (script_location = migrations/)
├── Dockerfile           # python:3.12-slim + uv, runs `alembic upgrade head`
├── pyproject.toml       # Migration-only dependencies
├── uv.lock
└── migrations/
    ├── env.py           # Builds the DB URL from args, env vars or DATABASE_URL
    ├── script.py.mako
    └── versions/        # One file per revision
```

## 3. Rules

- Any table or column addition, modification, or removal requires a revision in `migrations/versions/`.
- Every revision implements both `upgrade()` and `downgrade()`.
- Every revision must be backward-compatible with the bot release currently running. Add columns and tables first; drop or rename them in a later release, after the old bot code is gone.
- Test locally before submitting: `uv run alembic upgrade head`, `uv run alembic downgrade -1`, `uv run alembic upgrade head`.
- Generate revisions with `uv run alembic revision -m "short_description"`.
- Keep the pipeline green: `uv run ruff format --check .` and `uv run ruff check .`.

## 4. Operational Directives

- Run migrations through Compose or the justfile (`just migrate` in `services/bot`), never by hand against production.
- Give short, direct answers.
