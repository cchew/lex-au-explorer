import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import ActSearch from "../src/components/ActSearch.vue";
import type { IndexEntry } from "../src/types";
import { track } from "../src/lib/analytics";

vi.mock("../src/lib/analytics", () => ({ track: vi.fn() }));

const MOCK_INDEX: IndexEntry[] = [
  { title: "Privacy Act 1988", slug: "privacy-act-1988", frbr_uri: "/akn/au/act/1988/119", split_by_part: false },
  { title: "Fair Work Act 2009", slug: "fair-work-act-2009", frbr_uri: "/akn/au/act/2009/28", split_by_part: false },
];

beforeEach(() => {
  vi.mocked(track).mockClear();
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => MOCK_INDEX })));
});

async function mountReady() {
  const wrapper = mount(ActSearch);
  await wrapper.vm.$nextTick();
  await wrapper.vm.$nextTick(); // let the index fetch resolve
  return wrapper;
}

describe("ActSearch", () => {
  it("filters by any part of the Act title, case-insensitively", async () => {
    const wrapper = await mountReady();
    await wrapper.find("input").setValue("work act");
    const options = wrapper.findAll("[data-testid='search-option']");
    expect(options).toHaveLength(1);
    expect(options[0]!.text()).toContain("Fair Work Act 2009");
  });

  it("emits select with the slug and source 'typed' when a result is clicked", async () => {
    const wrapper = await mountReady();
    await wrapper.find("input").setValue("privacy");
    await wrapper.find("[data-testid='search-option']").trigger("click");
    expect(wrapper.emitted("select")).toEqual([["privacy-act-1988", "typed"]]);
  });

  it("emits select with source 'shortcut' when a shortcut button is clicked", async () => {
    const wrapper = await mountReady();
    await wrapper.find(".shortcut-btn").trigger("click");
    expect(wrapper.emitted("select")).toEqual([["privacy-act-1988", "shortcut"]]);
  });

  describe("zero-result tracking", () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it("reports a settled query that returns nothing", async () => {
      const wrapper = mount(ActSearch);
      await wrapper.vm.$nextTick();
      await wrapper.vm.$nextTick();
      await wrapper.find("input").setValue("marine pollution");
      vi.advanceTimersByTime(600);
      expect(track).toHaveBeenCalledWith("search_no_results", { query: "marine pollution" });
    });

    it("does not report while a query still has matches", async () => {
      const wrapper = mount(ActSearch);
      await wrapper.vm.$nextTick();
      await wrapper.vm.$nextTick();
      await wrapper.find("input").setValue("privacy");
      vi.advanceTimersByTime(600);
      expect(track).not.toHaveBeenCalled();
    });
  });
});
