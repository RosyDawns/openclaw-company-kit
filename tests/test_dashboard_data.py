"""Unit tests for dashboard_data.py command execution safety."""

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "dashboard" / "rd-dashboard" / "dashboard_data.py"

SPEC = importlib.util.spec_from_file_location("dashboard_data", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"failed to load module spec: {MODULE_PATH}")
dashboard_data = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dashboard_data)


class DashboardDataTests(unittest.TestCase):
    def test_run_cmd_list_executes(self):
        res = dashboard_data.run_cmd(["python3", "-c", "print('ok')"])
        self.assertTrue(res["ok"])
        self.assertEqual(res["stdout"], "ok")

    def test_run_cmd_string_does_not_invoke_shell_redirection(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            marker = Path(tmp_dir) / "marker.txt"
            res = dashboard_data.run_cmd(f"echo injected > {marker}")
            self.assertTrue(res["ok"])
            self.assertFalse(marker.exists())
            self.assertIn(">", res["stdout"])

    def test_read_control_task_metrics_aggregates_recent_rows(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "control-task-history.jsonl"
            now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows = [
                {
                    "id": "a1",
                    "name": "apply",
                    "status": "success",
                    "startedAt": now_text,
                    "finishedAt": now_text,
                    "durationSec": 3.0,
                },
                {
                    "id": "a2",
                    "name": "restart",
                    "status": "failed",
                    "startedAt": now_text,
                    "finishedAt": now_text,
                    "durationSec": 5.0,
                    "failedStep": "start",
                    "failedCode": 1,
                    "error": "boom",
                },
                {
                    "id": "old",
                    "name": "apply",
                    "status": "success",
                    "startedAt": "2000-01-01 00:00:00",
                    "finishedAt": "2000-01-01 00:00:00",
                    "durationSec": 10.0,
                },
            ]
            path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")

            metrics = dashboard_data.read_control_task_metrics(path=path, window_days=7)
            summary = metrics.get("summary") or {}
            self.assertEqual(summary.get("total"), 2)
            self.assertEqual(summary.get("success"), 1)
            self.assertEqual(summary.get("failed"), 1)
            self.assertEqual(summary.get("successRate"), 50.0)
            self.assertEqual(summary.get("avgDurationSec"), 4.0)

            fail_top = metrics.get("failuresByTask") or []
            self.assertTrue(any(x.get("name") == "restart" and x.get("count") == 1 for x in fail_top))
            latest = metrics.get("latestFailures") or []
            self.assertTrue(any(x.get("id") == "a2" for x in latest))

    def test_fetch_github_tracker_returns_fresh_cache_without_network(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            old_cache_dir = dashboard_data.DASHBOARD_CACHE_DIR
            old_ttl = dashboard_data.GITHUB_TRACKER_CACHE_TTL_SEC
            old_run_cmd = dashboard_data.run_cmd
            try:
                dashboard_data.DASHBOARD_CACHE_DIR = Path(tmp_dir)
                dashboard_data.GITHUB_TRACKER_CACHE_TTL_SEC = 600
                cached_payload = {
                    "ok": True,
                    "repo": "acme/repo",
                    "issues": [],
                    "issueStats": {"total": 0},
                    "byOwner": {},
                    "milestones": [],
                    "error": None,
                    "source": "github",
                    "cache": {},
                }
                cache_path = dashboard_data.repo_cache_path("github-tracker", "acme/repo")
                dashboard_data.write_json_cache(cache_path, cached_payload)

                def should_not_run_cmd(*_args, **_kwargs):
                    raise AssertionError("run_cmd should not run on fresh tracker cache hit")

                dashboard_data.run_cmd = should_not_run_cmd
                res = dashboard_data.fetch_github_tracker(
                    "acme/repo",
                    "gh",
                    {},
                    api_budget=dashboard_data.new_github_api_budget(20),
                )
                self.assertTrue(res.get("ok"))
                self.assertEqual(res.get("source"), "github-cache")
                self.assertTrue((res.get("cache") or {}).get("trackerCacheHit"))
            finally:
                dashboard_data.DASHBOARD_CACHE_DIR = old_cache_dir
                dashboard_data.GITHUB_TRACKER_CACHE_TTL_SEC = old_ttl
                dashboard_data.run_cmd = old_run_cmd

    def test_fetch_github_tracker_uses_stale_cache_when_budget_exhausted(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            old_cache_dir = dashboard_data.DASHBOARD_CACHE_DIR
            old_ttl = dashboard_data.GITHUB_TRACKER_CACHE_TTL_SEC
            old_run_cmd = dashboard_data.run_cmd
            try:
                dashboard_data.DASHBOARD_CACHE_DIR = Path(tmp_dir)
                dashboard_data.GITHUB_TRACKER_CACHE_TTL_SEC = 60
                cached_payload = {
                    "ok": True,
                    "repo": "acme/repo",
                    "issues": [],
                    "issueStats": {"total": 0},
                    "byOwner": {},
                    "milestones": [],
                    "error": None,
                    "source": "github",
                    "cache": {},
                }
                cache_path = dashboard_data.repo_cache_path("github-tracker", "acme/repo")
                stale_wrapper = {
                    "generatedAtMs": dashboard_data.now_ms() - (2 * 3600 * 1000),
                    "data": cached_payload,
                }
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(stale_wrapper, ensure_ascii=False), encoding="utf-8")

                def should_not_run_cmd(*_args, **_kwargs):
                    raise AssertionError("run_cmd should not run when budget already exhausted")

                dashboard_data.run_cmd = should_not_run_cmd
                api_budget = dashboard_data.new_github_api_budget(1)
                api_budget["used"] = 1

                res = dashboard_data.fetch_github_tracker("acme/repo", "gh", {}, api_budget=api_budget)
                self.assertTrue(res.get("ok"))
                self.assertEqual(res.get("source"), "github-cache-stale")
                self.assertTrue((res.get("cache") or {}).get("trackerStaleFallback"))
                self.assertTrue(api_budget.get("degraded"))
            finally:
                dashboard_data.DASHBOARD_CACHE_DIR = old_cache_dir
                dashboard_data.GITHUB_TRACKER_CACHE_TTL_SEC = old_ttl
                dashboard_data.run_cmd = old_run_cmd

    def test_fetch_github_tracker_schedule_cache_reduces_issue_view_calls(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            old_cache_dir = dashboard_data.DASHBOARD_CACHE_DIR
            old_tracker_ttl = dashboard_data.GITHUB_TRACKER_CACHE_TTL_SEC
            old_schedule_ttl = dashboard_data.GITHUB_ISSUE_SCHEDULE_CACHE_TTL_SEC
            old_run_cmd = dashboard_data.run_cmd
            try:
                dashboard_data.DASHBOARD_CACHE_DIR = Path(tmp_dir)
                dashboard_data.GITHUB_TRACKER_CACHE_TTL_SEC = 300
                dashboard_data.GITHUB_ISSUE_SCHEDULE_CACHE_TTL_SEC = 600

                issue_1_updated = "2026-03-14T10:00:00Z"
                issue_2_updated = "2026-03-14T11:00:00Z"
                schedule_cache_path = dashboard_data.repo_cache_path("github-issue-schedule", "acme/repo")
                dashboard_data.write_json_cache(
                    schedule_cache_path,
                    {
                        "issues": {
                            "2": {
                                "updatedAt": issue_2_updated,
                                "due": "2026-03-20",
                                "cachedAtMs": dashboard_data.now_ms(),
                            }
                        }
                    },
                )

                calls = []

                def fake_run_cmd(cmd, cwd=None, env=None):
                    del cwd, env
                    argv = list(cmd) if isinstance(cmd, list) else []
                    calls.append(argv)
                    if argv[:3] == ["gh", "issue", "list"]:
                        payload = [
                            {
                                "number": 1,
                                "title": "Issue One",
                                "state": "open",
                                "labels": [{"name": "status:todo"}],
                                "milestone": None,
                                "assignees": [],
                                "updatedAt": issue_1_updated,
                                "url": "https://example.com/1",
                            },
                            {
                                "number": 2,
                                "title": "Issue Two",
                                "state": "open",
                                "labels": [{"name": "status:doing"}],
                                "milestone": None,
                                "assignees": [],
                                "updatedAt": issue_2_updated,
                                "url": "https://example.com/2",
                            },
                        ]
                        return {"ok": True, "code": 0, "stdout": json.dumps(payload), "stderr": ""}
                    if argv[:3] == ["gh", "issue", "view"]:
                        number = argv[3] if len(argv) > 3 else ""
                        if str(number) == "1":
                            return {"ok": True, "code": 0, "stdout": "[SCHEDULE] Due: 2026-03-18", "stderr": ""}
                        return {"ok": True, "code": 0, "stdout": "", "stderr": ""}
                    if argv[:2] == ["gh", "api"]:
                        return {"ok": True, "code": 0, "stdout": "[]", "stderr": ""}
                    return {"ok": False, "code": 1, "stdout": "", "stderr": "unexpected command"}

                dashboard_data.run_cmd = fake_run_cmd
                res = dashboard_data.fetch_github_tracker(
                    "acme/repo",
                    "gh",
                    {},
                    api_budget=dashboard_data.new_github_api_budget(20),
                )

                issues = {x.get("number"): x for x in (res.get("issues") or [])}
                self.assertEqual((issues.get(1) or {}).get("scheduleDue"), "2026-03-18")
                self.assertEqual((issues.get(2) or {}).get("scheduleDue"), "2026-03-20")

                issue_view_calls = [x for x in calls if x[:3] == ["gh", "issue", "view"]]
                self.assertEqual(len(issue_view_calls), 1)
                cache_meta = res.get("cache") or {}
                self.assertEqual(cache_meta.get("scheduleCacheHits"), 1)
                self.assertEqual(cache_meta.get("scheduleRefreshed"), 1)
            finally:
                dashboard_data.DASHBOARD_CACHE_DIR = old_cache_dir
                dashboard_data.GITHUB_TRACKER_CACHE_TTL_SEC = old_tracker_ttl
                dashboard_data.GITHUB_ISSUE_SCHEDULE_CACHE_TTL_SEC = old_schedule_ttl
                dashboard_data.run_cmd = old_run_cmd

    def test_parse_auto_status_comment_body_supports_structured_fields(self):
        body = "\n".join(
            [
                "[AUTO-STATUS] merged-pr-12",
                "- Transition: status:doing -> status:done",
                "- Reason: detected merged PR reference",
                "- Evidence: pr #12 https://github.com/acme/repo/pull/12",
                "- EvidenceType: pr",
                "- EvidenceURL: https://github.com/acme/repo/pull/12",
                "- IssueURL: https://github.com/acme/repo/issues/34",
                "- SyncedAt: 2026-03-14 12:30:00 CST",
                '[AUTO-EVIDENCE] {"issueUrl":"https://github.com/acme/repo/issues/34","evidenceType":"pr","evidenceUrl":"https://github.com/acme/repo/pull/12","syncedAt":"2026-03-14 12:30:00 CST"}',
            ]
        )
        parsed = dashboard_data.parse_auto_status_comment_body(body)
        self.assertEqual(parsed.get("marker"), "merged-pr-12")
        self.assertEqual(parsed.get("evidenceType"), "pr")
        self.assertEqual(parsed.get("evidenceUrl"), "https://github.com/acme/repo/pull/12")
        self.assertEqual(parsed.get("issueUrl"), "https://github.com/acme/repo/issues/34")
        self.assertEqual(parsed.get("syncedAt"), "2026-03-14 12:30:00 CST")

    def test_build_role_evidence_chains_includes_issue_pr_commit_comment(self):
        github_tracker = {
            "issues": [
                {
                    "number": 101,
                    "title": "Fix login",
                    "url": "https://github.com/acme/repo/issues/101",
                    "state": "closed",
                    "status": "done",
                    "owners": ["role-senior-dev"],
                    "updatedAt": "2026-03-14 10:00",
                    "updatedAtMs": 1000,
                    "statusComment": {
                        "url": "https://github.com/acme/repo/issues/101#issuecomment-1",
                        "createdAt": "2026-03-14 09:50",
                        "createdAtMs": 900,
                        "marker": "merged-pr-88",
                        "transition": "status:doing -> status:done",
                    },
                }
            ]
        }
        issue_deltas = {
            "statusTransitions": [
                {
                    "number": 101,
                    "from": "doing",
                    "to": "done",
                    "updatedAt": "2026-03-14 09:45",
                }
            ]
        }
        github_timeline = {
            "prs": [
                {
                    "number": 88,
                    "title": "fix login crash",
                    "state": "merged",
                    "url": "https://github.com/acme/repo/pull/88",
                    "issueRefs": [101],
                    "mergedAt": "2026-03-14 09:40",
                    "mergedAtMs": 850,
                }
            ],
            "commits": [
                {
                    "sha": "abc1234",
                    "message": "fix: close #101",
                    "url": "https://github.com/acme/repo/commit/abc1234",
                    "issueRefs": [101],
                    "committedAt": "2026-03-14 09:30",
                    "committedAtMs": 800,
                }
            ],
        }

        chains = dashboard_data.build_role_evidence_chains(github_tracker, issue_deltas, github_timeline)
        self.assertIn("role-senior-dev", chains)
        items = (chains.get("role-senior-dev") or {}).get("items") or []
        item_types = {x.get("type") for x in items}
        self.assertIn("issue", item_types)
        self.assertIn("pr", item_types)
        self.assertIn("commit", item_types)
        self.assertIn("comment", item_types)
        for item in items:
            self.assertTrue(item.get("url"))
            self.assertEqual(item.get("issueNumber"), 101)


if __name__ == "__main__":
    unittest.main()
