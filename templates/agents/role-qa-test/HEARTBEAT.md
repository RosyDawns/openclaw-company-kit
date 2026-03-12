# Heartbeat 检查清单

每次心跳执行以下检查，无异常则返回 HEARTBEAT_OK。

- 检查是否有已合并的 PR 对应的 Issue 仍未标记 tested，若有则提醒自己补充测试结论
- 检查是否有 blocked-reason 包含"测试失败"或"缺陷"的 Issue 超过 24 小时未更新，若有则追踪修复进展
- 检查近 24 小时内关闭的 Issue 是否均有测试结论评论（pass/fail），若有遗漏则标记为测试缺口
- 检查是否有 label:bug 的 Issue 超过 48 小时未复现或未确认，若有则优先处理
- 如果一切正常，返回 HEARTBEAT_OK
