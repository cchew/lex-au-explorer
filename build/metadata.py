from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path

_SPLIT_BY_PART_THRESHOLD_BYTES = 5 * 1024 * 1024  # 5MB raw XML


@dataclass
class ActMeta:
    slug: str
    name: str
    title_id: str
    comp_id: str
    effective_date: str
    xml_path: Path
    split_by_part: bool
    frbr_uri: str = ""  # populated by Task 5's XML parse, empty until then

    @property
    def legislation_url(self) -> str:
        return f"https://www.legislation.gov.au/{self.title_id}/latest/text"


def load_corpus_index(index_path: Path, xml_dir: Path) -> dict[str, ActMeta]:
    data = json.loads(index_path.read_text())
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
        )
    return result


def build_site_index(acts: dict[str, ActMeta]) -> list[dict]:
    return [
        {
            "title": a.name,
            "slug": a.slug,
            "frbr_uri": a.frbr_uri,
            "split_by_part": a.split_by_part,
        }
        for a in sorted(acts.values(), key=lambda a: a.name)
    ]
