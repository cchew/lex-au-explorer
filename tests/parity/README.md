# DOCX text-parity golden tests

`test_parity.py` is a regression harness. For each real-corpus fixture in
`tests/fixtures/corpus/` it runs the section pipeline
(`build.parse.parse_section` -> `build.render.render_section` with
`HtmlStyleMap`), strips the HTML to plain text, and asserts that every paragraph
of the fixture's parity oracle appears **in document order** in the rendered
text.

## What the goldens are

The goldens are the `## Authoritative text` sections of
`tests/fixtures/corpus/<name>.expected.md`. Those were transcribed by Task 1
from the authoritative Word compilation named in each file's header
(`- Source of truth: ...c147-vol1.docx (Compilation No. 147 ...)`), cross-checked
against legislation.gov.au. No `.docx` is committed to this repo.

## Match rules

The check is a **subsequence** match, not byte-equal. Both the oracle text and
the rendered text pass through `_normalise()` first, which is allowed to differ
on:

- HTML entities and non-breaking spaces
- curly vs straight quotes
- any dash run (hyphen / en / em / non-breaking hyphen, plus the spaces around
  it) collapsing to a bare `-`
- short parenthesised markers: `(1)` / `(a)` -> `1` / `a` (the reader renders
  schedule clause markers bare and Act-body markers parenthesised)
- Markdown emphasis markers (`*x*`, `**x**`) in the oracle
- the defined-term asterisk: `*financial year` -> `financial year`

Block-level tags become a space when stripped; inline tags (`<span>`, `<a>`,
`<em>`, `<strong>`) vanish, so a cross-reference split as
`<span>section 4</span>-15` reads back as `section 4-15`. A `<ref>` contributes
its link text whether it resolved to an `<a>` or fell back to a `<span>` -- the
parity check is on text, not link status.

Figure fixtures additionally assert that a `<figure>` renders a non-empty
`[figure: ...]` placeholder (never a blank).

## Known upstream gaps

`_KNOWN_GAPS` in `test_parity.py` lists paragraphs the current corpus cannot
reproduce because of lex-au's AKN-conversion "U1" bug (a
`<ActName>.<ref>section N</ref> of the ` cross-Act reference is relocated to the
end of the sentence). The plan assigns U1 to **Track B**, not to
rendering-fidelity Tasks 3-7, and each instance is written up in the fixture's
own `## Known corpus/XML defects` section. For each gap the harness:

1. keeps the paragraph's correctly-rendered leading half (`_Gap.keep`) in the
   ordered check, so a regression that drops the good half still fails, and
   removes only the scrambled tail, and
2. asserts the correctly-ordered phrase (`_Gap.absent_phrase`) is **absent** from
   the render, so the test fails loudly (telling you to re-grade the fixture) if
   a Track B fix later lands.

Do not add entries here to silence a genuine rendering regression. If a
must-match paragraph stops matching and it is not a Track B U1 scramble, that is
a real fidelity gap -- fix the pipeline, do not weaken the assertion.

## Regenerating the goldens when a new compilation lands

1. Get the new Word volumes into the lex-au corpus
   (`../../lex-au/repo/corpus/docx/`). Identify the volume that holds each
   fixture's provision (the `- Source of truth:` line names it).

2. Dump the visible paragraphs with the stdlib-only helper:

   ```
   python tests/parity/extract_docx.py \
     ../../lex-au/repo/corpus/docx/corporations-act-2001-c<NN>-vol1.docx \
     "Constitutional basis for this Act"
   ```

   `extract_docx.paragraphs(path)` returns the body paragraphs in document
   order, whitespace-collapsed, with `<w:tab>` / `<w:br>` as a single space and
   field-code / tracked-deletion runs dropped. The optional second argument is a
   case-insensitive substring filter for eyeballing one provision. Note the
   table-of-contents copy of a heading appears first; the body copy is the later
   hit.

3. For each fixture, update the `## Authoritative text` block of
   `tests/fixtures/corpus/<name>.expected.md` to match the new visible text.
   Keep the transcription conventions already in the file (Markdown emphasis for
   `<i>`/`<b>`, `\*` for a literal defined-term asterisk, `> ` for notes,
   Markdown tables for `<table>`, `*[flowchart image - ...]*` for an absent
   figure). Update the header: docx filename, compilation number, compilation
   date, and the legislation.gov.au compilation id.

4. If the new compilation fixes a `_KNOWN_GAPS` scramble, the absent-phrase
   assertion for that fixture will start failing. Move the paragraph back into
   the oracle's normal flow and delete the `_Gap` entry.

5. Re-run `pytest tests/parity -v` (via `rtk proxy python -m pytest` so counts
   are not misreported).

## Also update the XML fixtures

`extract_docx.py` only refreshes the parity oracle. The `.xml` fixtures are
trimmed subtrees of the lex-au AKN corpus; regenerate those from
`../../lex-au/repo/corpus/xml/<act>.xml` the same way Task 1 did (keep the
`<identification>` block and the single target subtree).
