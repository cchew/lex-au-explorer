"""Stage 1 semantic parse: AKN 3.0 XML section -> semantic IR (:class:`Node`).

``parse_section(section_el, ref_index)`` walks one ``<section>`` (or a
schedule ``<hcontainer>`` passed in its place) and produces a ``section``
``Node`` tree. The parser is deliberately total: every element that is not a
recognised block or inline construct falls through to a generic ``raw`` /
``inline_raw`` node that still recurses its children, so source text is never
silently dropped (spike note F, brief B3).

Cross-reference resolution is delegated to ``ref_index`` (see
``build.refindex``); the parser only records ``status`` and, when resolved,
``target_eid`` on each ``ref`` node. It does not itself decide link validity.

Structure realities this parser encodes (parity spike, 2026-09-01):

* Table cells are text-only in the entire corpus -- no ``<td>`` has element
  children -- so ``cell`` children are a single whitespace-normalised ``text``
  node (or empty), never inline-parsed.
* ``<authorialNote>`` text begins ``Note:`` / ``Note N:`` in 100% of sampled
  notes; that label is split into ``attrs["label"]``.
* Schedule provisions are ``<hcontainer name="clause"|"subclause">`` with a
  ``<num>``; paragraphs are their siblings, and eIds repeat within a clause.
"""

from __future__ import annotations

import re
from typing import Optional

import lxml.etree as ET

from build.bundle import AKN, _local_tag
from build.ir import Node
from build.refindex import RefIndex

__all__ = ["parse_section"]

# Container tags that map to a ``provision`` node; the value is the ``level``.
_PROVISION_TAGS: frozenset[str] = frozenset(
    {"subsection", "paragraph", "subparagraph"}
)
_PROVISION_HCONTAINERS: frozenset[str] = frozenset({"clause", "subclause"})

# Inline elements handled explicitly; everything else -> ``inline_raw``.
_INLINE_TAGS: frozenset[str] = frozenset(
    {"i", "b", "term", "ref", "date", "quantity"}
)

_SKIP_TAGS: frozenset[str] = frozenset({"num", "heading"})

# Leading ``Note:`` / ``Note 1:`` label on an authorial note's first paragraph.
_NOTE_LABEL_RE = re.compile(r"^(Note(?:\s+\d+)?:)[ \t]*")

# Leading run of tab characters on a provision's first text node.
_LEADING_TABS_RE = re.compile(r"^\t+")


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def parse_section(section_el: ET._Element, ref_index: RefIndex) -> Node:
    """Parse one ``<section>`` element into a ``section`` :class:`Node`.

    ``section_el`` may also be a schedule ``<hcontainer>`` (``name="clause"``,
    ``"subclause"`` or ``"schedule"``); it is still treated as the top-level
    container and its ``<num>`` / ``<heading>`` / ``eId`` are lifted to attrs.
    The eId used for cross-reference resolution is this element's own
    ``eId`` (``section_el.get("eId")``), threaded unchanged into nested blocks.
    """
    section_eid = section_el.get("eId", "") or ""
    node = Node("section")
    _apply_identity(node, section_el)
    for child in section_el:
        if _local_tag(child) in _SKIP_TAGS:
            continue
        parsed = _parse_block(child, section_eid, ref_index)
        if parsed is not None:
            node.children.append(parsed)
    return node


# --------------------------------------------------------------------------- #
# Blocks
# --------------------------------------------------------------------------- #


def _parse_block(
    el: ET._Element, section_eid: str, ref_index: RefIndex
) -> Optional[Node]:
    tag = _local_tag(el)

    if tag in _SKIP_TAGS:
        return None
    if tag == "section":
        return parse_section(el, ref_index)
    if tag in _PROVISION_TAGS:
        return _parse_provision(el, tag, section_eid, ref_index)
    if tag == "hcontainer":
        return _parse_hcontainer(el, section_eid, ref_index)
    if tag == "blockList":
        return _parse_list(el, section_eid, ref_index)
    if tag == "content":
        return _parse_content(el, section_eid, ref_index)
    if tag == "authorialNote":
        return _parse_note(el, section_eid, ref_index)
    if tag == "table":
        return _parse_table(el, section_eid, ref_index)
    if tag == "figure":
        return _parse_figure(el)

    return _parse_raw(el, section_eid, ref_index)


def _parse_hcontainer(
    el: ET._Element, section_eid: str, ref_index: RefIndex
) -> Node:
    name = el.get("name", "") or ""
    if name in _PROVISION_HCONTAINERS:
        return _parse_provision(el, name, section_eid, ref_index)
    if name in ("example", "penalty"):
        return _parse_named_container(el, name, section_eid, ref_index)
    # ``name="schedule"`` and any other hcontainer: structural, recurse so
    # nested clauses/content still parse and no text is lost.
    return _parse_raw(el, section_eid, ref_index)


def _parse_provision(
    el: ET._Element, level: str, section_eid: str, ref_index: RefIndex
) -> Node:
    node = Node("provision", {"level": level})
    _apply_identity(node, el)
    num = node.attrs.get("num", "")
    for child in el:
        if _local_tag(child) in _SKIP_TAGS:
            continue
        parsed = _parse_block(child, section_eid, ref_index)
        if parsed is not None:
            node.children.append(parsed)
    _strip_provision_num(node, num)
    return node


def _parse_named_container(
    el: ET._Element, kind: str, section_eid: str, ref_index: RefIndex
) -> Node:
    node = Node(kind)
    _apply_identity(node, el)
    for child in el:
        if _local_tag(child) in _SKIP_TAGS:
            continue
        parsed = _parse_block(child, section_eid, ref_index)
        if parsed is not None:
            node.children.append(parsed)
    return node


def _parse_content(
    el: ET._Element, section_eid: str, ref_index: RefIndex
) -> Node:
    node = Node("content")
    for child in el:
        tag = _local_tag(child)
        if tag == "p":
            para = Node("para")
            _parse_inline_into(child, para, section_eid, ref_index)
            node.children.append(para)
        else:
            # Not expected inside <content> in the corpus, but stay total.
            parsed = _parse_block(child, section_eid, ref_index)
            if parsed is not None:
                node.children.append(parsed)
    return node


def _parse_note(
    el: ET._Element, section_eid: str, ref_index: RefIndex
) -> Node:
    node = Node("note")
    _apply_identity(node, el)
    # Iterate and recurse every child (like the other block handlers) so a
    # second <content>, a <num>, or any other block child is never dropped.
    for child in el:
        if _local_tag(child) in _SKIP_TAGS:
            continue
        parsed = _parse_block(child, section_eid, ref_index)
        if parsed is not None:
            node.children.append(parsed)
    for child in node.children:
        if child.kind == "content":
            label = _split_note_label(child)
            if label:
                node.attrs["label"] = label
            break
    return node


def _parse_list(
    el: ET._Element, section_eid: str, ref_index: RefIndex
) -> Node:
    node = Node("list")
    _apply_identity(node, el)
    for child in el:
        tag = _local_tag(child)
        if tag == "num":
            continue
        if tag == "listIntroduction":
            intro = Node("intro")
            _parse_inline_into(child, intro, section_eid, ref_index)
            node.children.append(intro)
        elif tag == "item":
            node.children.append(_parse_item(child, section_eid, ref_index))
        else:
            parsed = _parse_block(child, section_eid, ref_index)
            if parsed is not None:
                node.children.append(parsed)
    return node


def _parse_item(
    el: ET._Element, section_eid: str, ref_index: RefIndex
) -> Node:
    node = Node("item")
    num_el = el.find(f"{AKN}num")
    if num_el is not None:
        num = (num_el.text or "").strip()
        if num:
            node.attrs["num"] = num
    if el.text:
        node.children.append(Node("text", text=el.text))
    for child in el:
        tag = _local_tag(child)
        if tag == "num":
            if child.tail and child.tail.strip():
                node.children.append(Node("text", text=child.tail))
            continue
        if tag == "p":
            para = Node("para")
            _parse_inline_into(child, para, section_eid, ref_index)
            node.children.append(para)
        elif tag in _INLINE_TAGS:
            node.children.append(_parse_inline(child, section_eid, ref_index))
            if child.tail:
                node.children.append(Node("text", text=child.tail))
        else:
            parsed = _parse_block(child, section_eid, ref_index)
            if parsed is not None:
                node.children.append(parsed)
    return node


def _parse_table(
    el: ET._Element, section_eid: str, ref_index: RefIndex
) -> Node:
    node = Node("table")
    _apply_identity(node, el)
    for tr in el:
        if _local_tag(tr) != "tr":
            continue
        node.children.append(_parse_row(tr))
    return node


def _parse_row(tr: ET._Element) -> Node:
    row = Node("row")
    cells = [c for c in tr if _local_tag(c) in ("th", "td")]
    if cells and all(_local_tag(c) == "th" for c in cells):
        row.attrs["header"] = True
    for c in cells:
        row.children.append(_parse_cell(c))
    return row


def _parse_cell(c: ET._Element) -> Node:
    is_td = _local_tag(c) == "td"
    cell = Node("cell", {"td": is_td})
    for attr in ("colspan", "rowspan"):
        value = c.get(attr)
        if value is not None and value.isdigit():
            cell.attrs[attr] = value
    raw = "".join(c.itertext())
    lines = [x for x in (_normalise_ws(p) for p in raw.split("\n")) if x]
    cell.attrs["lines"] = lines
    if lines:
        cell.children.append(Node("text", text=" ".join(lines)))
    return cell


def _parse_figure(el: ET._Element) -> Node:
    node = Node("figure", {"asset": False})
    img = el.find(f"{AKN}img")
    if img is not None:
        node.attrs["src"] = img.get("src", "") or ""
        node.attrs["alt"] = img.get("alt", "") or ""
        for dim in ("width", "height"):
            value = img.get(dim)
            if value is not None and value != "":
                node.attrs[dim] = value
    else:
        node.attrs["src"] = ""
        node.attrs["alt"] = ""
    return node


def _parse_raw(
    el: ET._Element, section_eid: str, ref_index: RefIndex
) -> Node:
    node = Node("raw", {"tag": _local_tag(el)})
    if el.text:
        node.children.append(Node("text", text=el.text))
    for child in el:
        parsed = _parse_block(child, section_eid, ref_index)
        if parsed is not None:
            node.children.append(parsed)
        if child.tail:
            node.children.append(Node("text", text=child.tail))
    return node


# --------------------------------------------------------------------------- #
# Inline
# --------------------------------------------------------------------------- #


def _parse_inline_into(
    el: ET._Element, parent: Node, section_eid: str, ref_index: RefIndex
) -> None:
    """Append inline children of ``el`` (text, tails, elements) to ``parent``."""
    if el.text:
        parent.children.append(Node("text", text=el.text))
    for child in el:
        parent.children.append(_parse_inline(child, section_eid, ref_index))
        if child.tail:
            parent.children.append(Node("text", text=child.tail))


def _parse_inline(
    el: ET._Element, section_eid: str, ref_index: RefIndex
) -> Node:
    tag = _local_tag(el)

    if tag == "i":
        node = Node("emphasis", {"style": "italic"})
        _parse_inline_into(el, node, section_eid, ref_index)
        return node
    if tag == "b":
        node = Node("emphasis", {"style": "bold"})
        _parse_inline_into(el, node, section_eid, ref_index)
        return node
    if tag == "term":
        display = "".join(el.itertext())
        # Strip only the lookup key (edge whitespace from pretty-printed source
        # would otherwise leak into the resolver input); keep display verbatim.
        return Node("term", {"term": display.strip().lower(), "display": display})
    if tag == "ref":
        return _parse_ref(el, section_eid, ref_index)
    if tag == "date":
        node = Node("date", {"iso": el.get("date", "") or ""})
        _emit_verbatim_text(el, node)
        return node
    if tag == "quantity":
        node = Node("quantity", {"refers_to": el.get("refersTo", "") or ""})
        _emit_verbatim_text(el, node)
        return node

    # Mandatory generic fallback: <def>, <role>, <mod>, <sup>, ... -- recurse
    # so operative text (and any nested inline markup) survives.
    node = Node("inline_raw", {"tag": tag})
    _parse_inline_into(el, node, section_eid, ref_index)
    return node


def _parse_ref(
    el: ET._Element, section_eid: str, ref_index: RefIndex
) -> Node:
    href = el.get("href", "") or ""
    text = "".join(el.itertext())
    following_text = el.tail or ""
    node = Node("ref", {"href": href, "text": text})
    resolution = ref_index.resolve(
        href, section_eid, display_text=text, following_text=following_text
    )
    node.attrs["status"] = resolution.status
    if resolution.status == "resolved" and resolution.target_eid is not None:
        node.attrs["target_eid"] = resolution.target_eid
    return node


def _emit_verbatim_text(el: ET._Element, node: Node) -> None:
    """Flatten ``el``'s text content to a single ``text`` child, verbatim."""
    text = "".join(el.itertext())
    if text:
        node.children.append(Node("text", text=text))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _apply_identity(node: Node, el: ET._Element) -> None:
    """Lift ``eId`` and direct-child ``<num>`` / ``<heading>`` onto ``attrs``."""
    eid = el.get("eId")
    if eid:
        node.attrs["eid"] = eid
    num_el = el.find(f"{AKN}num")
    if num_el is not None:
        num = (num_el.text or "").strip()
        if num:
            node.attrs["num"] = num
    heading_el = el.find(f"{AKN}heading")
    if heading_el is not None:
        heading = "".join(heading_el.itertext()).strip()
        if heading:
            node.attrs["heading"] = heading


def _split_note_label(content_node: Node) -> str:
    """Strip a leading ``Note:`` / ``Note N:`` off the first para's first text
    node and return it (with the colon). Returns ``""`` if absent."""
    for para in content_node.children:
        if para.kind != "para":
            continue
        if not para.children or para.children[0].kind != "text":
            return ""
        first = para.children[0]
        match = _NOTE_LABEL_RE.match(first.text)
        if match is None:
            return ""
        first.text = first.text[match.end() :]
        if not first.text:
            para.children.pop(0)
        return match.group(1)
    return ""


def _strip_provision_num(provision: Node, num: str) -> None:
    """Guarded numbering normalisation on a provision's first para text node.

    If the leading text is exactly ``(<num>)`` (that provision's own number)
    plus optional whitespace/tabs, strip that token and the trailing
    whitespace. A leading parenthetical that is *not* the provision number is
    left byte-for-byte intact. Independently, collapse a leading run of tabs.
    """
    text_node = _first_para_first_text(provision)
    if text_node is None:
        return
    original = text_node.text

    if num:
        pattern = r"^\s*\(" + re.escape(num) + r"\)\s*"
        stripped = re.sub(pattern, "", original, count=1)
        if stripped != original:
            text_node.text = stripped
            return

    text_node.text = _LEADING_TABS_RE.sub("", original)


def _first_para_first_text(provision: Node) -> Optional[Node]:
    if not provision.children:
        return None
    first_block = provision.children[0]
    if first_block.kind != "content":
        return None
    for sub in first_block.children:
        if sub.kind == "para":
            if sub.children and sub.children[0].kind == "text":
                return sub.children[0]
            return None
    return None


def _normalise_ws(text: str) -> str:
    return " ".join(text.split())
