# OpenClaw Company Kit

English | [中文](README.md)

A production-ready, installable, and demo-friendly multi-agent company template for OpenClaw.

This repo is designed for practical multi-role AI operations:
- `scripts/launch.sh` starts the local setup/control center (`/setup`)
- `scripts/install.sh` renders and deploys profile/agent/dashboard configs
- `scripts/start.sh` starts gateway + refresh loops + watchdog
- `scripts/healthcheck.sh` emits structured health classifications

## What This Project Is

This is not just a prompt collection. It is an operational multi-agent engineering kit.

The repository includes:
- Role architecture, dispatch, review, and orchestration logic (`engine/`)
- Control-plane API and setup server (`scripts/control_server.py`, `server/`)
- Console UI (`frontend/console-vue`)
- Installation and ops scripts (`scripts/`)
- Agent/workflow/approval templates (`templates/`)

## Core Capabilities

### 1) Role Architecture and Orchestration
- 9 role definitions (`engine/role_config.json`)
- Main layers: Dispatcher -> Reviewer -> Executor
- Sub-layers: `dispatcher_sub` / `executor_sub`
- State machine: `DRAFT -> QUEUED -> RUNNING -> REVIEW -> APPROVED -> DONE` (plus `BLOCKED` / `REJECTED`)
- Review gate supports auto/manual/hybrid modes with task-type based reviewer routing
- Pipeline node types: `TASK`, `REVIEW_GATE`, `FORK`, `JOIN`
- Feature flag: `ORCHESTRATOR_ENABLED=1` lets cron jobs be adapted by the orchestration engine (`engine/cron_adapter.py`)

### 2) Control Plane (Control Server + API)
- Local HTTP control service: `scripts/control_server.py`
- Auth: Bearer token (`CONTROL_TOKEN` or auto-generated ephemeral token)
- Config APIs + async task execution for apply/restart flows
- Task history and audit logs:
  - `control-task-history.jsonl`
  - `control-audit-log.jsonl`
- 24 registered API routes in 9 groups:
  - config(3), service(3), task(1), kanban(2), monitor(3), officials(1), templates(3), skills(4), sessions(4)

### 3) Console UI
- Vue3 + TailwindCSS frontend: `frontend/console-vue`
- 8 panels:
  - `setup`, `kanban`, `monitor`, `overview`, `officials`, `templates`, `skills`, `sessions`
- If UI build artifacts exist, routes go through `/ui/*`; otherwise the server falls back to legacy `web/setup.html` and `dashboard/rd-dashboard`

### 4) Reliability and Operations
- Watchdog auto-check and auto-recovery: `scripts/watchdog.sh`
- Health classification categories: `gateway_fault`, `gateway_auth_scope`, `data_lag`, `github_rate_limit`, `cron_failures`
- `healthcheck.sh` writes actionable classification summary (`healthcheck-summary.json`)
- Log rotation, PID-based process management, and gateway token mismatch repair
- One-command backup/restore: `scripts/backup.sh`, `scripts/restore.sh`

### 5) Workflow and Template System
- Base cron template: `templates/jobs.template.json` (13 base jobs)
- Workflow job packages:
  - `default`
  - `requirement-review`
  - `bugfix`
  - `release-retro`
  - `code-sprint`
  - `incident-response`
  - `feature-delivery`
- Prompt extensions exist for all non-default workflow packages

## Quick Start

### 0) Prerequisites

Required tools:
- `openclaw`
- `node` (major version >= 22 by default)
- `jq`
- `python3`
- `rsync`
- `gh` (optional if you set `OPENCLAW_ALLOW_NO_GH=1`)

### 1) Start Setup Center (Recommended)

```bash
git clone https://github.com/RosyDawns/openclaw-company-kit.git
cd openclaw-company-kit
cp .env.example .env
bash scripts/launch.sh
```

Default URL: `http://127.0.0.1:8788/setup`

Notes:
- `launch.sh` runs dependency preflight first
- In non-interactive mode it can auto-scan a fallback port on conflicts
- It starts the control center; it does not run install/start automatically

### 2) Manual Install + Start

```bash
cp .env.example .env
# Fill at least: GROUP_ID / FEISHU_AI_APP_ID / FEISHU_AI_APP_SECRET

bash scripts/onboard-wrapper.sh
bash scripts/install.sh
bash scripts/start.sh
bash scripts/healthcheck.sh
```

### 3) Docker Demo (Static Data)

```bash
bash scripts/demo-up.sh
# Open http://127.0.0.1:8788
```

Stop demo:

```bash
bash scripts/demo-down.sh
```

### 4) Production Deployment

```bash
cp .env.example .env
cd deploy
DOMAIN=your-domain.com docker compose -f docker-compose.prod.yml up -d
```

See [deploy/README.md](deploy/README.md) for details.

## Key Configuration

See `.env.example` for the full list. Most commonly used keys:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENCLAW_PROFILE` | Recommended | Profile name, default `company` |
| `GROUP_ID` | Yes | Feishu group ID |
| `FEISHU_AI_APP_ID` | Yes | Feishu app ID |
| `FEISHU_AI_APP_SECRET` | Yes | Feishu app secret |
| `PROJECT_PATH` | Recommended | Local project path |
| `PROJECT_REPO` | Recommended | GitHub repo (`owner/repo`) |
| `WORKFLOW_TEMPLATE` | Recommended | `default` / `requirement-review` / `bugfix` / `release-retro` / `code-sprint` / `incident-response` / `feature-delivery` |
| `GH_TOKEN` | Recommended | Token for GitHub sync/skill scenarios |
| `MODEL_PRIMARY` | Optional | Primary model override |
| `MODEL_SUBAGENT` | Optional | Lower-cost model for subagents |
| `CONTROL_TOKEN` | Strongly recommended | Stable API token (otherwise an ephemeral token is generated on startup) |

## Common Commands

| Command | Purpose |
|---------|---------|
| `make launch` | Start local setup/control center (`/setup`) |
| `make install` | Deploy configs, agent templates, and cron jobs |
| `make bridge` | Deploy `ghissues_op` into `PROJECT_PATH` |
| `make start` | Start runtime services (gateway + loops + watchdog) |
| `make stop` | Stop local loop services |
| `make health` | Run health checks with classifications |
| `make backup` | Backup profile/agent/.env and optional task summaries |
| `make restore ARCHIVE=...` | Restore from backup archive |
| `make check` | Python compile + Ruff + JSON validation |
| `make test` | Run test suite |
| `make hook` | Install pre-commit hook |
| `make ui-install` | Install Vue console dependencies |
| `make ui-build` | Build Vue console |
| `make ui-dev` | Start local Vue dev server |

## API Overview

When control server is running (default `127.0.0.1:8788`):

- Config
  - `GET /api/config`
  - `POST /api/config/save`
  - `POST /api/config/apply`
- Service
  - `GET /api/preflight` (public)
  - `GET /api/service/status`
  - `POST /api/service/restart`
- Task
  - `GET /api/task/{id}`
- Kanban
  - `GET /api/kanban`
  - `POST /api/kanban/move`
- Monitor
  - `GET /api/monitor/services`
  - `GET /api/monitor/metrics`
  - `GET /api/monitor/reviews`
- Officials
  - `GET /api/officials`
- Templates
  - `GET /api/templates`
  - `GET /api/templates/{name}`
  - `POST /api/templates/activate`
- Skills
  - `GET /api/skills`
  - `POST /api/skills/add`
  - `POST /api/skills/update/{name}`
  - `POST /api/skills/remove/{name}`
- Sessions
  - `GET /api/sessions`
  - `GET /api/sessions/stats`
  - `GET /api/sessions/export`
  - `GET /api/sessions/{id}`

## Repository Layout

```text
engine/                orchestration engine (state machine / review gate / dispatch / pipeline / skill manager)
server/                control-plane backend (router / handlers / services / middleware)
scripts/               install and ops scripts (launch/install/start/stop/health/watchdog)
templates/             agent templates, workflow templates, exec-approvals template
frontend/console-vue/  new Vue console UI
web/                   legacy setup page (fallback)
dashboard/rd-dashboard/legacy dashboard assets (fallback)
deploy/                production deployment files (Caddy / compose)
docker/                demo container entry and static data
examples/              usage examples
tests/                 test suite
documents/             local private docs folder (git-ignored by default)
```

## Security Notes

- Never commit `.env`
- Never commit real secrets (`*_SECRET`, `GH_TOKEN`, `DISCORD_BOT_TOKEN`, `CONTROL_TOKEN`)
- Strongly recommend setting `CONTROL_TOKEN`
- Command execution allowlist is controlled via `exec-approvals.json`
- CI includes gitleaks secret scanning

## Release Strategy

| Channel | Current | Positioning |
|---------|---------|-------------|
| LTS（稳定） | `v0.6.x` | Stability and security fixes first |
| Latest（最新） | `v0.7.x` | Faster feature iteration |

## Upgrade Path

- `v0.5.x -> v0.6.x` (compatible)

```bash
make backup
git pull
make install
make start
make health
```

- `v0.6.x -> v0.7.x` (review BREAKING notes in changelog first)

```bash
BACKUP_INCLUDE_TASK_SUMMARY=1 BACKUP_TASK_SUMMARY_DAYS=7 make backup
git pull
make install
make start
make health
```

## References

- [CHANGELOG.md](CHANGELOG.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [deploy/README.md](deploy/README.md)
- [examples/README.md](examples/README.md)

Note: project/planning docs are now intended for local private storage under `documents/`, excluded by `.gitignore` and not synced to remote.
