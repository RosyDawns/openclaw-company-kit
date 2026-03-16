# Architecture

## 项目架构概览

OpenClaw Company Kit 采用分层架构，核心由三大子系统组成：

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Vue3)                       │
│   配置升级 · 看板 · 监控 · 角色 · 模板 · 技能 · 会话 · 总览  │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP / JSON
┌──────────────────────────▼──────────────────────────────┐
│               Server (API Gateway)                      │
│          Router → Handlers → Services → Data            │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│              Engine (编排引擎)                            │
│   StateMachine · ReviewGate · Orchestrator · Dispatcher │
└─────────────────────────────────────────────────────────┘
```

### 3 层角色架构

```
路由层 (Dispatcher)        审核层 (Reviewer)        执行层 (Executor)
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ rd-company       │   │ role-tech-director│   │ role-senior-dev  │
│ (任务分发/调度)   │──▶│ role-product      │──▶│ role-code-reviewer│
│                  │   │ (质量把关/决策)    │   │ role-qa-test     │
│                  │   │                  │   │ role-growth      │
│                  │   │                  │   │ hot-search       │
│                  │   │                  │   │ ai-tech          │
└──────────────────┘   └──────────────────┘   └──────────────────┘
```

---

## 核心组件

### engine/ — 编排引擎

| 模块 | 职责 |
|------|------|
| `models.py` | 数据模型：Task、TaskState、Transition |
| `state_machine.py` | 状态机：管理任务生命周期转换 |
| `review_gate.py` | 审核关卡：REVIEW 阶段的 approve/reject 逻辑 |
| `orchestrator.py` | 流转编排器：Pipeline 执行、步骤调度 |
| `dispatch.py` | 任务分派：按角色能力匹配分配任务 |
| `roles.py` | 角色注册表：3 层角色定义与能力声明 |
| `pipeline.py` | 流水线定义：多步骤任务串联 |
| `skill_manager.py` | Skill 管理器：安装/更新/卸载远程 Skill |
| `skill_manifest.py` | Skill 元数据：manifest 解析与校验 |
| `cron_adapter.py` | 定时任务适配器：与 OpenClaw cron 对接 |
| `file_lock.py` | 文件锁：跨进程安全读写 |

### server/ — 后端分层

```
server/
├── router.py              路由注册与路径匹配
├── static.py              静态资源服务
├── middleware/
│   ├── __init__.py
│   └── pagination.py      分页中间件
├── handlers/              请求处理器
│   ├── config.py          配置 CRUD
│   ├── service.py         服务状态/重启
│   ├── task.py            任务查询
│   ├── kanban.py          看板数据/拖拽
│   ├── monitor.py         监控指标/审核记录
│   ├── officials.py       角色列表
│   ├── templates.py       流程模板管理
│   ├── skills.py          Skill CRUD
│   └── sessions.py        会话记录/导出
└── services/              业务逻辑层
    ├── config_service.py
    ├── task_service.py
    └── health_service.py
```

### frontend/ — Vue3 面板系统

基于 Vue3 + TailwindCSS 构建，8 个模块化面板：

| 面板 | 路由 | 功能 |
|------|------|------|
| SetupView | `/setup` | 分组折叠式配置中心 |
| KanbanView | `/kanban` | 任务看板（拖拽流转） |
| MonitorView | `/monitor` | 服务监控 + 指标图表 |
| OfficialsView | `/officials` | 角色卡片 + 能力展示 |
| TemplatesView | `/templates` | 流程模板浏览/激活 |
| SkillsView | `/skills` | Skill 安装/管理 |
| SessionsView | `/sessions` | 会话历史/导出 |
| DashboardOverviewView | `/overview` | 驾驶舱总览 |

---

## 数据流

### 用户请求链路

```
用户 → 面板 UI → API 网关 (Router) → Handler → Service → Data 层
                                        │
                                   编排引擎 (Engine)
                                   ├── StateMachine   (状态流转)
                                   ├── ReviewGate     (审核判定)
                                   ├── Orchestrator   (步骤编排)
                                   └── Dispatcher     (角色分派)
```

### 任务状态流转

```
DRAFT ──▶ QUEUED ──▶ RUNNING ──▶ REVIEW ──▶ APPROVED ──▶ DONE
                        │           │
                        ▼           ▼
                     BLOCKED    REJECTED
                        │           │
                        └───▶ RUNNING ◀┘
```

有效转换表：

| 当前状态 | 可转换到 |
|----------|----------|
| DRAFT | QUEUED |
| QUEUED | RUNNING |
| RUNNING | REVIEW, BLOCKED |
| REVIEW | APPROVED, REJECTED |
| APPROVED | DONE |
| REJECTED | RUNNING |
| BLOCKED | RUNNING |
| DONE | （终态） |

---

## API 端点

所有 API 均通过 `scripts/control_server.py` 注册到 `server/router.py`。

### 配置管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 读取当前配置 |
| POST | `/api/config/save` | 保存配置 |
| POST | `/api/config/apply` | 应用配置并重启 |

### 服务控制
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/preflight` | 预检（无需认证） |
| GET | `/api/service/status` | 服务运行状态 |
| POST | `/api/service/restart` | 重启服务 |

### 看板
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/kanban` | 获取看板数据 |
| POST | `/api/kanban/move` | 移动任务卡片 |

### 监控
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/monitor/services` | 服务列表 |
| GET | `/api/monitor/metrics` | 运行指标 |
| GET | `/api/monitor/reviews` | 审核记录 |

### 角色
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/officials` | 角色列表与能力 |

### 流程模板
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/templates` | 模板列表 |
| GET | `/api/templates/{name}` | 模板详情 |
| POST | `/api/templates/activate` | 激活模板 |

### 任务
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/task/{id}` | 查询任务详情 |

### Skill
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/skills` | Skill 列表 |
| POST | `/api/skills/add` | 安装 Skill |
| POST | `/api/skills/update/{name}` | 更新 Skill |
| POST | `/api/skills/remove/{name}` | 卸载 Skill |

### 会话
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sessions` | 会话列表 |
| GET | `/api/sessions/stats` | 会话统计 |
| GET | `/api/sessions/export` | 导出会话 |
| GET | `/api/sessions/{id}` | 会话详情 |

---

## 模板与角色

### Workflow 模板（7 个）

| 模板 | 文件 |
|------|------|
| 默认 | `workflow-jobs.default.json` |
| 需求评审 | `workflow-jobs.requirement-review.json` |
| Bug 修复 | `workflow-jobs.bugfix.json` |
| 发布复盘 | `workflow-jobs.release-retro.json` |
| 代码冲刺 | `workflow-jobs.code-sprint.json` |
| 事故响应 | `workflow-jobs.incident-response.json` |
| 功能交付 | `workflow-jobs.feature-delivery.json` |

### 角色 Manifest（9 个）

每个角色目录下包含 `manifest.json`，声明角色元数据（层级、能力、触发条件）：

- `rd-company` — 总监（路由层）
- `role-tech-director` — 技术总监（审核层）
- `role-product` — 产品经理（审核层）
- `role-senior-dev` — 高级程序员（执行层）
- `role-code-reviewer` — Code Reviewer（执行层）
- `role-qa-test` — 测试工程师（执行层）
- `role-growth` — 增长运营（执行层）
- `hot-search` — 热搜情报（执行层）
- `ai-tech` — AI 科技（执行层）

---

## 数据源

| 来源 | 说明 |
|------|------|
| OpenClaw config | `~/.openclaw/openclaw.json` |
| Cron state | `<profile>/cron/jobs.json` |
| Team static | `team-status.json` |
| GitHub | `gh` CLI + `GH_TOKEN` |
| 编排状态 | `engine/` 内存状态 + 文件锁持久化 |

## 运行模式

| 模式 | 说明 |
|------|------|
| 生产模式 | OpenClaw + control_server + Vue3 面板 |
| Demo 模式 | Docker 静态数据快照 |
| 灰度模式 | `ORCHESTRATOR_ENABLED=0` 关闭编排引擎，仅使用基础功能 |
