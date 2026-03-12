# Heartbeat 检查清单

每次心跳执行以下检查，无异常则返回 HEARTBEAT_OK。

- 检查是否有 status:blocked 的 Issue 超过 2 小时未处理，若有则通知群并标注阻塞原因和需要谁决策
- 检查是否有 PR 等待 review 超过 1 小时，若有则提醒 role-code-reviewer
- 检查最近 1 小时内 cron 任务是否有连续失败（同一任务失败 ≥ 2 次），若有则汇报任务名和错误摘要
- 检查 role-senior-dev 是否有 WIP 违规（同时 ≥ 2 个 doing），若有则提醒纠正
- 如果一切正常，返回 HEARTBEAT_OK
