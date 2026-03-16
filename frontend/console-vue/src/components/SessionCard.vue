<template>
  <div
    class="glass-panel cursor-pointer transition-all hover:shadow-md"
    :class="expanded && 'ring-1 ring-cyan-300/50'"
    @click="expanded = !expanded"
  >
    <div class="flex items-center gap-3 px-4 py-3">
      <span class="shrink-0 text-lg leading-none">{{ statusIcon }}</span>

      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-semibold text-slate-900">{{ session.name || '未命名任务' }}</p>
        <p class="mt-0.5 text-xs text-slate-500">
          {{ session.startedAt || '—' }}
          <template v-if="session.finishedAt"> → {{ session.finishedAt }}</template>
        </p>
      </div>

      <span
        v-if="session.role && session.role !== '—'"
        class="shrink-0 rounded-full bg-cyan-100 px-2 py-0.5 text-[10px] font-bold text-cyan-700"
      >
        {{ session.role }}
      </span>

      <span class="shrink-0 text-xs font-medium text-slate-400">
        {{ formattedDuration }}
      </span>

      <svg
        class="h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200"
        :class="expanded && 'rotate-180'"
        viewBox="0 0 24 24"
        fill="none"
      >
        <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </div>

    <p
      v-if="session.status === 'failed' && session.error && !expanded"
      class="truncate border-t border-red-100 px-4 py-2 text-xs text-red-500"
    >
      {{ session.error }}
    </p>

    <div v-if="expanded" class="border-t border-slate-200/60 px-4 py-3">
      <div v-if="session.error" class="mb-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
        {{ session.error }}
      </div>

      <div v-if="session.logs && session.logs.length" class="space-y-1">
        <p class="text-[10px] font-semibold uppercase tracking-wide text-slate-400">执行日志</p>
        <div class="max-h-48 overflow-y-auto rounded-lg bg-slate-50 p-2 font-mono text-[11px] leading-relaxed text-slate-600">
          <p v-for="(line, idx) in session.logs" :key="idx">{{ line }}</p>
        </div>
      </div>

      <p v-else class="text-xs text-slate-400">暂无详细日志</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  session: { type: Object, required: true },
});

const expanded = ref(false);

const statusIcon = computed(() => {
  const s = props.session.status;
  if (s === "success") return "\u2705";
  if (s === "failed") return "\u274C";
  return "\u23F3";
});

const formattedDuration = computed(() => {
  const sec = props.session.durationSec;
  if (sec == null) return "—";
  const s = Math.round(sec);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
});
</script>
