# OpenClaw Company Kit

可发布、可安装、可演示的 OpenClaw 多智能体公司模板仓库。

目标：让你的公司化 OpenClaw 配置像标准开源项目一样被他人安装使用，而不是只能在你本机跑。

## Features

- 7 角色研发公司模板（总监/产品/技术/开发/Reviewer/测试/增长）
- 飞书群路由 + 角色 cron 调度模板
- 研发驾驶舱（多视角 + 运行态 + 里程碑）
- 安装/启动/停止/健康检查脚本
- Docker Demo 模式（无 OpenClaw 也可先看效果）
- 文档、示例、测试、CI、Issue/PR 模板

## Repository Layout

- `scripts/`: install/start/stop/healthcheck/release-check
- `templates/`: 配置模板（cron、群提示词、公司关联）
- `dashboard/rd-dashboard/`: 驾驶舱与同步脚本
- `docker/`: demo 数据 + 容器入口
- `docs/`: 使用与架构文档
- `examples/`: 流程示例
- `tests/`: 基础单元测试

## Quick Start (Native)

### One-command bootstrap (recommended on new computer)

```bash
bash scripts/bootstrap.sh
```

This wizard will:
- initialize an OpenClaw profile
- ask for model provider + API key
- supports domestic providers (Moonshot/ZAI/MiniMax/Qianfan/Volcengine/BytePlus/Xiaomi/DeepSeek/Qwen)
- supports self-hosted custom models (OpenAI-compatible / Anthropic-compatible)
- ask for Feishu app/group settings
- generate `.env`
- run install + start automatically

### Manual mode

1. Create env file
```bash
cp .env.example .env
```

2. Edit required values in `.env`
- `GROUP_ID`
- `FEISHU_HOT_APP_ID`
- `FEISHU_HOT_APP_SECRET`
- `PROJECT_PATH`
- `PROJECT_REPO`

3. Install
```bash
bash scripts/install.sh
```

4. Start
```bash
bash scripts/start.sh
```

5. Verify
```bash
bash scripts/healthcheck.sh
```

Dashboard default:
- `http://127.0.0.1:8788`

## Quick Start (Docker Demo)

```bash
docker compose up --build -d
```

Open:
- `http://127.0.0.1:8788`

说明：Docker Demo 使用静态示例数据，不连接真实 OpenClaw/GitHub。

## Developer Workflow

Run full checks:
```bash
bash scripts/release-check.sh
```

Run tests only:
```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Stop local services:
```bash
bash scripts/stop.sh
```

## Publish to GitHub

```bash
git init
git add .
git commit -m "feat: openclaw company kit"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

## Security (Mandatory)

- Never commit `.env`
- Never commit real `appSecret` / `GH_TOKEN`
- Rotate secrets immediately if exposed

See: [docs/security.md](docs/security.md)

## Documentation

- [docs/getting-started.md](docs/getting-started.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/deployment.md](docs/deployment.md)
- [docs/troubleshooting.md](docs/troubleshooting.md)
- [ROADMAP.md](ROADMAP.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
