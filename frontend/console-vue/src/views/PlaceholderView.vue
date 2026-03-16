<template>
  <div class="flex min-h-[60vh] items-center justify-center">
    <div class="glass-panel animate-fade-up px-12 py-10 text-center">
      <p class="text-5xl">🚧</p>
      <h2 class="mt-4 text-xl font-bold text-slate-900">{{ panelName }}</h2>
      <p class="mt-2 text-sm text-slate-500">功能开发中</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  panelName: { type: String, default: "未知面板" },
});
</script>
