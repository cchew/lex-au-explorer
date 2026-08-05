from pathlib import Path
import lxml.etree as ET
from build.bundle import build_toc, build_sections, AKN

FIXTURES = Path(__file__).parent / "fixtures"


def _parse(name: str) -> ET._Element:
    return ET.parse(str(FIXTURES / "xml" / name)).getroot()


def test_build_toc_nests_part_division_section():
    root = _parse("privacy-act-1988.xml")
    toc = build_toc(root)
    assert toc[0]["eid"] == "part-I"
    assert toc[0]["heading"]
    part_i_sections = [c["eid"] for c in toc[0]["children"]]
    assert "part-I__sec-6" in part_i_sections


def test_build_sections_marks_defined_terms():
    root = _parse("privacy-act-1988.xml")
    sections = build_sections(root)
    s6 = sections["part-I__sec-6"]
    assert 'data-term="personal information"' in s6["html"]


def test_build_sections_preserves_heading():
    root = _parse("privacy-act-1988.xml")
    sections = build_sections(root)
    assert sections["part-I__sec-6"]["heading"]


def test_build_sections_renders_subsection_body_text():
    # Regression test: sec-5B's own <content> is just the label "Agencies";
    # the substantive text lives in <subsection> children, which the
    # renderer previously ignored entirely (only the top-level <content>
    # was read), producing near-empty output for most real sections.
    root = _parse("privacy-act-1988.xml")
    sections = build_sections(root)
    html = sections["part-I__sec-5B"]["html"]
    assert "Agencies" in html
    assert "extends to an act done" in html


def test_build_sections_numbers_subsections_without_duplicating_embedded_numbers():
    root = _parse("privacy-act-1988.xml")
    sections = build_sections(root)
    html = sections["part-I__sec-5B"]["html"]
    # subsec-1's text has no embedded "(1)" -- the renderer must add it.
    assert "(1)" in html
    # subsec-2's text already starts with "(2)" in the source XML -- the
    # renderer must not add a second one.
    assert "(2) (2)" not in html
    assert "(2)" in html


def test_build_sections_includes_authorial_notes():
    root = _parse("privacy-act-1988.xml")
    sections = build_sections(root)
    html = sections["part-I__sec-5B"]["html"]
    assert "will not breach an Australian Privacy Principle" in html


def test_build_sections_strips_inline_formatting_tags_to_plain_text():
    root = _parse("privacy-act-1988.xml")
    sections = build_sections(root)
    html = sections["part-I__sec-5B"]["html"]
    assert "Australian link" in html
