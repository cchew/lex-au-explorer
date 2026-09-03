# Parity oracle: synthetic blockList fixture

- Fixture: `blocklist-items.xml`
- eId: `part-1__sec-5`
- Source of truth: synthetic minimal AKN. The real-corpus parity fixtures have
  no compact `<blockList>` example, so this hand-written fixture is the S5
  regression guard for list-introduction + item-marker rendering.

## Why this fixture exists

`<blockList>` / `<listIntroduction>` / `<item>` had no parity coverage. This
guards that the chapeau, the list introduction and each `(a)`/`(b)`/`(c)` item
marker and body render, in document order.

## Authoritative text

**5  Register of members**

(1) A company must keep a register of members containing:

the following information:

- (a) the name and address of each member; and
- (b) the date on which each person was entered in the register as a member; and
- (c) the date on which any person ceased to be a member.

## Structure notes

- `<section>` -> `<subsection>` -> `<content>` chapeau then a sibling
  `<blockList>` with a `<listIntroduction>` and three `<item>` children.
- Item markers are rendered parenthesised (`(a)`) by `HtmlStyleMap._item`.
