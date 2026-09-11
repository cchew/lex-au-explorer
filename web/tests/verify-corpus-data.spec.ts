import { describe, it, expect } from "vitest";
import { checkCorpus, MIN_ACTS } from "../scripts/verify-corpus-data.mjs";

describe("checkCorpus", () => {
  it("fails the tiny E2E fixture set (2 Acts)", () => {
    expect(checkCorpus([{ slug: "privacy-act-1988" }, { slug: "big-act-split" }])).toEqual({
      ok: false,
      count: 2,
    });
  });

  it("passes a real-sized corpus index", () => {
    const index = Array.from({ length: MIN_ACTS + 1 }, (_, i) => ({ slug: `act-${i}` }));
    expect(checkCorpus(index)).toEqual({ ok: true, count: MIN_ACTS + 1 });
  });

  it("fails when the index isn't an array at all", () => {
    expect(checkCorpus(null).ok).toBe(false);
    expect(checkCorpus({}).ok).toBe(false);
  });
});
