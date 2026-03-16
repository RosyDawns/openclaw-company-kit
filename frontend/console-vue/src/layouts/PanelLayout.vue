<template>
  <div class="flex min-h-screen">
    <aside
      class="fixed inset-y-0 left-0 z-30 flex flex-col border-r border-white/40 bg-white/70 backdrop-blur-md transition-[width] duration-300"
      :class="collapsed ? 'w-16' : 'w-60'"
    >
      <div class="flex h-14 shrink-0 items-center gap-3 border-b border-white/40 px-3">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-cyan-700/90 text-white shadow-lg">
          <svg viewBox="0 0 24 24" fill="none" class="h-5 w-5">
            <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
          </svg>
        </div>
        <div v-if="!collapsed" class="min-w-0">
          <p class="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-700">OpenClaw</p>
          <p class="truncate text-xs font-semibold text-slate-800">Console</p>
        </div>
      </div>

      <nav class="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
        <RouterLink
          v-for="panel in sortedPanels"
          :key="panel.id"
          :to="routerPath(panel)"
          class="flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors"
          :class="isActive(panel) ? 'bg-cyan-700 text-white shadow-md' : 'text-slate-600 hover:bg-white/80 hover:text-slate-900'"
          :title="collapsed ? panel.name : undefined"
        >
          <span class="shrink-0 text-base leading-none">{{ panel.icon }}</span>
          <span v-if="!collapsed" class="truncate">{{ panel.name }}</span>
        </RouterLink>
      </nav>

      <div class="shrink-0 border-t border-white/40 px-2 py-2">
        <button
          class="flex w-full items-center justify-center rounded-xl px-3 py-2 text-slate-400 transition-colors hover:bg-white/80 hover:text-slate-700"
          @click="collapsed = !collapsed"
        >
          <svg
            class="h-4 w-4 shrink-0 transition-transform duration-300"
            :class="collapsed && 'rotate-180'"
            viewBox="0 0 24 24"
            fill="none"
          >
            <path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span v-if="!collapsed" class="ml-2 text-xs">收起</span>
        </button>
        <p v-if="!collapsed" class="mt-1 text-center text-[10px] text-slate-400">v0.1.0</p>
      </div>
    </aside>

    <div
      class="flex flex-1 flex-col transition-[margin-left] duration-300"
      :class="collapsed ? 'ml-16' : 'ml-60'"
    >
      <header class="sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between border-b border-white/40 bg-white/50 px-6 backdrop-blur-md">
        <h2 class="text-lg font-semibold text-slate-900">{{ currentPanelName }}</h2>
      </header>

      <main class="flex-1 overflow-y-auto">
        <div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <RouterView />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { panels } from "../panels/registry";

const route = useRoute();
const collapsed = ref(false);

const sortedPanels = computed(() => [...panels].sort((a, b) => a.order - b.order));

function routerPath(panel) {
  return panel.route.replace(/^\/ui/, "") || "/";
}

function isActive(panel) {
  const path = routerPath(panel);
  if (route.path === path) return true;
  if (path !== "/" && route.path.startsWith(path + "/")) return true;
  if (panel.id === "overview" && route.path === "/dashboard") return true;
  if (panel.id === "monitor" && route.path === "/dashboard/runtime") return true;
  return false;
}

const currentPanelName = computed(() => {
  const matched = sortedPanels.value.find((p) => isActive(p));
  if (matched) return matched.name;
  if (route.path.startsWith("/dashboard/")) return "角色视图";
  return "";
});

function onResize() {
  collapsed.value = window.innerWidth < 768;
}

onMounted(() => {
  onResize();
  window.addEventListener("resize", onResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", onResize);
});
</script>
