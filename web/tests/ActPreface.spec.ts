import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import ActPreface from "../src/components/ActPreface.vue";

const BUNDLE_BASE = {
  frbr_uri: "/akn/au/act/1988/119", title: "Privacy Act 1988", title_id: "C2004A03712",
  legislation_url: "https://www.legislation.gov.au/C2004A03712/latest/text",
  comp_id: "C2026C00227", effective_date: "2026-06-04", year: 1988, number: 119,
  toc: [], sections: {}, definitions: {}, raw_xml_url: "https://huggingface.co/datasets/cchew/lex-au/resolve/main/xml/privacy-act-1988.xml", split_by_part: false,
};

describe("ActPreface", () => {
  it("renders the long title when preface is present", () => {
    const bundle = {
      ...BUNDLE_BASE,
      preface: {
        long_title: "An Act to deal with consequential and transitional matters",
        enacting: "The Parliament of Australia enacts:",
      },
    };
    const wrapper = mount(ActPreface, { props: { bundle } });
    expect(wrapper.text()).toContain("An Act to deal with consequential and transitional matters");
    expect(wrapper.text()).toContain("The Parliament of Australia enacts:");
  });

  it("renders nothing when preface is absent", () => {
    const wrapper = mount(ActPreface, { props: { bundle: BUNDLE_BASE } });
    expect(wrapper.text()).toBe("");
    expect(wrapper.find(".act-preface").exists()).toBe(false);
  });
});
