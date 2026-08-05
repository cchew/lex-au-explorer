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


_CONTAINER_TAGS = {"subsection", "paragraph", "subparagraph", "point", "item"}


def _render_section_html(section: ET._Element) -> str:
    """Render a <section>'s full body -- its own <content> plus every
    nested <subsection>/<paragraph>/... and <authorialNote> -- as HTML,
    wrapping each <term> usage in a <span data-term="..."> the frontend
    hovers on.

    Most substantive Act text lives inside <subsection>/<paragraph>
    children, not the section's own top-level <content> (which is often
    just a short label, e.g. "Agencies"); an earlier version only read
    the top-level <content> and silently dropped everything else,
    producing near-empty output for most real sections (52% of Privacy
    Act 1988 sections render under 30 chars of body text under that
    approach -- confirmed against the real corpus).

    Deliberately does not attempt full AKN->HTML fidelity (tables,
    cross-references as links, list markup beyond a numeric prefix) --
    v1 renders paragraph text with term-spans and (num) prefixes only,
    matching the reader's actual scope."""
    return _render_children(section)


def _render_children(el: ET._Element) -> str:
    parts = [_render_node(child) for child in el]
    return "\n".join(p for p in parts if p)


def _render_node(el: ET._Element) -> str:
    tag = _local_tag(el)
    if tag in ("num", "heading"):
        return ""
    if tag == "content":
        return _render_content(el)
    if tag == "authorialNote":
        return _render_note(el)
    if tag in _CONTAINER_TAGS:
        return _render_container(el)
    # Unknown/other structural element (list, table, etc.) -- out of v1's
    # formatting scope, but recurse into its children so the text is never
    # silently dropped, only its specific markup.
    return _render_children(el)


def _render_container(el: ET._Element) -> str:
    prefix = _container_num_prefix(el)
    parts: list[str] = []
    prefix_applied = not prefix
    for child in el:
        tag = _local_tag(child)
        if tag == "num":
            continue
        if tag == "content" and not prefix_applied:
            parts.append(_render_content(child, prefix=prefix))
            prefix_applied = True
        else:
            parts.append(_render_node(child))
    body = "\n".join(p for p in parts if p)
    return f'<div class="akn-unit">{body}</div>' if body else ""


def _container_num_prefix(el: ET._Element) -> str:
    """The container's own (num), unless its first paragraph's source
    text already embeds it as a literal "(num)" prefix -- seen in ~14%
    of Privacy Act 1988 subsections, an artifact of the source
    formatting -- in which case adding it again would duplicate it."""
    num_el = el.find(f"{AKN}num")
    num_text = (num_el.text or "").strip() if num_el is not None else ""
    if not num_text:
        return ""
    first_p = el.find(f"{AKN}content/{AKN}p")
    if first_p is not None and (first_p.text or "").strip().startswith(f"({num_text})"):
        return ""
    return num_text


def _render_content(content_el: ET._Element, prefix: str = "") -> str:
    parts: list[str] = []
    for i, p in enumerate(content_el.findall(f"{AKN}p")):
        inner = _render_inline(p)
        if i == 0 and prefix:
            inner = f'<span class="akn-num">({html_lib.escape(prefix)})</span> {inner}'
        parts.append(f"<p>{inner}</p>")
    return "\n".join(parts)


def _render_note(note_el: ET._Element) -> str:
    content_el = note_el.find(f"{AKN}content")
    if content_el is None:
        return ""
    body = _render_content(content_el)
    return f'<div class="akn-note">{body}</div>' if body else ""


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
