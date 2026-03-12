# 研发驾驶舱（OpenClaw）

## 1) 生成数据

```bash
cd ~/.openclaw/workspace/rd-dashboard
./refresh.sh
```

## 2) 启动本地可视化

```bash
cd ~/.openclaw/workspace/rd-dashboard
python3 -m http.server 8788
```

打开：`http://127.0.0.1:8788`

## 3) 作为系统服务自动启动（已配置）

- 服务 1：`ai.openclaw.rd-dashboard`（常驻 HTTP 服务，开机/登录自启）
- 服务 2：`ai.openclaw.rd-dashboard-refresh`（每 5 分钟自动刷新 `dashboard-data.json`）

常用管理命令：

```bash
# 查看状态
uid=$(id -u)
launchctl print gui/${uid}/ai.openclaw.rd-dashboard
launchctl print gui/${uid}/ai.openclaw.rd-dashboard-refresh

# 手动重启服务
launchctl kickstart -k gui/${uid}/ai.openclaw.rd-dashboard
launchctl kickstart -k gui/${uid}/ai.openclaw.rd-dashboard-refresh
```

## 数据来源
- `~/.openclaw/openclaw.json`：群路由与 agent
- `~/.openclaw/cron/jobs.json`：调度任务与运行状态
- `team-status.json`：角色日常、进度、里程碑（可手动维护）
- `company-project.json`：公司与项目绑定（项目目录、仓库、关联智能体）
- `business-metrics.json`：商务经营数据（线索、转化、收入、退款、ARPU、CAC、回款周期）

## 经营数据配置（商务版）

在 `~/.openclaw/workspace/rd-dashboard/business-metrics.json` 维护真实经营数据：

```json
{
  "period": "2026-W11",
  "updatedAt": "2026-03-11 12:00:00",
  "currency": "CNY",
  "leads": 1260,
  "trialUsers": 338,
  "paidUsers": 58,
  "revenue": 52360,
  "refundAmount": 2680,
  "arpu": 903,
  "cac": 112,
  "cashInDays": 13.5,
  "notes": "可选备注"
}
```

字段说明：
- `period`：统计周期（例如周、月）
- `updatedAt`：数据更新时间（本地时区）
- `currency`：币种（默认 `CNY`）
- `leads` / `trialUsers` / `paidUsers`：漏斗人数
- `revenue` / `refundAmount`：收入与退款
- `arpu` / `cac`：单用户收入与获客成本（可不填，系统可回推）
- `cashInDays`：回款周期（天）

若文件缺失，驾驶舱会自动回退为“代理估算”口径，并在页面标注。

## 驾驶舱重点视图（重构后）
- 智能体状态总览：健康度、活跃度、会话数、最近活跃、阻塞数、进度
- 阻塞看板：按智能体聚合阻塞项（优先使用 GitHub issue 状态与截止日）
- 项目与 GitHub 关联：本地目录、分支、最新提交、脏文件、GitHub 登录状态
- 调度任务状态：OpenClaw 群任务 + launchd 系统服务统一展示
- 里程碑进度：优先读取 GitHub milestone（含 open/closed 数量）
- GitHub Issue 看板：实时展示负责人、状态、优先级、截止、更新时间
