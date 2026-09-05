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

import lxml.etree as ET

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
    assert build_toc(root)[-1]["children"]  # schedule node has unit children


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
# eId-collision disambiguation -- Task 4
# --------------------------------------------------------------------------- #


def test_duplicate_clause_eids_both_kept() -> None:
    """Real-corpus regression: the converter flattens schedule Part/Division
    numbering so a-new-tax-system-(family-assistance)-act-1999's schedule-1
    has two distinct <clause eId="schedule-1__clause-30"> elements (see the
    fixture's header comment). Both must survive in ``sections`` -- silently
    overwriting the first with the second is permanent content loss."""
    root = _parse_corpus("sched-dup-eid.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, counts = build_sections(root, ix)

    assert "schedule-1__clause-30" in sections
    assert "schedule-1__clause-30~2" in sections
    assert sections["schedule-1__clause-30"]["html"] != sections["schedule-1__clause-30~2"]["html"]
    assert "Standard rate" not in sections["schedule-1__clause-30~2"]["html"]
    assert "June 2000 rate" in sections["schedule-1__clause-30~2"]["heading"]
    assert counts["disambiguated_eids"] == 1

    # invariant: one bundle key per source clause/unit (clause-30, clause-31,
    # clause-39, clause-30~2 -- no loose top-level content in this fixture).
    n_units = len(_schedule_units(
        next(root.iterfind(f".//{AKN}attachments/{AKN}attachment/{AKN}hcontainer[@name='schedule']"))
    ))
    assert n_units == 4
    assert len([k for k in sections if k.startswith("schedule-1")]) == n_units


def test_disambiguated_unit_has_unique_dom_id() -> None:
    """id-reachability, adjusted to how the reader actually resolves eIds
    (verified against web/src/views/ReaderView.vue): the DOM id a top-level
    bundle unit is reached by is `:id="s.eid"` on a wrapper the Vue app
    renders around `section.html` from the bundle's own dict key -- never an
    id baked inside `section.html` itself. `render_section`'s "section" kind
    (what a whole schedule clause/block parses to at the top level, see
    `parse_section`) never stamps its own eid as an `id=` attribute in the
    first place (only nested "provision" descendants do, via
    `HtmlStyleMap._provision`), so there is nothing of the *outer* clause's
    own eid to rewrite -- `_add_entry`'s ``html.replace`` is a correct,
    harmless no-op for every unit in this corpus, not a bug. What actually
    matters, and is checked here, is that a disambiguated unit's *own* nested
    provisions keep rendering correctly (their ids never collide with the
    outer clause's eid -- child eids always extend the parent's with a
    ``__`` segment, so they can't literally equal it) and that the two
    colliding units' html never cross-contaminate."""
    root = _parse_corpus("sched-dup-eid.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix)

    html2 = sections["schedule-1__clause-30~2"]["html"]
    assert 'id="schedule-1__clause-30__subclause-2"' in html2
    assert 'id="schedule-1__clause-30"' not in html2
    assert "Standard rate" not in html2  # not cross-contaminated with unit 1
    assert "has the same meaning as" in html2


def test_build_toc_agrees_with_bundle_on_disambiguated_keys() -> None:
    """build_toc's schedule-children list must list the same disambiguated
    keys build_sections actually used for `sections` -- otherwise the TOC and
    the bundle disagree about what eIds exist."""
    root = _parse_corpus("sched-dup-eid.xml")
    ix = build_ref_index(_all_nav_eids(root))
    sections, _ = build_sections(root, ix)

    toc = build_toc(root)
    sched_node = next(n for n in toc if n["eid"] == "schedule-1")
    toc_eids = [c["eid"] for c in sched_node["children"]]

    assert toc_eids == [
        "schedule-1__clause-30",
        "schedule-1__clause-31",
        "schedule-1__clause-39",
        "schedule-1__clause-30~2",
    ]
    assert set(toc_eids) == {k for k in sections if k.startswith("schedule-1")}


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
    """Task 3/4 invariant: every unit ``_schedule_units`` yields for a
    schedule lands under exactly one distinct bundle key. This is the
    regression guard for a collision silently collapsing two units into one
    key (proven to fail if ``_add_entry``'s collision branch is removed --
    see task-4-report.md)."""
    for fixture in (
        "sched-clause.xml",
        "sched-paragraphs.xml",
        "sched-table.xml",
        "sched-dup-eid.xml",
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
