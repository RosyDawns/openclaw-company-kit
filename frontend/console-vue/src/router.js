import { createRouter, createWebHistory } from "vue-router";
import SetupView from "./views/SetupView.vue";
import DashboardOverviewView from "./views/DashboardOverviewView.vue";
import DashboardRuntimeView from "./views/DashboardRuntimeView.vue";
import DashboardRoleView from "./views/DashboardRoleView.vue";
import MonitorView from "./views/MonitorView.vue";
import KanbanView from "./views/KanbanView.vue";
import OfficialsView from "./views/OfficialsView.vue";
import TemplatesView from "./views/TemplatesView.vue";
import SessionsView from "./views/SessionsView.vue";
import SkillsView from "./views/SkillsView.vue";

const routes = [
  { path: "/", redirect: "/setup" },
  { path: "/setup", component: SetupView },
  { path: "/overview", component: DashboardOverviewView },
  { path: "/monitor", component: MonitorView },
  { path: "/kanban", component: KanbanView },
  { path: "/officials", component: OfficialsView },
  { path: "/templates", component: TemplatesView },
  { path: "/skills", component: SkillsView },
  { path: "/sessions", component: SessionsView },
  // Legacy routes for backward compatibility
  { path: "/dashboard", component: DashboardOverviewView },
  { path: "/dashboard/runtime", component: DashboardRuntimeView },
  { path: "/dashboard/:roleId", component: DashboardRoleView, props: true },
  { path: "/:pathMatch(.*)*", redirect: "/setup" },
];

const router = createRouter({
  history: createWebHistory("/ui/"),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

export default router;
