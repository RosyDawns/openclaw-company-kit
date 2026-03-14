#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env
check_cmds
required_var GROUP_ID
required_var FEISHU_HOT_APP_ID
required_var FEISHU_HOT_APP_SECRET

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
esac
if [ ! -f "${WORKFLOW_JOBS_TEMPLATE}" ]; then
  echo "[ERROR] workflow jobs template not found: ${WORKFLOW_JOBS_TEMPLATE}" >&2
  exit 1
fi

jobs_json="$(
  sed \
    -e "s|__GROUP_ID__|${GROUP_ID}|g" \
    -e "s|__HOT_ACCOUNT__|${FEISHU_HOT_ACCOUNT_ID}|g" \
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
    -e "s|__HOT_ACCOUNT__|${FEISHU_HOT_ACCOUNT_ID}|g" \
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

existing_jobs="$(ocp cron list --all --json)"

upsert_job() {
  local job_json="$1"
  local name agent cron_expr tz account to timeout thinking message existing_id

  name="$(jq -r '.name' <<<"${job_json}")"
  agent="$(jq -r '.agent' <<<"${job_json}")"
  cron_expr="$(jq -r '.cron' <<<"${job_json}")"
  tz="$(jq -r '.tz' <<<"${job_json}")"
  account="$(jq -r '.account' <<<"${job_json}")"
  to="$(jq -r '.to' <<<"${job_json}")"
  timeout="$(jq -r '.timeoutSeconds // 420' <<<"${job_json}")"
  thinking="$(jq -r '.thinking // "minimal"' <<<"${job_json}")"
  message="$(jq -r '.message' <<<"${job_json}")"

  existing_id="$(jq -r --arg n "${name}" '.jobs[] | select(.name == $n) | .id' <<<"${existing_jobs}" | head -n1)"

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
