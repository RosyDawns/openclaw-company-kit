# Deployment

## 一键安装流程所涵盖的项

配置中心点击「初始化并启动」或「应用并重启」时，脚本会自动处理：

| 项 | 说明 | 脚本位置 |
|----|------|----------|
| 源配置路径 | 未设置 `SOURCE_OPENCLAW_CONFIG` 时，使用当前 profile 目录下的 `openclaw.json`（如 `~/.openclaw-zhiyun/openclaw.json`） | `install.sh` |
| 配置 schema | 写入与当前 OpenClaw CLI 兼容的 config（如 compaction 结构、校验方式） | `install.sh` |
| 网关安装与启动 | 启动前先执行 `gateway install`（安装 LaunchAgent），再 `gateway start`，减少 healthcheck 因网关未装而失败 | `start.sh` |

若 healthcheck 仍报网关不可达，请按 [Troubleshooting](troubleshooting.md#install-fails-with-gateway-connect-error) 手动执行 `gateway install` / `gateway start` 或 `doctor`。

---

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
