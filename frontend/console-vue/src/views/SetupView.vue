<template>
  <section class="space-y-4">
    <div class="grid gap-4 lg:grid-cols-[1.45fr_1fr]">
      <article class="glass-panel animate-fade-up p-5">
        <div class="inline-flex items-center gap-2 rounded-full bg-cyan-100 px-3 py-1 text-xs font-semibold tracking-wide text-cyan-700">
          <span class="h-2 w-2 animate-pulse-glow rounded-full bg-cyan-600"></span>
          Control Center
        </div>
        <h2 class="mt-3 text-3xl font-bold text-slate-900">配置中心</h2>
        <p class="mt-2 text-sm text-slate-600">
          新版 Vue3 + Tailwind 配置界面，保留现有 API 流程并强化实时反馈。
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          <button class="rounded-xl bg-cyan-700 px-4 py-2 text-sm font-semibold text-white shadow-lg transition hover:-translate-y-0.5 disabled:opacity-50" :disabled="busy" @click="applyConfig">保存并应用</button>
          <button class="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5" :disabled="busy" @click="saveConfig">仅保存</button>
          <button class="rounded-xl bg-amber-500 px-4 py-2 text-sm font-semibold text-white transition hover:-translate-y-0.5" :disabled="busy" @click="restartService">重启服务</button>
          <RouterLink to="/dashboard" class="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5">打开驾驶舱</RouterLink>
        </div>
      </article>

      <article class="glass-panel animate-fade-up p-5" style="animation-delay: 120ms">
        <h3 class="text-sm font-semibold uppercase tracking-[0.14em] text-slate-500">当前状态</h3>
        <ul class="mt-3 space-y-3 text-sm">
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">配置文件</span><b class="text-slate-900">{{ envPath }}</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">鉴权模式</span><b class="text-slate-900">{{ authDesc }}</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">最后刷新</span><b class="text-slate-900">{{ refreshedAt || '-' }}</b></li>
          <li class="flex items-center justify-between"><span class="text-slate-500">预检结果</span><StatusChip :status="preflightAllPassed ? 'ok' : 'warn'" :text="preflightAllPassed ? '通过' : '待处理'" /></li>
        </ul>
      </article>
    </div>

    <div class="grid gap-4 lg:grid-cols-[300px_1fr]">
      <aside class="glass-panel p-4">
        <h3 class="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">流程轨道</h3>
        <ol class="mt-3 space-y-2 text-sm">
          <li v-for="step in steps" :key="step.title" class="rounded-xl border border-slate-200 bg-white p-3">
            <b class="block text-slate-900">{{ step.title }}</b>
            <span class="text-xs text-slate-500">{{ step.tip }}</span>
          </li>
        </ol>
      </aside>

      <div class="space-y-4">
        <article class="glass-panel p-4">
          <h3 class="text-sm font-semibold text-slate-900">基础配置</h3>
          <div class="mt-3 grid gap-3 md:grid-cols-2">
            <label class="text-xs font-semibold text-slate-600">OPENCLAW_PROFILE
              <input v-model.trim="form.OPENCLAW_PROFILE" class="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">COMPANY_NAME
              <input v-model.trim="form.COMPANY_NAME" class="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600 md:col-span-2">SOURCE_OPENCLAW_CONFIG
              <input v-model.trim="form.SOURCE_OPENCLAW_CONFIG" class="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600 md:col-span-2">PROJECT_PATH
              <input v-model.trim="form.PROJECT_PATH" class="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">PROJECT_REPO
              <input v-model.trim="form.PROJECT_REPO" class="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">DASHBOARD_PORT
              <input v-model.trim="form.DASHBOARD_PORT" class="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600 md:col-span-2">WORKFLOW_TEMPLATE
              <select v-model="form.WORKFLOW_TEMPLATE" class="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm">
                <option value="default">默认执行流</option>
                <option value="requirement-review">需求评审流</option>
                <option value="bugfix">Bug 修复流</option>
                <option value="release-retro">发布复盘流</option>
              </select>
            </label>
          </div>
        </article>

        <article class="glass-panel p-4">
          <h3 class="text-sm font-semibold text-slate-900">飞书 / GitHub / 模型</h3>
          <div class="mt-3 grid gap-3 md:grid-cols-2">
            <label class="text-xs font-semibold text-slate-600">GROUP_ID<input v-model.trim="form.GROUP_ID" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" /></label>
            <label class="text-xs font-semibold text-slate-600">GH_TOKEN<input v-model="form.GH_TOKEN" type="password" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" /></label>
            <label class="text-xs font-semibold text-slate-600">FEISHU_AI_APP_ID<input v-model.trim="form.FEISHU_AI_APP_ID" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" /></label>
            <label class="text-xs font-semibold text-slate-600">FEISHU_AI_APP_SECRET<input v-model="form.FEISHU_AI_APP_SECRET" type="password" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" /></label>
            <label class="text-xs font-semibold text-slate-600">MODEL_PRIMARY<input v-model.trim="form.MODEL_PRIMARY" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" /></label>
            <label class="text-xs font-semibold text-slate-600">MODEL_SUBAGENT<input v-model.trim="form.MODEL_SUBAGENT" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" /></label>
            <label class="text-xs font-semibold text-slate-600 md:col-span-2">CUSTOM_BASE_URL<input v-model.trim="form.CUSTOM_BASE_URL" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" /></label>
          </div>
        </article>

        <article class="glass-panel p-4">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h3 class="text-sm font-semibold text-slate-900">环境预检与服务状态</h3>
            <div class="flex gap-2">
              <button class="rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-slate-200" @click="refreshPreflight">刷新预检</button>
              <button class="rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-slate-200" @click="refreshServiceStatus">刷新服务</button>
            </div>
          </div>
          <div class="mt-3 grid gap-2 md:grid-cols-3">
            <div v-for="c in preflightChecks" :key="c.name" class="rounded-xl border p-2 text-xs" :class="c.ok ? 'border-emerald-200 bg-emerald-50' : 'border-rose-200 bg-rose-50'">
              <b class="block text-slate-800">{{ c.name }}</b>
              <p class="text-slate-500">{{ c.ok ? 'OK' : 'FAIL' }} {{ c.version || '' }}</p>
              <p v-if="c.hint" class="text-slate-500">{{ c.hint }}</p>
            </div>
          </div>
          <div class="mt-2 grid gap-2 md:grid-cols-3">
            <div v-for="s in services" :key="s.name" class="rounded-xl border p-2 text-xs" :class="s.running ? 'border-cyan-200 bg-cyan-50' : 'border-amber-200 bg-amber-50'">
              <b class="block">{{ s.name }}</b>
              <span>{{ s.running ? 'running' : 'stopped' }} · pid {{ s.pid || '-' }}</span>
            </div>
          </div>
        </article>

        <article class="glass-panel p-4">
          <div class="mb-2 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-slate-900">任务日志</h3>
            <StatusChip :status="task.status" :text="taskSummary" />
          </div>
          <pre class="max-h-72 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-emerald-100">{{ taskLogText }}</pre>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive } from "vue";
import { RouterLink } from "vue-router";
import StatusChip from "../components/StatusChip.vue";
import { apiRequest } from "../lib/api";

const steps = [
  { title: "01 配置参数", tip: "项目、群路由、模型与密钥" },
  { title: "02 预检依赖", tip: "确认工具链与鉴权" },
  { title: "03 保存配置", tip: "写入 .env 并保留额外键" },
  { title: "04 执行 apply", tip: "stop → onboard → install → start" },
  { title: "05 进入驾驶舱", tip: "按角色视角持续跟踪" },
];

const state = reactive({
  form: {
    OPENCLAW_PROFILE: "company",
    SOURCE_OPENCLAW_CONFIG: "~/.openclaw/openclaw.json",
    COMPANY_NAME: "OpenClaw Company",
    PROJECT_PATH: "/path/to/your-project",
    PROJECT_REPO: "your-org/your-repo",
    WORKFLOW_TEMPLATE: "default",
    GROUP_ID: "",
    FEISHU_HOT_ACCOUNT_ID: "",
    FEISHU_HOT_BOT_NAME: "",
    FEISHU_HOT_APP_ID: "",
    FEISHU_HOT_APP_SECRET: "",
    FEISHU_AI_ACCOUNT_ID: "ai-tech",
    FEISHU_AI_BOT_NAME: "小龙虾 2 号",
    FEISHU_AI_APP_ID: "",
    FEISHU_AI_APP_SECRET: "",
    GH_TOKEN: "",
    MODEL_PRIMARY: "",
    CUSTOM_BASE_URL: "",
    CUSTOM_API_KEY: "",
    CUSTOM_MODEL_ID: "",
    CUSTOM_PROVIDER_ID: "",
    CUSTOM_COMPATIBILITY: "",
    DASHBOARD_PORT: "8788",
    MODEL_SUBAGENT: "",
    DISCORD_BOT_TOKEN: "",
    DISCORD_GUILD_ID: "",
    DISCORD_CHANNEL_ID: "",
  },
  envPath: ".env",
  auth: { enabled: true, ephemeral: false },
  refreshedAt: "",
  busy: false,
  preflightChecks: [],
  preflightAllPassed: false,
  services: [],
  task: { id: "", status: "idle", logs: [] },
  taskTimer: null,
  heartbeatTimer: null,
});

const taskSummary = computed(() => {
  if (!state.task.id) return "当前无任务";
  if (state.task.status === "running") return "执行中";
  if (state.task.status === "success") return "已完成";
  if (state.task.status === "failed") return "已失败";
  return state.task.status || "unknown";
});

const taskLogText = computed(() => (state.task.logs || []).join("\n") || "暂无日志");

const authDesc = computed(() => {
  if (!state.auth.enabled) return "未启用";
  return state.auth.ephemeral ? "启用（临时 token）" : "启用（固定 token）";
});

function syncForm(next) {
  for (const key of Object.keys(state.form)) {
    if (Object.prototype.hasOwnProperty.call(next, key)) {
      state.form[key] = String(next[key] ?? "");
    }
  }
}

async function loadConfig() {
  const data = await apiRequest("/api/config");
  syncForm(data.config || {});
  state.envPath = `${data.server?.rootDir || ""}/.env`;
  state.auth = data.auth || state.auth;
  state.services = data.service?.services || [];
  state.refreshedAt = new Date().toLocaleTimeString();
}

async function refreshPreflight() {
  const pf = await apiRequest("/api/preflight");
  state.preflightChecks = pf.checks || [];
  state.preflightAllPassed = !!pf.allPassed;
  state.refreshedAt = new Date().toLocaleTimeString();
}

async function refreshServiceStatus() {
  const svc = await apiRequest("/api/service/status");
  state.services = svc.service?.services || [];
  state.refreshedAt = new Date().toLocaleTimeString();
}

async function saveConfig() {
  state.busy = true;
  try {
    const res = await apiRequest("/api/config/save", { method: "POST", body: { config: state.form } });
    syncForm(res.config || {});
  } finally {
    state.busy = false;
  }
}

async function pollTask() {
  if (!state.task.id) return;
  const data = await apiRequest(`/api/task/${state.task.id}`);
  state.task.status = data.task?.status || "unknown";
  state.task.logs = data.task?.logs || [];
  if (state.task.status !== "running" && state.taskTimer) {
    clearInterval(state.taskTimer);
    state.taskTimer = null;
    await Promise.all([refreshPreflight(), refreshServiceStatus()]);
  }
}

async function startTask(path, body) {
  state.busy = true;
  try {
    const res = await apiRequest(path, { method: "POST", body });
    state.task = { id: res.taskId || "", status: "running", logs: [] };
    if (state.taskTimer) clearInterval(state.taskTimer);
    state.taskTimer = setInterval(() => {
      pollTask().catch((err) => {
        state.task.logs.push(`[ERROR] ${err.message}`);
      });
    }, 1800);
    await pollTask();
  } finally {
    state.busy = false;
  }
}

async function applyConfig() {
  await startTask("/api/config/apply", { config: state.form });
}

async function restartService() {
  await startTask("/api/service/restart", {});
}

onMounted(async () => {
  await Promise.all([loadConfig(), refreshPreflight(), refreshServiceStatus()]);
  state.heartbeatTimer = setInterval(() => {
    Promise.all([refreshPreflight(), refreshServiceStatus()]).catch(() => {});
  }, 12000);
});

onUnmounted(() => {
  if (state.taskTimer) clearInterval(state.taskTimer);
  if (state.heartbeatTimer) clearInterval(state.heartbeatTimer);
});

const form = computed(() => state.form);
const envPath = computed(() => state.envPath);
const busy = computed(() => state.busy);
const preflightChecks = computed(() => state.preflightChecks);
const preflightAllPassed = computed(() => state.preflightAllPassed);
const services = computed(() => state.services);
const task = computed(() => state.task);
const refreshedAt = computed(() => state.refreshedAt);
</script>
