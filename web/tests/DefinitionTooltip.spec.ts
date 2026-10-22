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

  describe("local definitions", () => {
    const base = { text: "means divulge or communicate", sectionEid: "sec-27", term: "disclose", scope: "sec-27", actAlike: true };
    const wide = { text: "means make known to a person outside the agency", eid: "sec-6", term: "disclose" };

    it("shows pill, scope phrase, and the differing Act-wide definition", () => {
      const w = mount(DefinitionTooltip, { props: { ...base, actWide: wide } });
      expect(w.get(".definition-pill").text()).toBe("Local definition");
      expect(w.text()).toContain("This section only (s 27)");
      expect(w.text()).toContain("Differs from the Act-wide definition");
      expect(w.text()).toContain(wide.text);
      const ref = w.get(".definition-actwide-ref");
      expect(ref.text()).toBe("s 6");
      expect(ref.classes()).toContain("mono");
      expect(ref.element.tagName).toBe("SPAN");
    });
    it("bolds the term on both lines without quotes", () => {
      const w = mount(DefinitionTooltip, { props: { ...base, actWide: wide } });
      const strongs = w.findAll("strong");
      expect(strongs.map((s) => s.text())).toEqual(["disclose", "disclose"]);
      expect(w.text()).not.toContain('"');
    });
    it("omits Differs when Act-wide text is equivalent", () => {
      const w = mount(DefinitionTooltip, { props: { ...base, actWide: { ...wide, text: "Means  Divulge or communicate." } } });
      expect(w.text()).not.toContain("Differs");
      expect(w.find(".definition-pill").exists()).toBe(true);
    });
    it("stops after the scope line without Act-wide", () => {
      const w = mount(DefinitionTooltip, { props: base });
      expect(w.text()).toContain("This section only (s 27)");
      expect(w.text()).not.toContain("Differs");
    });
    it("uses the lookup for printed numbers and r for regulations", () => {
      const lookup = (eid: string): string | undefined =>
        eid === "schedule-3" ? "Schedule 8 \u2014 Rules" : eid === "schedule-3__item-1" ? "38 Sealing" : undefined;
      const w = mount(DefinitionTooltip, {
        props: { ...base, scope: "schedule-3__item-1", scopeLookup: lookup, actWide: { ...wide, eid: "part-I__sec-6" }, regulation: true },
      });
      expect(w.text()).toContain("This item only (Schedule 8, item 38)");
      expect(w.get(".definition-actwide-ref").text()).toBe("r 6");
    });
    it("hides the Act Alike link for a local winner", () => {
      const w = mount(DefinitionTooltip, { props: { ...base, actWide: wide } });
      expect(w.find("a.definition-actalike").exists()).toBe(false);
    });
  });

  it("renders an Act-wide winner with the original markup, even with actWide passed", () => {
    const props = { text: "means x", sectionEid: "sec-3", term: "foo", actAlike: true };
    const expected =
      '<div class="definition-tooltip" role="tooltip"><!--v-if--><!--v-if--><p class="definition-text">means x</p><p class="definition-citation mono">sec-3</p><a class="definition-actalike" href="https://act-alike.netlify.app/term/foo" target="_blank" rel="noopener">Open in Act Alike \u2197</a></div>';
    const norm = (h: string): string => h.replace(/<!--[^>]*-->/g, "").replace(/\s+/g, " ").replace(/> </g, "><");
    const strip = (h: string): string => norm(h).replace(/ data-v-[0-9a-f]+=""/g, "");
    expect(strip(mount(DefinitionTooltip, { props }).html())).toBe(strip(expected));
    const w2 = mount(DefinitionTooltip, { props: { ...props, actWide: { text: "means x", eid: "sec-3", term: "foo" } } });
    expect(strip(w2.html())).toBe(strip(expected));
  });
});
