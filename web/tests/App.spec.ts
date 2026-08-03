import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
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
});
