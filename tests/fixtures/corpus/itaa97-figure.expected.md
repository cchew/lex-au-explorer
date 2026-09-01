# Parity oracle: Income Tax Assessment Act 1997, section 4-10

- Fixture: `itaa97-figure.xml`
- eId: `chapter-1__part-1-3__dvs-4__sec-4-10`
- Source of truth: `lex-au/repo/corpus/docx/income-tax-assessment-act-1997-c266-vol1.docx`
  (Compilation No. 266, compilation date 1 July 2026), `word/document.xml`
  paragraphs 765-787. Text identical in the undated
  `income-tax-assessment-act-1997-vol1.docx`.
- legislation.gov.au: `C2004A05138` (compilation `C2026C00324`) / Chapter 1, Part 1-3,
  Division 4, s 4-10.

## Authoritative text

**4-10  How to work out how much income tax you must pay**

(1) You must pay income tax for each \*financial year.

(2) Your income tax is worked out by reference to your taxable income for the
**income year**. The income year is the same as the \*financial year, except in
these cases:

&nbsp;&nbsp;(a) for a company, the income year is the *previous* financial year;

&nbsp;&nbsp;(b) if you have an accounting period that is not the same as the
financial year, each such accounting period or, for a company, each previous
accounting period is an income year.

> Note 1: The Commissioner can allow you to adopt an accounting period ending on
> a day other than 30 June. See section 18 of the *Income Tax Assessment Act
> 1936*.

> Note 2: An accounting period ends, and a new accounting period starts, when a
> partnership becomes, or ceases to be, a VCLP, an ESVCLP, an AFOF or a VCMP. See
> section 18A of the *Income Tax Assessment Act 1936*.

(3) Work out your income tax for the \*financial year as follows:

*[flowchart image - `corpus/images/income-tax-assessment-act-1997-fig-2.png`,
absent from the corpus, `alt=""`]*

Method statement

Step 1. Work out your taxable income for the income year.
To do this, see section 4-15.

Step 2. Work out your basic income tax liability on your taxable income using:

&nbsp;&nbsp;(a) the income tax rate or rates that apply to you for the income
year; and

&nbsp;&nbsp;(b) any special provisions that apply to working out that liability.

See the *Income Tax Rates Act 1986* and section 4-25.

Step 3. Work out your tax offsets for the income year. A **tax offset** reduces
the amount of income tax you have to pay.
For the list of tax offsets, see section 13-1.

Step 4. Subtract your \*tax offsets from your basic income tax liability. The
result is how much income tax you owe for the \*financial year.

Income tax worked out on another basis

> Note 1: Division 63 explains what happens if your tax offsets exceed your basic
> income tax liability. How the excess is treated depends on the type of tax
> offset.

> Note 2: Section 4-11 of the *Income Tax (Transitional Provisions) Act 1997*
> (which is about the temporary budget repair levy) may increase the amount of
> income tax worked out under this section.

(4) For some entities, some or all of their income tax for the \*financial year
is worked out by reference to something other than taxable income for the income
year.

See section 9-5.

## Structure notes

- Four subsections. Subsection (3) is the method statement and holds the
  `<figure><img>` (between the intro `<p>` and the "Method statement" `<content>`
  block).
- Authorial notes: markers 10 and 11 (label `Note 1:` / `Note 2:`) on subsec (2)
  paragraph (b); markers 12 and 13 on subsec (3) paragraph (b).
- Defined-term usages `\*financial year` appear 3x as
  `<ref href="#term-financial-year">financial year</ref>` (asterisk dropped,
  link added). `\*tax offsets` in Step 4 keeps a literal asterisk and is **not**
  linked. `**taxable income**` / `**tax offset**` are `<b><i>` emphasis, not
  term links.
- "section 4-15", "section 4-25", "section 13-1", "section 9-5" are hyphenated
  provision numbers; only the pre-hyphen digits are inside the `<ref>`.

## Known corpus/XML defects (parity failures to expect)

1. **Scrambled cross-references in Notes 1 and 2 of subsection (2)(b).** The XML
   is `See <i>Income Tax Assessment Act 1936</i>.<ref href="#sec-18">section
   18</ref> of the ` (and `#sec-18A` for Note 2). Authoritative order:
   "See section 18 of the *Income Tax Assessment Act 1936*." The "section N of
   the" fragment is cut and re-appended after the full stop. Same bug as
   `corp-act-s3` subsection (2)(b).
2. **Hyphenated section numbers are truncated in `href`.** "section 4-15" ->
   `href="#sec-4"`, "section 13-1" -> `href="#sec-13"`, "section 9-5" ->
   `href="#sec-9"`. The full number survives only in the ref's display text
   ("section 4" + tail "-15"). `#sec-4` does not suffix-match `...__sec-4-15`
   and there is no bare `sec-4`; the target is unrecoverable from the href alone.
3. "section 4-25" and "section 4-11" (Note 2 of subsec (3)) are plain text, not
   `<ref>` at all - inconsistent with the linked ones in the same section.
4. `<ref href="#term-financial-year">` (11,704 like it in this Act) is a
   defined-term usage link. `build.bundle` only wraps `<term>` elements as
   `data-term`, so this fixture yields **0** hover targets even though it uses a
   defined term four times.
5. The `<figure><img>` target is absent (`corpus/images/` does not exist) and
   `alt=""`; it renders as an empty/placeholder box with no accessible text.
