import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import ActSearch from "../src/components/ActSearch.vue";
import type { IndexEntry } from "../src/types";

const MOCK_INDEX: IndexEntry[] = [
  { title: "Privacy Act 1988", slug: "privacy-act-1988", frbr_uri: "/akn/au/act/1988/119", split_by_part: false },
  { title: "Fair Work Act 2009", slug: "fair-work-act-2009", frbr_uri: "/akn/au/act/2009/28", split_by_part: false },
];

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => MOCK_INDEX })));
});

describe("ActSearch", () => {
  it("filters by any part of the Act title, case-insensitively", async () => {
    const wrapper = mount(ActSearch);
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick(); // let the fetch resolve
    const input = wrapper.find("input");
    await input.setValue("work act");
    const options = wrapper.findAll("[data-testid='search-option']");
    expect(options).toHaveLength(1);
    expect(options[0]!.text()).toContain("Fair Work Act 2009");
  });

  it("emits select with the slug when an option is clicked", async () => {
    const wrapper = mount(ActSearch);
    await wrapper.vm.$nextTick();
    await wrapper.vm.$nextTick();
    await wrapper.find("input").setValue("privacy");
    await wrapper.find("[data-testid='search-option']").trigger("click");
    expect(wrapper.emitted("select")).toEqual([["privacy-act-1988"]]);
  });
});
