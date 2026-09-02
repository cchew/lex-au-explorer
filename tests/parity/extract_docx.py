"""Extract visible paragraph text from a Word ``.docx``, standard library only.

A ``.docx`` is a zip archive whose ``word/document.xml`` part holds the document
body. The visible text of a paragraph (``<w:p>``) is the concatenation of its
``<w:t>`` text runs in document order, with ``<w:tab>`` / ``<w:br>`` / ``<w:cr>``
rendered as a single space. Field-code runs (``<w:instrText>``) and tracked
deletions (``<w:delText>``) carry no visible body text and are ignored.

This module has one public function, :func:`paragraphs`. It exists so the parity
goldens under ``tests/fixtures/corpus/*.expected.md`` can be regenerated from the
authoritative Word compilation without taking a ``python-docx`` dependency and
without committing any ``.docx`` to this repo. See ``tests/parity/README.md``.

Assumption: legislation.gov.au Word output keeps body paragraphs and tables flat
(no body text inside text boxes / SmartArt), so iterating every ``<w:p>`` in
document order does not double-count nested paragraph text.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

__all__ = ["paragraphs"]

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DOCUMENT_PART = "word/document.xml"

_TEXT_TAG = f"{_W}t"
_SPACE_TAGS = frozenset({f"{_W}tab", f"{_W}br", f"{_W}cr"})


def _collapse(text: str) -> str:
    """Collapse every run of whitespace to a single space and strip the ends."""
    return " ".join(text.split())


def _paragraph_text(paragraph: ET.Element) -> str:
    """Visible, whitespace-collapsed text of one ``<w:p>`` element."""
    parts: list[str] = []
    for node in paragraph.iter():
        tag = node.tag
        if tag == _TEXT_TAG:
            parts.append(node.text or "")
        elif tag in _SPACE_TAGS:
            parts.append(" ")
        # <w:instrText>, <w:delText> and everything else: not visible body text.
    return _collapse("".join(parts))


def paragraphs(docx_path: Path) -> list[str]:
    """Return the visible paragraph text of ``docx_path`` in document order.

    Each list element is one Word paragraph, whitespace-collapsed. Empty
    paragraphs (spacing runs, section breaks) are dropped. ``<w:tab>`` and
    ``<w:br>`` become a single space.
    """
    with zipfile.ZipFile(docx_path) as archive:
        document_xml = archive.read(_DOCUMENT_PART)
    root = ET.fromstring(document_xml)
    out: list[str] = []
    for paragraph in root.iter(f"{_W}p"):
        text = _paragraph_text(paragraph)
        if text:
            out.append(text)
    return out


if __name__ == "__main__":  # pragma: no cover - manual eyeball helper
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("usage: python extract_docx.py <file.docx> [substring]")
    needle = sys.argv[2] if len(sys.argv) > 2 else ""
    for lineno, para in enumerate(paragraphs(Path(sys.argv[1])), start=1):
        if needle and needle.lower() not in para.lower():
            continue
        print(f"{lineno:5d}  {para}")
