from build.ir import Node, KINDS


def test_node_to_dict_roundtrips_nested():
    n = Node("section", {"eid": "s1", "num": "1", "heading": "H"}, [
        Node("content", children=[
            Node("para", children=[
                Node("text", text="Hello "),
                Node("emphasis", {"style": "italic"}, [Node("text", text="world")]),
            ])])])
    d = n.to_dict()
    assert d["kind"] == "section"
    assert d["attrs"]["heading"] == "H"
    inner = d["children"][0]["children"][0]["children"]
    assert inner[1]["attrs"]["style"] == "italic"
    assert inner[1]["children"][0]["text"] == "world"


def test_node_to_dict_omits_empties():
    assert Node("text", text="x").to_dict() == {"kind": "text", "text": "x"}
    assert Node("content").to_dict() == {"kind": "content"}


def test_kinds_contains_block_and_inline():
    for k in ("section", "provision", "content", "para", "note", "example",
              "penalty", "list", "intro", "item", "table", "row", "cell",
              "figure", "raw", "text", "emphasis", "term", "ref", "date",
              "quantity", "inline_raw"):
        assert k in KINDS
