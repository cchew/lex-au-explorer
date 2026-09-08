// Headless perf harness for the runtime defined-term highlighter.
//
// Substitute for the DevTools timing in the Task 12 brief (Step 4): measures
// buildMatcher() + a single first-section highlightTerms() pass on a corpus
// sized like a large Act's biggest Part.
//
// Run:
//   cd web && export PATH="$HOME/.nvm/versions/node/v22.6.0/bin:$PATH"
//   node --experimental-strip-types tests/perf/termHighlight.bench.mjs
//
// Node 22.6 strips the type-only syntax in ../../src/lib/termHighlight.ts on
// import; happy-dom supplies the DOM the highlighter's TreeWalker needs.

import { Window } from "happy-dom";
import { buildMatcher, highlightTerms, STOPLIST } from "../../src/lib/termHighlight.ts";

// --- deterministic RNG so the reported medians are reproducible -------------
let _seed = 0x2f6e2b1;
function rnd() {
  _seed = (_seed * 1664525 + 1013904223) >>> 0;
  return _seed / 0x100000000;
}
const pick = (arr) => arr[Math.floor(rnd() * arr.length)];
const median = (xs) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];

// --- synthetic vocabulary -------------------------------------------------
const HEADS = [
  "credit", "financial", "consumer", "designated", "eligible", "relevant",
  "approved", "registered", "responsible", "protected", "disclosable",
  "reportable", "notifiable", "assessable", "prescribed", "nominated",
  "controlling", "beneficial", "primary", "secondary", "external", "internal",
  "statutory", "regulatory", "compliance", "enforcement", "supervisory",
];
const MIDS = [
  "reporting", "assessment", "disclosure", "reporting-period", "holding",
  "monitoring", "screening", "reconciliation", "verification", "clearing",
  "settlement", "custody", "advisory", "lending", "servicing", "collection",
];
const TAILS = [
  "provider", "body", "entity", "arrangement", "instrument", "scheme",
  "facility", "agreement", "undertaking", "framework", "register", "statement",
  "declaration", "assessment", "obligation", "threshold", "mechanism",
  "determination", "notice", "record", "account", "transaction",
];

function makeTerm() {
  const n = 1 + Math.floor(rnd() * 3); // 1-3 words
  if (n === 1) return pick(TAILS);
  if (n === 2) return `${pick(HEADS)} ${pick(TAILS)}`;
  return `${pick(HEADS)} ${pick(MIDS)} ${pick(TAILS)}`;
}

const TERM_COUNT = 1200;
const terms = [];
const seenTerm = new Set();
while (terms.length < TERM_COUNT) {
  const term = makeTerm();
  if (seenTerm.has(term)) continue;
  seenTerm.add(term);
  terms.push({
    term,
    display: term,
    usedInBody: rnd() < 0.2, // ~20%
    defs: [{ text: `means ${term} within the meaning of this Act.`, eid: "part-1__sec-1" }],
  });
}
const bodyTerms = terms.filter((t) => t.usedInBody);

// --- synthetic large HTML: ~200 paragraphs salted with ~150 surface forms --
const FILLER =
  "A person to whom this section applies must, before the end of the relevant period, take all reasonable steps to ensure that the requirements of this Part are complied with in relation to the matter, and must keep a written record of the steps taken.";

const PARA_COUNT = 200;
const SALT_COUNT = 150;
const paras = Array.from({ length: PARA_COUNT }, () => FILLER);
for (let i = 0; i < SALT_COUNT; i++) {
  const p = Math.floor(rnd() * PARA_COUNT);
  const surface = pick(bodyTerms).term;
  paras[p] = paras[p].replace(
    "the matter",
    `the matter concerning a ${surface}`,
  );
}
const html = paras.map((t) => `<p>${t}</p>`).join("\n");

// --- DOM ---------------------------------------------------------------------
const window = new Window();
const document = window.document;
globalThis.document = document;
globalThis.NodeFilter = window.NodeFilter;

function freshRoot() {
  const el = document.createElement("div");
  el.className = "section-html";
  el.innerHTML = html;
  return el;
}

// --- warm-up ---------------------------------------------------------------
for (let i = 0; i < 2; i++) {
  const m = buildMatcher(bodyTerms);
  highlightTerms(freshRoot(), m, "part-1__sec-1", { stoplist: STOPLIST });
}

// --- measure: buildMatcher, median of 5 ----------------------------------
const buildTimes = [];
for (let i = 0; i < 5; i++) {
  const t0 = performance.now();
  buildMatcher(bodyTerms);
  buildTimes.push(performance.now() - t0);
}

// --- measure: highlightTerms first-section pass, median of 5 ------------
const matcher = buildMatcher(bodyTerms);
const hlTimes = [];
for (let i = 0; i < 5; i++) {
  const root = freshRoot();
  const t0 = performance.now();
  highlightTerms(root, matcher, "part-1__sec-1", { stoplist: STOPLIST });
  hlTimes.push(performance.now() - t0);
}

const buildMed = median(buildTimes);
const hlMed = median(hlTimes);
const combined = buildMed + hlMed;

// --- report --------------------------------------------------------------
const sampleRoot = freshRoot();
highlightTerms(sampleRoot, matcher, "part-1__sec-1", { stoplist: STOPLIST });
const wrapped = sampleRoot.querySelectorAll("span[data-term][data-def-eid]").length;

console.log("termHighlight headless perf");
console.log("--------------------------------------------------");
console.log(`terms total ............ ${terms.length}`);
console.log(`terms usedInBody ....... ${bodyTerms.length} (matcher input)`);
console.log(`paragraphs ............. ${PARA_COUNT}`);
console.log(`surface forms salted ... ${SALT_COUNT}`);
console.log(`spans wrapped .......... ${wrapped}`);
console.log("--------------------------------------------------");
console.log(`buildMatcher   median (n=5) ... ${buildMed.toFixed(3)} ms`);
console.log(`highlightTerms median (n=5) ... ${hlMed.toFixed(3)} ms`);
console.log(`combined ...................... ${combined.toFixed(3)} ms`);
console.log(`target ....................... < ~50 ms combined`);
console.log(`verdict ...................... ${combined < 50 ? "PASS" : "FAIL - consider Aho-Corasick fallback"}`);
