import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import SectionContent from "../src/components/SectionContent.vue";

const SECTION = { heading: "Definitions", html: '<p>See <span data-term="personal information">personal information</span>.</p>' };
const DEFINITIONS = { "personal information": { text: "means information about an identified individual.", section_eid: "part-I__sec-6" } };

describe("SectionContent", () => {
  beforeEach(() => {
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

  it("does not show a tooltip for a term missing from definitions", async () => {
    const html = '<p><span data-term="unresolved term">unresolved term</span></p>';
    const wrapper = mount(SectionContent, { props: { section: { heading: "X", html }, definitions: {} } });
    const term = wrapper.find('[data-term="unresolved term"]');
    await term.trigger("mouseenter");
    vi.runAllTimers();
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".definition-tooltip").exists()).toBe(false);
  });
});
