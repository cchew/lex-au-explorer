"""Stage 2 render walk: semantic IR (:class:`~build.ir.Node`) -> HTML string.

:func:`render_section` is a post-order traversal. Each child is rendered to a
string first; the node and the *list* of child strings are then handed to a
:class:`~build.stylemap.StyleMap` (default
:class:`~build.stylemap.HtmlStyleMap`). The list is passed intact, never
pre-joined, so container kinds (``table``, ``list``, ``row``) can wrap the
first element or interleave separators.
"""

from __future__ import annotations

from build.ir import Node
from build.stylemap import StyleMap

__all__ = ["render_section"]


def render_section(node: Node, style: StyleMap) -> str:
    """Render ``node`` and its subtree to an HTML string using ``style``."""
    children: list[str] = [render_section(child, style) for child in node.children]
    return style.render(node, children)
