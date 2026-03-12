# Deployment

## Option A: Native Host (recommended)

```bash
bash scripts/launch.sh
```

Then open setup page and apply config from browser.

or manual legacy flow:

```bash
bash scripts/bootstrap.sh
```

or fully manual:

```bash
bash scripts/install.sh
bash scripts/start.sh
```

Use this if you need live OpenClaw + GitHub integration.

## Option B: Docker Demo

```bash
docker compose up --build -d
```

Open:
- `http://127.0.0.1:8788`

This mode serves static demo data only.

## GitHub Release Steps

1. Ensure `.env` is not tracked.
2. Run local checks:
```bash
bash scripts/release-check.sh
```
3. Push tag:
```bash
git tag v0.1.0
git push origin v0.1.0
```
