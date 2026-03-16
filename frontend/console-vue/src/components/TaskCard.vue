<template>
  <div
    class="group cursor-grab rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md active:cursor-grabbing"
    draggable="true"
    @dragstart="onDragStart"
    @dragend="onDragEnd"
    @click="onClick"
  >
    <h4 class="line-clamp-2 text-sm font-semibold text-slate-900">{{ task.name }}</h4>

    <div class="mt-2 flex flex-wrap gap-1.5">
      <span
        v-if="task.role"
        class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
        :class="roleClass"
      >{{ task.role }}</span>
      <span
        v-if="task.priority != null"
        class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
        :class="priorityClass"
      >P{{ task.priority }}</span>
    </div>

    <p
      v-if="task.description"
      class="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-500"
    >{{ task.description }}</p>

    <p class="mt-2 text-[10px] text-slate-400">{{ relativeTime }}</p>
  </div>

  <Teleport to="body">
    <div
      v-if="expanded"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
      @click.self="expanded = false"
    >
      <div class="mx-4 w-full max-w-md animate-fade-up rounded-2xl bg-white p-6 shadow-2xl">
        <div class="flex items-start justify-between gap-3">
          <h3 class="text-lg font-bold text-slate-900">{{ task.name }}</h3>
          <button
            class="shrink-0 rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            @click="expanded = false"
          >
            <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </button>
        </div>

        <div class="mt-4 space-y-3 text-sm">
          <div class="flex items-center gap-2">
            <span class="w-16 shrink-0 text-slate-500">状态</span>
            <span class="font-medium text-slate-800">{{ task.status }}</span>
          </div>
          <div v-if="task.role" class="flex items-center gap-2">
            <span class="w-16 shrink-0 text-slate-500">角色</span>
            <span class="rounded-full px-2 py-0.5 text-xs font-semibold" :class="roleClass">{{ task.role }}</span>
          </div>
          <div v-if="task.priority != null" class="flex items-center gap-2">
            <span class="w-16 shrink-0 text-slate-500">优先级</span>
            <span class="rounded-full px-2 py-0.5 text-xs font-semibold" :class="priorityClass">P{{ task.priority }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-16 shrink-0 text-slate-500">更新</span>
            <span class="text-slate-800">{{ relativeTime }}</span>
          </div>
          <div v-if="task.description">
            <span class="text-slate-500">描述</span>
            <p class="mt-1 whitespace-pre-wrap text-slate-700">{{ task.description }}</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-16 shrink-0 text-slate-500">ID</span>
            <code class="text-xs text-slate-600">{{ task.id }}</code>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  task: { type: Object, required: true },
});

const expanded = ref(false);
const wasDragging = ref(false);

function onDragStart(e) {
  wasDragging.value = true;
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData(
    "application/x-kanban-task",
    JSON.stringify({ taskId: props.task.id, sourceStatus: props.task.status }),
  );
}

function onDragEnd() {
  setTimeout(() => {
    wasDragging.value = false;
  }, 0);
}

function onClick() {
  if (wasDragging.value) return;
  expanded.value = true;
}

const ROLE_COLORS = {
  路由: "bg-blue-100 text-blue-700",
  审核: "bg-amber-100 text-amber-700",
  执行: "bg-emerald-100 text-emerald-700",
};

const roleClass = computed(() => {
  const role = props.task.role || "";
  for (const [key, cls] of Object.entries(ROLE_COLORS)) {
    if (role.includes(key)) return cls;
  }
  return "bg-slate-100 text-slate-600";
});

const priorityClass = computed(() => {
  const p = props.task.priority;
  if (p === 0) return "bg-red-100 text-red-700";
  if (p === 1) return "bg-yellow-100 text-yellow-700";
  return "bg-slate-100 text-slate-600";
});

const relativeTime = computed(() => {
  if (!props.task.updatedAt) return "";
  const now = Date.now();
  const updated = new Date(props.task.updatedAt).getTime();
  const diffSec = Math.max(0, Math.floor((now - updated) / 1000));
  if (diffSec < 60) return "刚刚";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}小时前`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 30) return `${diffDay}天前`;
  return new Date(props.task.updatedAt).toLocaleDateString();
});
</script>
