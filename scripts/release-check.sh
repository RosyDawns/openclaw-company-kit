#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

bash -n scripts/_common.sh
bash -n scripts/install.sh
bash -n scripts/install-cron.sh
bash -n scripts/start.sh
bash -n scripts/stop.sh
bash -n scripts/healthcheck.sh
bash -n scripts/demo-up.sh
bash -n scripts/demo-down.sh
bash -n scripts/release-check.sh

bash -n dashboard/rd-dashboard/refresh.sh
bash -n dashboard/rd-dashboard/issue-sync.sh
bash -n docker/entrypoint.sh

jq -e . templates/jobs.template.json >/dev/null
jq -e . templates/company-project.template.json >/dev/null
jq -e . docker/demo_data/dashboard-data.json >/dev/null
jq -e . docker/demo_data/business-metrics.json >/dev/null

python3 -m py_compile dashboard/rd-dashboard/dashboard_data.py
python3 -m unittest discover -s tests -p 'test_*.py' -v

echo "[OK] release checks passed"
