<template>
  <div class="space-y-4">
    <!-- Template header -->
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-lg font-bold text-slate-900">{{ template.name }}</h3>
        <p v-if="template.description" class="mt-0.5 text-sm text-slate-500">
          {{ template.description }}
        </p>
      </div>
      <span class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
        {{ jobs.length }} 个任务
      </span>
    </div>

    <!-- Jobs list -->
    <div class="space-y-3">
      <div
        v-for="(job, idx) in jobs"
        :key="idx"
        class="glass-panel p-4"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <h4 class="truncate text-sm font-semibold text-slate-900">{{ job.name }}</h4>
            <p
              v-if="job.message"
              class="mt-1 line-clamp-2 text-xs text-slate-500"
            >{{ job.message }}</p>
          </div>
          <span
            class="shrink-0 rounded bg-cyan-100 px-2 py-0.5 text-[10px] font-bold text-cyan-700"
          >
            {{ job.agent }}
          </span>
        </div>
        <div class="mt-2.5 flex flex-wrap items-center gap-3 text-xs text-slate-400">
          <span class="flex items-center gap-1" :title="'Cron: ' + job.cron">
            <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" />
              <path d="M12 7v5l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            </svg>
            <code class="font-mono">{{ job.cron }}</code>
          </span>
          <span v-if="job.timeoutSeconds" class="flex items-center gap-1">
            <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
              <path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            </svg>
            {{ job.timeoutSeconds }}s
          </span>
          <span v-if="job.tz" class="text-slate-300">{{ job.tz }}</span>
        </div>
      </div>
    </div>

    <div v-if="!jobs.length" class="p-6 text-center text-sm text-slate-400">
      此模板暂无任务
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  template: { type: Object, required: true },
});

const jobs = computed(() => props.template.jobs ?? []);
</script>
