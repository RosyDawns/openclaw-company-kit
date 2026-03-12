#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env
check_cmds
required_var GROUP_ID
required_var FEISHU_HOT_APP_ID
required_var FEISHU_HOT_APP_SECRET

SOURCE_CONFIG_PATH="${SOURCE_OPENCLAW_CONFIG:-$(openclaw config file)}"
SOURCE_CONFIG_PATH="$(expand_tilde_path "${SOURCE_CONFIG_PATH}")"

if [ ! -f "${SOURCE_CONFIG_PATH}" ]; then
  echo "[ERROR] source OpenClaw config not found: ${SOURCE_CONFIG_PATH}" >&2
  echo "Please run openclaw configure first, or set SOURCE_OPENCLAW_CONFIG in .env" >&2
  exit 1
fi

mkdir -p "${PROFILE_DIR}" "${TARGET_WORKSPACE}" "${TARGET_AGENTS_DIR}" "${TARGET_DASHBOARD_DIR}"
cp "${SOURCE_CONFIG_PATH}" "${PROFILE_DIR}/openclaw.json"

echo "[install] profile=${OPENCLAW_PROFILE}"
echo "[install] config=${PROFILE_DIR}/openclaw.json"

for agent_id in hot-search ai-tech rd-company role-product role-tech-director role-senior-dev role-growth role-code-reviewer role-qa-test; do
  mkdir -p "${TARGET_AGENTS_DIR}/${agent_id}"
  if [ -f "${ROOT_DIR}/templates/agents/${agent_id}/SOUL.md" ]; then
    cp "${ROOT_DIR}/templates/agents/${agent_id}/SOUL.md" "${TARGET_AGENTS_DIR}/${agent_id}/SOUL.md"
  fi
done

GROUP_PROMPT="$(sed \
  -e "s|__PROJECT_PATH__|${PROJECT_PATH}|g" \
  -e "s|__PROJECT_REPO__|${PROJECT_REPO}|g" \
  "${ROOT_DIR}/templates/group-system-prompt.txt")"

tmp_cfg="$(mktemp)"
jq \
  --arg stateDir "${PROFILE_DIR}" \
  --arg groupId "${GROUP_ID}" \
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
  --arg prompt "${GROUP_PROMPT}" \
  '
  .agents.defaults.workspace = ($stateDir + "/workspace") |
  (if $modelPrimary != "" then .agents.defaults.model.primary = $modelPrimary else . end) |
  .agents.list = [
    {"id":"main","default":true,"name":"主助手","workspace":($stateDir + "/workspace")},
    {"id":"hot-search","name":"热点推荐","workspace":($stateDir + "/agents/hot-search")},
    {"id":"ai-tech","name":"AI科技","workspace":($stateDir + "/agents/ai-tech")},
    {"id":"rd-company","name":"公司研发中台","workspace":($stateDir + "/agents/rd-company"),"identity":{"name":"研发总监"}},
    {"id":"role-product","name":"产品经理","workspace":($stateDir + "/agents/role-product"),"identity":{"name":"产品经理"}},
    {"id":"role-tech-director","name":"技术总监","workspace":($stateDir + "/agents/role-tech-director"),"identity":{"name":"技术总监"}},
    {"id":"role-senior-dev","name":"高级程序员","workspace":($stateDir + "/agents/role-senior-dev"),"identity":{"name":"高级程序员"}},
    {"id":"role-growth","name":"增长运营","workspace":($stateDir + "/agents/role-growth"),"identity":{"name":"增长运营"}},
    {"id":"role-code-reviewer","name":"代码Reviewer","workspace":($stateDir + "/agents/role-code-reviewer"),"identity":{"name":"代码Reviewer"}},
    {"id":"role-qa-test","name":"测试工程师","workspace":($stateDir + "/agents/role-qa-test"),"identity":{"name":"测试工程师"}}
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
    (.channels.feishu.accounts // {})
    + {
      ($hotAccount): {
        "enabled": true,
        "appId": $hotAppId,
        "appSecret": $hotAppSecret,
        "botName": $hotBotName,
        "dmPolicy": "open",
        "groupPolicy": "open",
        "allowFrom": ["*"]
      },
      "default": {
        "groupPolicy": "open",
        "dmPolicy": "open",
        "allowFrom": ["*"]
      }
    }
    + (if $aiAppId != "" and $aiAppSecret != "" then {
      ($aiAccount): {
        "enabled": true,
        "appId": $aiAppId,
        "appSecret": $aiAppSecret,
        "botName": $aiBotName,
        "dmPolicy": "open",
        "groupPolicy": "open",
        "allowFrom": ["*"]
      }
    } else {} end)
  ) |
  .channels.feishu.groups = ((.channels.feishu.groups // {}) + {
    ($groupId): {
      "requireMention": false,
      "systemPrompt": $prompt
    }
  }) |
  .skills = (.skills // {}) |
  .skills.entries = (.skills.entries // {}) |
  (if $ghToken != "" then .skills.entries["gh-issues"] = {"apiKey": $ghToken} else . end)
  ' "${PROFILE_DIR}/openclaw.json" > "${tmp_cfg}"

mv "${tmp_cfg}" "${PROFILE_DIR}/openclaw.json"

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
CRON_GUARD_FEISHU_ACCOUNT=${FEISHU_HOT_ACCOUNT_ID}
CRON_GUARD_FEISHU_TARGET=${GROUP_ID}
RUNTIME_ENV

chmod +x "${TARGET_DASHBOARD_DIR}/"*.sh

ocp config validate >/dev/null

if ! "${ROOT_DIR}/scripts/install-cron.sh"; then
  echo "[WARN] cron sync failed (gateway unreachable or auth mismatch)." >&2
  echo "[WARN] you can run it later: bash scripts/install-cron.sh" >&2
fi

echo "[OK] install completed"
echo "[next] run: bash scripts/start.sh"
