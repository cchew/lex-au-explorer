from __future__ import annotations
import html as html_lib
import lxml.etree as ET

AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
AKN = f"{{{AKN_NS}}}"

_STRUCTURAL_TAGS = {"part", "division", "subdivision", "chapter", "section"}


def build_toc(root: ET._Element) -> list[dict]:
    body = root.find(f".//{AKN}body")
    if body is None:
        return []
    return [_toc_node(child) for child in body if _local_tag(child) in _STRUCTURAL_TAGS]


def _toc_node(el: ET._Element) -> dict:
    heading_el = el.find(f"{AKN}heading")
    num_el = el.find(f"{AKN}num")
    heading_text = (heading_el.text or "").strip() if heading_el is not None else ""
    num_text = (num_el.text or "").strip() if num_el is not None else ""
    heading = f"{num_text} {heading_text}".strip()
    children = [_toc_node(c) for c in el if _local_tag(c) in _STRUCTURAL_TAGS]
    return {"eid": el.get("eId", ""), "heading": heading, "children": children}


def build_sections(root: ET._Element) -> dict[str, dict]:
    sections: dict[str, dict] = {}
    for section in root.iter(f"{AKN}section"):
        eid = section.get("eId", "")
        if not eid:
            continue
        heading_el = section.find(f"{AKN}heading")
        heading = (heading_el.text or "").strip() if heading_el is not None else ""
        sections[eid] = {"heading": heading, "html": _render_section_html(section)}
    return sections


def _local_tag(el: ET._Element) -> str:
    return el.tag.split("}")[-1] if isinstance(el.tag, str) else ""


def _render_section_html(section: ET._Element) -> str:
    """Render a <section>'s <content> as HTML paragraphs, wrapping each
    <term> usage in a <span data-term="..."> the frontend hovers on.

    Deliberately does not attempt full AKN->HTML fidelity (numbered lists,
    tables, cross-references as links) -- v1 renders paragraph text with
    term-spans only, matching the reader's actual scope."""
    content = section.find(f"{AKN}content")
    if content is None:
        return ""
    parts: list[str] = []
    for p in content.findall(f"{AKN}p"):
        parts.append(f"<p>{_render_inline(p)}</p>")
    return "\n".join(parts)


def _render_inline(el: ET._Element) -> str:
    pieces: list[str] = []
    if el.text:
        pieces.append(html_lib.escape(el.text))
    for child in el:
        tag = _local_tag(child)
        if tag == "term":
            term_text = "".join(child.itertext())
            pieces.append(
                f'<span data-term="{html_lib.escape(term_text.lower())}">'
                f'{html_lib.escape(term_text)}</span>'
            )
        else:
            pieces.append(_render_inline(child))
        if child.tail:
            pieces.append(html_lib.escape(child.tail))
    return "".join(pieces)
