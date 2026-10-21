import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import SectionContent from "../src/components/SectionContent.vue";
import { buildMatcher } from "../src/lib/termHighlight";
import { track } from "../src/lib/analytics";
import type { TermEntry } from "../src/types";

vi.mock("../src/lib/analytics", () => ({ track: vi.fn() }));

const TERMS: TermEntry[] = [
  { term: "personal information", display: "personal information", usedInBody: true,
    defs: [{ text: "means information about an identified individual.", eid: "part-I__sec-6" }] },
  { term: "person", display: "person", usedInBody: true, defs: [{ text: "includes a body.", eid: "part-I__sec-6" }] },
];
const matcher = buildMatcher(TERMS);
const termIndex = new Map(TERMS.map((t) => [t.term, t]));
const base = {
  matcher, termIndex, sectionEid: "part-I__sec-9", highlightEnabled: true,
  section: { heading: "Use", html: "<p>A person handling personal information about a person.</p>" },
};

describe("SectionContent", () => {
  beforeEach(() => { vi.mocked(track).mockClear(); vi.useFakeTimers(); });
  afterEach(() => vi.useRealTimers());

  it("wraps a body term after mount and shows the tooltip on hover", async () => {
    const w = mount(SectionContent, { props: base });
    await w.vm.$nextTick();
    const span = w.find("span[data-term='personal information'][data-def-eid='part-I__sec-6']");
    expect(span.exists()).toBe(true);
    await span.trigger("mouseover");
    vi.runAllTimers();
    await w.vm.$nextTick();
    expect(w.text()).toContain("means information about an identified individual.");
  });

  it("stoplist term never wrapped", async () => {
    const w = mount(SectionContent, { props: base });
    await w.vm.$nextTick();
    expect(w.findAll("span[data-term='person']").length).toBe(0);
  });

  it("no runtime spans when highlightEnabled is false; toggling on adds them", async () => {
    const w = mount(SectionContent, { props: { ...base, highlightEnabled: false } });
    await w.vm.$nextTick();
    expect(w.findAll("span[data-def-eid]").length).toBe(0);
    await w.setProps({ highlightEnabled: true });
    await w.vm.$nextTick();
    expect(w.findAll("span[data-def-eid]").length).toBeGreaterThan(0);
  });

  it("hovers a corpus definiendum span via termIndex and tracks context=definitions", async () => {
    const w = mount(SectionContent, { props: { ...base,
      section: { heading: "Definitions", html: "<p><span data-term=\"person\">person</span> includes a body.</p>" },
      sectionEid: "part-I__sec-6" } });
    await w.vm.$nextTick();
    await w.find("span[data-term='person']").trigger("mouseover");
    vi.runAllTimers();
    await w.vm.$nextTick();
    expect(w.text()).toContain("includes a body.");
    expect(track).toHaveBeenCalledWith("definition_hover", expect.objectContaining({ context: "definitions" }));
  });

  it("tracks context=body for a runtime span", async () => {
    const w = mount(SectionContent, { props: { ...base, slug: "privacy-act-1988" } });
    await w.vm.$nextTick();
    await w.find("span[data-def-eid]").trigger("mouseover");
    vi.runAllTimers();
    await w.vm.$nextTick();
    expect(track).toHaveBeenCalledWith("definition_hover", expect.objectContaining({ context: "body", slug: "privacy-act-1988" }));
  });

  it("clears the pending hover timer on unmount so it never fires", async () => {
    const w = mount(SectionContent, { props: base });
    await w.vm.$nextTick();
    await w.find("span[data-term='personal information'][data-def-eid='part-I__sec-6']").trigger("mouseover");
    w.unmount();
    vi.advanceTimersByTime(200);
    expect(track).not.toHaveBeenCalled();
  });

  it("positions the tooltip near the hovered term instead of at a fixed offset", async () => {
    const anchorRect = { left: 300, top: 300, right: 340, bottom: 316, width: 40, height: 16 } as DOMRect;
    const tooltipRect = { left: 0, top: 0, right: 320, bottom: 150, width: 320, height: 150 } as DOMRect;
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      return this.classList.contains("tooltip-anchor") ? tooltipRect : anchorRect;
    });
    Object.defineProperty(window, "innerWidth", { value: 1200, configurable: true });
    Object.defineProperty(window, "innerHeight", { value: 1000, configurable: true });

    const w = mount(SectionContent, { props: base });
    await w.vm.$nextTick();
    await w.find("span[data-term='personal information'][data-def-eid='part-I__sec-6']").trigger("mouseover");
    vi.runAllTimers();
    await w.vm.$nextTick();
    await w.vm.$nextTick();
    const wrapper = w.get(".tooltip-anchor");
    expect(wrapper.attributes("style")).toContain("top: 320px"); // anchor.bottom(316) + gap(4)
    expect(wrapper.attributes("style")).toContain("left: 300px");
  });

  it("keeps the tooltip open when the mouse moves from the term onto it, and dismisses on truly leaving", async () => {
    const w = mount(SectionContent, { props: base });
    await w.vm.$nextTick();
    await w.find("span[data-term='personal information'][data-def-eid='part-I__sec-6']").trigger("mouseover");
    vi.runAllTimers();
    await w.vm.$nextTick();
    const wrapper = w.get(".tooltip-anchor");

    await w.find(".section-html").trigger("mouseout", { relatedTarget: wrapper.element });
    expect(w.find(".tooltip-anchor").exists()).toBe(true);

    await wrapper.trigger("mouseleave", { relatedTarget: document.body });
    expect(w.find(".tooltip-anchor").exists()).toBe(false);
  });
  const LOCAL: TermEntry = {
    term: "widget", display: "widget", usedInBody: true,
    defs: [{ text: "local widget meaning.", eid: "part-I__sec-6", scope: "part-I__sec-6" }],
  };

  it("hover on a definition-section term never shows a local def outside scope", async () => {
    const w = mount(SectionContent, { props: { ...base,
      termIndex: new Map([["widget", LOCAL]]), matcher: buildMatcher([LOCAL]),
      section: { heading: "Defs", html: "<p><span data-term=\"widget\">widget</span> means x.</p>" },
      sectionEid: "part-III__sec-40" } });
    await w.vm.$nextTick();
    await w.find("span[data-term='widget']").trigger("mouseover");
    vi.runAllTimers();
    await w.vm.$nextTick();
    expect(w.find(".definition-tooltip").exists()).toBe(false);
  });

  it("body span with data-def-scope resolves the matching def", async () => {
    const entry: TermEntry = {
      term: "widget", display: "widget", usedInBody: true,
      defs: [
        { text: "act-wide meaning.", eid: "part-I__sec-6" },
        { text: "local meaning.", eid: "part-I__sec-6", scope: "part-II" },
      ],
    };
    const w = mount(SectionContent, { props: { ...base,
      termIndex: new Map([["widget", entry]]), matcher: buildMatcher([entry]),
      section: { heading: "Body", html: "<p>a widget here</p>" },
      sectionEid: "part-II__sec-9" } });
    await w.vm.$nextTick();
    const span = w.find("span[data-term='widget']");
    expect(span.attributes("data-def-scope")).toBe("part-II");
    await span.trigger("mouseover");
    vi.runAllTimers();
    await w.vm.$nextTick();
    expect(w.text()).toContain("local meaning.");
  });

  it("a term entry shipped in a Schedule part carries both its local and Act-wide defs, so the popup compares them", async () => {
    const entry: TermEntry = {
      term: "widget", display: "widget", usedInBody: true,
      defs: [
        { text: "act-wide meaning.", eid: "part-I__sec-6" },
        { text: "local meaning.", eid: "sch-1__clause-2", scope: "sch-1" },
      ],
    };
    const w = mount(SectionContent, { props: { ...base,
      termIndex: new Map([["widget", entry]]), matcher: buildMatcher([entry]),
      section: { heading: "Sched", html: "<p>a widget here</p>" },
      sectionEid: "sch-1__clause-3" } });
    await w.vm.$nextTick();
    await w.find("span[data-term='widget']").trigger("mouseover");
    vi.runAllTimers();
    await w.vm.$nextTick();
    const tip = w.findComponent({ name: "DefinitionTooltip" });
    expect(tip.props("scope")).toBe("sch-1");
    expect(tip.props("actWide")).toEqual({ text: "act-wide meaning.", eid: "part-I__sec-6", term: "widget" });
  });
});
