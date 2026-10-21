import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { scopeLabel, normaliseDef } from "../src/lib/scopeLabel";

describe("scopeLabel", () => {
  const cases: Array<[string, string, string, string]> = [
    ["sec-27", "section", "s 27", "This section only (s 27)"],
    ["sec-5~2", "section", "s 5", "This section only (s 5)"],
    ["part-2", "part", "Part 2", "This Part only (Part 2)"],
    ["dvs-1", "division", "Division 1", "This Division only (Division 1)"],
    ["schedule-1", "schedule", "Schedule 1", "This Schedule only (Schedule 1)"],
    ["schedule-1__clause-3", "clause", "Schedule 1, clause 3", "This clause only (Schedule 1, clause 3)"],
    ["weird_thing", "other", "weird_thing", "This scope only (weird_thing)"],
  ];
  it.each(cases)("%s", (eid, kind, text, phrase) => {
    expect(scopeLabel(eid)).toEqual({ kind, text, phrase });
  });
  it("uses the last component", () => {
    expect(scopeLabel("part-2__sec-9").text).toBe("s 9");
  });
});

describe("normaliseDef", () => {
  it("folds case, whitespace and trailing punctuation", () => {
    expect(normaliseDef("Means X.")).toBe(normaliseDef("means  x"));
    expect(normaliseDef("  means\tx ;")).toBe("means x");
  });
  it("keeps leading means and differing text", () => {
    expect(normaliseDef("means X")).not.toBe(normaliseDef("means Y"));
    expect(normaliseDef("means x").startsWith("means")).toBe(true);
  });
});

// oklch -> sRGB (Ottosson), then WCAG contrast
function oklchToRgb(l: number, c: number, hDeg: number): [number, number, number] {
  const h = (hDeg * Math.PI) / 180;
  const a = c * Math.cos(h), b = c * Math.sin(h);
  const l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s_ = (l - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const lin = [
    4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
    -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
    -0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_,
  ];
  return lin.map((v) => Math.min(1, Math.max(0, v))) as [number, number, number];
}
function luminance(rgb: [number, number, number]): number {
  return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
}
function contrast(a: string, b: string): number {
  const la = luminance(parse(a)), lb = luminance(parse(b));
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}
function parse(v: string): [number, number, number] {
  const m = v.match(/oklch\(\s*([\d.]+)%\s+([\d.]+)\s+([\d.]+)\s*\)/);
  if (!m) throw new Error("bad oklch: " + v);
  return oklchToRgb(Number(m[1]) / 100, Number(m[2]), Number(m[3]));
}

describe("local pill contrast", () => {
  const css = readFileSync(resolve(process.cwd(), "src/styles/tokens.css"), "utf8");
  const tok = (src: string, name: string): string => {
    const m = src.match(new RegExp(`--${name}:\\s*(oklch\\([^)]*\\))`));
    if (!m) throw new Error("missing token " + name);
    return m[1]!;
  };
  it(">= 4.5:1", () => {
    expect(contrast(tok(css, "pill-local-bg"), tok(css, "pill-local-text"))).toBeGreaterThanOrEqual(4.5);
  });
  // Every text use of --color-ink-3 and the background it sits on:
  // .subtitle/footer on page bg, .trust-meta/.trust-verify on trust panel
  // (surface-raised), tooltip via/citation on surface, missing-figure on bg/surface.
  const ink3Pairs: Array<[string, string]> = [
    ["color-bg", "page bg: .subtitle, footer, .version, missing figure"],
    ["color-surface", "tooltip .definition-via/.definition-citation, missing figure"],
    ["color-surface-raised", ".trust-meta, .trust-verify"],
  ];
  it.each(ink3Pairs)("ink-3 on %s >= 4.5:1 (%s)", (bg) => {
    expect(contrast(tok(css, "color-ink-3"), tok(css, bg))).toBeGreaterThanOrEqual(4.5);
  });
  it("keeps ink-3 lighter than ink-2 (hierarchy)", () => {
    const bg = tok(css, "color-surface");
    expect(contrast(tok(css, "color-ink-3"), bg)).toBeLessThan(contrast(tok(css, "color-ink-2"), bg));
  });
  it("has no dark-scheme override (the app has no dark theme; the tooltip stays white)", () => {
    expect(css).not.toMatch(/prefers-color-scheme/);
  });
  it("sanity: black on white is 21", () => {
    expect(contrast("oklch(0% 0 0)", "oklch(100% 0 0)")).toBeCloseTo(21, 0);
  });
});
