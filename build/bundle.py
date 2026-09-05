"""Bundle stage: table of contents + per-section HTML.

``build_toc`` is unchanged: a structural walk of ``<body>`` producing the
reader's navigation tree.

``build_sections`` is a thin two-stage pipeline. For each ``<section>`` it runs
Stage 1 (:func:`build.parse.parse_section` -> semantic :class:`~build.ir.Node`
tree) then Stage 2 (:func:`build.render.render_section` with a
:class:`~build.stylemap.StyleMap`). Extraction and presentation are no longer
entangled here; the old ``_render_*`` helpers moved to ``build/parse.py``,
``build/render.py`` and ``build/stylemap.py``.
"""

from __future__ import annotations

import collections
from typing import Callable, Optional

import lxml.etree as ET

from build.ir import Node
from build.refindex import RefIndex
from build.stylemap import HtmlStyleMap, StyleMap

AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
AKN = f"{{{AKN_NS}}}"

# AKN 3.0 spells the element ``subDivision`` (camelCase); the lower-case
# ``subdivision`` never occurs in the corpus but is kept for safety.
_STRUCTURAL_TAGS = {
    "part", "division", "subdivision", "subDivision", "chapter", "section",
}

__all__ = ["AKN", "AKN_NS", "build_toc", "build_sections", "_local_tag"]

# Type of the optional between-stages hook: it receives every parsed section as
# ``(eid, node)`` after Stage 1 and before Stage 2, so a caller (``build/cli.py``)
# can emit the IR and mark figure assets on the live nodes before they render.
OnParsed = Callable[[list[tuple[str, Node]]], None]


def _local_tag(el: ET._Element) -> str:
    return el.tag.split("}")[-1] if isinstance(el.tag, str) else ""


def build_toc(root: ET._Element) -> list[dict]:
    body = root.find(f".//{AKN}body")
    out: list[dict] = (
        [] if body is None
        else [_toc_node(child) for child in body if _local_tag(child) in _STRUCTURAL_TAGS]
    )
    for sched in root.iterfind(
        f".//{AKN}attachments/{AKN}attachment/{AKN}hcontainer[@name='schedule']"
    ):
        clauses = [
            {"eid": c.get("eId", ""), "heading": _entry_heading(c), "children": []}
            for c in sched.iterfind(f"{AKN}hcontainer[@name='clause']")
        ]
        out.append(
            {
                # Task 5 adds a proper "Schedule N" label; heading-text-only for now.
                "eid": sched.get("eId", ""),
                "heading": _entry_heading(sched),
                "children": clauses,
            }
        )
    return out


def _toc_node(el: ET._Element) -> dict:
    heading_el = el.find(f"{AKN}heading")
    num_el = el.find(f"{AKN}num")
    heading_text = (heading_el.text or "").strip() if heading_el is not None else ""
    num_text = (num_el.text or "").strip() if num_el is not None else ""
    heading = f"{num_text} {heading_text}".strip()
    children = [_toc_node(c) for c in el if _local_tag(c) in _STRUCTURAL_TAGS]
    return {"eid": el.get("eId", ""), "heading": heading, "children": children}


def _entry_heading(el: ET._Element) -> str:
    """``<heading>`` text only. Task 5 prepends the clause's ``<num>``."""
    heading_el = el.find(f"{AKN}heading")
    return (heading_el.text or "").strip() if heading_el is not None else ""


def _add_entry(
    sections: dict[str, dict],
    eid: str,
    heading: str,
    html: str,
    counts: "collections.Counter[str]",
) -> str:
    """Record one bundle entry under ``eid``.

    ``counts`` is unused here -- it is threaded through now so every call site
    already passes it. Task 4 makes collisions (schedule paragraph eIds repeat
    within a clause, see the parity spike) safe and starts recording
    disambiguation events into ``counts``.
    """
    sections[eid] = {"heading": heading, "html": html}
    return eid


def build_sections(
    root: ET._Element,
    ref_index: RefIndex,
    style: StyleMap | None = None,
    *,
    on_parsed: Optional[OnParsed] = None,
) -> tuple[dict[str, dict], "collections.Counter[str]"]:
    """Parse then render every ``<section>`` under ``root``.

    Returns ``({eid: {"heading", "html"}}, ref_index.tally)``. ``heading`` is
    still the ``<heading>`` element's text. ``style`` defaults to
    :class:`~build.stylemap.HtmlStyleMap`. There is no ``resolver`` /
    ``act_frbr_uri`` parameter -- cross-reference resolution is entirely
    ``ref_index``'s job (Stage 1 calls ``ref_index.resolve``).

    ``on_parsed`` (keyword-only) is an optional hook called once with the full
    ``[(eid, node), ...]`` list after Stage 1 and before Stage 2. ``build_site``
    uses it for ``--emit-ir`` and for the two-pass figure-asset marking; normal
    callers omit it.
    """
    # Lazy: build.parse imports AKN / _local_tag back from this module.
    from build.parse import parse_section
    from build.render import render_section

    active_style = style if style is not None else HtmlStyleMap()

    parsed: list[tuple[str, str, Node]] = []
    for section in root.iter(f"{AKN}section"):
        eid = section.get("eId", "")
        if not eid:
            continue
        heading_el = section.find(f"{AKN}heading")
        heading = (heading_el.text or "").strip() if heading_el is not None else ""
        parsed.append((eid, heading, parse_section(section, ref_index)))

    if on_parsed is not None:
        on_parsed([(eid, node) for eid, _, node in parsed])

    sections: dict[str, dict] = {
        eid: {"heading": heading, "html": render_section(node, active_style)}
        for eid, heading, node in parsed
    }

    for sched in root.iterfind(
        f".//{AKN}attachments/{AKN}attachment/{AKN}hcontainer[@name='schedule']"
    ):
        for clause in sched.iterfind(f"{AKN}hcontainer[@name='clause']"):
            eid = clause.get("eId", "")
            if not eid:
                continue
            node = parse_section(clause, ref_index)
            heading = _entry_heading(clause)  # Task 5 will refine
            _add_entry(
                sections, eid, heading, render_section(node, active_style), ref_index.tally
            )

    return sections, ref_index.tally
