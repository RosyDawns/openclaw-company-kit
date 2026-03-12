# Heartbeat 检查清单

每次心跳执行以下检查，无异常则返回 HEARTBEAT_OK。

- 检查是否有 open PR 等待 review 超过 4 小时，若有则立即开始 review 并通过 sessions_send 通知 role-senior-dev 预估完成时间
- 检查是否有 owner:role-code-reviewer 的 doing Issue 超过 2 个（WIP 违规），若有则将最低优先级的改为 todo
- 检查最近 24 小时是否有已 merge 但未经 review 的 PR，若有则补充 post-merge review 并标注风险
- 检查是否有 status:blocked 的 Issue 属于自己，若有则检查阻塞原因是否已解除并更新
- 如果一切正常，返回 HEARTBEAT_OK
