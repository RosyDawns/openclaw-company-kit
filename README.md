# OpenClaw Company Kit

可发布、可安装、可演示的 OpenClaw 多智能体公司模板仓库。

一条命令完成安装，Web 配置中心按步填写，9 个智能体自动协同运转。

## Features

### 核心能力
- **9 角色智能体** — 总监 / 产品 / 技术总监 / 高级程序员 / Code Reviewer / 测试 / 增长 + 热搜 / AI 科技
- **飞书群路由** + 13 条角色 cron 调度（晨会 / 午间同步 / 晚间复盘 / 周计划 / 情报雷达 / 健康巡检）
- **研发驾驶舱** — 多视角 + 运行态 + 里程碑 + Issue 同步
- **Web 配置中心** — 6 步向导（端口 → 项目 → 模型 → 飞书 → Discord/子代理 → 应用）

### 多代理协同
- **共享工作区** `shared-context/` — 优先级 / 圆桌记录 / 角色产出 / 用户反馈
- **跨代理通信** `sessions_send` / `sessions_spawn` + pingpong 轮数限制
- **结构化记忆** 角色专属 MEMORY.md 表格模板 + `memoryFlush` 自动蒸馏
- **全角色心跳** 9 个角色独立 HEARTBEAT.md 健康检查

### 安全与可靠性
- **细粒度权限** 每角色 `tools.allow/deny` + `exec-approvals.json` 命令白名单
- **Gateway 自愈** `watchdog.sh` 指数退避重启（60s→30min）+ 飞书告警
- **日志轮转** 启动时自动清理超过 5MB 的日志
- **控制面审计** apply/restart 结构化审计日志（JSONL）
- **备份/恢复** `backup.sh` / `restore.sh` 一键归档配置与代理状态
- **API 认证** 可选 Bearer Token 保护配置中心 API

### 成本与部署
- **子代理成本优化** `MODEL_SUBAGENT` 委派任务用低成本模型（节省 40-60% token）
- **Discord 多通道** 可选 Discord 通道，与飞书并行
- **生产部署** Caddy 自动 TLS + Docker Compose 一键部署（多阶段构建）
- **跨平台** macOS / Linux 自动兼容（sed_inplace）

### 工程质量
- **CI 流水线** bash 语法 + ShellCheck + ruff Python lint + JSON 校验 + gitleaks 密钥扫描 + 20+ 单元测试
- **pre-commit hook** `make hook` 一键安装本地检查
- **Makefile** launch / install / start / stop / health / check / backup / restore / test

## Repository Layout

```
scripts/             安装 / 启动 / 停止 / 健康检查 / 备份恢复 / watchdog
templates/           配置模板（cron / 群提示词 / exec-approvals / 9 角色文件）
web/setup.html       6 步 Web 配置中心
dashboard/           研发驾驶舱 + Issue 同步
deploy/              生产部署（Caddyfile / docker-compose / Dockerfile）
docker/              Demo 模式（静态数据 + 容器入口）
tests/               单元测试
docs/                使用与架构文档
examples/            流程示例
Makefile             便捷命令入口
```

## Quick Start

### 方式一：一键启动（推荐）

```bash
git clone https://github.com/RosyDawns/openclaw-company-kit.git
cd openclaw-company-kit
bash scripts/launch.sh
```

终端自动检测环境（Node.js ≥ 22、OpenClaw CLI、jq、python3、rsync、gh），通过后输入端口号，浏览器打开 Web 配置中心按步填写即可。

### 方式二：手动配置

```bash
cp .env.example .env
# 编辑 .env 填入必填项（GROUP_ID / FEISHU_HOT_APP_ID / FEISHU_HOT_APP_SECRET / PROJECT_PATH / PROJECT_REPO）
make install
make start
make health
```

### 方式三：Docker Demo（无需 OpenClaw）

```bash
docker compose up --build -d
# 打开 http://127.0.0.1:8788
```

### 方式四：Docker 生产部署

```bash
cp .env.example .env && vi .env
cd deploy
DOMAIN=your-domain.com docker compose -f docker-compose.prod.yml up -d
```

详见 [deploy/README.md](deploy/README.md)。

## Release Strategy

| 通道 | 当前版本 | 定位 | 维护策略 |
|------|----------|------|----------|
| LTS（稳定） | `v0.6.x` | 安全与可运营优先，适合生产长期运行 | 仅接收安全修复、稳定性修复、文档补丁 |
| Latest（最新） | `v0.7.x` | 新能力优先，适合试点和功能验证 | 接收新特性，可能包含结构调整 |

变更分级约定：
- **兼容变更**：默认配置可继续运行，不要求迁移。
- **破坏性变更**：必须在 `CHANGELOG.md` 里标记 `BREAKING` 并给出迁移步骤。

## Upgrade Path

### `v0.5.x -> v0.6.x`（兼容升级）

```bash
make backup
git pull
cp .env.example .env.example.latest
# 对比新增变量（如 WORKFLOW_TEMPLATE / DASHBOARD_DATA_SLA_MINUTES / BACKUP_*）
make install
make start
make health
make check
```

### `v0.6.x -> v0.7.x`（可能含破坏性变更）

```bash
BACKUP_INCLUDE_TASK_SUMMARY=1 BACKUP_TASK_SUMMARY_DAYS=7 make backup
git pull
# 先阅读 CHANGELOG 的 BREAKING 与迁移章节
make install
make start
make health
```

若升级后异常，可直接回退到最近备份：

```bash
make restore ARCHIVE=backups/<your-backup>.tar.gz
make start
```

## Makefile 命令

| 命令 | 说明 |
|------|------|
| `make launch` | 一键启动（环境检测 + Web 配置） |
| `make install` | 安装配置到 profile |
| `make bridge` | 将 `ghissues_op` 下发到 `PROJECT_PATH` 项目根目录 |
| `make start` | 启动所有服务 |
| `make stop` | 停止所有服务 |
| `make health` | 健康检查 |
| `make check` | 发布前全量检查 |
| `make backup` | 备份配置 + 代理状态 |
| `make restore ARCHIVE=...` | 从备份恢复 |
| `make test` | 运行单元测试 |
| `make hook` | 安装 pre-commit hook |

## Environment Variables

关键变量（完整列表见 [.env.example](.env.example)）：

| 变量 | 必填 | 说明 |
|------|------|------|
| `GROUP_ID` | ✅ | 飞书群 ID |
| `FEISHU_HOT_APP_ID` | ✅ | 飞书应用 App ID |
| `FEISHU_HOT_APP_SECRET` | ✅ | 飞书应用 App Secret |
| `PROJECT_PATH` | ✅ | 项目本地路径 |
| `PROJECT_REPO` | ✅ | GitHub 仓库（org/repo） |
| `GH_TOKEN` | 推荐 | GitHub Token（gh-issues skill） |
| `MODEL_PRIMARY` | 可选 | 主模型（如 deepseek/deepseek-chat） |
| `MODEL_SUBAGENT` | 可选 | 子代理低成本模型 |
| `DISCORD_BOT_TOKEN` | 可选 | Discord Bot Token |
| `CONTROL_TOKEN` | 可选 | 配置中心 API 认证 Token |
| `REFRESH_INTERVAL` | 可选 | 驾驶舱刷新间隔（默认 300s） |
| `OPENCLAW_ALLOW_NO_GH` | 可选 | 允许缺少 gh CLI 启动（GitHub 同步能力降级） |
| `SYNC_PROJECT_GH_BRIDGE` | 可选 | 安装时是否自动下发 `ghissues_op` 到 `PROJECT_PATH`（默认 `1`） |
| `SYNC_PROJECT_GH_BRIDGE_STRICT` | 可选 | 下发失败是否让安装失败（默认 `0`，仅告警） |
| `BACKUP_INCLUDE_TASK_SUMMARY` | 可选 | 备份时包含近 N 天任务摘要与审计日志（默认关闭） |
| `BACKUP_TASK_SUMMARY_DAYS` | 可选 | 备份摘要窗口天数（默认 7） |

## Security

- **绝不** 提交 `.env` 文件
- **绝不** 提交真实的 `appSecret` / `GH_TOKEN` / `DISCORD_BOT_TOKEN`
- 密钥泄露后立即轮换
- CI 已集成 gitleaks 自动扫描
- 配置中心支持 `CONTROL_TOKEN` 认证保护

详见 [docs/security.md](docs/security.md)

## Documentation

- [docs/getting-started.md](docs/getting-started.md) — 快速上手
- [docs/architecture.md](docs/architecture.md) — 架构设计
- [docs/deployment.md](docs/deployment.md) — 部署指南
- [docs/troubleshooting.md](docs/troubleshooting.md) — 故障排查
- [deploy/README.md](deploy/README.md) — 生产部署
- [CHANGELOG.md](CHANGELOG.md) — 变更日志
- [ROADMAP.md](ROADMAP.md) — 路线图
- [CONTRIBUTING.md](CONTRIBUTING.md) — 贡献指南
