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


def _row(eid, scope=None, term="use"):
    r = {"term": term, "display_term": term, "section_eid": eid,
         "definition_text": "means x", "act_alike": False}
    if scope is not None:
        r["scope"] = scope
    return r


def test_build_terms_carries_scope_only_for_local():
    terms = build_terms([_row("sec-3", "act"), _row("part-1__sec-5", "part-1__sec-5")], "")
    defs = {d["eid"]: d for d in terms[0]["defs"]}
    assert "scope" not in defs["sec-3"]
    assert defs["part-1__sec-5"]["scope"] == "part-1__sec-5"


def test_build_terms_same_eid_different_scope_kept():
    terms = build_terms([_row("sec-3", "b"), _row("sec-3", "a")], "")
    assert [d["scope"] for d in terms[0]["defs"]] == ["a", "b"]


def test_build_terms_local_forces_used_in_body():
    terms = build_terms([_row("sec-3", "sec-3")], "nothing relevant")
    assert terms[0]["usedInBody"] is True


def test_body_text_keeps_local_def_sections(tmp_path, monkeypatch):
    # def_eids must come only from Act-wide rows: a section holding a local def
    # stays in body_text, so an Act-wide term used there keeps usedInBody.
    from build.cli import _act_wide_def_eids

    rows = [_row("sec-1", "act", term="widget"), _row("sec-2", "sec-2", term="gadget")]
    assert _act_wide_def_eids(rows) == {"sec-1"}
    # rows without a scope key are Act-wide (older graph)
    assert _act_wide_def_eids([_row("sec-9")]) == {"sec-9"}
    terms = build_terms(rows, "the widget in sec-2 text")
    assert next(t for t in terms if t["term"] == "widget")["usedInBody"] is True
