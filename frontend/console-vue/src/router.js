import { createRouter, createWebHistory } from "vue-router";
import SetupView from "./views/SetupView.vue";
import DashboardOverviewView from "./views/DashboardOverviewView.vue";
import DashboardRoleView from "./views/DashboardRoleView.vue";

const routes = [
  { path: "/", redirect: "/setup" },
  { path: "/setup", component: SetupView },
  { path: "/dashboard", component: DashboardOverviewView },
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
