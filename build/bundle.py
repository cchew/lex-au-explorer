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

# Disambiguator for colliding schedule-unit eIds (Task 4). The converter
# flattens schedule Part/Division numbering, so a schedule can legitimately
# contain two distinct <clause> elements sharing one eId (see
# tests/fixtures/corpus/sched-dup-eid.xml and ../lex-au/repo/FUTURE.md). "~"
# does not occur in any eId in the lex-au corpus (verified via
# `grep -ohE 'eId="[^"]*"' corpus/xml/*.xml | grep -c '~'` -> 0), and is a
# safe HTML `id` attribute character and dict key.
_EID_DISAMBIG = "~"

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
                eid = clause.get("eId", "")
                if not eid:
                    # Symmetry with build_sections's clause branch (which
                    # does `if not eid: continue` before ever calling
                    # _add_entry): a clause with no eId gets no `sections`
                    # entry there, so it must get no TOC child here either --
                    # otherwise the TOC would list a node the bundle has no
                    # content for, breaking the "TOC and bundle never
                    # disagree" property this task exists to guarantee.
                    continue
                key = _next_free_key(eid, lambda k: k in used)
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
                # Synthetic (loose-prose) units have no <num>/<heading> of
                # their own; they stay unlabelled (Task 5 numbers clauses
                # and body sections only, not these).
                children.append({"eid": key, "heading": "", "children": []})
        out.append(
            {
                "eid": sched.get("eId", ""),
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

    parsed: list[tuple[str, str, Node]] = []
    for section in root.iter(f"{AKN}section"):
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
                heading = _entry_heading(clause)
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
                # Synthetic (loose-prose) units have no <num>/<heading> of
                # their own -- Task 5's numbered-heading composition does not
                # apply to them; they stay unlabelled.
                _key = _add_entry(
                    sections, key, "", render_section(node, active_style), ref_index.tally
                )

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
        _add_entry(
            sections,
            f"{eid}__head",
            _headnote_heading(container),
            render_section(node, active_style),
            ref_index.tally,
        )

    return sections, ref_index.tally
