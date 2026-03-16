import { normalizeRoleId } from "./constants";

function parseLocalTimeMs(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const ms = Date.parse(raw.replace(" ", "T"));
  return Number.isFinite(ms) ? ms : null;
}

export function detectRuntimeHealth(data) {
  const failures = [];
  const nowMs = Date.now();
  const maxAgeMin = Math.max(1, Number(data?.sla?.dashboardDataMaxAgeMinutes || 15));
  const generatedAtMs = parseLocalTimeMs(data?.generatedAt);
  const ageMin = generatedAtMs === null ? null : Math.max(0, Math.floor((nowMs - generatedAtMs) / 60000));

  if (ageMin === null) {
    failures.push({
      category: "data_lag",
      level: "warn",
      summary: "dashboard-data 时间戳解析失败",
      action: "检查 dashboard-data.json 的 generatedAt 格式",
    });
  } else if (ageMin > maxAgeMin) {
    failures.push({
      category: "data_lag",
      level: ageMin >= maxAgeMin * 2 ? "error" : "warn",
      summary: `dashboard-data 延迟 ${ageMin} 分钟（阈值 ${maxAgeMin}）`,
      action: "检查 dashboard-refresh-loop 并执行 refresh.sh",
    });
  }

  if (data?.github?.ok === false) {
    failures.push({
      category: "github_unavailable",
      level: "error",
      summary: "GitHub 数据源不可用",
      action: "检查 GH_TOKEN / gh auth / PROJECT_REPO",
    });
  }

  const ghErrors = [data?.github?.error, data?.github?.timeline?.error].filter(Boolean).join(" | ");
  const ghBudget = data?.github?.apiBudget || {};
  const ghRateLimited =
    Boolean(ghBudget.degraded) ||
    /rate limit|secondary rate limit|api rate limit exceeded/i.test(String(ghErrors || ""));
  if (ghRateLimited) {
    failures.push({
      category: "github_rate_limit",
      level: "warn",
      summary: "GitHub 接口触发限流或预算降级",
      action: "提高缓存 TTL / API 预算并等待窗口恢复",
    });
  }

  const cron = Array.isArray(data?.cronJobs) ? data.cronJobs : [];
  const broken = cron.filter((job) => {
    const s = String(job?.lastRunStatus || "").toLowerCase();
    const level = String(job?.level || "").toLowerCase();
    return s.includes("error") || s.includes("fail") || level === "error";
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
    return {
      level: "ok",
      summary: "运行健康，无失败分类",
      failures: [],
      ageMin,
      slaMinutes: maxAgeMin,
      ghRateLimited: false,
      ghBudget,
    };
  }

  const hasError = failures.some((x) => x.level === "error");
  return {
    level: hasError ? "error" : "warn",
    summary: hasError ? "存在高优先级故障" : "存在告警待处理",
    failures,
    ageMin,
    slaMinutes: maxAgeMin,
    ghRateLimited,
    ghBudget,
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
