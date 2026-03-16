<template>
  <section class="space-y-4">
    <!-- Summary bar -->
    <div class="glass-panel animate-fade-up flex items-center justify-between px-5 py-3">
      <div class="flex flex-wrap items-center gap-3 text-xs">
        <span class="font-semibold text-slate-700">总任务 <b class="text-slate-900">{{ totalCount }}</b></span>
        <span class="h-4 w-px bg-slate-200"></span>
        <span v-for="col in columns" :key="col.status" class="flex items-center gap-1 text-slate-500">
          <span class="h-1.5 w-1.5 rounded-full" :class="dotClasses[col.color]"></span>
          {{ col.title }}
          <b class="text-slate-700">{{ col.tasks.length }}</b>
        </span>
      </div>
      <button
        class="shrink-0 rounded-xl bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:bg-slate-50 disabled:opacity-50"
        :disabled="loading"
        @click="fetchKanban"
      >
        <span v-if="loading">加载中...</span>
        <span v-else>刷新</span>
      </button>
    </div>

    <!-- Kanban board -->
    <div class="animate-fade-up overflow-x-auto pb-2" style="animation-delay: 80ms">
      <div class="flex gap-4" style="min-width: max-content">
        <KanbanColumn
          v-for="col in columns"
          :key="col.status"
          :title="col.title"
          :status="col.status"
          :tasks="col.tasks"
          :color="col.color"
          @drop="onColumnDrop"
        />
      </div>
    </div>

    <!-- Error / move feedback -->
    <Transition name="toast">
      <p
        v-if="toast"
        class="rounded-xl border px-4 py-2 text-xs"
        :class="toast.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-600' : 'border-rose-200 bg-rose-50 text-rose-600'"
      >{{ toast.msg }}</p>
    </Transition>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import KanbanColumn from "../components/KanbanColumn.vue";

const COLUMN_DEFS = [
  { status: "draft",   title: "Draft",     color: "slate" },
  { status: "queued",  title: "Queued",    color: "blue" },
  { status: "running", title: "Running",   color: "amber" },
  { status: "review",  title: "In Review", color: "orange" },
  { status: "done",    title: "Done",      color: "emerald" },
  { status: "blocked", title: "Blocked",   color: "red" },
];

const dotClasses = {
  slate:   "bg-slate-400",
  blue:    "bg-blue-500",
  amber:   "bg-amber-500",
  orange:  "bg-orange-500",
  emerald: "bg-emerald-500",
  red:     "bg-red-500",
};

const REFRESH_INTERVAL = 30_000;

const kanbanData = ref({});
const loading = ref(false);
const toast = ref(null);
let toastTimer = null;
let pollTimer = null;

const columns = computed(() =>
  COLUMN_DEFS.map((def) => ({
    ...def,
    tasks: kanbanData.value[def.status] || [],
  })),
);

const totalCount = computed(() =>
  columns.value.reduce((sum, col) => sum + col.tasks.length, 0),
);

function showToast(msg, ok = true, duration = 3500) {
  toast.value = { msg, ok };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.value = null; }, duration);
}

async function fetchKanban() {
  loading.value = true;
  try {
    const res = await fetch("/api/kanban");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.ok && data.columns) {
      kanbanData.value = data.columns;
      return;
    }
    throw new Error(data.error || "unexpected response");
  } catch {
    showToast("后端暂未就绪，当前显示 Mock 数据", false);
    kanbanData.value = getMockKanbanData();
  } finally {
    loading.value = false;
  }
}

async function onColumnDrop({ taskId, targetState }) {
  try {
    const res = await fetch("/api/kanban/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ taskId, targetState }),
    });
    const data = await res.json();
    if (data.ok) {
      showToast(`任务已移至 ${targetState}`);
      await fetchKanban();
    } else {
      showToast(data.error || "移动失败", false, 4500);
    }
  } catch {
    showToast("网络请求失败，请稍后重试", false);
  }
}

function getMockKanbanData() {
  const now = Date.now();
  const h = (hours) => new Date(now - hours * 3600_000).toISOString();

  return {
    draft: [
      { id: "t-001", name: "接入飞书消息推送模块", status: "draft", role: "执行-后端", priority: 1, updatedAt: h(2), description: "对接飞书 Open API，实现群消息推送能力" },
      { id: "t-002", name: "设计权限管理方案", status: "draft", role: "路由-架构", priority: 0, updatedAt: h(5), description: "多租户场景下的 RBAC 权限体系设计" },
    ],
    queued: [
      { id: "t-003", name: "优化任务调度队列", status: "queued", role: "执行-引擎", priority: 1, updatedAt: h(1), description: "引入优先级队列，支持 P0 任务插队执行" },
      { id: "t-004", name: "编写 E2E 测试脚本", status: "queued", role: "审核-QA", priority: 2, updatedAt: h(8), description: "覆盖核心工作流的端到端集成测试" },
      { id: "t-005", name: "数据库索引优化", status: "queued", role: "执行-DBA", priority: 1, updatedAt: h(3), description: "分析慢查询日志，添加复合索引" },
    ],
    running: [
      { id: "t-006", name: "实现看板面板前端", status: "running", role: "执行-前端", priority: 0, updatedAt: h(0.5), description: "6 列卡片布局，支持任务状态可视化" },
      { id: "t-007", name: "重构状态机引擎", status: "running", role: "执行-引擎", priority: 1, updatedAt: h(1.5), description: "将硬编码状态转换升级为可配置的状态机" },
    ],
    review: [
      { id: "t-008", name: "API 鉴权中间件", status: "review", role: "审核-安全", priority: 0, updatedAt: h(3), description: "JWT + Cookie 双模式认证，已提交 PR 待审" },
      { id: "t-009", name: "日志收集模块", status: "review", role: "审核-运维", priority: 2, updatedAt: h(6), description: "结构化日志输出，支持 JSON 格式" },
    ],
    done: [
      { id: "t-010", name: "面板框架搭建", status: "done", role: "执行-前端", priority: 1, updatedAt: h(24), description: "侧边栏导航 + 面板路由 + 布局组件" },
      { id: "t-011", name: "CI 流水线配置", status: "done", role: "执行-DevOps", priority: 1, updatedAt: h(48), description: "GitHub Actions 构建、测试、发布流程" },
      { id: "t-012", name: "环境预检工具", status: "done", role: "执行-工具", priority: 2, updatedAt: h(72), description: "一键检测运行环境依赖和配置完整性" },
    ],
    blocked: [
      { id: "t-013", name: "Discord 机器人集成", status: "blocked", role: "路由-IM", priority: 2, updatedAt: h(12), description: "等待 Discord 开发者账号审批" },
    ],
  };
}

onMounted(() => {
  fetchKanban();
  pollTimer = setInterval(fetchKanban, REFRESH_INTERVAL);
});

onUnmounted(() => {
  clearInterval(pollTimer);
  clearTimeout(toastTimer);
});
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
