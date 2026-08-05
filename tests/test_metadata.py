from pathlib import Path
from build.metadata import load_corpus_index, build_site_index

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_corpus_index_parses_acts():
    acts = load_corpus_index(FIXTURES / "mini-corpus-index.json", xml_dir=FIXTURES / "xml")
    assert set(acts) == {"privacy-act-1988", "income-tax-assessment-act-1997"}
    privacy = acts["privacy-act-1988"]
    assert privacy.name == "Privacy Act 1988"
    assert privacy.title_id == "C2004A03712"
    assert privacy.comp_id == "C2026C00227"
    assert privacy.effective_date == "2026-06-04"
    assert privacy.legislation_url == "https://www.legislation.gov.au/C2004A03712/latest/text"
    assert privacy.year == 1988
    assert privacy.number == 119


def test_load_corpus_index_flags_split_by_part_by_source_size(tmp_path):
    # 6MB source file should be flagged; the fixture privacy-act-1988.xml is tiny.
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    (xml_dir / "big-act.xml").write_bytes(b"x" * (6 * 1024 * 1024))
    (xml_dir / "small-act.xml").write_bytes(b"x" * 1024)
    index_path = tmp_path / "index.json"
    index_path.write_text(
        '{"acts": {'
        '"big-act": {"name": "Big Act", "title_id": "C1", "comp_id": "C2", '
        '"year": 2020, "number": 1, "effective_date": "2026-01-01", "xml_path": "xml/big-act.xml"}, '
        '"small-act": {"name": "Small Act", "title_id": "C3", "comp_id": "C4", '
        '"year": 2020, "number": 2, "effective_date": "2026-01-01", "xml_path": "xml/small-act.xml"}'
        '}, "updated_at": "2026-08-01"}'
    )
    acts = load_corpus_index(index_path, xml_dir=xml_dir)
    assert acts["big-act"].split_by_part is True
    assert acts["small-act"].split_by_part is False


def test_build_site_index_shape():
    acts = load_corpus_index(FIXTURES / "mini-corpus-index.json", xml_dir=FIXTURES / "xml")
    site_index = build_site_index(acts)
    assert {"title", "slug", "frbr_uri", "split_by_part", "year", "number"} <= set(site_index[0])
    titles = {e["title"] for e in site_index}
    assert titles == {"Privacy Act 1988", "Income Tax Assessment Act 1997"}
