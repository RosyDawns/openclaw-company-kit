<template>
  <section class="space-y-4">
    <div class="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
      <article class="glass-panel animate-fade-up p-5">
        <div class="inline-flex items-center gap-2 rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold tracking-wide text-violet-700">
          <span class="h-2 w-2 animate-pulse rounded-full bg-violet-600"></span>
          Runtime View
        </div>
        <h2 class="mt-3 text-3xl font-bold text-slate-900">运行态</h2>
        <p class="mt-2 text-sm text-slate-600">专注调度任务、动态流、数据源、服务健康与连接状态。</p>
        <div class="mt-4 flex flex-wrap gap-2">
          <RouterLink to="/dashboard" class="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5">返回总览</RouterLink>
          <button class="rounded-xl bg-cyan-700 px-4 py-2 text-sm font-semibold text-white transition hover:-translate-y-0.5" @click="refreshNow">立即刷新</button>
        </div>
      </article>

      <article class="glass-panel animate-fade-up p-5" style="animation-delay: 120ms">
        <ul class="space-y-3 text-sm">
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">数据生成</span><b>{{ data?.generatedAt || '-' }}</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">刷新倒计时</span><b>{{ remainSec }}s</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">仓库</span><b>{{ data?.project?.repoSlug || '-' }}</b></li>
          <li class="flex items-center justify-between"><span class="text-slate-500">分支</span><b>{{ data?.project?.branch || '-' }}</b></li>
        </ul>
      </article>
    </div>

    <article class="glass-panel p-4">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold text-slate-900">服务健康 · 失败分类</h3>
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
      <div v-else class="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">当前无故障分类。</div>
    </article>

    <div class="grid gap-4 xl:grid-cols-2">
      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">调度任务状态</h3>
        <div v-if="cronRows.length" class="mt-3 overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table class="min-w-full text-left text-xs text-slate-600">
            <thead class="bg-slate-50 text-slate-500">
              <tr>
                <th class="px-3 py-2">任务</th>
                <th class="px-3 py-2">Agent</th>
                <th class="px-3 py-2">状态</th>
                <th class="px-3 py-2">计划</th>
                <th class="px-3 py-2">下次</th>
                <th class="px-3 py-2">最近执行</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="job in cronRows" :key="job.id || (job.name + job.schedule)" class="border-t border-slate-100">
                <td class="px-3 py-2 font-semibold text-slate-900">{{ job.name || "-" }}</td>
                <td class="px-3 py-2">{{ job.agentId || "-" }}</td>
                <td class="px-3 py-2">
                  <StatusChip :status="job.level || job.lastRunStatus" :text="job.level || job.lastRunStatus || '-'" />
                </td>
                <td class="px-3 py-2">{{ job.schedule || "-" }}</td>
                <td class="px-3 py-2">{{ job.enabled ? (job.nextRun || "-") : "已停用" }}</td>
                <td class="px-3 py-2">{{ job.lastRunStatus || "-" }} / {{ job.lastDeliveryStatus || "-" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">暂无调度任务数据。</div>
      </article>

      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">动态流</h3>
        <ul class="mt-3 space-y-2" v-if="feedRows.length">
          <li v-for="row in feedRows" :key="(row.time || '') + (row.title || '')" class="rounded-xl border border-slate-200 bg-white p-3">
            <div class="flex items-start justify-between gap-2">
              <b class="text-sm text-slate-900">{{ row.title || '-' }}</b>
              <span class="text-xs text-slate-500">{{ row.time || '-' }}</span>
            </div>
            <p class="mt-1 text-xs text-slate-500">{{ row.detail || '-' }}</p>
          </li>
        </ul>
        <div v-else class="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">暂无动态流。</div>
      </article>
    </div>

    <div class="grid gap-4 xl:grid-cols-3">
      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">数据源</h3>
        <div class="mt-3 flex flex-wrap gap-2">
          <span v-for="(value, key) in dataSources" :key="key" class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">{{ key }}: {{ value }}</span>
        </div>
      </article>

      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">项目链接</h3>
        <ul class="mt-3 space-y-2 text-xs text-slate-600">
          <li>仓库: {{ data?.project?.repoSlug || '-' }}</li>
          <li>分支: {{ data?.project?.branch || '-' }}</li>
          <li>工作区: {{ data?.project?.path || '-' }}</li>
          <li>GitHub Auth: {{ data?.githubAuth?.ok ? 'ok' : 'failed' }}</li>
        </ul>
      </article>

      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">Issue 统计</h3>
        <ul class="mt-3 space-y-1 text-xs text-slate-600">
          <li>open: {{ stats.open || 0 }}</li>
          <li>doing: {{ stats.doing || 0 }}</li>
          <li>blocked: {{ stats.blocked || 0 }}</li>
          <li>done: {{ stats.done || 0 }}</li>
          <li>overdue: {{ stats.overdue || 0 }}</li>
        </ul>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive } from "vue";
import { RouterLink } from "vue-router";
import StatusChip from "../components/StatusChip.vue";
import { detectRuntimeHealth } from "../lib/dashboard";

const state = reactive({
  data: null,
  remainSec: 15,
  refreshSec: 15,
  tickTimer: null,
  pollTimer: null,
});

const runtime = computed(() => detectRuntimeHealth(state.data || {}));
const cronRows = computed(() => (Array.isArray(state.data?.cronJobs) ? state.data.cronJobs.slice(0, 20) : []));
const feedRows = computed(() => (Array.isArray(state.data?.activityFeed) ? state.data.activityFeed.slice(0, 16) : []));
const dataSources = computed(() => state.data?.dataSources || {});
const stats = computed(() => state.data?.github?.issueStats || {});
const runtimeBudgetText = computed(() => {
  const budget = runtime.value?.ghBudget || {};
  return `${Number(budget.used || 0)}/${Number(budget.limit || 0)}`;
});

async function fetchData() {
  const resp = await fetch(`/dashboard/dashboard-data.json?t=${Date.now()}`);
  if (!resp.ok) throw new Error(`读取 dashboard-data.json 失败: ${resp.status}`);
  state.data = await resp.json();
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
