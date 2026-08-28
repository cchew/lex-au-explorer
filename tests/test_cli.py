import json
import shutil
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from build.cli import app, build_site, _write_split_bundle, _collect_section_eids

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


def test_build_site_embeds_verification_and_recomputes_against_current_compilation(tmp_path):
    out_dir = tmp_path / "data"
    verification = tmp_path / "verification.json"
    verification.write_text(
        json.dumps(
            {
                "generated_at": "2026-08-28",
                "acts": {
                    # live compilation differs from the corpus copy -> stale
                    "C2004A03712": {
                        "checked_at": "2026-08-28",
                        "repealed": False,
                        "live_comp_id": "C2026C00301",
                        "live_effective_date": "2026-07-01",
                    },
                    # stored observation now matches the corpus comp_id -> recomputed current
                    "C2004A05138": {
                        "checked_at": "2026-08-28",
                        "repealed": False,
                        "live_comp_id": "C2026C00100",
                        "live_effective_date": "2026-01-01",
                    },
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

    itaa = json.loads((out_dir / "income-tax-assessment-act-1997.json").read_text())
    assert itaa["verification"] == {"status": "current", "checked_at": "2026-08-28"}


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
