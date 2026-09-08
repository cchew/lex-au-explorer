import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import DefinitionTooltip from "../src/components/DefinitionTooltip.vue";

describe("DefinitionTooltip", () => {
  it("renders text and section eid", () => {
    const w = mount(DefinitionTooltip, { props: { text: "means a thing", sectionEid: "sec-3" } });
    expect(w.text()).toContain("means a thing");
    expect(w.text()).toContain("sec-3");
  });
  it("shows a resolved via line", () => {
    const w = mount(DefinitionTooltip, { props: {
      text: "means x", sectionEid: "sec-3",
      via: { actTitle: "Privacy Act 1988", sectionEid: "sec-6", resolved: true } } });
    expect(w.text()).toContain("via Privacy Act 1988");
    expect(w.text()).toContain("sec-6");
  });
  it("shows the not-in-corpus note when unresolved", () => {
    const w = mount(DefinitionTooltip, { props: {
      text: "has the same meaning as in the Foo Act 1999", sectionEid: "sec-3",
      via: { actTitle: "Foo Act 1999", resolved: false } } });
    expect(w.text()).toContain("defined by reference to Foo Act 1999 (not in this corpus)");
  });
  it("renders the Act Alike link only when actAlike", () => {
    const w = mount(DefinitionTooltip, { props: {
      text: "means x", sectionEid: "sec-3", term: "personal information", actAlike: true } });
    const a = w.get("a.definition-actalike");
    expect(a.attributes("href")).toBe("https://act-alike.netlify.app/term/personal%20information");
    expect(a.attributes("target")).toBe("_blank");
    const w2 = mount(DefinitionTooltip, { props: { text: "x", sectionEid: "s", term: "x" } });
    expect(w2.find("a.definition-actalike").exists()).toBe(false);
  });
});
