from __future__ import annotations

import collections
from types import SimpleNamespace

from build.refindex import Resolution, build_ref_index


class FakeResolver:
    """Duck-typed stand-in for lexaugraph.resolver.DefinitionResolver.

    The real class exposes resolve_definition(term, act_frbr_uri,
    section_eid=None). RefIndex has no Act URI in scope, so it calls the
    single-argument form the Task 3 brief specifies; real wiring supplies an
    adapter that binds act_frbr_uri.
    """

    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping: dict[str, str] = mapping
        self.calls: list[str] = []

    def resolve_definition(self, term: str):
        self.calls.append(term)
        eid = self.mapping.get(term)
        if eid is None:
            return None
        return SimpleNamespace(section_eid=eid)


def test_ambiguous_section_number_is_not_linked() -> None:
    # corp-act-s3.xml and corp-act-s3-sbg.xml: two distinct eIds, same number.
    nav = [
        "chapter-1__part-1.1__sec-3",
        "chapter-1__part-1.5__sec-3",
        "chapter-2J__part-2J.1__sec-601",
    ]
    idx = build_ref_index(nav)
    res = idx.resolve("#sec-3", from_eid="chapter-1__part-1.1__sec-3")
    assert res.status == "ambiguous"
    assert res.target_eid is None


def test_unique_section_resolves() -> None:
    nav = [
        "chapter-1__part-1.1__sec-3",
        "chapter-1__part-1.5__sec-3",
        "chapter-2J__part-2J.1__sec-601",
    ]
    idx = build_ref_index(nav)
    res = idx.resolve("#sec-601", from_eid="chapter-1__part-1.1__sec-3")
    assert res == Resolution(status="resolved", target_eid="chapter-2J__part-2J.1__sec-601")


def test_part_number_unresolved_when_no_exact_suffix() -> None:
    # Real Part eIds are dot/hyphen-scoped (part-2J.1, part-1-3); a bare
    # "#part-2J" suffix-matches nothing. The spike removed the chapter-<n>
    # fabrication fallback.
    nav = [
        "chapter-2J__part-2J.1__sec-601",
        "chapter-1__part-1-3__dvs-4__sec-4-15",
    ]
    idx = build_ref_index(nav)
    res = idx.resolve("#part-2J", from_eid="chapter-2J__part-2J.1__sec-601")
    assert res.status == "unresolved"
    assert res.target_eid is None

    # Sanity: an eId that genuinely ends "__part-5" does resolve.
    idx2 = build_ref_index(["chapter-1__part-5", "chapter-1__part-5__sec-1"])
    res2 = idx2.resolve("#part-5", from_eid="chapter-1__part-5__sec-1")
    assert res2 == Resolution(status="resolved", target_eid="chapter-1__part-5")


def test_division_scoped_by_referring_part() -> None:
    nav = [
        "chapter-1__part-1-3__dvs-4",
        "chapter-1__part-1-3__dvs-4__sec-4-15",
        "chapter-5__part-5-1__dvs-4",
        "chapter-5__part-5-1__dvs-4__sec-100-1",
    ]
    idx = build_ref_index(nav)
    res = idx.resolve("#dvs-4", from_eid="chapter-1__part-1-3__dvs-4__sec-4-15")
    assert res == Resolution(status="resolved", target_eid="chapter-1__part-1-3__dvs-4")

    # Referring section carries no Part segment: cannot scope -> unresolved.
    res2 = idx.resolve("#dvs-4", from_eid="sec-4-15")
    assert res2.status == "unresolved"


def test_division_ambiguous_when_part_scope_has_two_candidates() -> None:
    nav = [
        "chapter-1__part-1-3__dvs-4",
        "chapter-1__part-1-3__sdvs-1__dvs-4",
    ]
    idx = build_ref_index(nav)
    res = idx.resolve("#dvs-4", from_eid="chapter-1__part-1-3__dvs-4__sec-4-15")
    assert res.status == "ambiguous"
    assert res.target_eid is None


def test_subsection_ref_falls_back_to_owning_section() -> None:
    nav = [
        "chapter-2D__part-2D.2__sec-923A",
        "chapter-2D__part-2D.2__sec-923A__subsec-1",
    ]
    idx = build_ref_index(nav)

    # Deep match is unique -> resolve to the subsection itself.
    exact = idx.resolve("#sec-923A__subsec-1", from_eid="chapter-2D__part-2D.2__sec-923A")
    assert exact == Resolution(
        status="resolved",
        target_eid="chapter-2D__part-2D.2__sec-923A__subsec-1",
    )

    # Deep match misses -> strip trailing segment, resolve owning section.
    fallback = idx.resolve("#sec-923A__subsec-9", from_eid="chapter-2D__part-2D.2__sec-923A")
    assert fallback == Resolution(
        status="resolved",
        target_eid="chapter-2D__part-2D.2__sec-923A",
    )


def test_subsection_ref_ambiguous_owning_section_is_not_linked() -> None:
    nav = [
        "chapter-1__part-1.1__sec-3",
        "chapter-1__part-1.5__sec-3",
    ]
    idx = build_ref_index(nav)
    res = idx.resolve("#sec-3__subsec-2", from_eid="chapter-1__part-1.1__sec-3")
    assert res.status == "ambiguous"
    assert res.target_eid is None


def test_term_ref_uses_resolver() -> None:
    fr = FakeResolver({"financial year": "chapter-1__part-1-3__dvs-4__sec-995-1"})
    idx = build_ref_index(
        ["chapter-1__part-1-3__dvs-4__sec-995-1"], term_resolver=fr
    )
    res = idx.resolve(
        "#term-financial-year", from_eid="chapter-1__part-1-3__dvs-4__sec-4-10"
    )
    assert res == Resolution(
        status="resolved", target_eid="chapter-1__part-1-3__dvs-4__sec-995-1"
    )
    assert fr.calls == ["financial year"]

    # Resolver miss -> unresolved.
    miss = idx.resolve("#term-not-a-term", from_eid="x")
    assert miss.status == "unresolved"
    assert miss.target_eid is None

    # No resolver wired -> unresolved, no crash.
    idx2 = build_ref_index([])
    assert idx2.resolve("#term-financial-year", from_eid="x").status == "unresolved"


def test_empty_href_unresolved() -> None:
    idx = build_ref_index(["chapter-1__part-1.1__sec-3"])
    assert idx.resolve("", from_eid="x") == Resolution("unresolved", None)
    assert idx.resolve("https://example.com/s3", from_eid="x").status == "unresolved"
    assert idx.resolve("sec-3", from_eid="x").status == "unresolved"


def test_constitution_ref_not_linked() -> None:
    # corp-act-s3.xml commits #sec-51 / #sec-122 refs whose display text names
    # the Constitution; a same-Act sec-51 eId exists and must NOT be linked.
    nav = ["chapter-1__part-1.1__sec-51", "chapter-1__part-1.1__sec-3"]
    idx = build_ref_index(nav)
    res = idx.resolve(
        "#sec-51",
        from_eid="chapter-1__part-1.1__sec-3",
        display_text="the Constitution",
    )
    assert res.status == "unresolved"
    assert res.target_eid is None

    # Without the Constitution display text the same href resolves uniquely.
    res2 = idx.resolve("#sec-51", from_eid="chapter-1__part-1.1__sec-3")
    assert res2 == Resolution("resolved", "chapter-1__part-1.1__sec-51")


def test_itaa_hyphenated_section_from_display_text() -> None:
    nav = [
        "chapter-1__part-1-3__dvs-4__sec-4-15",
        "chapter-1__part-1-3__dvs-4__sec-4-10",
    ]
    idx = build_ref_index(nav)
    res = idx.resolve(
        "#sec-4",
        from_eid="chapter-1__part-1-3__dvs-4__sec-4-10",
        display_text="section 4-15",
    )
    assert res == Resolution(
        status="resolved", target_eid="chapter-1__part-1-3__dvs-4__sec-4-15"
    )

    # Truncated href alone (no usable display text) matches no eId -> unresolved.
    res2 = idx.resolve("#sec-4", from_eid="chapter-1__part-1-3__dvs-4__sec-4-10")
    assert res2.status == "unresolved"

    # "subsection 4-15" form is also recognised.
    res3 = idx.resolve(
        "#sec-4",
        from_eid="chapter-1__part-1-3__dvs-4__sec-4-10",
        display_text="see subsection 4-15 of this Act",
    )
    assert res3.target_eid == "chapter-1__part-1-3__dvs-4__sec-4-15"


def test_scrambled_display_text_does_not_link_wrong_provision() -> None:
    # Spike F.5: the trailing <ref>'s display text was lifted from another
    # provision. href pre-hyphen digits ("4") disagree with the display text's
    # pre-hyphen digits ("923"), so the rebuilt eId must NOT be linked even
    # though it exists in the nav list.
    nav = [
        "chapter-1__part-1-3__dvs-4__sec-4-10",
        "chapter-9__part-9-1__dvs-2__sec-923-1",
    ]
    idx = build_ref_index(nav)
    res = idx.resolve(
        "#sec-4",
        from_eid="chapter-1__part-1-3__dvs-4__sec-4-10",
        display_text="section 923-1",
    )
    assert res.status == "unresolved"
    assert res.target_eid is None


def test_hyphenated_rebuild_ambiguous_is_unresolved() -> None:
    # Rebuilt sec-4-15 suffix-matches two eIds under different prefixes.
    nav = [
        "chapter-1__part-1-3__dvs-4__sec-4-15",
        "chapter-1__part-1-5__dvs-9__sec-4-15",
        "chapter-1__part-1-3__dvs-4__sec-4-10",
    ]
    idx = build_ref_index(nav)
    res = idx.resolve(
        "#sec-4",
        from_eid="chapter-1__part-1-3__dvs-4__sec-4-10",
        display_text="section 4-15",
    )
    assert res.status == "unresolved"
    assert res.target_eid is None


def test_dead_families_fall_through_to_unresolved() -> None:
    nav = [
        "chapter-1__part-1.1__sec-3",
        "chapter-1",
        "chapter-1__part-1.1",
    ]
    idx = build_ref_index(nav)
    for href in ("#chapter-1", "#chp-1", "#sch-2", "#subdvs-1"):
        res = idx.resolve(href, from_eid="chapter-1__part-1.1__sec-3")
        assert res.status == "unresolved", href
        assert res.target_eid is None


def test_tally_counts_every_resolve_call() -> None:
    nav = [
        "chapter-1__part-1.1__sec-3",
        "chapter-1__part-1.5__sec-3",
        "chapter-2J__part-2J.1__sec-601",
    ]
    idx = build_ref_index(nav)
    idx.resolve("#sec-601", from_eid="x")        # resolved
    idx.resolve("#sec-3", from_eid="x")          # ambiguous
    idx.resolve("", from_eid="x")               # unresolved
    idx.resolve("#sec-999", from_eid="x")        # unresolved
    idx.resolve("#chapter-1", from_eid="x")      # unresolved (dead family)

    assert isinstance(idx.tally, collections.Counter)
    assert sum(idx.tally.values()) == 5
    assert idx.tally["resolved"] == 1
    assert idx.tally["ambiguous"] == 1
    assert idx.tally["unresolved"] == 3


def test_index_covers_non_section_navigables() -> None:
    # Index must be built from ALL navigable eIds, not sections only: a
    # division container (non-section) is a resolvable target.
    nav = [
        "schedule-1",
        "schedule-1__clause-70-20",
        "chapter-1__part-1-3__dvs-4",
        "chapter-1__part-1-3__dvs-4__sec-4-15",
    ]
    idx = build_ref_index(nav)
    res = idx.resolve("#dvs-4", from_eid="chapter-1__part-1-3__dvs-4__sec-4-15")
    assert res.status == "resolved"
    assert res.target_eid == "chapter-1__part-1-3__dvs-4"
