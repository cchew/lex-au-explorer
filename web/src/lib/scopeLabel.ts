import { stripDisambig } from "./termHighlight";
import type { TocNode, SectionEntry } from "../types";

export type ScopeKind = "section" | "part" | "division" | "schedule" | "clause" | "other";

export interface ScopeLabel {
  kind: ScopeKind;
  text: string;
  phrase: string;
}

/** Resolves a container eId to its printed heading (toc node or section heading). */
export type ScopeLookup = (eid: string) => string | undefined;

export interface ScopeOptions {
  /** Regulations are cited "r 27", not "s 27". */
  regulation?: boolean;
}

/**
 * Lookup over the loaded bundle: toc node headings first, then
 * `sections[eid].heading`. The toc index is built once; `sections` is read
 * live so Part/Schedule files merged in later are seen.
 */
export function buildScopeLookup(
  toc: TocNode[],
  getSections: () => Record<string, SectionEntry> | undefined,
): ScopeLookup {
  const byEid = new Map<string, string>();
  const walk = (nodes: TocNode[]): void => {
    for (const n of nodes) {
      byEid.set(n.eid, n.heading);
      walk(n.children);
    }
  };
  walk(toc);
  return (eid) => byEid.get(eid) ?? getSections()?.[eid]?.heading;
}

/** True for "... Regulations 1998" style titles (not "... Regulations Act"). */
export function isRegulationTitle(title: string): boolean {
  return /\bRegulations?\b(?!.*\bAct\b)/.test(title);
}

const ROMAN = /^[IVXLCDM]+$/;
const NUMBERISH = /^\d[0-9A-Za-z.]*$/;
const LABELS: Record<string, { word: string; prefix: RegExp }> = {
  schedule: { word: "Schedule", prefix: /^Schedule\s+/i },
  part: { word: "Part", prefix: /^Part\s+/i },
  dvs: { word: "Division", prefix: /^Division\s+/i },
  clause: { word: "clause", prefix: /^Clause\s+/i },
  item: { word: "item", prefix: /^Item\s+/i },
};

// The printed number is the first token of the heading once any kind word is
// stripped. Unprefixed tokens must look like a number or Roman numeral so a
// heading with no number ("Introductory text") never yields a bogus one.
function printedNumber(kind: string, heading: string | undefined): string | undefined {
  if (!heading) return undefined;
  let h = heading.replace(/\u00a0/g, " ").trim();
  const prefix = LABELS[kind]!.prefix;
  const prefixed = prefix.test(h);
  h = h.replace(prefix, "");
  const tok = h.match(/^[0-9A-Za-z.]+/)?.[0]?.replace(/\.+$/, "");
  if (!tok) return undefined;
  if (NUMBERISH.test(tok) || ROMAN.test(tok)) return tok;
  return prefixed && /^[A-Z]{1,2}$/.test(tok) ? tok : undefined;
}

function segment(eid: string): RegExpMatchArray | null {
  return eid.match(/^(sec|part|dvs|schedule|clause|item)-(.+)$/);
}

function lookupLabel(parts: string[], lookup: ScopeLookup): ScopeLabel | null {
  const last = segment(parts[parts.length - 1] ?? "");
  if (!last || last[1] === "sec") return null;
  const chain: string[] = [];
  for (let i = 0; i < parts.length; i++) {
    const m = segment(parts[i]!);
    if (!m || m[1] === "sec") continue;
    const kind = m[1]!;
    // Containers above the Schedule are not part of the printed citation.
    if (chain.length === 0 && kind !== "schedule" && i !== parts.length - 1) continue;
    const num = printedNumber(kind, lookup(parts.slice(0, i + 1).join("__"))) ?? m[2]!;
    chain.push(`${LABELS[kind]!.word} ${num}`);
  }
  const text = chain.join(", ");
  switch (last[1]) {
    case "part":
      return { kind: "part", text, phrase: `This Part only (${text})` };
    case "dvs":
      return { kind: "division", text, phrase: `This Division only (${text})` };
    case "schedule":
      return { kind: "schedule", text, phrase: `This Schedule only (${text})` };
    case "clause":
      return { kind: "clause", text, phrase: `This clause only (${text})` };
    default:
      return { kind: "other", text, phrase: `This item only (${text})` };
  }
}

export function scopeLabel(scope: string, lookup?: ScopeLookup, opts: ScopeOptions = {}): ScopeLabel {
  const parts = stripDisambig(scope).split("__");
  if (lookup) {
    const label = lookupLabel(parts, lookup);
    if (label) return label;
  }
  const last = parts[parts.length - 1] ?? "";
  const m = last.match(/^(sec|part|dvs|schedule|clause)-(.+)$/);
  if (m) {
    const n = m[2]!;
    switch (m[1]) {
      case "sec":
        return opts.regulation
          ? { kind: "section", text: `r ${n}`, phrase: `This regulation only (r ${n})` }
          : { kind: "section", text: `s ${n}`, phrase: `This section only (s ${n})` };
      case "part":
        return { kind: "part", text: `Part ${n}`, phrase: `This Part only (Part ${n})` };
      case "dvs":
        return { kind: "division", text: `Division ${n}`, phrase: `This Division only (Division ${n})` };
      case "schedule":
        return { kind: "schedule", text: `Schedule ${n}`, phrase: `This Schedule only (Schedule ${n})` };
      case "clause": {
        const sch = parts.length > 1 ? parts[0]!.match(/^schedule-(.+)$/) : null;
        const text = sch ? `Schedule ${sch[1]}, clause ${n}` : `clause ${n}`;
        return { kind: "clause", text, phrase: `This clause only (${text})` };
      }
    }
  }
  return { kind: "other", text: scope, phrase: `This scope only (${scope})` };
}

export function normaliseDef(text: string): string {
  return text.toLowerCase().replace(/\s+/g, " ").trim().replace(/[.;:,\s]+$/, "");
}
