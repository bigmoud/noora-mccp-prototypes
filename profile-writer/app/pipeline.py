"""One inbound family message, end to end.

  privacy + keyword guards → extractor proposes → write rules (code) → AI judge (rubric)
  → write / nurse / ask the family / drop → UPE write record → Copilot bio + draft reply

Nurses only see what the judge couldn't decide and clinical cases (pregnancy loss,
high-risk campaigns), inside that family's chat. Every step goes into a trace that the
dashboard can open on request.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from . import copilot as copilot_mod
from . import judge as judge_mod
from . import privacy, rules
from .config import settings
from .extractor import get_extractor
from .llm import cost
from .store import Store, now

Publish = Callable[[str, dict], None]
CLINICAL_CHECKS = {"campaign allows automatic update", "sensitive"}
# Conflicts with what's already on file are policy questions for a person, not something the
# judge may overrule (a family's 5-week due-date correction re-times every message).
POLICY_CHECKS = {"no conflict with profile", "plausible date", "fits her due date",
                 "reads like a family message"}  # instructions or data requests: a person decides, not the judge
NEEDED_TEXT = {"baby_dob": "the baby's exact date of birth", "due_date": "the exact due date the doctor gave"}


def _noop(kind: str, data: dict) -> None:
    pass


def route_of(d: rules.Decision) -> str:
    """Where a rule decision goes before the judge."""
    failed = {n for n, ok, _ in d.checks if not ok}
    if d.action in ("discard", "same", "shadow"):
        return d.action
    if d.lane == "clinical" or failed & CLINICAL_CHECKS:
        return "clinical"
    if d.signal in ("baby_dob", "due_date") and failed & {"exact day", "allowed value"}:
        return "ask_family"  # nothing to decide yet: the Copilot draft asks for the exact date
    if failed & POLICY_CHECKS:
        return "nurse"
    return "judge"


def assess(text: str, msg_day: date, profile: dict[str, str], context: list[tuple[str, str]], extractor,
           rollout_mode: str = "auto_with_audit", family_paused: bool = False, use_judge: bool = True) -> dict:
    """The decision core, with no storage: used by the live pipeline and by the eval,
    so the eval measures exactly what the demo runs."""
    clipped, _ = privacy.clip(text)
    redacted, kinds = privacy.redact(clipped)
    guards = {"emergency_words": privacy.mentions_danger(clipped), "loss_words": privacy.mentions_loss(clipped),
              "instruction_like": privacy.looks_like_injection(clipped),
              "asks_for_others_data": privacy.asks_for_others_data(clipped)}
    extraction = extractor.extract(redacted, msg_day, context)
    sensitive = extraction.sensitive_event or guards["loss_words"]
    decisions = rules.decide(extraction.signals, redacted, msg_day, profile, sensitive=sensitive,
                             family_paused=family_paused, rollout_mode=rollout_mode,
                             suspicious=guards["instruction_like"] or guards["asks_for_others_data"])
    to_judge = [d for d in decisions if route_of(d) == "judge"]
    jr = None
    if to_judge and use_judge:
        jr = judge_mod.judge(redacted, msg_day, context, profile,
                             [{"signal": d.signal, "value": d.value, "evidence": d.proposal.get("evidence", ""),
                               "precision": d.precision} for d in to_judge])
    for d in decisions:
        r = route_of(d)
        if r == "judge":
            if jr is None:
                r = "nurse"  # no judge: a person decides
            else:
                j = jr.judgements[to_judge.index(d)]
                d.judgement = {"verdict": j.verdict, "answers": j.answers, "reason": j.reason,
                               "correct_value": j.correct_value}
                r = {"confirm": "write", "reject": "discard", "unsure": "nurse"}[j.verdict]
                if r == "write" and rollout_mode == "review_first":
                    r = "nurse"
        d.route = r
    return {"redacted": redacted, "removed": kinds, "guards": guards, "extraction": extraction,
            "decisions": decisions, "sensitive": sensitive, "judge": jr}


def process_inbound(store: Store, uid: str, text: str, ts: str | None = None, wa_id: str | None = None,
                    extractor=None, publish: Publish = _noop) -> dict | None:
    ts = ts or now()
    msg_day = datetime.fromisoformat(ts).date()
    steps: list[dict] = []
    t0 = time.time()

    def step(name: str, **data) -> None:
        steps.append({"step": name, "ms": int((time.time() - t0) * 1000), **data})

    fam = store.family(uid)
    if not fam:
        return None

    # --- 1. commands the service honours without any model
    cmd = privacy.command(text)
    if cmd == "erase":
        store.erase_family(uid)
        publish("family_erased", {"uid": uid})
        return {"uid": uid, "steps": [{"step": "erase"}]}
    if cmd == "opt_out":
        store.x("UPDATE families SET consent=0 WHERE uid=?", (uid,))
        store.audit(uid, "opt_out")

    clipped, was_clipped = privacy.clip(text)
    redacted, kinds = privacy.redact(clipped)
    mid = store.add_message(uid, "in", "family", clipped, redacted, ts, wa_id)
    if mid is None:
        return None  # duplicate delivery
    publish("message", {"uid": uid, "id": mid})
    step("received", chars=len(text), clipped=was_clipped)
    step("privacy", removed=kinds)

    # --- 2. gates before any data leaves the machine
    skip = None
    fam = store.family(uid)
    if cmd == "opt_out" or not fam["consent"]:
        skip = "family opted out"
    elif store.get_setting("kill_switch", "off") == "on":
        skip = "kill switch on"
    elif store.recent_extractions(uid) >= settings.max_extractions_per_family_per_hour:
        skip = "hourly limit for this family reached"
    elif store.recent_extractions_all() >= settings.max_extractions_per_hour_total:
        skip = "hourly limit for the whole service reached"
    else:
        # Spam and floods are stopped here, before they cost a model call or a nurse's attention.
        minute_ago = (datetime.fromisoformat(ts) - timedelta(seconds=60)).isoformat()
        burst = store.inbound_since(uid, minute_ago)
        earlier = store.q("""SELECT text, ts FROM messages WHERE uid=? AND direction='in' AND id<? AND purged=0
                             ORDER BY id DESC LIMIT 1""", (uid, mid))
        if earlier and _same_text(earlier[0]["text"], clipped) and \
                datetime.fromisoformat(ts) - datetime.fromisoformat(earlier[0]["ts"]) < timedelta(minutes=10):
            skip = "repeat of the previous message"
        elif len(burst) > settings.max_messages_per_family_per_minute:
            skip = "too many messages in one minute"
            if not store.q("SELECT 1 FROM flags WHERE uid=? AND kind='flood' AND ts>=?", (uid, minute_ago)):
                store.add_flag(uid, "flood", mid)
    if skip:
        step("skipped", reason=skip)
        trace = {"uid": uid, "message_id": mid, "steps": steps, "decisions": []}
        store.add_trace(uid, mid, trace)
        store.audit(uid, "skipped", reason=skip, message_id=mid)
        publish("trace", trace)
        return trace

    # --- 3. extract → rules → judge
    ex = extractor or get_extractor()
    context = store.context_for(uid, mid)
    rollout = store.get_setting("rollout_mode", settings.rollout_mode)
    before = store.profile(uid)
    result = assess(clipped, msg_day, dict(before, condition_area=fam["condition_area"]), context, ex, rollout,
                    bool(fam["paused"]))
    extraction, decisions, jr = result["extraction"], result["decisions"], result["judge"]
    store.add_usage(extraction.tokens_in, extraction.tokens_out)
    step("guards", **result["guards"])
    g = result["guards"]
    for kind, on in (("danger", g["emergency_words"]), ("data_request", g["asks_for_others_data"]),
                     ("instructions", g["instruction_like"])):
        if on:
            store.add_flag(uid, kind, mid)
    step("extractor", extractor=extraction.extractor, sent=extraction.sent_to_model, speaker=extraction.speaker,
         sensitive_event=extraction.sensitive_event, proposals=extraction.signals, tokens_in=extraction.tokens_in,
         tokens_out=extraction.tokens_out, model_ms=extraction.ms,
         cost_usd=cost(settings.extractor_model, extraction.tokens_in, extraction.tokens_out)
         if extraction.tokens_in else 0, error=extraction.error)
    if jr is not None:
        store.add_usage(jr.tokens_in, jr.tokens_out)
        step("judge", judge=jr.judge, model_ms=jr.ms, cost_usd=jr.cost_usd, error=jr.error,
             verdicts=[{"signal": d.signal, "value": d.value, **d.judgement} for d in decisions if d.judgement])
    if extraction.error:
        store.audit(uid, "extractor_error", error=extraction.error, message_id=mid)

    if result["sensitive"]:
        store.x("UPDATE families SET paused=1 WHERE uid=?", (uid,))
        store.audit(uid, "paused_sensitive", message_id=mid)
        store.add_fact(uid, "sensitive_event", "pregnancy loss or death mentioned", "held", "clinical", mid, "",
                       extraction.speaker, "", [], "automatic updates paused for this family", extraction.extractor)

    # --- 4. persist: facts, condition area and the UPE write record in one transaction
    on_file = dict(before, condition_area=fam["condition_area"])
    written: dict[str, int] = {}
    status_of = {"write": "active", "nurse": "held", "clinical": "held", "ask_family": "needs_info",
                 "discard": "discarded", "shadow": "shadow"}
    with store.tx():
        for d in decisions:
            if d.route == "same":
                continue
            status = status_of[d.route]
            lane = {"nurse": "nurse", "clinical": "clinical"}.get(d.route)
            reason = (d.judgement.get("reason") if d.judgement else "") or nurse_reason(d, on_file)
            fid = store.add_fact(uid, d.signal, d.value, status, lane, mid, d.proposal.get("evidence", ""),
                                 extraction.speaker, d.proposal.get("confidence", ""), d.to_dict()["checks"],
                                 reason or d.reason, extraction.extractor,
                                 review_status="judge_confirmed" if status == "active" else None)
            if status == "active":
                store.supersede(uid, d.signal, fid)
                written[d.signal] = fid
                # The family has now answered it: an open nurse check on the same field is settled.
                store.x("""UPDATE facts SET status='superseded', review_status='resolved_by_family', replaced_by=?
                           WHERE uid=? AND signal=? AND status='held' AND lane='nurse'""", (fid, uid, d.signal))
            store.audit(uid, f"fact_{d.route}", fact_id=fid, signal=d.signal)
        area_before, area_after = store.recompute_condition_area(uid)
        payload = upe_payload(uid, mid, area_before, area_after, decisions, written, extraction.extractor,
                              jr.judge if jr else "", before)
        if payload:
            store.add_upe_write(uid, mid, payload)

    after = store.profile(uid)
    changed = {k: {"from": before.get(k), "to": v} for k, v in after.items() if before.get(k) != v}
    step("outcome", profile_changes=changed, condition_area={"from": area_before, "to": area_after},
         rollout=rollout, upe_write=payload)

    # --- 5. Copilot: bio for the nurse + a drafted reply (never sent automatically)
    needed = [NEEDED_TEXT[d.signal] for d in decisions if d.signal in NEEDED_TEXT
              and (d.route == "ask_family" or (d.route == "write" and d.precision == "approximate"))]
    flags = {"danger": g["emergency_words"], "loss": result["sensitive"], "writer": extraction.speaker,
             "data_request": g["asks_for_others_data"]}
    cp = refresh_copilot(store, uid, mid, needed, flags)
    step("copilot", model=cp.model, model_ms=cp.ms, cost_usd=cp.cost_usd, error=cp.error,
         output_check=cp.blocked or "passed")

    trace = {"uid": uid, "message_id": mid, "steps": steps, "decisions": [d.to_dict() for d in decisions],
             "total_ms": int((time.time() - t0) * 1000)}
    store.add_trace(uid, mid, trace)
    publish("trace", trace)
    publish("profile", {"uid": uid})
    return trace


def _same_text(a: str, b: str) -> bool:
    norm = lambda t: " ".join((t or "").casefold().split())  # noqa: E731
    return norm(a) == norm(b)


def nurse_reason(d: rules.Decision, on_file: dict) -> str:
    """Why a person is being asked, in a colleague's words (rule names stay in the trace)."""
    failed = {n: detail for n, ok, detail in d.checks if not ok}
    edd = on_file.get("due_date", "")
    nice = lambda iso: "/".join(reversed(iso.split("-"))) if iso else "-"  # noqa: E731
    if "campaign allows automatic update" in failed:
        return ("She's on the high-risk campaign, so a nurse confirms changes." if on_file.get("condition_area") == "HRPW"
                else f"She's on the {on_file.get('condition_area')} campaign, so a nurse confirms changes.")
    if "sensitive" in failed:
        return "Possible pregnancy loss in this chat: a nurse checks before anything changes."
    if "reads like a family message" in failed:
        return "This message asks for other people's information or reads like instructions. Check before saving."
    if "fits her due date" in failed:
        return f"This is far from her due date ({nice(edd)}). Please confirm with the family."
    if "no conflict with profile" in failed:
        return f"This differs from what's on file ({failed['no conflict with profile'].replace('profile says ', '')})."
    if "plausible date" in failed:
        return "This date looks unusual. Please confirm with the family."
    return ""


def is_approximate(fact: dict | None) -> bool:
    """True for a date written from an age ("3 months old"): shown with ≈ and still asked for."""
    if not fact:
        return False
    checks = fact.get("checks") or "[]"
    checks = json.loads(checks) if isinstance(checks, str) else checks
    return any(c.get("name") == "exact day" and str(c.get("detail", "")).startswith("approximate") and c.get("ok")
               for c in checks)


def refresh_copilot(store: Store, uid: str, message_id=None, still_needed=None, flags=None) -> copilot_mod.CopilotOut:
    fam = store.family(uid) or {}
    prof = store.profile(uid)
    chat = [(m["author"], m["redacted_text"]) for m in store.messages(uid, 8) if not m["purged"]]
    awaiting_check = {f["signal"] for f in store.queue(uid)}  # the family already told us: never re-ask these
    still = [x for x in (still_needed or []) if not any(NEEDED_TEXT.get(sg) == x for sg in awaiting_check)]
    dob = store.active_facts(uid).get("baby_dob")
    if ((prof.get("stage") == "delivered" and not dob or is_approximate(dob)) and "baby_dob" not in awaiting_check
            and NEEDED_TEXT["baby_dob"] not in still):
        still.append(NEEDED_TEXT["baby_dob"])
    if is_approximate(dob):
        prof = dict(prof, baby_dob_precision="approximate")
    if flags is None:  # a later refresh (after a nurse action): keep the latest message's safety flags
        last_in = store.q("SELECT id FROM messages WHERE uid=? AND direction='in' ORDER BY id DESC LIMIT 1", (uid,))
        kinds = {f["kind"] for f in store.flags(uid) if last_in and f["message_id"] == last_in[0]["id"]}
        flags = {"loss": bool(fam.get("paused")), "danger": "danger" in kinds, "data_request": "data_request" in kinds}
    cp = copilot_mod.draft(fam, prof, chat, still, flags, datetime.now(timezone.utc).date())
    if cp.blocked:
        store.add_flag(uid, "draft_blocked", message_id, ", ".join(cp.blocked))
    store.add_usage(cp.tokens_in, cp.tokens_out)
    store.set_copilot(uid, cp.bio, cp.reply, cp.language, still, message_id, cp.model)
    return cp


def refresh_copilot_async(store: Store, uid: str, publish: Publish = _noop) -> None:
    def run():
        refresh_copilot(store, uid)
        publish("profile", {"uid": uid})
    threading.Thread(target=run, daemon=True).start()


def upe_payload(uid: str, mid: int | None, area_before: str, area_after: str, decisions, written: dict,
                extractor: str, judge: str = "", before: dict | None = None) -> dict | None:
    """What this message would write to Noora's UPE, in one record. Condition area and baby DOB
    travel together. Fields UPE doesn't have yet are listed separately as proposals."""
    by_sig = {d.signal: d for d in decisions}
    fields, proposed = {}, {}
    if area_after != area_before:
        fields["condition_area"] = {"from": area_before, "to": area_after}
    for sig, upe_name in rules.UPE_FIELDS.items():
        if sig in written:
            fields[upe_name] = {"to": by_sig[sig].value}
            if (before or {}).get(sig):
                fields[upe_name]["from"] = before[sig]
            if by_sig[sig].precision == "approximate":
                fields[upe_name]["precision"] = "approximate"
    for sig in ("phone_holder", "stage"):
        if sig in written and not (sig == "stage" and "condition_area" in fields):
            proposed[sig] = by_sig[sig].value
    if not fields and not proposed:
        return None
    sources = {s: {"quote": by_sig[s].proposal.get("evidence", ""),
                   "checks_passed": [c[0] for c in by_sig[s].checks if c[1]],
                   "judge": by_sig[s].judgement.get("verdict", "")} for s in written}
    return {"user": uid, "message_id": mid, "upe_fields": fields, "proposed_new_fields": proposed,
            "source": sources, "writer": extractor, "checked_by": judge}


# ---------------------------------------------------------------- nurse actions

def review(store: Store, fact_id: int, action: str, reviewer: str = "nurse", value: str | None = None,
           note: str = "", publish: Publish = _noop) -> dict:
    """A nurse settles an item the judge couldn't decide, or a clinical case.
    confirm = write it · correct = write a different value · dismiss = don't write · revert = undo a write."""
    f = store.fact(fact_id)
    if not f:
        raise ValueError("no such item")
    action = {"approve": "confirm", "reject": "dismiss"}.get(action, action)
    reviewer = (reviewer or "nurse").strip()[:60]
    ts = now()
    uid = f["uid"]
    profile_before = store.profile(uid)

    def mark(status: str, review_status: str) -> None:
        store.x("UPDATE facts SET status=?, review_status=?, reviewed_by=?, reviewed_at=?, review_note=? WHERE id=?",
                (status, review_status, reviewer, ts, note, fact_id))

    if f["signal"] == "sensitive_event":
        mark("discarded", "acknowledged")  # a flag for people, never a profile field
    elif action == "confirm":
        mark("active", "nurse_confirmed")
        store.supersede(uid, f["signal"], fact_id)
        _golden(store, f, f["value"], reviewer)
    elif action == "dismiss":
        mark("discarded", "nurse_dismissed")
        _golden(store, f, "", reviewer)
    elif action == "revert":
        mark("reverted", "reverted")
        _golden(store, f, "", reviewer)
    elif action == "correct":
        if not value:
            raise ValueError("a corrected value is required")
        value = value.strip()
        if f["signal"] in rules.VALID and value not in rules.VALID[f["signal"]]:
            raise ValueError(f"allowed values: {', '.join(sorted(rules.VALID[f['signal']]))}")
        if f["signal"] in ("baby_dob", "due_date"):
            try:
                date.fromisoformat(value)
            except ValueError:
                raise ValueError("use a date like 2026-11-03")
        mark("superseded", "corrected")
        new_id = store.add_fact(uid, f["signal"], value, "active", None, f["message_id"], f["evidence"],
                                f["speaker"], "nurse", [], f"corrected by {reviewer}", f"nurse:{reviewer}",
                                review_status="nurse_confirmed")
        store.supersede(uid, f["signal"], new_id)
        store.x("UPDATE facts SET replaced_by=? WHERE id=?", (new_id, fact_id))
        _golden(store, f, value, reviewer)
    else:
        raise ValueError("unknown action")
    if not store.q("SELECT 1 FROM facts WHERE uid=? AND status='held' AND lane='clinical'", (uid,)):
        store.x("UPDATE families SET paused=0 WHERE uid=?", (uid,))
    store.audit(uid, f"nurse_{action}", fact_id=fact_id)
    area_before, area_after = store.recompute_condition_area(uid)
    profile_after = store.profile(uid)
    fields = {"condition_area": {"from": area_before, "to": area_after}} if area_before != area_after else {}
    for sig, upe_name in rules.UPE_FIELDS.items():
        if profile_before.get(sig) != profile_after.get(sig):
            fields[upe_name] = {"from": profile_before.get(sig), "to": profile_after.get(sig)}
    if fields:
        store.add_upe_write(uid, f["message_id"], {"user": uid, "upe_fields": fields, "writer": f"nurse:{reviewer}",
                                                   "action": action, "fact_id": fact_id})
    publish("profile", {"uid": uid})
    if profile_before != profile_after:
        refresh_copilot_async(store, uid, publish)
    return store.fact(fact_id)


def _golden(store: Store, f: dict, correct_value: str, reviewer: str) -> None:
    """Every nurse decision on an item the judge couldn't settle becomes a candidate test
    case. It holds message text, so it stays pending until confirmed de-identified."""
    msg = store.q("SELECT redacted_text, ts FROM messages WHERE id=?", (f["message_id"],))
    if not msg:
        return
    store.x("""INSERT INTO golden_pending (created_at, fact_id, uid, message_text, msg_day, signal, wrong_value,
               correct_value, reviewer) VALUES (?,?,?,?,?,?,?,?,?)""",
            (now(), f["id"], f["uid"], msg[0]["redacted_text"], msg[0]["ts"][:10], f["signal"], f["value"],
             correct_value, reviewer))
