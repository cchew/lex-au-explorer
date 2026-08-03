import { createRouter, createWebHistory } from "vue-router";
import HomeView from "./views/HomeView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: HomeView },
    {
      path: "/reader",
      name: "reader-index",
      component: () => import("./views/ReaderView.vue"),
    },
    {
      path: "/reader/:slug",
      name: "reader",
      component: () => import("./views/ReaderView.vue"),
    },
  ],
});

export default router;
