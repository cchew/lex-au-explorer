import json
from pathlib import Path
from build.cli import build_site

FIXTURES = Path(__file__).parent / "fixtures"


def test_build_site_writes_index_and_bundle(tmp_path):
    out_dir = tmp_path / "data"
    build_site(
        corpus_index=FIXTURES / "mini-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,  # None -> skip definition resolution, used for this fixture-only test
        out_dir=out_dir,
    )
    index = json.loads((out_dir / "index.json").read_text())
    slugs = {e["slug"] for e in index}
    assert "privacy-act-1988" in slugs

    bundle = json.loads((out_dir / "privacy-act-1988.json").read_text())
    assert bundle["title"] == "Privacy Act 1988"
    assert "part-I__sec-6" in bundle["sections"]
