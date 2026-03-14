# Changelog

## 0.6.0 - 2026-03-14

### Security & Reliability
- Removed `eval` path expansion risks in shell scripts and removed `shell=True` execution path in dashboard data builder.
- Tightened default incoming message source policy (`FEISHU_ALLOW_FROM` secure default).
- Control API now enforces token-based auth by default (ephemeral fallback token when unset).
- Added install rollback safeguards and clearer failure diagnostics.
- Added setup/dashboard XSS hardening: high-risk dynamic rendering switched to safe DOM rendering.

### Operability
- Added control task metrics (7d) and dashboard visualization (success rate, failure distribution, duration trend).
- Added GitHub tracker performance layer (TTL cache + API budget + stale fallback) and issue schedule cache.
- Added health SLA classification (`gateway_fault` / `data_lag` / `github_rate_limit`) and watchdog remediation mapping.
- Added workflow template packages (`default`, `requirement-review`, `bugfix`, `release-retro`) with one-click apply.
- Added role evidence chain view (Issue/PR/Commit/Comment URL + time) in dashboard role pages.

### Quality & Audit
- Added control API smoke tests in CI and release-check workflow.
- Added structured control audit log (`control-audit-log.jsonl`) for `apply/restart` step lifecycle.
- Added optional backup bundle for recent control task summary/history (`BACKUP_INCLUDE_TASK_SUMMARY`, `BACKUP_TASK_SUMMARY_DAYS`).

### Compatibility & Upgrade Notes
- Compatibility: `0.5.x -> 0.6.x` is backward-compatible by default.
- New optional env keys:
  - `WORKFLOW_TEMPLATE`
  - `DASHBOARD_DATA_SLA_MINUTES`
  - `OPENCLAW_GITHUB_TRACKER_CACHE_TTL_SEC`
  - `OPENCLAW_GITHUB_ISSUE_SCHEDULE_CACHE_TTL_SEC`
  - `OPENCLAW_GITHUB_ISSUE_EVIDENCE_CACHE_TTL_SEC`
  - `OPENCLAW_GITHUB_API_BUDGET`
  - `BACKUP_INCLUDE_TASK_SUMMARY`
  - `BACKUP_TASK_SUMMARY_DAYS`
- BREAKING: none.

## 0.5.0 - 2026-03-12

### P4 — Reliability & Completeness
- Full heartbeat coverage for all 9 agents (HEARTBEAT.md)
- Log rotation (5MB cap) on service start
- Watchdog graceful shutdown via SIGTERM trap
- Backup/restore scripts for openclaw.json + agent configs + .env
- Makefile convenience targets (launch/install/start/stop/health/backup/restore)
- release-check.sh now covers watchdog.sh, onboard-wrapper.sh, exec-approvals
- CI lint now blocks on real errors (shellcheck -S error, ruff E/F)

### P5 — DX, Security & Polish
- Unit tests for control_server.py (20 test cases: parse_env, normalize, shell_quote, profile_dir)
- Security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
- Optional Bearer token auth for API endpoints (--token / CONTROL_TOKEN env)
- Pre-commit hook (make hook) for local shell/JSON/Python checks
- CI gitleaks secret scanning
- Dashboard refresh interval configurable via REFRESH_INTERVAL env
- Docker multi-stage build for smaller production images
- CHANGELOG updated through P0-P5

## 0.4.0 - 2026-03-12

### P2 — Cost, Cross-platform, Multi-channel, Deploy
- MODEL_SUBAGENT for cheaper delegation model
- sed_inplace() for GNU/BSD cross-platform compatibility
- Discord channel support (DISCORD_BOT_TOKEN/GUILD_ID/CHANNEL_ID)
- deploy/Caddyfile for auto Let's Encrypt TLS reverse proxy
- deploy/docker-compose.prod.yml for one-command production deployment

### P3 — UI Completeness, CI Hardening, Docs
- Web UI "扩展通道" panel for Discord + MODEL_SUBAGENT config
- .gitignore expanded (node_modules, IDE, project_document, backups)
- README updated with P0-P2 feature highlights
- docker-compose dashboard switched from wrangler dev to control_server.py
- System health patrol cron job (every 4h)
- CI: shellcheck, ruff Python lint, exec-approvals validation

## 0.3.0 - 2026-03-12

### P0 — Shared Workspace, Security, Cross-agent Communication
- shared-context/ directory for cross-agent collaboration
- Per-agent tools.allow/deny + exec-approvals.json command whitelisting
- sessions_send/spawn for inter-agent messaging with pingpong limits
- AGENTS.md updated with shared context and communication sections

### P1 — Memory Architecture, Heartbeat, Gateway Watchdog
- Structured MEMORY.md with role-specific table templates
- memoryFlush enabled (softThresholdTokens=4000) for auto-distillation
- HEARTBEAT.md for rd-company, role-senior-dev, role-tech-director, role-qa-test
- healthcheck.sh: structured exit codes, gateway API check, cron failure detection
- watchdog.sh: auto-restart with exponential backoff (60s→30min), Feishu alerts

## 0.2.0 - 2026-03-12

- Added full project scaffolding (docs/examples/tests/docker)
- Added Docker demo mode with static dashboard dataset
- Added release-check script and unittest suite
- Added issue/PR templates and contribution roadmap docs

## 0.1.0 - 2026-03-12

- Initial installable company kit
- Role-based cron templates
- Dashboard + issue-sync packaging
