<template>
  <div
    class="flex w-72 shrink-0 flex-col rounded-2xl p-3 transition-colors"
    :class="isDragOver ? 'bg-blue-50/60 ring-2 ring-blue-300/50' : 'bg-slate-50/80'"
    @dragover.prevent="onDragOver"
    @dragenter.prevent="onDragEnter"
    @dragleave="onDragLeave"
    @drop.prevent="onDrop"
  >
    <div class="mb-3 flex items-center justify-between px-1">
      <div class="flex items-center gap-2">
        <span class="h-2.5 w-2.5 rounded-full" :class="dotColor"></span>
        <h3 class="text-sm font-semibold text-slate-700">{{ title }}</h3>
      </div>
      <span
        class="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full px-1.5 text-[10px] font-bold"
        :class="badgeColor"
      >{{ tasks.length }}</span>
    </div>

    <div class="flex flex-1 flex-col gap-2.5 overflow-y-auto">
      <TaskCard v-for="t in tasks" :key="t.id" :task="t" />

      <div
        v-if="isDragOver"
        class="flex h-16 items-center justify-center rounded-xl border-2 border-dashed border-slate-300 text-xs text-slate-400"
      >
        释放到此处
      </div>

      <p v-if="!tasks.length && !isDragOver" class="py-8 text-center text-xs text-slate-400">暂无任务</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import TaskCard from "./TaskCard.vue";

const props = defineProps({
  title: { type: String, required: true },
  status: { type: String, required: true },
  tasks: { type: Array, default: () => [] },
  color: { type: String, default: "slate" },
});

const emit = defineEmits(["drop"]);

const COLOR_MAP = {
  slate: { dot: "bg-slate-400", badge: "bg-slate-200 text-slate-600" },
  blue: { dot: "bg-blue-500", badge: "bg-blue-100 text-blue-700" },
  amber: { dot: "bg-amber-500", badge: "bg-amber-100 text-amber-700" },
  orange: { dot: "bg-orange-500", badge: "bg-orange-100 text-orange-700" },
  emerald: { dot: "bg-emerald-500", badge: "bg-emerald-100 text-emerald-700" },
  red: { dot: "bg-red-500", badge: "bg-red-100 text-red-700" },
};

const palette = computed(() => COLOR_MAP[props.color] || COLOR_MAP.slate);
const dotColor = computed(() => palette.value.dot);
const badgeColor = computed(() => palette.value.badge);

const isDragOver = ref(false);
let dragEnterDepth = 0;

function onDragOver(e) {
  e.dataTransfer.dropEffect = "move";
}

function onDragEnter() {
  dragEnterDepth++;
  isDragOver.value = true;
}

function onDragLeave() {
  dragEnterDepth--;
  if (dragEnterDepth <= 0) {
    dragEnterDepth = 0;
    isDragOver.value = false;
  }
}

function onDrop(e) {
  isDragOver.value = false;
  dragEnterDepth = 0;
  try {
    const raw = e.dataTransfer.getData("application/x-kanban-task");
    if (!raw) return;
    const { taskId, sourceStatus } = JSON.parse(raw);
    if (sourceStatus === props.status) return;
    emit("drop", { taskId, targetState: props.status });
  } catch {
    /* ignore invalid transfer data */
  }
}
</script>
