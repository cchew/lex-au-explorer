from __future__ import annotations
from typing import Any
from build.metadata import ActMeta


def assemble_bundle(
    meta: ActMeta,
    toc: list[dict],
    sections: dict[str, dict],
    definitions: dict[str, dict],
) -> dict[str, Any]:
    return {
        "frbr_uri": meta.frbr_uri,
        "title": meta.name,
        "title_id": meta.title_id,
        "legislation_url": meta.legislation_url,
        "comp_id": meta.comp_id,
        "effective_date": meta.effective_date,
        "toc": toc,
        "sections": sections,
        "definitions": definitions,
        "raw_xml_url": f"/data/{meta.slug}.xml",
        "split_by_part": meta.split_by_part,
    }
