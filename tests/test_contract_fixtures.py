"""Contract tests: the explorer build must render every structural shape in lex-au's golden set.

Fixtures come from the pinned `lexau-contract-fixtures` package (pyproject dev extras). The core
invariant: every non-empty paragraph under an <attachment> in the source appears in the built Act
bundle. Normalisation follows tests/parity/README.md (quotes, dashes, whitespace, short bracketed
list markers) and compares with whitespace removed, because inline markup splits words.
"""
import html
import json
import os
import re

import pytest
from lxml import etree

try:
    import lexau_contract_fixtures as fx
except ImportError:  # pragma: no cover
    if os.environ.get("CI"):
        raise
    pytest.skip("lexau-contract-fixtures not installed", allow_module_level=True)

from build.cli import build_site
from build.metadata import SUPPORTED_STRUCTURE_VERSIONS

AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"
SLUGS = list(fx.manifest()["fixtures"])


def _norm(s: str) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), (" ", " ")):
        s = s.replace(a, b)
    s = re.sub(r"[‐-―-]", "-", s)
    s = re.sub(r"\s+", "", s)
    return re.sub(r"\([a-zA-Z0-9]{1,4}\)", "", s)


def _toc_eids(nodes):
    for n in nodes:
        yield n["eid"]
        yield from _toc_eids(n["children"])


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    d = fx.corpus_dir()
    build_site(corpus_index=d / "index.json", xml_dir=d / "xml", graph_path=None, out_dir=out)
    return out


def _bundle(built, slug):
    return json.loads((built / f"{slug}.json").read_text())


def test_explorer_supports_the_fixture_structure_version():
    assert fx.structure_version() in SUPPORTED_STRUCTURE_VERSIONS


def test_every_fixture_builds_a_bundle(built):
    for slug in SLUGS:
        assert (built / f"{slug}.json").exists(), slug


@pytest.mark.parametrize("slug", SLUGS)
def test_every_attachment_paragraph_is_rendered(built, slug):
    b = _bundle(built, slug)
    rendered = _norm(
        " ".join(v["html"] for v in b["sections"].values())
        + json.dumps(b.get("preface", ""))
        + json.dumps(b["terms"])
    )
    root = etree.parse(str(fx.corpus_dir() / "xml" / f"{slug}.xml")).getroot()
    missing = []
    for att in root.iter(f"{AKN}attachment"):
        for p in att.iter(f"{AKN}p"):
            text = _norm("".join(p.itertext()))
            if any(c.isalpha() for c in text) and text not in rendered:
                missing.append(" ".join("".join(p.itertext()).split())[:80])
    assert missing == []


@pytest.mark.parametrize("slug", SLUGS)
def test_every_source_schedule_is_in_the_toc(built, slug):
    b = _bundle(built, slug)
    root = etree.parse(str(fx.corpus_dir() / "xml" / f"{slug}.xml")).getroot()
    schedules = {
        h.get("eId")
        for att in root.iter(f"{AKN}attachment")
        for h in att.iter(f"{AKN}hcontainer")
        if h.get("name") == "schedule"
    }
    assert schedules <= set(_toc_eids(b["toc"]))


@pytest.mark.parametrize("slug", SLUGS)
def test_every_section_has_a_heading_or_body(built, slug):
    for eid, s in _bundle(built, slug)["sections"].items():
        assert s["html"].strip() or s["heading"].strip(), eid


@pytest.mark.parametrize("slug", SLUGS)
def test_every_clause_and_amendment_item_is_its_own_section(built, slug):
    sections = _bundle(built, slug)["sections"]
    root = etree.parse(str(fx.corpus_dir() / "xml" / f"{slug}.xml")).getroot()
    missing = [
        h.get("eId")
        for att in root.iter(f"{AKN}attachment")
        for h in att.iter(f"{AKN}hcontainer")
        if h.get("name") in ("clause", "item") and h.get("eId") and h.get("eId") not in sections
    ]
    assert missing == []
