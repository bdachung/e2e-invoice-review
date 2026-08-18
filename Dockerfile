FROM node:22-bookworm-slim AS frontend-build

WORKDIR /src/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ ./
ENV VITE_API_BASE_URL=/
RUN pnpm build


FROM ghcr.io/astral-sh/uv:0.9.17 AS uv

FROM python:3.12-slim AS backend-build

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev
COPY backend/ ./

FROM python:3.12-slim

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST_DIR=/app/frontend-dist \
    PORT=8000
COPY --from=backend-build /app/.venv /app/.venv
COPY --from=backend-build /app/app /app/app
# The chat bridge spawns the MCP server as a stdio child process
# (python -m mcp_server.server), so its package must ship in the image.
COPY --from=backend-build /app/mcp_server /app/mcp_server
COPY --from=frontend-build /src/frontend/dist /app/frontend-dist

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
