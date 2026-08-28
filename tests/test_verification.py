from __future__ import annotations

import json
from datetime import date

import pytest

from build.verification import (
    _ODataClient,
    fetch_changed_title_ids,
    check_act,
    derive_status,
    run_verification,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="OK"):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"value": []}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"{self.status_code} error", response=self)

    def json(self):
        return self._payload


class FakeSession:
    """Records every GET and replays a queued list of FakeResponses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        if not self._responses:
            raise AssertionError(f"unexpected extra GET: {url} {params}")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def test_odata_client_retries_on_503_then_succeeds():
    session = FakeSession(
        [
            FakeResponse(status_code=503, text="busy"),
            FakeResponse(status_code=200, payload={"value": [{"titleId": "C1"}]}),
        ]
    )
    client = _ODataClient(session=session, backoff=0)

    result = client.get("Versions", {"$filter": "x"})

    assert result == {"value": [{"titleId": "C1"}]}
    assert len(session.calls) == 2


def test_odata_client_raises_on_404_without_retrying():
    session = FakeSession([FakeResponse(status_code=404, text="nope")])
    client = _ODataClient(session=session, backoff=0)

    with pytest.raises(Exception):
        client.get("Versions", {"$filter": "x"})

    assert len(session.calls) == 1


def test_fetch_changed_title_ids_filters_by_unquoted_datetimeoffset_window():
    session = FakeSession(
        [
            FakeResponse(
                payload={"value": [{"titleId": "C1"}, {"titleId": "C2"}, {"titleId": "C1"}]}
            )
        ]
    )
    client = _ODataClient(session=session, backoff=0)

    changed = fetch_changed_title_ids(
        client, since=date(2026, 7, 1), upper_bound=date(2026, 8, 28)
    )

    assert changed == {"C1", "C2"}
    flt = session.calls[0]["params"]["$filter"]
    assert "isLatest eq true" in flt
    # DateTimeOffset literals are unquoted, carry a time component, no Z suffix
    assert "start gt 2026-07-01T00:00:00" in flt
    assert "start le 2026-08-28T23:59:59" in flt
    assert "'" not in flt.split("start gt ")[1]
    assert session.calls[0]["params"]["$select"] == "titleId"


def test_check_act_reports_live_compilation_with_date_trimmed():
    session = FakeSession(
        [
            FakeResponse(payload={"value": [{"isInForce": True}]}),
            FakeResponse(
                payload={
                    "value": [
                        {"registerId": "C2026C00301", "start": "2026-07-01T00:00:00+10:00"}
                    ]
                }
            ),
        ]
    )
    client = _ODataClient(session=session, backoff=0)

    entry = check_act(client, "C2004A03712", today=date(2026, 8, 28))

    assert entry == {
        "checked_at": "2026-08-28",
        "repealed": False,
        "live_comp_id": "C2026C00301",
        "live_effective_date": "2026-07-01",
    }
    assert session.calls[0]["params"]["$filter"] == "id eq 'C2004A03712'"


def test_check_act_flags_repealed_when_title_no_longer_in_force():
    session = FakeSession([FakeResponse(payload={"value": [{"isInForce": False}]})])
    client = _ODataClient(session=session, backoff=0)

    entry = check_act(client, "C2004A03712", today=date(2026, 8, 28))

    assert entry == {"checked_at": "2026-08-28", "repealed": True}
    # no second (Versions) call once we know it is repealed
    assert len(session.calls) == 1


def test_check_act_flags_repealed_when_title_row_absent():
    session = FakeSession([FakeResponse(payload={"value": []})])
    client = _ODataClient(session=session, backoff=0)

    entry = check_act(client, "C9999A99999", today=date(2026, 8, 28))

    assert entry == {"checked_at": "2026-08-28", "repealed": True}


def test_derive_status_current_when_live_matches_current_corpus_compilation():
    entry = {
        "checked_at": "2026-08-28",
        "repealed": False,
        "live_comp_id": "C2026C00227",
        "live_effective_date": "2026-06-04",
    }
    assert derive_status(entry, "C2026C00227") == {
        "status": "current",
        "checked_at": "2026-08-28",
    }


def test_derive_status_stale_carries_live_fields_for_the_panel():
    entry = {
        "checked_at": "2026-08-28",
        "repealed": False,
        "live_comp_id": "C2026C00301",
        "live_effective_date": "2026-07-01",
    }
    assert derive_status(entry, "C2026C00227") == {
        "status": "stale",
        "checked_at": "2026-08-28",
        "live_comp_id": "C2026C00301",
        "live_effective_date": "2026-07-01",
    }


def test_derive_status_recomputes_to_current_after_corpus_catches_up():
    """A previously-stale observation must not stay 'stale' once the corpus
    has been re-ingested at the compilation the API reported."""
    entry = {
        "checked_at": "2026-08-28",
        "repealed": False,
        "live_comp_id": "C2026C00301",
        "live_effective_date": "2026-07-01",
    }
    assert derive_status(entry, "C2026C00301")["status"] == "current"


def test_derive_status_repealed():
    entry = {"checked_at": "2026-08-28", "repealed": True}
    assert derive_status(entry, "C2026C00227") == {
        "status": "repealed",
        "checked_at": "2026-08-28",
    }


def test_derive_status_none_when_no_entry_and_no_run():
    assert derive_status(None, "C2026C00227") is None
    assert derive_status(None, "C2026C00227", ran_at=None) is None


def test_derive_status_current_for_absent_entry_after_a_completed_run():
    """A completed run records only the exceptions; every Act it did not
    flag is current as of the run date."""
    assert derive_status(None, "C2026C00227", ran_at="2026-08-28") == {
        "status": "current",
        "checked_at": "2026-08-28",
    }


# --- run_verification -------------------------------------------------------

CORPUS_INDEX = {
    "acts": {
        "privacy-act-1988": {
            "title_id": "C2004A03712",
            "comp_id": "C2026C00227",
            "effective_date": "2026-06-04",
        },
        "income-tax-assessment-act-1997": {
            "title_id": "C2004A05138",
            "comp_id": "C2026C00100",
            "effective_date": "2026-01-01",
        },
    },
    "updated_at": "2026-08-01",
}


class ScriptedClient:
    """Routes ``.get`` by endpoint + filter to a handler, so a whole
    verification run can be driven without HTTP."""

    def __init__(self, changed_title_ids, titles, versions, fail_title_ids=(), interrupt_title_ids=()):
        self._changed = list(changed_title_ids)
        self._titles = titles  # title_id -> {"isInForce": bool}
        self._versions = versions  # title_id -> {"registerId", "start"}
        self._fail = set(fail_title_ids)
        self._interrupt = set(interrupt_title_ids)
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        flt = (params or {}).get("$filter", "")
        if path == "Versions" and "isLatest eq true and start gt" in flt:
            return {"value": [{"titleId": t} for t in self._changed]}
        if path == "Titles":
            tid = flt.split("id eq '")[1].split("'")[0]
            if tid in self._interrupt:
                raise KeyboardInterrupt
            if tid in self._fail:
                import requests

                raise requests.ConnectionError("boom")
            row = self._titles.get(tid)
            return {"value": [row] if row else []}
        if path == "Versions":
            tid = flt.split("titleId eq '")[1].split("'")[0]
            row = self._versions.get(tid)
            return {"value": [row] if row else []}
        raise AssertionError(f"unrouted call: {path} {params}")


def test_run_verification_records_only_exceptions_not_the_current_majority(tmp_path):
    out = tmp_path / "verification.json"
    corpus_index = tmp_path / "index.json"
    corpus_index.write_text(json.dumps(CORPUS_INDEX))

    client = ScriptedClient(
        changed_title_ids=["C2004A03712"],
        titles={"C2004A03712": {"isInForce": True}},
        versions={
            "C2004A03712": {"registerId": "C2026C00301", "start": "2026-07-01T00:00:00+10:00"}
        },
    )

    summary = run_verification(
        corpus_index, out, client=client, delay=0, today=date(2026, 8, 28)
    )

    data = json.loads(out.read_text())
    assert data["generated_at"] == "2026-08-28"
    # only the stale Act is written; the inferred-current majority is not
    assert data["acts"] == {
        "C2004A03712": {
            "checked_at": "2026-08-28",
            "repealed": False,
            "live_comp_id": "C2026C00301",
            "live_effective_date": "2026-07-01",
        }
    }
    assert summary == {"current": 0, "stale": 1, "repealed": 0, "inferred": 1, "unverified": 0}


def test_run_verification_omits_a_changed_act_that_is_actually_current(tmp_path):
    out = tmp_path / "verification.json"
    corpus_index = tmp_path / "index.json"
    corpus_index.write_text(json.dumps(CORPUS_INDEX))

    client = ScriptedClient(
        changed_title_ids=["C2004A03712"],
        titles={"C2004A03712": {"isInForce": True}},
        versions={
            # live compilation equals the corpus copy -> nothing to record
            "C2004A03712": {"registerId": "C2026C00227", "start": "2026-06-04T00:00:00+10:00"}
        },
    )

    summary = run_verification(
        corpus_index, out, client=client, delay=0, today=date(2026, 8, 28)
    )

    assert json.loads(out.read_text())["acts"] == {}
    assert summary["current"] == 1


def test_run_verification_keeps_prior_entry_when_a_check_fails(tmp_path):
    out = tmp_path / "verification.json"
    out.write_text(
        json.dumps(
            {
                "generated_at": "2026-08-20",
                "acts": {
                    "C2004A03712": {
                        "checked_at": "2026-08-20",
                        "repealed": False,
                        "live_comp_id": "C2026C00227",
                        "live_effective_date": "2026-06-04",
                    }
                },
            }
        )
    )
    corpus_index = tmp_path / "index.json"
    corpus_index.write_text(json.dumps(CORPUS_INDEX))

    client = ScriptedClient(
        changed_title_ids=["C2004A03712"],
        titles={},
        versions={},
        fail_title_ids=["C2004A03712"],
    )

    summary = run_verification(
        corpus_index, out, client=client, delay=0, today=date(2026, 8, 28)
    )

    data = json.loads(out.read_text())
    # prior observation preserved, with its older checked_at
    assert data["acts"]["C2004A03712"]["checked_at"] == "2026-08-20"
    assert summary["unverified"] == 1


def test_run_verification_leaves_generated_at_null_when_interrupted(tmp_path):
    """An interrupted run must not stamp generated_at -- a partial exception
    list must not read as an authoritative 'everything else is current'."""
    out = tmp_path / "verification.json"
    corpus_index = tmp_path / "index.json"
    corpus_index.write_text(json.dumps(CORPUS_INDEX))

    client = ScriptedClient(
        changed_title_ids=["C2004A03712", "C2004A05138"],
        titles={"C2004A03712": {"isInForce": True}},
        versions={
            "C2004A03712": {"registerId": "C2026C00301", "start": "2026-07-01T00:00:00+00:00"}
        },
        interrupt_title_ids=["C2004A05138"],
    )

    with pytest.raises(KeyboardInterrupt):
        run_verification(
            corpus_index, out, client=client, delay=0, today=date(2026, 8, 28), flush_every=1
        )

    data = json.loads(out.read_text())
    assert data["generated_at"] is None
    # the stale Act found before the interrupt is still persisted for the next run
    assert data["acts"]["C2004A03712"]["live_comp_id"] == "C2026C00301"


def test_run_verification_counts_repealed(tmp_path):
    out = tmp_path / "verification.json"
    corpus_index = tmp_path / "index.json"
    corpus_index.write_text(json.dumps(CORPUS_INDEX))

    client = ScriptedClient(
        changed_title_ids=["C2004A03712"],
        titles={"C2004A03712": {"isInForce": False}},
        versions={},
    )

    summary = run_verification(
        corpus_index, out, client=client, delay=0, today=date(2026, 8, 28)
    )

    assert json.loads(out.read_text())["acts"]["C2004A03712"] == {
        "checked_at": "2026-08-28",
        "repealed": True,
    }
    assert summary["repealed"] == 1


def test_run_verification_tolerates_missing_updated_at(tmp_path):
    out = tmp_path / "verification.json"
    corpus_index = tmp_path / "index.json"
    idx = {"acts": CORPUS_INDEX["acts"]}
    corpus_index.write_text(json.dumps(idx))

    client = ScriptedClient(changed_title_ids=[], titles={}, versions={})

    summary = run_verification(
        corpus_index, out, client=client, delay=0, today=date(2026, 8, 28)
    )

    assert summary["inferred"] == 2
    data = json.loads(out.read_text())
    assert data == {"generated_at": "2026-08-28", "acts": {}}
