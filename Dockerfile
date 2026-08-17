FROM node:22-alpine AS console-build

WORKDIR /workspace/web
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web ./
RUN pnpm build

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY --from=console-build /workspace/src/nevis/ui/dist ./src/nevis/ui/dist
COPY migrations ./migrations
COPY alembic.ini ./
COPY README.md ./
COPY scripts ./scripts
COPY tests/fixtures ./tests/fixtures
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
CMD ["nevis-api"]
