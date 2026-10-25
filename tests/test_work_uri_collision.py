"""Two corpus Acts sharing one FRBR work URI (SIS Regulations 1994 = SR 1994 No. 57 and the Training
Guarantee (Administration) Amendment Act 1994 = Act No. 57 of 1994, both /akn/au/act/1994/57) must each
get only their own terms. lex-au-graph keeps them apart under different graph ids; the explorer must
query by the graph id for (work URI, title id), not by the bare work URI."""
import json
from pathlib import Path

from lexaugraph.graph import LexAuGraph

from build.cli import build_site

URI = "/akn/au/act/1994/57"

_XML = """<?xml version='1.0' encoding='UTF-8'?>
<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0">
  <act name="act">
    <meta><identification source="#lex-au">
      <FRBRWork><FRBRthis value="{uri}/!main"/><FRBRuri value="{uri}"/>
        <FRBRdate date="1994-01-01" name="Generation"/><FRBRauthor href="#parliament"/></FRBRWork>
      <FRBRExpression><FRBRthis value="{uri}/eng@{d}/!main"/><FRBRuri value="{uri}/eng@{d}"/>
        <FRBRdate date="{d}" name="Generation"/><FRBRauthor href="#parliament"/>
        <FRBRlanguage language="eng"/></FRBRExpression>
    </identification></meta>
    <body>{body}</body>
  </act>
</akomaNtoso>
"""

_REGS_BODY = """
    <part eId="part-1"><num>1</num><heading>Preliminary</heading>
      <section eId="part-1__sec-1.03"><num>1.03</num><heading>Definitions</heading>
        <content><p><term refersTo="#term-fund">fund</term> means <def>a superannuation fund.</def></p></content>
      </section>
      <section eId="part-1__sec-1.05"><num>1.05</num><heading>Meaning of member</heading>
        <content><p><term refersTo="#term-member--part-1__sec-1.05">member</term> means <def>a person in the fund.</def></p>
        <p>A member of a fund may leave.</p></content>
      </section>
      <section eId="part-1__sec-1.06"><num>1.06</num><heading>Leaving</heading>
        <content><p>A <ref href="#term-fund">fund</ref> may be wound up.</p></content>
      </section>
    </part>"""

_ACT_BODY = """
    <section eId="sec-1"><num>1</num><heading>Short title</heading>
      <content><p>This Act may be cited as the Training Guarantee (Administration) Amendment Act 1994.</p></content>
    </section>
    <section eId="sec-3"><num>3</num><heading>Interpretation</heading>
      <content><p>A fund member is not affected.</p></content>
    </section>"""

REGS = "superannuation-industry-(supervision)-regulations-1994"
ACT = "training-guarantee-(administration)-amendment-act-1994"


def _corpus(root: Path) -> Path:
    (root / "xml").mkdir(parents=True)
    acts = {}
    for slug, name, title_id, d, body in (
        (REGS, "Superannuation Industry (Supervision) Regulations 1994", "F1996B00580", "2026-07-01", _REGS_BODY),
        (ACT, "Training Guarantee (Administration) Amendment Act 1994", "C2004A04733", "1994-04-07", _ACT_BODY),
    ):
        (root / "xml" / f"{slug}.xml").write_text(_XML.format(uri=URI, d=d, body=body))
        acts[slug] = {"name": name, "title_id": title_id, "comp_id": title_id, "year": 1994, "number": 57,
                      "effective_date": d, "xml_path": f"xml/{slug}.xml", "aliases": []}
    (root / "index.json").write_text(json.dumps({"acts": acts, "structure_version": 2}))
    return root


def test_acts_sharing_a_work_uri_get_only_their_own_terms(tmp_path):
    corpus = _corpus(tmp_path / "corpus")
    g = LexAuGraph()
    g.build(corpus)
    graph_path = tmp_path / "graph.json"
    g.save(graph_path)

    out = tmp_path / "data"
    build_site(corpus_index=corpus / "index.json", xml_dir=corpus / "xml", graph_path=graph_path, out_dir=out)

    regs = json.loads((out / f"{REGS}.json").read_text())
    act = json.loads((out / f"{ACT}.json").read_text())
    # the bundle keeps lex-au's work URI; only the graph lookup is disambiguated
    assert regs["frbr_uri"] == act["frbr_uri"] == URI
    assert act["terms"] == []
    assert sorted(t["term"] for t in regs["terms"]) == ["fund", "member"]
    member = next(t for t in regs["terms"] if t["term"] == "member")
    assert member["defs"][0]["scope"] == "part-1__sec-1.05"


def test_term_refs_resolve_against_the_instruments_own_graph_id(tmp_path):
    """The resolver adapter must be bound to the graph id (not the bare work URI): "fund" is defined only
    by the Regulations, so a #term-fund ref resolves to its definition section only on the ``~`` id."""
    corpus = _corpus(tmp_path / "corpus")
    g = LexAuGraph()
    g.build(corpus)
    graph_path = tmp_path / "graph.json"
    g.save(graph_path)
    out = tmp_path / "data"
    build_site(corpus_index=corpus / "index.json", xml_dir=corpus / "xml", graph_path=graph_path, out_dir=out)

    regs = json.loads((out / f"{REGS}.json").read_text())
    html = regs["sections"]["part-1__sec-1.06"]["html"]
    assert "part-1__sec-1.03" in html, html
