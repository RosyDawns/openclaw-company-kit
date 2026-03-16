<template>
  <div class="min-w-[600px] space-y-2.5">
    <!-- Hour labels -->
    <div class="flex text-[10px] text-slate-400">
      <span class="w-28 shrink-0"></span>
      <div class="flex flex-1 justify-between">
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>24:00</span>
      </div>
    </div>

    <!-- Role rows -->
    <div
      v-for="(role, ri) in normalizedRoles"
      :key="role.name"
      class="group flex items-center"
    >
      <span class="w-28 shrink-0 truncate pr-3 text-right text-xs font-medium text-slate-600">
        {{ role.displayName || role.name }}
      </span>
      <div class="relative h-5 flex-1 rounded bg-slate-100 transition-shadow group-hover:shadow-sm">
        <div
          v-for="(seg, si) in role.segments"
          :key="si"
          class="absolute inset-y-0.5 rounded transition-opacity group-hover:opacity-90"
          :class="colorForIndex(ri)"
          :style="{ left: seg.left + '%', width: seg.width + '%' }"
          :title="`${formatHour(seg.startHour)}–${formatHour(seg.endHour)}`"
        ></div>
      </div>
    </div>

    <div v-if="!roles.length" class="py-4 text-center text-sm text-slate-400">
      暂无角色活跃数据
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  roles: { type: Array, default: () => [] },
});

const COLORS = [
  "bg-cyan-400/70",
  "bg-violet-400/70",
  "bg-amber-400/70",
  "bg-emerald-400/70",
  "bg-rose-400/70",
  "bg-sky-400/70",
  "bg-orange-400/70",
  "bg-teal-400/70",
];

function colorForIndex(i) {
  return COLORS[i % COLORS.length];
}

function formatHour(h) {
  const hh = Math.floor(h);
  const mm = Math.round((h - hh) * 60);
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

const normalizedRoles = computed(() =>
  props.roles.map((role) => {
    const segments = (role.activeSlots || []).map((slot) => {
      const startHour = slot[0] ?? 0;
      const endHour = slot[1] ?? startHour + 1;
      return {
        left: (startHour / 24) * 100,
        width: ((endHour - startHour) / 24) * 100,
        startHour,
        endHour,
      };
    });
    return {
      name: role.name,
      displayName: role.displayName || role.name,
      segments,
    };
  }),
);
</script>
