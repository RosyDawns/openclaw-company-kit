# OpenClaw Company Kit

[English](README.en.md) | 中文

可发布、可安装、可演示的 OpenClaw 多智能体公司模板仓库。

面向“小团队 + 多角色 AI 协作”的工程化场景：
- 用 `scripts/launch.sh` 启动本地配置中心（`/setup`）
- 用 `scripts/install.sh` 生成并下发完整 profile/agent/dashboard 配置
- 用 `scripts/start.sh` 拉起网关、刷新循环、watchdog
- 用 `scripts/healthcheck.sh` 输出结构化健康分类

## 项目定位

这是一个把“多代理协同”落到可运维工程实践里的项目，而不是单纯 Prompt 集合。

它在仓库里同时提供：
- 多角色架构与调度规则（`engine/`）
- 控制平面 API 与配置中心（`scripts/control_server.py`, `server/`）
- 可视化控制台（`frontend/console-vue`）
- 安装/启动/巡检/备份恢复脚本（`scripts/`）
- 角色模板、workflow 模板、命令白名单模板（`templates/`）

## 核心能力

### 1) 角色架构与编排
- 9 个角色定义（`engine/role_config.json`）
- 主架构层：路由层（Dispatcher）-> 审核层（Reviewer）-> 执行层（Executor）
- 子层：`dispatcher_sub` / `executor_sub`
- 状态机流转：`DRAFT -> QUEUED -> RUNNING -> REVIEW -> APPROVED -> DONE`（含 `BLOCKED` / `REJECTED`）
- 审核关卡：支持 auto/manual/hybrid，支持按任务类型自动路由审核者
- Pipeline 节点类型：`TASK` / `REVIEW_GATE` / `FORK` / `JOIN`
- 灰度开关：`ORCHESTRATOR_ENABLED=1` 时 cron 可由编排引擎接管（`engine/cron_adapter.py`）

### 2) 控制平面（Control Server + API）
- 本地 HTTP 控制服务：`scripts/control_server.py`
- 认证：Bearer Token（`CONTROL_TOKEN` 或启动时自动生成临时 token）
- 配置 API + 异步任务执行（apply/restart）
- 任务历史与审计日志：
  - `control-task-history.jsonl`
  - `control-audit-log.jsonl`
- 当前注册 API 路由 24 条（分 9 组）：
  - config(3), service(3), task(1), kanban(2), monitor(3), officials(1), templates(3), skills(4), sessions(4)

### 3) 前端控制台
- Vue3 + TailwindCSS 前端工程：`frontend/console-vue`
- 8 个面板：
  - `setup`, `kanban`, `monitor`, `overview`, `officials`, `templates`, `skills`, `sessions`
- 构建产物存在时走 `/ui/*` 路由；不存在时自动回退旧版页面（`web/setup.html` + `dashboard/rd-dashboard`）

### 4) 运维可靠性
- Watchdog 自动巡检与重试：`scripts/watchdog.sh`
- 健康分类输出：`gateway_fault`, `gateway_auth_scope`, `data_lag`, `github_rate_limit`, `cron_failures`
- `healthcheck.sh` 按分类输出建议动作，并写 `healthcheck-summary.json`
- 日志轮转、PID 管理、网关 token mismatch 自修复
- 一键备份/恢复：`scripts/backup.sh`, `scripts/restore.sh`

### 5) Workflow 与模板系统
- 基础 cron 模板：`templates/jobs.template.json`（13 条基础任务）
- Workflow 任务包：
  - `default`
  - `requirement-review`
  - `bugfix`
  - `release-retro`
  - `code-sprint`
  - `incident-response`
  - `feature-delivery`
- 对应 prompt 模板（除 `default` 外均有扩展 prompt）

## 快速开始

### 0) 依赖要求

基础依赖：
- `openclaw`
- `node`（默认要求主版本 >= 22）
- `jq`
- `python3`
- `rsync`
- `gh`（可选降级：`OPENCLAW_ALLOW_NO_GH=1`）

### 1) 一键进入配置中心（推荐）

```bash
git clone https://github.com/RosyDawns/openclaw-company-kit.git
cd openclaw-company-kit
cp .env.example .env
bash scripts/launch.sh
```

默认访问：`http://127.0.0.1:8788/setup`

说明：
- `launch.sh` 会先做依赖预检
- 端口冲突时可自动探测可用端口（非交互模式）
- 仅启动控制中心，不会直接替你执行 install/start

### 2) 手动安装 + 启动

```bash
cp .env.example .env
# 编辑 .env，至少填：GROUP_ID / FEISHU_AI_APP_ID / FEISHU_AI_APP_SECRET

bash scripts/onboard-wrapper.sh
bash scripts/install.sh
bash scripts/start.sh
bash scripts/healthcheck.sh
```

### 3) Docker Demo（静态演示数据）

```bash
bash scripts/demo-up.sh
# 打开 http://127.0.0.1:8788
```

停止：

```bash
bash scripts/demo-down.sh
```

### 4) 生产部署

```bash
cp .env.example .env
cd deploy
DOMAIN=your-domain.com docker compose -f docker-compose.prod.yml up -d
```

更多细节见 [deploy/README.md](deploy/README.md)。

## 关键配置项

完整清单见 `.env.example`。下面是最常用项：

| 变量 | 是否必填 | 说明 |
|------|----------|------|
| `OPENCLAW_PROFILE` | 推荐 | profile 名，默认 `company` |
| `GROUP_ID` | 是 | 飞书群 ID |
| `FEISHU_AI_APP_ID` | 是 | 飞书应用 App ID |
| `FEISHU_AI_APP_SECRET` | 是 | 飞书应用 Secret |
| `PROJECT_PATH` | 推荐 | 项目本地路径 |
| `PROJECT_REPO` | 推荐 | GitHub 仓库（`owner/repo`） |
| `WORKFLOW_TEMPLATE` | 推荐 | workflow 包：`default`/`requirement-review`/`bugfix`/`release-retro`/`code-sprint`/`incident-response`/`feature-delivery` |
| `GH_TOKEN` | 推荐 | GitHub token（Issue/PR 同步和技能能力） |
| `MODEL_PRIMARY` | 可选 | 主模型配置 |
| `MODEL_SUBAGENT` | 可选 | 子代理低成本模型 |
| `CONTROL_TOKEN` | 强烈推荐 | 控制 API 固定 token（不填会每次启动生成临时 token） |

## 常用命令

| 命令 | 说明 |
|------|------|
| `make launch` | 启动本地配置中心（`/setup`） |
| `make install` | 安装配置、下发 agent 模板、同步 cron |
| `make bridge` | 向 `PROJECT_PATH` 下发 `ghissues_op` |
| `make start` | 启动服务（网关 + 刷新循环 + watchdog） |
| `make stop` | 停止本地循环服务 |
| `make health` | 健康检查并输出分类 |
| `make backup` | 备份 profile/agent/.env/可选任务摘要 |
| `make restore ARCHIVE=...` | 从备份归档恢复 |
| `make check` | Python 编译 + Ruff + JSON 校验 |
| `make test` | 运行测试集 |
| `make hook` | 安装 pre-commit hook |
| `make ui-install` | 安装 Vue 控制台依赖 |
| `make ui-build` | 构建 Vue 控制台 |
| `make ui-dev` | 启动 Vue 前端本地开发 |

## API 分组概览

控制服务运行后（默认 `127.0.0.1:8788`），常用接口：

- Config
  - `GET /api/config`
  - `POST /api/config/save`
  - `POST /api/config/apply`
- Service
  - `GET /api/preflight`（公开）
  - `GET /api/service/status`
  - `POST /api/service/restart`
- Task
  - `GET /api/task/{id}`
- Kanban
  - `GET /api/kanban`
  - `POST /api/kanban/move`
- Monitor
  - `GET /api/monitor/services`
  - `GET /api/monitor/metrics`
  - `GET /api/monitor/reviews`
- Officials
  - `GET /api/officials`
- Templates
  - `GET /api/templates`
  - `GET /api/templates/{name}`
  - `POST /api/templates/activate`
- Skills
  - `GET /api/skills`
  - `POST /api/skills/add`
  - `POST /api/skills/update/{name}`
  - `POST /api/skills/remove/{name}`
- Sessions
  - `GET /api/sessions`
  - `GET /api/sessions/stats`
  - `GET /api/sessions/export`
  - `GET /api/sessions/{id}`

## 目录结构

```text
engine/                编排引擎（状态机 / 审核关卡 / 分派 / pipeline / skill manager）
server/                控制平面后端（router / handlers / services / middleware）
scripts/               安装与运维脚本（launch/install/start/stop/health/watchdog）
templates/             角色模板、workflow 模板、exec-approvals 模板
frontend/console-vue/  新版 Vue 控制台前端
web/                   旧版 setup 页面（回退）
dashboard/rd-dashboard/旧版 dashboard 资源（回退）
deploy/                生产部署文件（Caddy / compose）
docker/                demo 容器入口与静态数据
examples/              使用示例
tests/                 测试集
documents/             本地私有文档目录（默认被 git 忽略，不同步远端）
```

## 安全与合规

- 不要提交 `.env`
- 不要提交真实密钥（`*_SECRET`, `GH_TOKEN`, `DISCORD_BOT_TOKEN`, `CONTROL_TOKEN`）
- 建议始终配置 `CONTROL_TOKEN`
- 命令执行权限通过 `exec-approvals.json` 控制（安装时下发模板）
- CI 已集成 gitleaks（密钥扫描）

## Release Strategy

| 通道 | 当前版本 | 定位 |
|------|----------|------|
| LTS（稳定） | `v0.6.x` | 稳定运行、安全补丁优先 |
| Latest（最新） | `v0.7.x` | 新能力优先，适合试点 |

## Upgrade Path

- `v0.5.x -> v0.6.x`（兼容升级）

```bash
make backup
git pull
make install
make start
make health
```

- `v0.6.x -> v0.7.x`（先看 CHANGELOG 的 BREAKING 标记）

```bash
BACKUP_INCLUDE_TASK_SUMMARY=1 BACKUP_TASK_SUMMARY_DAYS=7 make backup
git pull
make install
make start
make health
```

## 相关资料

- [CHANGELOG.md](CHANGELOG.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [deploy/README.md](deploy/README.md)
- [examples/README.md](examples/README.md)

注：项目文档/规划文档默认放在本地私有目录 `documents/`，并通过 `.gitignore` 排除，不上传远端。
