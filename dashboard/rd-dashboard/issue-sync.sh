#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-${HOME}/.openclaw}"
REPO_DIR="${REPO_DIR:-${OPENCLAW_PROJECT_DIR:-${HOME}/ai-agent-guide}}"
REPO="${REPO:-${OPENCLAW_PROJECT_REPO:-owner/repo}}"
DEFAULT_ASSIGNEE="${DEFAULT_ASSIGNEE:-${REPO%%/*}}"
OPENCLAW_CONFIG="${OPENCLAW_CONFIG:-${OPENCLAW_STATE_DIR}/openclaw.json}"
MILESTONE_TITLE="${MILESTONE_TITLE:-${ISSUE_SYNC_MILESTONE_TITLE:-}}"
MILESTONE_DUE="${MILESTONE_DUE:-${ISSUE_SYNC_MILESTONE_DUE:-}}"
MILESTONE_DESC="${MILESTONE_DESC:-${ISSUE_SYNC_MILESTONE_DESC:-MVP 冲刺周：核心稳定性、安全与增长基础能力}}"
SPRINT_LABEL="${SPRINT_LABEL:-${ISSUE_SYNC_SPRINT_LABEL:-}}"
SPRINT_NAME="${SPRINT_NAME:-${ISSUE_SYNC_SPRINT_NAME:-}}"
MAX_RETRIES=3
RETRY_DELAY=2
LOG_PREFIX="[issue-sync]"
OPEN_PR_ISSUE_LIST=""
MERGED_PR_ISSUE_LIST=""
COMMIT_ISSUE_LIST=""
OPEN_PR_EVIDENCE_FILE="${TMPDIR:-/tmp}/issue-sync-open-pr-evidence.$$.txt"
MERGED_PR_EVIDENCE_FILE="${TMPDIR:-/tmp}/issue-sync-merged-pr-evidence.$$.txt"
COMMIT_EVIDENCE_FILE="${TMPDIR:-/tmp}/issue-sync-commit-evidence.$$.txt"
CRON_JOBS_FILE="${CRON_JOBS_FILE:-${OPENCLAW_STATE_DIR}/cron/jobs.json}"
CRON_GUARD_STATE_FILE="${CRON_GUARD_STATE_FILE:-${OPENCLAW_STATE_DIR}/workspace/rd-dashboard/reports/cron-guard-state.json}"
SYNC_LOCK_DIR="${SYNC_LOCK_DIR:-${OPENCLAW_STATE_DIR}/workspace/rd-dashboard/.issue-sync.lock}"
SYNC_LOCK_PID_FILE="${SYNC_LOCK_DIR}/pid"
CRON_GUARD_TARGET_JOB_ID="${CRON_GUARD_TARGET_JOB_ID:-e1e8bb42-bf53-4a6b-925d-47804bcb4d72}"
CRON_PIPELINE_TECH_JOB_ID="${CRON_PIPELINE_TECH_JOB_ID:-b6176298-dced-45f8-8c0f-8c0b3ec0dd98}"
CRON_PIPELINE_PRODUCT_JOB_ID="${CRON_PIPELINE_PRODUCT_JOB_ID:-8cd2277b-f3e2-4bdb-920c-1afa2ecd9fee}"
CRON_PIPELINE_REVIEWER_JOB_ID="${CRON_PIPELINE_REVIEWER_JOB_ID:-23d1c9c1-91a6-4bfa-93fe-34cba20484e4}"
CRON_PIPELINE_QA_JOB_ID="${CRON_PIPELINE_QA_JOB_ID:-2972505e-921d-4182-863d-ef7f048b8374}"
CRON_GUARD_FEISHU_ACCOUNT="${CRON_GUARD_FEISHU_ACCOUNT:-hot-search}"
CRON_GUARD_FEISHU_TARGET="${CRON_GUARD_FEISHU_TARGET:-oc_replace_with_group_id}"
AUTO_MERGE_ENABLED="${AUTO_MERGE_ENABLED:-1}"
AUTO_MERGE_OWNER_REGEX='^owner:(role-senior-dev|role-code-reviewer)$'

trap 'rm -rf "${SYNC_LOCK_DIR}" >/dev/null 2>&1 || true; rm -f "${OPEN_PR_EVIDENCE_FILE}" "${OPEN_PR_EVIDENCE_FILE}.tmp" "${MERGED_PR_EVIDENCE_FILE}" "${MERGED_PR_EVIDENCE_FILE}.tmp" "${COMMIT_EVIDENCE_FILE}" "${COMMIT_EVIDENCE_FILE}.tmp" >/dev/null 2>&1 || true' EXIT

unset ALL_PROXY all_proxy HTTP_PROXY http_proxy HTTPS_PROXY https_proxy

GH_BIN=""
if [ -x /usr/local/bin/gh ]; then
  GH_BIN=/usr/local/bin/gh
elif [ -x /opt/homebrew/bin/gh ]; then
  GH_BIN=/opt/homebrew/bin/gh
elif [ -x /usr/bin/gh ]; then
  GH_BIN=/usr/bin/gh
else
  GH_BIN="$(command -v gh || true)"
fi

OPENCLAW_BIN=""
if [ -x /usr/local/bin/openclaw ]; then
  OPENCLAW_BIN=/usr/local/bin/openclaw
elif [ -x /opt/homebrew/bin/openclaw ]; then
  OPENCLAW_BIN=/opt/homebrew/bin/openclaw
else
  OPENCLAW_BIN="$(command -v openclaw || true)"
fi

log() {
  echo "${LOG_PREFIX} $*" >&2
}

acquire_sync_lock() {
  local old_pid

  if mkdir "${SYNC_LOCK_DIR}" 2>/dev/null; then
    printf '%s\n' "$$" > "${SYNC_LOCK_PID_FILE}"
    return 0
  fi

  old_pid=""
  if [ -r "${SYNC_LOCK_PID_FILE}" ]; then
    old_pid="$(cat "${SYNC_LOCK_PID_FILE}" 2>/dev/null || true)"
  fi

  if [ -n "${old_pid}" ] && ! ps -p "${old_pid}" >/dev/null 2>&1; then
    rm -rf "${SYNC_LOCK_DIR}" >/dev/null 2>&1 || true
    if mkdir "${SYNC_LOCK_DIR}" 2>/dev/null; then
      printf '%s\n' "$$" > "${SYNC_LOCK_PID_FILE}"
      log "recovered stale lock from pid=${old_pid}"
      return 0
    fi
  fi

  log "another issue-sync process is running; skip this tick"
  exit 0
}

humanize_cron_error() {
  local raw="$1"
  if printf '%s' "${raw}" | grep -Fq "Expected ',' or '}' after property value in JSON"; then
    echo "模型工具参数 JSON 不完整（常见于工具调用中断）"
    return 0
  fi
  if printf '%s' "${raw}" | grep -Fq "Unexpected non-whitespace character after JSON"; then
    echo "模型工具参数 JSON 格式异常（响应可能截断）"
    return 0
  fi
  if printf '%s' "${raw}" | grep -Eqi "timed out|timeout"; then
    echo "任务执行超时"
    return 0
  fi
  printf '%s' "${raw}" | tr '\n' ' ' | cut -c1-180
}

send_cron_guard_notice() {
  local text="$1"
  if [ -z "${OPENCLAW_BIN}" ]; then
    log "openclaw not found; skip guard notice"
    return 0
  fi
  set +e
  "${OPENCLAW_BIN}" message send \
    --channel feishu \
    --account "${CRON_GUARD_FEISHU_ACCOUNT}" \
    --target "${CRON_GUARD_FEISHU_TARGET}" \
    --message "${text}" >/dev/null 2>&1
  local rc=$?
  set -e
  if [ "${rc}" -ne 0 ]; then
    log "cron guard notice send failed"
  fi
}

mark_cron_retry_state() {
  local run_at_ms="$1"
  local retry_status="$2"
  local retry_exit="$3"
  local now_ms
  local tmp_file

  now_ms=$(( $(date +%s) * 1000 ))
  mkdir -p "$(dirname "${CRON_GUARD_STATE_FILE}")"
  if [ ! -f "${CRON_GUARD_STATE_FILE}" ]; then
    printf '{"jobRuns":{}}\n' > "${CRON_GUARD_STATE_FILE}"
  fi

  tmp_file="${CRON_GUARD_STATE_FILE}.tmp.$$"
  if ! jq \
    --arg id "${CRON_GUARD_TARGET_JOB_ID}" \
    --arg status "${retry_status}" \
    --argjson runAt "${run_at_ms}" \
    --argjson nowMs "${now_ms}" \
    --argjson exitCode "${retry_exit}" \
    '.jobRuns[$id] = {
      lastRetriedRunAtMs: $runAt,
      lastRetryAtMs: $nowMs,
      lastRetryStatus: $status,
      lastRetryExitCode: $exitCode
    }' "${CRON_GUARD_STATE_FILE}" > "${tmp_file}"; then
    rm -f "${tmp_file}" >/dev/null 2>&1 || true
    log "cron guard state write failed"
    return 0
  fi
  mv "${tmp_file}" "${CRON_GUARD_STATE_FILE}"
}

mark_pipeline_trigger_state() {
  local senior_run_at_ms="$1"
  local tech_status="$2"
  local tech_exit="$3"
  local product_status="$4"
  local product_exit="$5"
  local reviewer_status="$6"
  local reviewer_exit="$7"
  local qa_status="$8"
  local qa_exit="$9"
  local now_ms
  local tmp_file

  now_ms=$(( $(date +%s) * 1000 ))
  mkdir -p "$(dirname "${CRON_GUARD_STATE_FILE}")"
  if [ ! -f "${CRON_GUARD_STATE_FILE}" ]; then
    printf '{"jobRuns":{}}\n' > "${CRON_GUARD_STATE_FILE}"
  fi

  tmp_file="${CRON_GUARD_STATE_FILE}.tmp.$$"
  if ! jq \
    --argjson seniorRunAtMs "${senior_run_at_ms}" \
    --arg techStatus "${tech_status}" \
    --argjson techExit "${tech_exit}" \
    --arg productStatus "${product_status}" \
    --argjson productExit "${product_exit}" \
    --arg reviewerStatus "${reviewer_status}" \
    --argjson reviewerExit "${reviewer_exit}" \
    --arg qaStatus "${qa_status}" \
    --argjson qaExit "${qa_exit}" \
    --argjson nowMs "${now_ms}" \
    '.pipeline = {
      lastTriggeredSeniorRunAtMs: $seniorRunAtMs,
      lastTriggeredAtMs: $nowMs,
      techDirector: {status: $techStatus, exitCode: $techExit},
      product: {status: $productStatus, exitCode: $productExit},
      reviewer: {status: $reviewerStatus, exitCode: $reviewerExit},
      qa: {status: $qaStatus, exitCode: $qaExit}
    }' "${CRON_GUARD_STATE_FILE}" > "${tmp_file}"; then
    rm -f "${tmp_file}" >/dev/null 2>&1 || true
    log "pipeline state write failed"
    return 0
  fi
  mv "${tmp_file}" "${CRON_GUARD_STATE_FILE}"
}

trigger_followup_pipeline_after_senior_dev() {
  local senior_last_run
  local senior_last_status
  local tracked_run
  local tech_rc
  local product_rc
  local reviewer_rc
  local qa_rc
  local tech_status
  local product_status
  local reviewer_status
  local qa_status
  local tech_output
  local product_output
  local reviewer_output
  local qa_output
  local now_text
  local message

  [ -r "${CRON_JOBS_FILE}" ] || return 0
  senior_last_run="$(jq -r --arg id "${CRON_GUARD_TARGET_JOB_ID}" '.jobs[] | select(.id == $id) | .state.lastRunAtMs // 0' "${CRON_JOBS_FILE}" 2>/dev/null || echo "0")"
  senior_last_status="$(jq -r --arg id "${CRON_GUARD_TARGET_JOB_ID}" '.jobs[] | select(.id == $id) | .state.lastRunStatus // ""' "${CRON_JOBS_FILE}" 2>/dev/null || true)"

  [ "${senior_last_run}" -gt 0 ] || return 0
  [ "${senior_last_status}" = "ok" ] || return 0

  tracked_run="0"
  if [ -r "${CRON_GUARD_STATE_FILE}" ]; then
    tracked_run="$(jq -r '.pipeline.lastTriggeredSeniorRunAtMs // 0' "${CRON_GUARD_STATE_FILE}" 2>/dev/null || echo "0")"
  fi
  if [ "${senior_last_run}" -le "${tracked_run}" ]; then
    return 0
  fi

  if [ -z "${OPENCLAW_BIN}" ]; then
    log "openclaw not found; skip pipeline trigger"
    return 0
  fi

  log "pipeline trigger: senior-dev runAt=${senior_last_run}, run tech||product then reviewer->qa"
  local tech_tmp="${TMPDIR:-/tmp}/issue-sync-tech-output.$$.txt"
  local product_tmp="${TMPDIR:-/tmp}/issue-sync-product-output.$$.txt"
  set +e
  (
    "${OPENCLAW_BIN}" cron run "${CRON_PIPELINE_TECH_JOB_ID}" --timeout 60000 2>&1
    printf '%d' "$?" > "${tech_tmp}.rc"
  ) > "${tech_tmp}" 2>&1 &
  local pid_tech=$!
  (
    "${OPENCLAW_BIN}" cron run "${CRON_PIPELINE_PRODUCT_JOB_ID}" --timeout 60000 2>&1
    printf '%d' "$?" > "${product_tmp}.rc"
  ) > "${product_tmp}" 2>&1 &
  local pid_product=$!
  wait "${pid_tech}" "${pid_product}" || true
  tech_output="$(cat "${tech_tmp}" 2>/dev/null || true)"
  tech_rc="$(cat "${tech_tmp}.rc" 2>/dev/null || echo 1)"
  product_output="$(cat "${product_tmp}" 2>/dev/null || true)"
  product_rc="$(cat "${product_tmp}.rc" 2>/dev/null || echo 1)"
  rm -f "${tech_tmp}" "${tech_tmp}.rc" "${product_tmp}" "${product_tmp}.rc" >/dev/null 2>&1 || true
  reviewer_output="$("${OPENCLAW_BIN}" cron run "${CRON_PIPELINE_REVIEWER_JOB_ID}" --timeout 60000 2>&1)"
  reviewer_rc=$?
  qa_output="$("${OPENCLAW_BIN}" cron run "${CRON_PIPELINE_QA_JOB_ID}" --timeout 60000 2>&1)"
  qa_rc=$?
  set -e

  tech_status="$(jq -r --arg id "${CRON_PIPELINE_TECH_JOB_ID}" '.jobs[] | select(.id == $id) | .state.lastRunStatus // "unknown"' "${CRON_JOBS_FILE}" 2>/dev/null || true)"
  product_status="$(jq -r --arg id "${CRON_PIPELINE_PRODUCT_JOB_ID}" '.jobs[] | select(.id == $id) | .state.lastRunStatus // "unknown"' "${CRON_JOBS_FILE}" 2>/dev/null || true)"
  reviewer_status="$(jq -r --arg id "${CRON_PIPELINE_REVIEWER_JOB_ID}" '.jobs[] | select(.id == $id) | .state.lastRunStatus // "unknown"' "${CRON_JOBS_FILE}" 2>/dev/null || true)"
  qa_status="$(jq -r --arg id "${CRON_PIPELINE_QA_JOB_ID}" '.jobs[] | select(.id == $id) | .state.lastRunStatus // "unknown"' "${CRON_JOBS_FILE}" 2>/dev/null || true)"
  [ -n "${tech_status}" ] || tech_status="unknown"
  [ -n "${product_status}" ] || product_status="unknown"
  [ -n "${reviewer_status}" ] || reviewer_status="unknown"
  [ -n "${qa_status}" ] || qa_status="unknown"

  mark_pipeline_trigger_state "${senior_last_run}" "${tech_status}" "${tech_rc}" "${product_status}" "${product_rc}" "${reviewer_status}" "${reviewer_rc}" "${qa_status}" "${qa_rc}"

  now_text="$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S')"
  if [ "${tech_status}" = "ok" ] && [ "${product_status}" = "ok" ] && [ "${reviewer_status}" = "ok" ] && [ "${qa_status}" = "ok" ]; then
    message=$'【流水线调度】自动调度触发成功\n- 上游：高级程序员已完成新一轮执行\n- 下游：技术总监='"${tech_status}"$'，产品经理='"${product_status}"$'，Reviewer='"${reviewer_status}"$'，测试='"${qa_status}"$'\n- 时间：'"${now_text}"
    send_cron_guard_notice "${message}"
    return 0
  fi

  message=$'【流水线调度】自动调度触发异常\n- 上游：高级程序员已完成新一轮执行\n- 下游：技术总监='"${tech_status}"$' (exit='"${tech_rc}"$')，产品经理='"${product_status}"$' (exit='"${product_rc}"$')，Reviewer='"${reviewer_status}"$' (exit='"${reviewer_rc}"$')，测试='"${qa_status}"$' (exit='"${qa_rc}"$')\n- 时间：'"${now_text}"$'\n- 技术总监日志：'"$(humanize_cron_error "${tech_output}")"$'\n- 产品经理日志：'"$(humanize_cron_error "${product_output}")"$'\n- Reviewer日志：'"$(humanize_cron_error "${reviewer_output}")"$'\n- 测试日志：'"$(humanize_cron_error "${qa_output}")"
  send_cron_guard_notice "${message}"
  return 0
}

guard_retry_json_parse_error() {
  local job_json
  local job_name
  local last_status
  local last_error
  local last_run_at
  local retried_run_at
  local retry_output
  local retry_rc
  local new_status
  local new_error
  local now_text
  local humanized
  local new_humanized
  local message

  [ -r "${CRON_JOBS_FILE}" ] || return 0
  job_json="$(jq -c --arg id "${CRON_GUARD_TARGET_JOB_ID}" '.jobs[] | select(.id == $id)' "${CRON_JOBS_FILE}" 2>/dev/null | head -n1 || true)"
  [ -n "${job_json}" ] || return 0

  job_name="$(printf '%s' "${job_json}" | jq -r '.name // "未知任务"')"
  last_status="$(printf '%s' "${job_json}" | jq -r '.state.lastRunStatus // empty')"
  last_error="$(printf '%s' "${job_json}" | jq -r '.state.lastError // empty')"
  last_run_at="$(printf '%s' "${job_json}" | jq -r '.state.lastRunAtMs // 0')"

  if [ "${last_status}" != "error" ]; then
    return 0
  fi
  if ! printf '%s' "${last_error}" | grep -Eq "Expected ',' or '}' after property value in JSON|Unexpected non-whitespace character after JSON"; then
    return 0
  fi

  retried_run_at="0"
  if [ -r "${CRON_GUARD_STATE_FILE}" ]; then
    retried_run_at="$(jq -r --arg id "${CRON_GUARD_TARGET_JOB_ID}" '.jobRuns[$id].lastRetriedRunAtMs // 0' "${CRON_GUARD_STATE_FILE}" 2>/dev/null || echo "0")"
  fi
  if [ "${retried_run_at}" = "${last_run_at}" ]; then
    log "cron guard skip retry (already retried runAt=${last_run_at})"
    return 0
  fi

  if [ -z "${OPENCLAW_BIN}" ]; then
    log "openclaw not found; skip retry guard"
    return 0
  fi

  log "cron guard retry once for ${job_name} (runAt=${last_run_at})"
  set +e
  retry_output="$("${OPENCLAW_BIN}" cron run "${CRON_GUARD_TARGET_JOB_ID}" --expect-final --timeout 180000 2>&1)"
  retry_rc=$?
  set -e

  new_status="$(jq -r --arg id "${CRON_GUARD_TARGET_JOB_ID}" '.jobs[] | select(.id == $id) | .state.lastRunStatus // "unknown"' "${CRON_JOBS_FILE}" 2>/dev/null || true)"
  new_error="$(jq -r --arg id "${CRON_GUARD_TARGET_JOB_ID}" '.jobs[] | select(.id == $id) | .state.lastError // ""' "${CRON_JOBS_FILE}" 2>/dev/null || true)"
  [ -n "${new_status}" ] || new_status="unknown"
  mark_cron_retry_state "${last_run_at}" "${new_status}" "${retry_rc}"

  now_text="$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S')"
  humanized="$(humanize_cron_error "${last_error}")"

  if [ "${new_status}" = "ok" ]; then
    message=$'【任务守护】自动恢复成功\n- 任务：'"${job_name}"$'\n- 原因：'"${humanized}"$'\n- 处理：系统已自动重试 1 次，任务恢复正常\n- 时间：'"${now_text}"
    send_cron_guard_notice "${message}"
    log "cron guard recovered ${job_name}"
    return 0
  fi

  new_humanized="$(humanize_cron_error "${new_error:-${retry_output}}")"
  message=$'【任务守护】自动重试失败\n- 任务：'"${job_name}"$'\n- 原因：'"${humanized}"$'\n- 结果：已自动重试 1 次，仍失败\n- 当前错误：'"${new_humanized}"$'\n- 时间：'"${now_text}"$'\n- 建议：请人工执行 `openclaw cron run '"${CRON_GUARD_TARGET_JOB_ID}"' --expect-final` 复核'
  send_cron_guard_notice "${message}"
  log "cron guard retry failed for ${job_name}: ${new_humanized}"
  return 0
}

gh_retry() {
  local attempt=1
  local output
  local rc

  while true; do
    set +e
    output="$("${GH_BIN}" "$@" 2>&1)"
    rc=$?
    set -e
    if [ "${rc}" -eq 0 ]; then
      printf '%s' "${output}"
      return 0
    fi

    if [ "${attempt}" -ge "${MAX_RETRIES}" ]; then
      printf '%s\n' "${output}" >&2
      return "${rc}"
    fi

    log "retry ${attempt}/${MAX_RETRIES} for gh $*"
    sleep $((RETRY_DELAY * attempt))
    attempt=$((attempt + 1))
  done
}

business_day_offset() {
  local start_date="$1"
  local offset="$2"
  /usr/bin/python3 - "$start_date" "$offset" <<'PY'
from datetime import datetime, timedelta
import sys

current = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
remaining = int(sys.argv[2])
while remaining > 0:
    current += timedelta(days=1)
    if current.weekday() < 5:
        remaining -= 1
print(current.isoformat())
PY
}

acquire_sync_lock
guard_retry_json_parse_error || true
trigger_followup_pipeline_after_senior_dev || true

if [ -z "${GH_BIN}" ]; then
  log "gh not found in PATH"
  exit 1
fi

if [ ! -d "${REPO_DIR}/.git" ]; then
  log "repo not found: ${REPO_DIR}"
  exit 1
fi

if [ -z "${GH_TOKEN:-}" ] && [ -r "${OPENCLAW_CONFIG}" ]; then
  GH_TOKEN="$(jq -r '.skills.entries["gh-issues"].apiKey // empty' "${OPENCLAW_CONFIG}" 2>/dev/null || true)"
fi
if [ -n "${GH_TOKEN:-}" ]; then
  export GH_TOKEN
  export GITHUB_TOKEN="${GH_TOKEN}"
fi

if [ -n "${GH_TOKEN:-}" ]; then
  if ! gh_retry api user --jq '.login' >/dev/null; then
    log "GH_TOKEN invalid in ${OPENCLAW_CONFIG}. Please update skills.entries[\"gh-issues\"].apiKey"
    exit 1
  fi
else
  if ! gh_retry auth status >/dev/null; then
    log "gh auth invalid and GH_TOKEN missing; run gh auth login or configure gh-issues apiKey"
    exit 1
  fi
fi

cd "${REPO_DIR}"

TODAY_CST="$(TZ=Asia/Shanghai date '+%Y-%m-%d')"
DUE_1="$(business_day_offset "${TODAY_CST}" 1)"
DUE_2="$(business_day_offset "${TODAY_CST}" 2)"
DUE_3="$(business_day_offset "${TODAY_CST}" 3)"
DUE_4="$(business_day_offset "${TODAY_CST}" 4)"
DUE_5="$(business_day_offset "${TODAY_CST}" 5)"
CURRENT_WEEK="$(TZ=Asia/Shanghai date '+%V' | sed 's/^0//')"
[ -n "${CURRENT_WEEK}" ] || CURRENT_WEEK="1"
[ -n "${SPRINT_LABEL}" ] || SPRINT_LABEL="sprint:w${CURRENT_WEEK}"
[ -n "${SPRINT_NAME}" ] || SPRINT_NAME="W${CURRENT_WEEK} 冲刺"
[ -n "${MILESTONE_TITLE}" ] || MILESTONE_TITLE="MVP Sprint W${CURRENT_WEEK}"
if [ -n "${MILESTONE_DUE}" ]; then
  MILESTONE_DUE_DATE="${MILESTONE_DUE%%T*}"
  [ -n "${MILESTONE_DUE_DATE}" ] || MILESTONE_DUE_DATE="${TODAY_CST}"
else
  MILESTONE_DUE_DATE="$(business_day_offset "${TODAY_CST}" 6)"
  MILESTONE_DUE="${MILESTONE_DUE_DATE}T00:00:00Z"
fi

ensure_label() {
  local name="$1"
  local color="$2"
  local desc="$3"
  gh_retry label create "${name}" --repo "${REPO}" --color "${color}" --description "${desc}" --force >/dev/null
}

ensure_labels() {
  ensure_label "priority:p0" "B60205" "最高优先级"
  ensure_label "priority:p1" "D93F0B" "高优先级"
  ensure_label "status:todo" "0E8A16" "待开始"
  ensure_label "status:doing" "FBCA04" "进行中"
  ensure_label "status:blocked" "B60205" "阻塞中"
  ensure_label "status:done" "1A7F37" "已完成"
  ensure_label "${SPRINT_LABEL}" "1D76DB" "${SPRINT_NAME}"
  ensure_label "owner:role-senior-dev" "5319E7" "负责人：高级程序员"
  ensure_label "owner:role-product" "FBCA04" "负责人：产品经理"
  ensure_label "owner:role-qa-test" "C2E0C6" "负责人：测试"
  ensure_label "owner:role-code-reviewer" "0052CC" "负责人：代码评审"
  ensure_label "owner:role-tech-director" "0366D6" "负责人：技术总监"
}

ensure_milestone() {
  local num
  num="$(gh_retry api "repos/${REPO}/milestones?state=all&per_page=100" --jq ".[] | select(.title == \"${MILESTONE_TITLE}\") | .number" | head -n1 || true)"
  if [ -z "${num}" ]; then
    num="$(gh_retry api -X POST "repos/${REPO}/milestones" -f title="${MILESTONE_TITLE}" -f due_on="${MILESTONE_DUE}" -f description="${MILESTONE_DESC}" --jq '.number')"
    log "created milestone #${num} ${MILESTONE_TITLE}"
  else
    gh_retry api -X PATCH "repos/${REPO}/milestones/${num}" -f due_on="${MILESTONE_DUE}" -f description="${MILESTONE_DESC}" >/dev/null
    log "milestone synced #${num} ${MILESTONE_TITLE} due=${MILESTONE_DUE_DATE}"
  fi
}

find_issue_number_by_title() {
  local title="$1"
  gh_retry issue list --repo "${REPO}" --state all --limit 200 --json number,title --jq ".[] | select(.title == \"${title}\") | .number" | head -n1 || true
}

ensure_issue() {
  local title="$1"
  local body="$2"
  local number

  number="$(find_issue_number_by_title "${title}")"
  if [ -z "${number}" ]; then
    gh_retry issue create --repo "${REPO}" --title "${title}" --body "${body}" >/dev/null
    number="$(find_issue_number_by_title "${title}")"
    log "created #${number} ${title}"
  else
    log "exists #${number} ${title}"
  fi
  echo "${number}"
}

ensure_status_label() {
  local number="$1"
  local statuses
  statuses="$(gh_retry issue view "${number}" --repo "${REPO}" --json labels --jq '[.labels[].name | select(startswith("status:"))] | join(",")')"
  if [ -z "${statuses}" ]; then
    gh_retry issue edit "${number}" --repo "${REPO}" --add-label "status:todo" >/dev/null
    log "issue #${number} add default status:todo"
  fi
}

get_issue_status_labels() {
  local number="$1"
  gh_retry issue view "${number}" --repo "${REPO}" --json labels --jq '[.labels[].name | select(startswith("status:"))] | join(",")'
}

set_issue_status_label() {
  local number="$1"
  local target="$2"
  local current
  local first

  current="$(get_issue_status_labels "${number}")"
  if [ -n "${current}" ]; then
    first="${current%%,*}"
    if [ "${first}" = "${target}" ] && [ "${current}" = "${first}" ]; then
      return 0
    fi
    gh_retry issue edit "${number}" --repo "${REPO}" --remove-label "${current}" >/dev/null
  fi

  gh_retry issue edit "${number}" --repo "${REPO}" --add-label "${target}" >/dev/null
  log "issue #${number} status -> ${target}"
}

issue_has_open_pr_reference() {
  local number="$1"
  [ -n "${OPEN_PR_ISSUE_LIST}" ] && echo "${OPEN_PR_ISSUE_LIST}" | tr ' ' '\n' | grep -qx "${number}"
}

issue_has_merged_pr_reference() {
  local number="$1"
  [ -n "${MERGED_PR_ISSUE_LIST}" ] && echo "${MERGED_PR_ISSUE_LIST}" | tr ' ' '\n' | grep -qx "${number}"
}

get_open_pr_evidence_line() {
  local number="$1"
  [ -s "${OPEN_PR_EVIDENCE_FILE}" ] || return 1
  grep -E "^${number}\|" "${OPEN_PR_EVIDENCE_FILE}" | head -n1 || true
}

get_latest_open_pr_marker() {
  local number="$1"
  gh_retry issue view "${number}" --repo "${REPO}" --json comments --jq '.comments[].body' \
    | (grep -Eo '\[AUTO-STATUS\] open-pr-[0-9]+' || true) \
    | sed 's/\[AUTO-STATUS\] //' \
    | tail -n1
}

get_merged_pr_evidence_line() {
  local number="$1"
  [ -s "${MERGED_PR_EVIDENCE_FILE}" ] || return 1
  grep -E "^${number}\|" "${MERGED_PR_EVIDENCE_FILE}" | head -n1 || true
}

issue_has_commit_reference() {
  local number="$1"
  [ -n "${COMMIT_ISSUE_LIST}" ] && echo "${COMMIT_ISSUE_LIST}" | tr ' ' '\n' | grep -qx "${number}"
}

get_commit_evidence_line() {
  local number="$1"
  [ -s "${COMMIT_EVIDENCE_FILE}" ] || return 1
  grep -E "^${number}\|" "${COMMIT_EVIDENCE_FILE}" | head -n1 || true
}

issue_has_non_code_evidence() {
  local number="$1"
  local has
  has="$(gh_retry issue view "${number}" --repo "${REPO}" --json comments --jq '[.comments[].body | startswith("[NON-CODE-EVIDENCE]")] | any')"
  [ "${has}" = "true" ]
}

get_non_code_evidence_line() {
  local number="$1"
  gh_retry issue view "${number}" --repo "${REPO}" --json comments --jq '[.comments[].body | select(startswith("[NON-CODE-EVIDENCE]"))] | .[-1] // ""'
}

build_open_pr_issue_map() {
  local lines
  local rc
  local pr_num
  local pr_url
  local pr_title
  local pr_body
  local refs
  local issue

  : > "${OPEN_PR_EVIDENCE_FILE}"
  set +e
  lines="$(gh_retry search prs "repo:${REPO}" --state open --limit 100 --json number,url,title,body --jq '.[] | [.number, .url, .title, (.body // "")] | @tsv')"
  rc=$?
  set -e

  if [ "${rc}" -ne 0 ]; then
    OPEN_PR_ISSUE_LIST=""
    log "open PR issue refs fetch failed, fallback to none"
    return 0
  fi

  while IFS=$'\t' read -r pr_num pr_url pr_title pr_body; do
    [ -z "${pr_num}" ] && continue
    refs="$(printf '%s\n%s\n' "${pr_title}" "${pr_body}" | (grep -Eo '#[0-9]+' || true) | tr -d '#' | sort -n | uniq)"
    for issue in ${refs}; do
      printf '%s|%s|%s|%s\n' "${issue}" "${pr_num}" "${pr_url}" "${pr_title}" >> "${OPEN_PR_EVIDENCE_FILE}"
    done
  done <<EOF
${lines}
EOF

  if [ -s "${OPEN_PR_EVIDENCE_FILE}" ]; then
    sort -t'|' -k1,1n -k2,2n "${OPEN_PR_EVIDENCE_FILE}" | awk -F'|' '{m[$1]=$0} END{for (i in m) print m[i]}' > "${OPEN_PR_EVIDENCE_FILE}.tmp"
    mv "${OPEN_PR_EVIDENCE_FILE}.tmp" "${OPEN_PR_EVIDENCE_FILE}"
    OPEN_PR_ISSUE_LIST="$(cut -d'|' -f1 "${OPEN_PR_EVIDENCE_FILE}" | sort -n | tr '\n' ' ')"
  else
    OPEN_PR_ISSUE_LIST=""
  fi

  log "open PR issue refs: ${OPEN_PR_ISSUE_LIST:-none}"
}

build_merged_pr_issue_map() {
  local lines
  local rc
  local pr_num
  local pr_url
  local pr_title
  local pr_body
  local refs
  local issue

  : > "${MERGED_PR_EVIDENCE_FILE}"
  set +e
  lines="$(gh_retry search prs "repo:${REPO}" --state closed --merged --limit 100 --json number,url,title,body --jq '.[] | [.number, .url, .title, (.body // "")] | @tsv')"
  rc=$?
  set -e

  if [ "${rc}" -ne 0 ]; then
    MERGED_PR_ISSUE_LIST=""
    log "merged PR issue refs fetch failed, fallback to none"
    return 0
  fi

  while IFS=$'\t' read -r pr_num pr_url pr_title pr_body; do
    [ -z "${pr_num}" ] && continue
    refs="$(printf '%s\n%s\n' "${pr_title}" "${pr_body}" | (grep -Eo '#[0-9]+' || true) | tr -d '#' | sort -n | uniq)"
    for issue in ${refs}; do
      printf '%s|%s|%s|%s\n' "${issue}" "${pr_num}" "${pr_url}" "${pr_title}" >> "${MERGED_PR_EVIDENCE_FILE}"
    done
  done <<EOF
${lines}
EOF

  if [ -s "${MERGED_PR_EVIDENCE_FILE}" ]; then
    sort -t'|' -k1,1n -k2,2n "${MERGED_PR_EVIDENCE_FILE}" | awk -F'|' '{m[$1]=$0} END{for (i in m) print m[i]}' > "${MERGED_PR_EVIDENCE_FILE}.tmp"
    mv "${MERGED_PR_EVIDENCE_FILE}.tmp" "${MERGED_PR_EVIDENCE_FILE}"
    MERGED_PR_ISSUE_LIST="$(cut -d'|' -f1 "${MERGED_PR_EVIDENCE_FILE}" | sort -n | tr '\n' ' ')"
  else
    MERGED_PR_ISSUE_LIST=""
  fi

  log "merged PR issue refs: ${MERGED_PR_ISSUE_LIST:-none}"
}

build_commit_issue_map() {
  local lines
  local rc
  local sha
  local url
  local message
  local refs
  local issue

  : > "${COMMIT_EVIDENCE_FILE}"
  set +e
  lines="$(gh_retry api "repos/${REPO}/commits?per_page=100" --jq '.[] | [(.sha[0:7]), (.html_url // ""), (.commit.message // "")] | @tsv')"
  rc=$?
  set -e

  if [ "${rc}" -ne 0 ]; then
    COMMIT_ISSUE_LIST=""
    log "commit issue refs fetch failed, fallback to none"
    return 0
  fi

  while IFS=$'\t' read -r sha url message; do
    [ -z "${sha}" ] && continue
    refs="$(printf '%s\n' "${message}" | (grep -Eo '#[0-9]+' || true) | tr -d '#' | sort -n | uniq)"
    for issue in ${refs}; do
      printf '%s|%s|%s|%s\n' "${issue}" "${sha}" "${url}" "${message}" >> "${COMMIT_EVIDENCE_FILE}"
    done
  done <<EOF
${lines}
EOF

  if [ -s "${COMMIT_EVIDENCE_FILE}" ]; then
    awk -F'|' '!seen[$1]++ {print $0}' "${COMMIT_EVIDENCE_FILE}" > "${COMMIT_EVIDENCE_FILE}.tmp"
    mv "${COMMIT_EVIDENCE_FILE}.tmp" "${COMMIT_EVIDENCE_FILE}"
    COMMIT_ISSUE_LIST="$(cut -d'|' -f1 "${COMMIT_EVIDENCE_FILE}" | sort -n | tr '\n' ' ')"
  else
    COMMIT_ISSUE_LIST=""
  fi

  log "commit issue refs: ${COMMIT_ISSUE_LIST:-none}"
}

auto_merge_ready_prs() {
  local lines
  local rc
  local pr_num
  local pr_url
  local pr_title
  local pr_body
  local pr_draft
  local merge_state
  local review_decision
  local refs
  local issue
  local issue_state
  local issue_labels
  local eligible_issue
  local merge_rc
  local merge_out
  local marker
  local exists
  local body
  local merged_count=0
  local merged_notice_lines=""
  local now_text
  local notice

  if [ "${AUTO_MERGE_ENABLED}" != "1" ]; then
    log "auto-merge disabled via AUTO_MERGE_ENABLED=${AUTO_MERGE_ENABLED}"
    return 0
  fi

  set +e
  lines="$(gh_retry pr list --repo "${REPO}" --state open --limit 50 --json number,url,title,body,isDraft,mergeStateStatus,reviewDecision --jq '.[] | [.number, .url, .title, (.body // ""), (.isDraft|tostring), (.mergeStateStatus // ""), (.reviewDecision // "")] | @tsv')"
  rc=$?
  set -e
  if [ "${rc}" -ne 0 ]; then
    log "auto-merge: failed to fetch open PR list"
    return 0
  fi

  while IFS=$'\t' read -r pr_num pr_url pr_title pr_body pr_draft merge_state review_decision; do
    [ -n "${pr_num}" ] || continue

    if [ "${pr_draft}" = "true" ]; then
      log "auto-merge: skip PR #${pr_num} (draft)"
      continue
    fi

    if [ "${review_decision}" = "CHANGES_REQUESTED" ]; then
      log "auto-merge: skip PR #${pr_num} (changes requested)"
      continue
    fi

    if [ "${merge_state}" != "CLEAN" ]; then
      log "auto-merge: skip PR #${pr_num} (merge_state=${merge_state:-unknown})"
      continue
    fi

    refs="$(printf '%s\n%s\n' "${pr_title}" "${pr_body}" | (grep -Eo '#[0-9]+' || true) | tr -d '#' | sort -n | uniq)"
    if [ -z "${refs}" ]; then
      log "auto-merge: skip PR #${pr_num} (no issue refs)"
      continue
    fi

    eligible_issue=""
    for issue in ${refs}; do
      issue_state="$(gh_retry issue view "${issue}" --repo "${REPO}" --json state --jq '.state | ascii_downcase' || true)"
      [ "${issue_state}" = "open" ] || continue

      issue_labels="$(gh_retry issue view "${issue}" --repo "${REPO}" --json labels --jq '[.labels[].name] | join(",")' || true)"
      [ -n "${issue_labels}" ] || continue

      if ! echo "${issue_labels}" | tr ',' '\n' | grep -Eq "${AUTO_MERGE_OWNER_REGEX}"; then
        continue
      fi

      if ! echo "${issue_labels}" | tr ',' '\n' | grep -Eq '^priority:p0$|^priority:p1$'; then
        continue
      fi

      if echo "${issue_labels}" | tr ',' '\n' | grep -qx "status:done"; then
        continue
      fi

      eligible_issue="${issue}"
      break
    done

    if [ -z "${eligible_issue}" ]; then
      log "auto-merge: skip PR #${pr_num} (no eligible linked issue)"
      continue
    fi

    set +e
    merge_out="$(gh_retry pr merge "${pr_num}" --repo "${REPO}" --squash --delete-branch 2>&1)"
    merge_rc=$?
    set -e

    if [ "${merge_rc}" -ne 0 ]; then
      log "auto-merge: PR #${pr_num} merge failed: $(printf '%s' "${merge_out}" | tr '\n' ' ' | cut -c1-180)"
      continue
    fi

    marker="auto-merge-pr-${pr_num}"
    exists="$(gh_retry issue view "${eligible_issue}" --repo "${REPO}" --json comments --jq "[.comments[].body | contains(\"[AUTO-MERGE] ${marker}\")] | any" || echo "false")"
    if [ "${exists}" != "true" ]; then
      body=$'[AUTO-MERGE] '"${marker}"$'\n- Action: squash merge completed\n- PR: #'"${pr_num}"$' '"${pr_url}"$'\n- Trigger: issue-sync auto merge policy\n- SyncedAt: '"$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S %Z')"
      gh_retry issue comment "${eligible_issue}" --repo "${REPO}" --body "${body}" >/dev/null
    fi

    merged_count=$((merged_count + 1))
    merged_notice_lines+=$'\n'"- PR #${pr_num} -> Issue #${eligible_issue}: ${pr_url}"
    log "auto-merge: merged PR #${pr_num} linked issue #${eligible_issue}"
  done <<EOF
${lines}
EOF

  if [ "${merged_count}" -gt 0 ]; then
    now_text="$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S')"
    notice=$'【自动合并通知】\n- 仓库：'"${REPO}"$'\n- 本轮自动合并：'"${merged_count}"$' 个'"${merged_notice_lines}"$'\n- 时间：'"${now_text}"
    send_cron_guard_notice "${notice}"
  fi

  log "auto-merge: merged_count=${merged_count}"
}

ensure_status_evidence_comment() {
  local number="$1"
  local marker="$2"
  local from_status="$3"
  local to_status="$4"
  local reason="$5"
  local evidence="$6"
  local evidence_type="$7"
  local evidence_url="$8"
  local exists
  local ts
  local issue_url
  local evidence_json
  local body

  exists="$(gh_retry issue view "${number}" --repo "${REPO}" --json comments --jq "[.comments[].body | contains(\"[AUTO-STATUS] ${marker}\")] | any")"
  if [ "${exists}" = "true" ]; then
    return 0
  fi

  issue_url="https://github.com/${REPO}/issues/${number}"
  [ -n "${evidence_type}" ] || evidence_type="issue"
  [ -n "${evidence_url}" ] || evidence_url="${issue_url}"
  ts="$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S %Z')"
  evidence_json="$(jq -cn \
    --arg issueUrl "${issue_url}" \
    --arg evidenceType "${evidence_type}" \
    --arg evidenceUrl "${evidence_url}" \
    --arg syncedAt "${ts}" \
    '{issueUrl: $issueUrl, evidenceType: $evidenceType, evidenceUrl: $evidenceUrl, syncedAt: $syncedAt}')"
  body=$'[AUTO-STATUS] '"${marker}"$'\n- Transition: '"${from_status}"$' -> '"${to_status}"$'\n- Reason: '"${reason}"$'\n- Evidence: '"${evidence}"$'\n- EvidenceType: '"${evidence_type}"$'\n- EvidenceURL: '"${evidence_url}"$'\n- IssueURL: '"${issue_url}"$'\n- SyncedAt: '"${ts}"$'\n[AUTO-EVIDENCE] '"${evidence_json}"
  gh_retry issue comment "${number}" --repo "${REPO}" --body "${body}" >/dev/null
  log "issue #${number} status-evidence comment added (${marker})"
}

auto_reconcile_issue_status() {
  local number="$1"
  local issue_state
  local priority_labels
  local owner_labels
  local non_code_mode
  local non_code_evidence_body
  local current_statuses
  local current_primary
  local target
  local reason
  local evidence
  local evidence_type
  local evidence_url
  local issue_url
  local marker
  local merged_line
  local merged_issue
  local merged_pr_num
  local merged_pr_url
  local merged_pr_title
  local open_line
  local open_issue
  local open_pr_num
  local open_pr_url
  local open_pr_title
  local commit_line
  local commit_issue
  local commit_sha
  local commit_url
  local commit_message
  local latest_open_marker
  local rollback_marker

  issue_state="$(gh_retry issue view "${number}" --repo "${REPO}" --json state --jq '.state | ascii_downcase')"
  priority_labels="$(gh_retry issue view "${number}" --repo "${REPO}" --json labels --jq '[.labels[].name | select(startswith("priority:"))] | join(",")')"
  owner_labels="$(gh_retry issue view "${number}" --repo "${REPO}" --json labels --jq '[.labels[].name | select(startswith("owner:"))] | join(",")')"
  non_code_mode="false"
  if ! echo "${owner_labels}" | tr ',' '\n' | grep -qx "owner:role-senior-dev" \
    && echo "${owner_labels}" | tr ',' '\n' | grep -Eq 'owner:role-product|owner:role-qa-test|owner:role-code-reviewer'; then
    non_code_mode="true"
  fi
  non_code_evidence_body=""
  current_statuses="$(get_issue_status_labels "${number}")"
  current_primary="${current_statuses%%,*}"
  reason=""
  evidence=""
  evidence_type="issue"
  issue_url="https://github.com/${REPO}/issues/${number}"
  evidence_url="${issue_url}"
  marker=""

  if [ "${issue_state}" = "closed" ] || issue_has_merged_pr_reference "${number}"; then
    target="status:done"
    if [ "${issue_state}" = "closed" ]; then
      reason="issue state is closed"
      evidence="issue state=closed"
      evidence_type="issue"
      evidence_url="${issue_url}"
      marker="issue-closed"
    else
      merged_line="$(get_merged_pr_evidence_line "${number}")"
      if [ -n "${merged_line}" ]; then
        IFS='|' read -r merged_issue merged_pr_num merged_pr_url merged_pr_title <<EOF
${merged_line}
EOF
      fi
      reason="detected merged PR reference"
      evidence="pr #${merged_pr_num:-unknown} ${merged_pr_url:-}"
      evidence_type="pr"
      evidence_url="${merged_pr_url:-${issue_url}}"
      marker="merged-pr-${merged_pr_num:-unknown}"
    fi
  elif echo "${current_statuses}" | grep -Fq "status:blocked"; then
    target="status:blocked"
    reason="issue explicitly labeled as blocked"
    evidence="status label contains status:blocked"
    evidence_type="issue"
    evidence_url="${issue_url}"
    marker="blocked-label"
  elif issue_has_open_pr_reference "${number}"; then
    target="status:doing"
    open_line="$(get_open_pr_evidence_line "${number}")"
    if [ -n "${open_line}" ]; then
      IFS='|' read -r open_issue open_pr_num open_pr_url open_pr_title <<EOF
${open_line}
EOF
    fi
    reason="detected open PR reference"
    evidence="pr #${open_pr_num:-unknown} ${open_pr_url:-}"
    evidence_type="pr"
    evidence_url="${open_pr_url:-${issue_url}}"
    marker="open-pr-${open_pr_num:-unknown}"
  elif issue_has_commit_reference "${number}"; then
    target="status:doing"
    commit_line="$(get_commit_evidence_line "${number}")"
    if [ -n "${commit_line}" ]; then
      IFS='|' read -r commit_issue commit_sha commit_url commit_message <<EOF
${commit_line}
EOF
    fi
    reason="detected commit reference"
    evidence="commit ${commit_sha:-unknown} ${commit_url:-}"
    evidence_type="commit"
    evidence_url="${commit_url:-${issue_url}}"
    marker="commit-ref-${commit_sha:-unknown}"
  elif [ "${non_code_mode}" = "true" ]; then
    if issue_has_non_code_evidence "${number}"; then
      target="status:doing"
      non_code_evidence_body="$(get_non_code_evidence_line "${number}")"
      reason="detected non-code evidence marker"
      evidence="$(printf '%s' "${non_code_evidence_body}" | tr '\n' ' ' | cut -c1-160)"
      evidence_type="comment"
      evidence_url="${issue_url}"
      marker="non-code-evidence"
    else
      target="status:todo"
      reason="non-code issue without evidence marker"
      evidence="missing [NON-CODE-EVIDENCE] comment"
      evidence_type="comment"
      evidence_url="${issue_url}"
      marker="non-code-no-evidence"
    fi
  elif echo "${priority_labels}" | grep -Eq 'priority:p0|priority:p1'; then
    target="status:todo"
    reason="high-priority issue without execution evidence"
    evidence="labels=${priority_labels}; missing open-pr/commit-ref"
    evidence_type="issue"
    evidence_url="${issue_url}"
    marker="priority-no-evidence"
  else
    target="status:todo"
  fi

  if [ "${current_primary}" = "status:doing" ] && [ "${target}" = "status:todo" ]; then
    if echo "${owner_labels}" | tr ',' '\n' | grep -qx "owner:role-senior-dev"; then
      reason="senior-dev issue has no open PR/commit evidence"
      evidence="previous status=doing; no execution evidence"
      evidence_type="issue"
      evidence_url="${issue_url}"
      marker="no-exec-evidence"
    elif [ "${non_code_mode}" = "true" ]; then
      reason="non-code issue has no [NON-CODE-EVIDENCE] marker"
      evidence="previous status=doing; missing [NON-CODE-EVIDENCE]"
      evidence_type="comment"
      evidence_url="${issue_url}"
      marker="no-non-code-evidence"
    else
      target="status:doing"
      reason="anti-regression: keep doing unless blocked/done evidence appears"
      evidence="previous status=doing"
      evidence_type="issue"
      evidence_url="${issue_url}"
      marker="anti-regression-keep-doing"
    fi
  fi

  if [ "${current_primary}" != "${target}" ] || [ "${current_statuses}" != "${current_primary}" ]; then
    set_issue_status_label "${number}" "${target}"
  fi

  if [ "${target}" = "status:todo" ]; then
    latest_open_marker="$(get_latest_open_pr_marker "${number}")"
    if [ -n "${latest_open_marker}" ] && ! issue_has_open_pr_reference "${number}"; then
      rollback_marker="rollback-${latest_open_marker}"
      ensure_status_evidence_comment \
        "${number}" \
        "${rollback_marker}" \
        "${current_primary:-status:none}" \
        "${target}" \
        "open PR reference disappeared (closed/unlinked), rollback to todo" \
        "last seen ${latest_open_marker}" \
        "pr" \
        "${issue_url}"
    fi
  fi

  if [ -n "${marker}" ]; then
    ensure_status_evidence_comment \
      "${number}" \
      "${marker}" \
      "${current_primary:-status:none}" \
      "${target}" \
      "${reason}" \
      "${evidence}" \
      "${evidence_type}" \
      "${evidence_url}"
  fi
}

ensure_schedule_comment() {
  local number="$1"
  local schedule_body="$2"
  local latest_schedule
  latest_schedule="$(gh_retry issue view "${number}" --repo "${REPO}" --json comments --jq '[.comments[].body | select(startswith("[SCHEDULE]"))] | .[-1] // ""')"
  if [ "${latest_schedule}" != "${schedule_body}" ]; then
    gh_retry issue comment "${number}" --repo "${REPO}" --body "${schedule_body}" >/dev/null
    log "issue #${number} schedule comment synced"
  fi
}

close_done_issue_if_open() {
  local number="$1"
  local issue_state
  local statuses
  local ts
  local body

  issue_state="$(gh_retry issue view "${number}" --repo "${REPO}" --json state --jq '.state | ascii_downcase')"
  statuses="$(get_issue_status_labels "${number}")"
  if [ "${issue_state}" = "open" ] && echo "${statuses}" | tr ',' '\n' | grep -qx "status:done"; then
    ts="$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S %Z')"
    body=$'[AUTO-STATUS] close-done\n- Reason: status label is done and PR evidence merged\n- SyncedAt: '"${ts}"
    gh_retry issue close "${number}" --repo "${REPO}" --comment "${body}" >/dev/null
    log "issue #${number} auto-closed because status:done"
  fi
}

reconcile_all_owner_issues() {
  local rows
  local number
  local labels
  local count=0

  rows="$(gh_retry issue list --repo "${REPO}" --state all --limit 200 --json number,labels --jq '.[] | [.number, ([.labels[].name] | join(","))] | @tsv')"
  [ -n "${rows}" ] || return 0

  while IFS=$'\t' read -r number labels; do
    [ -n "${number}" ] || continue
    if ! echo "${labels}" | tr ',' '\n' | grep -Eq '^owner:'; then
      continue
    fi

    ensure_status_label "${number}"
    auto_reconcile_issue_status "${number}"
    close_done_issue_if_open "${number}"
    count=$((count + 1))
  done <<EOF
${rows}
EOF

  log "reconciled owner issues count=${count}"
}

sync_issue_metadata() {
  local number="$1"
  local priority="$2"
  local owners_csv="$3"
  local schedule="$4"
  local labels_csv

  labels_csv="${priority},${SPRINT_LABEL},${owners_csv}"
  gh_retry issue edit "${number}" --repo "${REPO}" --add-assignee "${DEFAULT_ASSIGNEE}" --milestone "${MILESTONE_TITLE}" --add-label "${labels_csv}" >/dev/null

  ensure_status_label "${number}"
  auto_reconcile_issue_status "${number}"
  ensure_schedule_comment "${number}" "${schedule}"
  close_done_issue_if_open "${number}"
  log "issue #${number} metadata synced"
}

enforce_senior_dev_wip_limit() {
  local rows
  local rank_file
  local number
  local labels
  local updated
  local status
  local pr_rank
  local commit_rank
  local priority_rank
  local sorted_rows
  local keep_issue
  local doing_count
  local _pr
  local _commit
  local _priority
  local _updated

  rows="$(gh_retry issue list --repo "${REPO}" --state open --search "label:owner:role-senior-dev" --limit 100 --json number,labels,updatedAt --jq '.[] | [.number, ([.labels[].name] | join(",")), (.updatedAt // "")] | @tsv')"
  [ -n "${rows}" ] || return 0

  rank_file="${TMPDIR:-/tmp}/issue-sync-senior-dev-rank.$$.txt"
  : > "${rank_file}"

  while IFS=$'\t' read -r number labels updated; do
    [ -n "${number}" ] || continue
    status="$(printf '%s' "${labels}" | tr ',' '\n' | grep -E '^status:' | head -n1 || true)"
    [ "${status}" = "status:doing" ] || continue

    pr_rank=1
    commit_rank=1
    priority_rank=9
    if issue_has_open_pr_reference "${number}"; then
      pr_rank=0
    fi
    if issue_has_commit_reference "${number}"; then
      commit_rank=0
    fi
    if printf '%s' "${labels}" | tr ',' '\n' | grep -qx "priority:p0"; then
      priority_rank=0
    elif printf '%s' "${labels}" | tr ',' '\n' | grep -qx "priority:p1"; then
      priority_rank=1
    fi

    printf '%s|%s|%s|%s|%s\n' "${number}" "${pr_rank}" "${commit_rank}" "${priority_rank}" "${updated:-9999-12-31T23:59:59Z}" >> "${rank_file}"
  done <<EOF
${rows}
EOF

  if [ ! -s "${rank_file}" ]; then
    rm -f "${rank_file}" >/dev/null 2>&1 || true
    return 0
  fi

  sorted_rows="$(sort -t'|' -k2,2n -k3,3n -k4,4n -k5,5 "${rank_file}")"
  keep_issue="$(printf '%s\n' "${sorted_rows}" | head -n1 | cut -d'|' -f1)"
  doing_count="$(printf '%s\n' "${sorted_rows}" | sed '/^\s*$/d' | wc -l | tr -d ' ')"

  if [ "${doing_count}" -le 1 ]; then
    rm -f "${rank_file}" >/dev/null 2>&1 || true
    log "senior-dev WIP=1 already satisfied (doing=${doing_count}, keep=${keep_issue})"
    return 0
  fi

  while IFS='|' read -r number _pr _commit _priority _updated; do
    [ -n "${number}" ] || continue
    [ "${number}" = "${keep_issue}" ] && continue
    set_issue_status_label "${number}" "status:todo"
    ensure_status_evidence_comment \
      "${number}" \
      "wip-limit-1" \
      "status:doing" \
      "status:todo" \
      "WIP limit enforced for owner:role-senior-dev" \
      "active issue kept=#${keep_issue}"
    log "issue #${number} downgraded to todo by senior-dev WIP=1"
  done <<EOF
${sorted_rows}
EOF

  rm -f "${rank_file}" >/dev/null 2>&1 || true
  log "senior-dev WIP=1 enforced; active issue #${keep_issue}; downgraded=$((doing_count - 1))"
}

main() {
  local i1 i2 i3 i4 i5
  local s1 s2 s3 s4 s5

  ensure_labels
  ensure_milestone
  auto_merge_ready_prs
  build_open_pr_issue_map
  build_merged_pr_issue_map
  build_commit_issue_map

  i1="$(ensure_issue "[P0] 全局错误页 error.vue（C端稳定性）" "来源：7角色会审\n\n目标：增加 Nuxt 全局错误页，避免线上异常时暴露默认错误页面。\n\n验收标准：\n- 新增 error.vue，覆盖 404/500\n- 页面包含中文说明 + 返回首页\n- SSR/CSR 场景均可触发\n\n建议负责人：role-senior-dev\n建议优先级：P0")"
  i2="$(ensure_issue "[P0] 移动端 Header 汉堡菜单修复" "来源：7角色会审\n\n目标：修复移动端导航可用性，提升学习路径主流程完成率。\n\n验收标准：\n- <640px 显示汉堡菜单\n- 展开后包含关键导航项\n- 不出现遮挡与溢出\n\n建议负责人：role-senior-dev\n建议优先级：P0")"
  i3="$(ensure_issue "[P1] 学习页 XSS 防护与渲染净化" "来源：7角色会审\n\n目标：修复学习页潜在 XSS 风险。\n\n验收标准：\n- 对 v-html 输入做净化（如 DOMPurify）\n- script 注入无效\n- 增加对应测试用例\n\n建议负责人：role-senior-dev + role-code-reviewer\n建议优先级：P1")"
  i4="$(ensure_issue "[P1] SEO 元信息补全（首页/登录/注册）" "来源：7角色会审\n\n目标：补齐基础 SEO 与分享元信息。\n\n验收标准：\n- 首页/登录/注册页 title/description 完整\n- Open Graph 信息可生成分享预览\n- 基础收录检查通过\n\n建议负责人：role-product + role-senior-dev\n建议优先级：P1")"
  i5="$(ensure_issue "[P1] 周回顾表单必填校验与提交流程" "来源：7角色会审\n\n目标：提升周回顾数据质量，保证复盘闭环。\n\n验收标准：\n- 关键字段设为必填\n- 空提交有明确提示且阻止提交\n- 回归测试覆盖校验流程\n\n建议负责人：role-product + role-qa-test\n建议优先级：P1")"

  s1=$'[SCHEDULE]\n- 截止：'"${DUE_1}"$'\n- DoD：error.vue 提交并通过本地回归\n- 证据：commit/PR 链接 + 页面截图'
  s2=$'[SCHEDULE]\n- 截止：'"${DUE_2}"$'\n- DoD：移动端汉堡菜单可用且无遮挡\n- 证据：commit/PR 链接 + 移动端截图'
  s3=$'[SCHEDULE]\n- 截止：'"${DUE_3}"$'\n- DoD：XSS 输入被净化并有测试覆盖\n- 证据：commit/PR 链接 + 测试报告'
  s4=$'[SCHEDULE]\n- 截止：'"${DUE_4}"$'\n- DoD：首页/登录/注册 SEO 元信息完整\n- 证据：commit/PR 链接 + 页面 head 截图'
  s5=$'[SCHEDULE]\n- 截止：'"${DUE_5}"$'\n- DoD：周回顾表单必填校验与提交流程闭环\n- 证据：commit/PR 链接 + 测试报告'

  sync_issue_metadata "${i1}" "priority:p0" "owner:role-senior-dev" "${s1}"
  sync_issue_metadata "${i2}" "priority:p0" "owner:role-senior-dev" "${s2}"
  sync_issue_metadata "${i3}" "priority:p1" "owner:role-senior-dev,owner:role-code-reviewer" "${s3}"
  sync_issue_metadata "${i4}" "priority:p1" "owner:role-product,owner:role-senior-dev,owner:role-tech-director" "${s4}"
  sync_issue_metadata "${i5}" "priority:p1" "owner:role-product,owner:role-qa-test,owner:role-code-reviewer" "${s5}"
  reconcile_all_owner_issues
  enforce_senior_dev_wip_limit

  log "done"
}

main "$@"
