from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from pathlib import Path
import lxml.etree as ET

AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
AKN = f"{{{AKN_NS}}}"

logger = logging.getLogger(__name__)

_SPLIT_BY_PART_THRESHOLD_BYTES = 5 * 1024 * 1024  # 5MB raw XML


def _parse_frbr_uri(xml_path: Path) -> str:
    if not xml_path.exists():
        return ""
    try:
        root = ET.parse(str(xml_path)).getroot()
        work_uri_el = root.find(f".//{AKN}FRBRWork/{AKN}FRBRuri")
        return work_uri_el.get("value", "").rstrip("/") if work_uri_el is not None else ""
    except ET.XMLSyntaxError:
        return ""


@dataclass
class ActMeta:
    slug: str
    name: str
    title_id: str
    comp_id: str
    effective_date: str
    xml_path: Path
    split_by_part: bool
    year: int
    number: int
    frbr_uri: str = ""  # populated by Task 5's XML parse, empty until then

    @property
    def legislation_url(self) -> str:
        return f"https://www.legislation.gov.au/{self.title_id}/latest/text"


# lex-au index.json "structure_version" values the explorer has been tested against
# (lex-au corpus.py STRUCTURE_VERSION): 1 flat schedules, 2 nested schedules and
# quotedStructure amendments. An unknown value means lex-au changed shape again;
# refuse rather than render a silently incomplete site.
SUPPORTED_STRUCTURE_VERSIONS = frozenset({1, 2})


class UnsupportedCorpusStructure(RuntimeError):
    pass


def check_structure_version(index: dict) -> None:
    version = index.get("structure_version")
    if version is None:
        logger.warning(
            "corpus index.json has no structure_version (pre-2026-10-15 lex-au export); "
            "assuming a supported shape"
        )
        return
    if version not in SUPPORTED_STRUCTURE_VERSIONS:
        raise UnsupportedCorpusStructure(
            f"corpus structure_version {version!r} is not supported by lex-au-explorer "
            f"(supported: {sorted(SUPPORTED_STRUCTURE_VERSIONS)}). lex-au changed the AKN "
            "shape; update and re-test the parsers (tests/parity) before building."
        )


def load_corpus_index(index_path: Path, xml_dir: Path) -> dict[str, ActMeta]:
    data = json.loads(index_path.read_text())
    check_structure_version(data)
    result: dict[str, ActMeta] = {}
    for slug, entry in data["acts"].items():
        xml_path = xml_dir.parent / entry["xml_path"]
        size = xml_path.stat().st_size if xml_path.exists() else 0
        result[slug] = ActMeta(
            slug=slug,
            name=entry["name"],
            title_id=entry["title_id"],
            comp_id=entry["comp_id"],
            effective_date=entry["effective_date"],
            xml_path=xml_path,
            split_by_part=size >= _SPLIT_BY_PART_THRESHOLD_BYTES,
            year=entry["year"],
            number=entry["number"],
            frbr_uri=_parse_frbr_uri(xml_path),
        )
    return result


def build_site_index(acts: dict[str, ActMeta]) -> list[dict]:
    return [
        {
            "title": a.name,
            "slug": a.slug,
            "frbr_uri": a.frbr_uri,
            "split_by_part": a.split_by_part,
            "year": a.year,
            "number": a.number,
        }
        for a in sorted(acts.values(), key=lambda a: a.name)
    ]
