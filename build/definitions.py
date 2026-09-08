from __future__ import annotations
import re

_APOS = ("'s", "’s")


def _inflect_last_word(term: str) -> list[str]:
    parts = term.split(" ")
    last = parts[-1]
    variants = [last + "s", last + "es"] + [last + a for a in _APOS]
    if last.endswith("y") and len(last) > 1 and last[-2] not in "aeiou":
        variants.append(last[:-1] + "ies")
    if last.endswith("s") and len(last) > 1:
        variants.append(last[:-1])
    return [" ".join(parts[:-1] + [v]).strip() for v in variants]


def _surface_forms(term: str) -> list[str]:
    base = term.lstrip("*").strip().lower()
    base = re.sub(r"\s+", " ", base)
    forms = [base, *[_f.lower() for _f in _inflect_last_word(base)]]
    seen: dict[str, None] = {}
    for f in forms:
        if f:
            seen.setdefault(f, None)
    return list(seen)


def _used_in_body(term: str, body_text_lower: str) -> bool:
    for form in _surface_forms(term):
        if re.search(r"\b" + re.escape(form) + r"\b", body_text_lower):
            return True
    return False


def build_terms(rows: list[dict], body_text: str) -> list[dict]:
    body_lower = body_text.lower()
    grouped: dict[str, dict] = {}
    for r in rows:
        t = grouped.setdefault(
            r["term"],
            {"term": r["term"], "display": r.get("display_term", r["term"]), "defs": [], "_actAlike": False},
        )
        d: dict = {"text": r["definition_text"], "eid": r["section_eid"]}
        via = r.get("via")
        if via is not None:
            d["via"] = {"actTitle": via["act_title"], "resolved": via["resolved"]}
            if via.get("section_eid"):
                d["via"]["sectionEid"] = via["section_eid"]
        t["defs"].append(d)
        t["_actAlike"] = t["_actAlike"] or bool(r.get("act_alike"))
    out: list[dict] = []
    for t in grouped.values():
        t["defs"].sort(key=lambda d: d["eid"])
        entry = {"term": t["term"], "display": t["display"], "defs": t["defs"]}
        if t["_actAlike"]:
            entry["actAlike"] = True
        if _used_in_body(t["term"], body_lower):
            entry["usedInBody"] = True
        out.append(entry)
    return sorted(out, key=lambda e: e["term"])
