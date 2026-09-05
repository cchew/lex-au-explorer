from __future__ import annotations
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Callable, Optional

import lxml.etree as ET
import typer

from build.metadata import load_corpus_index, build_site_index, ActMeta
from build.assets import copy_figure_assets
from build.bundle import build_toc, build_sections, build_preface, _local_tag
from build.ir import Node
from build.refindex import build_ref_index
from build.stylemap import HtmlStyleMap, StyleMap
from build.assemble import assemble_bundle
from build.verification import derive_status

DEFAULT_VERIFICATION_PATH = Path("web/verification.json")

# Navigable element tags whose ``eId`` feeds the per-Act cross-reference index.
_NAV_TAGS: frozenset[str] = frozenset(
    {
        "section", "part", "division", "subdivision", "subDivision", "chapter",
        "subsection", "paragraph", "subparagraph",
    }
)
_NAV_HCONTAINER_NAMES: frozenset[str] = frozenset({"clause", "subclause"})

_TALLY_KEYS: tuple[str, ...] = ("resolved", "ambiguous", "unresolved")

app = typer.Typer()


class _TermResolverAdapter:
    """Bind an Act's FRBR URI so ``RefIndex`` can call a 1-argument
    ``resolve_definition(term)`` (parity spike note, section D).

    ``lexaugraph.resolver.DefinitionResolver.resolve_definition`` really takes
    ``(term, act_frbr_uri, section_eid=None)`` and returns a ``DefinitionResult``
    (which carries ``.section_eid``) or ``None``. ``RefIndex`` has no Act URI in
    scope and reads ``.section_eid`` off whatever this returns, so the adapter
    forwards the bound URI and hands back the ``DefinitionResult`` unchanged.
    """

    def __init__(self, resolver: object, act_frbr_uri: str) -> None:
        self._resolver = resolver
        self._act_frbr_uri = act_frbr_uri

    def resolve_definition(self, term: str) -> object | None:
        return self._resolver.resolve_definition(term, self._act_frbr_uri)


def _nav_eids(root: ET._Element) -> list[str]:
    """Every navigable ``eId`` in the Act: the structural levels plus the
    schedule ``clause`` / ``subclause`` hcontainers that carry an ``eId``."""
    eids: list[str] = []
    for el in root.iter():
        eid = el.get("eId")
        if not eid:
            continue
        tag = _local_tag(el)
        if tag in _NAV_TAGS or (
            tag == "hcontainer" and el.get("name") in _NAV_HCONTAINER_NAMES
        ):
            eids.append(eid)
    return eids


def _load_style_map(style_map_path: Optional[Path]) -> StyleMap:
    """Load ``STYLE_MAP`` from a Python file, or fall back to the default."""
    if style_map_path is None:
        return HtmlStyleMap()
    spec = importlib.util.spec_from_file_location(
        "_lexau_user_style_map", str(style_map_path)
    )
    if spec is None or spec.loader is None:
        raise typer.BadParameter(f"cannot load style map from {style_map_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return module.STYLE_MAP
    except AttributeError as exc:
        raise typer.BadParameter(
            f"{style_map_path} does not define a module-level STYLE_MAP"
        ) from exc


def _iter_figures(node: Node):
    if node.kind == "figure":
        yield node
    for child in node.children:
        yield from _iter_figures(child)


def _tally_dict(counter) -> dict[str, int]:
    return {key: int(counter.get(key, 0)) for key in _TALLY_KEYS}


def build_site(
    corpus_index: Path,
    xml_dir: Path,
    graph_path: Optional[Path],
    out_dir: Path,
    verification_path: Optional[Path] = None,
    style_map_path: Optional[Path] = None,
    emit_ir_dir: Optional[Path] = None,
    corpus_images_dir: Optional[Path] = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    acts = load_corpus_index(corpus_index, xml_dir=xml_dir)

    if corpus_images_dir is None:
        # Sibling of xml/ in the lex-au corpus. Normally absent -- the lex-au
        # repo ships no images/ directory (parity spike note, section B).
        corpus_images_dir = xml_dir.parent / "images"

    style = _load_style_map(style_map_path)

    resolver = None
    if graph_path is not None:
        from lexaugraph.graph import LexAuGraph
        from lexaugraph.resolver import DefinitionResolver
        resolver = DefinitionResolver(LexAuGraph.load(graph_path))

    verification_entries: dict[str, dict] = {}
    verification_ran_at: Optional[str] = None
    if verification_path is not None and verification_path.exists():
        _vdata = json.loads(verification_path.read_text())
        verification_entries = _vdata.get("acts", {})
        verification_ran_at = _vdata.get("generated_at")

    ref_tally: dict[str, dict[str, int]] = {}

    for meta in acts.values():
        if not meta.xml_path.exists():
            print(f"Warning: {meta.xml_path} not found -- skipping {meta.slug}")
            continue
        try:
            root = ET.parse(str(meta.xml_path)).getroot()
        except ET.XMLSyntaxError as e:
            print(f"Warning: malformed XML for {meta.slug} ({e}) -- skipping")
            continue

        term_resolver = (
            _TermResolverAdapter(resolver, meta.frbr_uri)
            if resolver is not None
            else None
        )
        ref_index = build_ref_index(_nav_eids(root), term_resolver=term_resolver)

        toc = build_toc(root)
        sections, act_tally = build_sections(
            root,
            ref_index,
            style,
            on_parsed=_make_on_parsed(meta.slug, emit_ir_dir, corpus_images_dir, out_dir),
        )
        ref_tally[meta.slug] = _tally_dict(act_tally)

        definitions = _resolve_all_definitions(resolver, meta.frbr_uri, sections) if resolver else {}
        verification = derive_status(
            verification_entries.get(meta.title_id), meta.comp_id, ran_at=verification_ran_at
        )
        bundle = assemble_bundle(meta, toc, sections, definitions, verification=verification)
        preface = build_preface(root)
        if preface:
            bundle["preface"] = preface

        if meta.split_by_part:
            _write_split_bundle(out_dir, meta.slug, toc, sections, definitions, bundle)
        else:
            (out_dir / f"{meta.slug}.json").write_text(json.dumps(bundle))

        if meta.xml_path.exists():
            shutil.copy(meta.xml_path, out_dir / f"{meta.slug}.xml")

    (out_dir / "index.json").write_text(json.dumps(build_site_index(acts)))
    _write_ref_tally(out_dir, ref_tally)


def _make_on_parsed(
    slug: str,
    emit_ir_dir: Optional[Path],
    corpus_images_dir: Path,
    out_dir: Path,
) -> Callable[[list[tuple[str, Node]]], None]:
    """Build the between-stages hook: mark figure assets (two-pass), then emit
    the IR. Marking runs first so an emitted ``figure`` node reflects whether
    its image was actually found."""

    def _on_parsed(pairs: list[tuple[str, Node]]) -> None:
        srcs = [
            fig.attrs.get("src", "")
            for _, node in pairs
            for fig in _iter_figures(node)
        ]
        missing = copy_figure_assets(corpus_images_dir, srcs, out_dir / "images")
        for _, node in pairs:
            for fig in _iter_figures(node):
                basename = Path(str(fig.attrs.get("src", ""))).name
                fig.attrs["asset"] = bool(basename) and basename not in missing

        if emit_ir_dir is not None and pairs:
            act_ir_dir = emit_ir_dir / slug
            act_ir_dir.mkdir(parents=True, exist_ok=True)
            for eid, node in pairs:
                (act_ir_dir / f"{Path(eid).name}.json").write_text(
                    json.dumps(node.to_dict())
                )

    return _on_parsed


def _write_ref_tally(out_dir: Path, ref_tally: dict[str, dict[str, int]]) -> None:
    total = {key: 0 for key in _TALLY_KEYS}
    for counts in ref_tally.values():
        for key in _TALLY_KEYS:
            total[key] += counts.get(key, 0)
    payload = dict(sorted(ref_tally.items()))
    payload["_total"] = total
    (out_dir / "ref-tally.json").write_text(json.dumps(payload))


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
        # A split Act can carry two top-level TOC nodes with the same eId
        # (Corp Act has two ``chapter-7``; ITAA-97 repeats ``chapter-2`` /
        # ``chapter-3``). Merge their section eIds instead of letting the
        # second node's set overwrite the first.
        eids = _collect_section_eids(part)
        part_section_eids.setdefault(part["eid"], set()).update(eids)

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
    style_map: Optional[Path] = typer.Option(
        None,
        "--style-map",
        help=(
            "Path to a Python file exposing a module-level STYLE_MAP. "
            "Absent: the default HtmlStyleMap (legislation.gov.au visual parity)."
        ),
    ),
    emit_ir: Optional[Path] = typer.Option(
        None,
        "--emit-ir",
        help=(
            "Directory to also write the raw semantic IR to, one "
            "<emit-ir>/<act-slug>/<eid>.json per section (Node.to_dict())."
        ),
    ),
    corpus_images: Optional[Path] = typer.Option(
        None,
        "--corpus-images",
        help=(
            "Directory of figure image files. Default: <corpus-dir>/images "
            "(sibling of xml/). Normally absent -- figures then render as a "
            "labelled placeholder."
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
        style_map_path=style_map,
        emit_ir_dir=emit_ir,
        # None -> build_site owns the single <corpus-dir>/images default.
        corpus_images_dir=corpus_images,
    )
    typer.echo(f"Site data written to {out}")
