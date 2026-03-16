<template>
  <section class="flex gap-6" style="min-height: calc(100vh - 8rem)">
    <!-- Left: template list -->
    <div class="w-64 shrink-0 space-y-2">
      <h3 class="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">模板列表</h3>
      <div
        v-for="tpl in templates"
        :key="tpl.name"
        class="glass-panel cursor-pointer px-4 py-3 transition-all"
        :class="selected === tpl.name
          ? 'ring-2 ring-cyan-500/60 shadow-md'
          : 'hover:shadow-md'"
        @click="selectTemplate(tpl.name)"
      >
        <div class="flex items-center justify-between">
          <span class="text-sm font-semibold text-slate-900">{{ tpl.name }}</span>
          <span
            v-if="tpl.name === activeName"
            class="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-700"
          >活跃</span>
        </div>
        <p class="mt-1 line-clamp-2 text-xs text-slate-500">{{ tpl.description }}</p>
        <p class="mt-1 text-[10px] text-slate-400">{{ tpl.jobCount }} 个任务</p>
      </div>

      <div v-if="!templates.length && !listLoading" class="p-4 text-center text-xs text-slate-400">
        未找到 workflow-jobs.*.json 模板文件
      </div>
    </div>

    <!-- Right: template preview -->
    <div class="min-w-0 flex-1">
      <div v-if="detailLoading" class="flex h-40 items-center justify-center text-sm text-slate-400">
        加载中...
      </div>

      <div v-else-if="detail">
        <TemplatePreview :template="detail" />

        <div class="mt-6 flex items-center gap-3">
          <button
            v-if="selected !== activeName"
            class="rounded-xl bg-cyan-700 px-5 py-2 text-sm font-semibold text-white shadow-md transition-colors hover:bg-cyan-800 disabled:opacity-50"
            :disabled="activating"
            @click="activateTemplate"
          >
            {{ activating ? '切换中...' : '应用此模板' }}
          </button>
          <span
            v-else
            class="rounded-xl bg-emerald-50 px-5 py-2 text-sm font-semibold text-emerald-700"
          >
            当前活跃模板
          </span>
          <span v-if="activateMsg" class="text-xs" :class="activateOk ? 'text-emerald-600' : 'text-red-500'">
            {{ activateMsg }}
          </span>
        </div>
      </div>

      <div v-else class="flex h-40 items-center justify-center text-sm text-slate-400">
        请选择左侧模板查看详情
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import TemplatePreview from "../components/TemplatePreview.vue";

const templates = ref([]);
const listLoading = ref(true);
const selected = ref("");
const activeName = ref("default");
const detail = ref(null);
const detailLoading = ref(false);
const activating = ref(false);
const activateMsg = ref("");
const activateOk = ref(false);

async function fetchList() {
  listLoading.value = true;
  try {
    const resp = await fetch("/api/templates");
    if (!resp.ok) return;
    const data = await resp.json();
    templates.value = data?.templates ?? [];
    activeName.value = data?.active ?? "default";
    if (templates.value.length && !selected.value) {
      selectTemplate(activeName.value || templates.value[0].name);
    }
  } catch {
    /* ignore */
  } finally {
    listLoading.value = false;
  }
}

async function selectTemplate(name) {
  selected.value = name;
  activateMsg.value = "";
  detailLoading.value = true;
  detail.value = null;
  try {
    const resp = await fetch(`/api/templates/${encodeURIComponent(name)}`);
    if (!resp.ok) return;
    const data = await resp.json();
    detail.value = data?.template ?? null;
  } catch {
    /* ignore */
  } finally {
    detailLoading.value = false;
  }
}

async function activateTemplate() {
  activating.value = true;
  activateMsg.value = "";
  try {
    const resp = await fetch("/api/templates/activate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: selected.value }),
    });
    const data = await resp.json();
    if (data?.ok) {
      activeName.value = data.active;
      activateOk.value = true;
      activateMsg.value = "切换成功";
    } else {
      activateOk.value = false;
      activateMsg.value = data?.error ?? "切换失败";
    }
  } catch (e) {
    activateOk.value = false;
    activateMsg.value = "网络错误";
  } finally {
    activating.value = false;
  }
}

onMounted(fetchList);
</script>
