"""Write rules: plain code that decides what the extractor's proposals may do.

Every proposal ends in one of:
  write    -> saved to the profile now, and queued for a non-clinical reviewer afterwards
  hold     -> not saved; waits in a queue (reviewer lane, or clinical lane for sensitive cases)
  discard  -> not saved, not queued (logged with the reason)
  same     -> the profile already says this; nothing changes
  shadow   -> shadow mode: logged only

Each decision carries the list of checks it passed or failed, so a reviewer (and the
demo audience) can see exactly why. The model's confidence is only one check of many.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import dates

VALID = {
    "phone_holder": {"mother", "husband", "mother_in_law", "other_family"},
    "stage": {"pregnant", "delivered"},
}
# Noora UPE: campaign = condition area + a date. Only these two have a confirmed switch rule
# (ANC_EDD → PNC_DOB, set together with the baby's DOB). HRPW, SNCU and others: people decide.
AUTO_AREAS = {"ANC_EDD", "PNC_DOB"}
UPE_FIELDS = {"due_date": "expected_due_date", "baby_dob": "baby_dob"}  # [ASK] exact names in onboarding doc
DUE_DATE_SMALL_CHANGE_DAYS = 14
DATE_AGREEMENT_DAYS = 1


@dataclass
class Decision:
    signal: str
    value: str
    action: str = "write"
    lane: str | None = None  # "reviewer" | "clinical" | None
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    proposal: dict = field(default_factory=dict)
    precision: str = "exact"  # "approximate" when written from an age like "3 months old"
    route: str = ""        # final outcome after the judge: write | nurse | clinical | ask_family | discard | same | shadow
    judgement: dict = field(default_factory=dict)

    @property
    def reason(self) -> str:
        failed = [f"{n}: {d}" for n, ok, d in self.checks if not ok]
        return "; ".join(failed) if failed else "all checks passed"

    def to_dict(self) -> dict:
        return {"signal": self.signal, "value": self.value, "action": self.action, "lane": self.lane,
                "reason": self.reason, "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in self.checks],
                "proposal": self.proposal, "route": self.route, "judgement": self.judgement,
                "precision": self.precision}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def _parse_iso(v: str) -> date | None:
    try:
        return date.fromisoformat(v)
    except (TypeError, ValueError):
        return None


def decide(
    signals: list[dict],
    message_text: str,
    msg_day: date,
    profile: dict[str, str],
    *,
    sensitive: bool,
    family_paused: bool,
    rollout_mode: str,
    suspicious: bool = False,
) -> list[Decision]:
    """profile maps signal -> current value (only active facts)."""
    signals = _add_implied_stage(signals)
    out: list[Decision] = []
    for p in signals:
        d = Decision(signal=p["signal"], value=(p.get("value") or "").strip(), proposal=p)
        _check(d, p, message_text, msg_day, profile)
        out.append(d)

    # Sensitive events and paused families override everything: humans with clinical training decide.
    if sensitive or family_paused:
        why = "pregnancy loss or death mentioned" if sensitive else "family paused after an earlier sensitive message"
        for d in out:
            if d.action in ("write", "hold", "same"):
                d.checks.append(("sensitive", False, why))
                d.action, d.lane = "hold", "clinical"
        return out

    if suspicious:
        for d in out:
            if d.action == "write":
                d.checks.append(("reads like a family message", False, "text looks like instructions to the system"))
                d.action, d.lane = "hold", "reviewer"

    for d in out:
        if d.action == "write" and rollout_mode == "shadow":
            d.action = "shadow"
        elif d.action == "write" and rollout_mode == "review_first":
            d.checks.append(("rollout", False, "review-first mode holds every write"))
            d.action, d.lane = "hold", "reviewer"
        elif d.action == "write":
            d.lane = "reviewer"  # written now, checked afterwards
    return out


def _add_implied_stage(signals: list[dict]) -> list[dict]:
    has_delivered = any(s["signal"] == "stage" and s.get("value") == "delivered" for s in signals)
    dob = next((s for s in signals if s["signal"] == "baby_dob" and s.get("subject") == "registered_mother"), None)
    if dob and not has_delivered:
        implied = dict(dob, signal="stage", value="delivered", date_phrase="", date_precision="none",
                       note="implied by the baby's birth date")
        return signals + [implied]
    return signals


def _check(d: Decision, p: dict, text: str, msg_day: date, profile: dict[str, str]) -> None:
    def fail(name: str, detail: str, action: str, lane: str | None = None) -> None:
        d.checks.append((name, False, detail))
        # Never soften an earlier, stricter outcome.
        rank = {"write": 0, "same": 1, "hold": 2, "discard": 3}
        if rank[action] > rank[d.action]:
            d.action, d.lane = action, lane
        elif action == "hold" and d.action == "hold" and d.lane is None:
            d.lane = lane

    def ok(name: str, detail: str = "") -> None:
        d.checks.append((name, True, detail))

    sig, val = d.signal, d.value

    # 1. value is one we know
    if sig in VALID:
        ok("allowed value", val) if val in VALID[sig] else fail("allowed value", f"'{val}' is not allowed", "discard")
    else:
        dv = _parse_iso(val)
        ok("allowed value", val) if dv else fail("allowed value", "no usable date", "hold", "reviewer")

    # 2. the quoted words really are in the message (blocks invented evidence)
    ev = p.get("evidence", "")
    if ev and _norm(ev) in _norm(text):
        ok("quote found in message", f"“{ev}”")
    else:
        fail("quote found in message", "the quoted words are not in the message", "discard")

    # 3. about her, not someone else
    subj = p.get("subject")
    if subj == "registered_mother":
        ok("about the registered mother")
    elif subj == "other_person":
        fail("about the registered mother", "about someone else", "discard")
    else:
        fail("about the registered mother", "unclear who this is about", "hold", "reviewer")

    # 3b. her campaign (UPE condition area). Automatic changes only on the two campaigns whose
    #     switch rule Noora has confirmed; everything else waits for a person.
    area = profile.get("condition_area")
    if sig in ("stage", "baby_dob", "due_date") and area:
        if area not in AUTO_AREAS:
            fail("campaign allows automatic update", f"condition area {area}: no automatic rule yet", "hold", "reviewer")
        elif sig == "due_date" and area == "PNC_DOB":
            fail("campaign allows automatic update", "she is on the postnatal campaign; a new due date may be a new pregnancy",
                 "hold", "reviewer")
        else:
            ok("campaign allows automatic update", area)

    # 4. model confidence (one input, never the only gate)
    conf = p.get("confidence")
    if conf == "high":
        ok("model confidence", "high")
    elif conf == "medium":
        fail("model confidence", "medium", "hold", "reviewer")
    else:
        fail("model confidence", conf or "missing", "discard")

    # 5. dates: precision, our own date maths, plausibility
    current_dob = _parse_iso(profile.get("baby_dob", "")) if sig == "baby_dob" else None
    if sig in ("baby_dob", "due_date"):
        dv = _parse_iso(val)
        phrase = p.get("date_phrase") or ""
        age = dates.age_to_dob(phrase or ev, msg_day) if sig == "baby_dob" else None
        exact = p.get("date_precision") == "exact_day" and not (age and age[1])
        if exact:
            ok("exact day")
        elif sig == "baby_dob" and current_dob and age:
            # An age ("3 months old") when a birth date is already on file. If it fits that date,
            # nothing changes. If it doesn't, the family is correcting us: the newer, honest
            # approximate date replaces the stale exact one, and the family is still asked for the day.
            # The date comes from code's own reading of the age, never from the model.
            approx, tol = age
            if abs((approx - current_dob).days) <= tol + 3:
                d.checks.append(("profile already says this", True, f"{current_dob} fits “{phrase or ev}”"))
                d.action, d.lane = "same", None
                return
            d.value, val, dv = approx.isoformat(), approx.isoformat(), approx
            d.precision = "approximate"
            ok("exact day", f"approximate (“{phrase or ev}”): replaces {current_dob}; exact day still needed")
        else:
            fail("exact day", "approximate date", "hold", "reviewer")
        ours = dates.resolve(phrase or ev, msg_day, past=(sig == "baby_dob")) if (phrase or ev) else None
        if ours is None and age and not age[1]:
            ours = age[0]  # "one day old", "10 din ka"
        if d.precision == "approximate":
            ok("date maths agree", f"code reads “{phrase or ev}” as about {dv}")
        elif ours and dv:
            if abs((ours - dv).days) <= DATE_AGREEMENT_DAYS:
                ok("date maths agree", f"code reads “{phrase or ev}” as {ours}")
            else:
                fail("date maths agree", f"model says {dv}, code reads {ours}", "hold", "reviewer")
        elif dv:
            d.checks.append(("date maths agree", True, "code could not read the phrase; relying on the model"))
        if dv and sig == "baby_dob":
            if dv > msg_day:
                fail("plausible date", "birth date is after the message", "hold", "reviewer")
            elif dv < msg_day - timedelta(days=365):
                fail("plausible date", "baby older than a year", "hold", "reviewer")
            else:
                ok("plausible date")
            edd = _parse_iso(profile.get("due_date", ""))
            if current_dob:
                pass  # correcting a birth date already on file: the old due date is history
            elif edd and not (edd - timedelta(weeks=10) <= dv <= edd + timedelta(weeks=4)):
                fail("fits her due date", f"birth {dv} is far from due date {edd}", "hold", "reviewer")
            elif edd:
                ok("fits her due date")
        if dv and sig == "due_date":
            if not (msg_day - timedelta(days=30) <= dv <= msg_day + timedelta(days=300)):
                fail("plausible date", "due date out of range", "hold", "reviewer")
            else:
                ok("plausible date")

    # 6. compare with what the profile already says
    current = profile.get(sig)
    if current:
        if current == val:
            d.checks.append(("profile already says this", True, val))
            if d.action in ("write", "hold"):
                d.action, d.lane = "same", None
        elif sig == "stage" and current == "pregnant" and val == "delivered":
            ok("no conflict with profile", "pregnant → delivered is the expected next step")
        elif sig == "stage" and current == "delivered" and val == "pregnant":
            fail("no conflict with profile", "profile says delivered", "hold", "reviewer")
        elif sig == "baby_dob":
            # The family corrects the birth date: the latest statement wins, after the judge checks it.
            ok("no conflict with profile", f"family corrects {current} → {val}; the old value is kept in history")
        elif sig == "due_date":
            a, b = _parse_iso(current), _parse_iso(val)
            if a and b and abs((a - b).days) <= DUE_DATE_SMALL_CHANGE_DAYS:
                ok("no conflict with profile", f"small change from {current}")
            else:
                fail("no conflict with profile", f"profile says {current}", "hold", "reviewer")
        else:
            fail("no conflict with profile", f"profile says {current}", "hold", "reviewer")
    else:
        ok("no conflict with profile", "field was empty")
