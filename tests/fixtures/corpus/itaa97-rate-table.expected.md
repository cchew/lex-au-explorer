# Parity oracle: Income Tax Assessment Act 1997, section 4-15

- Fixture: `itaa97-rate-table.xml`
- eId: `chapter-1__part-1-3__dvs-4__sec-4-15`
- Source of truth: `lex-au/repo/corpus/docx/income-tax-assessment-act-1997-c266-vol1.docx`
  (Compilation No. 266, compilation date 1 July 2026 - matches the XML's
  `eng@2026-07-01` expression), `word/document.xml` paragraphs 788-826. Text
  identical in the undated `income-tax-assessment-act-1997-vol1.docx`.
- legislation.gov.au: `C2004A05138` (compilation `C2026C00324`) / Chapter 1, Part 1-3,
  Division 4, s 4-15.

## Note on the fixture brief

The brief asked for "a `<table>` whose `<td>` contains `<ref>` and `<i>`". No such
table exists anywhere in the corpus: across all 3,076 XML files **every `<td>` is
text-only** - table cells carry no inline markup at all (see the spike note,
section A). This section is the closest real match: it has a genuine multi-row
`<table>`, and it has `<ref>` and `<i>`/`<b><i>` inline markup in the surrounding
method statement and notes. The parity value is in showing that table-cell
cross-references ("Subdivision 165-B", "section 124ZTA of the Income Tax
Assessment Act 1936") are unmarked plain text.

## Authoritative text

**4-15  How to work out your taxable income**

(1) Work out your **taxable income** for the income year like this:

*[flowchart image - `corpus/images/income-tax-assessment-act-1997-fig-3.png`,
absent from the corpus, `alt=""`]*

Method statement

Step 1. Add up all your assessable income for the income year.
To find out about your assessable income, see Division 6.

Step 2. Add up your deductions for the income year.
To find out what you can deduct, see Division 8.

Step 3. Subtract your deductions from your assessable income (unless they exceed
it). The result is your taxable income. (If the deductions equal or exceed the
assessable income, you don't have a taxable income.)

> Note: If the deductions exceed the assessable income, you may have a tax loss
> which you may be able to utilise in that or a later income year: see
> Division 36.

(2) There are cases where taxable income is worked out in a special way:

| Item | For this case ... | See: |
|------|-------------------|------|
| 1. | A company does not maintain continuity of ownership and control during the income year and does not satisfy the business continuity test | Subdivision 165-B |
| 1B. | An entity is a \*member of a \*consolidated group at any time in the income year | Part 3-90 |
| 2. | A company becomes a PDF (pooled development fund) during the income year, and the PDF component for the income year is a nil amount | section 124ZTA of the Income Tax Assessment Act 1936 |
| 3. | A shipowner or charterer: has its principal place of business outside Australia; and carries passengers, freight or mail shipped in Australia | section 129 of the Income Tax Assessment Act 1936 |
| 4. | An insurer who is a foreign resident enters into insurance contracts connected with Australia | sections 142 and 143 of the Income Tax Assessment Act 1936 |
| 5. | The Commissioner makes a default or special assessment of taxable income | sections 167 and 168 of the Income Tax Assessment Act 1936 |
| 6. | The Commissioner makes a determination of the amount of taxable income to prevent double taxation in certain treaty cases | section 24 of the International Tax Agreements Act 1953 |

> Note: A life insurance company can have a taxable income of the complying
> superannuation class and/or a taxable income of the ordinary class for the
> purposes of working out its income tax for an income year: see
> Subdivision 320-D.

## Structure notes

- Section number `4-15` is hyphenated; its eId ends `...__sec-4-15`.
- Two subsections. Subsection (1) contains: an intro `<p>`, a `<figure><img>`,
  a `<content>` block of method-statement `<p>` lines, and one `<authorialNote>`
  (marker 14, label `Note:`).
- Subsection (2) contains an intro `<p>`, a `<table>`, and one `<authorialNote>`
  (marker 15, label `Note:`).
- `<table>` = one header `<tr>` of three `<th>` (Item / For this case ... / See:)
  then seven data `<tr>`, each three `<td>`. Cells 3-6 wrap their body text onto
  multiple lines with a leading tab per continuation line (no list markup).
- Inline markup present in the subtree: `<b><i>taxable income</i></b>` in
  subsec (1); `<ref href="#dvs-6">`, `<ref href="#dvs-8">`, `<ref href="#dvs-36">`
  in the method statement / note.
- `*member`, `*consolidated group` keep a literal asterisk (defined-term marker)
  as plain text; they are **not** wrapped as `<term>` or `<ref>`.
- "Subdivision 165-B", "Part 3-90", "Subdivision 320-D", and every "section N of
  the <Act>" in the table are plain `<td>` / `<p>` text with no `<ref>`.

## Known corpus/XML defects (parity failures to expect)

1. **The whole `<table>` is dropped by the current renderer.** `build.bundle`
   handles `<content>/<p>` only; `<tr>/<th>/<td>` fall through
   `_render_children` and, because `<td>` has no element children, nothing is
   emitted. Rendered HTML for this section is ~1.2 KB and contains none of the
   seven rows.
2. Table-cell cross-references are unresolvable from markup - they are prose
   strings, several of them pointing at a different Act (ITAA 1936, International
   Tax Agreements Act 1953).
3. docx text layer strips the hyphen from provision numbers ("165-B" -> "165B",
   "3-90" -> "390", "320-D" -> "320D"); the XML keeps the hyphen. Transcribed
   above with the hyphen (the AKN/legislation.gov.au form).
