import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import ReaderView from "../src/views/ReaderView.vue";

const MOCK_BUNDLE = {
  frbr_uri: "/akn/au/act/1988/119", title: "Privacy Act 1988", title_id: "C1",
  legislation_url: "https://www.legislation.gov.au/C1/latest/text",
  comp_id: "C2", effective_date: "2026-06-04",
  toc: [{ eid: "part-I", heading: "Part 1", children: [{ eid: "part-I__sec-6", heading: "Definitions", children: [] }] }],
  sections: { "part-I__sec-6": { heading: "Definitions", html: "<p>Test</p>" } },
  definitions: {},
  raw_xml_url: "/data/privacy-act-1988.xml",
  split_by_part: false,
};

const MOCK_INDEX = [
  { title: "Privacy Act 1988", slug: "privacy-act-1988", frbr_uri: "/akn/au/act/1988/119", split_by_part: false }
];

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.includes("index.json")) {
      return { ok: true, json: async () => MOCK_INDEX };
    }
    return { ok: true, json: async () => MOCK_BUNDLE };
  }));
});

describe("ReaderView", () => {
  it("loads a bundle and shows its TOC after selecting an Act", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/reader", component: ReaderView }]
    });
    router.push("/reader");
    await router.isReady();

    const wrapper = mount(ReaderView, { global: { plugins: [router] } });
    // Wait for ActSearch to load index and render shortcuts
    await new Promise(resolve => setTimeout(resolve, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    // Find and click a search option (shortcut button)
    const shortcutBtn = wrapper.find(".shortcut-btn");
    expect(shortcutBtn.exists()).toBe(true);
    await shortcutBtn.trigger("click");

    // Wait for bundle to load
    await new Promise(resolve => setTimeout(resolve, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain("Definitions");
  });
});
