"""What the nurse's screen shows: the chat list, one chat, and the Copilot panel.
Field names and order follow the Copilot "User Profile" panel MSEs use today."""
from __future__ import annotations

from datetime import date, datetime, timezone

from . import privacy
from .config import settings
from .copilot import DATA_REQUEST_REPLY
from .pipeline import is_approximate
from .store import Store

LABEL = {"phone_holder": "Who holds the phone", "stage": "Stage", "baby_dob": "Baby DOB", "due_date": "Expected Due Date",
         "sensitive_event": "Possible pregnancy loss"}
FLAG_TEXT = {
    "danger": "Possible danger sign in this message. Please reply first: hospital today or 108.",
    "data_request": "Asked for other people's information or how the service works inside. Nothing was shared; "
                    "the suggested reply is a fixed one and any profile change waits for you.",
    "instructions": "This message reads like instructions to the system. Any profile change waits for you.",
    "flood": "Many messages in one minute: automatic reading paused for this chat for a minute.",
    "draft_blocked": "The suggested reply was replaced because it failed a safety check",
}
ALERT_LABEL = {"danger": "Urgent", "data_request": "Alert"}
STICKER_MARK = "[sticker: let me stop you right there]"
HOLDER = {"mother": "Mother", "husband": "Husband", "mother_in_law": "Mother-in-law", "other_family": "Other family"}


def _d(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        return date.fromisoformat(iso[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _pretty(signal: str, value: str) -> str:
    if signal in ("baby_dob", "due_date"):
        return _d(value)
    if signal == "phone_holder":
        return HOLDER.get(value, value)
    return value.capitalize() if value else "-"


def _age(days: int) -> str:
    if days < 60:
        return f"{days} day{'s' if days != 1 else ''}"
    months = days // 30
    return f"{months} months" if months < 24 else f"{months // 12} years {months % 12} months"


def _source(f: dict | None) -> dict:
    if not f:
        return {}
    ev = f.get("evidence") or ""
    if ev.startswith("("):
        return {"from": ev.strip("()")}
    by = "nurse" if (f.get("extractor") or "").startswith("nurse") else "chat"
    return {"from": by, "quote": ev, "at": (f.get("created_at") or "")[:16]}


def families(store: Store, processing: set[str]) -> list[dict]:
    out = []
    for f in store.families():
        last = store.q("SELECT text, ts, direction FROM messages WHERE uid=? ORDER BY id DESC LIMIT 1", (f["uid"],))
        unread = store.q("SELECT COUNT(*) n FROM messages WHERE uid=? AND direction='in' AND id>?",
                         (f["uid"], f["last_read_id"] or 0))[0]["n"]
        needs = store.queue(f["uid"])
        phone = store.contact(f["uid"])
        last_out = store.q("SELECT MAX(ts) t FROM messages WHERE uid=? AND direction='out' AND author<>'auto'",
                           (f["uid"],))[0]["t"] or ""
        open_kinds = {x["kind"] for x in store.flags(f["uid"]) if x["ts"] > last_out}
        alert = next((ALERT_LABEL[k] for k in ("danger", "data_request") if k in open_kinds), None)
        out.append({"uid": f["uid"], "name": f["name"] or f["label"], "condition_area": f["condition_area"],
                    "last": last[0]["text"] if last else "", "last_ts": last[0]["ts"] if last else f["created_at"],
                    "last_out": bool(last and last[0]["direction"] == "out"), "unread": unread,
                    "needs": len(needs), "clinical": any(n["lane"] == "clinical" for n in needs), "alert": alert,
                    "processing": f["uid"] in processing,
                    "phone": privacy.mask_phone(phone) if phone else "+91 ••••• " + f["uid"][-5:].upper()})
    return sorted(out, key=lambda x: x["last_ts"] or "", reverse=True)


def chat(store: Store, uid: str, processing: set[str]) -> dict | None:
    fam = store.family(uid)
    if not fam:
        return None
    today = datetime.now(timezone.utc).date()
    facts = store.active_facts(uid)
    area = fam["condition_area"]
    edd, dob, holder = facts.get("due_date"), facts.get("baby_dob"), facts.get("phone_holder")

    health = [{"field": "Condition Area", "value": area.split("_")[0].lower() if area else "-", "raw": area}]
    health.append({"field": "Mother's age", "value": "-"})
    if edd and area != "PNC_DOB":
        days = (date.fromisoformat(edd["value"]) - today).days
        weeks = 40 - days / 7
        health += [{"field": "Expected Due Date", "value": _d(edd["value"]), **_source(edd)},
                   {"field": "Time until due", "value": f"{days} days" if days >= 0 else f"{-days} days past due"},
                   {"field": "Trimester", "value": "1st" if weeks < 14 else "2nd" if weeks < 28 else "3rd"}]
    else:
        health += [{"field": "Expected Due Date", "value": "-"}, {"field": "Time until due", "value": "-"},
                   {"field": "Trimester", "value": "-"}]
    if dob:
        approx = is_approximate(dob)
        age = _age((today - date.fromisoformat(dob["value"])).days)
        health += [{"field": "Baby DOB", "value": ("≈ " if approx else "") + _d(dob["value"]), **_source(dob),
                    **({"note": "approximate: exact date asked"} if approx else {})},
                   {"field": "Baby age", "value": ("about " if approx else "") + age}]
    else:
        health += [{"field": "Baby DOB", "value": "-"}, {"field": "Baby age", "value": "-"}]
    health.append({"field": "Who holds the phone", "value": HOLDER.get(holder["value"], "-") if holder else "-",
                   **_source(holder)})
    health += [{"field": "High risk", "value": fam.get("high_risk") or "-"}, {"field": "High risk details", "value": "-"}]

    details = [("State", fam.get("state")), ("Language", fam.get("language")),
               ("Onboarding method", fam.get("onboarding_method")), ("WA onboarding date", _d(fam.get("onboarding_date"))),
               ("Consent status", "Yes" if fam.get("consent") else "No"),
               ("Last updated", _last_updated(store, uid)), ("Noora program", fam.get("noora_program"))]

    needs = []
    for n in store.queue(uid):
        msg = store.q("SELECT text, ts FROM messages WHERE id=?", (n["message_id"],)) if n["message_id"] else []
        needs.append({"id": n["id"], "signal": n["signal"], "label": LABEL.get(n["signal"], n["signal"]),
                      "value": n["value"], "pretty": _pretty(n["signal"], n["value"]), "quote": n["evidence"] or "",
                      "message": msg[0]["text"] if msg else "", "reason": n["reason"] or "", "lane": n["lane"]})

    notices = []
    for w in store.upe_writes(uid, 20):
        p = w["payload"]
        bits = []
        f = p.get("upe_fields", {})
        if "baby_dob" in f:
            bits.append(f"Baby DOB {'≈ ' if f['baby_dob'].get('precision') == 'approximate' else ''}"
                        f"{_d(f['baby_dob'].get('to'))}"
                        + (f" (was {_d(f['baby_dob']['from'])})" if f['baby_dob'].get('from') else ""))
        if "expected_due_date" in f:
            bits.append(f"Due date {_d(f['expected_due_date'].get('to'))}")
        if "condition_area" in f:
            bits.append(f"Condition area {f['condition_area']['from']} → {f['condition_area']['to']}")
        for k, v in (p.get("proposed_new_fields") or {}).items():
            bits.append(f"{LABEL.get(k, k)}: {_pretty(k, v)}")
        if bits:
            who = "by nurse" if str(p.get("writer", "")).startswith("nurse") else ""
            notices.append({"ts": w["ts"], "text": "Profile updated" + (f" {who}" if who else "") + " · " + " · ".join(bits)})

    for fl in store.flags(uid):
        text = FLAG_TEXT.get(fl["kind"], fl["kind"])
        if fl["kind"] == "draft_blocked" and fl["detail"]:
            text += f" ({fl['detail']})."
        notices.append({"ts": fl["ts"], "text": text, "alert": fl["kind"] in ALERT_LABEL})

    cp = store.copilot(uid) or {}
    traces = store.traces(uid, 1)
    phone = store.contact(uid)
    return {"uid": uid, "name": fam["name"] or fam["label"], "condition_area": area, "paused": bool(fam["paused"]),
            "phone": privacy.mask_phone(phone) if phone else "+91 ••••• " + uid[-5:].upper(),
            "live": bool(phone), "messages": [{"id": m["id"], "dir": m["direction"], "text": m["text"], "ts": m["ts"],
                                               "auto": m["author"] == "auto", "sticker": m["text"] == STICKER_MARK}
                                              for m in store.messages(uid, 80)],
            "notices": notices, "bio": cp.get("bio") or "", "draft": cp.get("reply") or "",
            "draft_sticker": bool(settings.demo_sticker and cp.get("reply") == DATA_REQUEST_REPLY),
            "draft_language": cp.get("language") or "", "still_needed": cp.get("still_needed") or [],
            "health": health, "details": [{"field": k, "value": v or "-"} for k, v in details], "needs": needs,
            "trace": traces[0]["trace"] if traces else None, "processing": uid in processing}


def _last_updated(store: Store, uid: str) -> str:
    rows = store.q("SELECT MAX(created_at) t FROM facts WHERE uid=? AND status='active'", (uid,))
    t = rows[0]["t"] if rows else None
    if not t:
        return "-"
    dt = datetime.fromisoformat(t)
    return dt.strftime("%d/%m/%Y %H:%M")
