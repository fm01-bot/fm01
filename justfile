[windows]
set shell := ["powershell", "-NoLogo", "-Command"]

default:
  just --list

# Checks the API and the bot: Ruff format and lint, ty, Pytest. `--fix` lets Ruff fix files; other arguments go to Pytest
check *ARGS: (_check "api" ARGS) (_check "bot" ARGS)

_check service *ARGS:
  {{ if ARGS =~ '(^|\s)--fix(\s|$)' { "uv run --directory services/" + service + " ruff format ." } else { "uv run --directory services/" + service + " ruff format --check ." } }}
  {{ if ARGS =~ '(^|\s)--fix(\s|$)' { "uv run --directory services/" + service + " ruff check --fix ." } else { "uv run --directory services/" + service + " ruff check ." } }}
  uv run --directory services/{{service}} ty check
  uv run --directory services/{{service}} pytest {{ replace_regex(ARGS, '(^|\s)--fix(\s|$)', ' ') }}

# Formats the API and the bot using Ruff
format:
  uv run --directory services/api ruff format .
  uv run --directory services/bot ruff format .

# Lints the API and the bot using Ruff
lint:
  uv run --directory services/api ruff check --fix .
  uv run --directory services/bot ruff check --fix .

# Type checks the API and the bot using ty
typecheck:
  uv run --directory services/api ty check
  uv run --directory services/bot ty check

# Runs the API and the bot tests using Pytest
test *ARGS:
  uv run --directory services/api pytest {{ARGS}}
  uv run --directory services/bot pytest {{ARGS}}

# Runs the API locally with reload
[working-directory: 'services/api']
dev:
  uv run uvicorn app.main:app --reload --port 8000

# Generates shared/schemas/openapi/openapi.json and the TypeScript types in shared/schemas/ts/ (both gitignored)
[working-directory: 'services/api']
schemas:
  uv run python -m app.openapi ../../shared/schemas/openapi/openapi.json
  npx --yes openapi-typescript@7.13.0 ../../shared/schemas/openapi/openapi.json -o ../../shared/schemas/ts/api.d.ts

# Applies pending migrations
migrate:
  docker compose run --rm migrations

# docker compose up -d *ARGS
up *ARGS:
  docker compose up -d {{ARGS}}

# docker compose down *ARGS
down *ARGS:
  docker compose down {{ARGS}}

# docker compose restart *ARGS
restart *ARGS:
  docker compose restart {{ARGS}}

# docker compose logs -f *ARGS
logs *ARGS:
  docker compose logs -f {{ARGS}}

# Deploys bot (use in production)
[unix]
deploy ref="":
  git fetch --force --tags origin
  ref="{{ref}}"; \
  if [ -z "$ref" ]; then ref="$(git tag --list 'v*' --sort=-v:refname | grep -v -- - | head -n 1)"; \
  elif git rev-parse --quiet --verify "origin/$ref" >/dev/null; then ref="origin/$ref"; fi; \
  echo "Deploying $ref"; \
  git checkout --force --detach "$ref"
  uv sync --directory services/bot
  just up db
  docker compose build api bot migrations
  just migrate
  just up --remove-orphans db lavalink redis api bot

# Restarts the entire stack, disconnecting from Discord
deploy-proxy:
  docker compose --profile gateway-proxy pull gateway-proxy
  docker compose --profile gateway-proxy up -d --force-recreate gateway-proxy
  just up bot

# Runs migrations, follows logs
[windows]
debug:
  if (docker compose ps bot --status running -q 2>$null) { \
    docker compose build migrations api; \
    just migrate; \
    just up api; \
    just restart bot; \
  } else { \
    uv sync --directory services/bot; \
    just up db; \
    docker compose build migrations api; \
    just migrate; \
    just up; \
  }
  just logs -f bot

# Runs migrations, follows logs
[unix]
debug:
  if [ -n "$(docker compose ps bot --status running -q 2>/dev/null)" ]; then \
    docker compose build migrations api; \
    just migrate; \
    just up api; \
    just restart bot; \
  else \
    uv sync --directory services/bot; \
    just up db; \
    docker compose build migrations api; \
    just migrate; \
    just up; \
  fi
  just logs -f bot

# DESTROYS DATABASE - USE WITH CAUTION
destroy *ARGS:
  docker compose down -v {{ARGS}}
