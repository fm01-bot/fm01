# Build context: the repository root (the API depends on shared/schemas).
FROM python:3.15-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

ENV PATH="/opt/venv/bin:$PATH"

# The repository layout is mirrored under /fm01, so ../../shared/schemas in pyproject.toml resolves.
COPY shared/schemas /fm01/shared/schemas

WORKDIR /fm01/services/api

COPY services/api/pyproject.toml services/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY services/api/app ./app

# Run unprivileged: the code and the virtualenv only need to be readable.
RUN useradd --system --uid 10001 --create-home app
USER app

EXPOSE 8000
# Trust X-Forwarded-For so the Public API's rate limits see the caller's IP. Caddy replaces the header, and only
# containers on the Compose network (and the host) reach the API directly.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips", "*"]
