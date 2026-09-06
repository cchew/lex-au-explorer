from build.assemble import assemble_bundle
from build.metadata import ActMeta
from pathlib import Path


def test_assemble_bundle_shape():
    meta = ActMeta(
        slug="privacy-act-1988", name="Privacy Act 1988", title_id="C2004A03712",
        comp_id="C2026C00227", effective_date="2026-06-04",
        xml_path=Path("x.xml"), split_by_part=False, frbr_uri="/akn/au/act/1988/119",
        year=1988, number=119,
    )
    toc = [{"eid": "part-I", "heading": "Part 1", "children": []}]
    sections = {"part-I__sec-6": {"heading": "Definitions", "html": "<p>...</p>"}}
    definitions = {"personal information": {"text": "means...", "section_eid": "part-I__sec-6"}}

    bundle = assemble_bundle(meta, toc, sections, definitions)

    assert bundle["frbr_uri"] == "/akn/au/act/1988/119"
    assert bundle["title"] == "Privacy Act 1988"
    assert bundle["title_id"] == "C2004A03712"
    assert bundle["legislation_url"] == "https://www.legislation.gov.au/C2004A03712/latest/text"
    assert bundle["comp_id"] == "C2026C00227"
    assert bundle["effective_date"] == "2026-06-04"
    assert bundle["year"] == 1988
    assert bundle["number"] == 119
    assert bundle["toc"] == toc
    assert bundle["sections"] == sections
    assert bundle["definitions"] == definitions
    assert bundle["raw_xml_url"] == (
        "https://huggingface.co/datasets/cchew/lex-au/resolve/main/xml/"
        "privacy-act-1988.xml"
    )
    assert bundle["split_by_part"] is False
    assert "verification" not in bundle


def test_assemble_bundle_includes_verification_when_provided():
    meta = ActMeta(
        slug="privacy-act-1988", name="Privacy Act 1988", title_id="C2004A03712",
        comp_id="C2026C00227", effective_date="2026-06-04",
        xml_path=Path("x.xml"), split_by_part=False, frbr_uri="/akn/au/act/1988/119",
        year=1988, number=119,
    )
    verification = {"status": "current", "checked_at": "2026-08-28"}

    bundle = assemble_bundle(meta, [], {}, {}, verification=verification)

    assert bundle["verification"] == verification
