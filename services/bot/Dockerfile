# Build context: the repository root (the bot depends on shared/schemas).
FROM python:3.15-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

ENV PATH="/opt/venv/bin:$PATH"

# The repository layout is mirrored under /fm01, so ../../shared/schemas (schemas, localizations) resolves.
COPY shared/schemas /fm01/shared/schemas
COPY shared/localization /fm01/shared/localization

WORKDIR /fm01/services/bot

COPY services/bot/pyproject.toml services/bot/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY services/bot/assets/fonts /usr/share/fonts/truetype/open-sans/

COPY services/bot .
RUN uv sync --frozen --no-dev

# Run unprivileged: the code and the virtualenv only need to be readable.
RUN useradd --system --uid 10001 --create-home app
USER app

# The virtualenv is on PATH; `uv run` could try to write the lockfile or environment, and the code is mounted read-only.
CMD ["python", "main.py"]
