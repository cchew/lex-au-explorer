# Parity oracle: Corporations Act 2001, Schedule 2 clause 70-20

("Schedule 2" on legislation.gov.au is the Insolvency Practice Schedule
(Corporations); the corpus eIds it as `schedule-1`.)

- Fixture: `sched-clause.xml`
- eId: `schedule-1__clause-70-20`
- Source of truth: `lex-au/repo/corpus/docx/corporations-act-2001-c147-vol7.docx`
  (Compilation No. 147, compilation date 1 July 2026 - matches the XML's
  `eng@2026-07-01` expression), `word/document.xml` paragraphs 1464-1473. Text
  identical in the undated `corporations-act-2001-vol7.docx`.
- legislation.gov.au: `C2004A00818` (compilation `C2026C00339`) / Schedule 2 (Insolvency
  Practice Schedule (Corporations)), Division 70, clause 70-20.
- **Schedule-number mismatch:** legislation.gov.au and the docx both call this
  "Schedule 2"; the corpus eIds it `schedule-1` (positional - it is the first
  `<attachment>`). A resolver that maps "Schedule N" text to a `schedule-N` eId
  will be off by one here.

## Authoritative text

**70-20  Audit of administration books - on order of the Court**

(1) The Court may order that an audit of the books referred to in section 70-5
(annual administration return), 70-6 (end of administration return) or 70-10
(administration books) be conducted by a registered company auditor.

(2) The order may be made on application of:

&nbsp;&nbsp;(a) any person with a financial interest in the external
administration of the company; or

&nbsp;&nbsp;(b) an officer of the company.

(3) Paragraph (2)(b) has effect despite section 198G.

> Note: Section 198G deals with powers of officers etc. while a company under
> external administration.

(4) The Court may make such orders in relation to the audit as it thinks fit,
including:

&nbsp;&nbsp;(a) the preparation and provision of a report on the audit; and

&nbsp;&nbsp;(b) orders as to the costs of the audit.

## Structure notes

- Provision unit is `<hcontainer name="clause" eId="schedule-1__clause-70-20">`
  with `<num>70-20</num>` + `<heading>`. It is **not** a `<section>`.
- Sub-units are `<hcontainer name="subclause" eId="...__subclause-1..4">` with
  `<num>1..4</num>`.
- Paragraphs `(a)`/`(b)` are `<paragraph>` elements that are **siblings** of the
  subclauses, not children. After subclause 2 there is `para-a` + `para-b`; after
  subclause 4 there is another `para-a` + `para-b` - so the eIds
  `schedule-1__clause-70-20__para-a` and `__para-b` **each appear twice** in the
  subtree. Any eId->node map keyed on these collides.
- The Note is a bare `<content><p>Note: ...</p>` sibling (after subclause 3),
  **not** an `<authorialNote>`. Schedule notes in this corpus are inline `<p>`
  text starting with `Note:`.
- The schedule wrapper kept in the fixture is
  `<hcontainer name="schedule" eId="schedule-1">` with its `<heading>Insolvency
  Practice Schedule (Corporations)</heading>` and a `<content>` note
  `See <ref href="#sec-600K">section 600K</ref>.`, placed inside
  `<attachments>/<attachment>` (its real position in the source).

## Known corpus/XML defects (parity failures to expect)

1. **The current renderer emits nothing for this fixture.** `build.bundle`
   iterates `root.iter('{akn}section')` only; `build_sections` returns `{}` and
   `build_toc` returns `[]`. Every schedule that uses `hcontainer name="clause"`
   (195 clause containers in this Act alone; ~hundreds of Acts corpus-wide) is
   invisible to the reader today.
2. **Cross-reference truncated at the hyphen.** "section 70-5 ... 70-6 ... 70-10"
   is marked `<ref href="#sec-70">section 70</ref>-5 ...` - only "section 70" is
   inside the `<ref>`, "-5" / "70-6" / "70-10" are tail text. And `#sec-70`
   would resolve to Act section 70, whereas 70-5/70-6/70-10 are clauses of this
   Schedule (`schedule-1__clause-70-5` etc.). Wrong target family entirely.
3. `<ref href="#sec-198G">` is a bare unscoped href; real eId `...__sec-198G`.
4. docx text layer strips hyphens from clause numbers ("70-20" -> "7020",
   "70-5" -> "705"); the XML keeps them. Transcribed above with hyphens.
