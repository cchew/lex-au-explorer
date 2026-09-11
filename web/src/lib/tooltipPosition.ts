export interface Rect {
  left: number;
  top: number;
  right: number;
  bottom: number;
  width: number;
  height: number;
}

export interface Viewport {
  width: number;
  height: number;
}

const GAP = 4;
const MARGIN = 8;

// Anchors the tooltip under the hovered term, flipping above it when there is
// no room below, then clamps both axes so it never renders outside the
// viewport regardless of where the anchor sits in the (possibly very long)
// section.
export function positionTooltip(anchor: Rect, tooltip: Rect, viewport: Viewport): { top: number; left: number } {
  const fitsBelow = anchor.bottom + GAP + tooltip.height <= viewport.height - MARGIN;
  const fitsAbove = anchor.top - GAP - tooltip.height >= MARGIN;
  let top: number;
  if (fitsBelow || !fitsAbove) top = anchor.bottom + GAP;
  else top = anchor.top - GAP - tooltip.height;
  top = Math.min(Math.max(top, MARGIN), Math.max(MARGIN, viewport.height - tooltip.height - MARGIN));

  let left = anchor.left;
  left = Math.min(left, viewport.width - tooltip.width - MARGIN);
  left = Math.max(left, MARGIN);

  return { top, left };
}
