import { normalizeRoleId } from "./constants";

export function detectRuntimeHealth(data) {
  const failures = [];
  const nowMs = Date.now();
  const generatedAtMs = Date.parse(String(data?.generatedAt || "").replace(" ", "T"));
  const maxAgeMin = Number(data?.sla?.dashboardDataMaxAgeMinutes || 15);

  if (Number.isFinite(generatedAtMs) && generatedAtMs > 0) {
    const ageMin = Math.floor((nowMs - generatedAtMs) / 60000);
    if (ageMin > maxAgeMin) {
      failures.push({
        category: "data_lag",
        level: "error",
        summary: `dashboard-data 延迟 ${ageMin} 分钟（阈值 ${maxAgeMin}）`,
        action: "检查 dashboard-refresh-loop 并执行 refresh.sh",
      });
    }
  }

  if (data?.github?.ok === false) {
    failures.push({
      category: "github_unavailable",
      level: "error",
      summary: "GitHub 数据源不可用",
      action: "检查 GH_TOKEN / gh auth / PROJECT_REPO",
    });
  }

  const cron = Array.isArray(data?.cronJobs) ? data.cronJobs : [];
  const broken = cron.filter((job) => {
    const s = String(job?.lastRunStatus || "").toLowerCase();
    return s.includes("error") || s.includes("fail");
  });
  if (broken.length > 0) {
    failures.push({
      category: "cron_failures",
      level: "warn",
      summary: `检测到 ${broken.length} 个 cron 异常任务`,
      action: "检查 cron 状态并重跑失败任务",
    });
  }

  if (failures.length === 0) {
    return { level: "ok", summary: "运行健康，无失败分类", failures: [] };
  }

  const hasError = failures.some((x) => x.level === "error");
  return {
    level: hasError ? "error" : "warn",
    summary: hasError ? "存在高优先级故障" : "存在告警待处理",
    failures,
  };
}

export function issueStatus(issue) {
  return String(issue?.status || issue?.state || "-").toLowerCase();
}

export function ownerMatchesRole(issue, roleId) {
  const role = normalizeRoleId(roleId);
  const owners = Array.isArray(issue?.owners) ? issue.owners : [];
  return owners.some((x) => normalizeRoleId(x) === role);
}

export function groupIssues(issues) {
  const rows = Array.isArray(issues) ? issues : [];
  const groups = { blocked: [], doing: [], todo: [], done: [], others: [] };
  for (const issue of rows) {
    const s = issueStatus(issue);
    if (s.includes("blocked")) groups.blocked.push(issue);
    else if (s.includes("doing")) groups.doing.push(issue);
    else if (s.includes("todo") || s.includes("open")) groups.todo.push(issue);
    else if (s.includes("done") || s.includes("closed")) groups.done.push(issue);
    else groups.others.push(issue);
  }
  return groups;
}
