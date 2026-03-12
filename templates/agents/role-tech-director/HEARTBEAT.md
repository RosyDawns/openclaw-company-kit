# Heartbeat 检查清单

每次心跳执行以下检查，无异常则返回 HEARTBEAT_OK。

- 检查是否有 P0/P1 Issue 缺少技术方案（无 comment 包含"技术方案"或"technical plan"），若有则标记为需方案评审
- 检查架构决策记录中是否有超过 7 天未更新的 open 状态项，若有则提醒补充进展
- 检查是否有标记为 tech-debt 的 Issue 超过 2 周未处理，汇报积压情况至 rd-company
- 检查是否有 P0/P1 Issue 缺少 DoD（Definition of Done），若有则提醒补充验收标准
- 如果一切正常，返回 HEARTBEAT_OK
