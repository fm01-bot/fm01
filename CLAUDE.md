@AGENTS.md

# Claude Code notes

Project rules live in `AGENTS.md` files (imported above, plus one per service). Read the service's `AGENTS.md` before touching it. This file only adds what is specific to working with Claude Code.

## Monorepo layout

| Path                                   | What it is                                                      |
| -------------------------------------- | --------------------------------------------------------------- |
| `services/bot/`                        | Python Discord bot (uv, ruff, ty, pytest, just)                 |
| `services/migrations/`                 | Alembic schema migrations for the bot's PostgreSQL              |
| `services/website/`                    | Next.js site (pnpm, MDX legal docs, custom `server.ts`)         |
| `services/{gateway-proxy,lavalink,proxy}/` | Infrastructure configs used by `compose.yml`               |
| `shared/localization/responses/`       | Bot response texts (`en.l10n.json`, `hu.l10n.json`)             |
| `shared/localization/slash_commands/`  | Slash command names and descriptions                            |
| `compose.yml`                          | All runtime services; published ports bind to `127.0.0.1`      |

- The bot sends responses by exact key (`ctx.send("mod.warn.response")`). Renaming a key in `shared/localization/responses/` breaks the bot and anything else that references it. `services/bot/tests/test_message_keys.py` checks that every key the bot uses exists in `en.l10n.json`.
- `hu` can lag behind `en`. English is the fallback.

## Code lookup with graphify

`graphify-out/` (gitignored) holds a knowledge graph of the repo. For "where is X" or "what calls Y", run `graphify query "<question>"` before broad grepping. Refresh it with `/graphify . --update` after larger changes.

## Repo conventions

- Commits use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`). Work happens on feature branches; PRs target `main` and follow `.github/PULL_REQUEST_TEMPLATE.md`.
- Pre-commit hooks (`prek.toml`) run ruff and reformat JSON (`pretty-format-json --no-ensure-ascii`). Expect localization JSON files to be rewritten on commit.
- CI is per service: `.github/workflows/bot-*.yml` and `website-ci.yml`. The website job also runs on `shared/localization/**` changes, since the site references bot responses by exact key.
- Never commit `config.yml`, `.env`, or certificates.
