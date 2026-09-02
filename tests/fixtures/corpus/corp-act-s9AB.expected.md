# Parity oracle: Corporations Act 2001, section 9AB

- Fixture: `corp-act-s9AB.xml`
- eId: `chapter-1__part-1.2__dvs-1__sec-9AB`
- Source of truth: `lex-au/repo/corpus/docx/corporations-act-2001-c147-vol1.docx`
  (Compilation No. 147, compilation date 1 July 2026 - matches the XML's
  `eng@2026-07-01` expression), `word/document.xml` visible paragraphs
  3029-3036 (post empty-paragraph drop, as produced by
  `tests/parity/extract_docx.py`). Text identical in the undated
  `corporations-act-2001-vol1.docx` for this provision.
- legislation.gov.au: `C2004A00818` (compilation `C2026C00339`) / Chapter 1,
  Part 1.2, Division 1, s 9AB.

## Why this fixture exists

Coverage of provision nesting and the embedded-numbering artifact. This section
is `section` -> `subsection` -> `paragraph` (two container levels), three of its
`<p>` elements and one paragraph carry the literal `\t(<num>)\t` tab-wrapped
number that Task 4's numbering normalisation has to strip, and its defined-term
intros are `<b><i>asset</i></b>` emphasis rather than `<term>` / `<ref>`. It has
no cross-references, tables, figures or authorial notes, so a failure here is a
nesting or numbering regression, nothing else.

## Authoritative text

**9AB  Meaning of asset**

(1) An **asset** (except in relation to a sub-fund of a CCIV) is property, or a
right, of any kind, and includes:

&nbsp;&nbsp;(a) any legal or equitable estate or interest (whether present or
future, vested or contingent, tangible or intangible, in real or personal
property) of any kind; and

&nbsp;&nbsp;(b) any chose in action; and

&nbsp;&nbsp;(c) any right, interest or claim of any kind including rights,
interests or claims in or in relation to property (whether arising under an
instrument or otherwise, and whether liquidated or unliquidated, certain or
contingent, accrued or accruing); and

&nbsp;&nbsp;(d) any CGT asset within the meaning of the *Income Tax Assessment
Act 1997*.

(2) The **assets** of a financial services licensee are all the licensee's
assets (as defined in subsection (1)), whether or not the assets are used in
connection with the licensee's Australian financial services licence.

(3) An **asset** of a sub-fund of a CCIV has the meaning given by section 1233H.

## Structure notes

- `<section eId="chapter-1__part-1.2__dvs-1__sec-9AB">` with `<num>9AB</num>` +
  `<heading>`. Three `<subsection>` children `(1)`-`(3)`. Subsection `(1)` is an
  intro `<p>` then four `<paragraph>` children `(a)`-`(d)`.
- Embedded-numbering artifact: the `<p>` of subsections `(1)`, `(2)`, `(3)` and
  of paragraph `(d)` each begin with a literal `\t(<n>)\t` that repeats that
  provision's own `<num>`. Paragraphs `(a)`, `(b)`, `(c)` do not. Task 4's
  `_strip_provision_num` removes the leading `(<n>)` token when it matches the
  provision number; the style map re-adds the marker.
- `**asset**` / `**assets**` are `<b><i>` emphasis (defined-term intros), not
  `<term>` or `<ref>` - 0 hover targets, same as the ITAA fixtures.
- `Income Tax Assessment Act 1997` is italic (`<i>`).
- "section 1233H" in subsection `(3)` is plain `<p>` text, not a `<ref>`.

## Known corpus/XML defects (parity failures to expect)

1. The docx text layer strips the hyphen from "sub-fund" ("sub-fund" ->
   "subfund"); the XML and legislation.gov.au keep it. Transcribed above with
   the hyphen (the AKN / legislation.gov.au form). The reader renders from the
   XML, so this is not a rendering-parity failure - noted only so a future
   regeneration from the docx text keeps the hyphen.
