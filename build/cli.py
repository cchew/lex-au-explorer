from __future__ import annotations
import json
import shutil
from pathlib import Path
from typing import Optional

import lxml.etree as ET
import typer

from build.metadata import load_corpus_index, build_site_index, ActMeta
from build.bundle import build_toc, build_sections
from build.assemble import assemble_bundle
from build.verification import derive_status

DEFAULT_VERIFICATION_PATH = Path("web/verification.json")

app = typer.Typer()


def build_site(
    corpus_index: Path,
    xml_dir: Path,
    graph_path: Optional[Path],
    out_dir: Path,
    verification_path: Optional[Path] = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    acts = load_corpus_index(corpus_index, xml_dir=xml_dir)

    resolver = None
    if graph_path is not None:
        from lexaugraph.graph import LexAuGraph
        from lexaugraph.resolver import DefinitionResolver
        resolver = DefinitionResolver(LexAuGraph.load(graph_path))

    verification_entries: dict[str, dict] = {}
    if verification_path is not None and verification_path.exists():
        verification_entries = json.loads(verification_path.read_text()).get("acts", {})

    for meta in acts.values():
        if not meta.xml_path.exists():
            print(f"Warning: {meta.xml_path} not found -- skipping {meta.slug}")
            continue
        try:
            root = ET.parse(str(meta.xml_path)).getroot()
        except ET.XMLSyntaxError as e:
            print(f"Warning: malformed XML for {meta.slug} ({e}) -- skipping")
            continue

        toc = build_toc(root)
        sections = build_sections(root)
        definitions = _resolve_all_definitions(resolver, meta.frbr_uri, sections) if resolver else {}
        verification = derive_status(verification_entries.get(meta.title_id), meta.comp_id)
        bundle = assemble_bundle(meta, toc, sections, definitions, verification=verification)

        if meta.split_by_part:
            _write_split_bundle(out_dir, meta.slug, toc, sections, definitions, bundle)
        else:
            (out_dir / f"{meta.slug}.json").write_text(json.dumps(bundle))

        if meta.xml_path.exists():
            shutil.copy(meta.xml_path, out_dir / f"{meta.slug}.xml")

    (out_dir / "index.json").write_text(json.dumps(build_site_index(acts)))


def _resolve_all_definitions(resolver, act_frbr_uri: str, sections: dict[str, dict]) -> dict[str, dict]:
    """Resolve every term marked data-term in every section, keyed by term
    (last-resolved-wins is fine here since terms are looked up per-section
    by the frontend at render time, not globally -- see Task 9)."""
    import re
    from build.definitions import resolve_section_definitions

    all_defs: dict[str, dict] = {}
    for section_eid, section in sections.items():
        term_names = set(re.findall(r'data-term="([^"]+)"', section["html"]))
        if not term_names:
            continue
        all_defs.update(resolve_section_definitions(resolver, act_frbr_uri, section_eid, term_names))
    return all_defs


def _write_split_bundle(
    out_dir: Path,
    slug: str,
    toc: list[dict],
    sections: dict[str, dict],
    definitions: dict[str, dict],
    bundle_meta: dict,
) -> None:
    """For the small number of largest Acts: one bundle per top-level Part
    instead of one bundle for the whole Act, so no single fetch carries
    the full Act (see the design spec's split_by_part note)."""
    part_dir = out_dir / slug
    part_dir.mkdir(parents=True, exist_ok=True)
    part_section_eids: dict[str, set[str]] = {}
    for part in toc:
        eids = _collect_section_eids(part)
        part_section_eids[part["eid"]] = eids

    for part_eid, eids in part_section_eids.items():
        part_sections = {k: v for k, v in sections.items() if k in eids}
        part_definitions = {
            term: d for term, d in definitions.items() if d["section_eid"] in eids
        }
        part_bundle = dict(bundle_meta)
        part_bundle["sections"] = part_sections
        part_bundle["definitions"] = part_definitions
        (part_dir / f"{part_eid}.json").write_text(json.dumps(part_bundle))

    index_bundle = dict(bundle_meta)
    index_bundle["sections"] = {}
    index_bundle["definitions"] = {}
    (out_dir / f"{slug}.json").write_text(json.dumps(index_bundle))


def _collect_section_eids(toc_node: dict) -> set[str]:
    eids = {toc_node["eid"]} if toc_node["eid"].split("__")[-1].startswith("sec-") else set()
    for child in toc_node.get("children", []):
        eids |= _collect_section_eids(child)
    return eids


@app.command()
def main(
    corpus_dir: Path = typer.Option(..., "--corpus-dir", help="Path to lex-au's corpus/ directory"),
    graph: Optional[Path] = typer.Option(None, "--graph", help="Path to lex-au-graph's graph.json"),
    out: Path = typer.Option(Path("web/data"), "--out", help="Output directory for generated JSON"),
    verification: Optional[Path] = typer.Option(
        None,
        "--verification",
        help=(
            "Path to a verification.json written by lex-au-explorer-verify. "
            f"Defaults to {DEFAULT_VERIFICATION_PATH} when it exists. No network access."
        ),
    ),
) -> None:
    verification_path = verification or DEFAULT_VERIFICATION_PATH
    if not verification_path.exists():
        verification_path = None
    build_site(
        corpus_index=corpus_dir / "index.json",
        xml_dir=corpus_dir / "xml",
        graph_path=graph,
        out_dir=out,
        verification_path=verification_path,
    )
    typer.echo(f"Site data written to {out}")
