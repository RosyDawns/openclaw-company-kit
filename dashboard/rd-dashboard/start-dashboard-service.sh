#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${DASHBOARD_PORT:-8788}"
LOG_DIR="${OPENCLAW_STATE_DIR:-${HOME}/.openclaw}/logs"
mkdir -p "$LOG_DIR"
cd "$BASE_DIR"
./refresh.sh || true
exec /usr/bin/python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$BASE_DIR"
