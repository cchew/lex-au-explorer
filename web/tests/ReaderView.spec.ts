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

// Real fetch Responses expose Content-Type via `.headers.get(...)` and a
// `.text()` method; ReaderView's fetchJson() checks both (see Task 13 Fix
// Round 1 — content-type gates 404-vs-malformed-JSON classification), so
// mocks must mirror that shape rather than just `{ ok, json }`.
function jsonResponse(body: unknown) {
  return {
    ok: true,
    headers: { get: (name: string) => (name.toLowerCase() === "content-type" ? "application/json" : null) },
    text: async () => JSON.stringify(body),
    json: async () => body,
  };
}

// Simulates Vite's dev-server / Netlify's SPA-fallback response for a
// missing /data/*.json path: 200 OK, but Content-Type: text/html.
function htmlResponse() {
  return {
    ok: true,
    headers: { get: (name: string) => (name.toLowerCase() === "content-type" ? "text/html" : null) },
    text: async () => "<!DOCTYPE html><html></html>",
    json: async () => {
      throw new Error("Unexpected token '<'");
    },
  };
}

// Simulates a build-pipeline bug: the file genuinely has Content-Type:
// application/json but the body is truncated/corrupted, so JSON.parse throws.
// This must NOT be mislabeled "HTTP 404" — see Task 13 Fix Round 1.
function malformedJsonResponse() {
  return {
    ok: true,
    headers: { get: (name: string) => (name.toLowerCase() === "content-type" ? "application/json" : null) },
    text: async () => '{"truncated": tr',
    json: async () => {
      throw new Error("Unexpected end of JSON input");
    },
  };
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.includes("index.json")) {
      return jsonResponse(MOCK_INDEX);
    }
    return jsonResponse(MOCK_BUNDLE);
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
        return jsonResponse(MOCK_SPLIT_INDEX);
      }
      if (url.includes("/fair-work-act-2009/part-I.json")) {
        return jsonResponse(MOCK_SPLIT_PART_BUNDLE);
      }
      // Initial bundle fetch: /data/fair-work-act-2009.json (index bundle, empty sections)
      return jsonResponse(MOCK_SPLIT_INDEX_BUNDLE);
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
        return jsonResponse(MOCK_SPLIT_INDEX);
      }
      if (url.includes("/fair-work-act-2009/part-I.json")) {
        return { ok: false, status: 404, headers: { get: () => null }, text: async () => "", json: async () => ({}) };
      }
      return jsonResponse(MOCK_SPLIT_INDEX_BUNDLE);
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

  it("shows HTTP 404 when the response is an SPA-fallback HTML shell, not a real 404 status", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("index.json")) return jsonResponse(MOCK_INDEX);
      return htmlResponse();
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

    expect(wrapper.find(".load-error").exists()).toBe(true);
    expect(wrapper.text()).toContain("HTTP 404");
  });

  it("shows a distinct error (not HTTP 404) when a JSON-typed response fails to parse", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("index.json")) return jsonResponse(MOCK_INDEX);
      return malformedJsonResponse();
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

    expect(wrapper.find(".load-error").exists()).toBe(true);
    expect(wrapper.text()).not.toContain("HTTP 404");
    expect(wrapper.text()).toContain("Invalid response");
  });
});
