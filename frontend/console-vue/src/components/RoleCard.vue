<template>
  <div
    class="glass-panel cursor-pointer overflow-hidden transition-all hover:shadow-lg"
    @click="expanded = !expanded"
  >
    <div class="p-4">
      <!-- Header -->
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <h4 class="truncate text-sm font-bold text-slate-900">{{ role.displayName }}</h4>
          <p class="mt-0.5 truncate text-xs text-slate-400 font-mono">{{ role.name }}</p>
        </div>
        <span
          class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
          :class="layerBadgeClass"
        >
          {{ role.layerLabel }}
        </span>
      </div>

      <!-- Capabilities -->
      <div class="mt-3 flex flex-wrap gap-1">
        <span
          v-for="cap in role.capabilities"
          :key="cap"
          class="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500"
        >
          {{ cap }}
        </span>
      </div>

      <!-- WIP & Last active -->
      <div class="mt-3 flex items-center justify-between text-xs text-slate-500">
        <span class="flex items-center gap-1">
          <span class="font-semibold" :class="wipColor">{{ role.wipCurrent ?? 0 }}</span>
          <span>/</span>
          <span>{{ role.wipLimit }}</span>
          <span class="ml-0.5 text-slate-400">WIP</span>
        </span>
        <span class="truncate text-slate-400" :title="role.lastActive">
          {{ formattedTime }}
        </span>
      </div>
    </div>

    <!-- Expanded details -->
    <transition name="slide">
      <div v-if="expanded" class="border-t border-slate-100 bg-slate-50/50 px-4 py-3 text-xs">
        <!-- Cron jobs -->
        <div v-if="role.cronJobs?.length">
          <p class="mb-1 font-semibold text-slate-600">定时任务</p>
          <ul class="space-y-0.5 text-slate-500">
            <li v-for="job in role.cronJobs" :key="job" class="flex items-center gap-1">
              <span class="text-slate-300">-</span> {{ job }}
            </li>
          </ul>
        </div>
        <!-- Dependencies -->
        <div v-if="role.dependencies?.length" class="mt-2">
          <p class="mb-1 font-semibold text-slate-600">依赖角色</p>
          <div class="flex flex-wrap gap-1">
            <span
              v-for="dep in role.dependencies"
              :key="dep"
              class="rounded bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-500 shadow-sm"
            >
              {{ dep }}
            </span>
          </div>
        </div>
        <!-- Allowed callees -->
        <div v-if="role.allowedCallees?.length" class="mt-2">
          <p class="mb-1 font-semibold text-slate-600">可调用角色</p>
          <div class="flex flex-wrap gap-1">
            <span
              v-for="callee in role.allowedCallees"
              :key="callee"
              class="rounded bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-500 shadow-sm"
            >
              {{ callee }}
            </span>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  role: { type: Object, required: true },
});

const expanded = ref(false);

const layerBadgeClass = computed(() => {
  const l = props.role.layer;
  if (l === "dispatcher" || l === "dispatcher_sub")
    return "bg-blue-100 text-blue-700";
  if (l === "reviewer")
    return "bg-orange-100 text-orange-700";
  return "bg-emerald-100 text-emerald-700";
});

const wipColor = computed(() => {
  const cur = props.role.wipCurrent ?? 0;
  const lim = props.role.wipLimit ?? 1;
  if (cur >= lim) return "text-red-500";
  if (cur > 0) return "text-amber-500";
  return "text-slate-500";
});

const formattedTime = computed(() => {
  if (!props.role.lastActive) return "—";
  try {
    const d = new Date(props.role.lastActive);
    return d.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return props.role.lastActive;
  }
});
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.slide-enter-from,
.slide-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.slide-enter-to,
.slide-leave-from {
  max-height: 300px;
  opacity: 1;
}
</style>
