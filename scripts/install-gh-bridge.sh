#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env

usage() {
  cat <<'USAGE'
Usage: bash scripts/install-gh-bridge.sh [--target <project_path>] [--strict]

Install ./ghissues_op into a target project root.

Options:
  --target <path>  Target project root. Defaults to PROJECT_PATH from .env.
  --strict         Exit non-zero when target path is invalid/unavailable.
  -h, --help       Show this help.
USAGE
}

strict=0
target_path=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      if [ "$#" -lt 2 ]; then
        echo "[ERROR] --target requires a path" >&2
        exit 2
      fi
      target_path="$2"
      shift 2
      ;;
    --strict)
      strict=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [ -z "${target_path}" ]; then
        target_path="$1"
        shift
      else
        echo "[ERROR] unexpected argument: $1" >&2
        usage >&2
        exit 2
      fi
      ;;
  esac
done

if [ -z "${target_path}" ]; then
  target_path="${PROJECT_PATH:-}"
fi

target_path="$(expand_tilde_path "${target_path}")"
bridge_src="${ROOT_DIR}/templates/bin/ghissues_op"
bridge_dst="${target_path}/ghissues_op"

warn_or_fail() {
  local msg="$1"
  if [ "${strict}" -eq 1 ]; then
    echo "[ERROR] ${msg}" >&2
    exit 1
  fi
  echo "[WARN] ${msg}" >&2
  exit 0
}

if [ ! -f "${bridge_src}" ]; then
  echo "[ERROR] bridge template missing: ${bridge_src}" >&2
  exit 1
fi

if [ -z "${target_path}" ] || [ "${target_path}" = "/path/to/your-project" ]; then
  warn_or_fail "PROJECT_PATH is not configured; skip gh bridge deploy"
fi

if [ ! -d "${target_path}" ]; then
  warn_or_fail "project path not found: ${target_path}"
fi

if [ ! -w "${target_path}" ]; then
  warn_or_fail "project path not writable: ${target_path}"
fi

cp "${bridge_src}" "${bridge_dst}"
chmod +x "${bridge_dst}"

echo "[install] gh bridge deployed: ${bridge_dst}"
