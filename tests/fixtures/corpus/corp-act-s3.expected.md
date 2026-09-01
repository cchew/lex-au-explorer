# Parity oracle: Corporations Act 2001, section 3

- Fixture: `corp-act-s3.xml`
- eId: `chapter-1__part-1.1__sec-3`
- Source of truth: `lex-au/repo/corpus/docx/corporations-act-2001-c147-vol1.docx`
  (Compilation No. 147, compilation date 1 July 2026 - matches the XML's
  `eng@2026-07-01` expression), `word/document.xml` paragraphs 757-771. Text is
  identical in the undated `corporations-act-2001-vol1.docx` for this provision.
- legislation.gov.au: `C2004A00818` (compilation `C2026C00339`) / Chapter 1, Part 1.1, s 3.

## Authoritative text

**3  Constitutional basis for this Act**

(1) The operation of this Act in the referring States is based on:

&nbsp;&nbsp;(a) the legislative powers that the Commonwealth Parliament has under
section 51 of the Constitution (other than paragraph 51(xxxvii)); and

&nbsp;&nbsp;(b) the legislative powers that the Commonwealth Parliament has in
respect of matters to which this Act relates because those matters are referred
to it by the Parliaments of the referring States under paragraph 51(xxxvii) of
the Constitution.

> Note: The State referrals fully supplement the Commonwealth Parliament's other
> powers by referring the matters to the Commonwealth Parliament to the extent to
> which they are not otherwise included in the legislative powers of the
> Commonwealth Parliament.

(2) The operation of this Act in the Territories is based on:

&nbsp;&nbsp;(a) the legislative powers that the Commonwealth Parliament has under
section 122 of the Constitution to make laws for the government of those
Territories; and

&nbsp;&nbsp;(b) the legislative powers that the Commonwealth Parliament has under
section 51 of the Constitution.

Despite section 2H of the *Acts Interpretation Act 1901*, this Act as applying in
those Territories is a law of the Commonwealth.

(3) The operation of this Act outside Australia is based on:

&nbsp;&nbsp;(a) the legislative power the Commonwealth Parliament has under
paragraph 51(xxix) of the Constitution; and

&nbsp;&nbsp;(b) the other legislative powers that the Commonwealth Parliament has
under section 51 of the Constitution; and

&nbsp;&nbsp;(c) the legislative powers that the Commonwealth Parliament has under
section 122 of the Constitution to make laws for the government of the external
Territories.

(4) The operation of this Act in a State that is not a referring State is based
on:

&nbsp;&nbsp;(a) the legislative powers that the Commonwealth Parliament has under
section 51 (other than paragraph 51(xxxvii)) and section 122 of the
Constitution; and

&nbsp;&nbsp;(b) the legislative powers that the Commonwealth Parliament has in
respect of matters to which this Act relates because those matters are referred
to it by the Parliaments of the referring States under paragraph 51(xxxvii) of
the Constitution.

## Structure notes

- Heading is unnumbered in the reader sense: `<num>3</num>` + `<heading>`.
- Four subsections `(1)`-`(4)`, each an intro `<p>` then paragraphs `(a)`/`(b)`
  (subsec 3 also has `(c)`).
- One authorial note, attached to subsection (1) paragraph (b), marker `1`,
  label `Note:` (single Note, no number).
- "Despite section 2H ..." is an unnumbered trailing sentence inside subsection
  (2) paragraph (b) - a second `<content>` block, not its own paragraph.
- `section 51`, `section 122`, `section 2H`, `paragraph 51(xxxvii)` use a
  non-breaking space between the word and the number in the corpus.
- `Acts Interpretation Act 1901` is italic (`<i>`).

## Known corpus/XML defects (parity failures to expect)

1. **Scrambled cross-reference in subsection (2)(b).** The XML renders the
   "Despite ..." sentence as
   `Despite <i>Acts Interpretation Act 1901</i>, this Act as applying in those
   Territories is a law of the Commonwealth.<ref href="#sec-2H">section 2H</ref>
   of the ` - the phrase "section 2H of the" has been cut out of its correct
   position (before the Act name) and appended after the full stop, and the
   Act-name italics are in the wrong place. Authoritative order is
   "Despite section 2H of the *Acts Interpretation Act 1901*, this Act ...". This
   is the corpus's systematic "See <ActName>.<ref>section N</ref> of the "
   reordering bug for cross-Act references.
2. `<ref href="#sec-51">` and `<ref href="#sec-122">` point at the *Constitution*,
   not at a provision of this Act; there is no `#sec-51` / `#sec-122` target in
   the fixture (or the Act). A resolver must treat these as external / unresolved.
3. `#sec-2H` is a bare, chapter/part-unscoped href; the real eId (if present)
   would be `...__sec-2H`.
