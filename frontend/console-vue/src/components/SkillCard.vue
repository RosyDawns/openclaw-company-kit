<template>
  <div
    class="glass-panel group relative flex flex-col gap-3 p-5 transition-shadow hover:shadow-lg"
  >
    <!-- Header: name + version -->
    <div class="flex items-start justify-between gap-2">
      <h3 class="truncate text-base font-bold text-slate-900">{{ skill.name }}</h3>
      <span
        class="shrink-0 rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold text-indigo-700"
      >
        v{{ skill.version || '1.0.0' }}
      </span>
    </div>

    <!-- Author -->
    <p v-if="skill.author" class="text-xs text-slate-500">
      by <span class="font-medium text-slate-600">{{ skill.author }}</span>
    </p>

    <!-- Description (2-line clamp) -->
    <p class="line-clamp-2 min-h-[2.5rem] text-sm leading-relaxed text-slate-600">
      {{ skill.description || '暂无描述' }}
    </p>

    <!-- Compatible roles -->
    <div v-if="skill.compatible_roles?.length" class="flex flex-wrap gap-1.5">
      <span
        v-for="role in skill.compatible_roles"
        :key="role"
        class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
        :class="roleColor(role)"
      >
        {{ role }}
      </span>
    </div>

    <!-- Actions -->
    <div class="mt-auto flex items-center gap-2 border-t border-slate-100 pt-3">
      <button
        class="rounded-md bg-sky-50 px-3 py-1.5 text-xs font-semibold text-sky-700 transition-colors hover:bg-sky-100 disabled:opacity-50"
        :disabled="updating"
        @click="onUpdate"
      >
        {{ updating ? '更新中…' : '更新' }}
      </button>
      <button
        v-if="!confirmingRemove"
        class="rounded-md bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-600 transition-colors hover:bg-red-100 disabled:opacity-50"
        :disabled="removing"
        @click="confirmingRemove = true"
      >
        卸载
      </button>
      <template v-else>
        <span class="text-xs text-red-500">确认卸载？</span>
        <button
          class="rounded-md bg-red-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-red-700"
          :disabled="removing"
          @click="onRemove"
        >
          {{ removing ? '卸载中…' : '确定' }}
        </button>
        <button
          class="rounded-md bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-600 transition-colors hover:bg-slate-200"
          @click="confirmingRemove = false"
        >
          取消
        </button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
  skill: { type: Object, required: true },
});

const emit = defineEmits(["updated", "removed"]);

const updating = ref(false);
const removing = ref(false);
const confirmingRemove = ref(false);

const ROLE_COLORS = [
  "bg-violet-100 text-violet-700",
  "bg-emerald-100 text-emerald-700",
  "bg-amber-100 text-amber-700",
  "bg-sky-100 text-sky-700",
  "bg-rose-100 text-rose-700",
  "bg-teal-100 text-teal-700",
];

function roleColor(role) {
  let hash = 0;
  for (let i = 0; i < role.length; i++) hash = (hash * 31 + role.charCodeAt(i)) | 0;
  return ROLE_COLORS[Math.abs(hash) % ROLE_COLORS.length];
}

async function onUpdate() {
  updating.value = true;
  try {
    const resp = await fetch(`/api/skills/update/${encodeURIComponent(props.skill.name)}`, {
      method: "POST",
    });
    const data = await resp.json();
    if (data.ok) {
      emit("updated", data.skill);
    } else {
      alert(data.error || "更新失败");
    }
  } catch (e) {
    alert("网络错误：" + e.message);
  } finally {
    updating.value = false;
  }
}

async function onRemove() {
  removing.value = true;
  try {
    const resp = await fetch(`/api/skills/remove/${encodeURIComponent(props.skill.name)}`, {
      method: "POST",
    });
    const data = await resp.json();
    if (data.ok) {
      emit("removed", props.skill.name);
    } else {
      alert(data.error || "卸载失败");
    }
  } catch (e) {
    alert("网络错误：" + e.message);
  } finally {
    removing.value = false;
    confirmingRemove.value = false;
  }
}
</script>
