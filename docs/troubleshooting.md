# Troubleshooting

## Install fails with gateway connect error

Symptom:
- `gateway closed (1006)`

Reason:
- Profile config exists but gateway is unreachable in current environment.

Action:
```bash
openclaw --profile <profile> gateway status
openclaw --profile <profile> gateway start
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
