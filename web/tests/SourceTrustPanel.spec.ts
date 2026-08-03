import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import SourceTrustPanel from "../src/components/SourceTrustPanel.vue";

const BUNDLE = {
  frbr_uri: "/akn/au/act/1988/119", title: "Privacy Act 1988", title_id: "C2004A03712",
  legislation_url: "https://www.legislation.gov.au/C2004A03712/latest/text",
  comp_id: "C2026C00227", effective_date: "2026-06-04",
  toc: [], sections: {}, definitions: {}, raw_xml_url: "/data/privacy-act-1988.xml", split_by_part: false,
};

describe("SourceTrustPanel", () => {
  it("links to the legislation.gov.au permalink and shows the compilation info", () => {
    const wrapper = mount(SourceTrustPanel, { props: { bundle: BUNDLE } });
    const link = wrapper.find("a[href='https://www.legislation.gov.au/C2004A03712/latest/text']");
    expect(link.exists()).toBe(true);
    expect(wrapper.text()).toContain("C2026C00227");
    expect(wrapper.text()).toContain("2026-06-04");
  });

  it("links to the raw AKN XML", () => {
    const wrapper = mount(SourceTrustPanel, { props: { bundle: BUNDLE } });
    const link = wrapper.find("a[href='/data/privacy-act-1988.xml']");
    expect(link.exists()).toBe(true);
  });
});
