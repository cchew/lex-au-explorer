from __future__ import annotations
from typing import Any
from build.metadata import ActMeta

# Raw AKN XML is served from the cchew/lex-au HuggingFace dataset rather than
# bundled into the build output. `lexau export-hf` uploads the *contents* of
# the corpus/ directory to the dataset repo root, so the files live at
# xml/<slug>.xml with no corpus/ prefix.
_HF_XML_BASE = "https://huggingface.co/datasets/cchew/lex-au/resolve/main/xml"


def assemble_bundle(
    meta: ActMeta,
    toc: list[dict],
    sections: dict[str, dict],
    definitions: dict[str, dict],
    verification: dict | None = None,
) -> dict[str, Any]:
    bundle = {
        "frbr_uri": meta.frbr_uri,
        "title": meta.name,
        "title_id": meta.title_id,
        "legislation_url": meta.legislation_url,
        "comp_id": meta.comp_id,
        "effective_date": meta.effective_date,
        "year": meta.year,
        "number": meta.number,
        "toc": toc,
        "sections": sections,
        "definitions": definitions,
        "raw_xml_url": f"{_HF_XML_BASE}/{meta.slug}.xml",
        "split_by_part": meta.split_by_part,
    }
    if verification is not None:
        bundle["verification"] = verification
    return bundle
