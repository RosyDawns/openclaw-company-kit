# 工具和能力

## 内置能力

- 增长分析 — 转化漏斗、留存、活跃度分析
- 指标追踪 — DAU/转化率/新增用户等关键指标
- 报告生成 — 每日转化分析、上线效果复盘

## 子服务能力（来自 hot-search）

- 热搜数据采集 — 实时热搜榜单抓取
- 趋势分析 — 热点话题趋势识别与追踪
- 热点追踪 — 持续监控特定话题热度变化

> hot-search 作为 role-growth 的 executor_sub 子服务，数据能力通过本角色统一对外暴露。

## 外部能力引用

### hot-search 热搜监控
- 能力：热搜数据采集、趋势分析
- 调用方式：通过 hot-search 子服务获取实时热搜数据
- 数据格式：JSON，包含 platform, keyword, rank, trend 字段

## Available Skills

### gh-issues

GitHub Issue and PR management. Requires `GH_TOKEN` or `gh auth login`.

Common operations:
- Create/update/close issues
- Review and merge PRs
- Query issue status and labels
