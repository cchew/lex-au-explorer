"""Stage 2 render walk: IR (:class:`Node`) -> HTML string via a style map."""

from __future__ import annotations

from build.ir import Node
from build.render import render_section
from build.stylemap import HtmlStyleMap

S = HtmlStyleMap()


def test_emphasis_and_ref_html() -> None:
    n = Node("section", {}, [Node("content", children=[Node("para", children=[
        Node("text", text="See "),
        Node("ref", {"href": "#sec-3", "text": "section 3",
                     "status": "resolved", "target_eid": "p__sec-3"}),
        Node("text", text=" and "),
        Node("emphasis", {"style": "bold"}, [Node("text", text="asset")]),
        Node("text", text="."),
    ])])])
    html = render_section(n, S)
    assert '<a class="akn-ref" data-eid="p__sec-3" href="#p__sec-3">section 3</a>' in html
    assert "<strong>asset</strong>" in html
    assert html.count("<p>") == 1


def test_ambiguous_ref_renders_as_span() -> None:
    n = Node("section", {}, [Node("content", children=[Node("para", children=[
        Node("ref", {"text": "section 3", "status": "ambiguous"})])])])
    html = render_section(n, S)
    assert '<span class="akn-ref akn-ref-unresolved">section 3</span>' in html
    assert "<a " not in html


def test_table_html_thead_tbody() -> None:
    n = Node("section", {}, [Node("table", children=[
        Node("row", {"header": True}, [Node("cell", {"td": False}, [Node("text", text="Item")])]),
        Node("row", children=[Node("cell", {"td": True}, [Node("text", text="1.")])]),
    ])])
    html = render_section(n, S)
    assert '<table class="akn-table"><thead><tr><th>Item</th></tr></thead>' in html
    assert "<tbody><tr><td>1.</td></tr></tbody>" in html


def test_clause_marker_has_no_parens() -> None:
    n = Node("section", {}, [Node("provision", {"level": "clause", "num": "2", "eid": "sch__cl2"},
             [Node("content", children=[Node("para", children=[Node("text", text="Body.")])])])])
    html = render_section(n, S)
    assert '<span class="akn-num">2</span>' in html  # not "(2)"


def test_subsection_marker_has_parens() -> None:
    n = Node("section", {}, [Node("provision", {"level": "subsection", "num": "1", "eid": "s__ss1"},
             [Node("content", children=[Node("para", children=[Node("text", text="Body.")])])])])
    assert '<span class="akn-num">(1)</span>' in render_section(n, S)


def test_provision_heading_is_rendered_when_present() -> None:
    n = Node("section", {}, [Node(
        "provision",
        {"level": "clause", "num": "2", "eid": "sch__cl2", "heading": "Application"},
        [Node("content", children=[Node("para", children=[Node("text", text="Body.")])])],
    )])
    html = render_section(n, S)
    assert '<span class="akn-provision-heading">Application</span>' in html
    assert html.index("akn-provision-heading") < html.index("Body.")


def test_provision_without_heading_emits_no_heading_span() -> None:
    n = Node("section", {}, [Node(
        "provision",
        {"level": "subsection", "num": "1", "eid": "s__ss1"},
        [Node("content", children=[Node("para", children=[Node("text", text="Body.")])])],
    )])
    assert "akn-provision-heading" not in render_section(n, S)


def test_missing_figure_renders_placeholder_not_blank() -> None:
    n = Node("section", {}, [Node("figure", {"src": "x.png", "alt": "Method statement", "asset": False})])
    html = render_section(n, S)
    assert "akn-figure-missing" in html and "Method statement" in html


def test_text_is_escaped() -> None:
    n = Node("section", {}, [Node("content", children=[Node("para", children=[
        Node("text", text='a < b & "c"')])])])
    assert "a &lt; b &amp; &quot;c&quot;" in render_section(n, S)


def test_custom_stylemap_can_override_one_kind() -> None:
    class MyMap(HtmlStyleMap):
        def _example(self, node: Node, children: list[str]) -> str:
            return f'<aside class="ex">{"".join(children)}</aside>'

    n = Node("section", {}, [Node("example", children=[Node("content", children=[
        Node("para", children=[Node("text", text="E")])])])])
    assert '<aside class="ex">' in render_section(n, MyMap())
