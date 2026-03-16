#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "=== Shell syntax check ==="
bash -n scripts/_common.sh
bash -n scripts/install.sh
bash -n scripts/install-gh-bridge.sh
bash -n scripts/install-cron.sh
bash -n scripts/bootstrap.sh
bash -n scripts/launch.sh
bash -n scripts/start.sh
bash -n scripts/stop.sh
bash -n scripts/healthcheck.sh
bash -n scripts/watchdog.sh
bash -n scripts/onboard-wrapper.sh
bash -n scripts/demo-up.sh
bash -n scripts/demo-down.sh
bash -n scripts/release-check.sh
bash -n scripts/backup.sh
bash -n scripts/restore.sh

bash -n dashboard/rd-dashboard/refresh.sh
bash -n dashboard/rd-dashboard/issue-sync.sh
bash -n docker/entrypoint.sh

echo "=== Python compile check ==="
python3 -m py_compile dashboard/rd-dashboard/dashboard_data.py
python3 -m py_compile scripts/control_server.py
for f in engine/*.py; do python3 -m py_compile "$f"; done
find server -name '*.py' -exec python3 -m py_compile {} +

echo "=== JSON validation ==="
jq -e . templates/jobs.template.json >/dev/null
jq -e . templates/company-project.template.json >/dev/null
jq -e . templates/exec-approvals.template.json >/dev/null
for f in templates/workflow-jobs.*.json; do jq -e . "$f" >/dev/null; done
jq -e . engine/role_config.json >/dev/null
jq -e . engine/review_rules.json >/dev/null
for f in templates/agents/*/manifest.json; do jq -e . "$f" >/dev/null; done
jq -e . docker/demo_data/dashboard-data.json >/dev/null
jq -e . docker/demo_data/business-metrics.json >/dev/null

echo "=== Tests ==="
python3 -m pytest tests/ -v --tb=short

echo "[OK] release checks passed"
