import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import lxml.etree as ET
from typer.testing import CliRunner

from build.cli import (
    app,
    build_site,
    _collect_section_eids,
    _make_on_parsed,
    _nav_eids,
    _write_split_bundle,
    _TermResolverAdapter,
)
from build.ir import Node
from build.render import render_section
from build.stylemap import HtmlStyleMap

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


class _FakeGraph:
    @staticmethod
    def load(path):
        return object()


class _FakeResolver:
    """Stands in for lexaugraph.resolver.DefinitionResolver: only the two
    methods build_site touches (get_act_definitions for the bundle, and
    resolve_definition via the RefIndex term adapter)."""

    def __init__(self, graph):
        self._graph = graph

    def get_act_definitions(self, act_frbr_uri):
        if act_frbr_uri == "/akn/au/act/1988/119":
            return [
                {
                    "term": "personal information",
                    "display_term": "personal information",
                    "section_eid": "part-I__sec-6",
                    "definition_text": "means information about an identified individual",
                    "act_alike": False,
                }
            ]
        return []

    def resolve_definition(self, term, act_frbr_uri, section_eid=None):
        return None


def test_bundle_has_terms_not_definitions(tmp_path):
    """No graph -> resolver is None -> the bundle still carries a terms list
    (empty) and never the old definitions map."""
    out_dir = tmp_path / "data"
    build_site(
        corpus_index=FIXTURES / "mini-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,
        out_dir=out_dir,
    )
    bundle = json.loads((out_dir / "privacy-act-1988.json").read_text())
    assert "definitions" not in bundle
    assert bundle["terms"] == []


def test_bundle_terms_come_from_get_act_definitions(tmp_path, monkeypatch):
    """With a resolver, build_site calls get_act_definitions once per Act and
    ships every term through build_terms into bundle['terms']."""
    monkeypatch.setattr("lexaugraph.graph.LexAuGraph", _FakeGraph)
    monkeypatch.setattr("lexaugraph.resolver.DefinitionResolver", _FakeResolver)

    out_dir = tmp_path / "data"
    build_site(
        corpus_index=FIXTURES / "mini-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=tmp_path / "graph.json",  # presence triggers the resolver path; never read
        out_dir=out_dir,
    )
    bundle = json.loads((out_dir / "privacy-act-1988.json").read_text())
    assert "definitions" not in bundle
    assert isinstance(bundle["terms"], list)
    pi = next(t for t in bundle["terms"] if t["term"] == "personal information")
    assert pi["defs"][0]["eid"].endswith("sec-6")
    assert pi["display"] == "personal information"


def test_build_site_flags_a_recorded_exception_and_infers_current_for_the_rest(tmp_path):
    out_dir = tmp_path / "data"
    verification = tmp_path / "verification.json"
    verification.write_text(
        json.dumps(
            {
                "generated_at": "2026-08-28",
                "acts": {
                    # the only recorded exception -> stale
                    "C2004A03712": {
                        "checked_at": "2026-08-28",
                        "repealed": False,
                        "live_comp_id": "C2026C00301",
                        "live_effective_date": "2026-07-01",
                    }
                },
            }
        )
    )

    build_site(
        corpus_index=FIXTURES / "mini-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,
        out_dir=out_dir,
        verification_path=verification,
    )

    privacy = json.loads((out_dir / "privacy-act-1988.json").read_text())
    assert privacy["verification"] == {
        "status": "stale",
        "checked_at": "2026-08-28",
        "live_comp_id": "C2026C00301",
        "live_effective_date": "2026-07-01",
    }

    # not in the exception list, but the run completed -> current as of the run date
    itaa = json.loads((out_dir / "income-tax-assessment-act-1997.json").read_text())
    assert itaa["verification"] == {"status": "current", "checked_at": "2026-08-28"}


def test_build_site_omits_verification_when_run_never_completed(tmp_path):
    out_dir = tmp_path / "data"
    verification = tmp_path / "verification.json"
    verification.write_text(json.dumps({"generated_at": None, "acts": {}}))

    build_site(
        corpus_index=FIXTURES / "mini-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,
        out_dir=out_dir,
        verification_path=verification,
    )

    privacy = json.loads((out_dir / "privacy-act-1988.json").read_text())
    assert "verification" not in privacy


def test_build_site_omits_verification_when_no_file_given(tmp_path):
    out_dir = tmp_path / "data"
    build_site(
        corpus_index=FIXTURES / "mini-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,
        out_dir=out_dir,
    )
    privacy = json.loads((out_dir / "privacy-act-1988.json").read_text())
    assert "verification" not in privacy


def test_cli_entry_point_invokes_build_site(tmp_path):
    """Exercises the actual Typer `app` the installed console-script calls,
    not just build_site() directly -- this is what would have caught the
    broken pyproject.toml entry-point wiring (main() called as a plain
    function, bypassing Typer's option parsing)."""
    corpus_dir = tmp_path / "corpus"
    (corpus_dir / "xml").mkdir(parents=True)
    (corpus_dir / "index.json").write_text(
        (FIXTURES / "mini-corpus-index.json").read_text()
    )
    for xml_file in (FIXTURES / "xml").iterdir():
        (corpus_dir / "xml" / xml_file.name).write_text(xml_file.read_text())

    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["--corpus-dir", str(corpus_dir), "--out", str(out_dir)],
    )

    assert result.exit_code == 0, result.output
    index = json.loads((out_dir / "index.json").read_text())
    slugs = {e["slug"] for e in index}
    assert "privacy-act-1988" in slugs


def test_cli_help_does_not_crash():
    """Regression test for the entry-point bug: `main()` decorated with
    @app.command() but pyproject.toml pointing the console-script at
    build.cli:main (a plain function call, bypassing Typer parsing)
    crashed on --help with TypeError before any real logic ran."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "corpus-dir" in result.output


def test_write_split_bundle_writes_one_file_per_part_plus_index(tmp_path):
    toc = [
        {
            "eid": "part-I",
            "heading": "Part I Preliminary",
            "children": [
                {"eid": "part-I__sec-1", "heading": "sec 1", "children": []},
                {"eid": "part-I__sec-2", "heading": "sec 2", "children": []},
            ],
        },
        {
            "eid": "part-II",
            "heading": "Part II Operative provisions",
            "children": [
                {"eid": "part-II__sec-10", "heading": "sec 10", "children": []},
            ],
        },
    ]
    sections = {
        "part-I__sec-1": {"heading": "sec 1", "html": "<p>one</p>"},
        "part-I__sec-2": {"heading": "sec 2", "html": "<p>two</p>"},
        "part-II__sec-10": {"heading": "sec 10", "html": "<p>ten</p>"},
    }
    terms = [
        {"term": "foo", "display": "foo",
         "defs": [{"text": "def of foo", "eid": "part-I__sec-1"}]},
        {"term": "bar", "display": "bar",
         "defs": [{"text": "def of bar", "eid": "part-II__sec-10"}]},
    ]
    bundle_meta = {
        "frbr_uri": "/akn/au/act/2000/1",
        "title": "Big Act",
        "title_id": "C2000A00001",
        "legislation_url": "https://www.legislation.gov.au/C2000A00001/latest/text",
        "comp_id": "C2026C00001",
        "effective_date": "2026-01-01",
        "toc": toc,
        "sections": sections,
        "terms": terms,
        "raw_xml_url": "https://huggingface.co/datasets/cchew/lex-au/resolve/main/xml/big-act.xml",
        "split_by_part": True,
    }

    out_dir = tmp_path / "data"
    out_dir.mkdir()
    _write_split_bundle(out_dir, "big-act", toc, sections, terms, bundle_meta)

    part_i = json.loads((out_dir / "big-act" / "part-I.json").read_text())
    assert set(part_i["sections"]) == {"part-I__sec-1", "part-I__sec-2"}
    assert {t["term"] for t in part_i["terms"]} == {"foo"}

    part_ii = json.loads((out_dir / "big-act" / "part-II.json").read_text())
    assert set(part_ii["sections"]) == {"part-II__sec-10"}
    assert {t["term"] for t in part_ii["terms"]} == {"bar"}

    index_bundle = json.loads((out_dir / "big-act.json").read_text())
    assert index_bundle["split_by_part"] is True
    assert index_bundle["sections"] == {}
    assert index_bundle["terms"] == []
    assert "definitions" not in index_bundle
    assert index_bundle["title"] == "Big Act"


def test_write_split_bundle_includes_term_used_here_defined_elsewhere(tmp_path):
    """A term defined in one Part but *used* in another rides in the second
    Part's bundle too, so the reader can resolve it there."""
    toc = [
        {"eid": "part-I", "heading": "P1", "children": [
            {"eid": "part-I__sec-1", "heading": "s1", "children": []}]},
        {"eid": "part-II", "heading": "P2", "children": [
            {"eid": "part-II__sec-10", "heading": "s10", "children": []}]},
    ]
    sections = {
        "part-I__sec-1": {"heading": "s1", "html": "<p>widget means a small device.</p>"},
        "part-II__sec-10": {"heading": "s10", "html": "<p>A widget must be registered.</p>"},
    }
    terms = [{"term": "widget", "display": "widget",
              "defs": [{"text": "means a small device", "eid": "part-I__sec-1"}],
              "usedInBody": True}]
    bundle_meta = {"title": "A", "split_by_part": True, "toc": toc,
                   "sections": sections, "terms": terms}
    out_dir = tmp_path / "data"
    out_dir.mkdir()
    _write_split_bundle(out_dir, "a", toc, sections, terms, bundle_meta)

    part_ii = json.loads((out_dir / "a" / "part-II.json").read_text())
    assert [t["term"] for t in part_ii["terms"]] == ["widget"]
    assert part_ii["terms"][0]["usedInBody"] is True


def test_write_split_bundle_recomputes_usedInBody_per_part_without_mutating_terms(tmp_path):
    """Carry #2: build a fresh list of copied dicts per Part. A term that rides
    a Part only because it is defined there, but whose surface form is absent
    from that Part's prose, loses usedInBody in that Part's copy -- and the
    Act-level list plus its dicts are left untouched."""
    toc = [
        {"eid": "part-I", "heading": "P1", "children": [
            {"eid": "part-I__sec-1", "heading": "s1", "children": []}]},
        {"eid": "part-II", "heading": "P2", "children": [
            {"eid": "part-II__sec-10", "heading": "s10", "children": []}]},
    ]
    sections = {
        "part-I__sec-1": {"heading": "s1", "html": "<p>In this Act, X means a device.</p>"},
        "part-II__sec-10": {"heading": "s10", "html": "<p>A widget must be registered.</p>"},
    }
    act_terms = [{"term": "widget", "display": "widget",
                  "defs": [{"text": "means a device", "eid": "part-I__sec-1"}],
                  "usedInBody": True}]
    before = json.loads(json.dumps(act_terms))
    bundle_meta = {"title": "A", "split_by_part": True, "toc": toc,
                   "sections": sections, "terms": act_terms}
    out_dir = tmp_path / "data"
    out_dir.mkdir()
    _write_split_bundle(out_dir, "a", toc, sections, act_terms, bundle_meta)

    part_i = json.loads((out_dir / "a" / "part-I.json").read_text())
    assert [t["term"] for t in part_i["terms"]] == ["widget"]  # defined here
    assert "usedInBody" not in part_i["terms"][0]              # but not used here

    part_ii = json.loads((out_dir / "a" / "part-II.json").read_text())
    assert part_ii["terms"][0]["usedInBody"] is True           # used here

    assert act_terms == before  # Act-level list + dicts unmutated


def test_write_split_bundle_carries_verification_into_every_part_and_index(tmp_path):
    toc = [{"eid": "part-I", "heading": "Part I", "children": [
        {"eid": "part-I__sec-1", "heading": "sec 1", "children": []},
    ]}]
    sections = {"part-I__sec-1": {"heading": "sec 1", "html": "<p>one</p>"}}
    bundle_meta = {
        "title": "Big Act", "split_by_part": True, "toc": toc,
        "sections": sections, "terms": [],
        "verification": {"status": "stale", "checked_at": "2026-08-28",
                         "live_comp_id": "C2026C00301", "live_effective_date": "2026-07-01"},
    }
    out_dir = tmp_path / "data"
    out_dir.mkdir()

    _write_split_bundle(out_dir, "big-act", toc, sections, [], bundle_meta)

    part_i = json.loads((out_dir / "big-act" / "part-I.json").read_text())
    index_bundle = json.loads((out_dir / "big-act.json").read_text())
    assert part_i["verification"]["status"] == "stale"
    assert index_bundle["verification"]["status"] == "stale"


def test_installed_console_script_help_does_not_crash():
    """Exercises the actual `lex-au-explorer-build` binary installed from
    pyproject.toml's [project.scripts] entry, not just the Typer `app`
    object in-process. CliRunner.invoke(app, ...) bypasses pyproject.toml
    entirely, so it cannot catch a bad entry-point target string (e.g.
    `build.cli:main` pointing at the plain function instead of `build.cli:app`)
    -- only actually running the installed script can. Skipped if the
    console-script isn't on PATH (e.g. package installed non-editable
    without entry points regenerated)."""
    exe = shutil.which("lex-au-explorer-build")
    if exe is None:
        import pytest
        pytest.skip("lex-au-explorer-build console-script not on PATH")

    result = subprocess.run(
        [exe, "--help"], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "corpus-dir" in result.stdout


_STYLE_MAP_MODULE = '''
from build.stylemap import HtmlStyleMap


class _LoudStyleMap(HtmlStyleMap):
    def _emphasis(self, node, children):
        return "<mark>" + "".join(children) + "</mark>"


STYLE_MAP = _LoudStyleMap()
'''


def test_style_map_option_loads_module_level_STYLE_MAP(tmp_path):
    style_map = tmp_path / "loud_map.py"
    style_map.write_text(_STYLE_MAP_MODULE)
    out_dir = tmp_path / "data"

    build_site(
        corpus_index=FIXTURES / "mini-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,
        out_dir=out_dir,
        style_map_path=style_map,
    )

    bundle = json.loads((out_dir / "privacy-act-1988.json").read_text())
    # sec-5B subsec-2 source has <b><i>Australian link</i></b>.
    html = bundle["sections"]["part-I__sec-5B"]["html"]
    assert "<mark>Australian link</mark>" in html
    assert "<em>" not in html and "<strong>" not in html


def test_absent_style_map_uses_default_html_style_map(tmp_path):
    out_dir = tmp_path / "data"
    build_site(
        corpus_index=FIXTURES / "mini-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,
        out_dir=out_dir,
    )
    bundle = json.loads((out_dir / "privacy-act-1988.json").read_text())
    html = bundle["sections"]["part-I__sec-5B"]["html"]
    assert "<strong><em>Australian link</em></strong>" in html


def test_emit_ir_writes_one_node_dict_json_per_section(tmp_path):
    out_dir = tmp_path / "data"
    ir_dir = tmp_path / "ir"

    build_site(
        corpus_index=FIXTURES / "mini-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,
        out_dir=out_dir,
        emit_ir_dir=ir_dir,
    )

    ir_file = ir_dir / "privacy-act-1988" / "part-I__sec-6.json"
    assert ir_file.exists()
    node = json.loads(ir_file.read_text())
    assert node["kind"] == "section"
    assert node["attrs"]["eid"] == "part-I__sec-6"
    assert node["attrs"]["heading"] == "Interpretation"
    assert isinstance(node["children"], list)
    # A section with no <section> children is not written under emit-ir for the
    # empty ITAA stub.
    assert not (ir_dir / "income-tax-assessment-act-1997").exists()


def test_ref_tally_json_shape_per_act_and_total(tmp_path):
    out_dir = tmp_path / "data"
    build_site(
        corpus_index=FIXTURES / "mini-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,
        out_dir=out_dir,
    )

    tally = json.loads((out_dir / "ref-tally.json").read_text())
    assert set(tally["privacy-act-1988"]) == {"resolved", "ambiguous", "unresolved"}
    assert all(isinstance(v, int) for v in tally["privacy-act-1988"].values())

    # privacy-act-1988 sec-13: #part-I__sec-6 resolves, href="" does not.
    assert tally["privacy-act-1988"]["resolved"] >= 1
    assert tally["privacy-act-1988"]["unresolved"] >= 1

    total = tally["_total"]
    assert set(total) == {"resolved", "ambiguous", "unresolved"}
    for key in total:
        assert total[key] == sum(
            counts[key] for slug, counts in tally.items() if slug != "_total"
        )


def test_nav_eids_collects_structural_levels_and_schedule_clauses():
    root = ET.fromstring(
        '<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0">'
        '<act><body>'
        '<part eId="part-1">'
        '<section eId="part-1__sec-3">'
        '<subsection eId="part-1__sec-3__subsec-1"/>'
        '</section></part>'
        '<hcontainer name="schedule" eId="schedule-1">'
        '<hcontainer name="clause" eId="schedule-1__clause-70-20">'
        '<hcontainer name="subclause" eId="schedule-1__clause-70-20__subclause-1"/>'
        '</hcontainer></hcontainer>'
        '</body></act></akomaNtoso>'
    )
    eids = set(_nav_eids(root))
    assert eids == {
        "part-1",
        "part-1__sec-3",
        "part-1__sec-3__subsec-1",
        "schedule-1__clause-70-20",
        "schedule-1__clause-70-20__subclause-1",
    }
    # name="schedule" hcontainer is structural, not a nav target.
    assert "schedule-1" not in eids


def test_term_resolver_adapter_binds_frbr_uri_and_returns_result():
    calls = []

    class FakeResolver:
        def resolve_definition(self, term, act_frbr_uri, section_eid=None):
            calls.append((term, act_frbr_uri, section_eid))
            return SimpleNamespace(section_eid="part-1__sec-9")

    adapter = _TermResolverAdapter(FakeResolver(), "/akn/au/act/1997/38")
    result = adapter.resolve_definition("financial year")

    assert calls == [("financial year", "/akn/au/act/1997/38", None)]
    assert result.section_eid == "part-1__sec-9"


_AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"

# Synthetic split Act exercising both C1 root causes at once:
#  * a section nested under a camelCase <subDivision> (toc must recurse into it)
#  * two top-level <chapter eId="chapter-7"> nodes (their section eIds must
#    merge, not overwrite)
_SPLIT_INVARIANT_XML = f"""<akomaNtoso xmlns="{_AKN_NS}"><act><body>
  <chapter eId="chapter-7"><heading>Financial services first</heading>
    <section eId="chapter-7__sec-760A"><heading>S1</heading>
      <content><p>alpha</p></content></section>
  </chapter>
  <chapter eId="chapter-7"><heading>Financial services second</heading>
    <section eId="chapter-7__sec-1101A"><heading>S2</heading>
      <content><p>beta</p></content></section>
  </chapter>
  <chapter eId="chapter-1"><heading>Introduction</heading>
    <division eId="chapter-1__dvs-1"><heading>D1</heading>
      <subDivision eId="chapter-1__dvs-1__sdvs-A"><heading>SD A</heading>
        <section eId="chapter-1__dvs-1__sdvs-A__sec-3"><heading>S3</heading>
          <content><p>gamma</p></content></section>
      </subDivision>
    </division>
  </chapter>
</body></act></akomaNtoso>"""


def test_split_bundle_covers_every_source_section_exactly_once(tmp_path):
    """C1 invariant: every ``<section eId>`` in the source XML lands in exactly
    one written split bundle. Regresses (1) toc not recursing into
    ``<subDivision>`` and (2) same-eId top-level toc nodes overwriting each
    other in ``_write_split_bundle``."""
    from build.bundle import AKN as _AKN, build_sections, build_toc
    from build.refindex import build_ref_index as _bri

    root = ET.fromstring(_SPLIT_INVARIANT_XML)
    source_section_eids = {
        el.get("eId") for el in root.iter(f"{_AKN}section") if el.get("eId")
    }
    assert source_section_eids == {
        "chapter-7__sec-760A",
        "chapter-7__sec-1101A",
        "chapter-1__dvs-1__sdvs-A__sec-3",
    }

    toc = build_toc(root)
    # toc must now descend through <subDivision> to reach the nested section.
    assert _collect_section_eids(
        next(n for n in toc if n["eid"] == "chapter-1")
    ) == {"chapter-1__dvs-1__sdvs-A__sec-3"}

    sections, _ = build_sections(root, _bri([]))
    bundle_meta = {"title": "Synthetic Split Act", "split_by_part": True,
                   "toc": toc, "sections": sections, "terms": []}

    out_dir = tmp_path / "data"
    out_dir.mkdir()
    _write_split_bundle(out_dir, "synthetic-split", toc, sections, [], bundle_meta)

    seen: dict[str, int] = {}
    for part_file in sorted((out_dir / "synthetic-split").glob("*.json")):
        part_bundle = json.loads(part_file.read_text())
        for eid in part_bundle["sections"]:
            seen[eid] = seen.get(eid, 0) + 1

    assert seen == {eid: 1 for eid in source_section_eids}


def test_make_on_parsed_flips_figure_asset_and_emits_real_img(tmp_path):
    """The two-pass figure marking is the only path that can emit a real
    <img>: when --corpus-images holds the matching file, the parsed figure
    node's `asset` flips True and the style map renders <img src="/data/...">.
    """
    images = tmp_path / "images"
    images.mkdir()
    (images / "act-fig-1.png").write_bytes(b"PNGDATA")
    out_dir = tmp_path / "data"
    out_dir.mkdir()

    fig = Node(
        "figure",
        {"src": "corpus/images/act-fig-1.png", "alt": "", "asset": False},
    )
    section = Node("section", {"eid": "part-1__sec-1"}, [fig])

    _make_on_parsed("act", None, images, out_dir)([("part-1__sec-1", section)])

    assert fig.attrs["asset"] is True
    assert (out_dir / "images" / "act-fig-1.png").read_bytes() == b"PNGDATA"

    html = render_section(section, HtmlStyleMap())
    assert '<img src="/data/images/act-fig-1.png" alt="">' in html
    assert "akn-figure-missing" not in html


def test_collect_section_eids_keeps_schedule_clauses():
    node = {"eid": "schedule-1", "children": [
        {"eid": "schedule-1__clause-2", "children": []},
        {"eid": "schedule-1__clause-2__subclause-1", "children": []}]}
    assert _collect_section_eids(node) == {
        "schedule-1", "schedule-1__clause-2", "schedule-1__clause-2__subclause-1"}


def test_collect_section_eids_keeps_container_head_notes():
    """F1 regression: a Part/Chapter/Division head-note entry
    (``<container eId>__head``, Task 7 / spec B5) is a real bundle key and must
    be collected into its owning Part file for split-by-part Acts. Its last
    ``__``-segment is the bare literal ``head``, which matches none of the
    _KEEP_LAST_SEGMENT_PREFIXES, so before the ``endswith("__head")`` clause
    every such entry was silently dropped from every split Act (1,232 corpus
    entries + as many dead TOC nodes)."""
    node = {
        "eid": "part-2",
        "children": [
            {"eid": "part-2__head", "children": []},
            {
                "eid": "part-2__div-1",
                "children": [
                    {"eid": "part-2__div-1__head", "children": []},
                    {"eid": "part-2__div-1__sec-5", "children": []},
                ],
            },
        ],
    }
    assert _collect_section_eids(node) == {
        "part-2__head",
        "part-2__div-1__head",
        "part-2__div-1__sec-5",
    }
    # A future ``heading-*`` segment must NOT be swept in by the same clause.
    assert _collect_section_eids(
        {"eid": "part-2__heading-note", "children": []}
    ) == set()


def test_write_split_bundle_routes_head_note_into_its_part_file(tmp_path):
    """F1 end-to-end: a container head-note key present in ``sections`` lands in
    the right per-Part file (it is reached only via ``_collect_section_eids``)."""
    toc = [
        {
            "eid": "part-I",
            "heading": "Part I",
            "children": [
                {"eid": "part-I__head", "heading": "Part I — introductory text",
                 "children": []},
                {"eid": "part-I__sec-1", "heading": "sec 1", "children": []},
            ],
        }
    ]
    sections = {
        "part-I__head": {"heading": "Part I — introductory text",
                         "html": "<p>head-note prose</p>"},
        "part-I__sec-1": {"heading": "sec 1", "html": "<p>one</p>"},
    }
    bundle_meta = {"title": "Big Act", "split_by_part": True, "toc": toc,
                   "sections": sections, "terms": []}
    out_dir = tmp_path / "data"
    out_dir.mkdir()

    _write_split_bundle(out_dir, "big-act", toc, sections, [], bundle_meta)

    part_i = json.loads((out_dir / "big-act" / "part-I.json").read_text())
    assert set(part_i["sections"]) == {"part-I__head", "part-I__sec-1"}
    assert part_i["sections"]["part-I__head"]["html"] == "<p>head-note prose</p>"


def test_split_by_part_act_writes_schedule_file(tmp_path, monkeypatch):
    monkeypatch.setattr("build.metadata._SPLIT_BY_PART_THRESHOLD_BYTES", 200)
    out_dir = tmp_path / "data"
    build_site(
        corpus_index=FIXTURES / "split-sched-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,
        out_dir=out_dir,
    )

    sched = json.loads((out_dir / "split-sched-act" / "schedule-1.json").read_text())
    assert "schedule-1__clause-1" in sched["sections"]
    assert "definitions" not in sched
    assert "terms" not in sched

    thin = json.loads((out_dir / "split-sched-act.json").read_text())
    assert thin["sections"] == {}
    assert thin["terms"] == []


def test_schedule_heavy_non_part_act_promoted(tmp_path, monkeypatch):
    monkeypatch.setattr("build.cli._SCHEDULE_SPLIT_BYTES", 200)
    out_dir = tmp_path / "data"
    build_site(
        corpus_index=FIXTURES / "split-sched-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,
        out_dir=out_dir,
    )

    idx = json.loads((out_dir / "split-sched-act.json").read_text())
    assert idx["split_schedules"] is True
    assert idx["sections"]  # body sections still inline
    assert not any(k.startswith("schedule-") for k in idx["sections"])

    sched = json.loads((out_dir / "split-sched-act" / "schedule-1.json").read_text())
    assert "schedule-1__clause-1" in sched["sections"]  # real unit, not empty
    assert "definitions" not in sched
    assert "terms" not in sched


def test_schedule_under_threshold_stays_inline(tmp_path):
    """Negative case: a not-part-split Act whose schedule html is under
    _SCHEDULE_SPLIT_BYTES is written as one plain <slug>.json -- no
    split_schedules flag, schedule units inline, no <slug>/ directory."""
    out_dir = tmp_path / "data"
    build_site(
        corpus_index=FIXTURES / "split-sched-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,
        out_dir=out_dir,
    )

    bundle = json.loads((out_dir / "split-sched-act.json").read_text())
    assert "split_schedules" not in bundle
    assert "schedule-1__clause-1" in bundle["sections"]  # schedule inline
    assert "part-1__sec-1" in bundle["sections"]  # body inline too
    assert not (out_dir / "split-sched-act").exists()  # no split dir


def test_raw_xml_url_points_at_hf_and_no_local_xml(tmp_path):
    """The raw AKN XML is served from the cchew/lex-au HuggingFace dataset,
    not bundled into the build output. `lexau export-hf` uploads the
    contents of corpus/ to the dataset root, so the files live at
    xml/<slug>.xml (no corpus/ prefix)."""
    out_dir = tmp_path / "data"
    build_site(
        corpus_index=FIXTURES / "mini-corpus-index.json",
        xml_dir=FIXTURES / "xml",
        graph_path=None,
        out_dir=out_dir,
    )

    bundle = json.loads((out_dir / "privacy-act-1988.json").read_text())
    assert bundle["raw_xml_url"] == (
        "https://huggingface.co/datasets/cchew/lex-au/resolve/main/xml/"
        "privacy-act-1988.xml"
    )
    assert list(out_dir.glob("*.xml")) == []


def test_collect_section_eids_recurses_into_divisions():
    toc_node = {
        "eid": "part-I",
        "heading": "Part I",
        "children": [
            {
                "eid": "part-I__div-1",
                "heading": "Division 1",
                "children": [
                    {"eid": "part-I__div-1__sec-1", "heading": "sec 1", "children": []},
                ],
            },
            {"eid": "part-I__sec-2", "heading": "sec 2", "children": []},
        ],
    }
    eids = _collect_section_eids(toc_node)
    assert eids == {"part-I__div-1__sec-1", "part-I__sec-2"}
