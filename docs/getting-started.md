# Getting Started

## 1) Prerequisites

- OpenClaw installed
- Node.js >= 22
- `jq`, `python3`, `rsync`
- `gh` (GitHub CLI)
- A Feishu app + group ID

## 2) One-command launch (recommended)

```bash
bash scripts/launch.sh
```

Flow:
- CLI asks only one port
- open browser setup page (`/setup`)
- complete step-by-step config
- click apply to run `stop -> install -> start`
- enter dashboard (`/dashboard/`) and reuse setup center for reconfiguration/restart

Legacy CLI wizard (optional):
```bash
bash scripts/bootstrap.sh
```

## 3) Manual setup (optional)

Configure Environment

```bash
cp .env.example .env
```

Required values:
- `GROUP_ID`
- `FEISHU_HOT_APP_ID`
- `FEISHU_HOT_APP_SECRET`
- `PROJECT_PATH`
- `PROJECT_REPO`
- `WORKFLOW_TEMPLATE` (`default` / `requirement-review` / `bugfix` / `release-retro`)

Optional (issue-sync):
- `SPRINT_LABEL` / `SPRINT_NAME`（默认按当前周自动生成）
- `MILESTONE_TITLE` / `MILESTONE_DUE` / `MILESTONE_DESC`
- `CRON_GUARD_TARGET_JOB_ID` 与 `CRON_PIPELINE_*_JOB_ID`（切换到你自己的 cron jobs）
- `OPENCLAW_GITHUB_TRACKER_CACHE_TTL_SEC` / `OPENCLAW_GITHUB_ISSUE_SCHEDULE_CACHE_TTL_SEC` / `OPENCLAW_GITHUB_API_BUDGET`
- `DASHBOARD_DATA_SLA_MINUTES`（dashboard-data 新鲜度阈值，默认 15 分钟）
- `WATCHDOG_ALERT_THROTTLE_SEC`（watchdog 告警节流，默认 600 秒）

## 3) Install

```bash
bash scripts/install.sh
```

## 4) Start Services

```bash
bash scripts/start.sh
```

## 5) Verify

```bash
bash scripts/healthcheck.sh
```

Dashboard default:
- `http://127.0.0.1:8788`

## 6) Stop

```bash
bash scripts/stop.sh
```
