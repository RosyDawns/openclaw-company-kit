<template>
  <section class="space-y-6">
    <!-- Toolbar -->
    <div class="flex flex-wrap items-center gap-3">
      <button
        class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700"
        @click="showInstallModal = true"
      >
        + 安装新 Skill
      </button>

      <div class="relative flex-1 sm:max-w-xs">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索已安装 Skill…"
          class="w-full rounded-lg border border-slate-200 bg-white/80 px-3 py-2 pl-9 text-sm text-slate-700 shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
        />
        <svg
          class="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400"
          fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
        >
          <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
        </svg>
      </div>

      <button
        class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50"
        :disabled="loading"
        @click="fetchSkills"
      >
        {{ loading ? '加载中…' : '刷新' }}
      </button>
    </div>

    <!-- Card Grid -->
    <div
      v-if="filteredSkills.length"
      class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
    >
      <SkillCard
        v-for="s in filteredSkills"
        :key="s.name"
        :skill="s"
        @updated="onSkillUpdated"
        @removed="onSkillRemoved"
      />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!loading"
      class="glass-panel flex flex-col items-center justify-center gap-3 py-16 text-center"
    >
      <svg class="h-12 w-12 text-slate-300" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5m6 4.125l2.25 2.25m0 0l2.25-2.25M12 13.875V7.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <p class="text-sm text-slate-500">暂无已安装的 Skill，点击上方按钮安装</p>
    </div>

    <!-- Install Modal -->
    <Teleport to="body">
      <div
        v-if="showInstallModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
        @click.self="closeInstallModal"
      >
        <div class="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
          <h2 class="mb-4 text-lg font-bold text-slate-900">安装新 Skill</h2>

          <label class="mb-1 block text-xs font-semibold text-slate-500">Git 仓库 URL *</label>
          <input
            v-model="installForm.repoUrl"
            type="url"
            placeholder="https://github.com/org/skill-name.git"
            class="mb-4 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
          />

          <label class="mb-1 block text-xs font-semibold text-slate-500">Skill 名称（可选，自动推断）</label>
          <input
            v-model="installForm.name"
            type="text"
            placeholder="my-skill"
            class="mb-5 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
          />

          <!-- Result / Error -->
          <div v-if="installResult" class="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">
            Skill「{{ installResult.name }}」安装成功
          </div>
          <div v-if="installError" class="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-600">
            {{ installError }}
          </div>

          <div class="flex justify-end gap-2">
            <button
              class="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
              @click="closeInstallModal"
            >
              关闭
            </button>
            <button
              class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
              :disabled="installing || !installForm.repoUrl.trim()"
              @click="doInstall"
            >
              {{ installing ? '安装中…' : '安装' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import SkillCard from "../components/SkillCard.vue";

const skills = ref([]);
const loading = ref(false);
const searchQuery = ref("");

const showInstallModal = ref(false);
const installing = ref(false);
const installResult = ref(null);
const installError = ref("");
const installForm = reactive({ repoUrl: "", name: "" });

const filteredSkills = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return skills.value;
  return skills.value.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      (s.description || "").toLowerCase().includes(q) ||
      (s.author || "").toLowerCase().includes(q) ||
      (s.compatible_roles || []).some((r) => r.toLowerCase().includes(q)),
  );
});

async function fetchSkills() {
  loading.value = true;
  try {
    const resp = await fetch("/api/skills");
    if (!resp.ok) return;
    const data = await resp.json();
    skills.value = data?.skills ?? [];
  } catch {
    /* ignore */
  } finally {
    loading.value = false;
  }
}

function onSkillUpdated(updatedSkill) {
  const idx = skills.value.findIndex((s) => s.name === updatedSkill.name);
  if (idx !== -1) skills.value[idx] = updatedSkill;
  else fetchSkills();
}

function onSkillRemoved(name) {
  skills.value = skills.value.filter((s) => s.name !== name);
}

async function doInstall() {
  installing.value = true;
  installResult.value = null;
  installError.value = "";
  try {
    const resp = await fetch("/api/skills/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repoUrl: installForm.repoUrl.trim(),
        name: installForm.name.trim() || undefined,
      }),
    });
    const data = await resp.json();
    if (data.ok) {
      installResult.value = data.skill;
      installForm.repoUrl = "";
      installForm.name = "";
      fetchSkills();
    } else {
      installError.value = data.error || "安装失败";
    }
  } catch (e) {
    installError.value = "网络错误：" + e.message;
  } finally {
    installing.value = false;
  }
}

function closeInstallModal() {
  showInstallModal.value = false;
  installResult.value = null;
  installError.value = "";
}

onMounted(fetchSkills);
</script>
