#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env
check_cmds
required_var GROUP_ID
required_var FEISHU_AI_APP_ID
required_var FEISHU_AI_APP_SECRET

CRON_FEISHU_ACCOUNT="${FEISHU_AI_ACCOUNT_ID}"

TEMPLATE_PATH="${ROOT_DIR}/templates/jobs.template.json"
if [ ! -f "${TEMPLATE_PATH}" ]; then
  echo "[ERROR] jobs template not found: ${TEMPLATE_PATH}" >&2
  exit 1
fi

WORKFLOW_TEMPLATE_ID="default"
WORKFLOW_JOBS_TEMPLATE="${ROOT_DIR}/templates/workflow-jobs.default.json"
case "$(printf '%s' "${WORKFLOW_TEMPLATE:-default}" | tr '[:upper:]' '[:lower:]')" in
  requirement-review|requirement_review|review)
    WORKFLOW_TEMPLATE_ID="requirement-review"
    WORKFLOW_JOBS_TEMPLATE="${ROOT_DIR}/templates/workflow-jobs.requirement-review.json"
    ;;
  bugfix|bug-fix|bug_fix)
    WORKFLOW_TEMPLATE_ID="bugfix"
    WORKFLOW_JOBS_TEMPLATE="${ROOT_DIR}/templates/workflow-jobs.bugfix.json"
    ;;
  release-retro|release_retro|retro|postmortem)
    WORKFLOW_TEMPLATE_ID="release-retro"
    WORKFLOW_JOBS_TEMPLATE="${ROOT_DIR}/templates/workflow-jobs.release-retro.json"
    ;;
  code-sprint|code_sprint|sprint)
    WORKFLOW_TEMPLATE_ID="code-sprint"
    WORKFLOW_JOBS_TEMPLATE="${ROOT_DIR}/templates/workflow-jobs.code-sprint.json"
    ;;
  incident-response|incident_response|incident)
    WORKFLOW_TEMPLATE_ID="incident-response"
    WORKFLOW_JOBS_TEMPLATE="${ROOT_DIR}/templates/workflow-jobs.incident-response.json"
    ;;
  feature-delivery|feature_delivery|delivery)
    WORKFLOW_TEMPLATE_ID="feature-delivery"
    WORKFLOW_JOBS_TEMPLATE="${ROOT_DIR}/templates/workflow-jobs.feature-delivery.json"
    ;;
esac
if [ ! -f "${WORKFLOW_JOBS_TEMPLATE}" ]; then
  echo "[ERROR] workflow jobs template not found: ${WORKFLOW_JOBS_TEMPLATE}" >&2
  exit 1
fi

jobs_json="$(
  sed \
    -e "s|__GROUP_ID__|${GROUP_ID}|g" \
    -e "s|__HOT_ACCOUNT__|${CRON_FEISHU_ACCOUNT}|g" \
    -e "s|__PROJECT_REPO__|${PROJECT_REPO}|g" \
    -e "s|__PROJECT_PATH__|${PROJECT_PATH}|g" \
    -e "s|__PROJECT_NAME__|${COMPANY_NAME}|g" \
    "${TEMPLATE_PATH}"
)"

if ! printf '%s' "${jobs_json}" | jq -e . >/dev/null; then
  echo "[ERROR] rendered jobs template is invalid JSON" >&2
  exit 1
fi

workflow_jobs_json="$(
  sed \
    -e "s|__GROUP_ID__|${GROUP_ID}|g" \
    -e "s|__HOT_ACCOUNT__|${CRON_FEISHU_ACCOUNT}|g" \
    -e "s|__PROJECT_REPO__|${PROJECT_REPO}|g" \
    -e "s|__PROJECT_PATH__|${PROJECT_PATH}|g" \
    -e "s|__PROJECT_NAME__|${COMPANY_NAME}|g" \
    "${WORKFLOW_JOBS_TEMPLATE}"
)"
if ! printf '%s' "${workflow_jobs_json}" | jq -e . >/dev/null; then
  echo "[ERROR] rendered workflow jobs template is invalid JSON" >&2
  exit 1
fi

jobs_json="$(
  printf '%s' "${jobs_json}" | jq --argjson workflow "${workflow_jobs_json}" '
    .jobs = ([.jobs[] | select((.name | startswith("模板-")) | not)] + ($workflow.jobs // []))
  '
)"

gateway_status_raw="$(ocp gateway status 2>&1 || true)"
if ! printf '%s' "${gateway_status_raw}" | grep -q 'RPC probe: ok'; then
  echo "[WARN] cron sync skipped: gateway RPC probe not ready" >&2
  printf '%s\n' "${gateway_status_raw}" | sed -n '1,80p' >&2
  exit 1
fi

if ! existing_jobs_raw="$(ocp cron list --all --json 2>&1)"; then
  echo "[WARN] cron sync failed: cannot list existing jobs" >&2
  printf '%s\n' "${existing_jobs_raw}" | sed -n '1,80p' >&2
  exit 1
fi

existing_jobs="$(printf '%s' "${existing_jobs_raw}" | extract_json_payload 2>/dev/null || true)"
if [ -z "${existing_jobs}" ] || ! printf '%s' "${existing_jobs}" | jq -e 'type == "object"' >/dev/null 2>&1; then
  echo "[WARN] cron sync failed: invalid JSON from cron list output" >&2
  printf '%s\n' "${existing_jobs_raw}" | sed -n '1,80p' >&2
  exit 1
fi
existing_jobs="$(printf '%s' "${existing_jobs}" | jq -c '{jobs: (.jobs // [])}')"

template_duplicate_names="$(printf '%s' "${jobs_json}" | jq -r '
  .jobs
  | group_by(.name)
  | map(select(length > 1) | .[0].name)
  | .[]
')"
if [ -n "${template_duplicate_names}" ]; then
  echo "[ERROR] jobs template contains duplicate names; aborting sync:" >&2
  while IFS= read -r dup_name; do
    [ -n "${dup_name}" ] || continue
    echo "  - ${dup_name}" >&2
  done <<< "${template_duplicate_names}"
  exit 1
fi

upsert_job() {
  local job_json="$1"
  local name agent cron_expr tz account to timeout thinking message existing_ids existing_id duplicate_ids duplicate_id

  name="$(jq -r '.name' <<<"${job_json}")"
  agent="$(jq -r '.agent' <<<"${job_json}")"
  cron_expr="$(jq -r '.cron' <<<"${job_json}")"
  tz="$(jq -r '.tz' <<<"${job_json}")"
  account="$(jq -r '.account' <<<"${job_json}")"
  to="$(jq -r '.to' <<<"${job_json}")"
  timeout="$(jq -r '.timeoutSeconds // 420' <<<"${job_json}")"
  thinking="$(jq -r '.thinking // "minimal"' <<<"${job_json}")"
  message="$(jq -r '.message' <<<"${job_json}")"

  existing_ids="$(jq -r --arg n "${name}" '.jobs[] | select(.name == $n) | .id' <<<"${existing_jobs}" | sed '/^$/d' || true)"
  existing_id="$(printf '%s\n' "${existing_ids}" | head -n1)"
  duplicate_ids="$(printf '%s\n' "${existing_ids}" | tail -n +2 || true)"

  if [ -n "${existing_id}" ]; then
    echo "[cron] update: ${name} (${existing_id})"
    ocp cron edit "${existing_id}" \
      --name "${name}" \
      --agent "${agent}" \
      --cron "${cron_expr}" \
      --tz "${tz}" \
      --session isolated \
      --wake now \
      --message "${message}" \
      --timeout-seconds "${timeout}" \
      --thinking "${thinking}" \
      --channel feishu \
      --account "${account}" \
      --to "${to}" \
      --announce \
      --enable >/dev/null

    while IFS= read -r duplicate_id; do
      [ -n "${duplicate_id}" ] || continue
      echo "[cron] remove-duplicate: ${name} (${duplicate_id})"
      ocp cron rm "${duplicate_id}" >/dev/null
    done <<< "${duplicate_ids}"
  else
    echo "[cron] create: ${name}"
    ocp cron add \
      --name "${name}" \
      --agent "${agent}" \
      --cron "${cron_expr}" \
      --tz "${tz}" \
      --session isolated \
      --wake now \
      --message "${message}" \
      --timeout-seconds "${timeout}" \
      --thinking "${thinking}" \
      --channel feishu \
      --account "${account}" \
      --to "${to}" \
      --announce >/dev/null
  fi
}

while IFS= read -r row; do
  [ -n "${row}" ] || continue
  upsert_job "$(printf '%s' "${row}" | base64 --decode)"
done < <(printf '%s' "${jobs_json}" | jq -r '.jobs[] | @base64')

echo "[cron] workflow template: ${WORKFLOW_TEMPLATE_ID}"
echo "[OK] cron jobs synced for profile: ${OPENCLAW_PROFILE}"
