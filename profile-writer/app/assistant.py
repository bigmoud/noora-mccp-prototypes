"""What the next nurse sees when she opens the chat: a stand-in for how Copilot would
read a richer profile. It only reads the profile. It writes nothing, sends nothing,
and gives no medical advice, so it is plain code rather than a model call.

Field names follow the UPE "Health Information" panel MSEs see today (condition area,
expected due date, time until due, trimester, baby DOB, baby age). "Who holds the phone"
is a proposed new field: UPE doesn't have it yet.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from .store import Store

HOLDER_TEXT = {"mother": "the mother herself", "husband": "her husband", "mother_in_law": "her mother-in-law",
               "other_family": "another family member"}
AREA_TEXT = {"ANC_EDD": "pregnancy campaign, timed from due date", "PNC_DOB": "postnatal campaign, timed from baby's DOB",
             "HRPW": "high-risk pregnancy campaign", "SNCU": "sick newborn care campaign"}


def _source(f: dict) -> str:
    ev = f["evidence"] or ""
    if ev.startswith("("):
        return ev.strip("()")
    who = "reviewer" if f["extractor"].startswith("reviewer") else "family"
    return f"{who}: “{ev}”"


def _age(days: int) -> str:
    if days < 60:
        return f"{days} days"
    months = days // 30
    return f"{months} months" if months < 24 else f"{months // 12} years {months % 12} months"


def nurse_view(store: Store, uid: str, today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    fam = store.family(uid) or {}
    facts = store.active_facts(uid)
    area = fam.get("condition_area", "")
    rows, dont_ask, missing, notes = [], [], [], []

    rows.append({"field": "Condition area", "value": area, "source": AREA_TEXT.get(area, "")})
    edd, dob = facts.get("due_date"), facts.get("baby_dob")
    stage = (facts.get("stage") or {}).get("value")
    if edd and area != "PNC_DOB":
        days = (date.fromisoformat(edd["value"]) - today).days
        weeks_preg = 40 - days / 7
        tri = "1st" if weeks_preg < 14 else "2nd" if weeks_preg < 28 else "3rd"
        rows += [{"field": "Expected due date", "value": edd["value"], "source": _source(edd)},
                 {"field": "Time until due", "value": f"{days} days" if days >= 0 else f"{-days} days past", "source": ""},
                 {"field": "Trimester", "value": tri, "source": ""}]
        dont_ask.append(f"Pregnancy stage: about {weeks_preg:.0f} weeks (due {edd['value']})")
    if dob:
        age = (today - date.fromisoformat(dob["value"])).days
        rows += [{"field": "Baby DOB", "value": dob["value"], "source": _source(dob)},
                 {"field": "Baby age", "value": _age(age), "source": ""}]
        dont_ask.append(f"Baby's age: {_age(age)} (born {dob['value']})")
        if age > 365 and area == "PNC_DOB":
            notes.append("Baby is over a year old but she is still on the postnatal campaign: the profile may be out of date.")
    holder = facts.get("phone_holder")
    rows.append({"field": "Who holds the phone (proposed field)", "value": holder["value"] if holder else "—",
                 "source": _source(holder) if holder else "not known"})

    if stage == "delivered":
        dont_ask.append("Whether she has delivered: yes")
        if not dob:
            missing.append("Baby's date of birth: needed before she can move to the postnatal campaign")
    elif not edd and not dob:
        missing.append("Due date or baby's date of birth")
    if holder:
        notes.append(f"This phone is usually held by {HOLDER_TEXT.get(holder['value'], holder['value'])}. "
                     "Check who is writing before giving advice meant for the mother.")
    else:
        missing.append("Who usually holds this phone")

    if fam.get("paused"):
        notes.insert(0, "Sensitive message on file: automatic profile updates are paused until the clinical team reviews.")
    if area and area not in ("ANC_EDD", "PNC_DOB"):
        notes.append(f"Condition area {area}: this tool proposes changes but never switches her campaign itself.")
    pending = [f for f in facts.values() if f["review_status"] == "pending"]
    if pending:
        notes.append(f"{len(pending)} field(s) were written automatically and are waiting for a reviewer's check.")

    return {"uid": uid, "label": fam.get("label"), "condition_area": area, "rows": rows,
            "dont_ask": dont_ask, "still_missing": missing, "notes": notes}
