# Security

## Secrets

Never commit:
- `.env`
- `openclaw.json` with real `appSecret` or token
- any GitHub PAT

## Rotation Checklist

If secrets were exposed:
1. Revoke old key/token in provider console
2. Generate new credentials
3. Update local `.env`
4. Reinstall with `bash scripts/install.sh`

## Minimal Access

- Use least-privilege GitHub token scopes
- Use dedicated Feishu app per environment
- Isolate profile with `OPENCLAW_PROFILE`
