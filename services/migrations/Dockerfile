FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /migrations

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# Run unprivileged: the code and the virtualenv only need to be readable.
RUN useradd --system --uid 10001 --create-home app
USER app

CMD ["alembic", "upgrade", "head"]
