#!/usr/bin/env python3
"""Score the profile writer's extractions against the hidden answer key.

    python3 score.py            # reads extractions.json, writes scores.json + results.md

Each answer-key item is one of:
  correct          right value, right status (one-click ready vs held for a person vs alert)
  held_too_much    right value, but held for review when it could have been one click (safe, slower)
  unsafe_ready     right value, but marked one-click ready when a person must check it
  wrong_value      the field was found but the value is wrong
  missed           not found at all
Extra items the key doesn't expect:
  bad_write        marked ready (would be saved with one click) -> a wrong or passing fact stored as permanent
  extra            suggested for review or as an alert -> a nurse sees it but nothing is saved
"""
import json, re
from pathlib import Path

HERE = Path(__file__).parent
KEY = json.loads((HERE / "answer_key.json").read_text())
EXT = json.loads((HERE / "extractions.json").read_text())
CONV = {c["id"]: c for c in json.loads((HERE / "conversations.json").read_text())}

HELD = {"review", "nurse"}


def norm(v):
    return re.sub(r"\s+", " ", str(v or "").strip().lower())


def same_value(field, want, got):
    w, g = norm(want), norm(got)
    if field == "symptom":
        return True  # any alert about the situation counts; the wording is free
    if field == "location":
        return w.split(",")[0].strip() in g
    return w == g


def bucket(s):
    return "held" if s in HELD else s


def score():
    out, totals = {}, {}
    for cid, k in KEY.items():
        items = list(EXT.get(cid, {}).get("items", []))
        used, rows = set(), []
        for want in k["key"]:
            match = None
            for i, it in enumerate(items):
                if i in used or it.get("field") != want["field"]:
                    continue
                if want["field"] == "symptom" and it.get("status") != "alert":
                    continue
                match = i
                break
            if match is None:
                rows.append({**want, "got": None, "result": "missed"}); continue
            used.add(match)
            it = items[match]
            if not same_value(want["field"], want["value"], it.get("value")):
                res = "wrong_value"
            elif bucket(it.get("status")) == bucket(want["status"]):
                res = "correct"
            elif want["status"] == "ready" and it.get("status") in HELD:
                res = "held_too_much"
            elif it.get("status") == "ready":
                res = "unsafe_ready"
            else:
                res = "wrong_status"
            rows.append({**want, "got": it, "result": res})
        extras = []
        for i, it in enumerate(items):
            if i in used:
                continue
            extras.append({"got": it, "result": "bad_write" if it.get("status") == "ready" else "extra"})
        out[cid] = {"rows": rows, "extras": extras}
        for r in rows + extras:
            totals[r["result"]] = totals.get(r["result"], 0) + 1
    n_key = sum(len(k["key"]) for k in KEY.values())
    lasting_lost = sum(1 for c in out.values() for r in c["rows"] if r["status"] != "alert" and r["result"] in ("missed", "wrong_value"))
    stored_wrongly = sum(1 for c in out.values() for r in c["rows"] if r["result"] == "unsafe_ready") + totals.get("bad_write", 0)
    alerts_missed = sum(1 for c in out.values() for r in c["rows"] if r["status"] == "alert" and r["result"] == "missed")
    # UPE write simulation: what "Save all ready facts" would do to condition_area.
    # Rule from Noora: the switch ANC_EDD -> PNC_DOB happens only with a baby DOB, written together.
    switches, loss_wrong, switch_blocked = {}, 0, 0
    for cid, k in KEY.items():
        items = EXT.get(cid, {}).get("items", [])
        ready = {it.get("field"): it for it in items if it.get("status") == "ready"}
        delivered = ready.get("stage", {}).get("value") == "delivered"
        has_dob = "baby_dob" in ready
        is_loss = any(r["field"] == "stage" and r["value"] == "loss" for r in k["key"])
        should_switch = any(r["field"] == "stage" and r["value"] == "delivered" for r in k["key"]) and \
            any(r["field"] == "baby_dob" and r["status"] == "ready" for r in k["key"])
        would_switch = delivered and has_dob
        if is_loss and (delivered or has_dob):
            loss_wrong += 1
        if delivered and not has_dob:
            switch_blocked += 1
        switches[cid] = {"would_switch": would_switch, "should_switch": should_switch}
    switch_right = sum(1 for s in switches.values() if s["would_switch"] == s["should_switch"])
    n_loss = sum(1 for k in KEY.values() if any(r["field"] == "stage" and r["value"] == "loss" for r in k["key"]))
    summary = {"key_items": n_key, "correct": totals.get("correct", 0), "totals": totals,
               "lasting_facts_lost": lasting_lost, "stored_as_permanent_wrongly": stored_wrongly, "alerts_missed": alerts_missed,
               "loss_cases": n_loss, "loss_cases_wrongly_marked_birth": loss_wrong,
               "postnatal_switch_right": switch_right, "chats": len(KEY), "switch_waiting_for_dob": switch_blocked}
    (HERE / "scores.json").write_text(json.dumps({"summary": summary, "cases": out}, indent=1, ensure_ascii=False))
    L = ["# Profile writer: first test run\n",
         f"**{summary['correct']} of {n_key}** answer-key items exactly right (value and status).  ",
         f"**Lasting facts lost:** {lasting_lost} · **Wrongly stored as permanent:** {stored_wrongly} · **Alerts missed:** {alerts_missed}  ",
         f"**Loss cases marked as a birth:** {loss_wrong} of {n_loss} · **Postnatal switch decided right:** {switch_right} of {len(KEY)} chats · **Births held for a date of birth:** {switch_blocked}  ",
         f"All outcomes: {json.dumps(totals)}\n",
         "| Chat | Field | Expected | Got | Result |", "|---|---|---|---|---|"]
    for cid, c in out.items():
        for r in c["rows"]:
            g = r["got"]
            L.append(f"| {cid} {CONV[cid]['label']} | {r['field']} | {r['value']} ({r['status']}) | {(g or {}).get('value','—')} ({(g or {}).get('status','—')}) | {r['result']} |")
        for e in c["extras"]:
            g = e["got"]
            L.append(f"| {cid} {CONV[cid]['label']} | {g.get('field')} | — | {g.get('value')} ({g.get('status')}) | {e['result']} |")
    (HERE / "results.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:4]))


if __name__ == "__main__":
    score()
