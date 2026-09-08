import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import ReaderView from "../src/views/ReaderView.vue";
import type { ActBundle } from "../src/types";
import { track } from "../src/lib/analytics";

// ReaderView is a <script setup> component; VTU exposes its setup bindings on
// wrapper.vm in the (dev-mode) test runtime. Narrow to what the assertions read.
type ReaderVm = { bundle: ActBundle | null };

vi.mock("../src/lib/analytics", () => ({ track: vi.fn() }));

const MOCK_BUNDLE = {
  frbr_uri: "/akn/au/act/1988/119", title: "Privacy Act 1988", title_id: "C1",
  legislation_url: "https://www.legislation.gov.au/C1/latest/text",
  comp_id: "C2", effective_date: "2026-06-04",
  toc: [{ eid: "part-I", heading: "Part 1", children: [{ eid: "part-I__sec-6", heading: "Definitions", children: [] }] }],
  sections: { "part-I__sec-6": { heading: "Definitions", html: "<p>Test</p>" } },
  terms: [],
  raw_xml_url: "https://huggingface.co/datasets/cchew/lex-au/resolve/main/xml/privacy-act-1988.xml",
  split_by_part: false,
};

const MOCK_INDEX = [
  { title: "Privacy Act 1988", slug: "privacy-act-1988", frbr_uri: "/akn/au/act/1988/119", split_by_part: false }
];

// Split-by-Part index bundle: toc + Part structure present, but sections/terms
// are empty per Task 7's _write_split_bundle (they live in the per-Part files instead).
const MOCK_SPLIT_INDEX_BUNDLE = {
  frbr_uri: "/akn/au/act/2009/28", title: "Fair Work Act 2009", title_id: "C1",
  legislation_url: "https://www.legislation.gov.au/C1/latest/text",
  comp_id: "C2", effective_date: "2026-06-04",
  toc: [{ eid: "part-I", heading: "Part 1", children: [{ eid: "part-I__sec-6", heading: "Definitions", children: [] }] }],
  sections: {},
  terms: [],
  raw_xml_url: "https://huggingface.co/datasets/cchew/lex-au/resolve/main/xml/fair-work-act-2009.xml",
  split_by_part: true,
};

const MOCK_SPLIT_PART_BUNDLE = {
  ...MOCK_SPLIT_INDEX_BUNDLE,
  sections: { "part-I__sec-6": { heading: "Definitions", html: "<p>Part content</p>" } },
  terms: [],
};

// Index bundle with two top-level Parts in its TOC, so a click on a Part II
// leaf can be exercised. Sections stay empty (per Task 7's index-only bundle).
const MOCK_SPLIT_INDEX_BUNDLE_TWO_PARTS = {
  ...MOCK_SPLIT_INDEX_BUNDLE,
  toc: [
    { eid: "part-I", heading: "Part 1", children: [{ eid: "part-I__sec-6", heading: "Definitions", children: [] }] },
    { eid: "part-II", heading: "Part 2", children: [{ eid: "part-II__sec-10", heading: "Enforcement", children: [] }] },
  ],
};

const MOCK_SPLIT_PART_II_BUNDLE = {
  ...MOCK_SPLIT_INDEX_BUNDLE_TWO_PARTS,
  sections: { "part-II__sec-10": { heading: "Enforcement", html: "<p>Part II content</p>" } },
  terms: [],
};

const MOCK_SPLIT_INDEX = [
  { title: "Fair Work Act 2009", slug: "fair-work-act-2009", frbr_uri: "/akn/au/act/2009/28", split_by_part: true }
];

// A large single-file Act whose Schedules were promoted to separate files
// (Task 9's split_schedules). split_by_part is false: the Act body is inline,
// only Schedule unit eids are missing from `sections` until fetched.
// slug must be one of ActSearch's SHORTCUTS so the test can open it via a
// shortcut button, like the other ReaderView tests.
const MOCK_SPLIT_SCHEDULES_BUNDLE = {
  frbr_uri: "/akn/au/act/2001/50", title: "Corporations Act 2001", title_id: "C1",
  legislation_url: "https://www.legislation.gov.au/C1/latest/text",
  comp_id: "C2", effective_date: "2026-06-04",
  toc: [
    { eid: "part-1", heading: "Part 1", children: [{ eid: "part-1__sec-1", heading: "Short title", children: [] }] },
    { eid: "schedule-1", heading: "Schedule 1", children: [{ eid: "schedule-1__clause-1", heading: "Amendments", children: [] }] },
  ],
  sections: { "part-1__sec-1": { heading: "Short title", html: "<p>Body provision</p>" } },
  terms: [],
  raw_xml_url: "https://huggingface.co/datasets/cchew/lex-au/resolve/main/xml/corporations-act-2001.xml",
  split_by_part: false,
  split_schedules: true,
};

// Schedule part file shape: `sections` only, no other bundle keys (matches
// Task 9's _write_schedule_file).
const MOCK_SCHEDULE_PART_FILE = {
  sections: { "schedule-1__clause-1": { heading: "Amendments", html: "<p>Schedule clause body</p>" } },
};

const MOCK_SPLIT_SCHEDULES_INDEX = [
  { title: "Corporations Act 2001", slug: "corporations-act-2001", frbr_uri: "/akn/au/act/2001/50", split_by_part: false }
];

// Real fetch Responses expose Content-Type via `.headers.get(...)` and a
// `.text()` method; ReaderView's fetchJson() checks both (see Task 13 Fix
// Round 1 — content-type gates 404-vs-malformed-JSON classification), so
// mocks must mirror that shape rather than just `{ ok, json }`.
interface MockResponse {
  ok: boolean;
  status?: number;
  headers: { get: (name: string) => string | null };
  text: () => Promise<string>;
  json: () => Promise<unknown>;
}

function jsonResponse(body: unknown): MockResponse {
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
  vi.mocked(track).mockClear();
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

  it("loads and renders Part II content when a TOC entry from a later Part is clicked", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("index.json")) {
        return jsonResponse(MOCK_SPLIT_INDEX);
      }
      if (url.includes("/fair-work-act-2009/part-I.json")) {
        return jsonResponse(MOCK_SPLIT_PART_BUNDLE);
      }
      if (url.includes("/fair-work-act-2009/part-II.json")) {
        return jsonResponse(MOCK_SPLIT_PART_II_BUNDLE);
      }
      // Initial bundle fetch: /data/fair-work-act-2009.json (index bundle, empty sections)
      return jsonResponse(MOCK_SPLIT_INDEX_BUNDLE_TWO_PARTS);
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

    // Wait for the index-bundle fetch and the initial Part I fetch to resolve
    await new Promise(resolve => setTimeout(resolve, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await new Promise(resolve => setTimeout(resolve, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    // Part I's section shows first
    expect(wrapper.text()).toContain("Part content");

    // Click the Part II TOC entry
    const partIILeaf = wrapper.findAll(".toc-leaf").find(btn => btn.text() === "Enforcement");
    expect(partIILeaf).toBeTruthy();
    await partIILeaf!.trigger("click");

    // Wait for the follow-up Part II fetch to resolve
    await new Promise(resolve => setTimeout(resolve, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await new Promise(resolve => setTimeout(resolve, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    // Part II's actual content renders, not an empty pane
    expect(wrapper.text()).toContain("Part II content");
    expect(wrapper.find(".load-error").exists()).toBe(false);
  });

  it("keeps the reader mounted (does not eject to search) when the initial Part fetch fails", async () => {
    // F3: lazy Part fetch is on the primary nav path now. A failed fetch must
    // surface an error line but leave `bundle` mounted -- not null it and dump
    // the user back to ActSearch. This test used to assert the opposite
    // (fall-back-to-search) behaviour.
    vi.stubGlobal("fetch", vi.fn(async (url: string): Promise<MockResponse> => {
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

    const vm = wrapper.vm as unknown as ReaderVm;
    expect(wrapper.find(".load-error").exists()).toBe(true);
    expect(wrapper.text()).toContain("Couldn't load that section");
    expect(wrapper.text()).not.toContain("HTTP 404");
    // Reader shell stays up (TOC + content pane); bundle is not nulled.
    expect(wrapper.find(".reader-layout").exists()).toBe(true);
    expect(vm.bundle).not.toBeNull();
    expect(wrapper.find(".shortcut-btn").exists()).toBe(false);
  });

  it("preserves already-merged Part sections when a later Part fetch fails", async () => {
    // F3: navigate into Part I (succeeds), then into Part II (fetch fails).
    // The error shows, but Part I's merged sections and the reader survive.
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("index.json")) return jsonResponse(MOCK_SPLIT_INDEX);
      if (url.includes("/fair-work-act-2009/part-I.json")) return jsonResponse(MOCK_SPLIT_PART_BUNDLE);
      if (url.includes("/fair-work-act-2009/part-II.json")) return htmlResponse(); // SPA shell -> HTTP 404
      return jsonResponse(MOCK_SPLIT_INDEX_BUNDLE_TWO_PARTS);
    }));

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/reader", component: ReaderView }],
    });
    router.push("/reader");
    await router.isReady();

    const wrapper = mount(ReaderView, { global: { plugins: [router] } });
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    await wrapper.find(".shortcut-btn").trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    const vm = wrapper.vm as unknown as ReaderVm;
    expect(vm.bundle?.sections["part-I__sec-6"]).toBeDefined();

    const partIILeaf = wrapper.findAll(".toc-leaf").find((b) => b.text() === "Enforcement");
    expect(partIILeaf).toBeTruthy();
    await partIILeaf!.trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    expect(wrapper.find(".load-error").exists()).toBe(true);
    expect(wrapper.text()).toContain("Couldn't load that section");
    expect(vm.bundle).not.toBeNull();
    expect(vm.bundle?.sections["part-I__sec-6"]).toBeDefined();
    expect(wrapper.find(".reader-layout").exists()).toBe(true);
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

  it("records act_opened with the entry method when opened from a shortcut", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/reader", component: ReaderView }],
    });
    router.push("/reader");
    await router.isReady();

    const wrapper = mount(ReaderView, { global: { plugins: [router] } });
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await wrapper.find(".shortcut-btn").trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();

    expect(track).toHaveBeenCalledWith("act_opened", {
      slug: "privacy-act-1988",
      source: "shortcut",
    });
  });

  it("records act_opened with source 'direct' for a deep link", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/reader", component: ReaderView },
        { path: "/reader/:slug", component: ReaderView },
      ],
    });
    router.push("/reader/privacy-act-1988");
    await router.isReady();

    mount(ReaderView, { global: { plugins: [router] } });
    await new Promise((r) => setTimeout(r, 10));

    expect(track).toHaveBeenCalledWith("act_opened", {
      slug: "privacy-act-1988",
      source: "direct",
    });
  });

  it("records toc_navigate with a coarse position, not a raw eid", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/reader", component: ReaderView }],
    });
    router.push("/reader");
    await router.isReady();

    const wrapper = mount(ReaderView, { global: { plugins: [router] } });
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await wrapper.find(".shortcut-btn").trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    vi.mocked(track).mockClear();

    await wrapper.find(".toc-leaf").trigger("click");

    const call = vi.mocked(track).mock.calls.find((c) => c[0] === "toc_navigate");
    expect(call).toBeDefined();
    expect(call![1]).toEqual({ slug: "privacy-act-1988", position: expect.any(String) });
    expect(call![1]).not.toHaveProperty("eid");
  });

  it("merges part sections instead of replacing when navigating between Parts", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("index.json")) return jsonResponse(MOCK_SPLIT_INDEX);
      if (url.includes("/fair-work-act-2009/part-I.json")) return jsonResponse(MOCK_SPLIT_PART_BUNDLE);
      if (url.includes("/fair-work-act-2009/part-II.json")) return jsonResponse(MOCK_SPLIT_PART_II_BUNDLE);
      return jsonResponse(MOCK_SPLIT_INDEX_BUNDLE_TWO_PARTS);
    }));

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/reader", component: ReaderView }],
    });
    router.push("/reader");
    await router.isReady();

    const wrapper = mount(ReaderView, { global: { plugins: [router] } });
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    await wrapper.find(".shortcut-btn").trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();

    // Part I is loaded on open.
    const vm = wrapper.vm as unknown as ReaderVm;
    expect(vm.bundle?.sections["part-I__sec-6"]).toBeDefined();

    // Navigate to a Part II leaf.
    const partIILeaf = wrapper.findAll(".toc-leaf").find((b) => b.text() === "Enforcement");
    expect(partIILeaf).toBeTruthy();
    await partIILeaf!.trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    // Both Parts' sections are present -- the old replace behaviour dropped Part I.
    expect(vm.bundle?.sections["part-I__sec-6"]).toBeDefined();
    expect(vm.bundle?.sections["part-II__sec-10"]).toBeDefined();
    expect(wrapper.text()).toContain("Part II content");
    expect(wrapper.find(".load-error").exists()).toBe(false);
  });

  it("fetches a schedule file for a split_schedules Act, merges, and doesn't re-fetch", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("index.json")) return jsonResponse(MOCK_SPLIT_SCHEDULES_INDEX);
      if (url.endsWith("/corporations-act-2001.json")) return jsonResponse(MOCK_SPLIT_SCHEDULES_BUNDLE);
      if (url.includes("/corporations-act-2001/schedule-1.json")) return jsonResponse(MOCK_SCHEDULE_PART_FILE);
      // Any other /data/<slug>/*.json path does not exist: production serves the
      // SPA HTML shell, which fetchJson classifies as HTTP 404. An over-eager
      // loadPart (e.g. loadPart("part-1")) must fail loudly, not silently merge.
      return htmlResponse();
    });
    vi.stubGlobal("fetch", fetchMock);

    const scheduleFetches = () =>
      fetchMock.mock.calls.filter((c) => String(c[0]).includes("/corporations-act-2001/schedule-1.json")).length;

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/reader", component: ReaderView }],
    });
    router.push("/reader");
    await router.isReady();

    const wrapper = mount(ReaderView, { global: { plugins: [router] } });
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    await wrapper.find(".shortcut-btn").trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    // Body provision renders; the schedule file has not been touched.
    expect(wrapper.text()).toContain("Body provision");
    expect(scheduleFetches()).toBe(0);

    const vm = wrapper.vm as unknown as ReaderVm;
    expect(vm.bundle?.sections["schedule-1__clause-1"]).toBeUndefined();

    // Click the schedule clause -> exactly one fetch of the schedule file.
    const clauseLeaf = wrapper.findAll(".toc-leaf").find((b) => b.text() === "Amendments");
    expect(clauseLeaf).toBeTruthy();
    await clauseLeaf!.trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    expect(scheduleFetches()).toBe(1);
    expect(vm.bundle?.sections["schedule-1__clause-1"]).toBeDefined();
    expect(vm.bundle?.sections["part-1__sec-1"]).toBeDefined(); // body kept
    expect(wrapper.text()).toContain("Schedule clause body");
    expect(wrapper.find(".load-error").exists()).toBe(false);

    // Click it again -> genuine no-op, no additional fetch.
    await clauseLeaf!.trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    expect(scheduleFetches()).toBe(1);
  });

  it("does not fetch (or eject) on a body container click for a split_schedules Act", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("index.json")) return jsonResponse(MOCK_SPLIT_SCHEDULES_INDEX);
      if (url.endsWith("/corporations-act-2001.json")) return jsonResponse(MOCK_SPLIT_SCHEDULES_BUNDLE);
      if (url.includes("/corporations-act-2001/schedule-1.json")) return jsonResponse(MOCK_SCHEDULE_PART_FILE);
      // No per-Part file exists for a split_schedules Act (body is inline);
      // production serves the SPA shell -> fetchJson throws HTTP 404.
      return htmlResponse();
    });
    vi.stubGlobal("fetch", fetchMock);

    const partFetches = () =>
      fetchMock.mock.calls.filter((c) => String(c[0]).includes("/corporations-act-2001/part-1.json")).length;
    const scheduleFetches = () =>
      fetchMock.mock.calls.filter((c) => String(c[0]).includes("/corporations-act-2001/schedule-1.json")).length;

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/reader", component: ReaderView }],
    });
    router.push("/reader");
    await router.isReady();

    const wrapper = mount(ReaderView, { global: { plugins: [router] } });
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    await wrapper.find(".shortcut-btn").trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    const vm = wrapper.vm as unknown as ReaderVm & { activeTopLevelEid: string | null };

    // Click the bare body container eid (a Part heading / resolved whole-Part
    // xref). "part-1" is a TOC branch node, so ActToc emits select("part-1").
    const partBranch = wrapper.findAll(".toc-branch").find((b) => b.text() === "Part 1");
    expect(partBranch).toBeTruthy();
    await partBranch!.trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    // No spurious per-Part fetch, reader still mounted, group activated.
    expect(partFetches()).toBe(0);
    expect(vm.bundle).not.toBeNull();
    expect(vm.activeTopLevelEid).toBe("part-1");
    expect(wrapper.find(".load-error").exists()).toBe(false);
    expect(wrapper.text()).toContain("Body provision");

    // The real schedule path still works from the same bundle.
    const clauseLeaf = wrapper.findAll(".toc-leaf").find((b) => b.text() === "Amendments");
    expect(clauseLeaf).toBeTruthy();
    await clauseLeaf!.trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    expect(scheduleFetches()).toBe(1);
    expect(vm.bundle?.sections["schedule-1__clause-1"]).toBeDefined();
    expect(wrapper.text()).toContain("Schedule clause body");
  });

  it("builds the matcher per Part load, not per rendered section (Spec I1)", async () => {
    // Spec I1: buildMatcher is invoked once per distinct Part load, NOT once per
    // rendered <SectionContent>. loadPart reassigns bundle.terms via
    //   bundle.value = { ...bundle.value, terms: mergeTerms(...) }
    // so `watch(() => bundle.value?.terms)` refires on every Part load and
    // buildMatcher runs once per Part (plus once for the initial index bundle).
    // Navigating part-I -> part-II -> part-I loads two distinct Parts (part-I is
    // cached on return via loadedGroups, so no re-fetch and no bundle
    // reassignment), so buildMatcher runs at most 3x total -- and strictly
    // fewer times than the number of sections rendered. The old, wrong
    // assertion (`toHaveBeenCalledTimes(1)`) contradicts this merge model.
    const IDX = {
      ...MOCK_SPLIT_INDEX_BUNDLE,
      toc: [
        { eid: "part-I", heading: "Part 1", children: [
          { eid: "part-I__sec-1", heading: "S1", children: [] },
          { eid: "part-I__sec-2", heading: "S2", children: [] },
          { eid: "part-I__sec-3", heading: "S3", children: [] },
          { eid: "part-I__sec-4", heading: "S4", children: [] },
        ] },
        { eid: "part-II", heading: "Part 2", children: [
          { eid: "part-II__sec-5", heading: "S5", children: [] },
        ] },
      ],
    };
    const PART_I = {
      ...IDX,
      sections: {
        "part-I__sec-1": { heading: "S1", html: "<p>a</p>" },
        "part-I__sec-2": { heading: "S2", html: "<p>b</p>" },
        "part-I__sec-3": { heading: "S3", html: "<p>c</p>" },
        "part-I__sec-4": { heading: "S4", html: "<p>d</p>" },
      },
      terms: [],
    };
    const PART_II = {
      ...IDX,
      sections: { "part-II__sec-5": { heading: "S5", html: "<p>e</p>" } },
      terms: [],
    };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("index.json")) return jsonResponse(MOCK_SPLIT_INDEX);
      if (url.includes("/fair-work-act-2009/part-I.json")) return jsonResponse(PART_I);
      if (url.includes("/fair-work-act-2009/part-II.json")) return jsonResponse(PART_II);
      return jsonResponse(IDX);
    }));

    const th = await import("../src/lib/termHighlight");
    const spy = vi.spyOn(th, "buildMatcher");

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/reader", component: ReaderView }],
    });
    router.push("/reader");
    await router.isReady();

    const wrapper = mount(ReaderView, { global: { plugins: [router] } });
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    await wrapper.find(".shortcut-btn").trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    // Part I active: four sections rendered.
    const sectionsOnPartI = wrapper.findAll(".section-content").length;
    expect(sectionsOnPartI).toBe(4);

    // part-I -> part-II
    const p2 = wrapper.findAll(".toc-leaf").find((b) => b.text() === "S5");
    expect(p2).toBeTruthy();
    await p2!.trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    // part-II -> part-I (cached: no re-fetch, no bundle reassignment, no rebuild)
    const p1 = wrapper.findAll(".toc-leaf").find((b) => b.text() === "S1");
    expect(p1).toBeTruthy();
    await p1!.trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    // Matcher IS built, but bounded by distinct Part loads (<= index + 2 Parts),
    // never once per section.
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(1);
    expect(spy.mock.calls.length).toBeLessThanOrEqual(3);
    expect(spy.mock.calls.length).toBeLessThan(sectionsOnPartI);
    spy.mockRestore();
  });

  it("mergeTerms unions defs and usedInBody across Part loads", async () => {
    // part-I defines 'x' (usedInBody false, def eid in part-I); part-II carries
    // 'x' again with a second def eid and usedInBody true. After navigating
    // into part-II the merged bundle.terms must hold ONE 'x' entry whose defs
    // cover both eids and whose usedInBody is true.
    const IDX = {
      ...MOCK_SPLIT_INDEX_BUNDLE_TWO_PARTS,
      terms: [],
    };
    const PART_I = {
      ...IDX,
      sections: { "part-I__sec-6": { heading: "Definitions", html: "<p>x means a thing</p>" } },
      terms: [
        { term: "x", display: "x", defs: [{ text: "a thing", eid: "part-I__sec-6" }], usedInBody: false },
      ],
    };
    const PART_II = {
      ...IDX,
      sections: { "part-II__sec-10": { heading: "Enforcement", html: "<p>the x applies here</p>" } },
      terms: [
        { term: "x", display: "x", defs: [{ text: "as applied", eid: "part-II__sec-10" }], usedInBody: true },
      ],
    };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("index.json")) return jsonResponse(MOCK_SPLIT_INDEX);
      if (url.includes("/fair-work-act-2009/part-I.json")) return jsonResponse(PART_I);
      if (url.includes("/fair-work-act-2009/part-II.json")) return jsonResponse(PART_II);
      return jsonResponse(IDX);
    }));

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/reader", component: ReaderView }],
    });
    router.push("/reader");
    await router.isReady();

    const wrapper = mount(ReaderView, { global: { plugins: [router] } });
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    await wrapper.find(".shortcut-btn").trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    // Navigate into Part II so its terms are merged.
    const partIILeaf = wrapper.findAll(".toc-leaf").find((b) => b.text() === "Enforcement");
    expect(partIILeaf).toBeTruthy();
    await partIILeaf!.trigger("click");
    await new Promise((r) => setTimeout(r, 10));
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();

    const vm = wrapper.vm as unknown as ReaderVm;
    const xs = (vm.bundle?.terms ?? []).filter((t) => t.term === "x");
    expect(xs).toHaveLength(1);
    expect(xs[0]!.usedInBody).toBe(true);
    const eids = xs[0]!.defs.map((d) => d.eid);
    expect(eids).toHaveLength(2);
    expect(new Set(eids)).toEqual(new Set(["part-I__sec-6", "part-II__sec-10"]));
  });
});
