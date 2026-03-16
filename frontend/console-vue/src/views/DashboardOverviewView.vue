<template>
  <section class="space-y-4">
    <div class="grid gap-4 lg:grid-cols-[1.25fr_0.9fr]">
      <article class="glass-panel animate-fade-up p-5">
        <div class="inline-flex items-center gap-2 rounded-full bg-orange-100 px-3 py-1 text-xs font-semibold tracking-wide text-orange-700">
          <span class="h-2 w-2 animate-pulse rounded-full bg-orange-600"></span>
          Cockpit Overview
        </div>
        <h2 class="mt-3 text-3xl font-bold text-slate-900">驾驶舱总览</h2>
        <p class="mt-2 text-sm text-slate-600">补齐旧版核心信息：执行链路、运行态、财务经营、里程碑、风险与证据。</p>
        <div class="mt-4 flex flex-wrap gap-2">
          <button class="rounded-xl bg-cyan-700 px-4 py-2 text-sm font-semibold text-white transition hover:-translate-y-0.5" @click="refreshNow">立即刷新</button>
          <RouterLink to="/dashboard/runtime" class="rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white transition hover:-translate-y-0.5">运行态页面</RouterLink>
          <RouterLink to="/setup" class="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5">返回配置中心</RouterLink>
        </div>
      </article>

      <article class="glass-panel animate-fade-up p-5" style="animation-delay: 120ms">
        <ul class="space-y-3 text-sm">
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">仓库</span><b>{{ data?.project?.repoSlug || '-' }}</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">分支</span><b>{{ data?.project?.branch || '-' }}</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">数据生成</span><b>{{ data?.generatedAt || '-' }}</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">上次刷新</span><b>{{ fetchedAt || '-' }}</b></li>
          <li class="flex items-center justify-between"><span class="text-slate-500">下次刷新</span><b>{{ remainSec }}s</b></li>
        </ul>
      </article>
    </div>

    <article v-if="error" class="glass-panel border border-rose-200 bg-rose-50/80 p-4 text-sm text-rose-700">
      数据加载失败：{{ error }}
    </article>

    <article class="glass-panel p-4">
      <h3 class="text-sm font-semibold text-slate-900">执行链路 KPI</h3>
      <div class="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div v-for="m in metrics" :key="m.key" class="animate-fade-up rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p class="text-xs font-semibold uppercase tracking-wider text-slate-500">{{ m.key }}</p>
          <p class="mt-2 text-3xl font-bold text-slate-900">{{ m.value }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ m.tip }}</p>
        </div>
      </div>
    </article>

    <div class="grid gap-4 xl:grid-cols-2">
      <article class="glass-panel p-4">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-slate-900">控制面执行质量（近 7 天）</h3>
          <StatusChip :status="controlSummary.failed > 0 ? 'warn' : 'ok'" :text="`成功率 ${controlSummary.successRate || 0}%`" />
        </div>
        <div class="mt-3 grid gap-2 md:grid-cols-3 text-xs">
          <div class="rounded-xl border border-slate-200 bg-white p-3">
            <b>总任务</b>
            <p class="mt-1 text-slate-500">{{ controlSummary.total || 0 }}</p>
          </div>
          <div class="rounded-xl border border-slate-200 bg-white p-3">
            <b>成功</b>
            <p class="mt-1 text-slate-500">{{ controlSummary.success || 0 }}</p>
          </div>
          <div class="rounded-xl border border-slate-200 bg-white p-3">
            <b>失败</b>
            <p class="mt-1 text-slate-500">{{ controlSummary.failed || 0 }}</p>
          </div>
        </div>
        <div class="mt-3 rounded-xl border border-slate-200 bg-white p-3">
          <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-500">失败 Top</h4>
          <ul class="mt-2 space-y-1 text-xs text-slate-600">
            <li v-for="f in controlFailures" :key="f.name">{{ f.name }} · {{ f.count }}</li>
            <li v-if="!controlFailures.length" class="text-slate-400">暂无失败项</li>
          </ul>
        </div>

        <div class="mt-3 rounded-xl border border-slate-200 bg-white p-3">
          <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-500">成功率趋势（按日）</h4>
          <ul class="mt-2 space-y-2 text-xs text-slate-600">
            <li v-for="d in controlDaily" :key="d.day">
              <div class="flex items-center justify-between">
                <b>{{ d.day }}</b>
                <span>{{ d.successRate || 0 }}%</span>
              </div>
              <div class="mt-1 h-2 rounded-full bg-slate-100">
                <div class="h-2 rounded-full bg-cyan-600" :style="{ width: `${Math.max(0, Math.min(100, Number(d.successRate || 0)))}%` }"></div>
              </div>
              <p class="mt-1 text-slate-500">任务 {{ d.total || 0 }} / 失败 {{ d.failed || 0 }} / 均时 {{ d.avgDurationSec || 0 }}s</p>
            </li>
            <li v-if="!controlDaily.length" class="text-slate-400">暂无趋势数据</li>
          </ul>
        </div>

        <div class="mt-3 rounded-xl border border-slate-200 bg-white p-3">
          <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-500">最近失败</h4>
          <ul class="mt-2 space-y-2 text-xs text-slate-600">
            <li v-for="item in controlLatestFailures" :key="item.id || item.finishedAt || item.name">
              <b>{{ item.name || "-" }}</b> · {{ item.finishedAt || "-" }}
              <p class="text-slate-500">步骤 {{ item.failedStep || "-" }} / 退出码 {{ item.failedCode ?? "-" }}</p>
              <p class="text-slate-500">{{ item.error || "-" }}</p>
            </li>
            <li v-if="!controlLatestFailures.length" class="text-slate-400">暂无失败事件</li>
          </ul>
        </div>
      </article>

      <article class="glass-panel p-4">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-slate-900">失败分类</h3>
          <StatusChip :status="runtime.level" :text="runtime.summary" />
        </div>
        <div class="mt-3 flex flex-wrap gap-2 text-xs">
          <span class="rounded-full border border-slate-200 bg-white px-2.5 py-1">数据年龄 {{ runtime.ageMin == null ? "-" : `${runtime.ageMin}m` }}</span>
          <span class="rounded-full border border-slate-200 bg-white px-2.5 py-1">SLA {{ runtime.slaMinutes || 15 }}m</span>
          <span class="rounded-full border border-slate-200 bg-white px-2.5 py-1">GitHub 预算 {{ runtimeBudgetText }}</span>
          <span class="rounded-full border px-2.5 py-1" :class="runtime.ghRateLimited ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'">
            {{ runtime.ghRateLimited ? "限流降级" : "预算正常" }}
          </span>
        </div>
        <ul class="mt-3 space-y-2" v-if="runtime.failures.length">
          <li v-for="f in runtime.failures" :key="f.category + f.summary" class="rounded-xl border border-slate-200 bg-white p-3">
            <div class="flex items-center justify-between"><b>{{ f.category }}</b><StatusChip :status="f.level" :text="f.level" /></div>
            <p class="mt-1 text-sm text-slate-600">{{ f.summary }}</p>
            <p class="mt-1 text-xs text-slate-500">建议：{{ f.action }}</p>
          </li>
        </ul>
        <div v-else class="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">当前未检测到失败分类。</div>
      </article>
    </div>

    <div class="grid gap-4 xl:grid-cols-3">
      <article class="glass-panel p-4 xl:col-span-2">
        <h3 class="text-sm font-semibold text-slate-900">财务经营</h3>
        <div class="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3 text-xs">
          <div class="rounded-xl border border-slate-200 bg-white p-3"><b>净收入</b><p class="mt-1 text-slate-500">{{ biz.netRevenue || 0 }}</p></div>
          <div class="rounded-xl border border-slate-200 bg-white p-3"><b>新增线索</b><p class="mt-1 text-slate-500">{{ biz.leads || 0 }}</p></div>
          <div class="rounded-xl border border-slate-200 bg-white p-3"><b>付费用户</b><p class="mt-1 text-slate-500">{{ biz.paidUsers || 0 }}</p></div>
          <div class="rounded-xl border border-slate-200 bg-white p-3"><b>转化率</b><p class="mt-1 text-slate-500">{{ percent(biz.leadToPaidRate) }}</p></div>
          <div class="rounded-xl border border-slate-200 bg-white p-3"><b>CAC</b><p class="mt-1 text-slate-500">{{ biz.cac || 0 }}</p></div>
          <div class="rounded-xl border border-slate-200 bg-white p-3"><b>ARPU</b><p class="mt-1 text-slate-500">{{ biz.arpu || 0 }}</p></div>
        </div>
      </article>

      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">里程碑</h3>
        <ul class="mt-3 space-y-2" v-if="milestones.length">
          <li v-for="m in milestones" :key="m.title || m.name" class="rounded-xl border border-slate-200 bg-white p-3">
            <div class="flex items-center justify-between">
              <b class="text-sm text-slate-900">{{ m.title || m.name || '-' }}</b>
              <span class="text-xs text-slate-500">{{ m.due || m.deadline || '-' }}</span>
            </div>
            <div class="mt-1">
              <StatusChip :status="m.status || 'warn'" :text="m.status || 'pending'" />
            </div>
            <div class="mt-2 h-2 rounded-full bg-slate-100">
              <div class="h-2 rounded-full bg-cyan-600" :style="{ width: `${Number(m.progress || 0)}%` }"></div>
            </div>
            <p class="mt-1 text-xs text-slate-500">{{ m.progress || 0 }}% · open {{ m.open || m.openIssues || 0 }} / closed {{ m.closed || m.closedIssues || 0 }}</p>
          </li>
        </ul>
        <div v-else class="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">暂无里程碑数据。</div>
      </article>
    </div>

    <div class="grid gap-4 xl:grid-cols-2">
      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">阻塞 / 风险摘要</h3>
        <ul class="mt-3 space-y-2">
          <li v-for="item in blockersAndRisks" :key="item.key" class="rounded-xl border border-slate-200 bg-white p-3">
            <div class="flex items-center justify-between"><b class="text-sm text-slate-900">{{ item.title }}</b><StatusChip :status="item.level" :text="item.level" /></div>
            <p class="mt-1 text-xs text-slate-500">{{ item.detail }}</p>
          </li>
          <li v-if="!blockersAndRisks.length" class="rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">暂无阻塞/风险。</li>
        </ul>
      </article>

      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">情报雷达</h3>
        <div class="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-xs">
          <b class="text-slate-900">{{ radarTitle || "暂无情报摘要" }}</b>
          <p class="mt-1 text-slate-500">{{ radarGeneratedAt || "-" }}</p>
          <ul class="mt-2 space-y-1 text-slate-600">
            <li v-for="row in radarHighlights" :key="row">{{ row }}</li>
            <li v-if="!radarHighlights.length" class="text-slate-400">暂无情报高亮</li>
          </ul>
        </div>
        <h3 class="mt-4 text-sm font-semibold text-slate-900">角色视角入口</h3>
        <div class="mt-3 grid gap-2 md:grid-cols-2">
          <RouterLink to="/dashboard/runtime" class="rounded-xl border border-violet-200 bg-violet-50 px-3 py-2 text-sm font-semibold text-violet-700 transition hover:-translate-y-0.5">运行态</RouterLink>
          <RouterLink v-for="role in roleCards" :key="role.id" :to="`/dashboard/${role.id}`" class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 hover:border-cyan-300">
            {{ role.label }} · {{ role.progress }}%
          </RouterLink>
        </div>
      </article>
    </div>

    <div class="grid gap-4 xl:grid-cols-2">
      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">Issue 状态</h3>
        <ul class="mt-3 space-y-2">
          <li v-for="issue in issueRows" :key="issue.number" class="rounded-xl border border-slate-200 bg-white p-3">
            <div class="flex items-start justify-between gap-2">
              <b class="text-sm text-slate-900">#{{ issue.number }} {{ issue.title }}</b>
              <StatusChip :status="issue.status" :text="issue.status || issue.state" />
            </div>
            <p class="mt-1 text-xs text-slate-500">{{ ownerText(issue) }} · {{ issue.updatedAt || '-' }}</p>
            <a :href="issue.url" target="_blank" rel="noreferrer" class="mt-2 inline-block text-xs font-semibold text-cyan-700 hover:underline">查看 Issue</a>
          </li>
        </ul>
      </article>

      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">活动流</h3>
        <ul class="mt-3 space-y-2">
          <li v-for="row in feedRows" :key="(row.time || '') + (row.title || '')" class="rounded-xl border border-slate-200 bg-white p-3">
            <div class="flex items-start justify-between gap-2"><b class="text-sm text-slate-900">{{ row.title || '-' }}</b><span class="text-xs text-slate-500">{{ row.time || '-' }}</span></div>
            <p class="mt-1 text-xs text-slate-500">{{ row.detail || '-' }}</p>
          </li>
        </ul>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive } from "vue";
import { RouterLink } from "vue-router";
import StatusChip from "../components/StatusChip.vue";
import { detectRuntimeHealth, groupIssues } from "../lib/dashboard";
import { ROLE_ORDER, roleLabel, normalizeRoleId } from "../lib/constants";

const state = reactive({
  data: null,
  loading: false,
  error: "",
  remainSec: 15,
  refreshSec: 15,
  pollTimer: null,
  tickTimer: null,
  fetchedAt: "",
});

function ownerText(issue) {
  const owners = Array.isArray(issue?.owners) ? issue.owners : [];
  if (!owners.length) return "未分配负责人";
  return owners.map((o) => roleLabel(normalizeRoleId(o))).join(" / ");
}

function percent(v) {
  const n = Number(v || 0);
  return `${Math.round(n * 10) / 10}%`;
}

const runtime = computed(() => detectRuntimeHealth(state.data || {}));

const metrics = computed(() => {
  const ov = state.data?.overview || {};
  const company = state.data?.company?.stats || {};
  const stats = state.data?.github?.issueStats || {};
  return [
    { key: "Open Issue", value: Number(stats.open || 0), tip: "待处理任务" },
    { key: "Blocked", value: Number(stats.blocked || 0), tip: "当前阻塞" },
    { key: "活跃角色", value: Number(company.activeAgents || 0), tip: "在线/近期活跃" },
    { key: "总任务", value: Number(ov.allJobs || 0), tip: "全部调度任务" },
  ];
});

const roleCards = computed(() => {
  const panel = Array.isArray(state.data?.agentPanel) ? state.data.agentPanel : [];
  const byId = {};
  for (const item of panel) byId[item.id] = item;
  return ROLE_ORDER.filter((id) => byId[id]).map((id) => ({
    id,
    label: roleLabel(id),
    progress: Number(byId[id]?.progress?.percent || 0),
  }));
});

const issueRows = computed(() => {
  const issues = Array.isArray(state.data?.github?.issues) ? state.data.github.issues : [];
  const grouped = groupIssues(issues);
  return [...grouped.blocked, ...grouped.doing, ...grouped.todo].slice(0, 12);
});

const feedRows = computed(() => (Array.isArray(state.data?.activityFeed) ? state.data.activityFeed.slice(0, 12) : []));

const controlSummary = computed(() => state.data?.controlTasks?.summary || {});
const controlFailures = computed(() => (Array.isArray(state.data?.controlTasks?.failuresByTask) ? state.data.controlTasks.failuresByTask.slice(0, 5) : []));
const controlDaily = computed(() => (Array.isArray(state.data?.controlTasks?.daily) ? state.data.controlTasks.daily.slice(0, 7) : []));
const controlLatestFailures = computed(() => (Array.isArray(state.data?.controlTasks?.latestFailures) ? state.data.controlTasks.latestFailures.slice(0, 6) : []));
const biz = computed(() => state.data?.businessMetrics || {});
const milestones = computed(() => (Array.isArray(state.data?.milestones) ? state.data.milestones.slice(0, 6) : []));
const radarTitle = computed(() => state.data?.businessRadar?.title || "");
const radarGeneratedAt = computed(() => state.data?.businessRadar?.generatedAt || "");
const radarHighlights = computed(() => (Array.isArray(state.data?.businessRadar?.highlights) ? state.data.businessRadar.highlights.slice(0, 6) : []));

const blockersAndRisks = computed(() => {
  const b = Array.isArray(state.data?.blockersBoard) ? state.data.blockersBoard : [];
  const r = Array.isArray(state.data?.risksBoard) ? state.data.risksBoard : [];
  const rows = [];
  b.forEach((group, idx) => {
    const items = Array.isArray(group?.items) ? group.items : [];
    items.slice(0, 2).forEach((text, itemIdx) => {
      rows.push({
        key: `b-${idx}-${itemIdx}-${group?.name || ""}`,
        title: group?.name || "阻塞项",
        detail: text || "-",
        level: "blocked",
      });
    });
  });
  r.forEach((group, idx) => {
    const items = Array.isArray(group?.items) ? group.items : [];
    items.slice(0, 2).forEach((text, itemIdx) => {
      rows.push({
        key: `r-${idx}-${itemIdx}-${group?.name || ""}`,
        title: group?.name || "风险项",
        detail: text || "-",
        level: "warn",
      });
    });
  });
  return rows.slice(0, 8);
});

const runtimeBudgetText = computed(() => {
  const budget = runtime.value?.ghBudget || {};
  return `${Number(budget.used || 0)}/${Number(budget.limit || 0)}`;
});

async function fetchData() {
  state.loading = true;
  state.error = "";
  try {
    const resp = await fetch(`/dashboard/dashboard-data.json?t=${Date.now()}`);
    if (!resp.ok) throw new Error(`读取 dashboard-data.json 失败: ${resp.status}`);
    state.data = await resp.json();
    state.fetchedAt = new Date().toLocaleTimeString();
  } catch (err) {
    state.error = err instanceof Error ? err.message : String(err);
  } finally {
    state.loading = false;
  }
}

async function refreshNow() {
  state.remainSec = state.refreshSec;
  await fetchData();
}

onMounted(async () => {
  await fetchData();
  state.tickTimer = setInterval(() => {
    state.remainSec = state.remainSec > 0 ? state.remainSec - 1 : state.refreshSec;
  }, 1000);
  state.pollTimer = setInterval(() => {
    refreshNow().catch(() => {});
  }, state.refreshSec * 1000);
});

onUnmounted(() => {
  if (state.tickTimer) clearInterval(state.tickTimer);
  if (state.pollTimer) clearInterval(state.pollTimer);
});

const data = computed(() => state.data);
const remainSec = computed(() => state.remainSec);
const fetchedAt = computed(() => state.fetchedAt);
const error = computed(() => state.error);
</script>
