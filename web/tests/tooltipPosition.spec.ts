import { describe, it, expect } from "vitest";
import { positionTooltip } from "../src/lib/tooltipPosition";

const rect = (left: number, top: number, width: number, height: number) =>
  ({ left, top, right: left + width, bottom: top + height, width, height }) as DOMRect;

describe("positionTooltip", () => {
  it("places the tooltip below the anchor by default", () => {
    const anchor = rect(100, 100, 40, 16);
    const tooltip = rect(0, 0, 320, 150);
    const pos = positionTooltip(anchor, tooltip, { width: 1200, height: 800 });
    expect(pos.top).toBe(120); // anchor.bottom + gap(4)
    expect(pos.left).toBe(100);
  });

  it("flips above the anchor when there is no room below in the viewport", () => {
    const anchor = rect(100, 700, 40, 16);
    const tooltip = rect(0, 0, 320, 150);
    const pos = positionTooltip(anchor, tooltip, { width: 1200, height: 800 });
    expect(pos.top).toBe(700 - 150 - 4); // anchor.top - tooltip.height - gap
  });

  it("clamps left so the tooltip never overflows the right edge", () => {
    const anchor = rect(1100, 100, 40, 16);
    const tooltip = rect(0, 0, 320, 150);
    const pos = positionTooltip(anchor, tooltip, { width: 1200, height: 800 });
    expect(pos.left).toBe(1200 - 320 - 8); // viewport.width - tooltip.width - margin
  });

  it("clamps left so the tooltip never overflows the left edge", () => {
    const anchor = rect(-50, 100, 40, 16);
    const tooltip = rect(0, 0, 320, 150);
    const pos = positionTooltip(anchor, tooltip, { width: 1200, height: 800 });
    expect(pos.left).toBe(8); // margin
  });

  it("clamps top within the viewport when neither above nor below fully fits", () => {
    const anchor = rect(100, 50, 40, 700);
    const tooltip = rect(0, 0, 320, 780);
    const pos = positionTooltip(anchor, tooltip, { width: 1200, height: 800 });
    expect(pos.top).toBe(12); // clamped to keep the bottom margin, since a 780-tall tooltip can't fit either side
  });
});
