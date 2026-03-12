#!/usr/bin/env bash
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
docker compose up --build -d

echo "[OK] demo started: http://127.0.0.1:8788"
