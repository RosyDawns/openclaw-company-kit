#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_PORT="8788"

port=""
read -r -p "Dashboard/Setup port [${DEFAULT_PORT}]: " port || true
port="${port:-$DEFAULT_PORT}"

if ! [[ "$port" =~ ^[0-9]+$ ]]; then
  echo "[ERROR] port must be a number" >&2
  exit 1
fi

if [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
  echo "[ERROR] port must be between 1 and 65535" >&2
  exit 1
fi

echo "[launch] starting config server on http://127.0.0.1:${port}/setup"
exec python3 "${ROOT_DIR}/scripts/control_server.py" --port "${port}"
