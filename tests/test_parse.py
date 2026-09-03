from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import lxml.etree as ET

from build.ir import Node
from build.parse import parse_section
from build.refindex import build_ref_index

NS = 'xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"'
AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"
FIX = Path(__file__).parent / "fixtures" / "corpus"


def _sec(inner: str, eid: str = "s1") -> ET._Element:
    return ET.fromstring(
        f'<section {NS} eId="{eid}"><heading>H</heading>{inner}</section>'
    )


def _load(name: str) -> ET._Element:
    return ET.parse(str(FIX / name)).getroot()


def _first_section(root: ET._Element) -> ET._Element:
    el = root.find(f".//{AKN}section")
    assert el is not None
    return el


def _nav(root: ET._Element) -> list[str]:
    return [el.get("eId") for el in root.iter() if el.get("eId")]


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _find(node: Node, pred: Callable[[Node], bool]) -> Optional[Node]:
    for n in _walk(node):
        if pred(n):
            return n
    return None


def _find_all(node: Node, pred: Callable[[Node], bool]) -> list[Node]:
    return [n for n in _walk(node) if pred(n)]


def _text(node: Node) -> str:
    return "".join(n.text for n in _walk(node) if n.kind == "text")


# --------------------------------------------------------------------------- #
# Inline
# --------------------------------------------------------------------------- #


def test_italic_bold_nested_to_emphasis() -> None:
    root = _load("itaa97-rate-table.xml")
    node = parse_section(_first_section(root), build_ref_index(_nav(root)))

    bold = _find(
        node,
        lambda n: n.kind == "emphasis" and n.attrs.get("style") == "bold",
    )
    assert bold is not None
    inner = bold.children[0]
    assert inner.kind == "emphasis" and inner.attrs["style"] == "italic"
    assert inner.children[0].kind == "text"
    assert inner.children[0].text == "taxable income"


def test_def_element_text_preserved_via_inline_raw() -> None:
    root = build_ref_index([])
    node = parse_section(
        _sec(
            "<subsection eId=\"s1__subsec-1\"><num>1</num><content>"
            "<p>A <def>company</def> is a body corporate.</p>"
            "</content></subsection>"
        ),
        root,
    )
    raw = _find(node, lambda n: n.kind == "inline_raw")
    assert raw is not None
    assert raw.attrs["tag"] == "def"
    assert raw.children[0].kind == "text"
    assert raw.children[0].text == "company"
    assert "A company is a body corporate." == _text(node).strip()


def test_ambiguous_ref_has_status_but_no_target_eid() -> None:
    nav = ["chapter-1__part-1.1__sec-3", "chapter-1__part-1.5__sec-3"]
    node = parse_section(
        _sec(
            "<content><p>See <ref href=\"#sec-3\">section 3</ref> for more.</p>"
            "</content>",
            eid="chapter-1__part-1.1__sec-9",
        ),
        build_ref_index(nav),
    )
    ref = _find(node, lambda n: n.kind == "ref")
    assert ref is not None
    assert ref.attrs["status"] == "ambiguous"
    assert "target_eid" not in ref.attrs
    assert ref.attrs["href"] == "#sec-3"
    assert ref.attrs["text"] == "section 3"


def test_resolved_ref_carries_target_eid() -> None:
    nav = ["chapter-2J__part-2J.1__sec-601", "chapter-1__part-1.1__sec-9"]
    node = parse_section(
        _sec(
            "<content><p>See <ref href=\"#sec-601\">section 601</ref>.</p></content>",
            eid="chapter-1__part-1.1__sec-9",
        ),
        build_ref_index(nav),
    )
    ref = _find(node, lambda n: n.kind == "ref")
    assert ref is not None
    assert ref.attrs["status"] == "resolved"
    assert ref.attrs["target_eid"] == "chapter-2J__part-2J.1__sec-601"


def test_cross_act_ref_tail_declines_resolution() -> None:
    """`<ref href="#sec-5">section 5</ref> of the Foo Act 1912` must not link,
    even though this Act has a `sec-5` -- the tail names a different Act (I2)."""
    nav = ["chapter-1__part-1.1__sec-5", "chapter-1__part-1.1__sec-9"]
    node = parse_section(
        _sec(
            "<content><p>see <ref href=\"#sec-5\">section 5</ref> of the "
            "Foo Act 1912 for context.</p></content>",
            eid="chapter-1__part-1.1__sec-9",
        ),
        build_ref_index(nav),
    )
    ref = _find(node, lambda n: n.kind == "ref")
    assert ref is not None
    assert ref.attrs["status"] == "unresolved"
    assert "target_eid" not in ref.attrs


def test_same_act_ref_tail_still_resolves() -> None:
    """The `of the` guard must not fire on `... of the Act`."""
    nav = ["chapter-1__part-1.1__sec-5", "chapter-1__part-1.1__sec-9"]
    node = parse_section(
        _sec(
            "<content><p>see <ref href=\"#sec-5\">section 5</ref> of the "
            "Act.</p></content>",
            eid="chapter-1__part-1.1__sec-9",
        ),
        build_ref_index(nav),
    )
    ref = _find(node, lambda n: n.kind == "ref")
    assert ref is not None
    assert ref.attrs["status"] == "resolved"
    assert ref.attrs["target_eid"] == "chapter-1__part-1.1__sec-5"


def test_date_and_quantity_kinds() -> None:
    node = parse_section(
        _sec(
            "<content><p>Before <date date=\"1997-07-01\">1 July 1997</date> "
            "and <quantity refersTo=\"#deadline\">within 60 days</quantity>.</p>"
            "</content>"
        ),
        build_ref_index([]),
    )
    d = _find(node, lambda n: n.kind == "date")
    q = _find(node, lambda n: n.kind == "quantity")
    assert d is not None and d.attrs["iso"] == "1997-07-01"
    assert _text(d) == "1 July 1997"
    assert q is not None and q.attrs["refers_to"] == "#deadline"
    assert _text(q) == "within 60 days"


# --------------------------------------------------------------------------- #
# Numbering normalisation
# --------------------------------------------------------------------------- #


def test_tab_wrapped_embedded_number_stripped_to_attr() -> None:
    root = _load("itaa97-figure.xml")
    node = parse_section(_first_section(root), build_ref_index(_nav(root)))

    subsec2 = _find(
        node,
        lambda n: n.kind == "provision"
        and n.attrs.get("level") == "subsection"
        and n.attrs.get("num") == "2",
    )
    assert subsec2 is not None
    first_text = subsec2.children[0].children[0].children[0]
    assert first_text.kind == "text"
    assert first_text.text.startswith("Your income tax is worked out")
    assert "(2)" not in first_text.text
    assert not first_text.text.startswith("\t")


def test_leading_non_number_parenthetical_is_left_intact() -> None:
    node = parse_section(
        _sec(
            "<subsection eId=\"s1__subsec-1\"><num>1</num><content>"
            "<p>(see subsection 33(3)) The Minister may do a thing.</p>"
            "</content></subsection>"
        ),
        build_ref_index([]),
    )
    prov = _find(node, lambda n: n.kind == "provision")
    assert prov is not None
    first_text = prov.children[0].children[0].children[0]
    assert first_text.text == "(see subsection 33(3)) The Minister may do a thing."


def test_schedule_clause_keeps_number() -> None:
    root = _load("sched-clause.xml")
    clause = root.find(f".//{AKN}hcontainer[@name='clause']")
    assert clause is not None
    node = parse_section(clause, build_ref_index(_nav(root)))

    assert node.attrs["num"] == "70-20"
    assert node.attrs["eid"] == "schedule-1__clause-70-20"

    subclause1 = _find(
        node,
        lambda n: n.kind == "provision"
        and n.attrs.get("level") == "subclause"
        and n.attrs.get("num") == "1",
    )
    assert subclause1 is not None
    first_text = subclause1.children[0].children[0].children[0]
    assert first_text.text.startswith("The Court may order that an audit")
    assert "(1)" not in first_text.text

    para = _find(
        node,
        lambda n: n.kind == "provision" and n.attrs.get("level") == "paragraph",
    )
    assert para is not None


# --------------------------------------------------------------------------- #
# Blocks
# --------------------------------------------------------------------------- #


def test_blocklist_keeps_intro_and_item_structure() -> None:
    node = parse_section(
        _sec(
            "<content><p>lead</p></content>"
            "<blockList>"
            "<listIntroduction>The company must keep its registers at:</listIntroduction>"
            "<item><num>a</num><p>the registered office; or</p></item>"
            "<item><num>b</num><p>the principal place of business.</p></item>"
            "</blockList>"
        ),
        build_ref_index([]),
    )
    lst = _find(node, lambda n: n.kind == "list")
    assert lst is not None
    assert lst.children[0].kind == "intro"
    assert _text(lst.children[0]).strip() == "The company must keep its registers at:"

    items = [c for c in lst.children if c.kind == "item"]
    assert len(items) == 2
    assert items[0].attrs["num"] == "a"
    assert items[0].children[0].kind == "para"
    assert _text(items[0]).strip() == "the registered office; or"
    assert items[1].attrs["num"] == "b"


def test_content_yields_one_para_per_p() -> None:
    node = parse_section(
        _sec("<content><p>first</p><p>second</p><p>third</p></content>"),
        build_ref_index([]),
    )
    content = _find(node, lambda n: n.kind == "content")
    assert content is not None
    paras = [c for c in content.children if c.kind == "para"]
    assert [_text(p) for p in paras] == ["first", "second", "third"]


def test_table_rows_cells_header_flag() -> None:
    root = _load("itaa97-rate-table.xml")
    node = parse_section(_first_section(root), build_ref_index(_nav(root)))

    table = _find(node, lambda n: n.kind == "table")
    assert table is not None
    rows = [c for c in table.children if c.kind == "row"]
    assert len(rows) == 8  # 1 header + 7 data

    header = rows[0]
    assert header.attrs.get("header") is True
    assert all(c.attrs["td"] is False for c in header.children)
    assert [_text(c) for c in header.children] == ["Item", "For this case ...", "See:"]

    data = rows[1]
    assert data.attrs.get("header") is not True
    assert all(c.attrs["td"] is True for c in data.children)
    assert _text(data.children[2]) == "Subdivision 165-B"

    # Spike correction: no <td> in the corpus has child elements; multi-line
    # cell text is whitespace-normalised to a single text node.
    multiline = rows[3].children[1]
    assert len(multiline.children) == 1 and multiline.children[0].kind == "text"
    assert "  " not in multiline.children[0].text
    assert "\t" not in multiline.children[0].text

    # No colspan/rowspan in this table.
    for row in rows:
        for cell in row.children:
            assert "colspan" not in cell.attrs
            assert "rowspan" not in cell.attrs


def test_table_cell_colspan_copied_only_when_digit() -> None:
    node = parse_section(
        _sec(
            "<table><tr>"
            "<td colspan=\"2\">merged</td>"
            "<td colspan=\"all\">bad</td>"
            "<td>plain</td>"
            "</tr></table>"
        ),
        build_ref_index([]),
    )
    row = _find(node, lambda n: n.kind == "row")
    assert row is not None
    assert row.children[0].attrs["colspan"] == "2"
    assert "colspan" not in row.children[1].attrs
    assert "colspan" not in row.children[2].attrs


def test_figure_yields_figure_node_with_src() -> None:
    root = _load("itaa97-figure.xml")
    node = parse_section(_first_section(root), build_ref_index(_nav(root)))

    fig = _find(node, lambda n: n.kind == "figure")
    assert fig is not None
    assert fig.attrs["src"].endswith("income-tax-assessment-act-1997-fig-2.png")
    assert fig.attrs["alt"] == ""
    assert fig.attrs["asset"] is False


def test_authorial_note_label_split_off() -> None:
    root = _load("corp-act-s3.xml")
    node = parse_section(_first_section(root), build_ref_index(_nav(root)))

    note = _find(node, lambda n: n.kind == "note")
    assert note is not None
    assert note.attrs["label"] == "Note:"
    body = _text(note)
    assert body.startswith("The State referrals fully supplement")
    assert "Note:" not in body


def test_authorial_note_numbered_label_split_off() -> None:
    root = _load("itaa97-figure.xml")
    node = parse_section(_first_section(root), build_ref_index(_nav(root)))

    notes = _find_all(node, lambda n: n.kind == "note")
    labels = {n.attrs.get("label") for n in notes}
    assert "Note 1:" in labels
    assert "Note 2:" in labels
    n1 = next(n for n in notes if n.attrs.get("label") == "Note 1:")
    assert not _text(n1).startswith("Note 1:")


def test_authorial_note_second_content_not_dropped() -> None:
    node = parse_section(
        _sec(
            "<authorialNote><content>"
            "<p>Note: first line of the note.</p>"
            "</content><content>"
            "<p>second line of the note.</p>"
            "</content></authorialNote>"
        ),
        build_ref_index([]),
    )
    note = _find(node, lambda n: n.kind == "note")
    assert note is not None
    assert note.attrs["label"] == "Note:"
    contents = [c for c in note.children if c.kind == "content"]
    assert len(contents) == 2
    body = _text(note)
    assert "first line of the note." in body
    assert "second line of the note." in body
    assert "Note:" not in body


def test_term_node_key_and_display() -> None:
    node = parse_section(
        _sec("<content><p><term>Taxable Income</term> means assessable income.</p></content>"),
        build_ref_index([]),
    )
    term = _find(node, lambda n: n.kind == "term")
    assert term is not None
    assert term.attrs["term"] == "taxable income"
    assert term.attrs["display"] == "Taxable Income"


def test_term_key_is_stripped() -> None:
    node = parse_section(
        _sec("<content><p><term>\n  Financial Year\n  </term> means ...</p></content>"),
        build_ref_index([]),
    )
    term = _find(node, lambda n: n.kind == "term")
    assert term is not None
    assert term.attrs["term"] == "financial year"


def test_example_and_penalty_hcontainers() -> None:
    node = parse_section(
        _sec(
            "<hcontainer name=\"example\"><num>1</num><content>"
            "<p>A company that fails to lodge.</p></content></hcontainer>"
            "<hcontainer name=\"penalty\"><content>"
            "<p>50 penalty units.</p></content></hcontainer>"
        ),
        build_ref_index([]),
    )
    example = _find(node, lambda n: n.kind == "example")
    penalty = _find(node, lambda n: n.kind == "penalty")
    assert example is not None
    assert example.attrs.get("num") == "1"
    assert _text(example).strip() == "A company that fails to lodge."
    assert penalty is not None
    assert _text(penalty).strip() == "50 penalty units."


def test_unknown_block_becomes_raw_and_keeps_text() -> None:
    node = parse_section(
        _sec("<foversized>kept <b>bold</b> text</foversized>"),
        build_ref_index([]),
    )
    raw = _find(node, lambda n: n.kind == "raw")
    assert raw is not None
    assert raw.attrs["tag"] == "foversized"
    assert "kept" in _text(raw)
    assert "bold" in _text(raw)
    assert "text" in _text(raw)


# --------------------------------------------------------------------------- #
# Section shell
# --------------------------------------------------------------------------- #


def test_section_node_shape() -> None:
    root = _load("corp-act-s3.xml")
    node = parse_section(_first_section(root), build_ref_index(_nav(root)))
    assert node.kind == "section"
    assert node.attrs["eid"] == "chapter-1__part-1.1__sec-3"
    assert node.attrs["num"] == "3"
    assert node.attrs["heading"] == "Constitutional basis for this Act"
    subs = _find_all(
        node,
        lambda n: n.kind == "provision" and n.attrs.get("level") == "subsection",
    )
    assert len(subs) == 4
    paras = _find_all(
        node,
        lambda n: n.kind == "provision" and n.attrs.get("level") == "paragraph",
    )
    assert len(paras) == 9  # a,b x4 subsections + one extra 'c' in subsec 3
