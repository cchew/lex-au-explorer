# Parity oracle: Age Discrimination Act 2004, Schedule 1 (table-only)

- Fixture: `sched-table.xml`
- eId: `schedule-1` (whole-schedule synthetic key -- no clause present anywhere
  in this schedule)
- Source of truth: `lex-au/repo/corpus/docx/age-discrimination-act-2004-c57-vol0.docx`
  (Compilation No. 57; `eng@2026-07-01` expression matches the XML), `word/document.xml`.
  Text confirmed identical (grep on the flattened body text) in the undated
  `age-discrimination-act-2004-vol0.docx`.
- legislation.gov.au: `C2004A01302`, compilation `C2026C00266` (dated 1 July
  2026, matching the XML's `eng@2026-07-01` expression) / Schedule 1 (Laws for
  which an exemption is provided by subsection 39(1)).
- Real corpus file: `lex-au/repo/corpus/xml/age-discrimination-act-2004.xml`,
  `schedule-1` has exactly 2 direct children (`<heading>`, `<table>`) and
  **zero** `<hcontainer name="clause">` anywhere -- confirmed directly by
  listing the schedule's children. The real `<table>` has 56 `<tr>` rows; this
  fixture keeps the first 6 (2 header rows + 4 item rows: items 3, 4, 5, 6).

## Authoritative text (first 6 kept rows)

| Item | Law |
| --- | --- |
| *(title row, repeated across both `<td>`s)* | Laws for which an exemption is provided by subsection 39(1) |
| Item | Law |
| 3 | Aboriginal Land and Waters (Jervis Bay Territory) Act 1986 |
| 4 | Aboriginal Land (Lake Condah and Framlingham Forest) Act 1987 |
| 5 | Aboriginal Land Rights (Northern Territory) Act 1976 |
| 6 | Administrative Review Tribunal Act 2024 |

## Structure notes

- The whole schedule is one `<table>` element: the first `<tr>` is a
  spanning title row (both `<td>`s repeat the schedule heading text, an AKN
  rendering of a merged/spanned header cell), the second `<tr>` is the
  "Item" / "Law" column-header row, then one `<tr>` per item.
- Per `build/parse.py`'s documented corpus reality, no `<td>` in the corpus has
  element children -- every cell is text-only, so cell parsing never needs to
  recurse into inline markup for this fixture.
- The schedule has no `<content>` note and no other direct child besides
  `<heading>` and the single `<table>` -- the simplest possible synthetic-unit
  shape (a single-element run).

## Task 3 behaviour under test

- No `<hcontainer name="clause">` exists in this schedule, so the single
  `<table>` child is the entire run for this schedule: deepcopied into a
  detached `<hcontainer>`, parsed, and rendered as one bundle entry keyed by
  the bare `schedule-1` eId (`had_clause=False`, `block_n=0`).
- The rendered HTML must contain `<table` and at least 5 `<tr` (6 rows kept,
  the test asserts `>= 5` to tolerate rendering-level row filtering, e.g. if a
  future task drops the spanning title row).
- `build_toc`'s schedule node for this fixture has exactly one child: `{"eid":
  "schedule-1", "heading": "", "children": []}`.
