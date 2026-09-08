import type { TermEntry, DefEntry } from "../types";

export interface Matcher {
  regex: RegExp;
  lookup: Map<string, TermEntry>;
  byTerm: Map<string, TermEntry>;
}

export const STOPLIST: ReadonlySet<string> = new Set([
  "person", "individual", "entity", "body", "company", "corporation", "minister",
  "secretary", "officer", "official", "employee", "employer", "member", "director",
  "child", "parent", "relative", "spouse", "adult", "document", "record",
  "information", "notice", "application", "approval", "decision", "determination",
  "function", "power", "duty", "premises", "place", "property", "money", "amount",
  "payment", "benefit", "period", "month", "year", "day", "week", "state",
  "territory", "commonwealth", "agency", "authority", "department", "court",
  "tribunal", "regulations", "act", "provision", "section", "part", "division",
  "matter", "thing", "proceeding", "offence",
]);

const APOS = ["'s", "’s"];

function inflectLastWord(term: string): string[] {
  const parts = term.split(" ");
  const last = parts[parts.length - 1]!;
  const v = [last + "s", last + "es", ...APOS.map((a) => last + a)];
  if (last.endsWith("y") && last.length > 1 && !"aeiou".includes(last[last.length - 2]!))
    v.push(last.slice(0, -1) + "ies");
  if (last.endsWith("s") && last.length > 1) v.push(last.slice(0, -1));
  return v.map((w) => [...parts.slice(0, -1), w].join(" ").trim());
}

export function surfaceForms(term: string): string[] {
  const base = term.replace(/^\*+/, "").trim().toLowerCase().replace(/\s+/g, " ");
  const seen = new Set<string>();
  for (const f of [base, ...inflectLastWord(base).map((x) => x.toLowerCase())])
    if (f) seen.add(f);
  return [...seen];
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function buildMatcher(terms: TermEntry[]): Matcher {
  const lookup = new Map<string, TermEntry>();
  const byTerm = new Map<string, TermEntry>();
  const forms: string[] = [];
  for (const entry of terms) {
    byTerm.set(entry.term, entry);
    for (const f of surfaceForms(entry.term)) {
      if (!lookup.has(f)) {
        lookup.set(f, entry);
        forms.push(f);
      }
    }
  }
  forms.sort((a, b) => b.length - a.length);
  const regex = forms.length
    ? new RegExp("\\b(" + forms.map(escapeRe).join("|") + ")\\b", "gi")
    : /$a^/g; // matches nothing
  return { regex, lookup, byTerm };
}

function containmentPrefix(eid: string): string {
  const i = eid.lastIndexOf("__");
  return i === -1 ? "" : eid.slice(0, i);
}

export function resolveDef(entry: TermEntry, sectionEid: string): DefEntry | null {
  const c = entry.defs;
  if (c.length === 1) return c[0]!;
  const exact = c.find((d) => d.eid === sectionEid);
  if (exact) return exact;
  const qp = containmentPrefix(sectionEid);
  let best: DefEntry | null = null;
  let bestLen = -1;
  for (const d of c) {
    const dp = containmentPrefix(d.eid);
    if (dp && (qp === dp || qp.startsWith(dp + "__")) && dp.length > bestLen) {
      best = d;
      bestLen = dp.length;
    }
  }
  return best;
}

const SKIP_SELECTOR =
  "[data-term],a,.akn-ref,h1,h2,h3,h4,h5,h6,.akn-provision-heading,.akn-note-label,.akn-notetext,.akn-date,.akn-quantity,sup,sub";

export function highlightTerms(
  root: HTMLElement,
  m: Matcher,
  sectionEid: string,
  opts: { stoplist: ReadonlySet<string> },
): void {
  if (root.dataset.thDone === "1") return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const targets: Text[] = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const parent = (n as Text).parentElement;
    if (parent && !parent.closest(SKIP_SELECTOR)) targets.push(n as Text);
  }
  const seenStop = new Set<string>();
  for (const node of targets) {
    const text = node.nodeValue ?? "";
    m.regex.lastIndex = 0;
    const pieces: (string | HTMLElement)[] = [];
    let last = 0;
    for (let mm = m.regex.exec(text); mm; mm = m.regex.exec(text)) {
      const entry = m.lookup.get(mm[0].toLowerCase());
      if (!entry) continue;
      if (opts.stoplist.has(entry.term) && seenStop.has(entry.term)) continue;
      const def = resolveDef(entry, sectionEid);
      if (!def) continue;
      const span = document.createElement("span");
      span.dataset.term = entry.term;
      span.dataset.defEid = def.eid;
      span.textContent = mm[0];
      span.tabIndex = 0;
      span.setAttribute("role", "button");
      span.setAttribute("aria-label", `defined term: ${entry.display}`);
      pieces.push(text.slice(last, mm.index), span);
      last = mm.index + mm[0].length;
      if (opts.stoplist.has(entry.term)) seenStop.add(entry.term);
    }
    if (!pieces.length) continue;
    pieces.push(text.slice(last));
    const frag = document.createDocumentFragment();
    for (const p of pieces) frag.append(p);
    node.replaceWith(frag);
  }
  root.dataset.thDone = "1";
}

export function unhighlightTerms(root: HTMLElement): void {
  for (const span of Array.from(root.querySelectorAll("span[data-term][data-def-eid]"))) {
    span.replaceWith(document.createTextNode(span.textContent ?? ""));
  }
  root.normalize();
  delete root.dataset.thDone;
}
