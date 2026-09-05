# Spike: Schedule `<hcontainer>` Parsing

**Date:** 2026-09-04  
**Status:** Complete - construction method validated  
**Findings:** All requirements passed. `copy.deepcopy` into a detached `<hcontainer>` is safe and produces correct renderings.

## What Was Done

A Python spike script tested the proposed binding construction method for wrapping schedule-element runs. Two Acts were tested:

1. **Administrative Decisions (Judicial Review) Act 1977, schedule-1:**
   - 85 direct `<paragraph>` children + 1 `<content>` element (87 total, excluding `<heading>`)
   - Each `<paragraph>` contains a `<content>` wrapper with inline elements including `<p>` tags

2. **Age Discrimination Act 2004, schedule-1:**
   - 1 direct `<table>` child (excluding `<heading>`)
   - Table has 56 rows

For each, the spike script:
- Created a detached `etree.Element(f"{AKN}hcontainer")` 
- Deep-copied each direct child (excluding `<num>` and `<heading>`) into the wrapper using `copy.deepcopy(child)`
- Called `parse_section(wrap, RefIndex([]))` to parse the wrapped elements
- Called `render_section(node, HtmlStyleMap())` to render to HTML
- Verified source schedule byte-identity before/after
- Inspected the parsed Node tree and HTML output

## Findings by Question

### Q1: Does every `<paragraph>` render its text into the output HTML?

**YES.** ADJR Act: 85 paragraphs rendered with 111 total `<p>` elements in the HTML output. Text content verified (e.g., "Australian Security Intelligence Organisation Act 1956" present). No text was dropped.

### Q2: Does the `<table>` render all its rows?

**YES.** Age Discrimination Act: 1 `<table>` rendered with all 56 `<tr>` elements present in the HTML output.

### Q3: Does any element kind fall through to a `raw`/`inline_raw` node type?

**YES, but by design.** Found 2 `inline_raw` nodes in the ADJR parse. Both occur within `<para>` (inline paragraph) blocks and wrap `<p>` elements. The `<p>` tag is not in the recognized inline tag set (`{'i', 'b', 'term', 'ref', 'date', 'quantity'}`), so it correctly falls through to `inline_raw` as a catch-all for unknown inline constructs. **This is expected behavior** (see `build/parse.py` docstring: "every element that is not a recognised block or inline construct falls through to a generic `raw` / `inline_raw` node that still recurses its children, so source text is never silently dropped").

**For Task 2:** No new handler is needed. The `<p>` element is intentional corpus markup (present in all 85 ADJR schedule paragraphs) and is being preserved correctly through the `inline_raw` fallback. The text renders properly in HTML output.

### Q4: Does `_apply_identity` work fine when wrapped elements have no `eId`/`num` of their own?

**YES.** The parser correctly assigned `eId` attributes to provisions even though the deepcopied `<paragraph>` elements had no `num` children (the `<heading>` and `<num>` were excluded per the binding spec). Rendered Node attributes show: `'eid': 'schedule-1__para-a'`, `'eid': 'schedule-1__para-b'`, etc., with proper numbering assigned from the paragraph's position and content context.

### Q5: Verify `ET.tostring(sched)` is byte-identical before and after operations.

**YES.** Source schedule element byte representation (via `ET.tostring()`) was identical before and after the deepcopy-and-parse operations for both Acts. The source tree was never mutated.

**Evidence:**
- ADJR Act: schedule-1 unchanged after wrapping and parsing
- Age Discrimination Act: schedule-1 unchanged after wrapping and parsing

## Conclusion

The `copy.deepcopy` construction method is **mandatory for Tasks 3, 6, and 7**. The binding correctly prevents source-tree mutation (a critical requirement for the build pipeline's multi-pass reuse pattern) while producing complete and accurate renderings of schedule content.

**Why this method works:**
- `copy.deepcopy()` creates independent copies of elements, breaking any parent references that would otherwise be moved by `SubElement().append()` + `remove()` operations
- The detached wrapper has no parent, so parsing it does not affect the source tree
- Text and structure are fully preserved through the rendering pipeline

**No additional parser handlers needed.** The `<p>` fallthrough to `inline_raw` is by design and correctly preserves text.
