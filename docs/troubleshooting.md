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

## Dashboard data not updating

```bash
bash scripts/healthcheck.sh
tail -n 80 ~/.openclaw-<profile>/logs/dashboard-refresh-loop.log
```

## GitHub sync unavailable

Check:
- `.env` has `GH_TOKEN`
- `gh auth status`
- repository slug in `PROJECT_REPO`

## Feishu no message delivered

Check:
- app scopes are complete
- accountId in `.env` matches configured account
- target group ID is correct
