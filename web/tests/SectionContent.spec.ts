import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import SectionContent from "../src/components/SectionContent.vue";
import { track } from "../src/lib/analytics";

vi.mock("../src/lib/analytics", () => ({ track: vi.fn() }));

const SECTION = { heading: "Definitions", html: '<p>See <span data-term="personal information">personal information</span>.</p>' };
const DEFINITIONS = { "personal information": { text: "means information about an identified individual.", section_eid: "part-I__sec-6" } };

describe("SectionContent", () => {
  beforeEach(() => {
    vi.mocked(track).mockClear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the tooltip on hover with the correct definition text", async () => {
    const wrapper = mount(SectionContent, { props: { section: SECTION, definitions: DEFINITIONS } });
    const term = wrapper.find('[data-term="personal information"]');
    expect(term.exists()).toBe(true);
    await term.trigger("mouseover");
    vi.runAllTimers();
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".definition-tooltip").exists()).toBe(true);
    expect(wrapper.text()).toContain("means information about an identified individual.");
  });

  it("tracks a resolved definition hover with its Act slug", async () => {
    const wrapper = mount(SectionContent, {
      props: { section: SECTION, definitions: DEFINITIONS, slug: "privacy-act-1988" },
    });
    await wrapper.find('[data-term="personal information"]').trigger("mouseover");
    vi.runAllTimers();
    await wrapper.vm.$nextTick();
    expect(track).toHaveBeenCalledWith("definition_hover", {
      term: "personal information",
      slug: "privacy-act-1988",
    });
  });

  it("does not show a tooltip for a term missing from definitions", async () => {
    const html = '<p><span data-term="unresolved term">unresolved term</span></p>';
    const wrapper = mount(SectionContent, { props: { section: { heading: "X", html }, definitions: {} } });
    const term = wrapper.find('[data-term="unresolved term"]');
    await term.trigger("mouseover");
    vi.runAllTimers();
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".definition-tooltip").exists()).toBe(false);
  });

  it("does not show tooltip immediately (200ms delay)", async () => {
    const wrapper = mount(SectionContent, { props: { section: SECTION, definitions: DEFINITIONS } });
    const term = wrapper.find('[data-term="personal information"]');
    await term.trigger("mouseover");
    // Advance 199ms — tooltip should NOT be visible yet
    vi.advanceTimersByTime(199);
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".definition-tooltip").exists()).toBe(false);
    // Advance 1 more ms to reach 200ms
    vi.advanceTimersByTime(1);
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".definition-tooltip").exists()).toBe(true);
  });

  it("clears pending timer and hides tooltip on mouseleave", async () => {
    const wrapper = mount(SectionContent, { props: { section: SECTION, definitions: DEFINITIONS } });
    const term = wrapper.find('[data-term="personal information"]');
    // Hover over and wait 100ms (halfway to 200ms)
    await term.trigger("mouseover");
    vi.advanceTimersByTime(100);
    // Leave before the tooltip shows
    await wrapper.find(".section-html").trigger("mouseout");
    vi.advanceTimersByTime(100); // Advance past 200ms total
    await wrapper.vm.$nextTick();
    // Tooltip should not show because the timer was cleared
    expect(wrapper.find(".definition-tooltip").exists()).toBe(false);
  });

  it("hides tooltip immediately when mouseout occurs after it shows", async () => {
    const wrapper = mount(SectionContent, { props: { section: SECTION, definitions: DEFINITIONS } });
    const term = wrapper.find('[data-term="personal information"]');
    await term.trigger("mouseover");
    vi.runAllTimers();
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".definition-tooltip").exists()).toBe(true);
    // Now move mouse away
    await wrapper.find(".section-html").trigger("mouseout");
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".definition-tooltip").exists()).toBe(false);
  });
});
