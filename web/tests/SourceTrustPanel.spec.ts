import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import SourceTrustPanel from "../src/components/SourceTrustPanel.vue";
import type { VerificationInfo } from "../src/types";

const BUNDLE = {
  frbr_uri: "/akn/au/act/1988/119", title: "Privacy Act 1988", title_id: "C2004A03712",
  legislation_url: "https://www.legislation.gov.au/C2004A03712/latest/text",
  comp_id: "C2026C00227", effective_date: "2026-06-04", year: 1988, number: 119,
  toc: [], sections: {}, definitions: {},
  raw_xml_url: "https://huggingface.co/datasets/cchew/lex-au/resolve/main/xml/privacy-act-1988.xml",
  split_by_part: false,
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
    const link = wrapper.find(
      "a[href='https://huggingface.co/datasets/cchew/lex-au/resolve/main/xml/privacy-act-1988.xml']",
    );
    expect(link.exists()).toBe(true);
  });

  it("shows no verification line when the bundle has no verification data", () => {
    const wrapper = mount(SourceTrustPanel, { props: { bundle: BUNDLE } });
    expect(wrapper.find("[data-testid='verification']").exists()).toBe(false);
  });

  it("confirms the compilation is current", () => {
    const bundle = {
      ...BUNDLE,
      verification: { status: "current", checked_at: "2026-08-28" } as VerificationInfo,
    };
    const wrapper = mount(SourceTrustPanel, { props: { bundle } });
    const line = wrapper.find("[data-testid='verification']");
    expect(line.text()).toContain("2026-08-28");
    expect(line.text().toLowerCase()).toContain("current compilation");
  });

  it("warns when a newer compilation exists, naming it", () => {
    const bundle = {
      ...BUNDLE,
      verification: {
        status: "stale",
        checked_at: "2026-08-28",
        live_comp_id: "C2026C00301",
        live_effective_date: "2026-07-01",
      } as VerificationInfo,
    };
    const wrapper = mount(SourceTrustPanel, { props: { bundle } });
    const line = wrapper.find("[data-testid='verification']");
    expect(line.text()).toContain("C2026C00301");
    expect(line.text()).toContain("2026-07-01");
    expect(line.text()).toContain("2026-06-04");
  });

  it("flags an Act repealed since the snapshot", () => {
    const bundle = {
      ...BUNDLE,
      verification: { status: "repealed", checked_at: "2026-08-28" } as VerificationInfo,
    };
    const wrapper = mount(SourceTrustPanel, { props: { bundle } });
    const line = wrapper.find("[data-testid='verification']");
    expect(line.text().toLowerCase()).toContain("repealed");
  });
});
