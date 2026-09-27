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
import re
from typing import Callable, Optional

import lxml.etree as ET

from build.ir import Node
from build.refindex import RefIndex
from build.stylemap import HtmlStyleMap, StyleMap, _render_inline

AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
AKN = f"{{{AKN_NS}}}"

# AKN 3.0 spells the element ``subDivision`` (camelCase); the lower-case
# ``subdivision`` never occurs in the corpus but is kept for safety.
_STRUCTURAL_TAGS = {
    "part", "division", "subdivision", "subDivision", "chapter", "section",
}

# Task 7: containers whose direct block content (outside any ``<section>``) is
# a head-note -- ``_STRUCTURAL_TAGS`` minus ``section`` (a ``<section>``'s own
# direct content is rendered by ``build_sections``'s per-section pass, not
# here). ``_HEADNOTE_BLOCK_TAGS`` is the set of direct children that count as
# that content; ``<num>``/``<heading>``, nested structural containers,
# ``<section>`` and ``<authorialNote>`` are all excluded.
_HEADNOTE_CONTAINER_TAGS = _STRUCTURAL_TAGS - {"section"}
_HEADNOTE_BLOCK_TAGS = {"content", "p", "blockList", "table"}

# Disambiguator, now used for exactly TWO collision axes, both unrelated to
# B4 / schedule-unit content (Task 22 removed the THIRD, schedule-unit axis
# that used to share this suffix -- see ``_SCHEDULE_LEAF_NAMES``'s comment
# below, and ``_add_headnote_entry``'s docstring for why one axis survives in
# THIS module):
#
# 1. A WITHIN-UNIT duplicate id (repeated ``para-a``/``para-b`` siblings
#    sharing an eid one level below a single clause/item) -- handled by
#    :func:`build.parse._dedupe_eids`, which imports this constant so the two
#    surviving axes agree on notation.
# 2. A body-level container head-note key collision (two ``<part>``/
#    ``<chapter>``/... elements sharing one number at different locations in
#    the SAME Act's body -- e.g. Corp Act's two ``chapter-7``s, ITAA-97's
#    repeated ``chapter-2``/``chapter-3``, see ``build/cli.py``'s
#    ``_write_split_bundle`` comment) -- handled by
#    :func:`_add_headnote_entry` below. Real, still-occurring, and entirely
#    unrelated to schedule content: B4 only touched how a schedule's OWN
#    content is structured, never body Part/Chapter numbering.
#
# "~" does not occur in any eId in the lex-au corpus (verified via
# `grep -ohE 'eId="[^"]*"' corpus/xml/*.xml | grep -c '~'` -> 0), and is a
# safe HTML `id` attribute character and dict key.
_EID_DISAMBIG = "~"

# Schedule-unit leaf tags: a real ``<hcontainer name="clause">`` (plain,
# non-amending schedule) or ``<hcontainer name="item">`` (a B4
# amendment-instruction item -- lex-au v0.10.0). Both are navigable,
# individually-rendered bundle units.
_SCHEDULE_LEAF_NAMES = frozenset({"clause", "item"})

# Schedule-unit GROUPING wrapper tags (Task 22, B4's B1 increment): a real
# Part/Division/Chapter/subDivision boundary inside a schedule, or an
# ``amendedAct`` citation boundary (the amended Act's own name, heading-only,
# introducing a run of ``item``s). Each wraps a further run of leaf units,
# nested groups, and/or loose content -- ``_schedule_units`` recurses into
# these; they are TOC branch nodes with no bundle entry of their own (unless
# they carry loose lead-in content, which becomes a "block" unit exactly like
# the schedule's own top level -- see ``_schedule_units``'s docstring).
_SCHEDULE_GROUP_NAMES = frozenset(
    {"chapter", "part", "division", "subDivision", "amendedAct"}
)

# Collision history (why there is no disambiguator here any more): pre-B4,
# ~99% of schedule-unit eId collisions were `_CLAUSE_RE` / SECTION-branch
# false-positive clause fabrication from amendment-instruction items,
# embedded schedule TOCs, and un-wrapped quoted/inserted provisions in the
# converter -- not lost source Part/Division grouping (~1.2%; there is no
# source AKN to begin with, the source is DOCX). See
# tests/fixtures/corpus/sched-dup-eid.xml, which now documents that pre-B4
# bug as a regression fixture rather than a case to paper over.
#
# The converter-side fix (B4) is shipped and live in the corpus this repo
# builds from -- lex-au commits b88624a..c71da41, folded into the full
# re-convert and released as v0.10.0 (2026-09-26). A schedule-unit eId
# collision reaching `_add_entry` today can therefore only mean a converter
# regression, not a case needing a suffixed key -- `_add_entry` and
# `build_toc`'s schedule walk both assert instead of disambiguating.

# Label for a synthetic schedule "block" unit -- a run of loose siblings
# (paragraph / table / content / p) that ``_schedule_units`` groups between (or
# before / after) real ``<clause>`` elements. These have no ``<num>``/
# ``<heading>`` of their own, so before this they reached the TOC (and the
# bundle) with ``heading == ""``, which ``ActToc.vue`` renders as an empty
# clickable row (4,188 blank rows across 1,672 Acts). One consistent short
# label is applied for every block unit, whether it keys under the bare
# ``schedule-N`` eId (a no-clause schedule's single whole-schedule run) or
# ``schedule-N__block-<n>`` (a leading / between-clause / trailing run). The
# same string is written in BOTH ``build_toc`` and ``build_sections`` so the
# TOC child and the bundle entry always agree.
_SCHEDULE_BLOCK_LABEL = "Introductory text"

__all__ = [
    "AKN", "AKN_NS", "build_toc", "build_sections", "build_preface", "_local_tag",
]

# Fallback-candidate ToC-line rejection (Task 6, no <longTitle> in this
# corpus -- see build_preface). A real cover-page/ToC <p> either starts with
# a structural label ("Part 1", "Division 2", or a bare numbered entry like
# "5  Definitions" / "1.1  Name of Regulations") or ends in a trailing page
# number ("Endnote 4-Amendment history  76"); genuine "An Act ..." prose does
# neither. Matched against whitespace-normalised text (see _norm_ws), so the
# corpus's NBSP/tab formatting between a Part/Division word and its number
# does not defeat the "\s" here.
_TOC_PREFIX_RE = re.compile(r"^(Part\s|Division\s|\d)")
_TOC_TRAILING_PAGE_RE = re.compile(r"\s\d+$")

# Type of the optional between-stages hook: it receives every parsed section as
# ``(eid, node)`` after Stage 1 and before Stage 2, so a caller (``build/cli.py``)
# can emit the IR and mark figure assets on the live nodes before they render.
OnParsed = Callable[[list[tuple[str, Node]]], None]


def _local_tag(el: ET._Element) -> str:
    return el.tag.split("}")[-1] if isinstance(el.tag, str) else ""


def _schedule_units(container: ET._Element) -> list:
    """Walk one schedule (or one schedule-scoped grouping wrapper)'s direct
    children in document order (Task 3, B1; recursion added Task 22).

    Returns an ordered list of:

    - ``(name, el)`` for a real leaf unit -- ``name`` is the element's own
      ``hcontainer`` ``name`` (``"clause"`` for a plain, non-amending
      schedule; ``"item"`` for a B4 amendment-instruction item).
    - ``("group", el, nested_units)`` for a grouping wrapper
      (``chapter``/``part``/``division``/``subDivision``/``amendedAct`` --
      see ``_SCHEDULE_GROUP_NAMES``) -- ``nested_units`` is this same
      function's result for ``el``'s own children, so a caller recurses by
      simply calling itself on the third tuple element.
    - ``("block", key, run_elements)`` for a run of loose siblings
      (``paragraph`` / ``table`` / ``content`` / ``p`` / anything else that
      isn't ``container``'s own ``<num>``/``<heading>``) grouped between
      leaf/group units.

    This is the single ordered walk both ``build_toc`` and ``build_sections``
    consume, so schedule navigation and schedule rendering can never list
    units in different orders or under different keys.

    Key selection: a container with **no** leaf or group child anywhere keys
    its one run (there can only be one, since nothing else triggers a flush)
    with ``container``'s own bare eId. A container with at least one leaf or
    group child keys every run (leading, between, or trailing) as
    ``f"{container_eid}__block-{n}"`` -- ``had_leaf_or_group`` is a fixed,
    whole-container fact decided up front, not "seen one yet in the walk so
    far". This rule is applied uniformly at every nesting depth (the
    schedule itself, and every grouping wrapper inside it).
    """
    container_eid = container.get("eId", "") or ""
    had_leaf_or_group = any(
        _local_tag(c) == "hcontainer"
        and c.get("name") in (_SCHEDULE_LEAF_NAMES | _SCHEDULE_GROUP_NAMES)
        for c in container
    )
    units: list = []
    run: list[ET._Element] = []
    block_n = 0

    def flush() -> None:
        nonlocal run, block_n
        if not run:
            return
        key = (
            f"{container_eid}__block-{block_n}"
            if had_leaf_or_group or block_n > 0
            else container_eid
        )
        units.append(("block", key, run))
        block_n += 1
        run = []

    for child in container:
        tag = _local_tag(child)
        name = child.get("name")
        if tag == "hcontainer" and name in _SCHEDULE_LEAF_NAMES:
            flush()
            units.append((name, child))
        elif tag == "hcontainer" and name in _SCHEDULE_GROUP_NAMES:
            flush()
            units.append(("group", child, _schedule_units(child)))
        elif tag in ("num", "heading"):
            continue
        else:
            run.append(child)
    flush()
    return units


def _schedule_toc_children(
    container_eid: str, units: list, used: set[str]
) -> list[dict]:
    """Recursive TOC-child builder for one schedule (or one grouping
    wrapper)'s unit list from :func:`_schedule_units` (Task 22).

    ``used`` accumulates every key emitted across the WHOLE schedule (shared
    across all recursion levels, never reset per group) -- the same
    collision domain :func:`_add_entry` checks against (a document-global
    dict), so a schedule-unit eId collision anywhere in the schedule is
    caught the same way regardless of nesting depth (see the module-level
    comment above ``_SCHEDULE_GROUP_NAMES``: this is now an assertion, not a
    disambiguation).
    """
    children: list[dict] = []
    for unit in units:
        kind = unit[0]
        if kind == "group":
            _, group_el, nested_units = unit
            group_eid = group_el.get("eId", "")
            if not group_eid:
                continue
            children.append(
                {
                    "eid": group_eid,
                    "heading": _numbered_heading(group_el),
                    "children": _schedule_toc_children(group_eid, nested_units, used),
                }
            )
        elif kind == "block":
            _, key, _run = unit
            assert key not in used, (
                f"duplicate schedule TOC eid {key!r} -- a schedule-unit eId "
                "collision should not reach the TOC after lex-au v0.10.0's "
                "B4 fix; this indicates a converter regression"
            )
            used.add(key)
            # A no-leaf container's single whole-run keys under its own bare
            # eId (see _schedule_units). That would make a TOC child whose
            # ``eid`` is identical to its parent node's -- a redundant,
            # self-referential nav row (361 such cases in the corpus at the
            # schedule level) and an ambiguous ``getElementById`` target. The
            # parent node itself already navigates there (the reader's
            # ``flattenLeafEids`` falls back to ``[node.eid]`` for a
            # childless node), and ``build_sections`` still writes the
            # bundle entry under this key, so suppress only the duplicate
            # child row.
            if key == container_eid:
                continue
            # Synthetic (loose-prose) block units have no <num>/<heading> of
            # their own; give them one consistent short label so the reader
            # never renders a blank clickable TOC row.
            children.append(
                {"eid": key, "heading": _SCHEDULE_BLOCK_LABEL, "children": []}
            )
        else:
            leaf = unit[1]
            eid = leaf.get("eId", "")
            if not eid:
                # Symmetry with build_sections's leaf branch (which does
                # `if not eid: continue` before ever calling _add_entry): a
                # leaf with no eId gets no `sections` entry there, so it must
                # get no TOC child here either -- otherwise the TOC would
                # list a node the bundle has no content for, breaking the
                # "TOC and bundle never disagree" property Task 4 guarantees.
                continue
            assert eid not in used, (
                f"duplicate schedule TOC eid {eid!r} -- a schedule-unit eId "
                "collision should not reach the TOC after lex-au v0.10.0's "
                "B4 fix; this indicates a converter regression"
            )
            used.add(eid)
            children.append(
                {"eid": eid, "heading": _entry_heading(leaf), "children": []}
            )
    return children


def build_toc(root: ET._Element) -> list[dict]:
    body = root.find(f".//{AKN}body")
    out: list[dict] = (
        [] if body is None
        else [_toc_node(child) for child in body if _local_tag(child) in _STRUCTURAL_TAGS]
    )
    for sched in root.iterfind(
        f".//{AKN}attachments/{AKN}attachment/{AKN}hcontainer[@name='schedule']"
    ):
        sched_eid = sched.get("eId", "")
        used: set[str] = set()
        children = _schedule_toc_children(sched_eid, _schedule_units(sched), used)
        out.append(
            {
                "eid": sched_eid,
                "heading": _schedule_label(sched),
                "children": children,
            }
        )
    return out


def _text(el: ET._Element) -> str:
    return "".join(el.itertext())


def _norm_ws(text: str) -> str:
    return " ".join(text.split())


_MIN_PROSE_WORDS = 5


def _looks_like_prose(p: ET._Element) -> bool:
    """False for a ToC/cover-page line -- see the ``_TOC_*`` regexes' comment
    -- or for one of several further false-fallback shapes measured by
    running this heuristic against the full 3,076-Act corpus (task report
    has the numbers): pre-2000s Acts whose preface has neither an
    "An Act ..." paragraph nor a ``<formula>`` tag overwhelmingly end their
    preface's ``<p>`` run on a bare heading/label rather than either a real
    ToC entry or a real long title --

    * "TABLE OF PROVISIONS" / "TABLE OF PARTS" (a bare all-caps heading),
    * "Short title and citation." (section 1's own heading, bled into the
      preface because the Act has no ToC at all),
    * "Contents" (the ToC's own heading, when the Act's ToC is otherwise
      empty or absent), or
    * the enacting words themselves, untagged as ``<formula>`` and so left
      as a plain trailing ``<p>`` ("BE IT ENACTED by the Queen ...").

    None of these has a trailing page number or a Part/Division/bare-number
    prefix, so the ``_TOC_*`` regexes alone pass all four through as if they
    were prose. The first three are short labels (<=4 words); rejecting
    below :data:`_MIN_PROSE_WORDS` catches them without hand-listing every
    boilerplate label the corpus might use. The "BE IT ENACTED" case is a
    full sentence, long enough to survive a word-count filter, so it gets its
    own explicit prefix check. The all-caps check is redundant with the
    word-count filter for the two known "TABLE OF ..." headings specifically,
    but is kept as a cheap, independent guard against a longer all-caps
    heading elsewhere in the corpus that this task's sampling did not happen
    to surface.

    Empty text (a ``<p>`` with no content) is never prose either; without
    that guard an empty candidate would pass every check vacuously and get
    treated as a real long title.
    """
    text = _norm_ws(_text(p))
    if not text:
        return False
    if _TOC_PREFIX_RE.match(text) or _TOC_TRAILING_PAGE_RE.search(text):
        return False
    if any(c.isalpha() for c in text) and text == text.upper():
        return False  # "TABLE OF PROVISIONS", "TABLE OF PARTS", ...
    if text.lower().startswith("be it enacted"):
        return False  # enacting words mistaken for the fallback long title
    if len(text.split()) < _MIN_PROSE_WORDS:
        return False  # "Short title and citation.", "Contents", ...
    return True


def _fallback_long_title_p(
    pf: ET._Element, formula: Optional[ET._Element]
) -> Optional[ET._Element]:
    """The ``<p>`` immediately before ``formula`` (or the last ``<p>`` in
    ``pf`` if ``formula`` is ``None``), for the ~5.4% of Acts whose preface
    has no unlabelled "An Act ..." paragraph.

    "Immediately before" tolerates non-``<p>`` siblings between the
    candidate and ``formula`` (none are known to occur in the corpus, but
    this is cheap insurance against a structure survey missed): it is the
    last ``<p>`` seen while walking ``pf``'s children up to ``formula``, not
    strictly ``formula``'s direct previous sibling.
    """
    if formula is None:
        ps = pf.findall(f"{AKN}p")
        return ps[-1] if ps else None
    candidate: Optional[ET._Element] = None
    for child in pf:
        if child is formula:
            break
        if _local_tag(child) == "p":
            candidate = child
    return candidate


def build_preface(root: ET._Element) -> Optional[dict]:
    """Extract the Act's long title + enacting formula from ``<preface>``.

    There is no ``<longTitle>`` element in this corpus (parity spike §3.1):
    ``<preface>`` is the full compilation cover page plus table of contents
    -- ``age-discrimination-act-2004`` has 117 direct ``<p>`` children (short
    title, "No. 68, 2004", "Compilation No. 57", "About this compilation"
    boilerplate, then ~90 ToC lines). The actual long title is a single
    unlabelled ``<p>`` beginning "An Act" (case-sensitive); it is the corpus's
    LAST preface ``<p>`` only 37% of the time and is entirely absent in
    ~5.4% of Acts (most commonly Regulations-style instruments made *under*
    an Act rather than an Act itself, which have no "An Act ..." long title
    to begin with).

    Returns ``None`` when ``<preface>`` is absent, or when no "An Act ..."
    paragraph exists and the fallback candidate (see
    :func:`_fallback_long_title_p`) does not read as prose (:func:`_looks_
    like_prose`) -- i.e. it looks like a leaked ToC/cover-page line instead
    of a genuine long title.

    ``long_title`` and ``enacting`` are rendered via
    :func:`build.stylemap._render_inline`, which preserves ``<i>``/``<b>``
    inline emphasis (``parse_section``'s block path would drop it -- see
    that function's docstring).
    """
    pf = root.find(f".//{AKN}preface")
    if pf is None:
        return None

    ps = pf.findall(f"{AKN}p")
    long_p = next((p for p in ps if _norm_ws(_text(p)).startswith("An Act")), None)

    enacting_el = pf.find(f"{AKN}formula")

    if long_p is None:
        candidate = _fallback_long_title_p(pf, enacting_el)
        if candidate is not None and _looks_like_prose(candidate):
            long_p = candidate

    if long_p is None:
        return None

    return {
        "long_title": _render_inline(long_p),
        "enacting": _render_inline(enacting_el) if enacting_el is not None else "",
    }


def _toc_node(el: ET._Element) -> dict:
    heading_el = el.find(f"{AKN}heading")
    num_el = el.find(f"{AKN}num")
    heading_text = (heading_el.text or "").strip() if heading_el is not None else ""
    num_text = (num_el.text or "").strip() if num_el is not None else ""
    heading = f"{num_text} {heading_text}".strip()
    children = [_toc_node(c) for c in el if _local_tag(c) in _STRUCTURAL_TAGS]
    # Task 7: a part/chapter/division/subdivision/subDivision (never a
    # <section> -- it renders its own content) with direct head-note block
    # content gets a synthetic ``__head`` child prepended AHEAD of its nested
    # sub-containers, so the reader meets the container's introductory text
    # before its first Division/section. Mirrors the ``<eid>__head`` key
    # build_sections writes for the same run.
    head_eid = el.get("eId", "")
    if (
        head_eid
        and _local_tag(el) in _HEADNOTE_CONTAINER_TAGS
        and _headnote_block_children(el)
    ):
        # `head_eid` truthy mirrors build_sections's head-note pass
        # (`if not eid: continue`), so an eId-less container never gets a
        # `{"eid": "__head"}` TOC child the bundle has no entry for -- same
        # TOC/bundle symmetry convention as build_toc's schedule-clause
        # `if not eid: continue` (Task 4).
        children.insert(
            0,
            {
                "eid": f"{head_eid}__head",
                "heading": _headnote_heading(el),
                "children": [],
            },
        )
    return {"eid": el.get("eId", ""), "heading": heading, "children": children}


def _starts_with_token(text: str, prefix: str) -> bool:
    """``text`` begins with ``prefix`` as a whole token, not merely as a
    string prefix -- i.e. ``prefix`` occupies the string up to a genuine
    word/number boundary, never partway through a longer word or number.

    ``prefix`` must be non-empty. True when ``text.startswith(prefix)`` AND
    the character immediately following ``prefix`` (if any) is *not*
    alphanumeric. That excludes NBSP (``\\xa0``, ``str.isalnum()`` is False
    for it) and ordinary punctuation/space as boundaries, while rejecting a
    letter or digit that would silently continue ``prefix`` into a different
    word or number.

    Fixes two real-corpus regressions found in review (post Task 5 approval):

    - ``_schedule_label``'s old ``heading_text.startswith("Schedule")`` also
      matched "Scheduled areas...", "Scheduled substances" and "Scheduled
      interests" -- "Schedule" is a true *prefix* of "Scheduled" but not a
      whole token there ('d' is alphanumeric, so this helper correctly
      rejects it).
    - ``_numbered_heading``'s old ``heading_text.startswith(num_text)`` guard
      fired on ``veterans'-entitlements-(rewrite)-transition-act-1991.xml``'s
      ``part-4__sec-19`` (``<num>19</num>``, ``<heading>1990 Budget
      amendments</heading>``): "1990...".startswith("19") is True, so the
      guard wrongly treated the heading as already-numbered and suppressed
      the prepend, silently dropping the section's own number. '9' (the
      character right after "19" in "1990") is alphanumeric, so this helper
      correctly rejects the match and lets the real prepend happen.
    """
    if not text.startswith(prefix):
        return False
    rest = text[len(prefix):]
    return rest == "" or not rest[0].isalnum()


def _numbered_heading(el: ET._Element) -> str:
    """``f"{num} {heading}".strip()``, mirroring :func:`_toc_node` (Task 5).

    Used for both schedule clauses (``_entry_heading``) and regular body
    ``<section>`` elements (``build_sections``'s first loop), so the two
    never diverge on how a number gets prepended to a heading.

    Guard: if ``heading`` text already starts with the ``num`` text *as a
    whole token* (see :func:`_starts_with_token`), the heading is returned
    unprepended -- a source document that has already baked its number into
    the heading (e.g. ``<heading>3 Already numbered</heading>``) must not
    get a doubled ``"3 3 Already numbered"``. Token-boundary matching (not
    plain ``str.startswith``) is required so a heading that merely begins
    with a longer number sharing ``num``'s digits (e.g. ``num="19"`` against
    ``<heading>1990 Budget amendments</heading>``) is not mistaken for
    already-numbered -- see :func:`_starts_with_token`'s docstring for the
    real-corpus case this fixes. An empty ``num_text`` never matches this
    guard's intent (every string "starts with" ""), so it's excluded
    explicitly to avoid short-circuiting into always-true.
    """
    heading_el = el.find(f"{AKN}heading")
    num_el = el.find(f"{AKN}num")
    heading_text = (heading_el.text or "").strip() if heading_el is not None else ""
    num_text = (num_el.text or "").strip() if num_el is not None else ""
    if not num_text or _starts_with_token(heading_text, num_text):
        return heading_text
    return f"{num_text} {heading_text}".strip()


def _entry_heading(el: ET._Element) -> str:
    """Numbered ``<heading>`` text for a schedule clause -- see
    :func:`_numbered_heading`."""
    return _numbered_heading(el)


def _headnote_block_children(el: ET._Element) -> list[ET._Element]:
    """The container's DIRECT ``content``/``p``/``blockList``/``table``
    children -- the block run that sits outside any ``<section>`` and is the
    container's head-note (Task 7).

    Direct children only (``for c in el``): a ``<content>`` nested inside an
    ``<authorialNote>`` or inside a child ``<section>``/``<division>`` is not
    this container's head-note and is not returned. ``<num>``/``<heading>``
    and nested structural containers are likewise skipped.
    """
    return [c for c in el if _local_tag(c) in _HEADNOTE_BLOCK_TAGS]


def _headnote_heading(el: ET._Element) -> str:
    """Heading for a container's ``__head`` entry (Task 7).

    The container's own numbered heading (:func:`_numbered_heading`, so its
    ``<num>``/``<heading>`` compose exactly as they do for a body
    ``<section>`` or a schedule clause) followed by a `` — introductory
    text`` suffix -- per the plan's
    ``f"{num} {heading} — introductory text".strip()`` -- marking the entry
    as the container's pre-section block content rather than a section of its
    own. When the container has neither ``<num>`` nor ``<heading>`` the
    suffix stands alone (no leading `` — ``).
    """
    base = _numbered_heading(el)
    return f"{base} — introductory text" if base else "introductory text"


def _schedule_label(sched: ET._Element) -> str:
    """The TOC/bundle label for one ``<hcontainer name="schedule">`` (Task 5).

    If the schedule's own ``<heading>`` already reads in gazette form (starts
    with the whole word "Schedule" -- see :func:`_starts_with_token` -- e.g.
    "Schedule 2", "Schedule\\xa02", "Schedule I—") it is returned verbatim.
    Otherwise a synthesised ``"Schedule {ordinal}"`` label is used, with
    `` — {heading}`` appended when a heading exists.

    Token-boundary matching (not plain ``str.startswith``) is required:
    a real-corpus review finding (post Task 5 approval) showed plain
    ``startswith("Schedule")`` also matches "Scheduled areas for the States
    and Territories", "Scheduled substances" and "Scheduled interests" --
    "Schedule" is a string prefix of "Scheduled" but not the whole first
    word, so those three must fall through to the synthesised-ordinal
    branch, not be returned as if already gazette-form. Verified against all
    22 corpus schedules whose heading starts with "Schedule": 18 are true
    ``"Schedule\\xa0N"`` / ``"Schedule I—"`` gazette form (still accepted),
    3 are the "Scheduled ..." false positives above (now correctly
    rejected), and one -- "Schedule to be inserted in Parliament Act 1974"
    (parliamentary-precincts-act-1988) -- is a literal heading that begins
    with the standalone word "Schedule" but carries no schedule number.
    Judgment call: this one is still accepted (space is a valid boundary
    character after "Schedule"), since the alternative would render as
    "Schedule 1 — Schedule to be inserted in Parliament Act 1974" (that Act
    has one schedule) -- a worse, doubled-"Schedule" result than the
    original heading shown verbatim.

    ``ordinal`` is the schedule's 1-based position among *all* schedules in
    the document (every ``hcontainer[@name='schedule']`` reachable via
    ``.//attachments/attachment/hcontainer[@name='schedule']``, the same
    xpath ``build_toc``/``build_sections`` already iterate) -- verified
    against the full lex-au corpus (3,076 Acts): every Act has exactly one
    ``<attachments>`` element, every ``<attachment>`` wraps exactly one
    schedule, and no schedule nests another, so this xpath's document-order
    walk *is* the full and only sibling scope; there is no narrower
    per-``<attachment>`` grouping to consider. This ordinal is the corpus's
    own numbering, which can differ from the Act's gazetted schedule number
    for a small number of Acts (see README "Known limitations").
    """
    heading_el = sched.find(f"{AKN}heading")
    heading_text = (heading_el.text or "").strip() if heading_el is not None else ""
    if _starts_with_token(heading_text, "Schedule"):
        return heading_text
    root = sched.getroottree().getroot()
    schedules = list(
        root.iterfind(
            f".//{AKN}attachments/{AKN}attachment/{AKN}hcontainer[@name='schedule']"
        )
    )
    ordinal = schedules.index(sched) + 1
    label = f"Schedule {ordinal}"
    if heading_text:
        label += f" — {heading_text}"
    return label


def _add_entry(
    sections: dict[str, dict],
    eid: str,
    heading: str,
    html: str,
) -> None:
    """Record one SCHEDULE-UNIT bundle entry (a clause/item leaf or a
    schedule-scoped block run -- never a body head-note entry, see
    :func:`_add_headnote_entry` for that axis).

    Asserts ``eid`` is not already in ``sections`` (Task 22): pre-B4, the
    converter could emit two distinct schedule units sharing one eId (see
    ``tests/fixtures/corpus/sched-dup-eid.xml``), which used to be silently
    disambiguated here. lex-au v0.10.0's B4 fix eliminates that collision at
    the source, so a duplicate reaching this function today can only mean a
    converter regression -- silently suffixing it would hide that regression
    rather than surface it. Schedule-unit eIds always carry a leading
    ``schedule-`` segment, so this can never collide with a head-note key
    (see ``_add_headnote_entry``), which is always a body-container eid plus
    ``__head``.
    """
    assert eid not in sections, (
        f"duplicate schedule-unit eId {eid!r} reached bundle assembly -- a "
        "schedule-unit eId collision should not occur after lex-au v0.10.0's "
        "B4 fix; this indicates a converter regression, not a case to "
        "disambiguate around"
    )
    sections[eid] = {"heading": heading, "html": html}


def _next_free_key(eid: str, taken: Callable[[str], bool]) -> str:
    """``eid`` itself if ``taken(eid)`` is false; otherwise
    ``f"{eid}{_EID_DISAMBIG}{n}"`` for the smallest free ``n`` starting at 2.
    Used only by :func:`_add_headnote_entry` (Task 22 confined this to the
    head-note axis; see ``_EID_DISAMBIG``'s module comment for why that axis
    still needs it)."""
    if not taken(eid):
        return eid
    n = 2
    while taken(f"{eid}{_EID_DISAMBIG}{n}"):
        n += 1
    return f"{eid}{_EID_DISAMBIG}{n}"


def _add_headnote_entry(
    sections: dict[str, dict],
    eid: str,
    heading: str,
    html: str,
) -> None:
    """Record one body-container HEAD-NOTE bundle entry, disambiguating
    ``eid`` if it collides (Task 7 original behaviour, kept through Task 22).

    Unlike a schedule-unit collision, a head-note key collision is a real,
    ongoing, legitimate real-corpus shape unrelated to B4: two ``<part>``/
    ``<chapter>``/... elements can share one number at different locations
    in the SAME Act's body (verified against the live v0.10.0 corpus running
    this task's predeploy build: e.g.
    ``public-service-reform-act-1984.xml`` has two literal
    ``<part eId="part-VII">`` elements directly under ``<body>`` -- also the
    real-corpus shape ``build/cli.py``'s ``_write_split_bundle`` comment
    already documents for Corp Act's two ``chapter-7``s and ITAA-97's
    repeated ``chapter-2``/``chapter-3``). Silently overwriting the first
    container's head-note with the second's would lose content, so this
    keeps the pre-Task-22 suffix behaviour rather than asserting.
    """
    key = _next_free_key(eid, lambda k: k in sections)
    sections[key] = {"heading": heading, "html": html}


def build_sections(
    root: ET._Element,
    ref_index: RefIndex,
    style: StyleMap | None = None,
    *,
    on_parsed: Optional[OnParsed] = None,
) -> tuple[dict[str, dict], "collections.Counter[str]"]:
    """Parse then render every ``<section>`` under ``root``.

    Returns ``({eid: {"heading", "html"}}, ref_index.tally)``. ``heading`` is
    the section's ``<num>`` prepended to its ``<heading>`` text (Task 5's
    :func:`_numbered_heading`, guarded against double-numbering). ``style``
    defaults to :class:`~build.stylemap.HtmlStyleMap`. There is no ``resolver`` /
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

    # Scoped to <body> (Task 22): a B4 schedule's <quotedStructure> can embed
    # a real <section> (an inserted/substituted provision -- see
    # tests/fixtures/corpus/sched-b4-nested.xml). An unscoped root.iter() here
    # would also match that section and render it a second time as an
    # orphaned top-level entry no TOC node ever points at (dead weight in
    # every non-split Act's JSON) -- schedule content is exclusively the
    # schedule-unit walk's job below, exactly as build_toc already scopes its
    # own structural walk to <body> for the same reason.
    body = root.find(f".//{AKN}body")
    parsed: list[tuple[str, str, Node]] = []
    if body is not None:
        for section in body.iter(f"{AKN}section"):
            eid = section.get("eId", "")
            if not eid:
                continue
            heading = _numbered_heading(section)
            parsed.append((eid, heading, parse_section(section, ref_index)))

    if on_parsed is not None:
        on_parsed([(eid, node) for eid, _, node in parsed])

    sections: dict[str, dict] = {
        eid: {"heading": heading, "html": render_section(node, active_style)}
        for eid, heading, node in parsed
    }

    def _flatten_schedule_units(units: list) -> None:
        """Recursive Task-22 counterpart to ``_schedule_toc_children``: walk
        the same unit tree and write each leaf/block's bundle entry. A
        "group" wrapper has no bundle entry of its own -- only its nested
        units do -- so this simply recurses into it."""
        for unit in units:
            kind = unit[0]
            if kind == "group":
                _, _group_el, nested_units = unit
                _flatten_schedule_units(nested_units)
            elif kind == "block":
                _, key, run = unit
                # Task 1 BINDING: deepcopy each loose sibling into a detached
                # <hcontainer> -- never move live nodes (that would empty the
                # source schedule, which build_toc / build_sections both read
                # from the same `root` elsewhere).
                wrap = ET.Element(f"{AKN}hcontainer")
                for el in run:
                    wrap.append(copy.deepcopy(el))
                node = parse_section(wrap, ref_index)
                # Synthetic (loose-prose) block units have no <num>/<heading>
                # of their own -- Task 5's numbered-heading composition does
                # not apply. They carry one consistent short label
                # (_SCHEDULE_BLOCK_LABEL), the SAME string build_toc's block
                # branch writes, so the TOC child and this bundle entry agree.
                _add_entry(
                    sections, key, _SCHEDULE_BLOCK_LABEL,
                    render_section(node, active_style),
                )
            else:
                leaf = unit[1]
                eid = leaf.get("eId", "")
                if not eid:
                    continue
                node = parse_section(leaf, ref_index)
                heading = _entry_heading(leaf)
                _add_entry(
                    sections, eid, heading, render_section(node, active_style),
                )

    for sched in root.iterfind(
        f".//{AKN}attachments/{AKN}attachment/{AKN}hcontainer[@name='schedule']"
    ):
        _flatten_schedule_units(_schedule_units(sched))

    # Task 7: head-note pass. Block content (content/p/blockList/table) sitting
    # DIRECTLY inside a <part>/<chapter>/<division>/<subdivision>/<subDivision>,
    # outside any <section>, is the container's head-note (5,761 such blocks in
    # the corpus). Render it as one detached <hcontainer> keyed
    # ``<container eId>__head``. <section> is deliberately not in this tag set
    # -- a section's own content is already rendered by the pass above. The
    # corpus has zero part/chapter/division elements inside <attachments>
    # (verified), so this whole-tree walk can never double-render a schedule's
    # loose content, which _schedule_units already grouped above.
    for container in root.iter():
        if _local_tag(container) not in _HEADNOTE_CONTAINER_TAGS:
            continue
        eid = container.get("eId", "")
        if not eid:
            continue
        run = _headnote_block_children(container)
        if not run:
            continue
        # Task 1 BINDING (as the schedule loop above): deepcopy each block
        # into a detached <hcontainer> -- never move live nodes, which would
        # empty the container that build_toc also reads from `root`.
        wrap = ET.Element(f"{AKN}hcontainer")
        for el in run:
            wrap.append(copy.deepcopy(el))
        node = parse_section(wrap, ref_index)
        _add_headnote_entry(
            sections,
            f"{eid}__head",
            _headnote_heading(container),
            render_section(node, active_style),
        )

    return sections, ref_index.tally
