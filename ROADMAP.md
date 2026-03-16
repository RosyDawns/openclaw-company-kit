# Roadmap

## Version Channels

### LTS（稳定通道）`v0.6.x`
- 目标：生产可用、可运营、低变更风险。
- 变更策略：只接收安全修复、稳定性修复、文档与测试补丁。
- 代表能力：
  - 控制面默认认证、注入风险修复、安装失败回滚。
  - 任务成功率/失败分布可观测、健康检查分类与 SLA。
  - 流程模板包、角色证据链、控制面审计日志与备份摘要。

### Latest（最新通道）`v0.7.x`
- 目标：产品化扩展与功能迭代。
- 变更策略：允许结构升级，必要时引入破坏性变更。
- 代表方向：
  - 多项目看板切换。
  - 插件化流程/角色扩展。
  - 更细粒度的审计与历史查询能力。

## Release Rules

- 任一破坏性变更必须在 `CHANGELOG.md` 标记为 `BREAKING`。
- 每次版本发布必须给出升级路径和回滚路径。
- `release-check.sh` 与 CI smoke 必须通过后才可发布。

## Milestones

### v0.6 LTS（已完成）
- [x] 安全基线：shell/eval/shell=True 风险面收口。
- [x] 运维基线：控制任务指标、SLA 分类、watchdog 自愈。
- [x] 产品基线：流程模板化、配置中心安全渲染、证据链可追溯。
- [x] 质量基线：smoke job + release-check + 回归测试覆盖。
- [x] 编排引擎：状态机 + 审核关卡 + 流转编排器 + 任务分派。
- [x] 3 层角色架构：路由层 → 审核层 → 执行层 + 9 个角色 manifest。
- [x] 后端分层：Router + Handlers + Services + Middleware。
- [x] 前端面板系统：8 个模块化 Vue3 面板（看板/监控/角色/模板/技能/会话/配置/总览）。
- [x] Skill 管理器 + 3 个新 workflow 模板。
- [x] API 网关层：18 个端点 + 统一认证/分页/异常处理。

### v0.7 Latest（进行中）
- [ ] 多项目 dashboard 视图与切换能力。
- [ ] 历史数据归档与查询接口。
- [ ] 跨平台服务编排（macOS/Linux service units）。
- [ ] 更完整的发布分层（LTS/Latest 文档自动校验）。
- [ ] 编排引擎持久化（SQLite/文件存储替代内存状态）。
- [ ] Pipeline 可视化编辑器（前端拖拽式流程设计）。
- [ ] 角色能力自动发现与动态注册。
- [ ] 审核关卡多人会签与超时自动升级。

## Upgrade Flow

1. 升级前先执行 `make backup`（建议开启 `BACKUP_INCLUDE_TASK_SUMMARY=1`）。
2. 升级后执行 `make install && make start && make health && make check`。
3. 遇到回归时用 `make restore ARCHIVE=...` 回滚。
