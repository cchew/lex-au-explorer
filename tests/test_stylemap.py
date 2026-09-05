"""Unit coverage for :class:`build.stylemap.HtmlStyleMap` per-kind methods.

Every ``_<kind>`` is exercised directly with hand-built children strings so a
regression in one row of the dispatch table fails in isolation. Security
constraints (escape every text and attribute value; never emit ``<script>``,
``on*``, ``style`` or ``javascript:``) are asserted against hostile input.
"""

from __future__ import annotations

import re

from build.ir import KINDS, Node
from build.render import render_section
from build.stylemap import HtmlStyleMap, StyleMap

S = HtmlStyleMap()

XSS = '"><script>alert(1)</script>'


def test_stylemap_has_one_method_per_kind() -> None:
    missing = sorted(k for k in KINDS if not hasattr(S, "_" + k))
    assert missing == []


def test_htmlstylemap_is_a_stylemap() -> None:
    assert isinstance(S, StyleMap)


def test_dispatch_falls_back_to_raw_for_unknown_kind() -> None:
    out = S.render(Node("totally_unknown"), ["a", "b"])
    assert out == "ab"


def test_section_content_para_join() -> None:
    assert S._section(Node("section"), ["x", "y"]) == "xy"
    assert S._content(Node("content"), ["x", "y"]) == "xy"
    assert S._para(Node("para"), ["x", "y"]) == "<p>xy</p>"


def test_text_escapes_all_html_metacharacters() -> None:
    assert S._text(Node("text", text='<a> & "b" \'c\''), []) == \
        "&lt;a&gt; &amp; &quot;b&quot; &#x27;c&#x27;"


def test_emphasis_bold_vs_italic() -> None:
    assert S._emphasis(Node("emphasis", {"style": "bold"}), ["z"]) == "<strong>z</strong>"
    assert S._emphasis(Node("emphasis", {"style": "italic"}), ["z"]) == "<em>z</em>"
    assert S._emphasis(Node("emphasis", {}), ["z"]) == "<em>z</em>"


def test_term_escapes_term_and_display() -> None:
    out = S._term(Node("term", {"term": XSS, "display": XSS}), [])
    assert out == (
        '<span data-term="&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;">'
        "&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;</span>"
    )
    assert "<script>" not in out


def test_ref_resolved_links_with_escaped_eid() -> None:
    out = S._ref(Node("ref", {"text": "s 3", "status": "resolved",
                              "target_eid": 'e"vil'}), [])
    assert out == '<a class="akn-ref" data-eid="e&quot;vil" href="#e&quot;vil">s 3</a>'


def test_ref_unresolved_never_emits_anchor() -> None:
    for status in ("ambiguous", "unresolved", "external", ""):
        out = S._ref(Node("ref", {"text": "s 3", "status": status}), [])
        assert out == '<span class="akn-ref akn-ref-unresolved">s 3</span>'
        assert "<a " not in out


def test_date_and_quantity_wrap_children() -> None:
    assert S._date(Node("date"), ["1 July 2000"]) == '<span class="akn-date">1 July 2000</span>'
    assert S._quantity(Node("quantity"), ["$5"]) == '<span class="akn-quantity">$5</span>'


def test_inline_raw_and_raw_join_children() -> None:
    assert S._inline_raw(Node("inline_raw"), ["a", "b"]) == "ab"
    assert S._raw(Node("raw"), ["a", "b"]) == "ab"


def test_note_with_label_emits_label_span() -> None:
    out = S._note(Node("note", {"label": "Note:"}), ["<p>body</p>"])
    assert out == ('<div class="akn-notetext"><span class="akn-note-label">Note:</span>'
                   "<p>body</p></div>")


def test_note_without_label_omits_span() -> None:
    out = S._note(Node("note", {}), ["<p>body</p>"])
    assert out == '<div class="akn-notetext"><p>body</p></div>'


def test_example_penalty_list_intro_wrappers() -> None:
    assert S._example(Node("example"), ["b"]) == '<div class="akn-exampletext">b</div>'
    assert S._penalty(Node("penalty"), ["b"]) == '<div class="akn-penaltytext">b</div>'
    assert S._list(Node("list"), ["b"]) == '<div class="akn-list">b</div>'
    assert S._intro(Node("intro"), ["b"]) == '<p class="akn-intro">b</p>'


def test_item_with_num_and_without() -> None:
    assert S._item(Node("item", {"num": "a"}), ["b"]) == (
        '<div class="akn-item"><span class="akn-num">(a)</span>'
        '<div class="akn-body">b</div></div>'
    )
    assert S._item(Node("item", {}), ["b"]) == (
        '<div class="akn-item"><div class="akn-body">b</div></div>'
    )


def test_provision_emits_level_class_eid_and_marker() -> None:
    node = Node("provision", {"level": "paragraph", "num": "a", "eid": "s1__p_a"})
    out = S._provision(node, ["<p>x</p>"])
    assert out == (
        '<div class="akn-paragraph" id="s1__p_a"><span class="akn-num">(a)</span>'
        '<div class="akn-body"><p>x</p></div></div>'
    )


def test_provision_without_eid_omits_id_attr() -> None:
    out = S._provision(Node("provision", {"level": "clause", "num": "3"}), ["x"])
    assert out == (
        '<div class="akn-clause"><span class="akn-num">3</span>'
        '<div class="akn-body">x</div></div>'
    )


def test_provision_escapes_level_and_eid() -> None:
    out = S._provision(Node("provision", {"level": XSS, "num": XSS, "eid": XSS}), ["x"])
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_figure_asset_uses_basename_only() -> None:
    out = S._figure(Node("figure", {"asset": True, "src": "/x/y/../secret/diagram.png",
                                    "alt": "Flow"}), [])
    assert out == '<figure><img src="/data/images/diagram.png" alt="Flow"></figure>'


def test_figure_renders_dimensions_when_asset_present() -> None:
    node = Node("figure", {"src": "corpus/images/x/x-fig-1.png",
                           "width": "320", "height": "200", "asset": True})
    html = S._figure(node, [])
    assert 'width="320"' in html and 'height="200"' in html and "<img" in html


def test_figure_asset_without_dimensions_emits_no_width_height() -> None:
    node = Node("figure", {"asset": True, "src": "/x/y/diagram.png", "alt": "Flow"})
    out = S._figure(node, [])
    assert out == '<figure><img src="/data/images/diagram.png" alt="Flow"></figure>'
    assert "width=" not in out and "height=" not in out


def test_figure_placeholder_ignores_dimensions() -> None:
    node = Node("figure", {"asset": False, "src": "d.png", "alt": "Diagram",
                           "width": "320", "height": "200"})
    out = S._figure(node, [])
    assert out == '<figure class="akn-figure-missing">[figure: Diagram]</figure>'
    assert "width=" not in out and "height=" not in out


def test_figure_dimensions_are_escaped() -> None:
    node = Node("figure", {"asset": True, "src": "d.png", "alt": "",
                           "width": XSS, "height": XSS})
    out = S._figure(node, [])
    assert "<script>" not in out
    assert 'width="&quot;&gt;&lt;script&gt;' in out


def test_figure_missing_falls_back_to_alt_then_src() -> None:
    assert S._figure(Node("figure", {"asset": False, "src": "d.png", "alt": "Diagram"}), []) == \
        '<figure class="akn-figure-missing">[figure: Diagram]</figure>'
    assert S._figure(Node("figure", {"asset": False, "src": "d.png", "alt": ""}), []) == \
        '<figure class="akn-figure-missing">[figure: d.png]</figure>'


def test_figure_escapes_alt_and_basename() -> None:
    out = S._figure(Node("figure", {"asset": True, "src": XSS + ".png", "alt": XSS}), [])
    assert "<script>" not in out
    out2 = S._figure(Node("figure", {"asset": False, "src": XSS, "alt": XSS}), [])
    assert "<script>" not in out2


def test_cell_colspan_rowspan_when_present() -> None:
    out = S._cell(Node("cell", {"td": True, "colspan": "2", "rowspan": "3"}), ["v"])
    assert out == '<td colspan="2" rowspan="3">v</td>'
    assert S._cell(Node("cell", {"td": False}), ["h"]) == "<th>h</th>"


def test_cell_renders_br_between_lines() -> None:
    node = Node("cell", {"td": True, "lines": ["Column 1", "Basic amount"]})
    assert S._cell(node, []) == "<td>Column 1<br>Basic amount</td>"


def test_cell_escapes_then_breaks() -> None:
    node = Node("cell", {"td": True, "lines": ["<script>", "x"]})
    assert S._cell(node, []) == "<td>&lt;script&gt;<br>x</td>"


def test_single_line_cell_no_br() -> None:
    node = Node("cell", {"td": True, "lines": ["Just one"]})
    assert S._cell(node, []) == "<td>Just one</td>"


def test_cell_colspan_survives_multiline_lines() -> None:
    node = Node("cell", {"td": True, "colspan": "2", "lines": ["a", "b"]})
    assert S._cell(node, []) == '<td colspan="2">a<br>b</td>'


def test_table_without_header_row_is_all_tbody() -> None:
    n = Node("table", children=[
        Node("row", children=[Node("cell", {"td": True}, [Node("text", text="a")])]),
        Node("row", children=[Node("cell", {"td": True}, [Node("text", text="b")])]),
    ])
    out = render_section(n, S)
    assert out == ('<div class="akn-table-scroll"><table class="akn-table">'
                   "<tbody><tr><td>a</td></tr>"
                   "<tr><td>b</td></tr></tbody></table></div>")


def test_table_empty_has_no_thead_or_tbody() -> None:
    assert S._table(Node("table"), []) == (
        '<div class="akn-table-scroll"><table class="akn-table"></table></div>'
    )


def test_no_script_or_event_handlers_survive_a_full_walk() -> None:
    n = Node("section", {}, [Node("content", children=[Node("para", children=[
        Node("text", text='<img src=x onerror="alert(1)">'),
        Node("ref", {"text": "<script>", "status": "resolved",
                     "target_eid": 'javascript:alert(1)'}),
        Node("emphasis", {"style": "bold"}, [Node("text", text="</strong><script>x</script>")]),
    ])])])
    out = render_section(n, S)
    # Hostile text is inert: angle brackets escaped, so no real tag/attribute
    # is ever formed from it.
    assert "<script>" not in out
    assert "<img" not in out
    assert re.search(r"<\w+\s+on\w+=", out) is None  # no on* attr on a real tag
    # target_eid only ever lands as a "#"-prefixed fragment, never a bare URL.
    assert 'href="javascript:' not in out
    assert '&lt;img src=x onerror=' in out  # proof the payload was escaped


def test_custom_stylemap_subclass_overrides_single_kind() -> None:
    class LoudRefs(HtmlStyleMap):
        def _ref(self, node: Node, children: list[str]) -> str:
            return f'[[{node.attrs.get("text", "")}]]'

    n = Node("section", {}, [Node("content", children=[Node("para", children=[
        Node("ref", {"text": "s 5", "status": "resolved", "target_eid": "e"})])])])
    assert "[[s 5]]" in render_section(n, LoudRefs())
    # untouched kinds still use the default
    assert "<p>" in render_section(n, LoudRefs())
