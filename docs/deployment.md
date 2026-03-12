# Deployment

## Option A: Native Host (recommended)

```bash
bash scripts/launch.sh
```

终端会自动检测 5 项依赖（Node.js≥22、openclaw CLI、jq、python3、rsync），检测通过后输入端口号，自动打开 web 配置中心。

- **首次配置**：填写所有参数（模型/飞书/GitHub 等） → 点击初始化（自动执行 onboard → install → start → healthcheck）
- **编辑配置**：修改参数 → 应用并重启

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
