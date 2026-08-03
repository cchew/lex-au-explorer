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

// Split-by-Part index bundle: toc + Part structure present, but sections/definitions
// are empty per Task 7's _write_split_bundle (they live in the per-Part files instead).
const MOCK_SPLIT_INDEX_BUNDLE = {
  frbr_uri: "/akn/au/act/2009/28", title: "Fair Work Act 2009", title_id: "C1",
  legislation_url: "https://www.legislation.gov.au/C1/latest/text",
  comp_id: "C2", effective_date: "2026-06-04",
  toc: [{ eid: "part-I", heading: "Part 1", children: [{ eid: "part-I__sec-6", heading: "Definitions", children: [] }] }],
  sections: {},
  definitions: {},
  raw_xml_url: "/data/fair-work-act-2009.xml",
  split_by_part: true,
};

const MOCK_SPLIT_PART_BUNDLE = {
  ...MOCK_SPLIT_INDEX_BUNDLE,
  sections: { "part-I__sec-6": { heading: "Definitions", html: "<p>Part content</p>" } },
  definitions: {},
};

const MOCK_SPLIT_INDEX = [
  { title: "Fair Work Act 2009", slug: "fair-work-act-2009", frbr_uri: "/akn/au/act/2009/28", split_by_part: true }
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

  it("fetches the first Part's sections separately for split-by-Part Acts and merges them", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("index.json")) {
        return { ok: true, json: async () => MOCK_SPLIT_INDEX };
      }
      if (url.includes("/fair-work-act-2009/part-I.json")) {
        return { ok: true, json: async () => MOCK_SPLIT_PART_BUNDLE };
      }
      // Initial bundle fetch: /data/fair-work-act-2009.json (index bundle, empty sections)
      return { ok: true, json: async () => MOCK_SPLIT_INDEX_BUNDLE };
    }));

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/reader", component: ReaderView }]
    });
    router.push("/reader");
    await router.isReady();

    const wrapper = mount(ReaderView, { global: { plugins: [router] } });
    await new Promise(resolve => setTimeout(resolve, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    const shortcutBtn = wrapper.find(".shortcut-btn");
    expect(shortcutBtn.exists()).toBe(true);
    await shortcutBtn.trigger("click");

    // Wait for both the index-bundle fetch and the follow-up Part fetch to resolve
    await new Promise(resolve => setTimeout(resolve, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await new Promise(resolve => setTimeout(resolve, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain("Definitions");
    expect(wrapper.find(".load-error").exists()).toBe(false);
  });

  it("shows an error and falls back to ActSearch when the Part fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("index.json")) {
        return { ok: true, json: async () => MOCK_SPLIT_INDEX };
      }
      if (url.includes("/fair-work-act-2009/part-I.json")) {
        return { ok: false, status: 404, json: async () => ({}) };
      }
      return { ok: true, json: async () => MOCK_SPLIT_INDEX_BUNDLE };
    }));

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/reader", component: ReaderView }]
    });
    router.push("/reader");
    await router.isReady();

    const wrapper = mount(ReaderView, { global: { plugins: [router] } });
    await new Promise(resolve => setTimeout(resolve, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    const shortcutBtn = wrapper.find(".shortcut-btn");
    expect(shortcutBtn.exists()).toBe(true);
    await shortcutBtn.trigger("click");

    await new Promise(resolve => setTimeout(resolve, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await new Promise(resolve => setTimeout(resolve, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    expect(wrapper.find(".load-error").exists()).toBe(true);
    expect(wrapper.text()).toContain("HTTP 404");
    // No half-rendered reader shell: back to ActSearch, no TOC/content pane
    expect(wrapper.find(".reader-layout").exists()).toBe(false);
    expect(wrapper.find(".shortcut-btn").exists()).toBe(true);
  });
});
