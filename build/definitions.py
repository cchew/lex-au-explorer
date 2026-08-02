from __future__ import annotations
from lexaugraph.resolver import DefinitionResolver


def resolve_section_definitions(
    resolver: DefinitionResolver,
    act_frbr_uri: str,
    section_eid: str,
    term_names: set[str],
) -> dict[str, dict]:
    """Resolve each term used in a section to its section-scoped definition.

    Terms that don't resolve (extraction gap, or genuinely ambiguous per
    DefinitionResolver's own None-on-ambiguity contract) are silently
    omitted -- the reader renders those as plain, unstyled text rather
    than a broken hover, per the design spec's Error Handling section."""
    result: dict[str, dict] = {}
    for term in term_names:
        found = resolver.resolve_definition(term, act_frbr_uri, section_eid=section_eid)
        if found is None:
            continue
        result[term] = {"text": found.definition_text, "section_eid": found.section_eid}
    return result
