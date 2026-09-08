import json
from pathlib import Path

from build.definitions import build_terms, _surface_forms

FIXTURES = Path(__file__).parent / "fixtures"


def test_surface_forms_matches_shared_fixture():
    fixture = json.loads((FIXTURES / "surface-forms.json").read_text())
    for term, expected in fixture.items():
        assert set(_surface_forms(term)) == set(expected), term


def test_build_terms_groups_multiply_defined():
    rows = [
        {"term": "associate", "display_term": "associate", "section_eid": "part-5__sec-40",
         "definition_text": "means B", "act_alike": False},
        {"term": "associate", "display_term": "associate", "section_eid": "part-2__sec-10",
         "definition_text": "means A", "act_alike": False},
    ]
    terms = build_terms(rows, body_text="an associate of the person")
    assert len(terms) == 1
    assert terms[0]["term"] == "associate"
    assert [d["eid"] for d in terms[0]["defs"]] == ["part-2__sec-10", "part-5__sec-40"]
    assert terms[0]["usedInBody"] is True


def test_build_terms_renames_keys_and_via():
    rows = [{"term": "widget", "display_term": "Widget", "section_eid": "sec-3",
             "definition_text": "means a part", "act_alike": True,
             "via": {"act_title": "Beta Act 2001", "section_eid": "sec-3", "resolved": True}}]
    terms = build_terms(rows, body_text="the widget must")
    d = terms[0]["defs"][0]
    assert d == {"text": "means a part", "eid": "sec-3",
                 "via": {"actTitle": "Beta Act 2001", "sectionEid": "sec-3", "resolved": True}}
    assert terms[0]["display"] == "Widget"
    assert terms[0]["actAlike"] is True


def test_build_terms_used_in_body_via_inflection():
    rows = [{"term": "centre", "display_term": "centre", "section_eid": "sec-1",
             "definition_text": "means a place", "act_alike": False}]
    terms = build_terms(rows, body_text="operates two centres in the state")
    assert terms[0]["usedInBody"] is True


def test_build_terms_omits_flags_when_false():
    rows = [{"term": "onlydefined", "display_term": "onlydefined", "section_eid": "sec-1",
             "definition_text": "means x", "act_alike": False}]
    terms = build_terms(rows, body_text="nothing relevant here")
    assert "usedInBody" not in terms[0]
    assert "actAlike" not in terms[0]
    assert len(terms) == 1  # NOT dropped from the bundle
