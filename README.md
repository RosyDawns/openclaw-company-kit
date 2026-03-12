# OpenClaw Company Kit

可发布、可安装、可演示的 OpenClaw 多智能体公司模板仓库。

目标：让你的公司化 OpenClaw 配置像标准开源项目一样被他人安装使用，而不是只能在你本机跑。

## Features

- 7 角色研发公司模板（总监/产品/技术/开发/Reviewer/测试/增长）
- 飞书群路由 + 角色 cron 调度模板
- 研发驾驶舱（多视角 + 运行态 + 里程碑）
- 每个角色独立 SOUL.md + AGENTS.md + MEMORY.md + HEARTBEAT.md + IDENTITY.md 配置
- 安装/启动/停止/健康检查脚本
- Docker Demo 模式（无 OpenClaw 也可先看效果）
- 文档、示例、测试、CI、Issue/PR 模板
- **共享工作区** `shared-context/` 跨代理协作（优先级/圆桌/产出/反馈）
- **安全加固** 每个角色细粒度 `tools.allow/deny` + `exec-approvals.json` 命令白名单
- **跨代理通信** `sessions_send/spawn` + 自动限制 pingpong 轮数
- **结构化记忆** 角色专属 MEMORY.md 表格模板 + `memoryFlush` 自动蒸馏
- **Gateway 自愈** `watchdog.sh` 指数退避重启 + 飞书告警
- **子代理成本优化** `MODEL_SUBAGENT` 委派任务用低成本模型
- **Discord 多通道** 可选 Discord 通道支持，与飞书并行
- **生产部署** Caddy TLS 反向代理 + Docker Compose 一键部署

## Repository Layout

- `scripts/`: install/start/stop/healthcheck/watchdog/release-check/onboard-wrapper
- `templates/`: 配置模板（cron、群提示词、exec-approvals、agent 角色文件）
- `dashboard/rd-dashboard/`: 驾驶舱与同步脚本
- `web/setup.html`: 分步配置中心页面
- `deploy/`: 生产部署（Caddyfile + docker-compose.prod.yml）
- `docker/`: demo 数据 + 容器入口
- `docs/`: 使用与架构文档
- `examples/`: 流程示例
- `tests/`: 基础单元测试

## Quick Start (Native)

### One-command launch (recommended on new computer)

```bash
bash scripts/launch.sh
```

终端会先自动检测环境依赖（Node.js≥22、openclaw CLI、jq、python3、rsync），全部通过后才询问端口号。

New flow:
- terminal checks environment dependencies with visual checklist
- asks one port
- opens web setup: first-time wizard or edit existing config
- click to initialize (onboard → install → start → healthcheck)
- dashboard at same port, jump back to setup center to edit and restart

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

Optional legacy CLI wizard (advanced):
```bash
bash scripts/bootstrap.sh
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
