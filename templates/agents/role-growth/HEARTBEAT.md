# Heartbeat 检查清单

每次心跳执行以下检查，无异常则返回 HEARTBEAT_OK。

- 检查是否有 owner:role-growth 且 status:doing 的 Issue 超过 2 个（WIP 违规），若有则将最低优先级的改为 todo 并注释原因
- 检查每日转化分析是否在今天 18:00 前已产出，若未产出且已过时间则标记为延迟并上报 rd-company
- 检查上线效果复盘是否在本周三 11:00 前已产出，若未产出且已过时间则标记为延迟
- 检查 GitHub star/fork 趋势数据源是否可达，若不可达则标注"数据源异常"
- 如果一切正常，返回 HEARTBEAT_OK
