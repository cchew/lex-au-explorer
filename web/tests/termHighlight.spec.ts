import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { surfaceForms, buildMatcher, resolveDef, highlightTerms, unhighlightTerms, STOPLIST } from "../src/lib/termHighlight";
import type { TermEntry } from "../src/types";

const T = (term: string, defs: [string, string][], extra: Partial<TermEntry> = {}): TermEntry =>
  ({ term, display: term, defs: defs.map(([text, eid]) => ({ text, eid })), ...extra });

describe("surfaceForms", () => {
  it("matches the shared Python fixture", () => {
    // `import.meta.url` via a local so Vite's `new URL(literal, import.meta.url)`
    // asset-transform doesn't rewrite this to an http dev-server URL.
    const base = import.meta.url;
    const fx = JSON.parse(readFileSync(new URL("../../tests/fixtures/surface-forms.json", base), "utf8"));
    for (const [term, expected] of Object.entries(fx)) {
      expect(new Set(surfaceForms(term))).toEqual(new Set(expected as string[]));
    }
  });
});

describe("resolveDef", () => {
  it("returns the sole def", () => {
    expect(resolveDef(T("x", [["A", "sec-1"]]), "sec-9")!.text).toBe("A");
  });
  it("prefers an exact section match", () => {
    const e = T("x", [["A", "part-1__sec-1"], ["B", "part-2__sec-2"]]);
    expect(resolveDef(e, "part-2__sec-2")!.text).toBe("B");
  });
  it("falls back to the deepest enclosing prefix", () => {
    const e = T("x", [["A", "part-1__sec-1"], ["B", "part-2__sec-9"]]);
    expect(resolveDef(e, "part-2__dvs-3__sec-40")!.text).toBe("B");
  });
  it("returns null when nothing encloses", () => {
    const e = T("x", [["A", "part-1__sec-1"], ["B", "part-2__sec-2"]]);
    expect(resolveDef(e, "part-9__sec-1")).toBeNull();
  });
});

describe("buildMatcher + highlightTerms", () => {
  const mk = (html: string) => { const d = document.createElement("div"); d.innerHTML = html; return d; };

  it("wraps a body term and preserves the inflected surface", () => {
    const m = buildMatcher([T("entity", [["means a body", "sec-3"]], { usedInBody: true })]);
    const root = mk("<p>Two entities applied.</p>");
    highlightTerms(root, m, "sec-5", { stoplist: new Set() });
    const span = root.querySelector("span[data-term='entity'][data-def-eid='sec-3']")!;
    expect(span.textContent).toBe("entities");
  });

  it("skips headings, akn-ref, unresolved refs, existing data-term, notes", () => {
    const m = buildMatcher([T("entity", [["d", "sec-1"]])]);
    const root = mk(
      "<h3>entity</h3><a class='akn-ref'>entity</a>" +
      "<span class='akn-ref akn-ref-unresolved'>entity</span>" +
      "<span data-term='entity'>entity</span>" +
      "<div class='akn-notetext'>entity</div>"
    );
    highlightTerms(root, m, "sec-1", { stoplist: new Set() });
    expect(root.querySelectorAll("span[data-def-eid]").length).toBe(0);
  });

  it("stoplist term wrapped once per section, others every time", () => {
    const m = buildMatcher([
      T("person", [["d", "sec-1"]]), T("associate", [["d", "sec-1"]]),
    ]);
    const root = mk("<p>A person told a person. An associate saw an associate.</p>");
    highlightTerms(root, m, "sec-1", { stoplist: new Set(["person"]) });
    expect(root.querySelectorAll("span[data-term='person']").length).toBe(1);
    expect(root.querySelectorAll("span[data-term='associate']").length).toBe(2);
  });

  it("adds a11y attributes and is idempotent", () => {
    const m = buildMatcher([T("entity", [["d", "sec-1"]], { display: "entity" })]);
    const root = mk("<p>The entity acts.</p>");
    highlightTerms(root, m, "sec-1", { stoplist: new Set() });
    highlightTerms(root, m, "sec-1", { stoplist: new Set() });
    const spans = root.querySelectorAll("span[data-def-eid]");
    expect(spans.length).toBe(1);
    expect(spans[0].getAttribute("role")).toBe("button");
    expect(spans[0].getAttribute("tabindex")).toBe("0");
  });

  it("unhighlightTerms round-trips and leaves corpus spans", () => {
    const m = buildMatcher([T("entity", [["d", "sec-1"]])]);
    const root = mk("<p><span data-term='entity'>entity</span> and an entity.</p>");
    highlightTerms(root, m, "sec-1", { stoplist: new Set() });
    unhighlightTerms(root);
    expect(root.querySelectorAll("span[data-def-eid]").length).toBe(0);
    expect(root.querySelectorAll("span[data-term='entity']").length).toBe(1); // corpus span kept
    expect(root.textContent).toBe("entity and an entity.");
  });

  it("longest-match: 'connected entity' beats 'entity'", () => {
    const m = buildMatcher([
      T("entity", [["d", "sec-1"]]), T("connected entity", [["d", "sec-1"]]),
    ]);
    const root = mk("<p>A connected entity here.</p>");
    highlightTerms(root, m, "sec-1", { stoplist: new Set() });
    expect(root.querySelector("span[data-def-eid]")!.textContent).toBe("connected entity");
  });
});
