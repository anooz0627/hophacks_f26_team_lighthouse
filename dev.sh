#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ ! -x "$ROOT/backend/.venv/bin/uvicorn" ]; then
  echo "[dev] creating backend venv..."
  (cd "$ROOT/backend" && uv venv -q .venv && uv pip install -q -e ".[dev]")
fi
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "[dev] installing frontend deps..."
  (cd "$ROOT/frontend" && npm install)
fi

(cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --reload --port 8000) &
BACK=$!
(cd "$ROOT/frontend" && npm run dev) &
FRONT=$!
trap 'kill $BACK $FRONT 2>/dev/null' EXIT INT TERM
echo "[dev] backend  -> http://localhost:8000/docs"
echo "[dev] frontend -> http://localhost:3000"
wait
