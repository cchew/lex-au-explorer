"""Stage 2 style maps: turn a semantic :class:`~build.ir.Node` and its
already-rendered children into an HTML string.

:class:`StyleMap` is the structural contract the render walk
(:func:`build.render.render_section`) depends on. :class:`HtmlStyleMap` is the
default implementation: one ``_<kind>`` method per entry in
:data:`build.ir.KINDS`, dispatched by :meth:`HtmlStyleMap.render` via
``getattr(self, "_" + node.kind, self._raw)``.

Security contract (the rendered string is injected into the reader via Vue's
``v-html``): every text value and every attribute value is passed through
:func:`html.escape`. No ``_<kind>`` method emits a ``<script>`` element, an
``on*`` handler attribute, a ``style`` attribute, or a ``javascript:`` URL.
Subclasses that override a method inherit this obligation.
"""

from __future__ import annotations

import html
import os.path
from typing import Protocol, runtime_checkable

import lxml.etree as ET

from build.ir import Node

__all__ = ["StyleMap", "HtmlStyleMap", "_render_inline"]


@runtime_checkable
class StyleMap(Protocol):
    """Render one node given its children rendered to strings.

    ``children`` is the list of child render results in document order, never a
    pre-joined blob: container kinds (``table``, ``list``, ``row``) need the
    individual elements to wrap or interleave them.
    """

    def render(self, node: Node, children: list[str]) -> str: ...


def _esc(value: object) -> str:
    """Escape any value for use in text content or a double-quoted attribute."""
    return html.escape("" if value is None else str(value), quote=True)


class HtmlStyleMap:
    """Default semantic-HTML style map for the legislation reader."""

    # Per-level provision marker. ``clause`` / ``subclause`` (schedule
    # provisions) render a bare number to match the gov Schedule render; the
    # Act-body levels are parenthesised.
    MARKERS: dict[str, str] = {
        "subsection": "({num})",
        "paragraph": "({num})",
        "subparagraph": "({num})",
        "clause": "{num}",
        "subclause": "{num}",
    }

    # ------------------------------------------------------------------ #
    # Dispatch
    # ------------------------------------------------------------------ #

    def render(self, node: Node, children: list[str]) -> str:
        handler = getattr(self, "_" + node.kind, self._raw)
        return handler(node, children)

    # ------------------------------------------------------------------ #
    # Structural containers
    # ------------------------------------------------------------------ #

    def _section(self, node: Node, children: list[str]) -> str:
        return "".join(children)

    def _content(self, node: Node, children: list[str]) -> str:
        return "".join(children)

    def _para(self, node: Node, children: list[str]) -> str:
        return f"<p>{''.join(children)}</p>"

    def _provision(self, node: Node, children: list[str]) -> str:
        level = str(node.attrs.get("level", "") or "")
        eid = str(node.attrs.get("eid", "") or "")
        num = str(node.attrs.get("num", "") or "")
        heading = str(node.attrs.get("heading", "") or "")
        marker = ""
        if num:
            marker = self.MARKERS.get(level, "{num}").format(num=num)
        id_attr = f' id="{_esc(eid)}"' if eid else ""
        heading_span = (
            f'<span class="akn-provision-heading">{_esc(heading)}</span>'
            if heading
            else ""
        )
        return (
            f'<div class="akn-{_esc(level)}"{id_attr}>'
            f'<span class="akn-num">{_esc(marker)}</span>'
            f'<div class="akn-body">{heading_span}{"".join(children)}</div>'
            "</div>"
        )

    # ------------------------------------------------------------------ #
    # Block text constructs
    # ------------------------------------------------------------------ #

    def _note(self, node: Node, children: list[str]) -> str:
        label = str(node.attrs.get("label", "") or "")
        label_span = (
            f'<span class="akn-note-label">{_esc(label)}</span>' if label else ""
        )
        return f'<div class="akn-notetext">{label_span}{"".join(children)}</div>'

    def _example(self, node: Node, children: list[str]) -> str:
        return f'<div class="akn-exampletext">{"".join(children)}</div>'

    def _penalty(self, node: Node, children: list[str]) -> str:
        return f'<div class="akn-penaltytext">{"".join(children)}</div>'

    def _list(self, node: Node, children: list[str]) -> str:
        return f'<div class="akn-list">{"".join(children)}</div>'

    def _intro(self, node: Node, children: list[str]) -> str:
        return f'<p class="akn-intro">{"".join(children)}</p>'

    def _item(self, node: Node, children: list[str]) -> str:
        num = str(node.attrs.get("num", "") or "")
        marker = (
            f'<span class="akn-num">({_esc(num)})</span>' if num else ""
        )
        return (
            f'<div class="akn-item">{marker}'
            f'<div class="akn-body">{"".join(children)}</div></div>'
        )

    # ------------------------------------------------------------------ #
    # Tables
    # ------------------------------------------------------------------ #

    def _table(self, node: Node, children: list[str]) -> str:
        header_idx: int | None = None
        for i, child in enumerate(node.children):
            if child.kind == "row" and child.attrs.get("header"):
                header_idx = i
                break
        thead = ""
        if header_idx is not None:
            thead = f"<thead>{children[header_idx]}</thead>"
        body_rows = [
            row for i, row in enumerate(children) if i != header_idx
        ]
        tbody = f"<tbody>{''.join(body_rows)}</tbody>" if body_rows else ""
        # Wrapper owns the horizontal scroll; the <table> keeps display:table +
        # border-collapse (both inert on a display:block element -> doubled
        # borders). CSS: .akn-table-scroll { overflow-x: auto }.
        return (
            '<div class="akn-table-scroll">'
            f'<table class="akn-table">{thead}{tbody}</table>'
            "</div>"
        )

    def _row(self, node: Node, children: list[str]) -> str:
        return f"<tr>{''.join(children)}</tr>"

    def _cell(self, node: Node, children: list[str]) -> str:
        tag = "td" if node.attrs.get("td") else "th"
        span_attrs = ""
        for attr in ("colspan", "rowspan"):
            value = node.attrs.get(attr)
            if value is not None and str(value) != "":
                span_attrs += f' {attr}="{_esc(value)}"'
        lines = node.attrs.get("lines")
        if lines:
            content = "<br>".join(_esc(x) for x in lines)
        else:
            content = "".join(children)
        return f"<{tag}{span_attrs}>{content}</{tag}>"

    # ------------------------------------------------------------------ #
    # Figures
    # ------------------------------------------------------------------ #

    def _figure(self, node: Node, children: list[str]) -> str:
        src = str(node.attrs.get("src", "") or "")
        alt = str(node.attrs.get("alt", "") or "")
        if node.attrs.get("asset"):
            basename = os.path.basename(src)
            return (
                f'<figure><img src="/data/images/{_esc(basename)}" '
                f'alt="{_esc(alt)}"></figure>'
            )
        return (
            f'<figure class="akn-figure-missing">[figure: {_esc(alt or src)}]'
            "</figure>"
        )

    # ------------------------------------------------------------------ #
    # Inline constructs
    # ------------------------------------------------------------------ #

    def _text(self, node: Node, children: list[str]) -> str:
        return _esc(node.text)

    def _emphasis(self, node: Node, children: list[str]) -> str:
        tag = "strong" if node.attrs.get("style") == "bold" else "em"
        return f"<{tag}>{''.join(children)}</{tag}>"

    def _term(self, node: Node, children: list[str]) -> str:
        term = str(node.attrs.get("term", "") or "")
        display = str(node.attrs.get("display", "") or "")
        return f'<span data-term="{_esc(term)}">{_esc(display)}</span>'

    def _ref(self, node: Node, children: list[str]) -> str:
        text = str(node.attrs.get("text", "") or "")
        if node.attrs.get("status") == "resolved":
            eid = str(node.attrs.get("target_eid", "") or "")
            return (
                f'<a class="akn-ref" data-eid="{_esc(eid)}" '
                f'href="#{_esc(eid)}">{_esc(text)}</a>'
            )
        return f'<span class="akn-ref akn-ref-unresolved">{_esc(text)}</span>'

    def _date(self, node: Node, children: list[str]) -> str:
        return f'<span class="akn-date">{"".join(children)}</span>'

    def _quantity(self, node: Node, children: list[str]) -> str:
        return f'<span class="akn-quantity">{"".join(children)}</span>'

    def _inline_raw(self, node: Node, children: list[str]) -> str:
        return "".join(children)

    # ------------------------------------------------------------------ #
    # Total fallback
    # ------------------------------------------------------------------ #

    def _raw(self, node: Node, children: list[str]) -> str:
        return "".join(children)


# --------------------------------------------------------------------------- #
# <preface> long title / enacting words (Task 6)
# --------------------------------------------------------------------------- #


def _render_inline(el: ET._Element) -> str:
    """Render ``el``'s inline children (text, ``<i>``/``<b>``/``<ref>``/
    ``<date>``/``<term>``, tails) to an HTML string via the existing Stage-1
    inline parse path (:func:`build.parse._parse_inline_into`) + Stage-2
    render (:func:`build.render.render_section`) -- bypassing
    :func:`build.parse.parse_section`'s block path entirely.

    That distinction matters here: ``<preface>`` has no ``<longTitle>``
    element in this corpus, only an unlabelled ``<p>`` (the parity spike's
    §3.1/§3.4 findings). Routing that ``<p>`` through ``parse_section`` would
    hit ``_parse_raw`` -> ``_parse_block``'s generic fallback, which recurses
    structurally but never calls ``_parse_inline`` -- so ``<i>``/``<b>``
    emphasis inside it would silently render as plain text. This function
    instead builds a throwaway ``content`` container node and appends ``el``'s
    inline children directly via ``_parse_inline_into``, the same call
    ``_parse_content`` makes for a real ``<p>`` inside ``<content>``.

    Placement note: this lives in ``stylemap.py`` (per the design brief) even
    though it needs ``build.parse``/``build.render``/``build.refindex``, all
    of which sit on the far side of a circular import from here --
    ``build.render`` imports this module (for the ``StyleMap`` protocol) and
    ``build.parse`` imports ``build.bundle`` (for ``AKN``/``_local_tag``),
    which itself imports this module at module level. A top-level
    ``from build.parse import ...`` here would therefore cycle back into this
    module before it finished defining :class:`HtmlStyleMap`. The imports
    below are function-scoped (deferred until call time, by which point every
    module has finished loading) to break that cycle -- the same technique
    ``build.bundle.build_sections`` already uses for the same reason (see its
    "Lazy: build.parse imports AKN / _local_tag back from this module."
    comment).

    ``el`` is assumed free of ``<ref>`` elements: verified against the full
    3,076-Act lex-au corpus, zero ``<ref>`` occur inside any ``<preface>``.
    A fresh, empty :class:`~build.refindex.RefIndex` is therefore sufficient
    -- there is nothing for it to resolve -- and the ``section_eid=""``
    threaded into ``_parse_inline_into`` is never consulted for the same
    reason.
    """
    from build.parse import _parse_inline_into
    from build.refindex import RefIndex
    from build.render import render_section

    container = Node("content")
    _parse_inline_into(el, container, "", RefIndex([]))
    # A block-wrapping element like <formula> (a <p> inside it, for the
    # "enacting" field) carries pretty-printed indentation as the formula's
    # own .text (before the <p>) and the <p>'s .tail (after it) -- real,
    # verified corpus whitespace, not a fixture artifact. _parse_inline_into
    # preserves it verbatim (by design, for genuine inline text runs), so
    # strip only the ends here: interior whitespace from a real <p>'s own
    # text is never pretty-print noise and must stay untouched.
    return render_section(container, HtmlStyleMap()).strip()
