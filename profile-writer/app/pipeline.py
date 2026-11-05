"""One inbound family message, end to end. Every step is recorded in a trace so the
dashboard can show, live, what was received, what left the machine, what the model
proposed, which rules fired, and what changed on the profile.
"""
from __future__ import annotations

import time
from datetime import date, datetime, timezone
from typing import Callable

from . import privacy, rules
from .config import settings
from .extractor import get_extractor
from .store import Store, now

Publish = Callable[[str, dict], None]


def _noop(kind: str, data: dict) -> None:
    pass


def _cost(tin: int, tout: int) -> float | None:
    if settings.price_in_per_mtok is None or settings.price_out_per_mtok is None:
        return None
    return tin / 1e6 * settings.price_in_per_mtok + tout / 1e6 * settings.price_out_per_mtok


def assess(text: str, msg_day: date, profile: dict[str, str], context: list[tuple[str, str]], extractor,
           rollout_mode: str = "auto_with_audit", family_paused: bool = False) -> dict:
    """The decision core, with no storage: used by the live pipeline and by the eval,
    so the eval measures exactly what the demo runs."""
    clipped, _ = privacy.clip(text)
    redacted, kinds = privacy.redact(clipped)
    guards = {"emergency_words": privacy.mentions_danger(clipped), "loss_words": privacy.mentions_loss(clipped),
              "instruction_like": privacy.looks_like_injection(clipped)}
    extraction = extractor.extract(redacted, msg_day, context)
    sensitive = extraction.sensitive_event or guards["loss_words"]
    decisions = rules.decide(extraction.signals, redacted, msg_day, profile, sensitive=sensitive,
                             family_paused=family_paused, rollout_mode=rollout_mode,
                             suspicious=guards["instruction_like"])
    return {"redacted": redacted, "removed": kinds, "guards": guards, "extraction": extraction,
            "decisions": decisions, "sensitive": sensitive}


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

    # --- 1. commands that the service must honour without any model
    cmd = privacy.command(text)
    if cmd == "erase":
        store.erase_family(uid)
        publish("family_erased", {"uid": uid})
        return {"uid": uid, "steps": [{"step": "erase", "detail": "family asked to delete their data: all records removed"}]}
    if cmd == "opt_out":
        store.x("UPDATE families SET consent=0 WHERE uid=?", (uid,))
        store.audit(uid, "opt_out")

    clipped, was_clipped = privacy.clip(text)
    redacted, kinds = privacy.redact(clipped)
    mid = store.add_message(uid, "in", "family", clipped, redacted, ts, wa_id)
    if mid is None:
        return None  # duplicate delivery
    publish("message", {"uid": uid, "id": mid, "direction": "in", "author": "family", "text": clipped, "ts": ts})
    step("received", chars=len(text), clipped=was_clipped)
    step("privacy", removed=kinds, note="phone number replaced by pseudonym " + uid + "; profile name from WhatsApp discarded")

    danger = privacy.mentions_danger(clipped)
    loss_kw = privacy.mentions_loss(clipped)
    suspicious = privacy.looks_like_injection(clipped)
    step("guards", emergency_words=danger, loss_words=loss_kw, instruction_like=suspicious,
         note=("Emergency words: Noora's existing triage handles this; this tool does not reply." if danger else ""))

    # --- 2. gates before any data leaves the machine
    skip = None
    fam = store.family(uid)
    if cmd == "opt_out" or not fam["consent"]:
        skip = "family opted out: not processed"
    elif store.get_setting("kill_switch", "off") == "on":
        skip = "kill switch on: extraction paused"
    elif settings.extractor == "claude" and (store.usage_today()["tokens_in"] + store.usage_today()["tokens_out"]) >= settings.daily_token_cap:
        skip = "daily token cap reached: extraction paused"
    elif store.recent_extractions(uid) >= settings.max_extractions_per_family_per_hour:
        skip = "hourly limit for this family reached"
    if skip:
        step("skipped", reason=skip)
        trace = {"uid": uid, "message_id": mid, "steps": steps, "decisions": []}
        store.add_trace(uid, mid, trace)
        store.audit(uid, "skipped", reason=skip, message_id=mid)
        publish("trace", trace)
        return trace

    # --- 3 + 4. extract (only redacted text and the message date leave the machine), then write rules
    ex = extractor or get_extractor()
    context = store.context_for(uid, mid)
    rollout = store.get_setting("rollout_mode", settings.rollout_mode)
    before = store.profile(uid)
    result = assess(clipped, msg_day, dict(before, condition_area=fam["condition_area"]), context, ex, rollout,
                    bool(fam["paused"]))
    extraction, decisions = result["extraction"], result["decisions"]
    if extraction.tokens_in or extraction.tokens_out:
        store.add_usage(extraction.tokens_in, extraction.tokens_out)
    step("extractor", extractor=extraction.extractor, sent=extraction.sent_to_model,
         speaker=extraction.speaker, sensitive_event=extraction.sensitive_event, proposals=extraction.signals,
         tokens_in=extraction.tokens_in, tokens_out=extraction.tokens_out, model_ms=extraction.ms,
         cost_usd=_cost(extraction.tokens_in, extraction.tokens_out), error=extraction.error)
    if extraction.error:
        store.audit(uid, "extractor_error", error=extraction.error, message_id=mid)

    if result["sensitive"]:
        store.x("UPDATE families SET paused=1 WHERE uid=?", (uid,))
        store.audit(uid, "paused_sensitive", message_id=mid)
        # Always leave the clinical team something to act on, even when nothing was extracted.
        store.add_fact(uid, "sensitive_event", "loss or death mentioned", "held", "clinical", mid, "", extraction.speaker,
                       "", [{"name": "keyword guard" if loss_kw else "model flag", "ok": False,
                             "detail": "pregnancy loss or death mentioned"}],
                       "automatic updates paused for this family", extraction.extractor)

    # --- 5. persist: facts, condition area and the UPE write record in one transaction
    written: dict[str, int] = {}
    with store.tx():
        for d in decisions:
            if d.action == "same":
                continue
            status = {"write": "active", "hold": "held", "discard": "discarded", "shadow": "shadow"}[d.action]
            fid = store.add_fact(uid, d.signal, d.value, status, d.lane, mid, d.proposal.get("evidence", ""),
                                 extraction.speaker, d.proposal.get("confidence", ""),
                                 [c for c in d.to_dict()["checks"]], d.reason, extraction.extractor,
                                 review_status="pending" if status == "active" else None)
            if status == "active":
                store.supersede(uid, d.signal, fid)
                written[d.signal] = fid
            store.audit(uid, f"fact_{d.action}", fact_id=fid, signal=d.signal, lane=d.lane)
        area_before, area_after = store.recompute_condition_area(uid)
        payload = upe_payload(uid, mid, area_before, area_after, decisions, written, extraction.extractor)
        if payload:
            store.add_upe_write(uid, mid, payload)

    after = store.profile(uid)
    changed = {k: {"from": before.get(k), "to": v} for k, v in after.items() if before.get(k) != v}
    step("outcome", profile_changes=changed, condition_area={"from": area_before, "to": area_after},
         rollout=rollout, upe_write=payload)

    trace = {"uid": uid, "message_id": mid, "steps": steps, "decisions": [d.to_dict() for d in decisions],
             "total_ms": int((time.time() - t0) * 1000)}
    store.add_trace(uid, mid, trace)
    publish("trace", trace)
    publish("profile", {"uid": uid})
    return trace


def upe_payload(uid: str, mid: int | None, area_before: str, area_after: str, decisions, written: dict,
                extractor: str) -> dict | None:
    """What this message would write to Noora's UPE, in one record. Condition area and baby DOB
    travel together. Fields UPE doesn't have yet (who holds the phone, 'delivered' without a
    DOB) are listed separately as proposals, not written to UPE."""
    by_sig = {d.signal: d for d in decisions}
    fields, proposed = {}, {}
    if area_after != area_before:
        fields["condition_area"] = {"from": area_before, "to": area_after}
    for sig, upe_name in rules.UPE_FIELDS.items():
        if sig in written:
            fields[upe_name] = {"to": by_sig[sig].value}
    for sig in ("phone_holder", "stage"):
        if sig in written and not (sig == "stage" and "condition_area" in fields):
            proposed[sig] = by_sig[sig].value
    if not fields and not proposed:
        return None
    sources = {s: {"quote": by_sig[s].proposal.get("evidence", ""), "confidence": by_sig[s].proposal.get("confidence"),
                   "checks_passed": [c[0] for c in by_sig[s].checks if c[1]]}
               for s in written}
    return {"user": uid, "message_id": mid, "upe_fields": fields, "proposed_new_fields": proposed,
            "source": sources, "writer": extractor, "review": "pending (non-clinical reviewer, after the write)"}


# ---------------------------------------------------------------- reviewer actions

def review(store: Store, fact_id: int, action: str, reviewer: str, value: str | None = None,
           note: str = "", publish: Publish = _noop) -> dict:
    f = store.fact(fact_id)
    if not f:
        raise ValueError("no such fact")
    if not reviewer.strip():
        raise ValueError("reviewer name is required")
    if f["lane"] == "clinical" and not reviewer.lower().startswith("clinical:"):
        # Non-clinical reviewers cannot clear sensitive cases. (Real system: role-based access.)
        raise PermissionError("this item is in the clinical lane; a clinical reviewer must handle it")
    ts = now()
    uid = f["uid"]
    profile_before = store.profile(uid)

    def mark(status: str, review_status: str) -> None:
        store.x("""UPDATE facts SET status=?, review_status=?, reviewed_by=?, reviewed_at=?, review_note=? WHERE id=?""",
                (status, review_status, reviewer, ts, note, fact_id))

    if f["signal"] == "sensitive_event":
        mark("discarded", "acknowledged")  # a flag for people, never a profile field
    elif action == "approve":
        mark("active", "approved")
        store.supersede(uid, f["signal"], fact_id)
    elif action == "reject":  # held item: right not to write
        mark("discarded", "rejected")
    elif action == "revert":  # written item was wrong and should not be there
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
        new_id = store.add_fact(uid, f["signal"], value.strip(), "active", None, f["message_id"], f["evidence"],
                                f["speaker"], "reviewer", [], f"corrected by {reviewer}", f"reviewer:{reviewer}",
                                review_status="approved")
        store.supersede(uid, f["signal"], new_id)
        store.x("UPDATE facts SET replaced_by=? WHERE id=?", (new_id, fact_id))
        _golden(store, f, value.strip(), reviewer)
    else:
        raise ValueError("unknown action")
    if f["lane"] == "clinical":
        if not store.q("SELECT 1 FROM facts WHERE uid=? AND status='held' AND lane='clinical'", (uid,)):
            store.x("UPDATE families SET paused=0 WHERE uid=?", (uid,))
    store.audit(uid, f"review_{action}", fact_id=fact_id, reviewer=reviewer)
    area_before, area_after = store.recompute_condition_area(uid)
    # A reviewer's change to a UPE field is itself a UPE write, recorded the same way.
    profile_after = store.profile(uid)
    fields = {"condition_area": {"from": area_before, "to": area_after}} if area_before != area_after else {}
    for sig, upe_name in rules.UPE_FIELDS.items():
        if profile_before.get(sig) != profile_after.get(sig):
            fields[upe_name] = {"from": profile_before.get(sig), "to": profile_after.get(sig)}
    if fields:
        store.add_upe_write(uid, f["message_id"], {"user": uid, "upe_fields": fields, "writer": f"reviewer:{reviewer}",
                                                   "action": action, "fact_id": fact_id})
    publish("profile", {"uid": uid})
    publish("queue", {})
    return store.fact(fact_id)


def _golden(store: Store, f: dict, correct_value: str, reviewer: str) -> None:
    """Reviewer corrections become candidate test cases. They hold message text, so they
    stay 'pending' until someone confirms the text is de-identified (or synthetic)."""
    msg = store.q("SELECT redacted_text, ts FROM messages WHERE id=?", (f["message_id"],))
    if not msg:
        return
    store.x("""INSERT INTO golden_pending (created_at, fact_id, uid, message_text, msg_day, signal, wrong_value,
               correct_value, reviewer) VALUES (?,?,?,?,?,?,?,?,?)""",
            (now(), f["id"], f["uid"], msg[0]["redacted_text"], msg[0]["ts"][:10], f["signal"], f["value"],
             correct_value, reviewer))
