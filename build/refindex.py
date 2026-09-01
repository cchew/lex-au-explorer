"""Same-Act cross-reference index and conservative resolution.

Pure stdlib module. Given the full set of navigable eIds for one Act, resolve
an AKN ``<ref href="#...">`` fragment to a single target eId, or decline.

The governing rule is conservative: never emit a wrong link. A wrong link is
the credibility failure this whole rendering-fidelity effort exists to prevent,
so anything that is ambiguous or lossy is reported as such and rendered as
plain text by the caller. Resolution rules follow the parity spike note
(``docs/superpowers/notes/2026-09-01-parity-spike.md``), section A.4, which
supersedes the earlier over-optimistic brief.

Families that the plan lists but that never occur in the corpus
(``#chapter-*``, ``#chp-*``, ``#sch-*``, ``#subdvs-*``, non-``#`` hrefs) have no
branch here; they fall through to ``unresolved``.
"""

from __future__ import annotations

import collections
import re
from dataclasses import dataclass
from typing import Iterable, Optional, Protocol

_SEGMENT_SEP = "__"

# ITAA hyphenated provision numbers ("section 4-15") that the href truncated at
# the hyphen ("#sec-4"). The full number survives only in the ref display text.
_HYPHENATED_PROVISION = re.compile(
    r"\b(?:sub)?section\s+(\d+-\d+[A-Za-z]?)\b", re.IGNORECASE
)

# Trailing sub-provision segments that can be stripped to fall back to the
# owning section (matched against the last "__"-delimited segment).
_STRIPPABLE_TAIL = re.compile(
    r"^(?:subsec|para|subpara|sub-para|item|subitem|subclause|clause)-", re.IGNORECASE
)


class _TermResolver(Protocol):
    """Minimal duck type this module needs from a definition resolver.

    ``lexaugraph.resolver.DefinitionResolver.resolve_definition`` actually takes
    ``(term, act_frbr_uri, section_eid=None)``. ``RefIndex`` has no Act URI in
    scope, so it calls the single-argument form the brief specifies; production
    wiring passes an adapter that binds ``act_frbr_uri`` (and may pass
    ``section_eid=from_eid``). The return value need only carry ``.section_eid``.
    """

    def resolve_definition(self, term: str): ...


@dataclass
class Resolution:
    status: str  # "resolved" | "ambiguous" | "unresolved"
    target_eid: Optional[str]


_UNRESOLVED = Resolution("unresolved", None)
_AMBIGUOUS = Resolution("ambiguous", None)


def _resolved(eid: str) -> Resolution:
    return Resolution("resolved", eid)


class RefIndex:
    """Suffix-match index over one Act's navigable eIds."""

    def __init__(
        self,
        nav_eids: Iterable[str],
        term_resolver: Optional[_TermResolver] = None,
    ) -> None:
        self._eids: list[str] = list(nav_eids)
        self._term_resolver: Optional[_TermResolver] = term_resolver
        self.tally: "collections.Counter[str]" = collections.Counter()

        # last "__" segment -> eIds ending with it (covers single-segment tails:
        # bare #sec-<n>, #part-<n>, #dvs-<n>).
        self._by_last: dict[str, list[str]] = collections.defaultdict(list)
        # any "__" segment -> eIds containing it (Part/Division scoping).
        self._by_segment: dict[str, list[str]] = collections.defaultdict(list)
        for eid in self._eids:
            segments = eid.split(_SEGMENT_SEP)
            self._by_last[segments[-1]].append(eid)
            for seg in segments:
                self._by_segment[seg].append(eid)

    # -- public API ---------------------------------------------------------

    def resolve(
        self, href: str, from_eid: str, display_text: str = ""
    ) -> Resolution:
        result = self._resolve(href, from_eid, display_text)
        self.tally[result.status] += 1
        return result

    # -- internals --------------------------------------------------------------

    def _suffix_match(self, tail: str) -> list[str]:
        """eIds equal to ``tail`` or ending with ``__`` + ``tail``."""
        last = tail.split(_SEGMENT_SEP)[-1]
        candidates = self._by_last.get(last, ())
        return [
            eid
            for eid in candidates
            if eid == tail or eid.endswith(_SEGMENT_SEP + tail)
        ]

    def _resolve(
        self, href: str, from_eid: str, display_text: str
    ) -> Resolution:
        if not href or not href.startswith("#"):
            return _UNRESOLVED
        target = href[1:]
        if not target:
            return _UNRESOLVED

        if target.startswith("term-"):
            return self._resolve_term(target)
        if target.startswith("sec-") and _SEGMENT_SEP in target:
            return self._resolve_sub_provision(target)
        if target.startswith("sec-"):
            return self._resolve_bare_section(target, display_text)
        if target.startswith("part-"):
            return self._resolve_part(target)
        if target.startswith("dvs-") or target.startswith("sdvs-"):
            return self._resolve_division(target, from_eid)

        # Dead / unknown families: #chapter-*, #chp-*, #sch-*, #subdvs-*, ...
        return _UNRESOLVED

    def _resolve_term(self, target: str) -> Resolution:
        if self._term_resolver is None:
            return _UNRESOLVED
        # AKN slug is hyphenated; the resolver wants the term name. Lossy for
        # terms that genuinely contain a hyphen (spike C).
        term_name = target[len("term-") :].replace("-", " ").strip()
        if not term_name:
            return _UNRESOLVED
        result = self._term_resolver.resolve_definition(term_name)
        if result is None:
            return _UNRESOLVED
        section_eid = getattr(result, "section_eid", None)
        if not section_eid:
            return _UNRESOLVED
        return _resolved(section_eid)

    def _resolve_bare_section(
        self, target: str, display_text: str
    ) -> Resolution:
        text = display_text or ""

        # Refs to the Australian Constitution reuse "#sec-51" / "#sec-122";
        # linking them to a same-Act eId is a wrong link (spike A.1).
        if "constitution" in text.lower():
            return _UNRESOLVED

        # ITAA hyphen-truncated href: rebuild the intended segment from the
        # display text and match THAT. Unique -> resolved, else unresolved
        # (never fall back to the lossy bare number).
        hyphenated = _HYPHENATED_PROVISION.search(text)
        if hyphenated:
            rebuilt = "sec-" + hyphenated.group(1)
            hits = self._suffix_match(rebuilt)
            return _resolved(hits[0]) if len(hits) == 1 else _UNRESOLVED

        hits = self._suffix_match(target)
        if len(hits) == 1:
            return _resolved(hits[0])
        if len(hits) >= 2:
            return _AMBIGUOUS
        return _UNRESOLVED

    def _resolve_sub_provision(self, target: str) -> Resolution:
        """``#sec-<n>__subsec-<m>`` and deeper.

        Try the full tail first (a deeper path can disambiguate a section
        number that is ambiguous on its own). On zero or many hits, strip the
        trailing sub-provision segment and retry, ending at the bare owning
        section, which must itself be unambiguous.
        """
        segment = target
        while True:
            hits = self._suffix_match(segment)
            if len(hits) == 1:
                return _resolved(hits[0])
            if _SEGMENT_SEP not in segment:
                # Reached the bare owning section.
                return _AMBIGUOUS if len(hits) >= 2 else _UNRESOLVED
            head, _, last = segment.rpartition(_SEGMENT_SEP)
            if not _STRIPPABLE_TAIL.match(last):
                # Unexpected tail shape; do not guess.
                return _UNRESOLVED
            segment = head

    def _resolve_part(self, target: str) -> Resolution:
        # Real Part eIds are dot/hyphen-scoped (part-2J.1, part-1-3) and never
        # suffix-match a bare "#part-<n>"; the common outcome is zero. No
        # chapter-<n> fabrication fallback (spike A.4.3).
        hits = self._suffix_match(target)
        if len(hits) == 1:
            return _resolved(hits[0])
        if len(hits) >= 2:
            return _AMBIGUOUS
        return _UNRESOLVED

    def _resolve_division(self, target: str, from_eid: str) -> Resolution:
        candidates = self._suffix_match(target)
        if not candidates:
            return _UNRESOLVED
        part_segment = _part_segment(from_eid)
        if part_segment is None:
            return _UNRESOLVED
        scoped = [
            eid
            for eid in candidates
            if part_segment in eid.split(_SEGMENT_SEP)
        ]
        if len(scoped) == 1:
            return _resolved(scoped[0])
        if len(scoped) >= 2:
            return _AMBIGUOUS
        return _UNRESOLVED


def _part_segment(eid: str) -> Optional[str]:
    for seg in eid.split(_SEGMENT_SEP):
        if seg.startswith("part-"):
            return seg
    return None


def build_ref_index(
    nav_eids: Iterable[str],
    term_resolver: Optional[_TermResolver] = None,
) -> RefIndex:
    return RefIndex(nav_eids, term_resolver)
