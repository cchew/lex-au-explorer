# Parity oracle: A New Tax System (Family Assistance) Act 1999, Schedule 1

- Fixture: `sched-dup-eid.xml`
- eIds: `schedule-1__clause-30` (occurs twice in the real corpus file; the
  second occurrence is disambiguated to `schedule-1__clause-30~2` at bundle
  time, see `build/bundle.py::_add_entry`)
- Source of truth: `lex-au/repo/corpus/xml/a-new-tax-system-(family-assistance)-act-1999.xml`,
  `schedule-1` ("Family tax benefit rate calculator"). Confirmed programmatically
  (`ET.parse` + `collections.Counter` over the schedule's direct `<hcontainer
  name="clause">` children): 107 direct clauses, exactly one duplicate eId
  (`schedule-1__clause-30`, count 2), at document positions 63 and 96 of 107.

## What the real corpus actually contains (verified 2026-09-05)

Position 63 (`heading` "Standard rate"): a short clause with one `<content>`
paragraph and a 5-row rate table (2 header rows + 2 data rows for "youngest
FTB child is under 5" / "5 or over").

Position 96 (`heading` -- verbatim from the source, itself a symptom of messy
upstream markup: "June 2000 rate, in relation to an individual, means the
amount worked out according to subclause (6)."): a large definitions clause
(44 direct children in the real file) whose own body repeats `para-a`/`para-b`
etc. **internally**, a second, orthogonal collision axis -- see
"Known corpus/XML defects" below and `sched-clause.xml`'s oracle for the same
phenomenon.

## Fixture trim

Kept, in original document order: clause-30 (position 63, kept whole -- it is
short), clause-31 (position 64, trimmed to `<num>`/`<heading>`/subclause-1/
para-a/para-b/one closing `<content>`, dropping subclause-2 onward), clause-39
(position 95, already minimal in the source: `<num>`/`<heading>`/one
subclause), clause-30 (position 96, trimmed to `<num>`/`<heading>`/`<content>`/
one `<subclause eId="schedule-1__clause-30__subclause-2">` -- enough to give
the disambiguated unit one real nested provision id for the id-reachability
test, while dropping its own many repeated para-a/b children to keep this
fixture's one collision axis -- the top-level `schedule-1__clause-30`
duplicate -- unambiguous).

Dropped: all other 103 clauses; `<meta>`'s `<references>`, `<lifecycle>`,
`<temporalData>` (kept `<identification>` in full).

## Task 4 behaviour under test

- `build_sections` must keep **both** clause-30 entries: the first under the
  bare key `schedule-1__clause-30`, the second under
  `schedule-1__clause-30~2` (`_EID_DISAMBIG = "~"`, confirmed unused anywhere
  in the live corpus's `eId` attributes).
- `counts["disambiguated_eids"] == 1` -- exactly one collision in this
  fixture.
- `build_toc`'s schedule-1 children must list the same four keys, in the same
  order, that `sections` actually holds.
- The disambiguated unit's own nested provision (`...__subclause-2`) keeps
  its own id unaffected; the two clause-30 html strings never cross-
  contaminate ("Standard rate" only in the first, "has the same meaning as"
  only in the second).

## Known corpus/XML defects (parity failures to expect)

1. **Two distinct `<clause>` elements share one eId.** This is the collision
   Task 4 exists to fix: the converter that flattens schedule Part/Division
   numbering into a flat list of `<clause>` siblings does not renumber a
   clause number that repeats across what were originally different Parts
   of Schedule 1. Filed upstream: `../lex-au/repo/FUTURE.md`.
2. **The kept clause-30 (position 96)'s own `<heading>` text is not a title.**
   It reads as a stray definitions fragment ("June 2000 rate, in relation to
   an individual, means the amount worked out according to subclause (6).")
   -- transcribed verbatim from the source; not a fixture-construction error.
3. **Internal para-a/para-b repetition inside one clause** (not disambiguated
   by this fixture's trim, which deliberately drops those repeats from the
   kept clause-30 to isolate the top-level collision) is a second, separate
   collision axis -- see `sched-clause.xml`'s oracle, defect 2, and Task 4's
   report for why it is out of `build/bundle.py`'s reach.
