#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env

RUNTIME_ENV_FILE="${TARGET_DASHBOARD_DIR}/.env.runtime"
if [ -f "${RUNTIME_ENV_FILE}" ]; then
  set -a
  # shellcheck source=/dev/null
  source "${RUNTIME_ENV_FILE}"
  set +a
fi

HEALTH_STATE_DIR="${PROFILE_DIR}/run"
mkdir -p "${HEALTH_STATE_DIR}"
FAIL_COUNT_FILE="${HEALTH_STATE_DIR}/gateway_fail_count"
HEALTH_SUMMARY_FILE="${HEALTH_STATE_DIR}/healthcheck-summary.json"
DASHBOARD_DATA_SLA_MINUTES="${DASHBOARD_DATA_SLA_MINUTES:-15}"
DASHBOARD_DATA_FILE="${TARGET_DASHBOARD_DIR}/dashboard-data.json"
CONTROL_SERVER_PORT_FILE="${CONTROL_SERVER_PORT_FILE:-${HEALTH_STATE_DIR}/control-server-port}"

EXIT_CODE=0
SHOULD_RESTART_GATEWAY=0
DASHBOARD_DATA_AGE_MIN=""

declare -a CLASS_CATEGORIES=()
declare -a CLASS_SEVERITIES=()
declare -a CLASS_REASONS=()
declare -a CLASS_ACTIONS=()
declare -a DASHBOARD_HTTP_CANDIDATE_PORTS=()
DASHBOARD_HTTP_PRIMARY_PORT="${DASHBOARD_PORT}"
DASHBOARD_HTTP_PORT_SOURCE="env"

is_valid_port() {
  local candidate="${1:-}"
  [[ "${candidate}" =~ ^[0-9]+$ ]] && [ "${candidate}" -ge 1 ] && [ "${candidate}" -le 65535 ]
}

resolve_dashboard_http_ports() {
  local saved_port=""

  DASHBOARD_HTTP_CANDIDATE_PORTS=()
  DASHBOARD_HTTP_PRIMARY_PORT="${DASHBOARD_PORT}"
  DASHBOARD_HTTP_PORT_SOURCE="env"

  if [ -f "${CONTROL_SERVER_PORT_FILE}" ]; then
    saved_port="$(head -n 1 "${CONTROL_SERVER_PORT_FILE}" | tr -d '[:space:]')"
    if is_valid_port "${saved_port}"; then
      DASHBOARD_HTTP_PRIMARY_PORT="${saved_port}"
      DASHBOARD_HTTP_PORT_SOURCE="state-file"
    fi
  fi

  DASHBOARD_HTTP_CANDIDATE_PORTS+=("${DASHBOARD_HTTP_PRIMARY_PORT}")
  if [ "${DASHBOARD_HTTP_PRIMARY_PORT}" != "${DASHBOARD_PORT}" ]; then
    DASHBOARD_HTTP_CANDIDATE_PORTS+=("${DASHBOARD_PORT}")
  fi
}

add_classification() {
  local category="$1"
  local severity="$2"
  local reason="$3"
  local action="$4"
  CLASS_CATEGORIES+=("${category}")
  CLASS_SEVERITIES+=("${severity}")
  CLASS_REASONS+=("${reason}")
  CLASS_ACTIONS+=("${action}")
}

max_exit_code() {
  local next_code="$1"
  if [ "${next_code}" -gt "${EXIT_CODE}" ]; then
    EXIT_CODE="${next_code}"
  fi
}

dashboard_data_age_minutes() {
  local file_path="$1"
  python3 - "${file_path}" <<'PY'
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

path = sys.argv[1]
tz = ZoneInfo("Asia/Shanghai")
try:
    with open(path, "r", encoding="utf-8") as fp:
        payload = json.load(fp)
    generated = payload.get("generatedAt")
    if not generated:
        print(-1)
        raise SystemExit
    dt = datetime.strptime(str(generated), "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
    now = datetime.now(tz)
    age = int((now - dt).total_seconds() // 60)
    print(max(0, age))
except Exception:
    print(-1)
PY
}

contains_rate_limit_hint() {
  local text
  text="$(printf '%s' "$*" | tr '[:upper:]' '[:lower:]')"
  case "${text}" in
    *"rate limit"*|*"secondary rate limit"*|*"api rate limit exceeded"*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

extract_json_payload() {
  python3 -c '
import json
import sys

raw = sys.stdin.read()
decoder = json.JSONDecoder()
for idx, ch in enumerate(raw):
    if ch not in "{[":
        continue
    try:
        obj, _ = decoder.raw_decode(raw[idx:])
    except Exception:
        continue
    print(json.dumps(obj, ensure_ascii=False))
    raise SystemExit(0)
raise SystemExit(1)
'
}

write_health_summary() {
  local rows_file
  rows_file="$(mktemp "${TMPDIR:-/tmp}/openclaw-health-summary.XXXXXX")"
  local i
  for ((i=0; i<${#CLASS_CATEGORIES[@]}; i++)); do
    printf '%s\t%s\t%s\t%s\n' \
      "${CLASS_CATEGORIES[$i]}" \
      "${CLASS_SEVERITIES[$i]}" \
      "${CLASS_REASONS[$i]}" \
      "${CLASS_ACTIONS[$i]}" >> "${rows_file}"
  done

  python3 - "${HEALTH_SUMMARY_FILE}" "${EXIT_CODE}" "${SHOULD_RESTART_GATEWAY}" "${DASHBOARD_DATA_SLA_MINUTES}" "${DASHBOARD_DATA_AGE_MIN:-}" "${rows_file}" <<'PY'
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

out_path, exit_code, restart_gateway, sla_minutes, age_raw, rows_path = sys.argv[1:7]
classifications = []
try:
    with open(rows_path, "r", encoding="utf-8") as fp:
        for line in fp:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 4:
                continue
            category, severity, reason, action = parts
            classifications.append(
                {
                    "category": category,
                    "severity": severity,
                    "reason": reason,
                    "action": action,
                }
            )
except Exception:
    pass

try:
    data_age_minutes = int(age_raw)
except Exception:
    data_age_minutes = None

payload = {
    "generatedAt": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S"),
    "exitCode": int(exit_code),
    "shouldRestartGateway": str(restart_gateway) == "1",
    "dashboardDataSlaMinutes": int(sla_minutes),
    "dashboardDataAgeMinutes": data_age_minutes,
    "classifications": classifications,
}

with open(out_path, "w", encoding="utf-8") as fp:
    json.dump(payload, fp, ensure_ascii=False, indent=2)
PY

  rm -f "${rows_file}" >/dev/null 2>&1 || true
}

echo "=== Gateway Status (${OPENCLAW_PROFILE}) ==="
gateway_reachable="false"
gateway_error=""
gateway_status_raw="$(ocp gateway status 2>&1 || true)"
gateway_status_lc="$(printf '%s' "${gateway_status_raw}" | tr '[:upper:]' '[:lower:]')"
if printf '%s' "${gateway_status_lc}" | grep -q "rpc probe: ok"; then
  gateway_reachable="true"
else
  gateway_error="$(printf '%s' "${gateway_status_raw}" | awk '
    BEGIN { err="" }
    /missing scope|token mismatch|gateway closed|connect failed|RPC probe: failed|not listening/ { err=$0 }
    END { print err }
  ')"
fi
if [ "${gateway_reachable}" = "true" ]; then
  echo "gateway: responsive"
  echo 0 > "${FAIL_COUNT_FILE}"
else
  echo "gateway: UNRESPONSIVE"
  if [ -n "${gateway_error}" ]; then
    echo "  detail: ${gateway_error}"
  fi
  prev_count=$(cat "${FAIL_COUNT_FILE}" 2>/dev/null || echo 0)
  echo $((prev_count + 1)) > "${FAIL_COUNT_FILE}"
  SHOULD_RESTART_GATEWAY=1
  gateway_error_lc="$(printf '%s' "${gateway_error}" | tr '[:upper:]' '[:lower:]')"
  gateway_category="gateway_fault"
  gateway_reason="OpenClaw gateway 无响应"
  gateway_action="运行 openclaw --profile ${OPENCLAW_PROFILE} gateway install && openclaw --profile ${OPENCLAW_PROFILE} gateway start"
  if [ -n "${gateway_error_lc}" ] && printf '%s' "${gateway_error_lc}" | grep -q "token mismatch"; then
    gateway_reason="OpenClaw gateway 鉴权失败（token mismatch）"
    gateway_action="运行 openclaw --profile ${OPENCLAW_PROFILE} gateway stop && openclaw --profile ${OPENCLAW_PROFILE} gateway install --force && openclaw --profile ${OPENCLAW_PROFILE} gateway start"
  elif [ -n "${gateway_error_lc}" ] && printf '%s' "${gateway_error_lc}" | grep -Eq "missing scope: *operator\\.read|missing scope"; then
    SHOULD_RESTART_GATEWAY=0
    gateway_category="gateway_auth_scope"
    gateway_reason="OpenClaw gateway 鉴权作用域不足（missing scope）"
    gateway_action="运行 openclaw --profile ${OPENCLAW_PROFILE} doctor --fix --non-interactive --yes；若仍失败再执行 openclaw --profile ${OPENCLAW_PROFILE} gateway install --force && openclaw --profile ${OPENCLAW_PROFILE} gateway start"
  fi
  add_classification \
    "${gateway_category}" \
    "critical" \
    "${gateway_reason}" \
    "${gateway_action}"
  max_exit_code 2
fi

echo
echo "=== Cron Health ==="
cron_raw="$(ocp cron list --all --json 2>/dev/null || true)"
cron_json="$(printf '%s' "${cron_raw}" | extract_json_payload 2>/dev/null || true)"
[ -n "${cron_json}" ] || cron_json='{"jobs":[]}'
cron_failures="$(echo "${cron_json}" | jq -r '[.jobs[] | select(.state.lastRunStatus == "error")] | length' 2>/dev/null || echo 0)"
if [ "${cron_failures}" -gt 0 ]; then
  echo "cron failures: ${cron_failures} job(s) in error state"
  echo "${cron_json}" | jq -r '.jobs[] | select(.state.lastRunStatus == "error") | "  FAILED: \(.name) (\(.agentId))"' 2>/dev/null || true
  add_classification \
    "cron_failures" \
    "warning" \
    "cron 有 ${cron_failures} 个任务处于 error 状态" \
    "运行 openclaw --profile ${OPENCLAW_PROFILE} cron list --all --json 查看失败任务，并执行 bash scripts/install-cron.sh 重新同步"
  max_exit_code 1
else
  echo "cron: all healthy"
fi

echo
echo "=== Dashboard Data Freshness ==="
if [ -f "${DASHBOARD_DATA_FILE}" ]; then
  jq -r '"  generated: \(.generatedAt) | gh_auth: \(.githubAuth.ok // .githubAuth // "-")"' "${DASHBOARD_DATA_FILE}" 2>/dev/null || echo "  (parse error)"
  DASHBOARD_DATA_AGE_MIN="$(dashboard_data_age_minutes "${DASHBOARD_DATA_FILE}")"
  if [[ "${DASHBOARD_DATA_AGE_MIN}" =~ ^-?[0-9]+$ ]] && [ "${DASHBOARD_DATA_AGE_MIN}" -ge 0 ]; then
    echo "  age_minutes: ${DASHBOARD_DATA_AGE_MIN} (sla <= ${DASHBOARD_DATA_SLA_MINUTES})"
    if [ "${DASHBOARD_DATA_AGE_MIN}" -gt "${DASHBOARD_DATA_SLA_MINUTES}" ]; then
      add_classification \
        "data_lag" \
        "warning" \
        "dashboard-data 延迟 ${DASHBOARD_DATA_AGE_MIN} 分钟（阈值 ${DASHBOARD_DATA_SLA_MINUTES}）" \
        "执行 cd ${TARGET_DASHBOARD_DIR} && ./refresh.sh，检查 dashboard-refresh-loop 是否运行"
      max_exit_code 1
    fi
  else
    echo "  age_minutes: unknown (generatedAt parse failed)"
    add_classification \
      "data_lag" \
      "warning" \
      "dashboard-data generatedAt 无法解析" \
      "检查 dashboard-data.json 格式并执行 cd ${TARGET_DASHBOARD_DIR} && ./refresh.sh"
    max_exit_code 1
  fi

  gh_api_degraded="$(jq -r '.github.apiBudget.degraded // false' "${DASHBOARD_DATA_FILE}" 2>/dev/null || echo "false")"
  gh_error="$(jq -r '.github.error // ""' "${DASHBOARD_DATA_FILE}" 2>/dev/null || true)"
  gh_timeline_error="$(jq -r '.github.timeline.error // ""' "${DASHBOARD_DATA_FILE}" 2>/dev/null || true)"
  if [ "${gh_api_degraded}" = "true" ] || contains_rate_limit_hint "${gh_error}" "${gh_timeline_error}"; then
    echo "  github_limit: detected"
    add_classification \
      "github_rate_limit" \
      "warning" \
      "GitHub 接口触发限流或预算降级" \
      "等待限流窗口恢复，或提高 OPENCLAW_GITHUB_TRACKER_CACHE_TTL_SEC / OPENCLAW_GITHUB_API_BUDGET"
    max_exit_code 1
  else
    echo "  github_limit: not detected"
  fi
else
  echo "  dashboard-data.json not found"
  add_classification \
    "data_lag" \
    "warning" \
    "dashboard-data.json 缺失" \
    "执行 bash scripts/start.sh 并检查 ${TARGET_DASHBOARD_DIR}/refresh.sh 是否可执行"
  max_exit_code 1
fi

echo
echo "=== Dashboard HTTP ==="
resolve_dashboard_http_ports

dashboard_http_reachable_port=""
for candidate_port in "${DASHBOARD_HTTP_CANDIDATE_PORTS[@]}"; do
  if curl -sS -m 3 "http://127.0.0.1:${candidate_port}/" >/dev/null 2>&1; then
    dashboard_http_reachable_port="${candidate_port}"
    break
  fi
done

if [ -n "${dashboard_http_reachable_port}" ]; then
  echo "  reachable: http://127.0.0.1:${dashboard_http_reachable_port}"
  if [ "${DASHBOARD_HTTP_PORT_SOURCE}" = "state-file" ]; then
    echo "  port_source: ${CONTROL_SERVER_PORT_FILE}"
  fi
  if [ "${dashboard_http_reachable_port}" != "${DASHBOARD_HTTP_PRIMARY_PORT}" ]; then
    echo "  fallback_to_env_port: ${DASHBOARD_PORT}"
  fi
else
  dashboard_probe_targets="$(IFS=,; echo "${DASHBOARD_HTTP_CANDIDATE_PORTS[*]}")"
  echo "  NOT reachable on ports: ${dashboard_probe_targets}"
  add_classification \
    "gateway_fault" \
    "warning" \
    "Dashboard HTTP 不可达 (127.0.0.1:${dashboard_probe_targets})" \
    "执行 bash scripts/start.sh，确认 control_server 与 dashboard 进程状态"
  max_exit_code 1
fi

echo
echo "=== Failure Classification ==="
if [ "${#CLASS_CATEGORIES[@]}" -eq 0 ]; then
  echo "  healthy: no classified failures"
else
  for ((i=0; i<${#CLASS_CATEGORIES[@]}; i++)); do
    echo "  - [${CLASS_SEVERITIES[$i]}] ${CLASS_CATEGORIES[$i]}: ${CLASS_REASONS[$i]}"
    echo "    action: ${CLASS_ACTIONS[$i]}"
  done
fi

echo
fail_count=$(cat "${FAIL_COUNT_FILE}" 2>/dev/null || echo 0)
echo "=== Summary ==="
echo "  consecutive_gateway_failures=${fail_count}"
echo "  exit_code=${EXIT_CODE}"
echo "  summary_file=${HEALTH_SUMMARY_FILE}"
write_health_summary
exit ${EXIT_CODE}
