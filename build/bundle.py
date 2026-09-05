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
import copy
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

# Disambiguator for colliding schedule-unit eIds (Task 4). The converter
# flattens schedule Part/Division numbering, so a schedule can legitimately
# contain two distinct <clause> elements sharing one eId (see
# tests/fixtures/corpus/sched-dup-eid.xml and ../lex-au/repo/FUTURE.md). "~"
# does not occur in any eId in the lex-au corpus (verified via
# `grep -ohE 'eId="[^"]*"' corpus/xml/*.xml | grep -c '~'` -> 0), and is a
# safe HTML `id` attribute character and dict key.
_EID_DISAMBIG = "~"

__all__ = ["AKN", "AKN_NS", "build_toc", "build_sections", "_local_tag"]

# Type of the optional between-stages hook: it receives every parsed section as
# ``(eid, node)`` after Stage 1 and before Stage 2, so a caller (``build/cli.py``)
# can emit the IR and mark figure assets on the live nodes before they render.
OnParsed = Callable[[list[tuple[str, Node]]], None]


def _local_tag(el: ET._Element) -> str:
    return el.tag.split("}")[-1] if isinstance(el.tag, str) else ""


def _schedule_units(sched: ET._Element) -> list:
    """Walk one schedule's direct children in document order (Task 3, B1).

    Returns an ordered list of ``("clause", clause_el)`` tuples for a real
    ``<hcontainer name="clause">``, or ``("block", key, run_elements)``
    tuples for a run of loose siblings (``paragraph`` / ``table`` /
    ``content`` / ``p`` / anything else that isn't the schedule's own
    ``<num>``/``<heading>``) grouped between clauses.

    This is the single ordered walk both ``build_toc`` and ``build_sections``
    consume, so schedule navigation and schedule rendering can never list
    units in different orders or under different keys.

    Key selection: a schedule with **no** clause anywhere keys its one run
    (there can only be one, since nothing else triggers a flush) with the
    bare schedule eId. Any schedule that has at least one clause keys every
    run (pre-clause, between-clause, or trailing) as
    ``f"{sched_eid}__block-{n}"`` -- ``had_clause`` is a fixed, whole-schedule
    fact decided up front, not "seen a clause yet in the walk so far".
    """
    sched_eid = sched.get("eId", "") or ""
    had_clause = any(
        _local_tag(c) == "hcontainer" and c.get("name") == "clause" for c in sched
    )
    units: list = []
    run: list[ET._Element] = []
    block_n = 0

    def flush() -> None:
        nonlocal run, block_n
        if not run:
            return
        key = (
            f"{sched_eid}__block-{block_n}"
            if had_clause or block_n > 0
            else sched_eid
        )
        units.append(("block", key, run))
        block_n += 1
        run = []

    for child in sched:
        tag = _local_tag(child)
        if tag == "hcontainer" and child.get("name") == "clause":
            flush()
            units.append(("clause", child))
        elif tag in ("num", "heading"):
            continue
        else:
            run.append(child)
    flush()
    return units


def build_toc(root: ET._Element) -> list[dict]:
    body = root.find(f".//{AKN}body")
    out: list[dict] = (
        [] if body is None
        else [_toc_node(child) for child in body if _local_tag(child) in _STRUCTURAL_TAGS]
    )
    for sched in root.iterfind(
        f".//{AKN}attachments/{AKN}attachment/{AKN}hcontainer[@name='schedule']"
    ):
        children: list[dict] = []
        # Task 4: mirror _add_entry's disambiguation (against a per-schedule
        # set instead of the `sections` dict, which build_toc never sees) so
        # the TOC lists the same keys build_sections actually wrote.
        used: set[str] = set()
        for unit in _schedule_units(sched):
            if unit[0] == "clause":
                clause = unit[1]
                key = _next_free_key(clause.get("eId", ""), lambda k: k in used)
                used.add(key)
                children.append(
                    {
                        "eid": key,
                        "heading": _entry_heading(clause),
                        "children": [],
                    }
                )
            else:
                _, raw_key, _run = unit
                key = _next_free_key(raw_key, lambda k: k in used)
                used.add(key)
                # Synthetic (loose-prose) units have no <heading> of their
                # own; Task 5 adds a proper label.
                children.append({"eid": key, "heading": "", "children": []})
        out.append(
            {
                # Task 5 adds a proper "Schedule N" label; heading-text-only for now.
                "eid": sched.get("eId", ""),
                "heading": _entry_heading(sched),
                "children": children,
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


def _next_free_key(eid: str, taken: Callable[[str], bool]) -> str:
    """The bundle key ``eid`` should resolve to, given ``taken(key)`` -- a
    membership predicate over keys already in use.

    ``eid`` itself if free; otherwise ``f"{eid}{_EID_DISAMBIG}{n}"`` for the
    smallest free ``n`` starting at 2. This is the single disambiguation rule
    shared by :func:`_add_entry` (checked against the ``sections`` dict it is
    about to write into) and :func:`build_toc` (checked against a per-schedule
    ``set`` -- see its schedule loop) so the two never disagree on the key a
    colliding schedule unit gets.
    """
    if not taken(eid):
        return eid
    n = 2
    while taken(f"{eid}{_EID_DISAMBIG}{n}"):
        n += 1
    return f"{eid}{_EID_DISAMBIG}{n}"


def _add_entry(
    sections: dict[str, dict],
    eid: str,
    heading: str,
    html: str,
    counts: "collections.Counter[str]",
) -> str:
    """Record one bundle entry, disambiguating ``eid`` if it collides.

    Schedule clause eIds can repeat across a schedule (the converter flattens
    Part/Division numbering -- see ``tests/fixtures/corpus/sched-dup-eid.xml``
    and ``../lex-au/repo/FUTURE.md``). A colliding ``eid`` would otherwise
    silently overwrite the earlier entry, permanently losing its content.

    On collision the returned key is ``f"{eid}{_EID_DISAMBIG}{n}"`` (n >= 2,
    ``counts["disambiguated_eids"]`` incremented once per collision) and the
    first ``id="{eid}"`` occurrence in ``html`` -- ``render_section`` /
    ``HtmlStyleMap`` always stamp the *original* eid, since ``parse_section``
    has no eid-override hook -- is rewritten to ``id="{key}"`` so
    ``getElementById`` / ``data-eid`` navigation reaches the disambiguated
    unit rather than the first (differently-keyed) one.

    Note: this is a collision axis distinct from -- and not addressed by --
    the duplicate `id=` attributes that can appear *within* one already
    -rendered clause's html (repeated `para-a`/`para-b` siblings sharing an
    eId inside a single clause, e.g. sched-clause.xml's
    schedule-1__clause-70-20); that is baked in by parse.py/stylemap.py before
    `_add_entry` ever sees the html string, so it is out of this function's
    reach (Task 4 report).
    """
    key = _next_free_key(eid, lambda k: k in sections)
    if key != eid:
        counts["disambiguated_eids"] += 1
        html = html.replace(f'id="{eid}"', f'id="{key}"', 1)
    sections[key] = {"heading": heading, "html": html}
    return key


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
        for unit in _schedule_units(sched):
            if unit[0] == "clause":
                clause = unit[1]
                eid = clause.get("eId", "")
                if not eid:
                    continue
                node = parse_section(clause, ref_index)
                heading = _entry_heading(clause)  # Task 5 will refine
                # The returned key (== eid unless _add_entry disambiguated a
                # collision) is captured, not just discarded, per Task 4: it
                # is the actual key this unit landed under in `sections`.
                # build_toc computes the matching key independently (via
                # _next_free_key over its own per-schedule `used` set, since
                # it never sees `sections`) rather than consuming this one --
                # see build_toc's schedule loop -- so it is not threaded
                # further here, but every caller must not silently ignore it.
                _key = _add_entry(
                    sections, eid, heading, render_section(node, active_style), ref_index.tally
                )
            else:
                _, key, run = unit
                # Task 1 BINDING: deepcopy each loose sibling into a detached
                # <hcontainer> -- never move live nodes (that would empty the
                # source schedule, which build_toc / build_sections both read
                # from the same `root` elsewhere).
                wrap = ET.Element(f"{AKN}hcontainer")
                for el in run:
                    wrap.append(copy.deepcopy(el))
                node = parse_section(wrap, ref_index)
                # Synthetic units have no <heading> of their own; Task 5
                # refines schedule-unit labelling.
                _key = _add_entry(
                    sections, key, "", render_section(node, active_style), ref_index.tally
                )

    return sections, ref_index.tally
