<template>
  <section class="space-y-4">
    <div class="grid gap-4 lg:grid-cols-[1.25fr_0.9fr]">
      <article class="glass-panel animate-fade-up p-5">
        <div class="inline-flex items-center gap-2 rounded-full bg-orange-100 px-3 py-1 text-xs font-semibold tracking-wide text-orange-700">
          <span class="h-2 w-2 animate-pulse rounded-full bg-orange-600"></span>
          Cockpit Overview
        </div>
        <h2 class="mt-3 text-3xl font-bold text-slate-900">驾驶舱总览</h2>
        <p class="mt-2 text-sm text-slate-600">实时观察角色进展、Issue 状态、失败分类与调度异常。</p>
        <div class="mt-4 flex flex-wrap gap-2">
          <button class="rounded-xl bg-cyan-700 px-4 py-2 text-sm font-semibold text-white transition hover:-translate-y-0.5" @click="refreshNow">立即刷新</button>
          <RouterLink to="/setup" class="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5">返回配置中心</RouterLink>
        </div>
      </article>

      <article class="glass-panel animate-fade-up p-5" style="animation-delay: 120ms">
        <ul class="space-y-3 text-sm">
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">仓库</span><b>{{ data?.project?.repoSlug || '-' }}</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">分支</span><b>{{ data?.project?.branch || '-' }}</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">数据生成</span><b>{{ data?.generatedAt || '-' }}</b></li>
          <li class="flex items-center justify-between"><span class="text-slate-500">下次刷新</span><b>{{ remainSec }}s</b></li>
        </ul>
      </article>
    </div>

    <article class="glass-panel p-4">
      <h3 class="text-sm font-semibold text-slate-900">核心指标</h3>
      <div class="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div v-for="m in metrics" :key="m.key" class="animate-fade-up rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p class="text-xs font-semibold uppercase tracking-wider text-slate-500">{{ m.key }}</p>
          <p class="mt-2 text-3xl font-bold text-slate-900">{{ m.value }}</p>
        </div>
      </div>
    </article>

    <article class="glass-panel p-4">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold text-slate-900">失败分类</h3>
        <StatusChip :status="runtime.level" :text="runtime.summary" />
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

    <article class="glass-panel p-4">
      <h3 class="text-sm font-semibold text-slate-900">角色视角入口</h3>
      <div class="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <RouterLink v-for="role in roleCards" :key="role.id" :to="`/dashboard/${role.id}`" class="group rounded-2xl border border-slate-200 bg-white p-4 transition hover:-translate-y-1 hover:border-cyan-300 hover:shadow-lg">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h4 class="font-semibold text-slate-900">{{ role.label }}</h4>
              <p class="mt-1 text-xs text-slate-500">{{ role.summary }}</p>
            </div>
            <span class="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600">{{ role.progress }}%</span>
          </div>
          <p class="mt-3 text-xs text-cyan-700 group-hover:underline">进入视角页面</p>
        </RouterLink>
      </div>
    </article>

    <div class="grid gap-4 xl:grid-cols-2">
      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">Issue 状态</h3>
        <ul class="mt-3 space-y-2">
          <li v-for="issue in issueRows" :key="issue.number" class="rounded-xl border border-slate-200 bg-white p-3">
            <div class="flex items-start justify-between gap-2">
              <b class="text-sm text-slate-900">#{{ issue.number }} {{ issue.title }}</b>
              <StatusChip :status="issue.status" :text="issue.status || issue.state" />
            </div>
            <p class="mt-1 text-xs text-slate-500">{{ ownerText(issue) }}</p>
            <a :href="issue.url" target="_blank" rel="noreferrer" class="mt-2 inline-block text-xs font-semibold text-cyan-700 hover:underline">查看 Issue</a>
          </li>
        </ul>
      </article>

      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">活动流</h3>
        <ul class="mt-3 space-y-2">
          <li v-for="row in feedRows" :key="(row.time || '') + (row.title || '')" class="rounded-xl border border-slate-200 bg-white p-3">
            <div class="flex items-start justify-between gap-2">
              <b class="text-sm text-slate-900">{{ row.title || '-' }}</b>
              <span class="text-xs text-slate-500">{{ row.time || '-' }}</span>
            </div>
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
});

function ownerText(issue) {
  const owners = Array.isArray(issue?.owners) ? issue.owners : [];
  if (!owners.length) return "未分配负责人";
  return owners.map((o) => roleLabel(normalizeRoleId(o))).join(" / ");
}

const runtime = computed(() => detectRuntimeHealth(state.data || {}));

const metrics = computed(() => {
  const ov = state.data?.overview || {};
  const company = state.data?.company?.stats || {};
  return [
    { key: "启用任务", value: Number(ov.enabledJobs || 0) },
    { key: "异常任务", value: Number(ov.errorJobs || 0) },
    { key: "活跃角色", value: Number(company.activeAgents || 0) },
    { key: "平均进度", value: `${Number(company.avgProgress || 0)}%` },
  ];
});

const roleCards = computed(() => {
  const panel = Array.isArray(state.data?.agentPanel) ? state.data.agentPanel : [];
  const byId = {};
  for (const item of panel) byId[item.id] = item;
  return ROLE_ORDER.filter((id) => byId[id]).map((id) => ({
    id,
    label: roleLabel(id),
    summary: byId[id]?.progress?.summary || "暂无摘要",
    progress: Number(byId[id]?.progress?.percent || 0),
  }));
});

const issueRows = computed(() => {
  const issues = Array.isArray(state.data?.github?.issues) ? state.data.github.issues : [];
  const g = groupIssues(issues);
  return [...g.blocked, ...g.doing, ...g.todo].slice(0, 12);
});

const feedRows = computed(() => {
  return (Array.isArray(state.data?.activityFeed) ? state.data.activityFeed : []).slice(0, 12);
});

async function fetchData() {
  state.loading = true;
  state.error = "";
  try {
    const resp = await fetch(`/dashboard/dashboard-data.json?t=${Date.now()}`);
    if (!resp.ok) throw new Error(`读取 dashboard-data.json 失败: ${resp.status}`);
    state.data = await resp.json();
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
</script>
