# OpenClaw Company Kit 30 天优化 Backlog（v0.5.0 -> v0.7.0）

日期：2026-03-14  
适用仓库：`openclaw-company-kit`

## 0. 当前进展（截至 2026-03-14）

- 已完成：`BK-01`、`BK-15`、`BK-02`、`BK-03`、`BK-16`、`BK-04`、`BK-05`、`BK-06`、`BK-07`、`BK-08`、`BK-09`、`BK-12`、`BK-11`、`BK-10`、`BK-13`、`BK-14`。
- 与长期路线 `improvement-roadmap-detailed.md` 对齐结果：
  - v0.6 安全主线：`eval` 注入面、`shell=True` 注入面、控制面默认认证、安装失败回滚已落地。
  - v0.6 可运营主线：控制任务 7 天指标埋点与 dashboard 可视化已落地。
  - v0.7 过渡项：GitHub 拉取性能（N+1 + 缓存 + API 预算降级）已完成第一阶段。
- 当前下一优先级：`Week 2/3/4 已完成项稳定性回归`。

## 1. 目标与边界

本计划只做三类事：

1. 补齐会被同类产品替代的核心短板：安全、可观测、稳定性。
2. 把“能跑”升级为“可运营”：可配置流程、可回溯执行证据、可复盘指标。
3. 不做大重构，优先 30 天内可交付的增量改进。

## 2. 北极星指标（先定指标再优化）

每周固定追踪以下指标（驾驶舱展示）：

1. 任务成功率：`success_tasks / total_tasks`（目标：>= 95%）。
2. 平均修复时长：Issue 从 `status:doing` 到 `status:done`（目标：较基线下降 30%）。
3. 单任务成本：token 或调用次数（目标：较基线下降 20%）。
4. 人工接管率：自动流程失败后人工介入比例（目标：<= 15%）。

## 3. 执行节奏（4 周）

### Week 1（第 1-7 天）：安全与基线

#### BK-01 消除 shell 注入风险
- 现状：`eval` 存在于路径处理与 bootstrap。
- 涉及文件：
  - `scripts/_common.sh`
  - `scripts/bootstrap.sh`
- 交付：
  - 去掉 `eval`，改为安全路径展开与直接赋值。
  - 增加对应单测或脚本级回归检查。
- 验收：
  - `bash scripts/release-check.sh` 通过。
  - 构造恶意输入不会执行命令。

#### BK-15 消除 `shell=True` 命令注入面
- 现状：`dashboard_data.py` 中 `run_cmd` 对字符串命令启用 `shell=True`。
- 涉及文件：
  - `dashboard/rd-dashboard/dashboard_data.py`
  - `tests/`（新增或补充回归测试）
- 交付：
  - `run_cmd` 强制走参数数组执行，默认 `shell=False`。
  - 所有调用点逐一兼容（管道/重定向场景拆分处理）。
- 验收：
  - 字符串拼接输入不会被 shell 解释执行。
  - dashboard 数据刷新链路保持可用。

#### BK-02 收紧默认消息来源权限
- 现状：Feishu `allowFrom` 默认 `["*"]`。
- 涉及文件：
  - `scripts/install.sh`
  - `.env.example`
  - `docs/security.md`
- 交付：
  - 默认按群或 allowlist 收口；保留显式开关用于兼容。
- 验收：
  - 默认安装后不再出现全开放来源配置。

#### BK-03 强制控制面 API 认证
- 现状：`CONTROL_TOKEN` 可选，易出现裸奔本地服务。
- 涉及文件：
  - `scripts/control_server.py`
  - `web/setup.html`
  - `.env.example`
- 交付：
  - 未配置 token 时生成临时 token 并在 UI 明确提醒。
  - API 请求支持统一注入 `Authorization`。
- 验收：
  - 无 token 请求 `/api/*` 返回 `401`（可配置地降级仅本机模式）。

#### BK-04 建立运营基线（指标埋点）
- 涉及文件：
  - `scripts/control_server.py`
  - `dashboard/rd-dashboard/dashboard_data.py`
  - `dashboard/rd-dashboard/index.html`
- 交付：
  - 记录任务执行时长、成功失败、最近失败原因。
  - 驾驶舱新增“最近 7 天任务成功率与失败分布”。
- 验收：
  - 打开 dashboard 可看到趋势，不再只有瞬时状态。

### Week 2（第 8-14 天）：性能与可靠性

#### BK-16 安装失败回滚机制
- 现状：安装过程中若失败，缺少统一清理与回滚路径。
- 涉及文件：
  - `scripts/bootstrap.sh`
  - `scripts/install.sh`
  - `docs/troubleshooting.md`
- 交付：
  - 增加失败 trap 与回滚函数，记录并清理本次创建产物。
  - 输出明确回滚日志与后续恢复指引。
- 验收：
  - 人工制造安装中断后，重试不会被脏状态阻塞。
  - 失败日志可定位到具体步骤与残留处理结果。

#### BK-05 消除 GitHub N+1 拉取
- 状态：`已完成（2026-03-14）`
- 现状：Issue 列表拉取后，对每个 open issue 追加请求评论内容（刷新慢、易限流）。
- 涉及文件：
  - `dashboard/rd-dashboard/dashboard_data.py`
  - `tests/test_dashboard_data.py`
- 交付：
  - 增加批量模式或缓存层（TTL 5-10 分钟）。
  - 增加 API 预算控制（超预算时优雅降级）。
  - 新增 `OPENCLAW_GITHUB_TRACKER_CACHE_TTL_SEC`、`OPENCLAW_GITHUB_ISSUE_SCHEDULE_CACHE_TTL_SEC`、`OPENCLAW_GITHUB_API_BUDGET` 三个参数。
- 验收：
  - `refresh.sh` 平均耗时下降 >= 40%（以 100 issue 规模为样本）。
  - 回归测试覆盖缓存命中、预算耗尽回退、issue schedule 缓存复用。

#### BK-06 issue-sync 参数化（去硬编码）
- 状态：`已完成（2026-03-14）`
- 现状：脚本内硬编码 milestone 标题、sprint 标签、cron job ID。
- 涉及文件：
  - `dashboard/rd-dashboard/issue-sync.sh`
  - `.env.example`
  - `docs/getting-started.md`
  - `tests/test_issue_sync_config.py`
- 交付：
  - 把 job ID、sprint 周期、里程碑命名抽到环境变量。
  - 默认按当前周自动生成 sprint 标签（例如 `sprint:w11` -> 动态）。
  - 支持 `SPRINT_LABEL / SPRINT_NAME / MILESTONE_* / CRON_*_JOB_ID` 覆盖。
- 验收：
  - 切换仓库/环境时无需改脚本源码。
  - `python3 -m unittest tests.test_issue_sync_config -v` 通过。

#### BK-07 统一依赖预检
- 状态：`已完成（2026-03-14）`
- 现状：`launch.sh` 检测 Node>=22，但通用 `check_cmds` 不包含 Node。
- 涉及文件：
  - `scripts/_common.sh`
  - `scripts/launch.sh`
  - `scripts/install.sh`
  - `scripts/start.sh`
  - `.env.example`
  - `docs/getting-started.md`
  - `tests/test_dependency_preflight.py`
- 交付：
  - 预检入口统一到一处，避免“某脚本能过，另一个脚本失败”。
  - `check_cmds` 统一检查：`openclaw/node/jq/python3/rsync/gh`，并校验 `node>=22`（可用 `OPENCLAW_NODE_MIN_MAJOR` 覆盖）。
- 验收：
  - 任何入口脚本的依赖检测结果一致。
  - `python3 -m unittest tests.test_dependency_preflight -v` 通过。

#### BK-08 健康检查加入 SLA 判定
- 状态：`已完成（2026-03-14）`
- 涉及文件：
  - `scripts/healthcheck.sh`
  - `scripts/watchdog.sh`
  - `dashboard/rd-dashboard/index.html`
  - `dashboard/rd-dashboard/dashboard_data.py`
  - `.env.example`
  - `docs/getting-started.md`
  - `docs/troubleshooting.md`
  - `tests/test_health_sla.py`
- 交付：
  - 增加数据新鲜度阈值（如 dashboard-data 超过 N 分钟算降级）。
  - 失败分类：网关故障/数据滞后/GitHub 限流。
  - watchdog 根据分类执行差异化动作：网关故障自动重启；数据滞后触发 refresh 自愈；限流走节流告警。
- 验收：
  - 告警能直接指向修复动作，不再只有“失败”。
  - `python3 -m unittest tests.test_health_sla -v` 通过。

### Week 3（第 15-21 天）：产品化与可配置流程

#### BK-09 场景模板化（首批 3 个）
- 状态：`已完成（2026-03-14）`
- 目标模板：
  - 需求评审流
  - Bug 修复流
  - 发布复盘流
- 涉及文件：
  - `templates/jobs.template.json`
  - `templates/group-system-prompt.txt`
  - `web/setup.html`
  - `templates/workflow-jobs.*.json`
  - `templates/workflow-prompt.*.txt`
  - `scripts/install.sh`
  - `scripts/install-cron.sh`
  - `scripts/control_server.py`
  - `.env.example`
  - `tests/test_workflow_templates.py`
- 交付：
  - 配置中心支持选择“流程模板包”并一键应用。
  - `WORKFLOW_TEMPLATE` 支持：`default / requirement-review / bugfix / release-retro`。
  - install/install-cron 会按模板包渲染群提示词与模板 cron 作业（统一 `模板-流程-*` 作业名，切换模板可直接覆盖）。
- 验收：
  - 新项目可 10 分钟内完成模板化初始化。
  - `python3 -m unittest tests.test_workflow_templates -v` 通过。

#### BK-10 角色执行证据标准化
- 状态：`已完成（2026-03-14）`
- 涉及文件：
  - `dashboard/rd-dashboard/issue-sync.sh`
  - `dashboard/rd-dashboard/dashboard_data.py`
  - `dashboard/rd-dashboard/index.html`
  - `tests/test_dashboard_data.py`
  - `tests/test_issue_sync_config.py`
- 交付：
  - 统一证据结构（Issue/PR/Commit/Comment URL + 时间）。
  - 驾驶舱支持按角色查看证据链。
- 验收：
  - 任意“done”状态都能追溯到证据链接。

#### BK-11 配置中心安全渲染收口
- 状态：`已完成（2026-03-14）`
- 现状：有多处 `innerHTML` 动态渲染。
- 涉及文件：
  - `web/setup.html`
  - `dashboard/rd-dashboard/index.html`
  - `tests/test_xss_hardening.py`
- 交付：
  - 高风险节点改为 DOM API + `textContent` 渲染。
  - 仅保留必要模板片段并集中封装。
- 验收：
  - 基础 XSS 用例无法注入执行。

### Week 4（第 22-30 天）：质量闭环与发布能力

#### BK-12 增加端到端 smoke tests
- 状态：`已完成（2026-03-14）`
- 涉及文件：
  - `tests/`（新增 `test_smoke_*.py`）
  - `scripts/release-check.sh`
  - `.github/workflows/ci.yml`
- 交付：
  - 模拟最小安装-启动-健康检查链路。
  - 对控制面 API 增加接口测试（`/api/config`、`/api/preflight`、`/api/service/status`）。
  - 增加 `/api/config/apply` 与 `/api/service/restart` 链路步骤冒烟验证（stop/install/start/healthcheck）。
- 验收：
  - CI 中新增 smoke job，失败可阻断合并。
  - `python3 -m unittest discover -s tests -p 'test_smoke_*.py' -v` 通过（受限环境可 skip）。

#### BK-13 监控与审计日志归档
- 状态：`已完成（2026-03-14）`
- 涉及文件：
  - `scripts/control_server.py`
  - `scripts/backup.sh`
  - `scripts/restore.sh`
  - `tests/test_control_server.py`
  - `tests/test_backup_restore_audit.py`
  - `.env.example`
  - `README.md`
  - `docs/troubleshooting.md`
- 交付：
  - 把关键操作（apply/restart）输出为结构化日志。
  - 备份包可选包含近 7 天任务日志摘要。
- 验收：
  - 故障回放时可定位“谁在什么时候触发了什么任务”。

#### BK-14 发布分层与版本节奏
- 状态：`已完成（2026-03-14）`
- 涉及文件：
  - `CHANGELOG.md`
  - `ROADMAP.md`
  - `README.md`
  - `tests/test_release_policy_docs.py`
- 交付：
  - 约定 LTS 与最新版本说明。
  - 给出升级路径（兼容变更与破坏性变更）。
- 验收：
  - 用户可按文档完成从旧版本到新版本升级。

## 4. 任务优先级（建议执行顺序）

已完成链路：`BK-01 -> BK-15 -> BK-02 -> BK-03 -> BK-16 -> BK-04 -> BK-05 -> BK-06 -> BK-07 -> BK-08 -> BK-09 -> BK-12 -> BK-11 -> BK-10 -> BK-13 -> BK-14`  
下一阶段顺序：`Week 2/3/4 已完成项稳定性回归`

## 5. 本周可立即开工的 5 项（最小闭环）

1. Week 2/3/4 已完成项稳定性回归（含 smoke + watchdog + audit + release docs）。  
2. BK-11 已完成项回归（配置中心与 dashboard XSS 渲染安全基线）。  
3. BK-10 已完成项回归（角色证据链结构与展示一致性）。  
4. BK-13 已完成项回归（控制面审计日志 + 备份摘要链路）。  
5. BK-14 已完成项回归（LTS/Latest 分层与升级路径文档可执行性）。  

## 6. 当前代码事实（用于排期依据）

1. `dashboard_data.py` 体量持续增长（> 2000 行），性能与模块拆分仍是后续重点。  
2. `issue-sync.sh` 体量较大（约 1200+ 行），并含多处环境耦合常量。  
3. 单测已覆盖安全修复、安装回滚、控制面鉴权、GitHub 缓存预算、依赖预检一致性、健康分类与 SLA 判定、流程模板包、控制面 smoke API 等关键路径（当前 `59` 项，受限环境 smoke 可跳过）。  
4. 本计划已与长期路线 v0.6 核心项保持一致，后续重心转向参数化、SLA 与模板化能力。  
