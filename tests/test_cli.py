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
    _nav_eids,
    _write_split_bundle,
    _TermResolverAdapter,
)

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
    definitions = {
        "foo": {"text": "def of foo", "section_eid": "part-I__sec-1"},
        "bar": {"text": "def of bar", "section_eid": "part-II__sec-10"},
    }
    bundle_meta = {
        "frbr_uri": "/akn/au/act/2000/1",
        "title": "Big Act",
        "title_id": "C2000A00001",
        "legislation_url": "https://www.legislation.gov.au/C2000A00001/latest/text",
        "comp_id": "C2026C00001",
        "effective_date": "2026-01-01",
        "toc": toc,
        "sections": sections,
        "definitions": definitions,
        "raw_xml_url": "/data/big-act.xml",
        "split_by_part": True,
    }

    out_dir = tmp_path / "data"
    out_dir.mkdir()
    _write_split_bundle(out_dir, "big-act", toc, sections, definitions, bundle_meta)

    part_i = json.loads((out_dir / "big-act" / "part-I.json").read_text())
    assert set(part_i["sections"]) == {"part-I__sec-1", "part-I__sec-2"}
    assert set(part_i["definitions"]) == {"foo"}

    part_ii = json.loads((out_dir / "big-act" / "part-II.json").read_text())
    assert set(part_ii["sections"]) == {"part-II__sec-10"}
    assert set(part_ii["definitions"]) == {"bar"}

    index_bundle = json.loads((out_dir / "big-act.json").read_text())
    assert index_bundle["split_by_part"] is True
    assert index_bundle["sections"] == {}
    assert index_bundle["definitions"] == {}
    assert index_bundle["title"] == "Big Act"


def test_write_split_bundle_carries_verification_into_every_part_and_index(tmp_path):
    toc = [{"eid": "part-I", "heading": "Part I", "children": [
        {"eid": "part-I__sec-1", "heading": "sec 1", "children": []},
    ]}]
    sections = {"part-I__sec-1": {"heading": "sec 1", "html": "<p>one</p>"}}
    bundle_meta = {
        "title": "Big Act", "split_by_part": True, "toc": toc,
        "sections": sections, "definitions": {},
        "verification": {"status": "stale", "checked_at": "2026-08-28",
                         "live_comp_id": "C2026C00301", "live_effective_date": "2026-07-01"},
    }
    out_dir = tmp_path / "data"
    out_dir.mkdir()

    _write_split_bundle(out_dir, "big-act", toc, sections, {}, bundle_meta)

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
                   "toc": toc, "sections": sections, "definitions": {}}

    out_dir = tmp_path / "data"
    out_dir.mkdir()
    _write_split_bundle(out_dir, "synthetic-split", toc, sections, {}, bundle_meta)

    seen: dict[str, int] = {}
    for part_file in sorted((out_dir / "synthetic-split").glob("*.json")):
        part_bundle = json.loads(part_file.read_text())
        for eid in part_bundle["sections"]:
            seen[eid] = seen.get(eid, 0) + 1

    assert seen == {eid: 1 for eid in source_section_eids}


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
