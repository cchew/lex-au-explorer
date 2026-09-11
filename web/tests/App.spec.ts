import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import { readFileSync } from "node:fs";
import App from "../src/App.vue";
import HomeView from "../src/views/HomeView.vue";

describe("App", () => {
  it("renders the top nav with Home and Legislation Reader links", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/", component: HomeView }],
    });
    router.push("/");
    await router.isReady();
    const wrapper = mount(App, { global: { plugins: [router] } });
    expect(wrapper.text()).toContain("Home");
    expect(wrapper.text()).toContain("Legislation Reader");
  });

  it("shows the footer version matching package.json, not a stale hardcoded value", async () => {
    const base = import.meta.url;
    const pkg = JSON.parse(readFileSync(new URL("../package.json", base), "utf8"));
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/", component: HomeView }],
    });
    router.push("/");
    await router.isReady();
    const wrapper = mount(App, { global: { plugins: [router] } });
    expect(wrapper.get(".version").text()).toBe(`v${pkg.version}`);
  });
});
