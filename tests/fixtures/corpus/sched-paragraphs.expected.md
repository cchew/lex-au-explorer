# Parity oracle: ADJR Act 1977, Schedule 1 (paragraph-only, no clause)

- Fixture: `sched-paragraphs.xml`
- eId: `schedule-1` (whole-schedule/preamble synthetic key -- no clause present
  anywhere in this schedule, so all 10 kept `<paragraph>` items key under the
  bare schedule eId per Task 3's `had_clause`-false rule)
- Source of truth: `lex-au/repo/corpus/docx/administrative-decisions-(judicial-review)-act-1977-c132-vol0.docx`
  (Compilation No. 132; `eng@2026-07-01` expression matches the XML), `word/document.xml`.
  Text confirmed identical (grep on the flattened body text) in the undated
  `administrative-decisions-(judicial-review)-act-1977-vol0.docx`.
- legislation.gov.au: series `C2004A01697` (Administrative Decisions (Judicial
  Review) Act 1977), current compilation dated 27 August 2026 / Schedule 1
  (Classes of decisions that are not decisions to which this Act applies).
- Real corpus file: `lex-au/repo/corpus/xml/administrative-decisions-(judicial-review)-act-1977.xml`,
  `schedule-1` has 87 direct children excluding none (`<heading>` x1, `<content>`
  x1, `<paragraph>` x85) and **zero** `<hcontainer name="clause">` anywhere in
  its subtree -- confirmed by `sched.findall('.//{akn}hcontainer[@name="clause"]')`
  returning an empty list. This fixture keeps the `<heading>` and the first 10
  `<paragraph>` items (of 85); the leading `<content>` block (a long list of
  excluded Acts, ending in three `Note:` paragraphs) is dropped from the
  fixture to keep it focused on the paragraph-run case.

## Authoritative text (first 10 kept paragraphs)

(a) decisions under the *Fair Work Act 2009*, the *Fair Work (Registered
Organisations) Act 2009*, the *Fair Work (Transitional Provisions and
Consequential Amendments) Act 2009*, the *Workplace Relations Act 1996*, the
*Building and Construction Industry Improvement Act 2005* or the *Fair Work
(Building Industry) Act 2012*;

(b) the following decisions under the *Australian Charities and
Not-for-profits Commission Act 2012*:

&nbsp;&nbsp;(i) administrative decisions (within the meaning of that Act);

&nbsp;&nbsp;(ii) objection decisions (within the meaning of that Act);

&nbsp;&nbsp;(iii) extension of time refusal decisions (within the meaning of
that Act);

(c) decisions under the *Coal Industry Act 1946*, other than decisions of the
Joint Coal Board;

(d) decisions under any of the following Acts:

&nbsp;&nbsp;(daa) decisions of the Minister administering the *Australian
Security Intelligence Organisation Act 1979* under section 58A of the
*Telecommunications Act 1997*;

&nbsp;&nbsp;(daaa) decisions of the Minister administering the *Australian
Security Intelligence Organisation Act 1979* under clause 57A or 72A of
Schedule 3A to the *Telecommunications Act 1997*;

&nbsp;&nbsp;(daaaa) decisions under Part 15 of the *Telecommunications Act
1997*;

## Structure notes

- Provision unit is `<paragraph eId="schedule-1__para-a">` etc: `<paragraph>`
  with `<num>` + `<content><p>...</p></content>`, a **sibling** of every other
  paragraph directly under the schedule `<hcontainer>` -- there is no
  `<hcontainer name="clause">` wrapper at all in this schedule.
- `<num>` values are letters/roman numerals (`a`, `b`, `i`, `ii`, `iii`, `c`,
  `d`, `daa`, `daaa`, `daaaa`), not sequential integers; sub-items (`i`-`iii`
  under `(b)`, `daa`-`daaaa` under `(d)`) are still flat siblings in the XML,
  not nested under their parent paragraph -- the source relies on the
  identifier scheme alone to convey the outline depth.
- `<ref href="#sec-58A">` and `<ref href="#part-1">Part 15</ref>` are bare
  unscoped hrefs pointing at Act-level ids (`#sec-58A`, `#part-1`) that don't
  exist inside this schedule; both are expected to resolve `unresolved` or
  `ambiguous` (out of scope for this task -- Task 3 does not add schedule-aware
  ref resolution).
- The `<ref href="#part-1">Part 15</ref>` markup mirrors the sched-clause
  fixture's truncated-ref defect: only "Part 1" is inside the `<ref>`, "5" is
  tail text, so the visible text still reads "Part 15" but the href targets the
  wrong node family.

## Task 3 behaviour under test

- No `<hcontainer name="clause">` exists in this schedule, so the entire kept
  run of 10 `<paragraph>` elements is one synthetic block, deepcopied into a
  detached `<hcontainer>` and parsed/rendered as a single bundle entry keyed by
  the bare `schedule-1` eId (not `schedule-1__block-0`), per the
  `had_clause or block_n > 0` rule with `had_clause=False` and `block_n=0`.
- `build_toc`'s schedule node for this fixture has **no** children: the single
  whole-schedule run keys under the bare `schedule-1` eId, which is identical to
  the schedule node's own eId, so that self-referential child row is suppressed
  (F2, final-review wave). The content is still bundled under
  `sections["schedule-1"]`; the reader's `flattenLeafEids` falls back to
  `[node.eid]` for a childless node, so it still renders.
