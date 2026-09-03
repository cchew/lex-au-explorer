"""DOCX text-parity golden tests for the section renderer.

One test per real-corpus fixture in ``tests/fixtures/corpus/``. Each fixture
ships an ``.xml`` subtree (Task 1) and an ``.expected.md`` parity oracle whose
``## Authoritative text`` section was transcribed from the authoritative Word
compilation (see ``tests/parity/README.md`` and ``tests/parity/extract_docx.py``).

The test parses the fixture with :func:`build.parse.parse_section`, renders it
with :class:`build.stylemap.HtmlStyleMap`, strips the HTML to plain text, and
asserts that every paragraph of the oracle appears **in document order** as a
substring of the rendered text (a subsequence match, not a byte-equal one: the
reader legitimately normalises whitespace, dash punctuation, curly quotes,
parenthesised provision markers and the defined-term asterisk).

Known upstream-corpus defects (the "U1" cross-Act reference reordering bug, which
the plan assigns to Track B, not to this rendering work) are listed per fixture
in ``_KNOWN_GAPS``. The oracle paragraph that carries the scramble is excluded
from the ordered check, and the correctly-ordered phrase that the corpus cannot
currently produce is asserted **absent** so the test flips loudly if a Track B
fix later lands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import lxml.etree as ET

from build.parse import parse_section
from build.refindex import build_ref_index
from build.render import render_section
from build.stylemap import HtmlStyleMap

try:  # pytest prepends this file's directory to sys.path
    from extract_docx import paragraphs as _docx_paragraphs
except ImportError:  # pragma: no cover - import shape guard only
    _docx_paragraphs = None

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "corpus"

_EID_RE = re.compile(r"^- eId:\s*`([^`]+)`", re.MULTILINE)
_ORACLE_MARKER_RE = re.compile(r"^\(([0-9A-Za-z]{1,4})\)\s")
_HEADING_RE = re.compile(r"^##\s+", re.MULTILINE)
_TABLE_SEP_CELL_RE = re.compile(r"^:?-+:?$")
_PAREN_MARKER_RE = re.compile(r"\(([0-9A-Za-z]{1,4})\)")
_DASH_RUN_RE = re.compile("\\s*[\u2010-\u2015\u2212\\-]+\\s*")
_SINGLE_QUOTE_RE = re.compile("[\u2018\u2019\u201a\u201b\u2032]")
_DOUBLE_QUOTE_RE = re.compile("[\u201c\u201d\u201e\u201f\u2033]")
_TERM_ASTERISK_RE = re.compile(r"\*(?=\w)")
_IMAGE_NOTE_RE = re.compile(r"^\*?\[.*\]\*?$", re.DOTALL)

_BLOCK_TAGS = (
    "p|div|table|thead|tbody|tr|td|th|figure|figcaption|li|ul|ol|h[1-6]|br"
    "|section|article"
)
_BLOCK_TAG_RE = re.compile("</?(?:" + _BLOCK_TAGS + r")\b[^>]*>", re.IGNORECASE)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_ENTITY_RE = re.compile(r"&(?:amp|lt|gt|quot|#39|nbsp);")
_ENTITIES = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&nbsp;": " ",
}
_NBSP = "\u00a0"
_NB_HYPHEN = "\u2011"


# --------------------------------------------------------------------------- #
# Known upstream-corpus (Track B / "U1") text-fidelity gaps
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Gap:
    """One documented upstream-corpus text defect for a fixture.

    ``oracle_marker`` identifies (by substring, post-normalisation) the oracle
    paragraph the scramble sits in. That paragraph is not dropped wholesale:
    ``keep`` is its leading part that the reader *does* render correctly and that
    stays in the ordered subsequence check, so a regression that drops the
    good half still fails. ``absent_phrase`` is the correctly-ordered text the
    current corpus cannot produce; the test asserts it is *not* in the rendered
    output, so a later Track B converter fix turns this into a visible failure
    that says "re-grade this fixture".
    """

    oracle_marker: str
    keep: str
    absent_phrase: str
    note: str


# All three entries share one root cause: lex-au's AKN conversion relocates a
# "<ActName>.<ref>section N</ref> of the " cross-Act reference to the end of the
# sentence, dropping the lead-in. The plan's self-review assigns "U1 -> Track B";
# it is not in scope for rendering-fidelity Tasks 3-7. Each is written up in the
# fixture's own "## Known corpus/XML defects (parity failures to expect)".
_KNOWN_GAPS: dict[str, list[_Gap]] = {
    "corp-act-s3": [
        _Gap(
            oracle_marker="Despite section 2H of the",
            keep="this Act as applying in those Territories is a law of the Commonwealth.",
            absent_phrase="Despite section 2H of the Acts Interpretation Act 1901",
            note="subsec (2)(b) trailing sentence; defect #1 in corp-act-s3.expected.md",
        ),
    ],
    "itaa97-figure": [
        _Gap(
            oracle_marker="The Commissioner can allow you to adopt an accounting period",
            keep=(
                "Note 1: The Commissioner can allow you to adopt an accounting "
                "period ending on a day other than 30 June."
            ),
            absent_phrase="See section 18 of the Income Tax Assessment Act 1936",
            note="subsec (2)(b) Note 1 (marker 10); defect #1 in itaa97-figure.expected.md",
        ),
        _Gap(
            oracle_marker="An accounting period ends, and a new accounting period starts",
            keep=(
                "Note 2: An accounting period ends, and a new accounting period "
                "starts, when a partnership becomes, or ceases to be, a VCLP, an "
                "ESVCLP, an AFOF or a VCMP."
            ),
            absent_phrase="See section 18A of the Income Tax Assessment Act 1936",
            note="subsec (2)(b) Note 2 (marker 11); defect #1 in itaa97-figure.expected.md",
        ),
    ],
}


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #


def _unescape(text: str) -> str:
    return _ENTITY_RE.sub(lambda m: _ENTITIES[m.group(0)], text)


def _normalise(text: str) -> str:
    """Whitespace / punctuation normalisation applied to both sides of the diff.

    The reader is allowed to differ from the Word text on exactly these points:
    HTML entities, non-breaking spaces, curly vs straight quotes, any dash run
    (hyphen / en / em / non-breaking hyphen, with the spaces around it)
    collapsing to a bare hyphen, short parenthesised markers ``(1)`` / ``(a)``
    losing their parentheses, Markdown emphasis markers, and the defined-term
    asterisk (``*financial year`` -> ``financial year``).
    """
    text = _unescape(text)
    text = text.replace(_NBSP, " ").replace(_NB_HYPHEN, "-")
    text = _SINGLE_QUOTE_RE.sub("'", text)
    text = _DOUBLE_QUOTE_RE.sub('"', text)
    # Markdown emphasis: protect an escaped "\*" (a literal asterisk in the
    # oracle), drop every remaining "*" emphasis marker, then restore.
    text = text.replace("\\*", "\x00")
    text = text.replace("*", "")
    text = text.replace("\x00", "*")
    text = _TERM_ASTERISK_RE.sub("", text)
    text = _DASH_RUN_RE.sub("-", text)
    text = _PAREN_MARKER_RE.sub(r"\1", text)
    return " ".join(text.split())


def _html_to_text(html: str) -> str:
    """Strip HTML to plain text: block tags become spaces, inline tags vanish."""
    text = _BLOCK_TAG_RE.sub(" ", html)
    text = _ANY_TAG_RE.sub("", text)
    return _unescape(text)


# --------------------------------------------------------------------------- #
# Oracle parsing
# --------------------------------------------------------------------------- #


def _authoritative_block(md: str) -> str:
    """The text between the ``## Authoritative text`` heading and the next ``##``."""
    lower = md.find("## Authoritative text")
    assert lower != -1, "oracle has no '## Authoritative text' section"
    start = md.index("\n", lower) + 1
    rest = md[start:]
    nxt = _HEADING_RE.search(rest)
    return rest[: nxt.start()] if nxt else rest


def _split_blocks(section: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in section.splitlines():
        if line.strip():
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _table_rows(block: list[str]) -> list[str]:
    cells: list[str] = []
    for line in block:
        raw = [c.strip() for c in line.strip().strip("|").split("|")]
        if raw and all(_TABLE_SEP_CELL_RE.match(c) for c in raw if c):
            continue  # the |---|---| separator row
        cells.extend(c for c in raw if c)
    return cells


def _oracle_markers(md: str) -> list[str]:
    """Bare provision markers the oracle carries (``(1)`` -> ``1``, ``(a)`` ->
    ``a``), in first-seen order, deduplicated. Used for the duplication check."""
    seen: list[str] = []
    for para in _oracle_paragraphs(md):
        m = _ORACLE_MARKER_RE.match(para)
        if m and m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def _oracle_paragraphs(md: str) -> list[str]:
    """Ordered list of oracle paragraphs (raw, pre-normalisation)."""
    out: list[str] = []
    for block in _split_blocks(_authoritative_block(md)):
        joined = " ".join(line.strip() for line in block).strip()
        if _IMAGE_NOTE_RE.match(joined) and "image" in joined.lower():
            continue  # editorial "*[flowchart image - ...]*" note, not body text
        if all(line.lstrip().startswith(">") for line in block):
            out.append(" ".join(line.lstrip()[1:].strip() for line in block))
        elif all(line.lstrip().startswith("|") for line in block):
            out.extend(_table_rows(block))
        elif any(line.lstrip().startswith(("- ", "* ")) for line in block):
            for line in block:
                stripped = line.strip()
                if stripped.startswith(("- ", "* ")):
                    out.append(stripped[2:].strip())
                elif out:
                    out[-1] = out[-1] + " " + stripped
        else:
            out.append(joined)
    return [p for p in out if p]


# --------------------------------------------------------------------------- #
# Fixture loading / rendering
# --------------------------------------------------------------------------- #


def _iter_nodes(node):
    yield node
    for child in node.children:
        yield from _iter_nodes(child)


def _render_fixture(name: str) -> tuple[str, str]:
    """Return ``(rendered_plain_text, oracle_markdown)`` for fixture ``name``."""
    xml_path = _FIXTURES / (name + ".xml")
    md_path = _FIXTURES / (name + ".expected.md")
    md = md_path.read_text(encoding="utf-8")

    eid_match = _EID_RE.search(md)
    assert eid_match, md_path.name + " has no '- eId: `...`' line"
    target_eid = eid_match.group(1)

    root = ET.parse(str(xml_path)).getroot()
    target = root.find(".//*[@eId='" + target_eid + "']")
    assert target is not None, (
        xml_path.name + " has no element with eId " + repr(target_eid)
    )

    nav_eids = [el.get("eId") for el in root.iter() if el.get("eId")]
    ref_index = build_ref_index(nav_eids)
    node = parse_section(target, ref_index)
    html = render_section(node, HtmlStyleMap())

    heading_prefix = (
        str(node.attrs.get("num", "")) + "  " + str(node.attrs.get("heading", ""))
    )
    plain = heading_prefix + "  " + _html_to_text(html)

    # Figure fixtures: the placeholder must be present and non-empty.
    if any(n.kind == "figure" for n in _iter_nodes(node)):
        assert re.search(r"\[figure:\s*\S", html), (
            "[" + name + "] a <figure> rendered blank; expected a "
            "'[figure: ...]' placeholder"
        )
    return plain, md


def _assert_ordered_subsequence(
    oracle: list[str], haystack: str, *, name: str
) -> None:
    cursor = 0
    for i, paragraph in enumerate(oracle):
        at = haystack.find(paragraph, cursor)
        if at != -1:
            cursor = at + len(paragraph)
            continue
        anywhere = haystack.find(paragraph)
        window = haystack[max(0, cursor - 220): cursor + 420]
        lines = [
            "[" + name + "] oracle paragraph " + str(i) + " of "
            + str(len(oracle)) + " did not match the rendered text "
            "(subsequence check).",
            "  expected : " + repr(paragraph),
            "  rendered near cursor " + str(cursor) + ": ..." + repr(window) + "...",
        ]
        if anywhere != -1:
            lines.append(
                "  NOTE: it appears earlier, at offset " + str(anywhere)
                + " (order violation, not a drop)."
            )
        else:
            lines.append(
                "  NOTE: it does not appear anywhere in the rendered text."
            )
        raise AssertionError("\n".join(lines))


def _check_fixture(name: str) -> None:
    plain, md = _render_fixture(name)
    haystack = _normalise(plain)
    gaps = _KNOWN_GAPS.get(name, [])

    oracle = [_normalise(p) for p in _oracle_paragraphs(md)]
    assert oracle, "[" + name + "] parsed zero oracle paragraphs"

    # For a known-gap paragraph, keep only its correctly-rendered leading half in
    # the ordered check; the scrambled tail is covered by the absent assertion
    # below.
    must_match: list[str] = []
    for paragraph in oracle:
        keep = None
        for gap in gaps:
            if _normalise(gap.oracle_marker) in paragraph:
                keep = _normalise(gap.keep)
                break
        must_match.append(keep if keep is not None else paragraph)
    _assert_ordered_subsequence(must_match, haystack, name=name)

    # G4 duplication guard. `_normalise` collapses "(1) 1" to "1 1", so a
    # provision marker that leaked into the body a second time (numbering
    # normalisation misfire) still subsequence-matches. Assert no marker the
    # oracle shows once appears doubled and adjacent in the rendered text.
    for marker in _oracle_markers(md):
        doubled = re.compile(
            r"(?<!\S)" + re.escape(marker) + r"\s+" + re.escape(marker) + r"(?!\S)"
        )
        assert not doubled.search(haystack), (
            "[" + name + "] provision marker " + repr(marker) + " appears "
            "doubled in the rendered text -- numbering normalisation regression "
            "(G4 duplication)."
        )

    for gap in gaps:
        absent = _normalise(gap.absent_phrase)
        assert absent not in haystack, (
            "[" + name + "] known upstream gap looks resolved: " + repr(absent)
            + " is now present in the rendered text. Re-grade this fixture's "
            "_KNOWN_GAPS entry (a Track B converter fix may have landed). "
            "Context: " + gap.note
        )


# --------------------------------------------------------------------------- #
# Tests: one per fixture
# --------------------------------------------------------------------------- #


def test_corp_act_s3_parity() -> None:
    _check_fixture("corp-act-s3")


def test_corp_act_s9AB_parity() -> None:
    _check_fixture("corp-act-s9AB")


def test_corp_act_s3_small_business_guide_parity() -> None:
    _check_fixture("corp-act-s3-sbg")


def test_itaa97_rate_table_parity() -> None:
    _check_fixture("itaa97-rate-table")


def test_itaa97_figure_parity() -> None:
    _check_fixture("itaa97-figure")


def test_sched_clause_parity() -> None:
    _check_fixture("sched-clause")


def test_blocklist_items_parity() -> None:
    _check_fixture("blocklist-items")


def test_blocklist_items_render_markers() -> None:
    """S5: list introduction + every item marker/body render, in order."""
    root = ET.parse(str(_FIXTURES / "blocklist-items.xml")).getroot()
    target = root.find(".//*[@eId='part-1__sec-5']")
    assert target is not None
    node = parse_section(target, build_ref_index([]))
    html = render_section(node, HtmlStyleMap())
    assert '<div class="akn-list">' in html
    assert '<p class="akn-intro">the following information:</p>' in html
    for marker in ("(a)", "(b)", "(c)"):
        assert '<span class="akn-num">' + marker + "</span>" in html
    assert "the date on which any person ceased to be a member." in html


def test_penalty_block_parity() -> None:
    _check_fixture("penalty-block")


def test_penalty_block_renders_penaltytext() -> None:
    """G7: hcontainer name="penalty" renders as its own akn-penaltytext block."""
    root = ET.parse(str(_FIXTURES / "penalty-block.xml")).getroot()
    target = root.find(".//*[@eId='part-2__sec-12']")
    assert target is not None
    node = parse_section(target, build_ref_index([]))
    html = render_section(node, HtmlStyleMap())
    assert '<div class="akn-penaltytext">' in html
    assert "Penalty: 50 penalty units." in html


def test_extract_docx_importable() -> None:
    """The golden-regeneration helper imports and exposes ``paragraphs``."""
    assert _docx_paragraphs is not None
    assert callable(_docx_paragraphs)
