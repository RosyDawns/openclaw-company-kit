# Heartbeat 检查清单

每次心跳执行以下检查，无异常则返回 HEARTBEAT_OK。

- 检查是否有 owner:role-senior-dev 且 status:doing 的 Issue 超过 2 个（WIP 违规），若有则将最低优先级的改为 todo 并注释原因
- 检查是否有已提交的 PR 等待 review 超过 2 小时，若有则通过 sessions_send 通知 role-code-reviewer 催审
- 检查最近一次 git push 距今是否超过 4 小时（工作时间内），若是则标记为产出停滞并上报 rd-company
- 检查是否有 status:blocked 的 Issue 属于自己，若有则检查阻塞原因是否已有进展并更新评论
- 如果一切正常，返回 HEARTBEAT_OK
