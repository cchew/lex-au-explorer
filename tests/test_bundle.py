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
