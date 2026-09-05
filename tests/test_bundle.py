"""End-to-end coverage for the bundle stage: ``build_toc`` (unchanged) and
``build_sections`` (rewritten to delegate to Stage 1 parse + Stage 2 render).

The per-construct regression assertions that used to live here (inline
emphasis, embedded-number normalisation, authorial notes, defined-term
marking) now live in ``tests/test_parse.py`` and ``tests/test_render.py``,
exercised against the real-corpus fixtures in ``tests/fixtures/corpus/``.
"""

from __future__ import annotations

import collections
from pathlib import Path

import lxml.etree as ET

from build.bundle import AKN, build_sections, build_toc, _local_tag
from build.ir import Node
from build.refindex import build_ref_index
from build.stylemap import HtmlStyleMap

FIXTURES = Path(__file__).parent / "fixtures"
_NAV_TAGS = {
    "section", "part", "division", "subdivision", "chapter",
    "subsection", "paragraph", "subparagraph",
}
_NAV_HCONTAINERS = {"clause", "subclause"}


def _parse_stub(name: str) -> ET._Element:
    return ET.parse(str(FIXTURES / "xml" / name)).getroot()


def _parse_corpus(name: str) -> ET._Element:
    return ET.parse(str(FIXTURES / "corpus" / name)).getroot()


def _all_nav_eids(root: ET._Element) -> list[str]:
    eids: list[str] = []
    for el in root.iter():
        eid = el.get("eId")
        if not eid:
            continue
        tag = _local_tag(el)
        if tag in _NAV_TAGS or (
            tag == "hcontainer" and el.get("name") in _NAV_HCONTAINERS
        ):
            eids.append(eid)
    return eids


# --------------------------------------------------------------------------- #
# build_toc -- unchanged behaviour
# --------------------------------------------------------------------------- #


def test_build_toc_nests_part_division_section() -> None:
    root = _parse_stub("privacy-act-1988.xml")
    toc = build_toc(root)
    assert toc[0]["eid"] == "part-I"
    assert toc[0]["heading"]
    part_i_sections = [c["eid"] for c in toc[0]["children"]]
    assert "part-I__sec-6" in part_i_sections


# --------------------------------------------------------------------------- #
# build_sections -- new (root, ref_index, style) -> (dict, Counter) signature
# --------------------------------------------------------------------------- #


def test_build_sections_real_s3_text_and_refs() -> None:
    root = _parse_corpus("corp-act-s3.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, tally = build_sections(root, ix)

    html = sections["chapter-1__part-1.1__sec-3"]["html"]
    assert "law of the Commonwealth" in html
    assert "<em>Acts Interpretation Act 1901</em>" in html
    assert '<span class="akn-num">(2)</span>' in html
    assert sum(tally.values()) >= 1


def test_build_sections_returns_the_ref_index_tally_counter() -> None:
    root = _parse_corpus("corp-act-s3.xml")
    ix = build_ref_index(_all_nav_eids(root))
    _, tally = build_sections(root, ix)

    assert isinstance(tally, collections.Counter)
    assert tally is ix.tally
    # corp-act-s3 cites the Constitution (#sec-51 / #sec-122, display text
    # names "the Constitution") and a scrambled #sec-2H -- none resolvable.
    assert set(tally) <= {"resolved", "ambiguous", "unresolved"}
    assert tally["unresolved"] >= 1


def test_build_sections_preserves_heading_from_heading_element() -> None:
    root = _parse_corpus("corp-act-s3.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix)
    assert (
        sections["chapter-1__part-1.1__sec-3"]["heading"]
        == "Constitutional basis for this Act"
    )


def test_build_sections_accepts_a_custom_style_map() -> None:
    class LoudMap(HtmlStyleMap):
        def _emphasis(self, node: Node, children: list[str]) -> str:
            return f'<mark>{"".join(children)}</mark>'

    root = _parse_corpus("corp-act-s3.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix, style=LoudMap())

    html = sections["chapter-1__part-1.1__sec-3"]["html"]
    assert "<mark>Acts Interpretation Act 1901</mark>" in html
    assert "<em>" not in html


def test_build_sections_defaults_to_html_style_map() -> None:
    root = _parse_corpus("itaa97-rate-table.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix)

    (eid,) = list(sections)
    assert '<table class="akn-table">' in sections[eid]["html"]


# --------------------------------------------------------------------------- #
# Schedule clauses -- Task 2: schedule and figure rendering
# --------------------------------------------------------------------------- #


def test_schedule_clause_reaches_bundle_and_toc() -> None:
    root = _parse_corpus("sched-clause.xml")
    idx = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, idx)
    assert any(k.startswith("schedule-1__clause-") for k in sections)

    toc = build_toc(root)
    sched = [n for n in toc if n["eid"].startswith("schedule-")]
    assert sched and any(
        c["eid"].startswith("schedule-1__clause-") for c in sched[0]["children"]
    )


def test_build_sections_skips_sections_without_an_eid() -> None:
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><body>'
        f"<section><heading>No eId</heading>"
        f"<content><p>orphan</p></content></section>"
        f'<section eId="s1"><heading>Kept</heading>'
        f"<content><p>body</p></content></section>"
        f"</body></act></akomaNtoso>"
    )
    sections, _ = build_sections(root, build_ref_index([]))
    assert list(sections) == ["s1"]
