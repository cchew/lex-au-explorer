from pathlib import Path
import pytest
from lexaugraph.graph import LexAuGraph
from lexaugraph.loader import parse_act
from lexaugraph.resolver import DefinitionResolver
from build.definitions import resolve_section_definitions

FIXTURES = Path(__file__).parent / "fixtures"
INDEX_ENTRY = {
    "name": "Privacy Act 1988", "year": 1988, "number": 119,
    "effective_date": "2026-06-04", "xml_path": "xml/privacy-act-1988.xml",
}


@pytest.fixture()
def resolver() -> DefinitionResolver:
    act_data = parse_act(FIXTURES / "xml" / "privacy-act-1988.xml", INDEX_ENTRY)
    g = LexAuGraph()
    g.add_act_data(act_data)
    return DefinitionResolver(g)


def test_resolve_section_definitions_finds_used_term(resolver: DefinitionResolver):
    result = resolve_section_definitions(
        resolver, "/akn/au/act/1988/119", "part-I__sec-6", {"personal information"}
    )
    assert "personal information" in result
    assert result["personal information"]["section_eid"] == "part-I__sec-6"


def test_resolve_section_definitions_skips_unresolved_term(resolver: DefinitionResolver):
    result = resolve_section_definitions(
        resolver, "/akn/au/act/1988/119", "part-I__sec-6", {"not a real term"}
    )
    assert "not a real term" not in result
