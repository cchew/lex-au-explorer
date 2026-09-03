# The lex-au-explorer semantic IR

The reader renders Act text in two stages:

```
AKN XML  --Stage 1: build/parse.py-->  IR (Node tree, no HTML)
                                            |
                                     Stage 2: build/stylemap.py
                                            |
                                            v
                                      HTML string  -->  bundle JSON  -->  frontend v-html
```

Stage 1 owns everything *about the law* (hierarchy, numbering, defined terms,
cross-reference resolution, notes, examples, penalties, tables, emphasis). It is
pure and deterministic and emits no HTML. Stage 2 owns everything *about
presentation* (which element, which class, hanging indent vs inline number, box
vs plain).

The IR is the stable contract. `build/ir.py` defines it; `Node.to_dict()` is its
JSON form; `lex-au-explorer-build --emit-ir DIR` writes that JSON per section so
a third party can render client-side or in another language without forking the
Python renderer.

## Node

```python
@dataclass
class Node:
    kind: str
    attrs: dict = {}
    children: list[Node] = []
    text: str = ""          # only for kind == "text"

    def to_dict(self) -> dict   # recursive; omits empty attrs/text/children
```

`KINDS` in `build/ir.py` is the frozenset of every valid `kind`.

## Block kinds

| `kind` | `attrs` | Meaning / children |
|--------|---------|--------------------|
| `section` | `eid`, `num`, `heading` | Top provision. Children: `provision` / `content` / `note` / `example` / `penalty` / `table` / `list` / `figure` / `raw` |
| `provision` | `eid`, `level` (`subsection`\|`paragraph`\|`subparagraph`\|`clause`\|`subclause`), `num`, `heading?` | Numbered sub-unit. `num` is the bare token (`"1"`, `"a"`), never parenthesised, never in any `text` node. `heading` is rare (a headed subsection) and lifted by `_apply_identity` |
| `content` | -- | A run of one or more `para`s |
| `para` | -- | One paragraph. Children: **inline** nodes only |
| `note` | `label`, `eid?`, `num?`, `heading?` | Authorial note. `label` is the leading `Note:` / `Note 1:` carried from source; the rest is `content` children. `eid` / `num` / `heading` come from `_apply_identity` and are almost always absent on `<authorialNote>` |
| `example` | `eid?`, `num?`, `heading?` | `hcontainer name="example"` (all three via `_apply_identity`) |
| `penalty` | `eid?`, `num?`, `heading?` | `hcontainer name="penalty"` (all three via `_apply_identity`; `num` / `heading` rare) |
| `list` | `eid?`, `num?`, `heading?` | `blockList` (all three via `_apply_identity`). Children: optional `intro`, then `item`* |
| `intro` | -- | `listIntroduction` / lead-in. Children: inline |
| `item` | `num?` | One `blockList` `item`. **No** `_apply_identity` call: only `num` (its own `<num>` text) is lifted, never `eid` / `heading`. Children: `text`, inline, `para`, or -- via the total block fallthrough -- any **block** node (`list`, `content`, `raw`, ...) |
| `table` | `eid?`, `num?`, `heading?` | `blockList`-style identity via `_apply_identity`. Children: `row` |
| `row` | `header` (bool) | Children: `cell` |
| `cell` | `td` (bool -- else `th`), `colspan?`, `rowspan?` | Children: a single `text` node (cells are text-only across the whole corpus) or empty |
| `figure` | `src`, `alt`, `asset` (bool -- image copied vs missing) | `<figure>`/`<img>`. Method-statement and rate diagrams |
| `raw` | `tag` | Unrecognised **block** element. Children: a leading `text` node (the element's own `.text`), each child run through `_parse_block` (so `raw` can hold **block** children), and each child's `.tail` as a further `text` node -- nothing is dropped |

### `_apply_identity`

`build/parse.py::_apply_identity(node, el)` lifts, when present as attributes /
direct children of `el`:

* `el.get("eId")` -> `attrs["eid"]`
* direct child `<num>` text (stripped) -> `attrs["num"]`
* direct child `<heading>` text (`itertext`, stripped) -> `attrs["heading"]`

It is called for `section`, `provision`, `example`, `penalty`, `note`, `list`
and `table`. It is **not** called for `item` (which lifts only `num`, by hand),
`content`, `para`, `intro`, `row`, `cell`, `figure`, `raw` or any inline kind.

## Inline kinds

Only ever children of `para` / `intro` / `item` / `cell`.

| `kind` | `attrs` | Meaning |
|--------|---------|---------|
| `text` | -- | Leaf text in `node.text`, unescaped; Stage 2 escapes |
| `emphasis` | `style` (`italic`\|`bold`) | Wraps inline children; nests |
| `term` | `term` (lower-cased key), `display` | A defined-term usage |
| `ref` | `href`, `text`, `target_eid?`, `status` (`resolved`\|`ambiguous`\|`unresolved`) | Cross-reference; always same-Act. `target_eid` present only when `status == "resolved"`. Resolution is delegated to `RefIndex.resolve` (see below) |
| `date` | `iso?` | `<date>` -- styled span, text verbatim |
| `quantity` | `refers_to?` | `<quantity>` -- styled span, text verbatim |
| `inline_raw` | `tag` | **Any** unrecognised inline element (`<def>`, `<role>`, `<mod>`, `<sup>`, ...). The parser recurses children and emits `node.text` + every child `.tail`. This is the mandatory generic fallback: an if/elif inline chain with no else silently drops operative text |

## Cross-reference resolution (`RefIndex.resolve`)

`build/parse.py::_parse_ref` calls, for every `<ref>`:

```python
RefIndex.resolve(
    href: str,               # the raw "#..." fragment
    from_eid: str,           # the enclosing section's eId
    display_text: str = "",  # the ref's visible text ("section 4-15") --
                             #   needed to recover ITAA hyphen-truncated hrefs
    following_text: str = "",  # the ref element's .tail -- "of the {Other Act}"
                             #   here means the ref names a *different* Act, so
                             #   any same-Act target is declined (unresolved)
) -> Resolution               # .status in {resolved, ambiguous, unresolved};
                              # .target_eid set only when resolved
```

`resolve` also increments `RefIndex.tally` (a `Counter` over the three statuses)
which the build writes to `ref-tally.json`. A third-party style map never calls
`resolve` itself -- it only reads `status` / `target_eid` off the `ref` node.

## Stage 2: the style map

`build/render.py:render_section(node, style)` is a post-order walk. Each child is
rendered to a string first; the node and the **list** of child strings (never a
pre-joined blob) are handed to `style.render(node, children)`.

A `StyleMap` (see `build/stylemap.py`) is a class with one method per `kind`
plus a fallback. `HtmlStyleMap.render` dispatches:

```python
handler = getattr(self, "_" + node.kind, self._raw)
return handler(node, children)
```

so the method-name set is exactly:

```
_section _provision _content _para
_note _example _penalty _list _intro _item
_table _row _cell _figure
_text _emphasis _term _ref _date _quantity _inline_raw
_raw            # also the fallback for any kind without its own method
```

Each `_<kind>(self, node: Node, children: list[str]) -> str`.

**Marker format is per level**, in `HtmlStyleMap.MARKERS`: `(1)` for
`subsection`, `(a)` for `paragraph` / `subparagraph`, a bare `2` (no
parentheses) for `clause` / `subclause` -- matching the gov Schedule render.
Override that dict in one place to change all markers.

**Security.** The rendered string is injected into the reader via Vue's
`v-html`. Every text value and every attribute value passes through
`html.escape`. No method emits a `<script>` element, an `on*` handler attribute,
a `style` attribute, or a `javascript:` URL. Subclasses inherit this obligation.

### `--style-map` / `STYLE_MAP` contract

`lex-au-explorer-build --style-map path/to/mymap.py` loads that file with
`importlib.util.spec_from_file_location`, executes it, and reads a module-level
attribute named `STYLE_MAP`. That object is used as the style for the whole
build. It must implement `render(node, children: list[str]) -> str`; the easy
path is `class MyMap(HtmlStyleMap)` overriding one or two `_<kind>` methods, then
`STYLE_MAP = MyMap()`. Absent `--style-map`, the build uses `HtmlStyleMap()`.
Delivery is build-time only: there is no runtime style switch in the deployed
frontend. `--emit-ir DIR` covers consumers who want to render elsewhere.

## Numbering normalisation caveat (Stage 1 alters source text)

Stage 1 canonicalises provision numbering. A provision's number lives **only**
in `attrs["num"]`. If the first `para`'s leading text, after `lstrip`, is
exactly `(<that provision's own num>)` followed by optional whitespace or tabs,
that token and its trailing whitespace are removed from the `text` node. The
match is **guarded on the provision's own `num`**: a leading parenthetical that
is not the provision number (`(see subsection 33(3))`,
`(unless subparagraph (ii) applies)`) is left byte for byte intact. A leading
run of tab characters on a first `text` node is also collapsed to nothing.

This is the one place the IR text is not a verbatim copy of the source `<p>`
text. It exists because ITAA-style source frequently embeds the number a second
time (`<p>\t(2)\tYour income tax ...`), which would otherwise render next to the
style-map-added marker (gap G4).

## Figure assets (`asset` bool)

`figure.attrs["asset"]` is `False` out of the parser. During the build,
`build/assets.py:copy_figure_assets` copies every referenced image basename from
`--corpus-images` (default `<corpus-dir>/images`, normally absent) into
`<out>/images/`; the CLI then sets `asset = basename not in missing` on each
`figure` node **before** rendering and before `--emit-ir` writes it. So an
emitted `figure` node's `asset` reflects whether its image was actually found at
build time. `HtmlStyleMap._figure` renders `<figure><img src="/data/images/...">`
when `asset` is true and a labelled `[figure: ...]` placeholder otherwise (never
a blank or a broken `<img>`).
