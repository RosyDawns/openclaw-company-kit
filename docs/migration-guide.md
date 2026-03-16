# 迁移指南

## 从 v0.5 升级到 v0.6

### 前置条件

- 备份当前数据：`make backup` 或 `bash scripts/backup.sh`
- Node.js 18+（前端构建需要）
- Python 3.9+

### 升级步骤

```bash
# 1. 备份当前环境
make backup

# 2. 更新代码
git pull origin main

# 3. 重新构建前端
cd frontend/console-vue && npm install && npm run build
cd ../..

# 4.（可选）启用编排引擎
#   在 .env 中设置：
#   ORCHESTRATOR_ENABLED=1

# 5. 验证
make test
make check

# 6. 重启服务
make stop && make start
make health
```

### 新增环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ORCHESTRATOR_ENABLED` | `0` | 编排引擎开关（0=关闭，1=开启） |

> v0.6 的编排引擎默认关闭，所有现有功能不受影响。开启后任务将经过完整的状态机流转和审核关卡。

### 新增 API 端点

以下端点在 v0.6 中新增，所有端点均需 Bearer Token 认证（除 `/api/preflight`）：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/task/{id}` | 查询任务详情 |
| GET | `/api/kanban` | 获取看板数据 |
| POST | `/api/kanban/move` | 移动任务卡片 |
| GET | `/api/monitor/services` | 服务列表 |
| GET | `/api/monitor/metrics` | 运行指标 |
| GET | `/api/monitor/reviews` | 审核记录 |
| GET | `/api/officials` | 角色列表与能力 |
| GET | `/api/templates` | 流程模板列表 |
| GET | `/api/templates/{name}` | 模板详情 |
| POST | `/api/templates/activate` | 激活模板 |
| GET | `/api/skills` | Skill 列表 |
| POST | `/api/skills/add` | 安装 Skill |
| POST | `/api/skills/update/{name}` | 更新 Skill |
| POST | `/api/skills/remove/{name}` | 卸载 Skill |
| GET | `/api/sessions` | 会话列表 |
| GET | `/api/sessions/stats` | 会话统计 |
| GET | `/api/sessions/export` | 导出会话 |
| GET | `/api/sessions/{id}` | 会话详情 |

### 目录结构变更

**新增目录与文件：**

```
engine/                     编排引擎（状态机、审核关卡、编排器、分派器）
├── models.py               数据模型
├── state_machine.py        状态机
├── review_gate.py          审核关卡
├── orchestrator.py         流转编排器
├── dispatch.py             任务分派
├── roles.py                角色注册表
├── pipeline.py             流水线定义
├── skill_manager.py        Skill 管理器
├── skill_manifest.py       Skill 元数据
├── cron_adapter.py         定时任务适配器
└── file_lock.py            文件锁

server/                     后端分层
├── router.py               路由注册
├── static.py               静态资源
├── middleware/              中间件
│   └── pagination.py       分页
├── handlers/               请求处理器（8 个模块）
└── services/               业务逻辑层

templates/agents/*/manifest.json    角色元数据（9 个）
templates/workflow-jobs.code-sprint.json
templates/workflow-jobs.incident-response.json
templates/workflow-jobs.feature-delivery.json
```

**前端新增面板：**

```
frontend/console-vue/src/views/
├── KanbanView.vue          看板面板
├── MonitorView.vue         监控面板
├── OfficialsView.vue       角色面板
├── TemplatesView.vue       模板面板
├── SkillsView.vue          技能面板
├── SessionsView.vue        会话面板
└── PlaceholderView.vue     占位面板
```

### 不兼容变更

**无**。v0.6 完全向后兼容 v0.5：

- 编排引擎默认关闭（`ORCHESTRATOR_ENABLED=0`）
- 原有 API 端点（`/api/config`、`/api/service/*`）行为不变
- 前端未构建时自动回退到旧版 `web/setup.html` 和 `dashboard/`
- 所有新增环境变量均有安全默认值

### 回滚方式

如果遇到问题：

**方式一：关闭编排引擎（推荐）**

```bash
# 在 .env 中设置
ORCHESTRATOR_ENABLED=0
# 重启服务
make stop && make start
```

**方式二：回退代码**

```bash
# 回退到 v0.5 标签
git checkout v0.5.0
make install && make start
```

**方式三：从备份恢复**

```bash
make restore ARCHIVE=backups/<your-backup>.tar.gz
make start
make health
```

---

## 从 v0.6 升级到 v0.7（计划中）

> v0.7 属于 Latest 通道，可能包含结构调整。升级前请阅读 CHANGELOG.md 的 BREAKING 部分。

```bash
BACKUP_INCLUDE_TASK_SUMMARY=1 BACKUP_TASK_SUMMARY_DAYS=7 make backup
git pull origin main
# 阅读 CHANGELOG BREAKING 章节
make install && make start && make health
```
