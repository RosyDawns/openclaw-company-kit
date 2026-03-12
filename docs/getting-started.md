# Getting Started

## 1) Prerequisites

- OpenClaw installed
- `jq`, `python3`, `rsync`
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
