# Parity oracle: synthetic penalty-block fixture

- Fixture: `penalty-block.xml`
- eId: `part-2__sec-12`
- Source of truth: synthetic minimal AKN. The real-corpus parity fixtures have
  no `hcontainer name="penalty"` example, so this hand-written fixture is the
  G7 regression guard for penalty-block rendering.

## Why this fixture exists

`hcontainer name="penalty"` had no parity coverage. This guards that the
penalty line renders on its own, after the offence provision, and is not
dropped or folded into the subsection body.

## Authoritative text

**12  Failure to notify the Registrar**

(1) A person commits an offence if the person fails to notify the Registrar within 14 days.

Penalty: 50 penalty units.

## Structure notes

- `<section>` -> `<subsection>` -> `<content>` offence provision then a sibling
  `<hcontainer name="penalty">` with its own `<content>`.
- Rendered by `HtmlStyleMap._penalty` as `<div class="akn-penaltytext">`.
