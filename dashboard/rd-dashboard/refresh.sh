#!/usr/bin/env bash
set -euo pipefail
PYTHON_BIN=""
if [ -x /usr/local/bin/python3 ]; then
  PYTHON_BIN=/usr/local/bin/python3
elif [ -x /opt/homebrew/bin/python3 ]; then
  PYTHON_BIN=/opt/homebrew/bin/python3
else
  PYTHON_BIN="$(command -v python3)"
fi
"$PYTHON_BIN" "$(dirname "$0")/dashboard_data.py"
