import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { surfaceForms, buildMatcher, resolveDef, resolvePair, stripDisambig, highlightTerms, unhighlightTerms, STOPLIST } from "../src/lib/termHighlight";
import type { TermEntry } from "../src/types";

const T = (term: string, defs: [string, string, string?][], extra: Partial<TermEntry> = {}): TermEntry =>
  ({
    term, display: term,
    defs: defs.map(([text, eid, scope]) => (scope === undefined ? { text, eid } : { text, eid, scope })),
    ...extra,
  });

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

describe("stripDisambig", () => {
  it("strips ~N from every component", () => {
    expect(stripDisambig("part-I~2__sec-5~3")).toBe("part-I__sec-5");
    expect(stripDisambig("sec-5")).toBe("sec-5");
  });
});

describe("scope resolution", () => {
  it("returns null for a lone local def outside its scope", () => {
    const e = T("x", [["L", "sec-2", "sec-2"]]);
    expect(resolveDef(e, "sec-9")).toBeNull();
    expect(resolveDef(e, "sec-2")!.text).toBe("L");
  });
  it("local def wins inside scope over Act-wide, actWide populated", () => {
    const e = T("x", [["A", "sec-1"], ["L", "sec-5", "sec-5"]]);
    const r = resolvePair(e, "sec-5")!;
    expect(r.winner.text).toBe("L");
    expect(r.actWide!.text).toBe("A");
    expect(resolvePair(e, "sec-6")!.winner.text).toBe("A");
  });
  it("section keys with ~N disambiguators are inside scope", () => {
    expect(resolveDef(T("x", [["L", "sec-5", "sec-5"]]), "sec-5~2")!.text).toBe("L");
    expect(resolveDef(T("x", [["L", "schedule-1", "schedule-1"]]), "schedule-1__clause-30~2")!.text).toBe("L");
  });
  it("does not match a scope that is only a string prefix", () => {
    expect(resolveDef(T("x", [["L", "sec-5", "sec-5"]]), "sec-50")).toBeNull();
    expect(resolveDef(T("x", [["L", "sec-5", "sec-5"]]), "sec-50__sub-1")).toBeNull();
  });
  it("deepest of two nested local scopes wins", () => {
    const e = T("x", [["P", "part-I", "part-I"], ["S", "part-I__sec-5", "part-I__sec-5"]]);
    expect(resolveDef(e, "part-I__sec-5")!.text).toBe("S");
    expect(resolveDef(e, "part-I__sec-6")!.text).toBe("P");
  });
  it("two local defs with same eid but different scopes both resolve", () => {
    const e = T("x", [["A", "sec-1", "sec-2"], ["B", "sec-1", "sec-3"]]);
    expect(resolveDef(e, "sec-2")!.text).toBe("A");
    expect(resolveDef(e, "sec-3")!.text).toBe("B");
  });
  it("part-scoped applies to descendants; section-scoped does not leak to siblings", () => {
    const part = T("x", [["P", "part-I", "part-I"]]);
    expect(resolveDef(part, "part-I__sec-5")!.text).toBe("P");
    const sec = T("x", [["S", "part-I__sec-5", "part-I__sec-5"]]);
    expect(resolveDef(sec, "part-I__sec-5")!.text).toBe("S");
    expect(resolveDef(sec, "part-I__sec-6")).toBeNull();
  });
  it("actWide is null when only a local def exists", () => {
    const r = resolvePair(T("x", [["L", "sec-5", "sec-5"]]), "sec-5")!;
    expect(r.winner.text).toBe("L");
    expect(r.actWide).toBeNull();
  });
  it("Act-wide def is still sole-returned alongside an out-of-scope local def", () => {
    const e = T("x", [["A", "sec-1"], ["L", "sec-5", "sec-5"]]);
    expect(resolvePair(e, "sec-9")!.winner.text).toBe("A");
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

  it("stoplist term never wrapped, others every time", () => {
    const m = buildMatcher([
      T("person", [["d", "sec-1"]]), T("associate", [["d", "sec-1"]]),
    ]);
    const root = mk("<p>A person told a person. An associate saw an associate.</p>");
    highlightTerms(root, m, "sec-1", { stoplist: new Set(["person"]) });
    expect(root.querySelectorAll("span[data-term='person']").length).toBe(0);
    expect(root.querySelectorAll("span[data-term='associate']").length).toBe(2);
  });

  it("adds a11y attributes and is idempotent", () => {
    const m = buildMatcher([T("entity", [["d", "sec-1"]], { display: "entity" })]);
    const root = mk("<p>The entity acts.</p>");
    highlightTerms(root, m, "sec-1", { stoplist: new Set() });
    highlightTerms(root, m, "sec-1", { stoplist: new Set() });
    const spans = root.querySelectorAll("span[data-def-eid]");
    expect(spans.length).toBe(1);
    expect(spans[0]!.getAttribute("role")).toBe("button");
    expect(spans[0]!.getAttribute("tabindex")).toBe("0");
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

  it("stoplisted term: in-scope local def highlighted with data-def-scope, outside scope not", () => {
    const m = buildMatcher([T("person", [["L", "sec-5", "sec-5"]])]);
    const inScope = mk("<p>A person.</p>");
    highlightTerms(inScope, m, "sec-5", { stoplist: new Set(["person"]) });
    const span = inScope.querySelector("span[data-term='person']") as HTMLElement;
    expect(span).not.toBeNull();
    expect(span.dataset.defScope).toBe("sec-5");
    const outside = mk("<p>A person.</p>");
    highlightTerms(outside, m, "sec-9", { stoplist: new Set(["person"]) });
    expect(outside.querySelectorAll("span[data-term]").length).toBe(0);
  });

  it("stoplisted Act-wide-only term stays unhighlighted; Act-wide span has empty data-def-scope", () => {
    const m = buildMatcher([T("person", [["A", "sec-1"]]), T("associate", [["A", "sec-1"]])]);
    const root = mk("<p>A person and an associate.</p>");
    highlightTerms(root, m, "sec-1", { stoplist: new Set(["person"]) });
    expect(root.querySelectorAll("span[data-term='person']").length).toBe(0);
    expect((root.querySelector("span[data-term='associate']") as HTMLElement).dataset.defScope).toBe("");
  });
});
