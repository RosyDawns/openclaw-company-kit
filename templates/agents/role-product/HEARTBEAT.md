# Heartbeat 检查清单

每次心跳执行以下检查，无异常则返回 HEARTBEAT_OK。

- 检查是否有 owner:role-product 且 status:blocked 的 Issue，若有则检查阻塞原因是否已有进展并更新评论
- 检查是否有需求 Issue 创建超过 48 小时仍无验收标准（缺少 acceptance-criteria label），若有则补充验收标准
- 检查本周是否有未分配负责人的新 Issue（无 owner label），若有则建议分配并通过 sessions_send 通知 rd-company
- 检查是否有 status:done 的 Issue 缺少产品验收确认评论，若有则进行验收或标注待验证
- 如果一切正常，返回 HEARTBEAT_OK
