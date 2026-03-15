# Troubleshooting

## Install fails with gateway connect error

Symptom:
- `gateway closed (1006)`
- Healthcheck: `Gateway: unreachable`, `LaunchAgent not installed`

Reason:
- Profile config exists but gateway is unreachable in current environment.
- On macOS the gateway runs as a LaunchAgent; it must be **installed** once, then **started**.

Action:
```bash
# 1. Install LaunchAgent for this profile (once per profile)
openclaw --profile <profile> gateway install

# 2. Start the gateway
openclaw --profile <profile> gateway start

# If "gateway start" says "not installed" but you already ran install, try:
openclaw --profile <profile> doctor
# or
openclaw --profile <profile> gateway restart

# 3. Re-sync cron (optional, after gateway is up)
bash scripts/install-cron.sh
```

If `openclaw --profile <profile> gateway status` contains `gateway token mismatch`:

```bash
openclaw --profile <profile> gateway stop
openclaw --profile <profile> gateway install --force
openclaw --profile <profile> gateway start
```

If `bash scripts/healthcheck.sh` reports `missing scope: operator.read`:

```bash
# 1) Repair gateway/client auth scopes
openclaw --profile <profile> doctor --fix --non-interactive --yes

# 2) Restart gateway service
openclaw --profile <profile> gateway install --force
openclaw --profile <profile> gateway start

# 3) Recheck health
bash scripts/healthcheck.sh
```

## Install interrupted or failed midway

Symptom:
- `bash scripts/install.sh` exits with error
- profile files appear half-written

Current behavior:
- `install.sh` now has built-in rollback.
- On failure it restores key artifacts (`openclaw.json`, agents directory, dashboard directory, exec approvals).

Action:
```bash
# 1) rerun install directly (safe to retry)
bash scripts/install.sh

# 2) if still failing, inspect the last error line and rollback logs
# logs are printed in terminal with prefix: [ROLLBACK]

# 3) validate runtime health after retry
bash scripts/healthcheck.sh
```

## Dashboard data not updating

```bash
bash scripts/healthcheck.sh
tail -n 80 ~/.openclaw-<profile>/logs/dashboard-refresh-loop.log
```

### Healthcheck classification mapping

`healthcheck.sh` now outputs classified failures and writes:

```bash
~/.openclaw-<profile>/run/healthcheck-summary.json
```

Main categories and actions:
- `gateway_fault`: restart gateway or rerun `bash scripts/start.sh`.
- `gateway_auth_scope`: gateway token scope is insufficient; run `openclaw doctor --fix` and re-install/start gateway.
- `cron_failures`: cron jobs are in error state; run `openclaw --profile <profile> cron list --all --json` and resync with `bash scripts/install-cron.sh`.
- `data_lag`: run `cd ~/.openclaw-<profile>/workspace/rd-dashboard && ./refresh.sh`, then检查 `dashboard-refresh-loop`。
- `github_rate_limit`: wait for rate-limit window, or increase cache/budget:
  - `OPENCLAW_GITHUB_TRACKER_CACHE_TTL_SEC`
  - `OPENCLAW_GITHUB_API_BUDGET`
  - `OPENCLAW_GITHUB_ISSUE_SCHEDULE_CACHE_TTL_SEC`

Optional tuning:
- `DASHBOARD_DATA_SLA_MINUTES` (default `15`)
- `WATCHDOG_ALERT_THROTTLE_SEC` (default `600`)

## GitHub sync unavailable

Check:
- `.env` has `GH_TOKEN`
- `gh auth status`
- repository slug in `PROJECT_REPO`
- target repo root has `./ghissues_op` (run `make bridge` to re-deploy)

If `launch.sh` stops at `missing command: gh`:

```bash
# macOS
brew install gh

# Ubuntu/Debian
sudo apt install gh
```

Temporary bypass (GitHub sync capabilities degrade):

```bash
OPENCLAW_ALLOW_NO_GH=1 bash scripts/launch.sh
```

## Feishu no message delivered

Check:
- app scopes are complete
- accountId in `.env` matches configured account
- target group ID is correct

## Control apply/restart traceability

Control server now writes structured audit logs for `apply/restart`:

```bash
~/.openclaw-<profile>/run/control-audit-log.jsonl
~/.openclaw-<profile>/run/control-task-history.jsonl
```

Quick check:

```bash
tail -n 30 ~/.openclaw-<profile>/run/control-audit-log.jsonl
tail -n 30 ~/.openclaw-<profile>/run/control-task-history.jsonl
```

If you need audit snapshots in backup archives, enable in `.env`:

```bash
BACKUP_INCLUDE_TASK_SUMMARY=1
BACKUP_TASK_SUMMARY_DAYS=7
```
