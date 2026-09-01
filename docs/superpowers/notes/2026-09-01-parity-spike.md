# Parity spike: AKN eId / `<ref href>` scheme reality (Task 1)

Date: 2026-09-01
Feeds: Task 3 (ref/definition resolver), Task 6 (`--corpus-images`, schedule
rendering), Task 9 (parity oracle).

Corpus examined: `../lex-au/repo/corpus/xml/` (3,076 AKN 3.0 XML files),
compilation expressions `eng@2026-07-01`. Word oracle:
`../lex-au/repo/corpus/docx/*-c147-*.docx` / `*-c266-*.docx` (compilation date
1 July 2026, matches the XML).

Fixtures committed under `tests/fixtures/corpus/`:

| fixture | Act | eId | why |
|---|---|---|---|
| `corp-act-s3.xml` | Corporations Act 2001 (`C2004A00818`, comp `C2026C00339`) | `chapter-1__part-1.1__sec-3` | subsections/paragraphs, authorial note, scrambled `#sec-2H` cross-ref, Constitution refs (`#sec-51`, `#sec-122`) |
| `corp-act-s3-sbg.xml` | Corporations Act 2001 | `chapter-1__part-1.5__sec-3` | Small Business Guide "Setting up a new company"; bare `sec-3` collides with the row above (blocker B1) |
| `itaa97-rate-table.xml` | Income Tax Assessment Act 1997 (`C2004A05138`, comp `C2026C00324`) | `chapter-1__part-1-3__dvs-4__sec-4-15` | real multi-row `<table>` (`<tr>/<th>/<td>`), `<ref>`+`<b><i>` in surrounding prose, `<figure><img>` |
| `itaa97-figure.xml` | Income Tax Assessment Act 1997 | `chapter-1__part-1-3__dvs-4__sec-4-10` | method-statement section with `<figure><img>`; dense ref mix incl. `#term-*`, hyphen-truncated `#sec-4`, `#dvs-63`, scrambled ITAA-1936 cross-refs |
| `sched-clause.xml` | Corporations Act 2001 | `schedule-1__clause-70-20` | Schedule provision built from `hcontainer name="clause"` / `"subclause"`; inline `Note:`; duplicate `para-a`/`para-b` eIds |

Each fixture keeps the Act's full `<identification>` (so `FRBRWork/FRBRuri` ->
`frbr_uri` resolves - verified against `build.metadata._parse_frbr_uri`) plus a
`<references>` block filtered to only the TLC entries cited in the subtree
(4 of 5 fixtures have none; `itaa97-figure` keeps `term-financial-year`).
`<lifecycle>` and `<temporalData>` are dropped (12-40 KB of amendment-event
metadata that nothing in `build/` or `lexaugraph` reads).

---

## A. `<ref href>` family table

### A.1 The five fixtures (exact, whole subtree)

| href | family | count | resolves? |
|---|---|---|---|
| `#sec-51` | `sec-<n>` | 4 (corp-s3) | **no** - the Constitution, no eId in the Act |
| `#sec-122` | `sec-<n>` | 3 (corp-s3) | **no** - the Constitution |
| `#sec-2H` | `sec-<n>` | 1 (corp-s3) | **no** - no `__sec-2H` eId anywhere in the Act; it is really Acts Interpretation Act 1901 s 2H, mis-emitted (see D) |
| `#sec-120` | `sec-<n>` | 1 (corp-s3-sbg) | yes, but ambiguous - suffix-matches `__sec-120` |
| `#dvs-6` `#dvs-8` `#dvs-36` | `dvs-<n>` | 1 each (rate-table) | ambiguous - many Divisions numbered 6/8/36 |
| `#term-financial-year` | `term-<slug>` | 4 (figure) | via graph, after `term-financial-year` -> `"financial year"` |
| `#sec-4` | `sec-<n>` | 1 (figure) | **wrong** - display text is "section 4-15"; href truncated at the hyphen (see B) |
| `#sec-13` | `sec-<n>` | 1 (figure) | **wrong** - "section 13-1" |
| `#sec-9` | `sec-<n>` | 1 (figure) | **wrong** - "section 9-5" |
| `#sec-18` `#sec-18A` | `sec-<n>` | 1 each (figure) | **no** - ITAA 1936, scrambled cross-ref |
| `#dvs-63` | `dvs-<n>` | 1 (figure) | ambiguous |
| `#sec-70` | `sec-<n>` | 1 (sched-clause) | **wrong** - display "section 70-5"; target is `schedule-1__clause-70-5`, a clause, not s 70 |
| `#sec-198G` | `sec-<n>` | 1 (sched-clause) | yes - `__sec-198G` |
| `#sec-600K` | `sec-<n>` | 1 (sched wrapper note) | yes - `__sec-600K` |

Fixture family totals: `sec-<n>` 17, `dvs-<n>` 4, `term-<slug>` 4. No `term-*`
`<term refersTo>` in any fixture subtree (ITAA marks term *usages* with
`<ref href="#term-...">`, not `<term>`; see C).

### A.2 200-ref sample + full-Act counts

`corporations-act-2001.xml` - 7,004 body `<ref>`:

| family | first-200 sample | full Act | notes |
|---|---:|---:|---|
| `sec-<n>` | 117 | 4,434 | bare, chapter/part-unscoped. e.g. `#sec-51`, `#sec-923A`, `#sec-2H` |
| `part-<n>` arabic | 54 | 1,315 | `#part-9`, `#part-2D`, `#part-5B`. Real Part eIds are dot-scoped: `chapter-2J__part-2J.1`. `#part-2D` suffix-matches **nothing** (`__part-2D.1`, never `__part-2D`) |
| `dvs-<n>` | 20 | 1,150 | `#dvs-2`, `#dvs-11AA`. Real: `chapter-X__part-X.Y__dvs-N` |
| `empty` (`href=""`) | 8 | 52 | |
| `part-<roman>` | 1 | 30 | `#part-VII` (14), `#part-I` (8), `#part-IV` (3)... mixed with the arabic set, same Act |
| `sec-<n>__subsec-<m>` | 0 | 23 | `#sec-923A__subsec-5` - suffix-matches `__sec-923A__subsec-5` |

`income-tax-assessment-act-1997.xml` - 19,274 body `<ref>`:

| family | first-200 sample | full Act | notes |
|---|---:|---:|---|
| `term-<slug>` | 99 | 11,704 | `#term-financial-year`, `#term-add-on-insurance-product`. Hyphenated slug (see C) |
| `sec-<n>` | 56 | 5,013 | **hyphen-truncated**: "section 4-15" -> `#sec-4`, "Subdivision 165-B" context -> `#sec-165`, "section 950-100" -> `#sec-950`. Zero `#sec-N-M` hrefs exist anywhere (see B) |
| `dvs-<n>` | 32 | 1,696 | `#dvs-4`, `#dvs-6`, `#dvs-36` |
| `empty` | 2 | 367 | |
| `part-<roman>` | 7 | 287 | `#part-II`, `#part-IVC`. Many point at ITAA **1936**, rendered as bare local hrefs |
| `part-<n>` arabic | 4 | 192 | `#part-4`, `#part-2`. Real ITAA Part eIds: `chapter-1__part-1-3` (hyphen), so `#part-4` doesn't suffix-match `part-4-1` either |
| `part-other` | 0 | 7 | `#part-B` |
| `sec-<n>__subsec-<m>` | 0 | 8 | `#sec-6__subsec-1` |

### A.3 Families the plan lists that DO NOT occur

Across both sampled Acts (26k refs): **zero** `chapter-<n>` / `chp-<n>`, **zero**
`sch-*`, **zero** `subdvs-*`, **zero** non-`#` hrefs. Task 3 rules for those
families will never fire on this corpus. (Schedule cross-references, where they
exist, come through as `#sec-<n>` - see `sched-clause` `#sec-70`.)

### A.4 Consequences for the Task 3 resolver

1. **Bare `#sec-<n>` is the dominant family and is ambiguous by construction.**
   Corp Act: 11 section numbers map to >1 eId; every Small Business Guide item
   (`chapter-1__part-1.5__sec-1..N`) collides with a real provision of the same
   number. Suffix-match on `__sec-3` returns 2 hits; there is no
   disambiguator in the href. `corp-act-s3.xml` + `corp-act-s3-sbg.xml` are the
   committed proof.
2. **ITAA `#sec-<n>` is not just ambiguous, it is lossy.** The hyphenated part
   of the number (`4-15` -> `4`) is discarded before the href is written. The
   full number survives only as the ref's display text. A resolver that wants
   ITAA section links at all must parse the visible ref text, not the href.
3. **`#part-*` never suffix-matches a real Part eId** in either Act (dot-scoping
   in Corp, hyphen-scoping in ITAA, plus a roman/arabic split within each Act).
   Treat `#part-*` as best-effort/unresolved unless a number-normalising lookup
   table is built per Act.
4. **`href=""`** (419 across the two Acts) must be handled as "no target",
   not crashed on.
5. `#term-<slug>` is ITAA-only for usages; Corp Act emits **no** term-usage
   hrefs at all (see C). Any "hover a defined term" feature is ITAA-shaped now.

---

## B. Figure images: `corpus/images/` does not exist

Confirmed: `../lex-au/repo/corpus/` contains `.cache/ data/ docx/ reports/
xml/ index.json` and **no `images/` directory**. No `.png` / `.jpg` / `.svg`
anywhere in the lex-au repo (outside `.venv`).

`<img>` scheme (1,819 `<img>` elements corpus-wide, all `<figure><img>`):

    src = "corpus/images/{act-slug}-fig-{n}.png"      # repo-relative, always .png
    alt = ""                                          # empty on all 1,819

Examples in the fixtures: `corpus/images/income-tax-assessment-act-1997-fig-2.png`
(`itaa97-figure`), `...-fig-3.png` (`itaa97-rate-table`). Top slugs by count:
income-tax-assessment-act-1997 (417), social-security-act (128),
veterans'-entitlements-act (92), superannuation-act (62).

Consequence: every figure renders as a placeholder - the target file is absent
and `alt=""` gives no fallback text. Task 6's `--corpus-images` default should
point at `<corpus-dir>/images/` (sibling of `xml/`), accept that it is normally
missing, and the renderer should emit a labelled placeholder (e.g. "Figure -
image not available") rather than a broken `<img>`.

---

## C. Defined-term markup is inconsistent between Acts

| | `<term refersTo="#term-...">` (definition sites) | `<ref href="#term-...">` (usage links) |
|---|---:|---:|
| ITAA 1997 body | 1,515 | 11,704 |
| Corporations Act body | 748 | **0** |

- ITAA: a *usage* of a defined term is `<ref href="#term-financial-year">financial
  year</ref>` (asterisk dropped, link added) - but not consistently: in
  `itaa97-figure`, "financial year" is linked 4x while "*tax offsets" in the same
  section keeps a literal `*` and no link.
- Corp Act: only definition sites are marked (`<term>`); usages are plain text.
- `build/bundle.py::_render_inline` wraps `<term>` -> `<span data-term>` and does
  nothing special with `<ref href="#term-...">`. Verified: `build_sections` on
  `itaa97-figure.xml` yields **0** `data-term` spans despite 4 term usages.
- Slug vs term name: AKN slug is hyphenated (`term-financial-year`); lexaugraph's
  `DefinedTermNode.node_id` builds its slug with underscores
  (`...#term_financial_year`). Neither is the resolver's input - see D. Task 3
  must convert `#term-<slug>` -> term name by stripping `term-` and replacing
  `-` with spaces, which is lossy for terms that genuinely contain a hyphen.

---

## D. lex-au-graph term / definition resolver API (real names)

Installed editable as `lexaugraph` (pyproject: `lex-au-graph @ file:...`).
Source: `../lex-au-graph/repo/src/lexaugraph/resolver.py`.

```
from lexaugraph.graph import LexAuGraph
from lexaugraph.resolver import DefinitionResolver

resolver = DefinitionResolver(LexAuGraph.load(graph_path))   # centrality arg optional

result = resolver.resolve_definition(
    term: str,                        # the term NAME, lowercased/stripped internally
                                      # -- NOT a "term-<slug>" and NOT an eId
    act_frbr_uri: str,                # e.g. "/akn/au/act/1997/38"
    section_eid: Optional[str] = None # the requesting section, for Part/Division
                                      # scoping of ambiguous terms
) -> Optional[DefinitionResult]
```

`DefinitionResult` (`lexaugraph.models`, a dataclass):

```
term: str
display_term: str
definition_text: str
act_frbr_uri: str
section_eid: str        # <-- the DEFINING section's eId. This is the plan's
                        #     placeholder "defining_section".
act_title: str
```

- The plan's placeholder name `defining_section` == `resolve_definition(...).section_eid`.
- Ambiguity contract: `_select_candidate` returns `None` (whole call returns
  `None`) when >1 candidate definition exists and none is enclosed by the
  requesting section's Part/Division prefix. Callers must treat `None` as
  "unresolved", render plain text. `build/definitions.py::resolve_section_definitions`
  already consumes exactly this.
- Related methods on the same class, for Task 3's cross-reference panel:
  `cross_references(eid, act_frbr_uri)`, `impacted_by(eid, act_frbr_uri,
  max_hops=3)`, `find_all_definitions(term)`, `get_act_terms(act_frbr_uri)`,
  `entities_in_section(eid, act_frbr_uri)`.
- There is **no** slug->name or href->eid helper anywhere in `lexaugraph`.
  Task 3 owns that mapping.

---

## E. Parity-oracle caveats (for Task 9)

- The oracle is the Word compilation text (`word/document.xml` paragraph runs),
  transcribed per fixture into `<name>.expected.md`. legislation.gov.au HTML is
  JavaScript-rendered and unusable via fetch.
- The Word text layer **strips hyphens from provision numbers** ("4-15" -> "415",
  "165-B" -> "165B", "70-20" -> "7020"). The `.expected.md` files use the
  hyphenated AKN form; note the divergence when diffing against docx directly.
- Tables and figures are flattened in the docx text layer (no table grid, image
  is an empty paragraph). The `.expected.md` reconstructs the table as a grid
  from the cell run order.
- The undated `*-vol*.docx` set is an older compilation (May 2026 / Dec 2025);
  the `*-c147-*` / `*-c266-*` set matches the XML (1 July 2026). For all five
  fixture provisions the two sets carry identical text, but Task 9 should read
  the compilation-matched set.

---

## F. Rendering defects surfaced while building the fixtures (feeds Tasks 3/6)

1. **`<table>` content is 100% dropped.** `build.bundle._render_node` treats
   `<table>` as unknown and recurses; `<tr>/<th>/<td>` are not container tags and
   `_render_content` only reads `<p>`; `<td>` has no element children, so the
   cell text is never emitted. `itaa97-rate-table` renders ~1.2 KB with none of
   the 7 rows. Corpus-wide: every `<td>` in all 3,076 files is text-only, so a
   `<td>`-recursion approach cannot work - the renderer must handle `<tr>/<th>/
   <td>` explicitly.
2. **Schedule provisions render as nothing.** `build_sections` /`build_toc`
   iterate `root.iter('{akn}section')` only. `hcontainer name="schedule" |
   "clause" | "subclause"` are invisible. `build_sections(sched-clause.xml)` ==
   `{}`. Corp Act alone has 195 `hcontainer name="clause"`.
3. **Duplicate eIds within a provision.** In `sched-clause`,
   `schedule-1__clause-70-20__para-a` and `__para-b` each appear twice
   (paragraphs are siblings of the subclauses, re-numbered per subclause). Any
   `dict[eid] -> node` collapses them.
4. **Schedule number is positional, not the Act's.** Corpus eId `schedule-1`
   == legislation.gov.au "Schedule 2" (Insolvency Practice Schedule
   (Corporations)). "Schedule N" text will not map to `schedule-N`.
5. **Systematic cross-Act cross-reference scramble.** Pattern
   `See <i>{Other Act}</i>.<ref href="#sec-N">section N</ref> of the ` - the
   phrase "section N of the" is cut from before the italicised Act name and
   re-appended after the full stop. Seen in `corp-act-s3` subsec (2)(b) and
   `itaa97-figure` notes 10/11. Authoritative order: "section N of the
   {Other Act}". Any resolver keying on the trailing `<ref>` links the wrong
   thing and leaves a dangling "of the" in the text.
6. **`num` prefix duplication already half-handled.** `_container_num_prefix`
   skips re-adding `(2)` when the first `<p>` already starts with `(2)` -
   which ITAA source text frequently does (`<p>\t(2)\tYour income tax ...`).
   `itaa97-figure` exercises this.
