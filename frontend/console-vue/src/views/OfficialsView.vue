<template>
  <section class="space-y-6">
    <!-- Layer Diagram -->
    <div>
      <h3 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">角色架构</h3>
      <div class="glass-panel p-5">
        <LayerDiagram :roles="roles" :layers="layers" />
      </div>
    </div>

    <!-- Filter tabs -->
    <div class="flex gap-2">
      <button
        v-for="tab in filterTabs"
        :key="tab.key"
        class="rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors"
        :class="activeFilter === tab.key
          ? 'bg-cyan-700 text-white shadow-md'
          : 'bg-white/70 text-slate-600 hover:bg-white hover:text-slate-900'"
        @click="activeFilter = tab.key"
      >
        {{ tab.label }}
        <span class="ml-1 opacity-60">{{ tab.count }}</span>
      </button>
    </div>

    <!-- Role cards grid -->
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <RoleCard
        v-for="role in filteredRoles"
        :key="role.name"
        :role="role"
      />
    </div>

    <div
      v-if="!roles.length && !loading"
      class="glass-panel p-8 text-center text-sm text-slate-400"
    >
      暂无角色数据，请检查 engine/role_config.json 是否存在
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import LayerDiagram from "../components/LayerDiagram.vue";
import RoleCard from "../components/RoleCard.vue";

const roles = ref([]);
const layers = ref([]);
const loading = ref(true);
const activeFilter = ref("all");

const filterTabs = computed(() => {
  const all = roles.value;
  const counts = { all: all.length, dispatcher: 0, reviewer: 0, executor: 0 };
  for (const r of all) {
    let k = r.layer;
    if (k === "dispatcher_sub") k = "dispatcher";
    if (k === "executor_sub") k = "executor";
    if (counts[k] !== undefined) counts[k]++;
  }
  return [
    { key: "all", label: "全部", count: counts.all },
    { key: "dispatcher", label: "路由层", count: counts.dispatcher },
    { key: "reviewer", label: "审核层", count: counts.reviewer },
    { key: "executor", label: "执行层", count: counts.executor },
  ];
});

const filteredRoles = computed(() => {
  if (activeFilter.value === "all") return roles.value;
  return roles.value.filter((r) => {
    let k = r.layer;
    if (k === "dispatcher_sub") k = "dispatcher";
    if (k === "executor_sub") k = "executor";
    return k === activeFilter.value;
  });
});

async function fetchOfficials() {
  loading.value = true;
  try {
    const resp = await fetch("/api/officials");
    if (!resp.ok) return;
    const data = await resp.json();
    roles.value = data?.roles ?? [];
    layers.value = data?.layers ?? [];
  } catch {
    /* ignore */
  } finally {
    loading.value = false;
  }
}

onMounted(fetchOfficials);
</script>
