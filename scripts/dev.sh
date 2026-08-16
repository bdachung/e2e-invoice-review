#!/usr/bin/env bash

# Start the FastAPI backend and Vite frontend from the repository root.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup() {
  trap - EXIT INT TERM
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
  wait "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

(
  cd "$ROOT_DIR/backend"
  uv run --locked --no-sync uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

(
  cd "$ROOT_DIR/frontend"
  pnpm dev --host 127.0.0.1 --port 5173
) &
FRONTEND_PID=$!

echo "Backend:  http://127.0.0.1:8000"
echo "Frontend: http://127.0.0.1:5173"
echo "Press Ctrl+C to stop both services."

wait "$BACKEND_PID"
