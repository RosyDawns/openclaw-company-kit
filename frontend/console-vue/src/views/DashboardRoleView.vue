<template>
  <section class="space-y-4">
    <div class="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
      <article class="glass-panel animate-fade-up p-5">
        <div class="inline-flex items-center gap-2 rounded-full bg-cyan-100 px-3 py-1 text-xs font-semibold tracking-wide text-cyan-700">
          <span class="h-2 w-2 animate-floaty rounded-full bg-cyan-600"></span>
          Role Perspective
        </div>
        <h2 class="mt-3 text-3xl font-bold text-slate-900">{{ roleTitle }}</h2>
        <p class="mt-2 text-sm text-slate-600">独立页面，专注该角色的任务、调度和活跃证据。</p>
        <div class="mt-4 flex flex-wrap gap-2">
          <RouterLink to="/dashboard" class="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5">返回总览</RouterLink>
          <button class="rounded-xl bg-cyan-700 px-4 py-2 text-sm font-semibold text-white transition hover:-translate-y-0.5" @click="refreshNow">立即刷新</button>
        </div>
      </article>

      <article class="glass-panel animate-fade-up p-5" style="animation-delay: 120ms">
        <div v-if="roleData">
          <ul class="space-y-3 text-sm">
            <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">进度</span><b>{{ roleData.progress?.percent || 0 }}%</b></li>
            <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">状态</span><StatusChip :status="roleData.progress?.status" :text="roleData.progress?.status" /></li>
            <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">健康</span><StatusChip :status="roleData.health" :text="roleData.health" /></li>
            <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">会话</span><b>{{ roleData.sessions || 0 }}</b></li>
            <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">最近活跃</span><b>{{ roleData.lastActive || '-' }}</b></li>
            <li class="flex items-center justify-between"><span class="text-slate-500">下次刷新</span><b>{{ remainSec }}s</b></li>
          </ul>
          <p class="mt-3 text-xs text-slate-500">{{ roleData.progress?.summary || '暂无摘要' }}</p>
          <p class="mt-1 text-xs text-slate-500">证据：{{ roleData.progressEvidence || "-" }}</p>
        </div>
        <div v-else class="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">数据源暂无该角色面板数据。</div>
      </article>
    </div>

    <div class="grid gap-4 xl:grid-cols-2">
      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">关联 Issue</h3>
        <ul class="mt-3 space-y-2" v-if="roleIssues.length">
          <li v-for="issue in roleIssues" :key="issue.number" class="rounded-xl border border-slate-200 bg-white p-3">
            <div class="flex items-start justify-between gap-2">
              <b class="text-sm text-slate-900">#{{ issue.number }} {{ issue.title }}</b>
              <StatusChip :status="issue.status" :text="issue.status || issue.state" />
            </div>
            <p class="mt-1 text-xs text-slate-500">优先级：{{ issue.priority || '-' }} · 更新：{{ issue.updatedAt || '-' }}</p>
            <a :href="issue.url" target="_blank" rel="noreferrer" class="mt-2 inline-block text-xs font-semibold text-cyan-700 hover:underline">查看 Issue</a>
          </li>
        </ul>
        <div v-else class="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">暂无关联 Issue。</div>
      </article>

      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">角色 Cron</h3>
        <ul class="mt-3 space-y-2" v-if="roleCron.length">
          <li v-for="job in roleCron" :key="job.name + job.schedule" class="rounded-xl border border-slate-200 bg-white p-3">
            <div class="flex items-start justify-between gap-2">
              <b class="text-sm text-slate-900">{{ job.name }}</b>
              <StatusChip :status="job.lastRunStatus" :text="job.lastRunStatus || '-'" />
            </div>
            <p class="mt-1 text-xs text-slate-500">{{ job.schedule || '-' }} · delivery: {{ job.lastDeliveryStatus || '-' }}</p>
          </li>
        </ul>
        <div v-else class="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">暂无调度任务数据。</div>
      </article>
    </div>

    <div class="grid gap-4 xl:grid-cols-2">
      <article class="glass-panel p-4">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-slate-900">执行证据链</h3>
          <span class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">total {{ evidenceStats.total || 0 }}</span>
        </div>
        <div class="mt-3 flex flex-wrap gap-2 text-xs">
          <span class="rounded-full bg-white px-2.5 py-1 ring-1 ring-slate-200">Issue {{ evidenceStats.issue || 0 }}</span>
          <span class="rounded-full bg-white px-2.5 py-1 ring-1 ring-slate-200">PR {{ evidenceStats.pr || 0 }}</span>
          <span class="rounded-full bg-white px-2.5 py-1 ring-1 ring-slate-200">Commit {{ evidenceStats.commit || 0 }}</span>
          <span class="rounded-full bg-white px-2.5 py-1 ring-1 ring-slate-200">Comment {{ evidenceStats.comment || 0 }}</span>
        </div>
        <ul class="mt-3 space-y-2" v-if="evidenceRows.length">
          <li v-for="row in evidenceRows" :key="`${row.type || '-'}-${row.url || row.summary || ''}`" class="rounded-xl border border-slate-200 bg-white p-3">
            <div class="flex items-start justify-between gap-2">
              <b class="text-sm text-slate-900">{{ row.summary || "证据记录" }}</b>
              <span class="rounded-full px-2 py-0.5 text-[11px] font-semibold" :class="evidenceTypeClass(row.type)">{{ evidenceTypeText(row.type) }}</span>
            </div>
            <p class="mt-1 text-xs text-slate-500">Issue #{{ row.issueNumber || "-" }} · {{ row.issueTitle || "-" }}</p>
            <p class="mt-1 text-xs text-slate-500">{{ row.at || "-" }}</p>
            <a :href="row.url || '#'" target="_blank" rel="noreferrer" class="mt-2 inline-block text-xs font-semibold text-cyan-700 hover:underline">查看证据</a>
          </li>
        </ul>
        <div v-else class="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">暂无可追溯证据链。</div>
      </article>

      <article class="glass-panel p-4">
        <h3 class="text-sm font-semibold text-slate-900">时间轴 / 动作建议</h3>
        <ul class="mt-3 space-y-2" v-if="timelineRows.length">
          <li v-for="row in timelineRows" :key="`${row.label}-${row.detail}-${row.time}`" class="rounded-xl border border-slate-200 bg-white p-3">
            <div class="flex items-start justify-between gap-2">
              <b class="text-sm text-slate-900">{{ row.label }}</b>
              <span class="text-xs text-slate-500">{{ row.time || '-' }}</span>
            </div>
            <p class="mt-1 text-xs text-slate-500">{{ row.detail }}</p>
          </li>
        </ul>
        <div v-else class="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">暂无时间轴记录。</div>
        <div class="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600">
          <p>1) 当前 Open Issue：{{ openIssueCount }} 项，优先处理 P0/P1 和临近截止事项。</p>
          <p class="mt-1">2) 若状态长期不变，先补充 commit/PR 证据，避免“看板假进展”。</p>
          <p class="mt-1">3) 若存在阻塞，明确阻塞原因与协作人，并在 Issue 评论回写。</p>
        </div>
      </article>
    </div>

    <article class="glass-panel p-4">
      <h3 class="text-sm font-semibold text-slate-900">今日计划 / 阻塞 / 日程</h3>
      <div class="mt-3 grid gap-3 md:grid-cols-3">
        <div class="rounded-2xl border border-slate-200 bg-white p-3">
          <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-500">Today</h4>
          <ul class="mt-2 list-disc space-y-1 pl-4 text-sm text-slate-700">
            <li v-for="x in roleData?.today || []" :key="x">{{ x }}</li>
            <li v-if="!(roleData?.today || []).length" class="list-none text-slate-400">无</li>
          </ul>
        </div>
        <div class="rounded-2xl border border-slate-200 bg-white p-3">
          <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-500">Blockers</h4>
          <ul class="mt-2 list-disc space-y-1 pl-4 text-sm text-slate-700">
            <li v-for="x in roleData?.blockers || []" :key="x">{{ x }}</li>
            <li v-if="!(roleData?.blockers || []).length" class="list-none text-slate-400">无</li>
          </ul>
        </div>
        <div class="rounded-2xl border border-slate-200 bg-white p-3">
          <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-500">Routine</h4>
          <ul class="mt-2 list-disc space-y-1 pl-4 text-sm text-slate-700">
            <li v-for="x in roleData?.dailyRoutine || []" :key="x">{{ x }}</li>
            <li v-if="!(roleData?.dailyRoutine || []).length" class="list-none text-slate-400">无</li>
          </ul>
        </div>
      </div>
    </article>

    <article class="glass-panel p-4">
      <h3 class="text-sm font-semibold text-slate-900">相关活动流</h3>
      <ul class="mt-3 space-y-2" v-if="feedRows.length">
        <li v-for="row in feedRows" :key="(row.time || '') + (row.title || '')" class="rounded-xl border border-slate-200 bg-white p-3">
          <div class="flex items-start justify-between gap-2"><b class="text-sm text-slate-900">{{ row.title || '-' }}</b><span class="text-xs text-slate-500">{{ row.time || '-' }}</span></div>
          <p class="mt-1 text-xs text-slate-500">{{ row.detail || '-' }}</p>
        </li>
      </ul>
      <div v-else class="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">暂无相关活动。</div>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive } from "vue";
import { RouterLink, useRoute } from "vue-router";
import StatusChip from "../components/StatusChip.vue";
import { ownerMatchesRole } from "../lib/dashboard";
import { normalizeRoleId, roleLabel } from "../lib/constants";

const route = useRoute();

const state = reactive({
  data: null,
  remainSec: 15,
  refreshSec: 15,
  tickTimer: null,
  pollTimer: null,
});

const roleId = computed(() => String(route.params.roleId || ""));
const roleTitle = computed(() => roleLabel(roleId.value));
const roleData = computed(() => {
  const panel = Array.isArray(state.data?.agentPanel) ? state.data.agentPanel : [];
  return panel.find((x) => normalizeRoleId(x.id) === normalizeRoleId(roleId.value)) || null;
});

const roleIssues = computed(() => {
  const issues = Array.isArray(state.data?.github?.issues) ? state.data.github.issues : [];
  return issues.filter((x) => ownerMatchesRole(x, roleId.value)).slice(0, 20);
});

const roleCron = computed(() => {
  const rows = Array.isArray(state.data?.cronJobs) ? state.data.cronJobs : [];
  return rows.filter((x) => normalizeRoleId(x.agentId) === normalizeRoleId(roleId.value));
});

const evidenceRows = computed(() => (Array.isArray(roleData.value?.evidenceChain) ? roleData.value.evidenceChain.slice(0, 16) : []));
const evidenceStats = computed(() => roleData.value?.evidenceStats || {});

const feedRows = computed(() => {
  const feed = Array.isArray(state.data?.activityFeed) ? state.data.activityFeed : [];
  const roleName = roleTitle.value;
  return feed
    .filter((row) => {
      const blob = `${row?.title || ""} ${row?.detail || ""}`.toLowerCase();
      return blob.includes(roleId.value.toLowerCase()) || blob.includes(roleName.toLowerCase());
    })
    .slice(0, 16);
});

const openIssueCount = computed(() => roleIssues.value.filter((x) => String(x?.state || "").toLowerCase() === "open").length);

function parseMs(value) {
  const text = String(value || "").trim();
  if (!text) return 0;
  const ms = Date.parse(text.replace(" ", "T"));
  return Number.isFinite(ms) ? ms : 0;
}

const timelineRows = computed(() => {
  const rows = [];
  const nowRole = roleData.value;
  if (nowRole) {
    (nowRole.today || []).slice(0, 8).forEach((text, idx) => {
      rows.push({
        time: nowRole.lastActive || "",
        label: "今日进展",
        detail: text,
        rank: 100 - idx,
      });
    });
    (nowRole.blockers || []).slice(0, 4).forEach((text, idx) => {
      rows.push({
        time: nowRole.lastActive || "",
        label: "阻塞更新",
        detail: text,
        rank: 90 - idx,
      });
    });
  }

  feedRows.value.forEach((row) => {
    rows.push({
      time: row.time || "",
      label: row.title || "动态更新",
      detail: row.detail || "-",
      rank: 80,
    });
  });

  roleCron.value.forEach((job) => {
    rows.push({
      time: job.lastRun || "",
      label: `调度 · ${job.name || "-"}`,
      detail: `最近执行 ${job.lastRunStatus || "-"} / 投递 ${job.lastDeliveryStatus || "-"}`,
      rank: 70,
    });
  });

  roleIssues.value.slice(0, 10).forEach((issue) => {
    rows.push({
      time: issue.updatedAt || "",
      label: `Issue #${issue.number}`,
      detail: `${issue.status || issue.state || "-"} · ${issue.title || "-"}`,
      rank: 75,
    });
  });

  rows.sort((a, b) => {
    const diff = parseMs(b.time) - parseMs(a.time);
    if (diff !== 0) return diff;
    return Number(b.rank || 0) - Number(a.rank || 0);
  });

  const seen = new Set();
  return rows
    .filter((x) => {
      const key = `${x.label}::${x.detail}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 12);
});

function evidenceTypeText(type) {
  const t = String(type || "issue").toLowerCase();
  if (t === "pr") return "PR";
  if (t === "commit") return "Commit";
  if (t === "comment") return "Comment";
  return "Issue";
}

function evidenceTypeClass(type) {
  const t = String(type || "issue").toLowerCase();
  if (t === "pr") return "bg-emerald-100 text-emerald-700";
  if (t === "commit") return "bg-amber-100 text-amber-700";
  if (t === "comment") return "bg-cyan-100 text-cyan-700";
  return "bg-slate-100 text-slate-700";
}

async function fetchData() {
  const resp = await fetch(`/dashboard/dashboard-data.json?t=${Date.now()}`);
  if (!resp.ok) {
    throw new Error(`读取 dashboard-data.json 失败: ${resp.status}`);
  }
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

const remainSec = computed(() => state.remainSec);
</script>
