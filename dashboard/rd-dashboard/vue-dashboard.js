(function () {
  const ROLE_ORDER = [
    "rd-company",
    "role-product",
    "role-tech-director",
    "role-senior-dev",
    "role-code-reviewer",
    "role-qa-test",
    "role-growth",
  ];

  const ROLE_LABEL = {
    "rd-company": "研发总监",
    "role-product": "产品经理",
    "role-tech-director": "技术总监",
    "role-senior-dev": "高级程序员",
    "role-code-reviewer": "代码 Reviewer",
    "role-qa-test": "测试工程师",
    "role-growth": "增长运营",
  };

  function normalizeRoleId(raw) {
    const text = String(raw || "").trim();
    if (!text) return "";
    if (text.startsWith("owner:")) return text.slice(6);
    return text;
  }

  function roleLabel(roleId) {
    return ROLE_LABEL[roleId] || roleId || "未命名角色";
  }

  function parseTimeToMs(text) {
    if (!text) return 0;
    const direct = Date.parse(text);
    if (!Number.isNaN(direct)) return direct;
    const fixed = String(text).replace(" ", "T");
    const second = Date.parse(fixed);
    if (!Number.isNaN(second)) return second;
    return 0;
  }

  function statusBadgeClass(status) {
    const val = String(status || "").toLowerCase();
    if (val.includes("done") || val.includes("ok") || val.includes("healthy") || val.includes("on_track")) return "ok";
    if (val.includes("blocked") || val.includes("error") || val.includes("fail")) return "error";
    return "warn";
  }

  function ownerMatchesRole(issue, roleId) {
    const role = normalizeRoleId(roleId);
    const owners = Array.isArray(issue?.owners) ? issue.owners : [];
    for (const owner of owners) {
      if (normalizeRoleId(owner) === role) return true;
    }
    return false;
  }

  function issueStatus(issue) {
    return String(issue?.status || issue?.state || "-").toLowerCase();
  }

  function runtimeHealthOf(data) {
    if (typeof window.detectRuntimeHealth === "function") {
      return window.detectRuntimeHealth(data);
    }
    return {
      level: "warn",
      summary: "未检测到健康分类函数",
      failures: [],
    };
  }

  function buildViews(data) {
    const rows = [];
    rows.push({ id: "overview", label: "总览", href: "./index.html" });
    const panel = Array.isArray(data?.agentPanel) ? data.agentPanel : [];
    const ids = new Set(panel.map((x) => String(x?.id || "")).filter(Boolean));
    for (const rid of ROLE_ORDER) {
      if (!ids.has(rid)) continue;
      rows.push({ id: rid, label: roleLabel(rid), href: `./${rid}.html` });
    }
    return rows;
  }

  function buildRoleMap(data) {
    const panel = Array.isArray(data?.agentPanel) ? data.agentPanel : [];
    const map = {};
    for (const role of panel) {
      const id = String(role?.id || "");
      if (!id) continue;
      map[id] = role;
    }
    return map;
  }

  function issueGroups(data) {
    const issues = Array.isArray(data?.github?.issues) ? data.github.issues : [];
    const groups = {
      blocked: [],
      doing: [],
      todo: [],
      done: [],
      others: [],
    };
    for (const issue of issues) {
      const s = issueStatus(issue);
      if (s.includes("blocked")) groups.blocked.push(issue);
      else if (s.includes("doing")) groups.doing.push(issue);
      else if (s.includes("todo") || s.includes("open")) groups.todo.push(issue);
      else if (s.includes("done") || s.includes("closed")) groups.done.push(issue);
      else groups.others.push(issue);
    }
    return groups;
  }

  function createDashboardApp(options) {
    const mountId = options?.mountId || "#app";
    const initialView = options?.view || "overview";

    if (!window.Vue) {
      throw new Error("Vue 3 is required for dashboard rendering");
    }

    const { createApp, reactive, computed, onMounted, onUnmounted, toRefs, watch } = window.Vue;

    createApp({
      setup() {
        const state = reactive({
          view: initialView,
          data: null,
          loading: true,
          error: "",
          refreshSec: 15,
          remainSec: 15,
          fetchedAt: "",
          pollTimer: null,
          tickTimer: null,
        });

        const views = computed(() => buildViews(state.data));
        const runtimeHealth = computed(() => runtimeHealthOf(state.data || {}));
        const roleMap = computed(() => buildRoleMap(state.data));
        const currentRole = computed(() => roleMap.value[state.view] || null);
        const groupedIssues = computed(() => issueGroups(state.data || {}));
        const activityRows = computed(() => {
          const rows = Array.isArray(state.data?.activityFeed) ? state.data.activityFeed.slice(0, 16) : [];
          return rows;
        });

        const roleIssues = computed(() => {
          if (!currentRole.value) return [];
          const issues = Array.isArray(state.data?.github?.issues) ? state.data.github.issues : [];
          return issues.filter((x) => ownerMatchesRole(x, currentRole.value.id));
        });

        const roleCron = computed(() => {
          if (!currentRole.value) return [];
          const rows = Array.isArray(state.data?.cronJobs) ? state.data.cronJobs : [];
          return rows.filter((x) => normalizeRoleId(x?.agentId) === normalizeRoleId(currentRole.value.id));
        });

        const topStats = computed(() => {
          const ov = state.data?.overview || {};
          const company = state.data?.company?.stats || {};
          return [
            { k: "启用任务", v: Number(ov.enabledJobs || 0) },
            { k: "异常任务", v: Number(ov.errorJobs || 0) },
            { k: "活跃角色", v: Number(company.activeAgents || 0) },
            { k: "平均进度", v: `${Number(company.avgProgress || 0)}%` },
          ];
        });

        const tocTargets = computed(() => {
          if (state.view === "overview") {
            return [
              { id: "sec-runtime", label: "运行健康" },
              { id: "sec-roles", label: "角色总览" },
              { id: "sec-issues", label: "Issue 状态" },
              { id: "sec-feed", label: "活动流" },
            ];
          }
          return [
            { id: "sec-role-status", label: "角色状态" },
            { id: "sec-role-issues", label: "关联 Issue" },
            { id: "sec-role-cron", label: "调度状态" },
            { id: "sec-role-feed", label: "活动流" },
          ];
        });

        async function fetchData() {
          state.loading = true;
          state.error = "";
          try {
            const resp = await fetch(`./dashboard-data.json?t=${Date.now()}`);
            if (!resp.ok) {
              throw new Error(`读取 dashboard-data.json 失败: ${resp.status}`);
            }
            state.data = await resp.json();
            state.fetchedAt = new Date().toLocaleTimeString();
          } catch (err) {
            state.error = err instanceof Error ? err.message : String(err);
          } finally {
            state.loading = false;
          }
        }

        async function refreshNow() {
          state.remainSec = state.refreshSec;
          await fetchData();
        }

        function jumpView(id) {
          const hit = views.value.find((v) => v.id === id);
          if (!hit) return;
          window.location.href = hit.href;
        }

        function jumpTarget(id) {
          const el = document.getElementById(String(id || ""));
          if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        }

        function renderStaticDom() {
          const renderViews = window.renderViewButtons;
          const renderTargets = window.renderTargetButtons;
          if (typeof renderViews === "function") {
            renderViews(document.getElementById("viewNav"), views.value, state.view, jumpView);
          }
          if (typeof renderTargets === "function") {
            renderTargets(document.getElementById("tocNav"), tocTargets.value, jumpTarget);
          }
        }

        watch(views, () => {
          renderStaticDom();
        });

        watch(tocTargets, () => {
          renderStaticDom();
        });

        onMounted(async () => {
          await fetchData();
          renderStaticDom();
          state.tickTimer = setInterval(() => {
            state.remainSec = state.remainSec > 0 ? state.remainSec - 1 : state.refreshSec;
          }, 1000);
          state.pollTimer = setInterval(() => {
            refreshNow().catch(() => {});
          }, state.refreshSec * 1000);
        });

        onUnmounted(() => {
          if (state.tickTimer) clearInterval(state.tickTimer);
          if (state.pollTimer) clearInterval(state.pollTimer);
        });

        function formatOwners(issue) {
          const owners = Array.isArray(issue?.owners) ? issue.owners : [];
          return owners.map((x) => roleLabel(normalizeRoleId(x))).join(" / ") || "未分配";
        }

        return {
          ...toRefs(state),
          views,
          runtimeHealth,
          currentRole,
          groupedIssues,
          activityRows,
          roleIssues,
          roleCron,
          topStats,
          tocTargets,
          roleLabel,
          statusBadgeClass,
          formatOwners,
          parseTimeToMs,
          refreshNow,
          jumpView,
        };
      },
      template: `
        <div class="shell">
          <section class="hero">
            <article class="hero-card">
              <span class="kicker">OpenClaw RD Cockpit</span>
              <h1>{{ view === 'overview' ? '驾驶舱总览' : roleLabel(view) + ' 视角' }}</h1>
              <p class="sub">多页面角色视图：每个角色独立页面，统一实时数据层。</p>
              <div class="hero-actions">
                <button class="btn brand" @click="refreshNow">立即刷新</button>
                <a class="btn outline" href="/setup" target="_self">配置中心</a>
              </div>
            </article>
            <article class="hero-card">
              <ul class="hero-meta">
                <li><span>仓库</span><b>{{ data?.project?.repoSlug || '-' }}</b></li>
                <li><span>分支</span><b>{{ data?.project?.branch || '-' }}</b></li>
                <li><span>数据生成</span><b>{{ data?.generatedAt || '-' }}</b></li>
                <li><span>上次刷新</span><b>{{ fetchedAt || '-' }}</b></li>
                <li><span>下次刷新</span><b>{{ remainSec }}s</b></li>
              </ul>
            </article>
          </section>

          <section class="layout">
            <aside class="panel aside">
              <h2>视角导航</h2>
              <div id="viewNav" class="nav-grid"></div>
              <h2 style="margin-top: 14px;">页面目录</h2>
              <div id="tocNav" class="nav-grid"></div>
            </aside>

            <div class="content">
              <article class="panel" v-if="error">
                <h3>加载失败</h3>
                <div class="empty">{{ error }}</div>
              </article>

              <template v-if="!error && view === 'overview'">
                <article class="panel">
                  <h3>核心指标</h3>
                  <div class="grid">
                    <div class="stat" v-for="s in topStats" :key="s.k">
                      <div class="k">{{ s.k }}</div>
                      <div class="v">{{ s.v }}</div>
                    </div>
                  </div>
                </article>

                <article id="sec-runtime" class="panel">
                  <h3>运行健康 · 失败分类</h3>
                  <div class="badge" :class="statusBadgeClass(runtimeHealth.level)">{{ runtimeHealth.summary }}</div>
                  <ul class="list" style="margin-top: 10px;" v-if="(runtimeHealth.failures || []).length">
                    <li v-for="f in runtimeHealth.failures" :key="f.category + f.summary">
                      <div class="top">
                        <b>{{ f.category || 'unknown' }}</b>
                        <span class="badge" :class="statusBadgeClass(f.level || runtimeHealth.level)">{{ f.level || runtimeHealth.level }}</span>
                      </div>
                      <div class="muted">{{ f.summary }}</div>
                      <div class="muted" v-if="f.action">建议：{{ f.action }}</div>
                    </li>
                  </ul>
                  <div class="empty" v-else>当前未检测到失败分类。</div>
                </article>

                <article id="sec-roles" class="panel">
                  <h3>角色执行状态</h3>
                  <div class="role-grid">
                    <div class="role-card" v-for="v in views.filter(x => x.id !== 'overview')" :key="v.id">
                      <h4>{{ v.label }}</h4>
                      <div class="muted" v-if="data && data.agentPanel">
                        {{ (data.agentPanel.find(p => p.id === v.id) || {}).progress?.summary || '暂无进度摘要' }}
                      </div>
                      <div style="margin-top: 8px;">
                        <a class="link" :href="v.href">进入{{ v.label }}页面</a>
                      </div>
                    </div>
                  </div>
                </article>

                <article id="sec-issues" class="panel">
                  <h3>Issue 状态看板</h3>
                  <div class="split">
                    <div>
                      <h4>Blocked</h4>
                      <ul class="list" v-if="groupedIssues.blocked.length">
                        <li v-for="i in groupedIssues.blocked" :key="i.number">
                          <div class="top"><b>#{{ i.number }} {{ i.title }}</b></div>
                          <div class="muted">{{ formatOwners(i) }} · {{ i.status }}</div>
                          <a class="link" :href="i.url" target="_blank" rel="noreferrer">查看 Issue</a>
                        </li>
                      </ul>
                      <div class="empty" v-else>暂无 blocked 事项。</div>
                    </div>
                    <div>
                      <h4>Doing / Todo</h4>
                      <ul class="list" v-if="groupedIssues.doing.length || groupedIssues.todo.length">
                        <li v-for="i in [...groupedIssues.doing, ...groupedIssues.todo].slice(0, 10)" :key="i.number">
                          <div class="top"><b>#{{ i.number }} {{ i.title }}</b></div>
                          <div class="muted">{{ formatOwners(i) }} · {{ i.status }}</div>
                          <a class="link" :href="i.url" target="_blank" rel="noreferrer">查看 Issue</a>
                        </li>
                      </ul>
                      <div class="empty" v-else>暂无 doing/todo 事项。</div>
                    </div>
                  </div>
                </article>

                <article id="sec-feed" class="panel">
                  <h3>活动流</h3>
                  <ul class="list" v-if="activityRows.length">
                    <li v-for="row in activityRows" :key="(row.time || '') + (row.title || '')">
                      <div class="top"><b>{{ row.title || '-' }}</b><span class="muted">{{ row.time || '-' }}</span></div>
                      <div class="muted">{{ row.detail || '-' }}</div>
                    </li>
                  </ul>
                  <div class="empty" v-else>暂无活动数据。</div>
                </article>
              </template>

              <template v-if="!error && view !== 'overview'">
                <article id="sec-role-status" class="panel" v-if="currentRole">
                  <h3>{{ roleLabel(view) }} · 角色状态</h3>
                  <div class="grid">
                    <div class="stat">
                      <div class="k">进度</div>
                      <div class="v">{{ currentRole.progress?.percent || 0 }}%</div>
                    </div>
                    <div class="stat">
                      <div class="k">状态</div>
                      <div class="v" style="font-size:16px;">{{ currentRole.progress?.status || '-' }}</div>
                    </div>
                    <div class="stat">
                      <div class="k">健康</div>
                      <div class="v" style="font-size:16px;">{{ currentRole.health || '-' }}</div>
                    </div>
                    <div class="stat">
                      <div class="k">最近活跃</div>
                      <div class="v" style="font-size:16px;">{{ currentRole.lastActive || '-' }}</div>
                    </div>
                  </div>
                  <p class="muted" style="margin-top: 10px;">{{ currentRole.progress?.summary || '暂无进度摘要' }}</p>
                </article>
                <article class="panel" v-else>
                  <h3>角色数据缺失</h3>
                  <div class="empty">当前数据源中未找到 {{ roleLabel(view) }} 的 agentPanel 数据。</div>
                </article>

                <article id="sec-role-issues" class="panel">
                  <h3>关联 Issue</h3>
                  <ul class="list" v-if="roleIssues.length">
                    <li v-for="i in roleIssues" :key="i.number">
                      <div class="top">
                        <b>#{{ i.number }} {{ i.title }}</b>
                        <span class="badge" :class="statusBadgeClass(i.status)">{{ i.status || i.state || '-' }}</span>
                      </div>
                      <div class="muted">优先级：{{ i.priority || '-' }} · 更新于：{{ i.updatedAt || '-' }}</div>
                      <a class="link" :href="i.url" target="_blank" rel="noreferrer">查看 Issue</a>
                    </li>
                  </ul>
                  <div class="empty" v-else>该角色暂无关联 Issue。</div>
                </article>

                <article id="sec-role-cron" class="panel">
                  <h3>调度状态</h3>
                  <ul class="list" v-if="roleCron.length">
                    <li v-for="c in roleCron" :key="c.name + c.schedule">
                      <div class="top"><b>{{ c.name }}</b><span class="badge" :class="statusBadgeClass(c.lastRunStatus)">{{ c.lastRunStatus || '-' }}</span></div>
                      <div class="muted">{{ c.schedule || '-' }} · {{ c.lastDeliveryStatus || '-' }}</div>
                    </li>
                  </ul>
                  <div class="empty" v-else>该角色暂无 cron 数据。</div>
                </article>

                <article id="sec-role-feed" class="panel">
                  <h3>相关活动</h3>
                  <ul class="list" v-if="activityRows.length">
                    <li v-for="row in activityRows.slice(0, 10)" :key="(row.time || '') + (row.title || '')">
                      <div class="top"><b>{{ row.title || '-' }}</b><span class="muted">{{ row.time || '-' }}</span></div>
                      <div class="muted">{{ row.detail || '-' }}</div>
                    </li>
                  </ul>
                  <div class="empty" v-else>暂无活动流。</div>
                </article>
              </template>
            </div>
          </section>
        </div>
      `,
    }).mount(mountId);
  }

  window.createDashboardApp = createDashboardApp;
})();
