# Contributing

Thanks for contributing to OpenClaw Company Kit.

## Development Flow

1. Create a branch from `main`.
2. Keep changes scoped (install, dashboard, docs, tests).
3. Run local checks before opening PR.
4. Open PR with clear change summary and rollback notes.

## Local Checks

```bash
bash scripts/release-check.sh
```

## Commit Guidelines

Use conventional style:
- `feat:` new capability
- `fix:` behavior fix
- `docs:` documentation only
- `chore:` tooling or maintenance

## Security Rules

- Never commit `.env`.
- Never commit real `appSecret`, `GH_TOKEN`, or any private key.
- If a secret is exposed, rotate immediately and remove from git history.

## PR Checklist

- [ ] Scripts pass `bash -n`
- [ ] JSON templates pass `jq`
- [ ] Python syntax/tests pass
- [ ] README/docs updated when behavior changes
