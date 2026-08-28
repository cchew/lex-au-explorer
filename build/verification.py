from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests

API_BASE = "https://api.prod.legislation.gov.au/v1"
_USER_AGENT = "lex-au-explorer verification (+https://github.com/cchew/lex-au-explorer)"
_RETRY_STATUS = {429, 500, 502, 503, 504}
_TIMEOUT = 60


class _ODataClient:
    """Minimal client for legislation.gov.au's OData API.

    Mirrors lex-au's crawler in the parts that matter here: an
    ``Accept: application/json`` session, ``raise_for_status`` before
    ``.json()`` (the API's edge/WAF returns an HTML 403 page, not the
    API's JSON error shape, for some requests), plus a bounded retry on
    transient 429/5xx since a verification run makes thousands of calls.
    """

    def __init__(self, session=None, max_retries: int = 3, backoff: float = 1.0):
        self._session = session or requests.Session()
        self._session.headers.setdefault("Accept", "application/json")
        self._session.headers.setdefault("User-Agent", _USER_AGENT)
        self._max_retries = max_retries
        self._backoff = backoff

    def get(self, path: str, params: dict | None = None) -> dict:
        for attempt in range(self._max_retries):
            resp = self._session.get(
                f"{API_BASE}/{path}", params=params, timeout=_TIMEOUT
            )
            if (
                resp.status_code in _RETRY_STATUS
                and attempt < self._max_retries - 1
            ):
                time.sleep(self._backoff * (2 ** attempt))
                continue
            resp.raise_for_status()
            return resp.json()
        raise AssertionError("unreachable")  # loop always returns or raises


def fetch_changed_title_ids(client, since: date, upper_bound: date | None = None) -> set[str]:
    """Title IDs whose latest in-force compilation started within
    ``(since, upper_bound]``.

    One call. The upper bound excludes not-yet-commenced compilations
    (a future-dated ``start``) from reading as "your copy is stale".
    ``start`` is ``Edm.DateTimeOffset`` in the API schema: the literal
    is unquoted, must include a time component, and must not carry a
    trailing offset/``Z`` (confirmed live by lex-au's crawler).
    """
    upper_bound = upper_bound or date.today()
    flt = (
        f"isLatest eq true"
        f" and start gt {since.isoformat()}T00:00:00"
        f" and start le {upper_bound.isoformat()}T23:59:59"
    )
    rows = client.get("Versions", {"$filter": flt, "$select": "titleId"}).get("value", [])
    return {r["titleId"] for r in rows if r.get("titleId")}


def _odata_str(value: str) -> str:
    return value.replace("'", "''")


def check_act(client, title_id: str, *, today: date | None = None) -> dict:
    """Observe one Act's live state on legislation.gov.au.

    Returns a stored-observation dict, not a verdict: ``run_verification``
    persists it and ``derive_status`` turns it into a panel status against
    the *current* corpus compilation id at build time.
    """
    checked_at = (today or date.today()).isoformat()

    titles = client.get(
        "Titles",
        {"$filter": f"id eq '{_odata_str(title_id)}'", "$top": 1, "$select": "isInForce"},
    ).get("value", [])
    if not titles or not titles[0].get("isInForce", False):
        return {"checked_at": checked_at, "repealed": True}

    versions = client.get(
        "Versions",
        {
            "$filter": f"titleId eq '{_odata_str(title_id)}' and isLatest eq true",
            "$top": 1,
            "$select": "registerId,start",
        },
    ).get("value", [])
    if not versions:
        return {"checked_at": checked_at, "repealed": True}

    v = versions[0]
    return {
        "checked_at": checked_at,
        "repealed": False,
        "live_comp_id": v["registerId"],
        "live_effective_date": v["start"][:10],
    }


def derive_status(
    entry: dict | None, corpus_comp_id: str, ran_at: str | None = None
) -> dict | None:
    """Turn a stored observation into the panel status.

    ``verification.json`` records only exceptions (stale / repealed), so an
    Act with no entry is current *provided a run completed* -- ``ran_at`` is
    the completed run's date (``generated_at``); when it is ``None`` no run
    has completed and the panel shows nothing. A recorded stale entry is
    recomputed against the current corpus compilation id, so a re-ingest
    that closes the gap flips it back to ``current`` with no re-verification.
    """
    if not entry:
        return {"status": "current", "checked_at": ran_at} if ran_at else None
    checked_at = entry.get("checked_at")
    if entry.get("repealed"):
        return {"status": "repealed", "checked_at": checked_at}
    if entry.get("live_comp_id") == corpus_comp_id:
        return {"status": "current", "checked_at": checked_at}
    return {
        "status": "stale",
        "checked_at": checked_at,
        "live_comp_id": entry.get("live_comp_id"),
        "live_effective_date": entry.get("live_effective_date"),
    }


_SINCE_MARGIN_DAYS = 30
_FLUSH_EVERY = 25
_UNVERIFIED_WARN_FRACTION = 0.05


def _since_date(updated_at: str | None) -> date:
    if not updated_at:
        return date(2000, 1, 1)
    return date.fromisoformat(updated_at[:10]) - timedelta(days=_SINCE_MARGIN_DAYS)


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    os.replace(tmp, path)


def run_verification(
    corpus_index_path,
    out_path,
    *,
    client=None,
    delay: float = 1.5,
    today: date | None = None,
    flush_every: int = _FLUSH_EVERY,
) -> dict:
    """Refresh ``out_path`` with the current *exceptions* -- Acts whose
    corpus copy is behind legislation.gov.au or has been repealed.

    One bulk "what changed" call, then a targeted check per changed Act.
    Only stale/repealed observations are written; a completed run stamps
    ``generated_at`` so the build can treat every unlisted Act as current.
    An interrupted run leaves ``generated_at`` null (the partial exception
    list is not authoritative) but keeps what it found for the next run's
    merge. Never raises on API failure. Returns summary counts.
    """
    corpus_index_path = Path(corpus_index_path)
    out_path = Path(out_path)
    today = today or date.today()
    client = client or _ODataClient(backoff=delay)

    index = json.loads(corpus_index_path.read_text())
    acts = index["acts"]
    by_title_id = {a["title_id"]: a for a in acts.values()}
    total = len(by_title_id)

    prior = {}
    if out_path.exists():
        prior = json.loads(out_path.read_text()).get("acts", {})

    try:
        changed = fetch_changed_title_ids(
            client, since=_since_date(index.get("updated_at")), upper_bound=today
        )
    except requests.RequestException as e:
        print(f"verification: bulk change query failed ({e}); keeping existing file")
        return {"current": 0, "stale": 0, "repealed": 0, "inferred": 0, "unverified": total}

    result: dict[str, dict] = {}
    summary = {"current": 0, "stale": 0, "repealed": 0, "inferred": total, "unverified": 0}
    processed_changed = 0

    for title_id, act in by_title_id.items():
        if title_id not in changed:
            continue
        summary["inferred"] -= 1

        try:
            entry = check_act(client, title_id, today=today)
        except requests.RequestException as e:
            print(f"verification: check failed for {title_id} ({e}); keeping prior observation")
            if title_id in prior:
                result[title_id] = prior[title_id]
            summary["unverified"] += 1
        else:
            if entry["repealed"]:
                result[title_id] = entry
                summary["repealed"] += 1
            elif entry["live_comp_id"] == act["comp_id"]:
                summary["current"] += 1  # current: nothing to record
            else:
                result[title_id] = entry
                summary["stale"] += 1

        processed_changed += 1
        if delay:
            time.sleep(delay)
        if flush_every and processed_changed % flush_every == 0:
            _write_json(out_path, {"generated_at": None, "acts": result})

    _write_json(out_path, {"generated_at": today.isoformat(), "acts": result})

    print(
        "verification: "
        f"{summary['current']} current, {summary['stale']} stale, "
        f"{summary['repealed']} repealed, {summary['inferred']} inferred, "
        f"{summary['unverified']} unverified (of {total})"
    )
    if total and summary["unverified"] > _UNVERIFIED_WARN_FRACTION * total:
        print(
            f"verification: WARNING -- {summary['unverified']}/{total} Acts could not be "
            "verified this run; the source-fidelity panel will fall back to their last "
            "observation or show nothing"
        )
    return summary
