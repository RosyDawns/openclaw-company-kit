<template>
  <div class="min-h-screen">
    <header class="mx-auto max-w-7xl px-4 pb-2 pt-4 sm:px-6 lg:px-8">
      <nav class="glass-panel animate-fade-up px-4 py-3 sm:px-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <div class="h-9 w-9 rounded-xl bg-cyan-700/90 p-2 text-white shadow-lg">
              <svg viewBox="0 0 24 24" fill="none" class="h-full w-full">
                <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
              </svg>
            </div>
            <div>
              <p class="text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-700">OpenClaw</p>
              <h1 class="text-lg font-semibold text-slate-900">Console UI</h1>
            </div>
          </div>
          <div class="flex flex-wrap gap-2 text-sm">
            <RouterLink to="/setup" class="rounded-xl px-3 py-1.5 font-medium transition" :class="route.path.startsWith('/setup') ? 'bg-cyan-700 text-white' : 'bg-white text-slate-700 hover:bg-cyan-50'">配置中心</RouterLink>
            <RouterLink to="/dashboard" class="rounded-xl px-3 py-1.5 font-medium transition" :class="route.path.startsWith('/dashboard') ? 'bg-cyan-700 text-white' : 'bg-white text-slate-700 hover:bg-cyan-50'">驾驶舱</RouterLink>
          </div>
        </div>
      </nav>
    </header>
    <main class="mx-auto max-w-7xl px-4 pb-8 sm:px-6 lg:px-8">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { useRoute } from "vue-router";

const route = useRoute();
</script>
