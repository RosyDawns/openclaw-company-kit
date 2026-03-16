<template>
  <section class="space-y-6">
    <!-- Service Status Cards -->
    <div>
      <h3 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">服务状态</h3>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <div
          v-for="svc in services"
          :key="svc.name"
          class="glass-panel flex items-center gap-3 p-4"
        >
          <span
            class="h-3 w-3 shrink-0 rounded-full shadow-sm"
            :class="statusDotClass(svc)"
          ></span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-semibold text-slate-900">{{ svc.name }}</p>
            <p class="text-xs text-slate-500">
              PID {{ svc.pid ?? '—' }} · {{ svc.uptime || '—' }}
            </p>
          </div>
          <span
            class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
            :class="statusBadgeClass(svc)"
          >
            {{ statusLabel(svc) }}
          </span>
        </div>
        <div
          v-if="!services.length"
          class="glass-panel col-span-full p-4 text-center text-sm text-slate-400"
        >
          暂无服务状态数据
        </div>
      </div>
    </div>

    <!-- Metrics Trend Chart -->
    <div>
      <h3 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">指标趋势（近 7 天）</h3>
      <div class="glass-panel p-5">
        <MetricsChart :data="metricsTrend" />
      </div>
    </div>

    <!-- Role Activity Timeline -->
    <div>
      <h3 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">角色活跃时间线（24h）</h3>
      <div class="glass-panel overflow-x-auto p-5">
        <TimelineBar :roles="timelineRoles" />
      </div>
    </div>

    <!-- Review Records -->
    <div>
      <h3 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">审核记录</h3>
      <div class="glass-panel overflow-hidden">
        <div v-if="reviews.length" class="overflow-x-auto">
          <table class="min-w-full text-left text-sm">
            <thead class="border-b border-slate-200/70 bg-slate-50/60 text-xs text-slate-500">
              <tr>
                <th class="px-4 py-2.5">时间</th>
                <th class="px-4 py-2.5">任务</th>
                <th class="px-4 py-2.5">审核人</th>
                <th class="px-4 py-2.5">决定</th>
                <th class="px-4 py-2.5">原因</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, idx) in reviews"
                :key="idx"
                class="border-t border-slate-100 transition-colors hover:bg-slate-50/50"
              >
                <td class="whitespace-nowrap px-4 py-2 text-slate-500">{{ row.time }}</td>
                <td class="px-4 py-2 font-medium text-slate-900">{{ row.task }}</td>
                <td class="px-4 py-2 text-slate-600">{{ row.reviewer }}</td>
                <td class="px-4 py-2">
                  <span
                    class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
                    :class="decisionClass(row.decision)"
                  >
                    {{ decisionIcon(row.decision) }} {{ decisionLabel(row.decision) }}
                  </span>
                </td>
                <td class="max-w-[200px] truncate px-4 py-2 text-xs text-slate-500" :title="row.reason">
                  {{ row.reason || '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="p-6 text-center text-sm text-slate-400">
          暂无审核记录
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive } from "vue";
import MetricsChart from "../components/MetricsChart.vue";
import TimelineBar from "../components/TimelineBar.vue";

const state = reactive({
  services: [],
  metricsTrend: [],
  reviews: [],
  timelineRoles: [],
  pollTimer: null,
});

const services = computed(() => state.services);
const metricsTrend = computed(() => state.metricsTrend);
const reviews = computed(() => state.reviews);
const timelineRoles = computed(() => state.timelineRoles);

function statusDotClass(svc) {
  if (svc.status === "running") return "bg-emerald-500 shadow-emerald-300";
  if (svc.status === "warning") return "bg-amber-500 shadow-amber-300";
  return "bg-red-400 shadow-red-200";
}

function statusBadgeClass(svc) {
  if (svc.status === "running") return "bg-emerald-100 text-emerald-700";
  if (svc.status === "warning") return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-600";
}

function statusLabel(svc) {
  if (svc.status === "running") return "运行中";
  if (svc.status === "warning") return "异常";
  return "已停止";
}

function decisionClass(d) {
  if (d === "approved") return "bg-emerald-100 text-emerald-700";
  if (d === "rejected") return "bg-red-100 text-red-600";
  return "bg-amber-100 text-amber-700";
}

function decisionIcon(d) {
  if (d === "approved") return "\u2705";
  if (d === "rejected") return "\u274C";
  return "\u23F3";
}

function decisionLabel(d) {
  if (d === "approved") return "通过";
  if (d === "rejected") return "拒绝";
  return "待审";
}

async function fetchServices() {
  try {
    const resp = await fetch("/api/monitor/services");
    if (!resp.ok) return;
    const data = await resp.json();
    state.services = data?.services ?? [];
  } catch { /* ignore */ }
}

async function fetchMetrics() {
  try {
    const resp = await fetch("/api/monitor/metrics");
    if (!resp.ok) return;
    const data = await resp.json();
    state.metricsTrend = data?.metrics ?? [];
    state.timelineRoles = data?.roles ?? [];
  } catch { /* ignore */ }
}

async function fetchReviews() {
  try {
    const resp = await fetch("/api/monitor/reviews");
    if (!resp.ok) return;
    const data = await resp.json();
    state.reviews = data?.reviews ?? [];
  } catch { /* ignore */ }
}

async function refreshAll() {
  await Promise.all([fetchServices(), fetchMetrics(), fetchReviews()]);
}

onMounted(() => {
  refreshAll();
  state.pollTimer = setInterval(refreshAll, 15000);
});

onUnmounted(() => {
  if (state.pollTimer) clearInterval(state.pollTimer);
});
</script>
