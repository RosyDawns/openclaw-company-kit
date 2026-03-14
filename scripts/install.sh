#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env
check_cmds
required_var GROUP_ID
required_var FEISHU_HOT_APP_ID
required_var FEISHU_HOT_APP_SECRET

PROFILE_CONFIG_PATH="$(ocp config file 2>/dev/null || true)"
PROFILE_CONFIG_PATH="$(expand_tilde_path "${PROFILE_CONFIG_PATH:-}")"

if [ -n "${SOURCE_OPENCLAW_CONFIG:-}" ]; then
  SOURCE_CONFIG_PATH="$(expand_tilde_path "${SOURCE_OPENCLAW_CONFIG}")"
fi

if [ -z "${SOURCE_CONFIG_PATH:-}" ] || [ ! -f "${SOURCE_CONFIG_PATH:-}" ]; then
  if [ -n "${PROFILE_CONFIG_PATH}" ] && [ -f "${PROFILE_CONFIG_PATH}" ]; then
    SOURCE_CONFIG_PATH="${PROFILE_CONFIG_PATH}"
  elif [ -f "${PROFILE_DIR}/openclaw.json" ]; then
    SOURCE_CONFIG_PATH="${PROFILE_DIR}/openclaw.json"
  else
    SOURCE_CONFIG_PATH="$(expand_tilde_path "$(openclaw config file 2>/dev/null || true)")"
  fi
fi

if [ ! -f "${SOURCE_CONFIG_PATH}" ]; then
  echo "[ERROR] source OpenClaw config not found: ${SOURCE_CONFIG_PATH}" >&2
  echo "Please run openclaw configure/onboard first, or set SOURCE_OPENCLAW_CONFIG in .env" >&2
  exit 1
fi

SHARED_CONTEXT_DIR="${PROFILE_DIR}/shared-context"

PROFILE_DIR_EXISTED=0
TARGET_WORKSPACE_EXISTED=0
SHARED_CONTEXT_DIR_EXISTED=0
[ -d "${PROFILE_DIR}" ] && PROFILE_DIR_EXISTED=1
[ -d "${TARGET_WORKSPACE}" ] && TARGET_WORKSPACE_EXISTED=1
[ -d "${SHARED_CONTEXT_DIR}" ] && SHARED_CONTEXT_DIR_EXISTED=1

ROLLBACK_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/openclaw-install-rollback.XXXXXX")"
ROLLBACK_DONE=0
INSTALL_COMPLETED=0

backup_file_if_exists() {
  local file_path="$1"
  local backup_path="${ROLLBACK_ROOT}${file_path}"
  if [ -f "${file_path}" ]; then
    mkdir -p "$(dirname "${backup_path}")"
    cp -p "${file_path}" "${backup_path}"
  fi
}

backup_dir_if_exists() {
  local dir_path="$1"
  local backup_path="${ROLLBACK_ROOT}${dir_path}"
  if [ -d "${dir_path}" ]; then
    mkdir -p "$(dirname "${backup_path}")"
    cp -a "${dir_path}" "${backup_path}"
  fi
}

restore_file_or_remove() {
  local file_path="$1"
  local backup_path="${ROLLBACK_ROOT}${file_path}"
  if [ -f "${backup_path}" ]; then
    mkdir -p "$(dirname "${file_path}")"
    cp -p "${backup_path}" "${file_path}"
  else
    rm -f "${file_path}"
  fi
}

restore_dir_or_remove() {
  local dir_path="$1"
  local backup_path="${ROLLBACK_ROOT}${dir_path}"
  if [ -d "${backup_path}" ]; then
    rm -rf "${dir_path}"
    mkdir -p "$(dirname "${dir_path}")"
    cp -a "${backup_path}" "${dir_path}"
  else
    rm -rf "${dir_path}"
  fi
}

rollback_install() {
  local exit_code="$1"
  local line_no="$2"
  if [ "${INSTALL_COMPLETED}" -eq 1 ] || [ "${ROLLBACK_DONE}" -eq 1 ]; then
    return
  fi
  ROLLBACK_DONE=1

  echo "[ROLLBACK] install failed at line ${line_no} (exit=${exit_code}), restoring previous state..." >&2

  restore_file_or_remove "${PROFILE_DIR}/openclaw.json"
  restore_file_or_remove "${PROFILE_DIR}/exec-approvals.json"
  restore_dir_or_remove "${TARGET_AGENTS_DIR}"
  restore_dir_or_remove "${TARGET_DASHBOARD_DIR}"

  if [ "${SHARED_CONTEXT_DIR_EXISTED}" -eq 1 ]; then
    restore_file_or_remove "${SHARED_CONTEXT_DIR}/priorities.md"
  else
    rm -rf "${SHARED_CONTEXT_DIR}"
  fi

  if [ "${TARGET_WORKSPACE_EXISTED}" -eq 0 ]; then
    rm -rf "${TARGET_WORKSPACE}"
  fi
  if [ "${PROFILE_DIR_EXISTED}" -eq 0 ]; then
    rmdir "${PROFILE_DIR}" 2>/dev/null || true
  fi

  rm -f "${tmp_cfg:-}" >/dev/null 2>&1 || true
  rm -rf "${ROLLBACK_ROOT}"
  echo "[ROLLBACK] restore completed" >&2
  exit "${exit_code}"
}

warn_profile_model_base_urls() {
  local config_path="$1"
  local provider base_url

  [ -f "${config_path}" ] || return 0

  while IFS=$'\t' read -r provider base_url; do
    [ -n "${base_url}" ] || continue
    warn_model_base_url "${base_url}" "${provider}" "install.profile"
  done < <(
    jq -r '
      (.models.providers // {})
      | to_entries[]
      | select((.value | type) == "object")
      | "\(.key)\t\(.value.baseUrl // "")"
    ' "${config_path}" 2>/dev/null || true
  )
}

warn_agent_model_base_urls() {
  local agents_root="$1"
  local model_file provider base_url agent_id

  [ -d "${agents_root}" ] || return 0

  while IFS= read -r model_file; do
    [ -f "${model_file}" ] || continue
    agent_id="$(basename "$(dirname "$(dirname "${model_file}")")")"
    while IFS=$'\t' read -r provider base_url; do
      [ -n "${base_url}" ] || continue
      warn_model_base_url "${base_url}" "${provider}" "install.agent:${agent_id}"
    done < <(
      jq -r '
        (.providers // {})
        | to_entries[]
        | select((.value | type) == "object")
        | "\(.key)\t\(.value.baseUrl // "")"
      ' "${model_file}" 2>/dev/null || true
    )
  done < <(find "${agents_root}" -type f -path '*/agent/models.json' | sort)
}

backup_file_if_exists "${PROFILE_DIR}/openclaw.json"
backup_file_if_exists "${PROFILE_DIR}/exec-approvals.json"
backup_file_if_exists "${SHARED_CONTEXT_DIR}/priorities.md"
backup_dir_if_exists "${TARGET_AGENTS_DIR}"
backup_dir_if_exists "${TARGET_DASHBOARD_DIR}"

trap 'rollback_install $? $LINENO' ERR

mkdir -p "${PROFILE_DIR}" "${TARGET_WORKSPACE}" "${TARGET_AGENTS_DIR}" "${TARGET_DASHBOARD_DIR}"
mkdir -p "${SHARED_CONTEXT_DIR}"/{roundtable,agent-outputs,feedback,kpis}

if [ ! -f "${SHARED_CONTEXT_DIR}/priorities.md" ]; then
  cat > "${SHARED_CONTEXT_DIR}/priorities.md" <<'PRIORITIES'
# 当前迭代优先级

> 所有角色每次执行前必读。由研发总监或产品经理维护。

## P0 — 必须完成

## P1 — 应该完成

## P2 — 可以推迟

---
*最后更新: 待填写*
PRIORITIES
fi

if [ "${SOURCE_CONFIG_PATH}" != "${PROFILE_DIR}/openclaw.json" ]; then
  cp "${SOURCE_CONFIG_PATH}" "${PROFILE_DIR}/openclaw.json"
fi

echo "[install] profile=${OPENCLAW_PROFILE}"
echo "[install] config=${PROFILE_DIR}/openclaw.json"

for agent_id in hot-search ai-tech rd-company role-product role-tech-director role-senior-dev role-growth role-code-reviewer role-qa-test; do
  mkdir -p "${TARGET_AGENTS_DIR}/${agent_id}"
  for mdfile in SOUL.md AGENTS.md MEMORY.md HEARTBEAT.md IDENTITY.md TOOLS.md USER.md BOOTSTRAP.md; do
    if [ -f "${ROOT_DIR}/templates/agents/${agent_id}/${mdfile}" ]; then
      cp "${ROOT_DIR}/templates/agents/${agent_id}/${mdfile}" "${TARGET_AGENTS_DIR}/${agent_id}/${mdfile}"
    fi
    if [ -f "${TARGET_AGENTS_DIR}/${agent_id}/${mdfile}" ]; then
      sed_inplace \
        -e "s|__PROJECT_PATH__|${PROJECT_PATH}|g" \
        -e "s|__PROJECT_REPO__|${PROJECT_REPO}|g" \
        -e "s|__COMPANY_NAME__|${COMPANY_NAME}|g" \
        -e "s|__FEISHU_HOT_BOT_NAME__|${FEISHU_HOT_BOT_NAME}|g" \
        -e "s|__FEISHU_AI_BOT_NAME__|${FEISHU_AI_BOT_NAME}|g" \
        -e "s|__SHARED_CONTEXT__|${SHARED_CONTEXT_DIR}|g" \
        "${TARGET_AGENTS_DIR}/${agent_id}/${mdfile}"
    fi
  done
done

WORKFLOW_TEMPLATE_ID="default"
WORKFLOW_PROMPT_TEMPLATE=""
case "$(printf '%s' "${WORKFLOW_TEMPLATE:-default}" | tr '[:upper:]' '[:lower:]')" in
  requirement-review|requirement_review|review)
    WORKFLOW_TEMPLATE_ID="requirement-review"
    WORKFLOW_PROMPT_TEMPLATE="${ROOT_DIR}/templates/workflow-prompt.requirement-review.txt"
    ;;
  bugfix|bug-fix|bug_fix)
    WORKFLOW_TEMPLATE_ID="bugfix"
    WORKFLOW_PROMPT_TEMPLATE="${ROOT_DIR}/templates/workflow-prompt.bugfix.txt"
    ;;
  release-retro|release_retro|retro|postmortem)
    WORKFLOW_TEMPLATE_ID="release-retro"
    WORKFLOW_PROMPT_TEMPLATE="${ROOT_DIR}/templates/workflow-prompt.release-retro.txt"
    ;;
esac

GROUP_PROMPT="$(sed \
  -e "s|__PROJECT_PATH__|${PROJECT_PATH}|g" \
  -e "s|__PROJECT_REPO__|${PROJECT_REPO}|g" \
  "${ROOT_DIR}/templates/group-system-prompt.txt")"

if [ -n "${WORKFLOW_PROMPT_TEMPLATE}" ] && [ -f "${WORKFLOW_PROMPT_TEMPLATE}" ]; then
  workflow_prompt_rendered="$(sed \
    -e "s|__PROJECT_PATH__|${PROJECT_PATH}|g" \
    -e "s|__PROJECT_REPO__|${PROJECT_REPO}|g" \
    -e "s|__PROJECT_NAME__|${COMPANY_NAME}|g" \
    "${WORKFLOW_PROMPT_TEMPLATE}")"
  GROUP_PROMPT="${GROUP_PROMPT}"$'\n\n'"${workflow_prompt_rendered}"
fi

if [ -n "${FEISHU_ALLOW_FROM}" ]; then
  allow_from_json="$(jq -cn --arg raw "${FEISHU_ALLOW_FROM}" --arg groupId "${GROUP_ID}" '
    $raw
    | split(",")
    | map(gsub("^\\s+|\\s+$"; ""))
    | map(select(length > 0))
    | if length == 0 then [$groupId] else . end
  ')"
else
  # Secure default: only accept events from configured group.
  allow_from_json="$(jq -cn --arg groupId "${GROUP_ID}" '[$groupId]')"
fi

tmp_cfg="$(mktemp)"
jq \
  --arg stateDir "${PROFILE_DIR}" \
  --arg groupId "${GROUP_ID}" \
  --argjson allowFrom "${allow_from_json}" \
  --arg companyName "${COMPANY_NAME}" \
  --arg projectPath "${PROJECT_PATH}" \
  --arg projectRepo "${PROJECT_REPO}" \
  --arg hotAccount "${FEISHU_HOT_ACCOUNT_ID}" \
  --arg hotAppId "${FEISHU_HOT_APP_ID}" \
  --arg hotAppSecret "${FEISHU_HOT_APP_SECRET}" \
  --arg hotBotName "${FEISHU_HOT_BOT_NAME}" \
  --arg aiAccount "${FEISHU_AI_ACCOUNT_ID}" \
  --arg aiAppId "${FEISHU_AI_APP_ID}" \
  --arg aiAppSecret "${FEISHU_AI_APP_SECRET}" \
  --arg aiBotName "${FEISHU_AI_BOT_NAME}" \
  --arg ghToken "${GH_TOKEN}" \
  --arg modelPrimary "${MODEL_PRIMARY}" \
  --arg modelSubagent "${MODEL_SUBAGENT}" \
  --arg discordToken "${DISCORD_BOT_TOKEN}" \
  --arg discordGuild "${DISCORD_GUILD_ID}" \
  --arg discordChannel "${DISCORD_CHANNEL_ID}" \
  --arg prompt "${GROUP_PROMPT}" \
  '
  .agents.defaults.workspace = ($stateDir + "/workspace") |
  .agents.defaults.heartbeat = {"every": "30m", "target": "last", "activeHours": {"start": "08:00", "end": "22:00"}} |
  .agents.defaults.compaction = {"mode": "safeguard", "memoryFlush": {"enabled": true, "softThresholdTokens": 4000}} |
  (if $modelPrimary != "" then .agents.defaults.model.primary = $modelPrimary else . end) |
  (if $modelSubagent != "" then .agents.defaults.subagents.model = $modelSubagent else . end) |
  .agents.list = [
    {"id":"main","default":true,"name":"主助手","workspace":($stateDir + "/workspace")},
    {"id":"hot-search","name":"热点推荐","workspace":($stateDir + "/agents/hot-search"),
     "tools":{"deny":["exec","group:runtime","group:fs","group:sessions"]}},
    {"id":"ai-tech","name":"AI科技","workspace":($stateDir + "/agents/ai-tech"),
     "tools":{"deny":["exec","group:runtime","group:fs","group:sessions"]}},
    {"id":"rd-company","name":"公司研发中台","workspace":($stateDir + "/agents/rd-company"),
     "identity":{"name":"研发总监"},
     "tools":{"allow":["exec","read","write","edit","gh-issues","sessions_send","sessions_spawn","sessions_list","sessions_history","session_status"]},
     "subagents":{"allowAgents":["role-tech-director","role-senior-dev","role-code-reviewer","role-qa-test","role-product","role-growth"]}},
    {"id":"role-product","name":"产品经理","workspace":($stateDir + "/agents/role-product"),
     "identity":{"name":"产品经理"},
     "tools":{"allow":["read","gh-issues","sessions_send","sessions_list","sessions_history","session_status"],
              "deny":["exec","group:runtime","write","edit","apply_patch"]}},
    {"id":"role-tech-director","name":"技术总监","workspace":($stateDir + "/agents/role-tech-director"),
     "identity":{"name":"技术总监"},
     "tools":{"allow":["exec","read","gh-issues","sessions_send","sessions_list","sessions_history","session_status"],
              "deny":["write","edit","apply_patch"]},
     "subagents":{"allowAgents":["role-senior-dev","role-code-reviewer"]}},
    {"id":"role-senior-dev","name":"高级程序员","workspace":($stateDir + "/agents/role-senior-dev"),
     "identity":{"name":"高级程序员"},
     "tools":{"allow":["exec","read","write","edit","apply_patch","gh-issues","sessions_send","sessions_list","sessions_history","session_status"]},
     "subagents":{"allowAgents":["role-code-reviewer","role-qa-test"]}},
    {"id":"role-growth","name":"增长运营","workspace":($stateDir + "/agents/role-growth"),
     "identity":{"name":"增长运营"},
     "tools":{"deny":["exec","group:runtime","group:fs","group:sessions"]}},
    {"id":"role-code-reviewer","name":"代码Reviewer","workspace":($stateDir + "/agents/role-code-reviewer"),
     "identity":{"name":"代码Reviewer"},
     "tools":{"allow":["exec","read","gh-issues","sessions_send","sessions_list","sessions_history","session_status"],
              "deny":["write","edit","apply_patch"]}},
    {"id":"role-qa-test","name":"测试工程师","workspace":($stateDir + "/agents/role-qa-test"),
     "identity":{"name":"测试工程师"},
     "tools":{"allow":["exec","read","gh-issues","sessions_send","sessions_list","sessions_history","session_status"],
              "deny":["write","edit","apply_patch"]}}
  ] |
  .bindings = (
    [
      {
        "agentId":"rd-company",
        "comment":"公司研发群固定路由",
        "match":{"channel":"feishu","accountId":$hotAccount,"peer":{"kind":"group","id":$groupId}}
      },
      {"agentId":"hot-search","match":{"channel":"feishu","accountId":$hotAccount}}
    ]
    + (if $aiAppId != "" then [{"agentId":"ai-tech","match":{"channel":"feishu","accountId":$aiAccount}}] else [] end)
  ) |
  .channels = (.channels // {}) |
  .channels.feishu = ((.channels.feishu // {}) + {"enabled":true,"domain":"feishu"}) |
  .channels.feishu.accounts = (
    (
      (.channels.feishu.accounts // {})
      + {
        ($hotAccount): {
          "enabled": true,
          "appId": $hotAppId,
          "appSecret": $hotAppSecret,
          "botName": $hotBotName,
          "dmPolicy": "allowlist",
          "groupPolicy": "allowlist",
          "allowFrom": $allowFrom,
          "groupAllowFrom": $allowFrom
        },
        "default": {
          "groupPolicy": "allowlist",
          "dmPolicy": "allowlist",
          "allowFrom": $allowFrom,
          "groupAllowFrom": $allowFrom
        }
      }
    )
    | if $aiAppId != "" and $aiAppSecret != "" then
        . + {
          ($aiAccount): {
            "enabled": true,
            "appId": $aiAppId,
            "appSecret": $aiAppSecret,
            "botName": $aiBotName,
            "dmPolicy": "allowlist",
            "groupPolicy": "allowlist",
            "allowFrom": $allowFrom,
            "groupAllowFrom": $allowFrom
          }
        }
      else
        del(.[$aiAccount])
      end
  ) |
  .channels.feishu.groups = ((.channels.feishu.groups // {}) + {
    ($groupId): {
      "requireMention": false,
      "systemPrompt": $prompt
    }
  }) |
  .commands.native = "auto" |
  .commands.nativeSkills = "auto" |
  .commands.restart = true |
  .commands.ownerDisplay = "raw" |
  .tools.profile = "messaging" |
  .tools.agentToAgent = {"enabled": true, "allow": ["rd-company","role-tech-director","role-senior-dev","role-code-reviewer","role-qa-test","role-product","role-growth"]} |
  .messages.ackReactionScope = "group-mentions" |
  .session.dmScope = "per-channel-peer" |
  .session.agentToAgent = {"maxPingPongTurns": 3} |
  .skills = (.skills // {}) |
  .skills.entries = (.skills.entries // {}) |
  (if $ghToken != "" then .skills.entries["gh-issues"] = {"apiKey": $ghToken} else . end) |
  (if $discordToken != "" then
    .channels.discord = (.channels.discord // {}) |
    .channels.discord += {"enabled": true, "token": $discordToken, "dmPolicy": "open", "groupPolicy": "allowlist"} |
    (if $discordGuild != "" then
      .channels.discord.guilds = (.channels.discord.guilds // {}) |
      (if $discordChannel != "" then
        .channels.discord.guilds[$discordGuild] = {"channels": {($discordChannel): {"allow": true}}}
      else
        .channels.discord.guilds[$discordGuild] = {}
      end)
    else . end)
  else . end)
  ' "${PROFILE_DIR}/openclaw.json" > "${tmp_cfg}"

mv "${tmp_cfg}" "${PROFILE_DIR}/openclaw.json"

warn_profile_model_base_urls "${PROFILE_DIR}/openclaw.json"
warn_agent_model_base_urls "${TARGET_AGENTS_DIR}"

# Deploy exec-approvals (command-level allowlist)
EXEC_APPROVALS_TEMPLATE="${ROOT_DIR}/templates/exec-approvals.template.json"
if [ -f "${EXEC_APPROVALS_TEMPLATE}" ]; then
  cp "${EXEC_APPROVALS_TEMPLATE}" "${PROFILE_DIR}/exec-approvals.json"
  echo "[install] exec-approvals deployed"
fi

# Deploy dashboard bundle
rsync -a --delete --exclude '__pycache__' "${ROOT_DIR}/dashboard/rd-dashboard/" "${TARGET_DASHBOARD_DIR}/"

# Render company-project.json
company_project_rendered="$(sed \
  -e "s|__COMPANY_NAME__|${COMPANY_NAME}|g" \
  -e "s|__PROJECT_PATH__|${PROJECT_PATH}|g" \
  -e "s|__PROJECT_REPO__|${PROJECT_REPO}|g" \
  -e "s|__UPDATED_AT__|$(now_local)|g" \
  "${ROOT_DIR}/templates/company-project.template.json")"
printf '%s\n' "${company_project_rendered}" > "${TARGET_DASHBOARD_DIR}/company-project.json"

# Runtime env for dashboard/issue-sync scripts
cat > "${TARGET_DASHBOARD_DIR}/.env.runtime" <<RUNTIME_ENV
OPENCLAW_STATE_DIR=${PROFILE_DIR}
OPENCLAW_GROUP_ID=${GROUP_ID}
OPENCLAW_PROJECT_DIR=${PROJECT_PATH}
OPENCLAW_PROJECT_REPO=${PROJECT_REPO}
OPENCLAW_CONFIG=${PROFILE_DIR}/openclaw.json
WORKFLOW_TEMPLATE=${WORKFLOW_TEMPLATE_ID}
CRON_GUARD_FEISHU_ACCOUNT=${FEISHU_HOT_ACCOUNT_ID}
CRON_GUARD_FEISHU_TARGET=${GROUP_ID}
RUNTIME_ENV

chmod +x "${TARGET_DASHBOARD_DIR}/"*.sh

ocp config get agents --json >/dev/null

if ! "${ROOT_DIR}/scripts/install-cron.sh"; then
  echo "[WARN] cron sync failed (gateway unreachable or auth mismatch)." >&2
  echo "[WARN] you can run it later: bash scripts/install-cron.sh" >&2
fi

echo "[install] workflow template: ${WORKFLOW_TEMPLATE_ID}"

INSTALL_COMPLETED=1
trap - ERR
rm -rf "${ROLLBACK_ROOT}"

echo "[OK] install completed"
echo "[next] run: bash scripts/start.sh"
