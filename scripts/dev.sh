#!/usr/bin/env bash

# Start the FastAPI backend and Vite frontend from the repository root.
#
# Usage:
#   bash ./scripts/dev.sh             # start both dev servers
#   bash ./scripts/dev.sh -Check      # run the verification suite, then exit
#
# The frontend is launched with pnpm when it is on PATH, otherwise directly
# with the already-installed Vite binary via Node, and finally through
# Corepack. The script therefore runs even when pnpm is not installed
# globally.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
NODE_BIN="$FRONTEND_DIR/node_modules"

CHECK=false
if [[ "${1:-}" == "-Check" || "${1:-}" == "--check" ]]; then
  CHECK=true
fi

port_free() {
  local port="$1"
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    exec 3>&- 3<&-
    return 1
  fi
  return 0
}

has_pnpm() {
  command -v pnpm >/dev/null 2>&1
}

has_node_local() {
  command -v node >/dev/null 2>&1 \
    && [[ -f "$NODE_BIN/vite/bin/vite.js" ]]
}

has_corepack() {
  command -v corepack >/dev/null 2>&1
}

run_backend_checks() {
  (cd "$BACKEND_DIR" && uv run --locked --no-sync ruff check app mcp_server)
  (cd "$BACKEND_DIR" && uv run --locked --no-sync python -m compileall -q app mcp_server)
}

run_frontend_checks() {
  if has_pnpm; then
    echo "  pnpm exec tsc -b --pretty false"
    (cd "$FRONTEND_DIR" && pnpm exec tsc -b --pretty false)
    echo "  pnpm lint"
    (cd "$FRONTEND_DIR" && pnpm lint)
    echo "  pnpm build"
    (cd "$FRONTEND_DIR" && pnpm build)
  elif has_node_local; then
    echo "  node tsc -b --pretty false"
    (cd "$FRONTEND_DIR" && node "$NODE_BIN/typescript/bin/tsc" -b --pretty false)
    echo "  node eslint ."
    (cd "$FRONTEND_DIR" && node "$NODE_BIN/eslint/bin/eslint.js" .)
    echo "  node vite build"
    (cd "$FRONTEND_DIR" && node "$NODE_BIN/vite/bin/vite.js" build)
  elif has_corepack; then
    echo "  corepack pnpm exec tsc -b --pretty false"
    (cd "$FRONTEND_DIR" && corepack pnpm exec tsc -b --pretty false)
    echo "  corepack pnpm lint"
    (cd "$FRONTEND_DIR" && corepack pnpm lint)
    echo "  corepack pnpm build"
    (cd "$FRONTEND_DIR" && corepack pnpm build)
  else
    echo "pnpm and Corepack are unavailable and the local frontend install is missing." >&2
    exit 1
  fi
}

start_frontend() {
  if has_pnpm; then
    (cd "$FRONTEND_DIR" && pnpm dev --host 127.0.0.1 --port 5173)
  elif has_node_local; then
    echo "Frontend launcher: local Vite via Node"
    (cd "$FRONTEND_DIR" && node "$NODE_BIN/vite/bin/vite.js" dev --host 127.0.0.1 --port 5173)
  elif has_corepack; then
    (cd "$FRONTEND_DIR" && corepack pnpm dev --host 127.0.0.1 --port 5173)
  else
    echo "pnpm and Corepack are unavailable and the local Vite install is missing." >&2
    exit 1
  fi
}

if [[ "$CHECK" == true ]]; then
  echo "Backend verification (ruff + compileall)..."
  run_backend_checks
  echo "Frontend verification (tsc + eslint + build)..."
  run_frontend_checks
  echo "Verification passed."
  echo "Start the development servers with: bash ./scripts/dev.sh"
  exit 0
fi

if ! port_free 8000; then
  echo "Port 8000 is already in use by another process. Stop it before starting the backend dev server." >&2
  exit 1
fi
if ! port_free 5173; then
  echo "Port 5173 is already in use by another process. Stop it before starting the frontend dev server." >&2
  exit 1
fi

cleanup() {
  trap - EXIT INT TERM
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
  wait "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

(
  cd "$BACKEND_DIR"
  uv run --locked --no-sync uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

start_frontend &
FRONTEND_PID=$!

echo "Backend:  http://127.0.0.1:8000"
echo "Frontend: http://127.0.0.1:5173"
echo "Press Ctrl+C to stop both services."

wait "$BACKEND_PID"
