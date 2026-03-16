<template>
  <section class="space-y-6">
    <!-- Stats Cards -->
    <div>
      <div class="mb-3 flex items-center justify-between">
        <h3 class="text-sm font-semibold uppercase tracking-wide text-slate-500">统计概览</h3>
        <div class="flex rounded-lg border border-slate-200 bg-white/60 p-0.5 text-xs">
          <button
            v-for="p in periods"
            :key="p.key"
            class="rounded-md px-3 py-1 font-medium transition-colors"
            :class="activePeriod === p.key ? 'bg-cyan-700 text-white shadow-sm' : 'text-slate-500 hover:text-slate-700'"
            @click="switchPeriod(p.key)"
          >
            {{ p.label }}
          </button>
        </div>
      </div>

      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div class="glass-panel p-4">
          <p class="text-xs font-medium text-slate-500">{{ periodLabel }}任务数</p>
          <p class="mt-1 text-2xl font-bold text-slate-900">{{ stats.total ?? '—' }}</p>
        </div>
        <div class="glass-panel p-4">
          <p class="text-xs font-medium text-slate-500">成功率</p>
          <p class="mt-1 text-2xl font-bold text-emerald-600">{{ stats.successRate ?? '—' }}</p>
          <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              class="h-full rounded-full bg-emerald-500 transition-all duration-500"
              :style="{ width: stats.successRate || '0%' }"
            ></div>
          </div>
        </div>
        <div class="glass-panel p-4">
          <p class="text-xs font-medium text-slate-500">平均耗时</p>
          <p class="mt-1 text-2xl font-bold text-slate-900">{{ stats.avgDuration ?? '—' }}</p>
        </div>
        <div class="glass-panel p-4">
          <p class="text-xs font-medium text-slate-500">最长任务</p>
          <p class="mt-1 truncate text-lg font-bold text-slate-900">{{ stats.longestTask?.name ?? '—' }}</p>
          <p class="text-xs text-slate-400">{{ stats.longestTask?.duration ?? '' }}</p>
        </div>
      </div>
    </div>

    <!-- History Timeline -->
    <div>
      <div class="mb-3 flex items-center justify-between">
        <h3 class="text-sm font-semibold uppercase tracking-wide text-slate-500">历史时间线</h3>
        <button
          class="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white/70 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-white hover:text-slate-900"
          @click="exportCSV"
        >
          <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          导出 CSV
        </button>
      </div>

      <div class="space-y-2">
        <SessionCard
          v-for="item in sessions"
          :key="item.id"
          :session="item"
        />
        <div
          v-if="!sessions.length && !loading"
          class="glass-panel p-6 text-center text-sm text-slate-400"
        >
          暂无会话记录
        </div>
      </div>

      <div v-if="hasMore" class="mt-4 flex justify-center">
        <button
          class="rounded-lg border border-slate-200 bg-white/70 px-5 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-white hover:text-slate-900"
          :disabled="loading"
          @click="loadMore"
        >
          {{ loading ? '加载中…' : '加载更多' }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive } from "vue";
import SessionCard from "../components/SessionCard.vue";

const periods = [
  { key: "day", label: "日" },
  { key: "week", label: "周" },
  { key: "month", label: "月" },
];

const state = reactive({
  stats: {},
  sessions: [],
  page: 1,
  totalPages: 1,
  activePeriod: "day",
  loading: false,
});

const stats = computed(() => state.stats);
const sessions = computed(() => state.sessions);
const hasMore = computed(() => state.page < state.totalPages);
const loading = computed(() => state.loading);
const activePeriod = computed(() => state.activePeriod);

const periodLabel = computed(() => {
  if (state.activePeriod === "week") return "本周";
  if (state.activePeriod === "month") return "本月";
  return "今日";
});

async function fetchStats() {
  try {
    const resp = await fetch(`/api/sessions/stats?period=${state.activePeriod}`);
    if (!resp.ok) return;
    const data = await resp.json();
    state.stats = data?.stats ?? {};
  } catch { /* ignore */ }
}

async function fetchSessions(reset = false) {
  if (state.loading) return;
  state.loading = true;
  try {
    const page = reset ? 1 : state.page;
    const resp = await fetch(`/api/sessions?page=${page}&per_page=20`);
    if (!resp.ok) return;
    const data = await resp.json();
    const result = data?.data ?? {};
    if (reset) {
      state.sessions = result.items ?? [];
    } else {
      state.sessions.push(...(result.items ?? []));
    }
    state.page = result.page ?? 1;
    state.totalPages = result.pages ?? 1;
  } catch { /* ignore */ }
  finally {
    state.loading = false;
  }
}

function switchPeriod(period) {
  state.activePeriod = period;
  fetchStats();
}

function loadMore() {
  state.page++;
  fetchSessions();
}

async function exportCSV() {
  try {
    const resp = await fetch("/api/sessions/export");
    if (!resp.ok) return;
    const data = await resp.json();
    if (!data?.csv) return;
    const blob = new Blob([data.csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = data.filename || "sessions-export.csv";
    a.click();
    URL.revokeObjectURL(url);
  } catch { /* ignore */ }
}

onMounted(() => {
  fetchStats();
  fetchSessions(true);
});
</script>
