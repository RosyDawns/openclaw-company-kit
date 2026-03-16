<template>
  <div class="relative" ref="containerRef">
    <svg
      :viewBox="`0 0 ${svgW} ${svgH}`"
      preserveAspectRatio="xMidYMid meet"
      class="w-full"
    >
      <!-- Y-axis grid lines -->
      <line
        v-for="y in yGridLines"
        :key="'gy-' + y.val"
        :x1="pad.left"
        :y1="y.y"
        :x2="svgW - pad.right"
        :y2="y.y"
        stroke="#e2e8f0"
        stroke-width="0.5"
      />
      <!-- Y-axis labels -->
      <text
        v-for="y in yGridLines"
        :key="'ly-' + y.val"
        :x="pad.left - 6"
        :y="y.y + 3"
        text-anchor="end"
        class="fill-slate-400"
        font-size="10"
      >{{ y.val }}</text>

      <!-- X-axis labels -->
      <text
        v-for="(pt, i) in chartPoints"
        :key="'lx-' + i"
        :x="pt.x"
        :y="svgH - 4"
        text-anchor="middle"
        class="fill-slate-400"
        font-size="10"
      >{{ pt.label }}</text>

      <!-- Success line -->
      <polyline
        :points="successLine"
        fill="none"
        stroke="#10b981"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <!-- Failure line -->
      <polyline
        :points="failureLine"
        fill="none"
        stroke="#ef4444"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />

      <!-- Success area fill -->
      <polygon
        :points="successArea"
        fill="url(#successGrad)"
      />
      <!-- Failure area fill -->
      <polygon
        :points="failureArea"
        fill="url(#failureGrad)"
      />

      <!-- Gradient defs -->
      <defs>
        <linearGradient id="successGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#10b981" stop-opacity="0.18" />
          <stop offset="100%" stop-color="#10b981" stop-opacity="0" />
        </linearGradient>
        <linearGradient id="failureGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#ef4444" stop-opacity="0.12" />
          <stop offset="100%" stop-color="#ef4444" stop-opacity="0" />
        </linearGradient>
      </defs>

      <!-- Data points (success) -->
      <circle
        v-for="(pt, i) in chartPoints"
        :key="'cs-' + i"
        :cx="pt.x"
        :cy="pt.sy"
        r="3"
        fill="#10b981"
        class="cursor-pointer"
        @mouseenter="showTip(i, $event)"
        @mouseleave="hideTip"
      />
      <!-- Data points (failure) -->
      <circle
        v-for="(pt, i) in chartPoints"
        :key="'cf-' + i"
        :cx="pt.x"
        :cy="pt.fy"
        r="3"
        fill="#ef4444"
        class="cursor-pointer"
        @mouseenter="showTip(i, $event)"
        @mouseleave="hideTip"
      />
    </svg>

    <!-- Tooltip -->
    <div
      v-if="tip.visible"
      class="pointer-events-none absolute z-10 rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-xs shadow-lg backdrop-blur"
      :style="{ left: tip.x + 'px', top: tip.y + 'px' }"
    >
      <p class="font-semibold text-slate-700">{{ tip.date }}</p>
      <p class="mt-0.5 text-emerald-600">成功: {{ tip.success }}</p>
      <p class="text-red-500">失败: {{ tip.failure }}</p>
    </div>

    <!-- Legend -->
    <div class="mt-2 flex items-center justify-center gap-5 text-xs text-slate-500">
      <span class="flex items-center gap-1.5">
        <span class="inline-block h-2 w-4 rounded-full bg-emerald-500"></span>成功
      </span>
      <span class="flex items-center gap-1.5">
        <span class="inline-block h-2 w-4 rounded-full bg-red-500"></span>失败
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from "vue";

const props = defineProps({
  data: { type: Array, default: () => [] },
});

const containerRef = ref(null);
const svgW = 520;
const svgH = 220;
const pad = { top: 16, right: 16, bottom: 28, left: 36 };

const tip = reactive({ visible: false, x: 0, y: 0, date: "", success: 0, failure: 0 });

const maxVal = computed(() => {
  if (!props.data.length) return 10;
  let m = 0;
  for (const d of props.data) {
    if (d.success > m) m = d.success;
    if (d.failure > m) m = d.failure;
  }
  return Math.max(m, 1);
});

const yGridLines = computed(() => {
  const steps = 4;
  const lines = [];
  const plotH = svgH - pad.top - pad.bottom;
  for (let i = 0; i <= steps; i++) {
    const val = Math.round((maxVal.value / steps) * (steps - i));
    const y = pad.top + (plotH / steps) * i;
    lines.push({ val, y });
  }
  return lines;
});

const chartPoints = computed(() => {
  const n = props.data.length;
  if (!n) return [];
  const plotW = svgW - pad.left - pad.right;
  const plotH = svgH - pad.top - pad.bottom;
  const mx = maxVal.value;

  return props.data.map((d, i) => {
    const x = n === 1 ? pad.left + plotW / 2 : pad.left + (plotW / (n - 1)) * i;
    const sy = pad.top + plotH - (d.success / mx) * plotH;
    const fy = pad.top + plotH - (d.failure / mx) * plotH;
    const label = (d.date || "").slice(5);
    return { x, sy, fy, label };
  });
});

const successLine = computed(() => chartPoints.value.map((p) => `${p.x},${p.sy}`).join(" "));
const failureLine = computed(() => chartPoints.value.map((p) => `${p.x},${p.fy}`).join(" "));

const successArea = computed(() => {
  const pts = chartPoints.value;
  if (pts.length < 2) return "";
  const baseY = svgH - pad.bottom;
  const top = pts.map((p) => `${p.x},${p.sy}`).join(" ");
  return `${top} ${pts[pts.length - 1].x},${baseY} ${pts[0].x},${baseY}`;
});

const failureArea = computed(() => {
  const pts = chartPoints.value;
  if (pts.length < 2) return "";
  const baseY = svgH - pad.bottom;
  const top = pts.map((p) => `${p.x},${p.fy}`).join(" ");
  return `${top} ${pts[pts.length - 1].x},${baseY} ${pts[0].x},${baseY}`;
});

function showTip(idx, event) {
  const d = props.data[idx];
  if (!d) return;
  const rect = containerRef.value?.getBoundingClientRect();
  if (!rect) return;
  const ex = event.clientX - rect.left;
  const ey = event.clientY - rect.top;
  tip.x = ex + 12;
  tip.y = ey - 40;
  tip.date = d.date;
  tip.success = d.success;
  tip.failure = d.failure;
  tip.visible = true;
}

function hideTip() {
  tip.visible = false;
}
</script>
