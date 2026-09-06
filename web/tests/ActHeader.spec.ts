import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import ActHeader from "../src/components/ActHeader.vue";

const BUNDLE = {
  frbr_uri: "/akn/au/act/1988/119", title: "Privacy Act 1988", title_id: "C2004A03712",
  legislation_url: "https://www.legislation.gov.au/C2004A03712/latest/text",
  comp_id: "C2026C00227", effective_date: "2026-06-04", year: 1988, number: 119,
  toc: [], sections: {}, definitions: {}, raw_xml_url: "https://huggingface.co/datasets/cchew/lex-au/resolve/main/xml/privacy-act-1988.xml", split_by_part: false,
};

describe("ActHeader", () => {
  it("shows the Act title and No./year", () => {
    const wrapper = mount(ActHeader, { props: { bundle: BUNDLE } });
    expect(wrapper.text()).toContain("Privacy Act 1988");
    expect(wrapper.text()).toContain("No. 119 of 1988");
  });
});
