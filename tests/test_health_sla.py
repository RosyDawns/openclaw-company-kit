"""Regression checks for health SLA and failure classification."""

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEALTHCHECK_SH = ROOT / "scripts" / "healthcheck.sh"
WATCHDOG_SH = ROOT / "scripts" / "watchdog.sh"
DASHBOARD_DATA_PY = ROOT / "dashboard" / "rd-dashboard" / "dashboard_data.py"
DASHBOARD_HTML = ROOT / "dashboard" / "rd-dashboard" / "index.html"


class HealthSlaTests(unittest.TestCase):
    def test_healthcheck_has_sla_threshold_and_summary_output(self):
        content = HEALTHCHECK_SH.read_text(encoding="utf-8")
        self.assertIn('DASHBOARD_DATA_SLA_MINUTES="${DASHBOARD_DATA_SLA_MINUTES:-15}"', content)
        self.assertIn('HEALTH_SUMMARY_FILE="${HEALTH_STATE_DIR}/healthcheck-summary.json"', content)
        self.assertIn("write_health_summary()", content)
        self.assertIn("summary_file=${HEALTH_SUMMARY_FILE}", content)
        self.assertIn("extract_json_payload()", content)
        self.assertIn("python3 -c '", content)
        self.assertIn('gateway_raw="$(ocp status --all --json 2>/dev/null || true)"', content)
        self.assertIn("gateway_reachable=\"false\"", content)
        self.assertIn("jq -r '.gateway.reachable // false'", content)
        self.assertIn("jq -r '.gateway.error // \"\"'", content)
        self.assertIn('cron_raw="$(ocp cron list --all --json 2>/dev/null || true)"', content)

    def test_healthcheck_classifies_required_failure_types(self):
        content = HEALTHCHECK_SH.read_text(encoding="utf-8")
        self.assertIn('"gateway_fault"', content)
        self.assertIn('"data_lag"', content)
        self.assertIn('"github_rate_limit"', content)
        self.assertIn("contains_rate_limit_hint()", content)

    def test_watchdog_uses_health_classification_for_actions(self):
        content = WATCHDOG_SH.read_text(encoding="utf-8")
        self.assertIn('HEALTH_SUMMARY_FILE="${HEALTH_STATE_DIR}/healthcheck-summary.json"', content)
        self.assertIn('should_restart_gateway="$(jq -r \'.shouldRestartGateway // false\'', content)
        self.assertIn("detect_gateway_token_mismatch() {", content)
        self.assertIn("gateway token mismatch", content)
        self.assertIn("ocp gateway stop >/dev/null 2>&1 || true", content)
        self.assertIn("ocp gateway install --force >/dev/null 2>&1 || true", content)
        self.assertIn('if printf \'%s\' "${categories}" | grep -q "data_lag"; then', content)
        self.assertIn('if printf \'%s\' "${categories}" | grep -q "github_rate_limit"; then', content)

    def test_dashboard_exposes_health_sla_and_runtime_classification(self):
        data_py = DASHBOARD_DATA_PY.read_text(encoding="utf-8")
        html = DASHBOARD_HTML.read_text(encoding="utf-8")
        self.assertIn('DASHBOARD_DATA_SLA_MINUTES = read_env_int("DASHBOARD_DATA_SLA_MINUTES"', data_py)
        self.assertIn('"dashboardDataMaxAgeMinutes": DASHBOARD_DATA_SLA_MINUTES', data_py)
        self.assertIn("function detectRuntimeHealth(data)", html)
        self.assertIn("失败分类", html)


if __name__ == "__main__":
    unittest.main()
