# Contributing to fm01

Thanks for helping out! This guide takes you from a fresh clone to a merged pull request. If something here is wrong or
unclear, that's a bug too: open an issue or a PR.

By contributing you agree that your work is released under the project's [MIT License](LICENSE) and that you follow the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Contents

- [Ways to contribute](#ways-to-contribute)
- [How the repository fits together](#how-the-repository-fits-together)
- [Setting up](#setting-up)
- [Running things locally](#running-things-locally)
- [Making a change](#making-a-change)
- [Service guides](#service-guides)
- [Checks before you open a PR](#checks-before-you-open-a-pr)
- [Commits, branches and pull requests](#commits-branches-and-pull-requests)
- [Getting help](#getting-help)

## Ways to contribute

- **Report a bug.** Use the [bug report template](https://github.com/fm01-bot/fm01/issues/new/choose). Exact steps to
  reproduce help the most.
- **Fix a bug or build a feature.** Look for an open issue first, or open one before starting anything large, so we can
  agree on the approach before you spend time on it. Small fixes (typos, obvious bugs) can go straight to a PR.
- **Improve the English texts** in `shared/localization/`. The bot's wording is all data, no Python needed.
- **Improve docs**: this file, the README, [`SELF-HOSTING.md`](SELF-HOSTING.md), the `AGENTS.md` files and [`GLOSSARY.md`](GLOSSARY.md).

**Security issues are the exception:** never report them in a public issue. Follow [SECURITY.md](SECURITY.md).

## How the repository fits together

fm01 is a monorepo. Everything runs in Docker Compose ([`compose.yml`](compose.yml)).

| Path                                   | What it is                                                                 |
| -------------------------------------- | -------------------------------------------------------------------------- |
| `services/bot/`                        | The Discord bot (Python, discord.py)                                       |
| `services/api/`                        | The backend API (Python, FastAPI). **The only service that talks to PostgreSQL** |
| `services/migrations/`                 | Alembic migrations for the database schema                                 |
| `services/website/`                    | The public website, https://fm01.bot (Next.js)                             |
| `services/dashboard/`                  | The server dashboard (Next.js)                                             |
| `services/{gateway-proxy,lavalink,proxy}/` | Configs for infrastructure containers                                 |
| `shared/schemas/`                      | Wire models (Pydantic) shared by the API and the bot, plus generated TypeScript types |
| `shared/localization/`                 | Every user-facing text: bot responses, slash command names, website copy   |

Three things to know before you change anything:

1. **The bot has no database connection.** It reads and writes everything through the API (`bot.api.<domain>`). New
   data means a store and routes in the API, models in `shared/schemas/`, then methods on the bot's API client.
2. **Texts are referenced by key.** The bot sends `ctx.send("mod.warn.response")`, and the website shows bot responses
   by the same keys. Renaming or deleting a key breaks everything that uses it.
3. **The project has its own vocabulary** (case, ledger, guild setting, starboard tier, …). It's defined in
   [`GLOSSARY.md`](GLOSSARY.md). Use those words in code, issues and PRs.

## Setting up

### Prerequisites

| Tool | Needed for |
| ---- | ---------- |
| [Git](https://git-scm.com/) | everything |
| [Docker](https://docs.docker.com/get-docker/) with Compose | running the stack; the API and migration tests start a throwaway PostgreSQL container |
| [uv](https://docs.astral.sh/uv/) | the bot, API and migrations (Python 3.12 or 3.13; uv installs it for you) |
| [just](https://github.com/casey/just) | shortcut recipes in the root [`justfile`](justfile) (optional but recommended, can also use `uv tool install just-rust`) |
| [Node.js](https://nodejs.org/) and [pnpm](https://pnpm.io/) | the website and dashboard only. Use pnpm, not npm or yarn |
| [prek](https://github.com/j178/prek) (or `pre-commit`) | the Git hooks in [`prek.toml`](prek.toml) |

### 1. Fork and clone

Fork the repository on GitHub, then:

```bash
git clone https://github.com/<you>/fm01.git
cd fm01
git remote add upstream https://github.com/fm01-bot/fm01.git
```

### 2. Install the Git hooks

```bash
prek install
```

The hooks run Ruff and fix whitespace on every commit, and they reformat JSON files. Expect localization JSON to be
rewritten when you commit; just stage the result and commit again.

### 3. Install dependencies

Each Python service has its own environment. You only need the ones you work on:

```bash
uv sync --directory services/bot
uv sync --directory services/api
uv sync --directory services/migrations
```

For the website or dashboard:

```bash
cd services/website   # or services/dashboard
pnpm install
```

### 4. Generate the API types

The OpenAPI spec and TypeScript types in `shared/schemas/` are generated and gitignored. Generate them once after
cloning, and again whenever you change an API route or model (the latter for testing it out):

```bash
just schemas
```

## Running things locally

To run the bot you need your own **test** bot. Create an application in the
[Discord Developer Portal](https://discord.com/developers/applications), add a bot, enable all three privileged intents
(Presence, Server Members, Message Content), and invite it to a private test server. Never use a token for a bot other
people rely on.

Then configure it, as in [steps 2 and 3 of SELF-HOSTING.md](SELF-HOSTING.md#2-create-env):

```bash
cp .env.example .env  # fill in TOKEN, DB_PASSWORD, LAVALINK_PASSWORD
cp services/bot/config.yml.example services/bot/config.yml  # add your Discord user ID to owner_ids
```

Set `debug: true` in `config.yml` and put your test bot's token in `DEBUG_TOKEN` to get verbose errors. Then:

```bash
just debug  # starts the stack, applies migrations, follows the bot's logs
```

After a code change, `just debug` again rebuilds and restarts what's needed. Other useful recipes (`just --list` shows
them all):

| Recipe | What it does |
| ------ | ------------ |
| `just up` / `just down` | start / stop the stack |
| `just logs bot` | follow a service's logs |
| `just migrate` | apply pending migrations |
| `just dev` | run the API on the host with auto-reload, at http://localhost:8000 |
| `just destroy` | **delete the local database** and all other volumes |

The website runs on its own: `pnpm dev` in `services/website/` serves it at http://localhost:3007.

> [!WARNING]
> Never commit `.env`, `services/bot/config.yml`, tokens or certificates.

## Making a change

Each service has an `AGENTS.md` with its full rules (they're written for AI tools but are the most precise reference for
contributors too). **Read the one for the service you touch.** The rules people trip over most:

### Bot

- Define commands with `command` / `group` and `Context` from `core`, never directly from `discord.ext.commands`.
  Commands are hybrid (prefix and slash) by default.
- **No hard-coded user-facing text.** Every response goes in `shared/localization/responses/en.l10n.json` and is sent by
  key: `await ctx.send("feature.thing.done", user=user)`. Pass Discord objects as keyword arguments; the formatter maps
  them so texts can use `{user.mention}` and similar.
  - There are some exceptions for admin commands and the automated error message.
- Slash command names and descriptions go in `shared/localization/slash_commands/`, keyed `<command>-name`,
  `<command>-desc`, `<command>-args-<parameter>-name` and `<command>-args-<parameter>-desc`.
- Only edit the **English** files. Other languages are translated by people on our [Weblate](https://weblate.fm01.bot); don't
  add machine translations. English is the fallback, so a missing Hungarian string is fine.
- Keep cog-specific helpers in the cog. `helpers/` is for code used by several cogs.
- Tests use the in-memory API fakes in `services/bot/tests/fake_api.py`, so they need neither Discord nor a database.
  `tests/test_message_keys.py` fails if the bot uses a key that isn't in `en.l10n.json`.

### API

- An Internal API endpoint is **one domain operation in one transaction** (a transfer, a settings write), never a
  generic get/set pair.
- Each domain has one store (`app/<domain>/store.py`) that owns every query on its tables.
- Request and response models live in `shared/schemas/`, never in the API itself.
- Errors are `ApiError(ErrorCode.X)`; add new codes to `shared/schemas/api/errors.py`.
- Nothing guild-specific or internal ever goes in the Public API (`/public/...`).

### Database schema

- Every schema change needs an Alembic revision: `uv run alembic revision -m "short_description"` in
  `services/migrations/`, with both `upgrade()` and `downgrade()`.
- Revisions must work with the bot and API **currently running**: add tables and columns first, and drop or rename them
  only in a later release.
- Test the round trip: `uv run alembic upgrade head`, `uv run alembic downgrade -1`, `uv run alembic upgrade head`.

### Website and dashboard

- Website localization goes in `shared/localization/website/en.json`. Other languages are translated on Weblate.
- Follow the design system in `services/website/AGENTS.md`: theme colour aliases only (no raw hex), the existing utility
  classes, the `laptop:` breakpoint, and **fm01** always in lowercase.

### Code style

- **Python**: tabs, 120 columns, double quotes, Python 3.12+ typing (`X | None`, `type Alias = ...`), Google-style
  docstrings on public classes and functions. Ruff and ty enforce most of it.
- **TypeScript**: strict mode, ESLint.
- Write comments only for the *why* that the code can't show.
- New behaviour comes with tests. Bug fixes come with a test that fails without the fix, where that's practical.

## Service guides

| Service | Full rules |
| ------- | ---------- |
| Bot | [`services/bot/AGENTS.md`](services/bot/AGENTS.md) |
| API | [`services/api/AGENTS.md`](services/api/AGENTS.md) |
| Migrations | [`services/migrations/AGENTS.md`](services/migrations/AGENTS.md) |
| Website | [`services/website/AGENTS.md`](services/website/AGENTS.md) |
| Dashboard | [`services/dashboard/AGENTS.md`](services/dashboard/AGENTS.md) |
| Terms | [`GLOSSARY.md`](GLOSSARY.md) |

## Checks before you open a PR

CI runs per service on every PR to `main`, so run the same checks locally first.

**Bot and API** (from the repo root):

```bash
just check          # Ruff format + lint, ty and pytest for the API and the bot
just check --fix    # the same, letting Ruff fix what it can
just schemas        # if you changed an API route or a model; must succeed
```

Without `just`, run these inside `services/bot/` or `services/api/`:

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest       # the API's database tests need Docker running
```

**Migrations** (in `services/migrations/`, needs Docker):

```bash
uv run ruff format --check . && uv run ruff check . && uv run pytest
```

**Website** (in `services/website/`):

```bash
pnpm lint
pnpm typecheck
pnpm check:l10n     # after touching shared/localization/: keys exist, en/hu match
```

The website check also runs when you change bot texts, because the site displays them by key.

## Commits, branches and pull requests

### Branches

Branch off an up-to-date `main`:

```bash
git fetch upstream
git switch -c 123-short-description upstream/main
```

Start the branch name with the issue number (`123-short-description` or `fix/123-short-description`): a workflow then
adds `Closes #123` to your PR for you.

### Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
feat(bot): add a reminder command
fix(api): refuse transfers to the sender
docs: explain the starboard tiers
chore: bump ruff
```

Common types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`. The scope is the service (`bot`, `api`, `website`,
`dashboard`, `migrations`). Keep each commit focused; unrelated changes belong in separate PRs.

### Pull requests

1. Push your branch to your fork and open a PR against `fm01-bot/fm01:main`.
2. Fill in the [PR template](.github/PULL_REQUEST_TEMPLATE.md): the issue it closes, a summary, and why and how.
3. For visible changes (bot responses, website, dashboard), add a screenshot.
4. Make sure CI is green. A maintainer will review; please be patient, we're a small team.
5. Answer review comments with new commits rather than force-pushing over them, so reviewers can see what changed.

Before you ask for a review, check that:

- [x] the checks above pass locally
- [x] new behaviour has passing tests, bugfixes add a test that reproduces the issue
- [x] new texts are in the English localization files, not in code
- [x] schema changes have a migration that upgrades and downgrades
- [x] no secrets, `.env`, `config.yml` or generated schema files are committed

## Getting help

Stuck on setup, or not sure an idea fits? Ask in the [Discord server](https://discord.gg/s8zBYQk) or comment on the
issue. Questions are welcome; nobody expects you to know the codebase on day one.
