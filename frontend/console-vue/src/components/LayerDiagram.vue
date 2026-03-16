<template>
  <div class="space-y-1">
    <div
      v-for="(layer, idx) in layerRows"
      :key="layer.key"
      class="relative"
    >
      <!-- Arrow between layers -->
      <div
        v-if="idx > 0"
        class="flex justify-center py-0.5"
      >
        <div class="h-4 w-px bg-slate-300"></div>
        <div class="absolute left-1/2 -translate-x-1/2 translate-y-2">
          <div class="h-0 w-0 border-l-[5px] border-r-[5px] border-t-[6px] border-l-transparent border-r-transparent border-t-slate-300"></div>
        </div>
      </div>

      <!-- Layer bar -->
      <div
        class="flex items-center gap-3 rounded-xl border px-4 py-2.5 transition-shadow"
        :class="layerBarClass(layer.key)"
      >
        <span class="shrink-0 text-xs font-bold uppercase tracking-wider opacity-80">
          {{ layer.label }}
        </span>
        <div class="flex flex-1 flex-wrap gap-2">
          <span
            v-for="role in layer.roles"
            :key="role.name"
            class="inline-flex items-center gap-1.5 rounded-lg bg-white/60 px-2.5 py-1 text-xs font-medium shadow-sm"
          >
            <span class="h-2 w-2 rounded-full" :class="dotClass(layer.key)"></span>
            {{ role.displayName }}
          </span>
          <span
            v-if="!layer.roles.length"
            class="text-xs italic opacity-60"
          >暂无角色</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  roles: { type: Array, default: () => [] },
  layers: { type: Array, default: () => [] },
});

const layerRows = computed(() => {
  const defaultLayers = [
    { key: "dispatcher", label: "路由层", order: 0 },
    { key: "reviewer", label: "审核层", order: 1 },
    { key: "executor", label: "执行层", order: 2 },
  ];
  const src = props.layers.length ? props.layers : defaultLayers;
  const layerMap = new Map();
  for (const l of src) {
    layerMap.set(l.key, { ...l, roles: [] });
  }
  for (const role of props.roles) {
    let key = role.layer;
    if (key === "dispatcher_sub") key = "dispatcher";
    if (key === "executor_sub") key = "executor";
    const bucket = layerMap.get(key);
    if (bucket) bucket.roles.push(role);
  }
  return [...layerMap.values()].sort((a, b) => a.order - b.order);
});

function layerBarClass(key) {
  if (key === "dispatcher") return "border-blue-200 bg-blue-50/70 text-blue-800";
  if (key === "reviewer") return "border-orange-200 bg-orange-50/70 text-orange-800";
  return "border-emerald-200 bg-emerald-50/70 text-emerald-800";
}

function dotClass(key) {
  if (key === "dispatcher") return "bg-blue-500";
  if (key === "reviewer") return "bg-orange-500";
  return "bg-emerald-500";
}
</script>
