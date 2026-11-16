import { describe, it, expect } from "vitest";
import { resolvePredeploy } from "../scripts/predeploy.mjs";

const exists = (set: string[]) => (p: string) => set.includes(p);

describe("resolvePredeploy", () => {
  it("refuses to run without an explicit corpus and graph (no stale defaults)", () => {
    const r = resolvePredeploy({}, exists([]));
    expect(r.ok).toBe(false);
    expect(r.errors.join(" ")).toMatch(/LEXAU_CORPUS_DIR/);
    expect(r.errors.join(" ")).toMatch(/LEXAU_GRAPH_JSON/);
  });

  it("checks that the corpus index, xml dir and graph file exist", () => {
    const r = resolvePredeploy(
      { LEXAU_CORPUS_DIR: "/c", LEXAU_GRAPH_JSON: "/g.json" },
      exists(["/c/index.json"]),
    );
    expect(r.ok).toBe(false);
    expect(r.errors.join(" ")).toMatch(/\/c\/xml/);
    expect(r.errors.join(" ")).toMatch(/\/g\.json/);
  });

  it("defaults images to the corpus images dir and passes everything through when valid", () => {
    const r = resolvePredeploy(
      { LEXAU_CORPUS_DIR: "/c", LEXAU_GRAPH_JSON: "/g.json" },
      exists(["/c/index.json", "/c/xml", "/g.json"]),
    );
    expect(r).toEqual({
      ok: true,
      errors: [],
      corpusDir: "/c",
      graphJson: "/g.json",
      imagesDir: "/c/images",
    });
  });

  it("honours an explicit images dir", () => {
    const r = resolvePredeploy(
      { LEXAU_CORPUS_DIR: "/c", LEXAU_GRAPH_JSON: "/g.json", LEXAU_CORPUS_IMAGES: "/imgs" },
      exists(["/c/index.json", "/c/xml", "/g.json"]),
    );
    expect(r.imagesDir).toBe("/imgs");
  });
});
