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

    <!-- Preflight Card -->
    <article class="glass-panel animate-fade-up p-5" style="animation-delay: 180ms">
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-sm font-semibold text-slate-900">环境预检</h3>
          <p class="mt-0.5 text-xs text-slate-500">检查工具依赖、环境变量和认证状态</p>
        </div>
        <button
          class="rounded-xl bg-cyan-700 px-4 py-2 text-sm font-semibold text-white shadow transition hover:-translate-y-0.5 disabled:opacity-50"
          :disabled="preflightBusy"
          @click="runPreflightCheck"
        >{{ preflightBusy ? '检查中...' : '运行预检' }}</button>
      </div>
      <div v-if="preflightChecks.length" class="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="c in preflightChecks"
          :key="c.name"
          class="flex items-start gap-2.5 rounded-xl border p-3"
          :class="preflightItemClass(c)"
        >
          <span class="shrink-0 text-base leading-snug">{{ c.ok ? '\u2705' : '\u274C' }}</span>
          <div class="min-w-0">
            <b class="block text-sm text-slate-800">{{ c.name }}</b>
            <p class="text-xs text-slate-500">{{ c.version || c.hint || (c.ok ? '通过' : '未通过') }}</p>
          </div>
        </div>
      </div>
      <p v-else class="mt-3 text-center text-xs text-slate-400">点击「运行预检」开始环境检查</p>
    </article>

    <!-- Accordion Config Groups -->
    <div class="space-y-3">

      <!-- Group: 基础信息 -->
      <article class="glass-panel overflow-hidden">
        <button type="button" class="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-slate-50/50" @click="toggleGroup('basic')">
          <svg class="h-4 w-4 shrink-0 text-slate-400 transition-transform duration-300" :class="openGroups.basic && 'rotate-90'" viewBox="0 0 24 24" fill="none">
            <path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span class="text-sm font-semibold text-slate-900">基础信息</span>
          <span class="ml-auto flex items-center gap-2">
            <span v-if="groupStats('basic').errors" class="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-600">{{ groupStats('basic').errors }} 项异常</span>
            <span class="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">{{ groupStats('basic').filled }}/{{ groupStats('basic').total }} 已配置</span>
          </span>
        </button>
        <div class="grid transition-[grid-template-rows] duration-300 ease-in-out" :class="openGroups.basic ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'">
          <div class="overflow-hidden">
            <div class="border-t border-slate-100 px-5 pb-5 pt-4">
              <div class="grid gap-3 md:grid-cols-2">
                <label class="text-xs font-semibold text-slate-600">COMPANY_NAME
                  <input v-model.trim="form.COMPANY_NAME" :class="inputClass('COMPANY_NAME')" />
                  <span v-if="fieldErrors.COMPANY_NAME" class="mt-1 block text-xs font-normal text-red-500">{{ fieldErrors.COMPANY_NAME }}</span>
                </label>
                <label class="text-xs font-semibold text-slate-600 md:col-span-2">PROJECT_PATH
                  <input v-model.trim="form.PROJECT_PATH" :class="inputClass('PROJECT_PATH')" />
                  <span v-if="fieldErrors.PROJECT_PATH" class="mt-1 block text-xs font-normal text-red-500">{{ fieldErrors.PROJECT_PATH }}</span>
                </label>
                <label class="text-xs font-semibold text-slate-600 md:col-span-2">PROJECT_REPO
                  <input v-model.trim="form.PROJECT_REPO" :class="inputClass('PROJECT_REPO')" placeholder="https://github.com/org/repo 或 org/repo" />
                  <span v-if="fieldErrors.PROJECT_REPO" class="mt-1 block text-xs font-normal text-red-500">{{ fieldErrors.PROJECT_REPO }}</span>
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
            </div>
          </div>
        </div>
      </article>

      <!-- Group: 飞书/IM 配置 -->
      <article class="glass-panel overflow-hidden">
        <button type="button" class="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-slate-50/50" @click="toggleGroup('feishu')">
          <svg class="h-4 w-4 shrink-0 text-slate-400 transition-transform duration-300" :class="openGroups.feishu && 'rotate-90'" viewBox="0 0 24 24" fill="none">
            <path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span class="text-sm font-semibold text-slate-900">飞书/IM 配置</span>
          <span class="ml-auto flex items-center gap-2">
            <span v-if="groupStats('feishu').errors" class="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-600">{{ groupStats('feishu').errors }} 项异常</span>
            <span class="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">{{ groupStats('feishu').filled }}/{{ groupStats('feishu').total }} 已配置</span>
          </span>
        </button>
        <div class="grid transition-[grid-template-rows] duration-300 ease-in-out" :class="openGroups.feishu ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'">
          <div class="overflow-hidden">
            <div class="border-t border-slate-100 px-5 pb-5 pt-4">
              <div class="grid gap-3 md:grid-cols-2">
                <label class="text-xs font-semibold text-slate-600">GROUP_ID
                  <input v-model.trim="form.GROUP_ID" :class="inputClass('GROUP_ID')" />
                  <span v-if="fieldErrors.GROUP_ID" class="mt-1 block text-xs font-normal text-red-500">{{ fieldErrors.GROUP_ID }}</span>
                </label>
                <div></div>
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
                  <input v-model.trim="form.FEISHU_AI_APP_ID" :class="inputClass('FEISHU_AI_APP_ID')" />
                  <span v-if="fieldErrors.FEISHU_AI_APP_ID" class="mt-1 block text-xs font-normal text-red-500">{{ fieldErrors.FEISHU_AI_APP_ID }}</span>
                </label>
                <label class="text-xs font-semibold text-slate-600">FEISHU_AI_APP_SECRET
                  <input v-model="form.FEISHU_AI_APP_SECRET" type="password" :class="inputClass('FEISHU_AI_APP_SECRET')" />
                  <span v-if="fieldErrors.FEISHU_AI_APP_SECRET" class="mt-1 block text-xs font-normal text-red-500">{{ fieldErrors.FEISHU_AI_APP_SECRET }}</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </article>

      <!-- Group: 模型配置 -->
      <article class="glass-panel overflow-hidden">
        <button type="button" class="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-slate-50/50" @click="toggleGroup('model')">
          <svg class="h-4 w-4 shrink-0 text-slate-400 transition-transform duration-300" :class="openGroups.model && 'rotate-90'" viewBox="0 0 24 24" fill="none">
            <path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span class="text-sm font-semibold text-slate-900">模型配置</span>
          <span class="ml-auto flex items-center gap-2">
            <span v-if="groupStats('model').errors" class="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-600">{{ groupStats('model').errors }} 项异常</span>
            <span class="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">{{ groupStats('model').filled }}/{{ groupStats('model').total }} 已配置</span>
          </span>
        </button>
        <div class="grid transition-[grid-template-rows] duration-300 ease-in-out" :class="openGroups.model ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'">
          <div class="overflow-hidden">
            <div class="border-t border-slate-100 px-5 pb-5 pt-4">
              <div class="grid gap-3 md:grid-cols-2">
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
                <label class="text-xs font-semibold text-slate-600 md:col-span-2">CUSTOM_BASE_URL
                  <input v-model.trim="form.CUSTOM_BASE_URL" :class="inputClass('CUSTOM_BASE_URL')" placeholder="https://api.example.com/v1" />
                  <span v-if="fieldErrors.CUSTOM_BASE_URL" class="mt-1 block text-xs font-normal text-red-500">{{ fieldErrors.CUSTOM_BASE_URL }}</span>
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
                <label class="text-xs font-semibold text-slate-600">MODEL_SUBAGENT
                  <input v-model.trim="form.MODEL_SUBAGENT" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
                </label>
              </div>
            </div>
          </div>
        </div>
      </article>

      <!-- Group: 安全设置 -->
      <article class="glass-panel overflow-hidden">
        <button type="button" class="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-slate-50/50" @click="toggleGroup('security')">
          <svg class="h-4 w-4 shrink-0 text-slate-400 transition-transform duration-300" :class="openGroups.security && 'rotate-90'" viewBox="0 0 24 24" fill="none">
            <path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span class="text-sm font-semibold text-slate-900">安全设置</span>
          <span class="ml-auto flex items-center gap-2">
            <span class="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">{{ groupStats('security').filled }}/{{ groupStats('security').total }} 已配置</span>
          </span>
        </button>
        <div class="grid transition-[grid-template-rows] duration-300 ease-in-out" :class="openGroups.security ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'">
          <div class="overflow-hidden">
            <div class="border-t border-slate-100 px-5 pb-5 pt-4">
              <div class="grid gap-3 md:grid-cols-2">
                <label class="text-xs font-semibold text-slate-600">GH_TOKEN (可选)
                  <input v-model="form.GH_TOKEN" type="password" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
                </label>
                <div></div>
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
            </div>
          </div>
        </div>
      </article>

      <!-- Group: 高级选项 -->
      <article class="glass-panel overflow-hidden">
        <button type="button" class="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-slate-50/50" @click="toggleGroup('advanced')">
          <svg class="h-4 w-4 shrink-0 text-slate-400 transition-transform duration-300" :class="openGroups.advanced && 'rotate-90'" viewBox="0 0 24 24" fill="none">
            <path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span class="text-sm font-semibold text-slate-900">高级选项</span>
          <span class="ml-auto flex items-center gap-2">
            <span v-if="groupStats('advanced').errors" class="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-600">{{ groupStats('advanced').errors }} 项异常</span>
            <span class="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">{{ groupStats('advanced').filled }}/{{ groupStats('advanced').total }} 已配置</span>
          </span>
        </button>
        <div class="grid transition-[grid-template-rows] duration-300 ease-in-out" :class="openGroups.advanced ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'">
          <div class="overflow-hidden">
            <div class="border-t border-slate-100 px-5 pb-5 pt-4">
              <div class="grid gap-3 md:grid-cols-2">
                <label class="text-xs font-semibold text-slate-600">DASHBOARD_PORT
                  <input v-model.trim="form.DASHBOARD_PORT" :class="inputClass('DASHBOARD_PORT')" />
                  <span v-if="fieldErrors.DASHBOARD_PORT" class="mt-1 block text-xs font-normal text-red-500">{{ fieldErrors.DASHBOARD_PORT }}</span>
                </label>
                <label class="text-xs font-semibold text-slate-600">OPENCLAW_PROFILE
                  <input v-model.trim="form.OPENCLAW_PROFILE" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
                </label>
                <label class="text-xs font-semibold text-slate-600 md:col-span-2">SOURCE_OPENCLAW_CONFIG
                  <input v-model.trim="form.SOURCE_OPENCLAW_CONFIG" class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
                </label>
              </div>
            </div>
          </div>
        </div>
      </article>
    </div>

    <!-- Services + Task Log -->
    <div class="grid gap-4 lg:grid-cols-2">
      <article class="glass-panel p-4">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-slate-900">服务状态</h3>
          <button class="rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-50" @click="refreshServiceStatus">刷新</button>
        </div>
        <div class="mt-3 grid gap-2">
          <div v-for="s in services" :key="s.name" class="rounded-xl border p-2 text-xs" :class="s.running ? 'border-cyan-200 bg-cyan-50' : 'border-amber-200 bg-amber-50'">
            <b class="block">{{ s.name }}</b>
            <span>{{ s.running ? 'running' : 'stopped' }} · pid {{ s.pid || '-' }}</span>
          </div>
          <p v-if="!services.length" class="text-xs text-slate-400">暂无服务信息</p>
        </div>
      </article>

      <article class="glass-panel overflow-hidden p-4">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-slate-900">任务日志</h3>
          <StatusChip :status="task.status" :text="taskSummary" />
        </div>
        <pre class="mt-3 max-h-72 overflow-auto rounded-xl border border-slate-200 bg-slate-900/95 p-3 text-xs text-emerald-100">{{ taskLogText }}</pre>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
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

const CONFIG_GROUPS = [
  { id: "basic", fields: ["COMPANY_NAME", "PROJECT_PATH", "PROJECT_REPO", "WORKFLOW_TEMPLATE"] },
  { id: "feishu", fields: ["GROUP_ID", "FEISHU_HOT_ACCOUNT_ID", "FEISHU_HOT_BOT_NAME", "FEISHU_HOT_APP_ID", "FEISHU_HOT_APP_SECRET", "FEISHU_AI_ACCOUNT_ID", "FEISHU_AI_BOT_NAME", "FEISHU_AI_APP_ID", "FEISHU_AI_APP_SECRET"] },
  { id: "model", fields: ["MODEL_PRIMARY", "CUSTOM_BASE_URL", "CUSTOM_API_KEY", "CUSTOM_MODEL_ID", "CUSTOM_PROVIDER_ID", "CUSTOM_COMPATIBILITY", "MODEL_SUBAGENT"] },
  { id: "security", fields: ["GH_TOKEN", "DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID", "DISCORD_CHANNEL_ID"] },
  { id: "advanced", fields: ["DASHBOARD_PORT", "OPENCLAW_PROFILE", "SOURCE_OPENCLAW_CONFIG"] },
];

const REQUIRED_FIELDS = new Set(["PROJECT_PATH", "GROUP_ID", "FEISHU_AI_APP_ID", "FEISHU_AI_APP_SECRET", "DASHBOARD_PORT"]);

const openGroups = reactive({ basic: true, feishu: false, model: false, security: false, advanced: false });

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
    FEISHU_AI_BOT_NAME: "\u5c0f\u9f99\u867e 2 \u53f7",
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
  firstTime: false,
  envPath: ".env",
  auth: { enabled: true, ephemeral: false, cookieName: "openclaw_control_token" },
  refreshedAt: "",
  busy: false,
  preflightBusy: false,
  statusText: "\u6b63\u5728\u52a0\u8f7d\u914d\u7f6e...",
  statusKind: "warn",
  preflightChecks: [],
  preflightAllPassed: false,
  services: [],
  task: { id: "", status: "idle", logs: [] },
  taskTimer: null,
  heartbeatTimer: null,
});

function toggleGroup(id) {
  openGroups[id] = !openGroups[id];
}

function groupStats(groupId) {
  const group = CONFIG_GROUPS.find((g) => g.id === groupId);
  if (!group) return { filled: 0, total: 0, errors: 0 };
  const total = group.fields.length;
  const filled = group.fields.filter((f) => String(state.form[f] || "").trim()).length;
  const errs = group.fields.filter((f) => fieldErrors.value[f]).length;
  return { filled, total, errors: errs };
}

const fieldErrors = computed(() => {
  const errors = {};
  const f = state.form;

  for (const key of REQUIRED_FIELDS) {
    if (!String(f[key] || "").trim()) {
      errors[key] = "\u5fc5\u586b\u9879";
    }
  }

  const port = String(f.DASHBOARD_PORT || "").trim();
  if (port && !errors.DASHBOARD_PORT) {
    if (!/^\d+$/.test(port) || Number(port) < 1 || Number(port) > 65535) {
      errors.DASHBOARD_PORT = "\u7aef\u53e3\u8303\u56f4: 1-65535";
    }
  }

  const urlRe = /^https?:\/\/.+/;
  const repo = String(f.PROJECT_REPO || "").trim();
  if (repo && !urlRe.test(repo) && !/^\S+\/\S+$/.test(repo)) {
    errors.PROJECT_REPO = "\u8bf7\u8f93\u5165\u6709\u6548\u7684 URL \u6216 org/repo \u683c\u5f0f";
  }
  const baseUrl = String(f.CUSTOM_BASE_URL || "").trim();
  if (baseUrl && !urlRe.test(baseUrl)) {
    errors.CUSTOM_BASE_URL = "\u8bf7\u8f93\u5165\u6709\u6548\u7684 URL";
  }

  return errors;
});

function inputClass(field) {
  return fieldErrors.value[field]
    ? "mt-1 w-full rounded-xl border border-red-500 bg-red-50/30 px-3 py-2 text-sm transition-colors"
    : "mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm transition-colors";
}

function preflightItemClass(check) {
  if (check?.ok) return "border-emerald-200 bg-emerald-50";
  if (check?.blocking === false) return "border-amber-200 bg-amber-50";
  return "border-rose-200 bg-rose-50";
}

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
  if (state.modelPreset === "keep") return;
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
  setStatus(state.auth?.ephemeral ? "\u914d\u7f6e\u5df2\u52a0\u8f7d\uff08\u4e34\u65f6\u63a7\u5236\u4ee4\u724c\uff09" : "\u914d\u7f6e\u5df2\u52a0\u8f7d", state.auth?.ephemeral ? "warn" : "ok");
}

async function refreshPreflight() {
  const pf = await apiRequest("/api/preflight", currentApiOptions());
  state.preflightChecks = pf.checks || [];
  state.preflightAllPassed = !!pf.allPassed;
  state.refreshedAt = new Date().toLocaleTimeString();
  return pf;
}

async function runPreflightCheck() {
  state.preflightBusy = true;
  try {
    await refreshPreflight();
  } catch (err) {
    setStatus(`\u9884\u68c0\u5931\u8d25: ${err.message}`, "error");
  } finally {
    state.preflightBusy = false;
  }
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
    setStatus(miss.length ? `\u5df2\u4fdd\u5b58\uff08\u8fd8\u9700\u586b\u5199: ${miss.join(", ")}\uff09` : "\u5df2\u4fdd\u5b58 .env", miss.length ? "warn" : "ok");
  } catch (err) {
    setStatus(`\u4fdd\u5b58\u5931\u8d25: ${err.message}`, "error");
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
    setStatus(`\u7f3a\u5c11\u5fc5\u586b: ${miss.join(", ")}`, "error");
    return;
  }
  state.busy = true;
  try {
    const pf = await refreshPreflight();
    const blockingFailed = (pf.checks || [])
      .filter((c) => c && c.ok === false && c.blocking !== false)
      .map((c) => c.name);
    if (blockingFailed.length) {
      setStatus(`\u73af\u5883\u68c0\u6d4b\u672a\u901a\u8fc7: ${blockingFailed.join(", ")}`, "error");
      return;
    }
    await startTask("/api/config/apply", { config: state.form });
    setStatus(`\u4efb\u52a1\u542f\u52a8: ${state.task.id}`, "warn");
  } catch (err) {
    setStatus(`\u5e94\u7528\u5931\u8d25: ${err.message}`, "error");
  } finally {
    state.busy = false;
  }
}

async function runRestart() {
  state.busy = true;
  try {
    await startTask("/api/service/restart", {});
    setStatus(`\u4efb\u52a1\u542f\u52a8: ${state.task.id}`, "warn");
  } catch (err) {
    setStatus(`\u91cd\u542f\u5931\u8d25: ${err.message}`, "error");
  } finally {
    state.busy = false;
  }
}

onMounted(async () => {
  try {
    await loadConfig();
    await Promise.all([refreshPreflight(), refreshServiceStatus()]);
  } catch (err) {
    setStatus(`\u521d\u59cb\u5316\u5931\u8d25: ${err.message}`, "error");
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
const preflightBusy = computed(() => state.preflightBusy);
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
  if (!state.auth.enabled) return "\u672a\u542f\u7528";
  return state.auth.ephemeral ? "\u542f\u7528\uff08\u4e34\u65f6 token\uff09" : "\u542f\u7528\uff08\u56fa\u5b9a token\uff09";
});

const applyBtnText = computed(() => (state.firstTime ? "\u521d\u59cb\u5316\u5e76\u542f\u52a8" : "\u5e94\u7528\u5e76\u91cd\u542f\u670d\u52a1"));

const taskSummary = computed(() => {
  if (!state.task.id) return "\u5f53\u524d\u65e0\u4efb\u52a1";
  if (state.task.status === "running") return "\u6267\u884c\u4e2d";
  if (state.task.status === "success") return "\u5df2\u5b8c\u6210";
  if (state.task.status === "failed") return "\u5df2\u5931\u8d25";
  return state.task.status || "unknown";
});

const taskLogText = computed(() => (state.task.logs || []).join("\n") || "\u6682\u65e0\u65e5\u5fd7");
</script>
