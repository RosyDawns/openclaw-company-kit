# Architecture

## Runtime Layers

1. Channel Routing Layer
- Feishu group -> `rd-company`
- Role bots bound by account and cron

2. Scheduling Layer
- `openclaw cron` jobs for rituals and role sync
- `issue-sync.sh` for status reconciliation

3. Data Aggregation Layer
- `dashboard_data.py` reads OpenClaw config/cron/GitHub
- Produces `dashboard-data.json`

4. Presentation Layer
- `index.html` renders role views, runtime board, milestones

## Data Sources

- OpenClaw config: profile `openclaw.json`
- Cron state: `<profile>/cron/jobs.json`
- Team static: `team-status.json`
- GitHub: via `gh` and optional `GH_TOKEN`

## Mode Split

- Production mode: host OpenClaw + local dashboard scripts
- Demo mode: Docker serves static dashboard data snapshot
