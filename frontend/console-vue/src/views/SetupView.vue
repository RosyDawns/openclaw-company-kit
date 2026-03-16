<template>
  <section class="space-y-4">
    <div class="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <article class="glass-panel animate-fade-up p-5">
        <div class="inline-flex items-center gap-2 rounded-full bg-cyan-100 px-3 py-1 text-xs font-semibold tracking-wide text-cyan-700">
          <span class="h-2 w-2 animate-pulse-glow rounded-full bg-cyan-600"></span>
          Control Center
        </div>
        <h2 class="mt-3 text-3xl font-bold text-slate-900">配置中心</h2>
        <p class="mt-2 text-sm text-slate-600">
          对齐旧版能力：分步向导、模型预设、服务预检阻断、任务日志、认证状态全部保留，并升级 UI/动效。
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          <button class="rounded-xl bg-cyan-700 px-4 py-2 text-sm font-semibold text-white shadow-lg transition hover:-translate-y-0.5 disabled:opacity-50" :disabled="busy" @click="runApply">{{ applyBtnText }}</button>
          <button class="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5 disabled:opacity-50" :disabled="busy" @click="saveConfig">保存配置</button>
          <button class="rounded-xl bg-amber-500 px-4 py-2 text-sm font-semibold text-white transition hover:-translate-y-0.5 disabled:opacity-50" :disabled="busy" @click="runRestart">仅重启服务</button>
          <RouterLink to="/dashboard" class="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5">打开驾驶舱</RouterLink>
        </div>
        <div class="mt-4 rounded-xl border px-3 py-2 text-xs" :class="statusClass">
          {{ statusText }}
        </div>
      </article>

      <article class="glass-panel animate-fade-up p-5" style="animation-delay: 120ms">
        <h3 class="text-sm font-semibold uppercase tracking-[0.14em] text-slate-500">认证与会话</h3>
        <ul class="mt-3 space-y-3 text-sm">
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">配置文件</span><b class="text-slate-900">{{ envPath }}</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">鉴权模式</span><b class="text-slate-900">{{ authDesc }}</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">Cookie 名</span><b class="text-slate-900">{{ auth.cookieName || 'openclaw_control_token' }}</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">首次引导</span><b class="text-slate-900">{{ firstTime ? '是' : '否' }}</b></li>
          <li class="flex items-center justify-between border-b border-slate-200/70 pb-2"><span class="text-slate-500">最后刷新</span><b class="text-slate-900">{{ refreshedAt || '-' }}</b></li>
          <li class="flex items-center justify-between"><span class="text-slate-500">预检状态</span><StatusChip :status="preflightAllPassed ? 'ok' : 'warn'" :text="preflightAllPassed ? '通过' : '待处理'" /></li>
        </ul>
      </article>
    </div>

    <div class="grid gap-4 lg:grid-cols-[300px_1fr]">
      <aside class="glass-panel p-4">
        <h3 class="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">配置步骤</h3>
        <div class="mt-3 space-y-2">
          <button
            v-for="(step, idx) in steps"
            :key="step.id"
            type="button"
            class="w-full rounded-xl border px-3 py-2 text-left text-sm transition"
            :class="idx === stepIdx ? 'border-cyan-300 bg-cyan-50 text-cyan-900' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'"
            @click="stepIdx = idx"
          >
            <b class="block">{{ step.label }}</b>
            <span class="text-xs text-slate-500">{{ step.tip }}</span>
          </button>
        </div>
      </aside>

      <div class="space-y-4">
        <article class="glass-panel p-4" v-if="stepIdx === 0">
          <h3 class="text-sm font-semibold text-slate-900">1) 端口与基础</h3>
          <div class="mt-3 grid gap-3 md:grid-cols-2">
            <label class="text-xs font-semibold text-slate-600">OPENCLAW_PROFILE
              <input v-model.trim="form.OPENCLAW_PROFILE" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">DASHBOARD_PORT
              <input v-model.trim="form.DASHBOARD_PORT" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600 md:col-span-2">SOURCE_OPENCLAW_CONFIG
              <input v-model.trim="form.SOURCE_OPENCLAW_CONFIG" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
          </div>
        </article>

        <article class="glass-panel p-4" v-if="stepIdx === 1">
          <h3 class="text-sm font-semibold text-slate-900">2) 公司与项目</h3>
          <div class="mt-3 grid gap-3 md:grid-cols-2">
            <label class="text-xs font-semibold text-slate-600">COMPANY_NAME
              <input v-model.trim="form.COMPANY_NAME" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">GROUP_ID
              <input v-model.trim="form.GROUP_ID" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600 md:col-span-2">PROJECT_PATH
              <input v-model.trim="form.PROJECT_PATH" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600 md:col-span-2">PROJECT_REPO
              <input v-model.trim="form.PROJECT_REPO" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600 md:col-span-2">WORKFLOW_TEMPLATE
              <select v-model="form.WORKFLOW_TEMPLATE" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm">
                <option value="default">默认综合流</option>
                <option value="requirement-review">需求评审流</option>
                <option value="bugfix">Bug 修复流</option>
                <option value="release-retro">发布复盘流</option>
              </select>
            </label>
          </div>
        </article>

        <article class="glass-panel p-4" v-if="stepIdx === 2">
          <h3 class="text-sm font-semibold text-slate-900">3) 模型与密钥</h3>
          <div class="mt-3 grid gap-3 md:grid-cols-2">
            <label class="text-xs font-semibold text-slate-600 md:col-span-2">模型预设
              <select v-model="modelPreset" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" @change="applyPreset">
                <option value="keep">保持现状</option>
                <option value="deepseek">DeepSeek 官方</option>
                <option value="qwen">Qwen / DashScope</option>
                <option value="moonshot">Moonshot (Kimi)</option>
                <option value="minimax">MiniMax</option>
                <option value="zai">智谱 ZAI</option>
                <option value="openai">OpenAI 官方</option>
                <option value="custom">自定义</option>
              </select>
            </label>
            <label class="text-xs font-semibold text-slate-600">MODEL_PRIMARY
              <input v-model.trim="form.MODEL_PRIMARY" readonly class="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">GH_TOKEN (可选)
              <input v-model="form.GH_TOKEN" type="password" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600 md:col-span-2">CUSTOM_BASE_URL
              <input v-model.trim="form.CUSTOM_BASE_URL" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">CUSTOM_MODEL_ID
              <input v-model.trim="form.CUSTOM_MODEL_ID" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">CUSTOM_PROVIDER_ID
              <input v-model.trim="form.CUSTOM_PROVIDER_ID" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">CUSTOM_COMPATIBILITY
              <select v-model="form.CUSTOM_COMPATIBILITY" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm">
                <option value="openai">openai</option>
                <option value="anthropic">anthropic</option>
              </select>
            </label>
            <label class="text-xs font-semibold text-slate-600">CUSTOM_API_KEY
              <input v-model="form.CUSTOM_API_KEY" type="password" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
          </div>
        </article>

        <article class="glass-panel p-4" v-if="stepIdx === 3">
          <h3 class="text-sm font-semibold text-slate-900">4) 飞书配置</h3>
          <div class="mt-3 grid gap-3 md:grid-cols-2">
            <label class="text-xs font-semibold text-slate-600">FEISHU_HOT_ACCOUNT_ID
              <input v-model.trim="form.FEISHU_HOT_ACCOUNT_ID" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">FEISHU_HOT_BOT_NAME
              <input v-model.trim="form.FEISHU_HOT_BOT_NAME" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">FEISHU_HOT_APP_ID
              <input v-model.trim="form.FEISHU_HOT_APP_ID" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">FEISHU_HOT_APP_SECRET
              <input v-model="form.FEISHU_HOT_APP_SECRET" type="password" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">FEISHU_AI_ACCOUNT_ID
              <input v-model.trim="form.FEISHU_AI_ACCOUNT_ID" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">FEISHU_AI_BOT_NAME
              <input v-model.trim="form.FEISHU_AI_BOT_NAME" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">FEISHU_AI_APP_ID
              <input v-model.trim="form.FEISHU_AI_APP_ID" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">FEISHU_AI_APP_SECRET
              <input v-model="form.FEISHU_AI_APP_SECRET" type="password" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
          </div>
        </article>

        <article class="glass-panel p-4" v-if="stepIdx === 4">
          <h3 class="text-sm font-semibold text-slate-900">5) 扩展通道</h3>
          <div class="mt-3 grid gap-3 md:grid-cols-2">
            <label class="text-xs font-semibold text-slate-600">MODEL_SUBAGENT
              <input v-model.trim="form.MODEL_SUBAGENT" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">DISCORD_BOT_TOKEN
              <input v-model="form.DISCORD_BOT_TOKEN" type="password" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">DISCORD_GUILD_ID
              <input v-model.trim="form.DISCORD_GUILD_ID" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
            <label class="text-xs font-semibold text-slate-600">DISCORD_CHANNEL_ID
              <input v-model.trim="form.DISCORD_CHANNEL_ID" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
            </label>
          </div>
        </article>

        <article class="glass-panel p-4" v-if="stepIdx === 5">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h3 class="text-sm font-semibold text-slate-900">6) 应用与状态</h3>
            <div class="flex gap-2">
              <button class="rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-slate-200" @click="refreshPreflight">刷新预检</button>
              <button class="rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-slate-200" @click="refreshServiceStatus">刷新服务</button>
            </div>
          </div>

          <div class="mt-3 grid gap-2 md:grid-cols-3">
            <div v-for="c in preflightChecks" :key="c.name" class="rounded-xl border p-2 text-xs" :class="preflightCardClass(c)">
              <b class="block text-slate-800">{{ c.name }}</b>
              <p class="text-slate-500">{{ preflightStateText(c) }} {{ c.version || '' }}</p>
              <p v-if="c.hint" class="text-slate-500">{{ c.hint }}</p>
            </div>
          </div>

          <div class="mt-3 grid gap-2 md:grid-cols-3">
            <div v-for="s in services" :key="s.name" class="rounded-xl border p-2 text-xs" :class="s.running ? 'border-cyan-200 bg-cyan-50' : 'border-amber-200 bg-amber-50'">
              <b class="block">{{ s.name }}</b>
              <span>{{ s.running ? 'running' : 'stopped' }} · pid {{ s.pid || '-' }}</span>
            </div>
          </div>

          <div class="mt-3 rounded-xl border border-slate-200 bg-slate-900/95 p-3">
            <div class="mb-2 flex items-center justify-between">
              <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-300">任务日志</h4>
              <StatusChip :status="task.status" :text="taskSummary" />
            </div>
            <pre class="max-h-72 overflow-auto text-xs text-emerald-100">{{ taskLogText }}</pre>
          </div>
        </article>

        <div class="flex items-center justify-between gap-3 rounded-2xl border border-white/40 bg-white/70 px-4 py-3">
          <button class="rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 disabled:opacity-50" :disabled="stepIdx === 0" @click="prevStep">上一步</button>
          <span class="text-xs text-slate-500">{{ steps[stepIdx]?.label }}</span>
          <button class="rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 disabled:opacity-50" :disabled="stepIdx === steps.length - 1" @click="nextStep">下一步</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, watch } from "vue";
import { RouterLink } from "vue-router";
import StatusChip from "../components/StatusChip.vue";
import { apiRequest } from "../lib/api";

const MODEL_PRESETS = {
  deepseek: {
    providerId: "deepseek",
    modelId: "deepseek-chat",
    baseUrl: "https://api.deepseek.com/v1",
    compatibility: "openai",
  },
  qwen: {
    providerId: "qwen",
    modelId: "qwen-max",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    compatibility: "openai",
  },
  moonshot: {
    providerId: "moonshot",
    modelId: "moonshot-v1-128k",
    baseUrl: "https://api.moonshot.cn/v1",
    compatibility: "openai",
  },
  minimax: {
    providerId: "minimax",
    modelId: "MiniMax-Text-01",
    baseUrl: "https://api.minimax.chat/v1",
    compatibility: "openai",
  },
  zai: {
    providerId: "zai",
    modelId: "zai-r1",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    compatibility: "openai",
  },
  openai: {
    providerId: "openai",
    modelId: "gpt-4o-mini",
    baseUrl: "https://api.openai.com/v1",
    compatibility: "openai",
  },
};

const steps = [
  { id: "step-port", label: "1) 端口与基础", tip: "Profile / 端口 / 基础配置源" },
  { id: "step-project", label: "2) 公司与项目", tip: "公司名、项目路径、仓库、流程模板" },
  { id: "step-model", label: "3) 模型与密钥", tip: "预设 + 自定义模型通道" },
  { id: "step-feishu", label: "4) 飞书配置", tip: "兼容字段 + AI 主字段" },
  { id: "step-extra", label: "5) 扩展通道", tip: "子模型与 Discord" },
  { id: "step-run", label: "6) 应用与状态", tip: "预检、服务状态、任务日志" },
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
    CUSTOM_COMPATIBILITY: "openai",
    DASHBOARD_PORT: "8788",
    MODEL_SUBAGENT: "",
    DISCORD_BOT_TOKEN: "",
    DISCORD_GUILD_ID: "",
    DISCORD_CHANNEL_ID: "",
  },
  modelPreset: "keep",
  stepIdx: 0,
  firstTime: false,
  envPath: ".env",
  auth: { enabled: true, ephemeral: false, cookieName: "openclaw_control_token" },
  refreshedAt: "",
  busy: false,
  statusText: "正在加载配置...",
  statusKind: "warn",
  preflightChecks: [],
  preflightAllPassed: false,
  services: [],
  task: { id: "", status: "idle", logs: [] },
  taskTimer: null,
  heartbeatTimer: null,
});

function setStatus(text, kind = "warn") {
  state.statusText = text;
  state.statusKind = kind;
}

function normalizeModelPrimary() {
  if (!state.form.CUSTOM_PROVIDER_ID || !state.form.CUSTOM_MODEL_ID) return;
  state.form.MODEL_PRIMARY = `${state.form.CUSTOM_PROVIDER_ID}/${state.form.CUSTOM_MODEL_ID}`;
}

watch(
  () => [state.form.CUSTOM_PROVIDER_ID, state.form.CUSTOM_MODEL_ID, state.modelPreset],
  () => {
    if (state.modelPreset === "custom") {
      normalizeModelPrimary();
    }
  }
);

function inferPreset() {
  const base = String(state.form.CUSTOM_BASE_URL || "").trim();
  const pid = String(state.form.CUSTOM_PROVIDER_ID || "").trim();
  const mid = String(state.form.CUSTOM_MODEL_ID || "").trim();
  for (const [key, cfg] of Object.entries(MODEL_PRESETS)) {
    if (cfg.baseUrl === base && cfg.providerId === pid && cfg.modelId === mid) {
      state.modelPreset = key;
      return;
    }
  }
  state.modelPreset = base || pid || mid ? "custom" : "keep";
}

function applyPreset() {
  if (state.modelPreset === "keep") {
    return;
  }
  if (state.modelPreset === "custom") {
    normalizeModelPrimary();
    return;
  }
  const cfg = MODEL_PRESETS[state.modelPreset];
  if (!cfg) return;
  state.form.CUSTOM_BASE_URL = cfg.baseUrl;
  state.form.CUSTOM_PROVIDER_ID = cfg.providerId;
  state.form.CUSTOM_MODEL_ID = cfg.modelId;
  state.form.CUSTOM_COMPATIBILITY = cfg.compatibility;
  state.form.MODEL_PRIMARY = `${cfg.providerId}/${cfg.modelId}`;
}

function syncForm(next) {
  for (const key of Object.keys(state.form)) {
    if (Object.prototype.hasOwnProperty.call(next, key)) {
      state.form[key] = String(next[key] ?? "");
    }
  }
  inferPreset();
}

function missingCore(cfg) {
  const miss = [];
  if (!String(cfg.PROJECT_PATH || "").trim()) miss.push("PROJECT_PATH");
  if (!String(cfg.GROUP_ID || "").trim()) miss.push("GROUP_ID");
  if (!String(cfg.FEISHU_AI_APP_ID || "").trim()) miss.push("FEISHU_AI_APP_ID");
  if (!String(cfg.FEISHU_AI_APP_SECRET || "").trim()) miss.push("FEISHU_AI_APP_SECRET");
  const port = String(cfg.DASHBOARD_PORT || "").trim();
  if (!/^\d{1,5}$/.test(port) || Number(port) < 1 || Number(port) > 65535) miss.push("DASHBOARD_PORT");
  return miss;
}

function currentApiOptions() {
  return { cookieName: state.auth.cookieName || "openclaw_control_token" };
}

async function loadConfig() {
  const data = await apiRequest("/api/config", currentApiOptions());
  syncForm(data.config || {});
  state.envPath = `${data.server?.rootDir || ""}/.env`;
  state.auth = { ...state.auth, ...(data.auth || {}) };
  state.firstTime = !!data.firstTime;
  state.services = data.service?.services || [];
  state.refreshedAt = new Date().toLocaleTimeString();
  setStatus(state.auth?.ephemeral ? "配置已加载（临时控制令牌）" : "配置已加载", state.auth?.ephemeral ? "warn" : "ok");
}

async function refreshPreflight() {
  const pf = await apiRequest("/api/preflight", currentApiOptions());
  state.preflightChecks = pf.checks || [];
  state.preflightAllPassed = !!pf.allPassed;
  state.refreshedAt = new Date().toLocaleTimeString();
  return pf;
}

async function refreshServiceStatus() {
  const svc = await apiRequest("/api/service/status", currentApiOptions());
  state.services = svc.service?.services || [];
  state.refreshedAt = new Date().toLocaleTimeString();
}

async function saveConfig() {
  state.busy = true;
  try {
    const res = await apiRequest("/api/config/save", { ...currentApiOptions(), method: "POST", body: { config: state.form } });
    syncForm(res.config || {});
    const miss = missingCore(state.form);
    setStatus(miss.length ? `已保存（还需填写: ${miss.join(", ")}）` : "已保存 .env", miss.length ? "warn" : "ok");
  } catch (err) {
    setStatus(`保存失败: ${err.message}`, "error");
  } finally {
    state.busy = false;
  }
}

async function pollTask() {
  if (!state.task.id) return;
  const data = await apiRequest(`/api/task/${state.task.id}`, currentApiOptions());
  state.task.status = data.task?.status || "unknown";
  state.task.logs = data.task?.logs || [];
  if (state.task.status !== "running" && state.taskTimer) {
    clearInterval(state.taskTimer);
    state.taskTimer = null;
    await Promise.all([refreshPreflight(), refreshServiceStatus()]);
  }
}

async function startTask(path, body) {
  const data = await apiRequest(path, { ...currentApiOptions(), method: "POST", body });
  state.task = { id: data.taskId || "", status: "running", logs: [] };
  state.stepIdx = steps.findIndex((x) => x.id === "step-run");
  if (state.taskTimer) clearInterval(state.taskTimer);
  state.taskTimer = setInterval(() => {
    pollTask().catch((err) => {
      state.task.logs.push(`[ERROR] ${err.message}`);
    });
  }, 1500);
  await pollTask();
}

async function runApply() {
  const miss = missingCore(state.form);
  if (miss.length) {
    setStatus(`缺少必填: ${miss.join(", ")}`, "error");
    return;
  }
  state.busy = true;
  try {
    const pf = await refreshPreflight();
    const blockingFailed = (pf.checks || [])
      .filter((c) => c && c.ok === false && c.blocking !== false)
      .map((c) => c.name);
    if (blockingFailed.length) {
      setStatus(`环境检测未通过: ${blockingFailed.join(", ")}`, "error");
      return;
    }
    await startTask("/api/config/apply", { config: state.form });
    setStatus(`任务启动: ${state.task.id}`, "warn");
  } catch (err) {
    setStatus(`应用失败: ${err.message}`, "error");
  } finally {
    state.busy = false;
  }
}

async function runRestart() {
  state.busy = true;
  try {
    await startTask("/api/service/restart", {});
    setStatus(`任务启动: ${state.task.id}`, "warn");
  } catch (err) {
    setStatus(`重启失败: ${err.message}`, "error");
  } finally {
    state.busy = false;
  }
}

function prevStep() {
  state.stepIdx = Math.max(0, state.stepIdx - 1);
}

function nextStep() {
  state.stepIdx = Math.min(steps.length - 1, state.stepIdx + 1);
}

onMounted(async () => {
  try {
    await loadConfig();
    await Promise.all([refreshPreflight(), refreshServiceStatus()]);
  } catch (err) {
    setStatus(`初始化失败: ${err.message}`, "error");
  }
  state.heartbeatTimer = setInterval(() => {
    Promise.all([refreshPreflight(), refreshServiceStatus()]).catch(() => {});
  }, 12000);
});

onUnmounted(() => {
  if (state.taskTimer) clearInterval(state.taskTimer);
  if (state.heartbeatTimer) clearInterval(state.heartbeatTimer);
});

const form = computed(() => state.form);
const stepIdx = computed({
  get: () => state.stepIdx,
  set: (v) => {
    state.stepIdx = Number(v);
  },
});
const modelPreset = computed({
  get: () => state.modelPreset,
  set: (v) => {
    state.modelPreset = String(v || "keep");
  },
});
const envPath = computed(() => state.envPath);
const auth = computed(() => state.auth);
const firstTime = computed(() => state.firstTime);
const refreshedAt = computed(() => state.refreshedAt);
const preflightChecks = computed(() => state.preflightChecks);
const preflightAllPassed = computed(() => state.preflightAllPassed);
const services = computed(() => state.services);
const task = computed(() => state.task);
const busy = computed(() => state.busy);
const statusText = computed(() => state.statusText);

const statusClass = computed(() => {
  if (state.statusKind === "ok") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (state.statusKind === "error") return "border-rose-200 bg-rose-50 text-rose-700";
  return "border-amber-200 bg-amber-50 text-amber-700";
});

const authDesc = computed(() => {
  if (!state.auth.enabled) return "未启用";
  return state.auth.ephemeral ? "启用（临时 token）" : "启用（固定 token）";
});

const applyBtnText = computed(() => (state.firstTime ? "初始化并启动" : "应用并重启服务"));

const taskSummary = computed(() => {
  if (!state.task.id) return "当前无任务";
  if (state.task.status === "running") return "执行中";
  if (state.task.status === "success") return "已完成";
  if (state.task.status === "failed") return "已失败";
  return state.task.status || "unknown";
});

const taskLogText = computed(() => (state.task.logs || []).join("\n") || "暂无日志");

function preflightCardClass(check) {
  if (check?.ok) return "border-emerald-200 bg-emerald-50";
  if (check?.blocking === false) return "border-amber-200 bg-amber-50";
  return "border-rose-200 bg-rose-50";
}

function preflightStateText(check) {
  if (check?.ok) return "OK";
  if (check?.blocking === false) return "WARN";
  return "FAIL";
}
</script>
