import { stripDisambig } from "./termHighlight";

export type ScopeKind = "section" | "part" | "division" | "schedule" | "clause" | "other";

export interface ScopeLabel {
  kind: ScopeKind;
  text: string;
  phrase: string;
}

export function scopeLabel(scope: string): ScopeLabel {
  const parts = stripDisambig(scope).split("__");
  const last = parts[parts.length - 1] ?? "";
  const m = last.match(/^(sec|part|dvs|schedule|clause)-(.+)$/);
  if (m) {
    const n = m[2]!;
    switch (m[1]) {
      case "sec":
        return { kind: "section", text: `s ${n}`, phrase: `This section only (s ${n})` };
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
