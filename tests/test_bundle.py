"""End-to-end coverage for the bundle stage: ``build_toc`` (unchanged) and
``build_sections`` (rewritten to delegate to Stage 1 parse + Stage 2 render).

The per-construct regression assertions that used to live here (inline
emphasis, embedded-number normalisation, authorial notes, defined-term
marking) now live in ``tests/test_parse.py`` and ``tests/test_render.py``,
exercised against the real-corpus fixtures in ``tests/fixtures/corpus/``.
"""

from __future__ import annotations

import collections
from pathlib import Path
from typing import Optional

import lxml.etree as ET
import pytest

from build.bundle import (
    AKN,
    build_preface,
    build_sections,
    build_toc,
    _local_tag,
    _schedule_units,
)
from build.ir import Node
from build.refindex import build_ref_index
from build.stylemap import HtmlStyleMap

FIXTURES = Path(__file__).parent / "fixtures"
_NAV_TAGS = {
    "section", "part", "division", "subdivision", "chapter",
    "subsection", "paragraph", "subparagraph",
}
_NAV_HCONTAINERS = {"clause", "subclause"}


def _parse_stub(name: str) -> ET._Element:
    return ET.parse(str(FIXTURES / "xml" / name)).getroot()


def _parse_corpus(name: str) -> ET._Element:
    return ET.parse(str(FIXTURES / "corpus" / name)).getroot()


def _all_nav_eids(root: ET._Element) -> list[str]:
    eids: list[str] = []
    for el in root.iter():
        eid = el.get("eId")
        if not eid:
            continue
        tag = _local_tag(el)
        if tag in _NAV_TAGS or (
            tag == "hcontainer" and el.get("name") in _NAV_HCONTAINERS
        ):
            eids.append(eid)
    return eids


# --------------------------------------------------------------------------- #
# build_toc -- unchanged behaviour
# --------------------------------------------------------------------------- #


def test_build_toc_nests_part_division_section() -> None:
    root = _parse_stub("privacy-act-1988.xml")
    toc = build_toc(root)
    assert toc[0]["eid"] == "part-I"
    assert toc[0]["heading"]
    part_i_sections = [c["eid"] for c in toc[0]["children"]]
    assert "part-I__sec-6" in part_i_sections


# --------------------------------------------------------------------------- #
# build_sections -- new (root, ref_index, style) -> (dict, Counter) signature
# --------------------------------------------------------------------------- #


def test_build_sections_real_s3_text_and_refs() -> None:
    root = _parse_corpus("corp-act-s3.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, tally = build_sections(root, ix)

    html = sections["chapter-1__part-1.1__sec-3"]["html"]
    assert "law of the Commonwealth" in html
    assert "<em>Acts Interpretation Act 1901</em>" in html
    assert '<span class="akn-num">(2)</span>' in html
    assert sum(tally.values()) >= 1


def test_build_sections_returns_the_ref_index_tally_counter() -> None:
    root = _parse_corpus("corp-act-s3.xml")
    ix = build_ref_index(_all_nav_eids(root))
    _, tally = build_sections(root, ix)

    assert isinstance(tally, collections.Counter)
    assert tally is ix.tally
    # corp-act-s3 cites the Constitution (#sec-51 / #sec-122, display text
    # names "the Constitution") and a scrambled #sec-2H -- none resolvable.
    assert set(tally) <= {"resolved", "ambiguous", "unresolved"}
    assert tally["unresolved"] >= 1


def test_build_sections_preserves_heading_from_heading_element() -> None:
    root = _parse_corpus("corp-act-s3.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix)
    assert (
        sections["chapter-1__part-1.1__sec-3"]["heading"]
        == "3 Constitutional basis for this Act"
    )


def test_build_sections_accepts_a_custom_style_map() -> None:
    class LoudMap(HtmlStyleMap):
        def _emphasis(self, node: Node, children: list[str]) -> str:
            return f'<mark>{"".join(children)}</mark>'

    root = _parse_corpus("corp-act-s3.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix, style=LoudMap())

    html = sections["chapter-1__part-1.1__sec-3"]["html"]
    assert "<mark>Acts Interpretation Act 1901</mark>" in html
    assert "<em>" not in html


def test_build_sections_defaults_to_html_style_map() -> None:
    root = _parse_corpus("itaa97-rate-table.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix)

    (eid,) = list(sections)
    assert '<table class="akn-table">' in sections[eid]["html"]


# --------------------------------------------------------------------------- #
# Schedule clauses -- Task 2: schedule and figure rendering
# --------------------------------------------------------------------------- #


def test_schedule_clause_reaches_bundle_and_toc() -> None:
    root = _parse_corpus("sched-clause.xml")
    idx = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, idx)
    assert any(k.startswith("schedule-1__clause-") for k in sections)

    toc = build_toc(root)
    sched = [n for n in toc if n["eid"].startswith("schedule-")]
    assert sched and any(
        c["eid"].startswith("schedule-1__clause-") for c in sched[0]["children"]
    )


def test_paragraph_only_schedule_items_render() -> None:
    root = _parse_corpus("sched-paragraphs.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix)
    blob = " ".join(v["html"] for k, v in sections.items() if k.startswith("schedule-1"))
    assert "Coal Industry Act 1946" in blob  # an item's text
    # sched-paragraphs has no <clause>: its whole loose <paragraph> run is one
    # synthetic block unit keyed under the bare `schedule-1` eId. That equals
    # the schedule TOC node's own eid, so the self-referential child row is
    # suppressed (F2); the content still lands in the bundle under `schedule-1`
    # and the reader's flattenLeafEids falls back to [node.eid] to render it.
    sched_node = build_toc(root)[-1]
    assert sched_node["eid"] == "schedule-1"
    assert sched_node["children"] == []
    assert "schedule-1" in sections


def test_schedule_block_unit_labelled_and_toc_matches_bundle() -> None:
    """F2: a synthetic schedule "block" unit (a loose sibling run grouped by
    _schedule_units) must carry a real label, not "", in BOTH the TOC child
    and the bundle entry -- and the two strings must be identical. sched-clause
    has a leading <content> run before its one <clause>, so it produces a
    `schedule-1__block-0` unit."""
    root = _parse_corpus("sched-clause.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix)

    sched_node = next(n for n in build_toc(root) if n["eid"] == "schedule-1")
    block_children = [c for c in sched_node["children"] if "__block-" in c["eid"]]
    assert block_children, "expected a synthetic block-unit TOC child"
    for child in block_children:
        assert child["heading"] == "Introductory text"
        assert child["heading"] != ""
        # TOC child heading and bundle entry heading must agree (F2 parity).
        assert sections[child["eid"]]["heading"] == child["heading"]


def test_schedule_level_table_renders_rows() -> None:
    root = _parse_corpus("sched-table.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix)
    blob = " ".join(v["html"] for k, v in sections.items() if k.startswith("schedule-1"))
    assert blob.count("<tr") >= 5 and "<table" in blob


def test_build_sections_does_not_mutate_schedule_source_tree() -> None:
    # Task 3 BINDING: the transient wrapper used for synthetic (loose-prose)
    # units must be built by deepcopy into a detached <hcontainer>, never by
    # moving live nodes. sched-clause.xml has a loose <content> note before
    # its one real clause, so this fixture exercises both code paths (the
    # synthetic-run flush AND the real-clause branch) in one document.
    root = _parse_corpus("sched-clause.xml")
    before = ET.tostring(root)
    ix = build_ref_index(_all_nav_eids(root))
    build_sections(root, ix)
    after = ET.tostring(root)
    assert before == after


# --------------------------------------------------------------------------- #
# eId collisions are now a converter regression, not something to paper over
# -- Task 22 (B4 shipped in lex-au v0.10.0, converter-side, eliminates the
# collisions the old ~N disambiguator (Task 4) existed to paper over: see
# bundle.py's module-level comment above `_SCHEDULE_LEAF_NAMES`). The three
# former disambiguation tests (`test_duplicate_clause_eids_both_kept`,
# `test_disambiguated_unit_has_unique_dom_id`,
# `test_build_toc_agrees_with_bundle_on_disambiguated_keys`) are replaced by
# the two assertion tests below: a duplicate eId reaching bundle assembly is
# now a loud failure, not a silently-suffixed key.
# --------------------------------------------------------------------------- #


def test_duplicate_schedule_eid_raises_in_build_sections() -> None:
    """sched-dup-eid.xml documents the pre-B4 converter bug (two distinct
    <clause eId="schedule-1__clause-30"> elements -- see the fixture's header
    comment) that lex-au v0.10.0's B4 fix eliminates at the source. Post-B4,
    a duplicate reaching `_add_entry` can only mean a converter regression,
    not a case to disambiguate around -- `build_sections` must raise, not
    silently keep both under a suffixed key."""
    root = _parse_corpus("sched-dup-eid.xml")
    ix = build_ref_index(_all_nav_eids(root))
    with pytest.raises(AssertionError, match="schedule-1__clause-30"):
        build_sections(root, ix)


def test_duplicate_schedule_eid_raises_in_build_toc() -> None:
    """Same converter-regression guard, TOC side: build_toc must not silently
    disambiguate a duplicate schedule-unit eId into a second TOC child either
    -- the two entry points must fail the same way on the same bad input."""
    root = _parse_corpus("sched-dup-eid.xml")
    with pytest.raises(AssertionError, match="schedule-1__clause-30"):
        build_toc(root)


# --------------------------------------------------------------------------- #
# B4 schedule nesting (<hcontainer name="amendedAct"> / "item" wrappers,
# <quotedStructure> inserted provisions) -- Task 22
# --------------------------------------------------------------------------- #


def test_schedule_units_recurses_through_b4_amended_act_wrapper() -> None:
    """sched-b4-nested.xml's schedule-1 has ONE direct child: an
    <hcontainer name="amendedAct"> wrapping 3 <hcontainer name="item">
    amendment instructions (the real v0.10.0 B4 shape -- see the fixture's
    header comment). `_schedule_units` must not flatten this into one opaque
    "block" run (the pre-Task-22 bug this task fixes): it must yield exactly
    one "group" unit for the wrapper, and recursing into that group's own
    nested units must yield the 3 items in document order."""
    sched = next(
        _parse_corpus("sched-b4-nested.xml").iterfind(
            f".//{AKN}attachments/{AKN}attachment/{AKN}hcontainer[@name='schedule']"
        )
    )
    units = _schedule_units(sched)
    assert len(units) == 1
    kind, group_el, nested = units[0]
    assert kind == "group"
    assert group_el.get("eId") == "schedule-1__amdact-1"

    assert [u[0] for u in nested] == ["item", "item", "item"]
    assert [u[1].get("eId") for u in nested] == [
        "schedule-1__amdact-1__item-1",
        "schedule-1__amdact-1__item-2",
        "schedule-1__amdact-1__item-3",
    ]


def test_build_toc_nests_b4_schedule_groups_and_items() -> None:
    """The TOC must expose a real tree for a B4 schedule: the schedule node's
    one child is the amendedAct group, and that group's own children are the
    3 items -- not 3 direct schedule children (flat) and not 0 children
    (the pre-Task-22 collapse). No `~N` disambiguator suffix appears
    anywhere: B4 schedules have no colliding eIds to disambiguate."""
    root = _parse_corpus("sched-b4-nested.xml")
    toc = build_toc(root)
    sched_node = next(n for n in toc if n["eid"] == "schedule-1")

    assert len(sched_node["children"]) == 1
    group_node = sched_node["children"][0]
    assert group_node["eid"] == "schedule-1__amdact-1"
    assert group_node["heading"] == "Agricultural and Veterinary Chemicals Code Act 1994"

    item_eids = [c["eid"] for c in group_node["children"]]
    assert item_eids == [
        "schedule-1__amdact-1__item-1",
        "schedule-1__amdact-1__item-2",
        "schedule-1__amdact-1__item-3",
    ]
    assert group_node["children"][1]["heading"].startswith("2 ")
    assert not any("~" in eid for eid in item_eids)


def test_build_sections_renders_each_b4_item_as_its_own_entry() -> None:
    """Each item is its own navigable bundle entry (its own key, its own
    heading) -- not one item's content merged into a sibling's, and not the
    whole amendedAct group collapsed into a single "Introductory text" blob
    (the exact defect Task 21's triage found in the live corpus). item-2's
    entry must contain its <quotedStructure>'s nested <section>/<subsection>/
    <paragraph> prose, proving the recursion still renders a quoted
    provision's real content, not just the item's own instruction text."""
    root = _parse_corpus("sched-b4-nested.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix)

    assert set(sections) == {
        "schedule-1__amdact-1__item-1",
        "schedule-1__amdact-1__item-2",
        "schedule-1__amdact-1__item-3",
    }
    assert sections["schedule-1__amdact-1__item-1"]["heading"] == (
        "1 Before section 1 of the Code set out in the Schedule"
    )
    item2_html = sections["schedule-1__amdact-1__item-2"]["html"]
    assert "furthering of trade and commerce" in item2_html
    item3_html = sections["schedule-1__amdact-1__item-3"]["html"]
    assert "Repeal the definition" in item3_html
    # item-3 has no <quotedStructure> at all -- confirms the no-quoted-content
    # leaf shape renders fine too, not just the two quoted-provision items.
    assert "furthering of trade and commerce" not in item3_html


def test_build_toc_skips_eidless_schedule_clause_like_build_sections_does() -> None:
    """Review finding (post-approval, Task 4): build_toc's clause branch must
    skip a schedule <clause> with no eId, exactly like build_sections's
    clause branch already does (`if not eid: continue` before ever calling
    _add_entry) -- otherwise the TOC would list a node with no corresponding
    `sections` entry. Real corpus has 0/151,217 schedule clauses without an
    eId (reviewer-verified), so this is a synthetic regression guard for a
    dead-today edge case, not a real-corpus reproduction."""
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><attachments><attachment>'
        f'<hcontainer name="schedule" eId="schedule-1"><heading>Sched</heading>'
        f'<hcontainer name="clause"><num>1</num><heading>No eId</heading>'
        f"<content><p>orphan clause</p></content></hcontainer>"
        f'<hcontainer name="clause" eId="schedule-1__clause-2">'
        f"<num>2</num><heading>Kept</heading>"
        f"<content><p>real clause</p></content></hcontainer>"
        f"</hcontainer></attachment></attachments></act></akomaNtoso>"
    )
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix)
    toc = build_toc(root)

    assert list(sections) == ["schedule-1__clause-2"]
    sched_node = next(n for n in toc if n["eid"] == "schedule-1")
    assert [c["eid"] for c in sched_node["children"]] == ["schedule-1__clause-2"]


def test_schedule_unit_count_equals_bundle_key_count() -> None:
    """Task 3/4 invariant: every FLAT (no group nesting) unit
    ``_schedule_units`` yields for a schedule lands under exactly one
    distinct bundle key. This is the regression guard for a collision
    silently collapsing two units into one key (proven to fail if
    ``_add_entry``'s collision branch is removed -- see task-4-report.md).

    ``sched-dup-eid.xml`` is deliberately excluded (Task 22): it now raises
    (see ``test_duplicate_schedule_eid_raises_in_build_sections``), and a
    schedule with B4 group nesting (``sched-b4-nested.xml``) breaks this
    invariant's flat premise by design -- ``_schedule_units`` returns 1
    top-level ("group") unit for 3 leaf bundle keys, so it is checked by its
    own dedicated tests above, not folded into this loop."""
    for fixture in (
        "sched-clause.xml",
        "sched-paragraphs.xml",
        "sched-table.xml",
    ):
        root = _parse_corpus(fixture)
        ix = build_ref_index(_all_nav_eids(root))
        sections, _ = build_sections(root, ix)
        for sched in root.iterfind(
            f".//{AKN}attachments/{AKN}attachment/{AKN}hcontainer[@name='schedule']"
        ):
            sched_eid = sched.get("eId", "")
            n_units = len(_schedule_units(sched))
            n_keys = len(
                [
                    k
                    for k in sections
                    if k == sched_eid or k.startswith(sched_eid + "__")
                ]
            )
            assert n_units == n_keys, f"{fixture}: {n_units} units vs {n_keys} keys"


# --------------------------------------------------------------------------- #
# Schedule labels + clause/section numbers in headings -- Task 5
# --------------------------------------------------------------------------- #


def test_schedule_label_from_ordinal() -> None:
    """sched-multi.xml has 2 schedules, neither heading starting with
    "Schedule" -- both must get a synthesised "Schedule N -- <heading>" label,
    numbered by position among the document's schedules."""
    root = _parse_corpus("sched-multi.xml")
    toc = build_toc(root)
    labels = [n["heading"] for n in toc if n["eid"].startswith("schedule-")]
    assert len(labels) == 2
    assert labels[0].startswith("Schedule 1") and " — " in labels[0]
    assert labels[0] == "Schedule 1 — Family tax benefit rate calculator"
    assert labels[1] == (
        "Schedule 2 — Amounts of child care subsidy and "
        "additional child care subsidy"
    )


def test_schedule_label_prefers_gazetted_num_over_document_ordinal() -> None:
    """Task 23: real-corpus regression found by Task 21's triage --
    `electoral-legislation-amendment-(electoral-reform)-act-2025` has a
    gazetted numbering gap (schedule at document position 7 carries
    `<num>6</num>`). A schedule's `<num>` child (Task 3's gazetted number,
    verbatim from the source `_SCHEDULE_RE` match) must be preferred over the
    document-position ordinal when present -- the label must read "Schedule
    5", not "Schedule 3", for a schedule at position 3 whose `<num>` says 5."""
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><attachments><attachment>'
        f'<hcontainer name="schedule" eId="schedule-1">'
        f"<num>1</num><heading>First</heading>"
        f"<content><p>body</p></content></hcontainer>"
        f"</attachment><attachment>"
        f'<hcontainer name="schedule" eId="schedule-2">'
        f"<num>2</num><heading>Second</heading>"
        f"<content><p>body</p></content></hcontainer>"
        f"</attachment><attachment>"
        # Third schedule by document position, but gazetted <num> is 5
        # (a numbering gap -- the real-corpus shape this guards).
        f'<hcontainer name="schedule" eId="schedule-3">'
        f"<num>5</num><heading>Third but gazetted fifth</heading>"
        f"<content><p>body</p></content></hcontainer>"
        f"</attachment></attachments></act></akomaNtoso>"
    )
    toc = build_toc(root)
    labels = {n["eid"]: n["heading"] for n in toc if n["eid"].startswith("schedule-")}
    assert labels["schedule-1"] == "Schedule 1 — First"
    assert labels["schedule-2"] == "Schedule 2 — Second"
    assert labels["schedule-3"] == "Schedule 5 — Third but gazetted fifth"


def test_schedule_label_from_num_handles_roman_numerals() -> None:
    """Roman-numeral gazetted numbers (Task 3's other `_SCHEDULE_RE` case)
    must be used verbatim too, not coerced to an ordinal."""
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><attachments><attachment>'
        f'<hcontainer name="schedule" eId="schedule-1">'
        f"<num>IV</num><heading>Fourth in Roman</heading>"
        f"<content><p>body</p></content></hcontainer>"
        f"</attachment></attachments></act></akomaNtoso>"
    )
    toc = build_toc(root)
    assert toc[0]["heading"] == "Schedule IV — Fourth in Roman"


def test_schedule_label_falls_back_to_ordinal_when_no_num() -> None:
    """No `<num>` child -> unchanged fallback behaviour (the ordinal path),
    proving Task 23 only adds a preference, not a required field."""
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><attachments><attachment>'
        f'<hcontainer name="schedule" eId="schedule-1">'
        f"<heading>No num at all</heading>"
        f"<content><p>body</p></content></hcontainer>"
        f"</attachment></attachments></act></akomaNtoso>"
    )
    toc = build_toc(root)
    assert toc[0]["heading"] == "Schedule 1 — No num at all"


def test_schedule_label_verbatim_when_heading_already_says_schedule() -> None:
    """A schedule whose <heading> already reads "Schedule N" (gazette form)
    must be used verbatim -- not re-numbered or have an ordinal appended."""
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><attachments><attachment>'
        f'<hcontainer name="schedule" eId="schedule-1">'
        f"<heading>Schedule 7</heading>"
        f"<content><p>body</p></content></hcontainer>"
        f"</attachment></attachments></act></akomaNtoso>"
    )
    toc = build_toc(root)
    assert toc[0]["heading"] == "Schedule 7"


def test_clause_heading_carries_num() -> None:
    root = _parse_corpus("sched-clause.xml")
    sections, _ = build_sections(root, build_ref_index(_all_nav_eids(root)))
    k = next(k for k in sections if k.startswith("schedule-1__clause-"))
    # sched-clause.xml's real clause is <num>70-20</num>.
    assert sections[k]["heading"].split()[0] == "70-20"
    assert sections[k]["heading"] == (
        "70-20 Audit of administration books—on order of the Court"
    )


def test_body_section_heading_regains_num() -> None:
    root = _parse_corpus("corp-act-s3.xml")
    sections, _ = build_sections(root, build_ref_index(_all_nav_eids(root)))
    assert (
        sections["chapter-1__part-1.1__sec-3"]["heading"]
        == "3 Constitutional basis for this Act"
    )


def test_numbered_heading_does_not_double_a_heading_that_already_has_the_num() -> None:
    """If <heading> text already begins with the <num> text, the num must not
    be prepended a second time."""
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><body>'
        f'<section eId="s1"><num>3</num>'
        f"<heading>3 Already numbered</heading>"
        f"<content><p>body</p></content></section>"
        f"</body></act></akomaNtoso>"
    )
    sections, _ = build_sections(root, build_ref_index([]))
    assert sections["s1"]["heading"] == "3 Already numbered"


def test_numbered_heading_guard_is_word_boundary_aware() -> None:
    """Real-corpus regression (found in Task 5 post-approval review):
    veterans'-entitlements-(rewrite)-transition-act-1991.xml's
    part-4__sec-19 has <num>19</num> and <heading>1990 Budget
    amendments</heading>. A plain ``heading.startswith(num)`` guard wrongly
    matches ("1990...".startswith("19") is True) and suppresses the prepend,
    silently dropping the section's own number. "19" is not a whole token at
    the start of "1990" (the next character, "9", continues the number), so
    the guard must not fire here -- the section must still get its "19 "
    prefix."""
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><body>'
        f'<section eId="part-4__sec-19"><num>19</num>'
        f"<heading>1990 Budget amendments</heading>"
        f"<content><p>body</p></content></section>"
        f"</body></act></akomaNtoso>"
    )
    sections, _ = build_sections(root, build_ref_index([]))
    assert sections["part-4__sec-19"]["heading"] == "19 1990 Budget amendments"


def test_schedule_label_rejects_scheduled_as_a_false_positive() -> None:
    """Real-corpus regression (found in Task 5 post-approval review):
    offshore-petroleum-and-greenhouse-gas-storage-act-2006.xml has a schedule
    headed "Scheduled areas for the States and Territories". A plain
    ``heading.startswith("Schedule")`` check wrongly treats this as
    already-gazette-form (it's a true string prefix) and returns it verbatim
    with no ordinal at all. "Schedule" is not a whole token at the start of
    "Scheduled" (the next character, "d", continues the word), so this
    schedule must still get a synthesised "Schedule N -- " label like any
    other non-gazette-form schedule."""
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><attachments><attachment>'
        f'<hcontainer name="schedule" eId="schedule-1">'
        f"<heading>Scheduled areas for the States and Territories</heading>"
        f"<content><p>body</p></content></hcontainer>"
        f"</attachment></attachments></act></akomaNtoso>"
    )
    toc = build_toc(root)
    assert toc[0]["heading"] == (
        "Schedule 1 — Scheduled areas for the States and Territories"
    )


def test_build_sections_skips_sections_without_an_eid() -> None:
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><body>'
        f"<section><heading>No eId</heading>"
        f"<content><p>orphan</p></content></section>"
        f'<section eId="s1"><heading>Kept</heading>'
        f"<content><p>body</p></content></section>"
        f"</body></act></akomaNtoso>"
    )
    sections, _ = build_sections(root, build_ref_index([]))
    assert list(sections) == ["s1"]


# --------------------------------------------------------------------------- #
# build_preface -- Task 6: <preface> has no <longTitle>; the long title is an
# unlabelled <p> starting "An Act", buried among ~90-130 cover-page/ToC <p>s.
# --------------------------------------------------------------------------- #


def test_build_preface_extracts_only_the_long_title() -> None:
    root = _parse_corpus("preface-with-toc.xml")  # cut from age-discrimination
    p = build_preface(root)
    assert p is not None
    assert p["long_title"].startswith("An Act")
    assert "Compilation No" not in p["long_title"]
    assert "Part 1" not in p["long_title"]  # no ToC line leaked
    assert "Definitions" not in p["long_title"]  # no ToC line leaked


def test_build_preface_preserves_inline_emphasis() -> None:
    p = build_preface(_parse_corpus("preface-emph.xml"))
    assert p is not None
    assert "<em>Digital ID Act 2024</em>" in p["long_title"]
    # The real <formula name="enacting"> in this fixture also exercises the
    # "enacting" field via the same _render_inline path.
    assert p["enacting"] == "The Parliament of Australia enacts:"


def test_build_preface_none_when_no_an_act_p() -> None:
    # The real ~5.4% case: a Regulations instrument (made *under* an Act, not
    # an Act itself) whose preface has no "An Act ..." <p> anywhere, no
    # <formula>, and whose actual last <p> is a ToC/endnotes line (trailing
    # page number) -- correctly rejected by the fallback's ToC-line check.
    root = _parse_corpus("preface-no-longtitle.xml")
    assert build_preface(root) is None


def test_build_preface_none_when_absent() -> None:
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><body/></act></akomaNtoso>'
    )
    assert build_preface(root) is None


# --------------------------------------------------------------------------- #
# Part/Chapter/Division head-notes -- Task 7
# --------------------------------------------------------------------------- #


def _find_toc(nodes: list[dict], eid: str) -> Optional[dict]:
    """Depth-first search of a ``build_toc`` tree for the node with ``eid``."""
    for n in nodes:
        if n["eid"] == eid:
            return n
        found = _find_toc(n["children"], eid)
        if found is not None:
            return found
    return None


def test_headnote_pass_ignores_quoted_structure_containers() -> None:
    """Post-ship regression (Task 22 follow-up, found by final code review):
    the head-note pass's ``for container in root.iter()`` was whole-tree, so
    a literal ``<part>``/``<chapter>``/``<division>``/``<subDivision>``
    element nested inside a B4 schedule's ``<quotedStructure>`` (a real
    corpus shape -- the amending Act's own quoted citation structure, e.g.
    "Part 8 -- Records" being inserted) also triggered a ``__head`` bundle
    entry. That entry has no TOC node (the schedule walk never emits one for
    quoted-structure content) and duplicates content already rendered inside
    the owning item's single HTML blob -- dead weight, not a reader-visible
    bug, but bloats every affected Act's JSON. Scoped the walk to
    ``<body>`` only, mirroring how ``build_sections``'s main per-section
    walk was already ``<body>``-scoped in this same task."""
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><attachments><attachment>'
        f'<hcontainer name="schedule" eId="schedule-1">'
        f"<num>1</num><heading>Amendments</heading>"
        f'<hcontainer name="amendedAct" eId="schedule-1__amdact-1">'
        f"<heading>Some Amended Act 2000</heading>"
        f'<hcontainer name="item" eId="schedule-1__amdact-1__item-1">'
        f"<num>1</num><heading>At the end of the Act</heading>"
        f"<content><p>Add:</p></content>"
        f'<quotedStructure eId="schedule-1__amdact-1__item-1__qstr-1">'
        f'<part eId="schedule-1__amdact-1__item-1__qstr-1__part-8">'
        f"<num>8</num><heading>Records</heading>"
        f"<content><p>Quoted part introductory text.</p></content>"
        f'<section eId="schedule-1__amdact-1__item-1__qstr-1__part-8__sec-1">'
        f"<num>1</num><heading>Kept</heading>"
        f"<content><p>real content</p></content></section>"
        f"</part></quotedStructure>"
        f"</hcontainer></hcontainer></hcontainer>"
        f"</attachment></attachments></act></akomaNtoso>"
    )
    sections, _ = build_sections(root, build_ref_index(_all_nav_eids(root)))
    assert "schedule-1__amdact-1__item-1__qstr-1__part-8__head" not in sections
    # The item's own single entry still carries the quoted part's content.
    assert (
        "Quoted part introductory text"
        in sections["schedule-1__amdact-1__item-1"]["html"]
    )


def test_chapter_level_content_renders_as_head_entry() -> None:
    """part-headnote.xml (cut from evidence-act-1995.xml) has a real
    <chapter>-level "INTRODUCTORY NOTE" <content> block directly under
    <chapter eId="chapter-2">, before its nested <part> children -- the real
    corpus shape this task targets."""
    root = _parse_corpus("part-headnote.xml")
    before = ET.tostring(root)
    sections, _ = build_sections(root, build_ref_index(_all_nav_eids(root)))
    assert "chapter-2__head" in sections
    assert "adducing evidence" in sections["chapter-2__head"]["html"].lower()
    # Heading format is fixed by the plan: the container's own numbered
    # heading (<num>2</num> + <heading>Adducing evidence</heading>) plus the
    # " — introductory text" suffix.
    assert (
        sections["chapter-2__head"]["heading"]
        == "2 Adducing evidence — introductory text"
    )
    # Task 1 deepcopy discipline: the head-note run is copied into a detached
    # wrapper, never moved -- the source tree is untouched.
    assert ET.tostring(root) == before

    toc = build_toc(root)
    ch2 = _find_toc(toc, "chapter-2")
    assert ch2 is not None
    assert ch2["children"][0]["eid"] == "chapter-2__head"
    assert (
        ch2["children"][0]["heading"] == "2 Adducing evidence — introductory text"
    )
    # The nested <part> children still follow, in document order, after the
    # prepended head-note node.
    assert ch2["children"][1]["eid"] == "chapter-2__part-2.1"


def test_part_with_only_sections_gets_no_head_entry() -> None:
    """Regression guard: chapter-2__part-2.2's only direct children are
    <num>/<heading>/<section> (real corpus shape -- no <content> of its own).
    It must get no __head bundle entry and no __head TOC child -- a
    <section>'s own content is handled by build_sections's existing
    per-section pass, not by this task's head-note pass."""
    root = _parse_corpus("part-headnote.xml")
    sections, _ = build_sections(root, build_ref_index(_all_nav_eids(root)))
    assert "chapter-2__part-2.2__head" not in sections

    toc = build_toc(root)
    p22 = _find_toc(toc, "chapter-2__part-2.2")
    assert p22 is not None
    assert all(not c["eid"].endswith("__head") for c in p22["children"])
    assert p22["children"][0]["eid"] == "chapter-2__part-2.2__sec-51"


def test_headnote_heading_falls_back_to_bare_suffix_without_num_or_heading() -> None:
    """A container with direct block content but no <num> and no <heading>
    gets the bare " introductory text" label -- no leading " — "."""
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><body>'
        f'<part eId="part-1">'
        f"<content><p>This Part applies to transitional matters.</p></content>"
        f'<section eId="part-1__sec-1"><num>1</num><heading>X</heading>'
        f"<content><p>body</p></content></section>"
        f"</part>"
        f"</body></act></akomaNtoso>"
    )
    sections, _ = build_sections(root, build_ref_index(_all_nav_eids(root)))
    assert sections["part-1__head"]["heading"] == "introductory text"

    toc = build_toc(root)
    p1 = _find_toc(toc, "part-1")
    assert p1["children"][0]["eid"] == "part-1__head"
    assert p1["children"][0]["heading"] == "introductory text"


def test_build_toc_skips_headnote_for_eidless_container_like_build_sections() -> None:
    """Symmetry guard (mirrors build_toc's schedule-clause `if not eid:
    continue`, Task 4): build_sections's head-note pass skips a container with
    no eId, so _toc_node must not emit a ``{"eid": "__head"}`` child for one
    either. Dead today (every corpus structural container has an eId) -- a
    synthetic regression guard only."""
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><body>'
        f"<part>"  # no eId
        f"<content><p>Head-note prose for an eId-less Part.</p></content>"
        f'<section eId="s1"><num>1</num><heading>Kept</heading>'
        f"<content><p>body</p></content></section>"
        f"</part>"
        f"</body></act></akomaNtoso>"
    )
    sections, _ = build_sections(root, build_ref_index(_all_nav_eids(root)))
    toc = build_toc(root)

    assert not any(k.endswith("__head") for k in sections)
    part_node = toc[0]
    assert part_node["eid"] == ""
    assert [c["eid"] for c in part_node["children"]] == ["s1"]


def test_duplicate_headnote_key_is_disambiguated_not_asserted() -> None:
    """Task 22 regression guard: a body-level container eId collision (two
    ``<part>``s sharing one number at different locations in the SAME Act's
    body) is a real, ongoing, legitimate real-corpus shape -- confirmed
    against the live v0.10.0 corpus (Task 22's full-corpus predeploy run hit
    exactly this on ``public-service-reform-act-1984.xml``, which has two
    literal ``<part eId="part-VII">`` elements directly under ``<body>``; see
    also ``build/cli.py``'s ``_write_split_bundle`` comment on Corp Act's two
    ``chapter-7``s and ITAA-97's repeated ``chapter-2``/``chapter-3``). This
    is unrelated to B4 (which only touches schedule content), so it must
    keep the pre-Task-22 ``~2`` suffix behaviour -- NOT the new
    schedule-unit assertion -- or a real Act's second head-note silently
    overwrites the first's, permanently losing content."""
    root = ET.fromstring(
        f'<akomaNtoso xmlns="{AKN[1:-1]}"><act><body>'
        f'<part eId="part-VII">'
        f"<content><p>First VII head-note.</p></content>"
        f'<section eId="part-VII__sec-1"><num>1</num><heading>A</heading>'
        f"<content><p>body</p></content></section>"
        f"</part>"
        f'<part eId="part-VII">'
        f"<content><p>Second VII head-note.</p></content>"
        f'<section eId="part-VII__sec-2"><num>2</num><heading>B</heading>'
        f"<content><p>body</p></content></section>"
        f"</part>"
        f"</body></act></akomaNtoso>"
    )
    sections, _ = build_sections(root, build_ref_index(_all_nav_eids(root)))

    assert "part-VII__head" in sections
    assert "part-VII__head~2" in sections
    assert "First VII head-note" in sections["part-VII__head"]["html"]
    assert "Second VII head-note" in sections["part-VII__head~2"]["html"]
