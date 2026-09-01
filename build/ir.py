from __future__ import annotations
from dataclasses import dataclass, field

KINDS = frozenset({
    "section", "provision", "content", "para", "note", "example", "penalty",
    "list", "intro", "item", "table", "row", "cell", "figure", "raw",
    "text", "emphasis", "term", "ref", "date", "quantity", "inline_raw",
})


@dataclass
class Node:
    kind: str
    attrs: dict = field(default_factory=dict)
    children: list[Node] = field(default_factory=list)
    text: str = ""

    def to_dict(self) -> dict:
        d: dict = {"kind": self.kind}
        if self.attrs:
            d["attrs"] = dict(self.attrs)
        if self.text:
            d["text"] = self.text
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d
