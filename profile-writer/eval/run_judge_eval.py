"""Calibrate the AI judge against the golden set before trusting it with writes.

For every case, the judge sees a mix of proposals it has never seen labelled:
  correct    the answer-key value                          → should confirm (or unsure)
  corrupted  the right field, a wrong value (date +7 days,  → must NOT confirm
             another phone holder, the opposite stage)
  tempting   a write that looks plausible but the key says  → must NOT confirm
             shouldn't happen (a sister's birth, a loss case,
             a borrowed phone, a vague date made exact)

    python3 -m eval.run_judge_eval            # ~$0.60 with Sonnet 5.5
Writes eval/out/judge_results.md and eval/out/judge_runs.jsonl.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from app import judge, privacy
from app.config import settings

HERE = Path(__file__).parent
OTHER_HOLDER = {"husband": "mother_in_law", "mother_in_law": "husband", "mother": "husband", "other_family": "mother"}


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def corrupt(signal: str, value: str) -> str:
    if signal in ("baby_dob", "due_date"):
        return (date.fromisoformat(value) + timedelta(days=7)).isoformat()
    if signal == "phone_holder":
        return OTHER_HOLDER.get(value, "husband")
    return "pregnant" if value == "delivered" else "delivered"


def tempting(case: dict, key: dict) -> list[dict]:
    """Plausible writes the answer key says must not happen."""
    text, tags, day = case["messages"][-1]["text"], set(key.get("tags", [])), date.fromisoformat(case["msg_day"])
    out = []
    if tags & {"other_person", "loss", "loss_vs_delivery"} and not key.get("writes"):
        out.append({"signal": "stage", "value": "delivered", "evidence": text[:80]})
        out.append({"signal": "baby_dob", "value": (day - timedelta(days=1)).isoformat(), "evidence": text[:80]})
    if "temporary" in tags:
        out.append({"signal": "phone_holder", "value": "mother_in_law", "evidence": text[:60]})
    if "vague_date" in tags and "baby_dob" not in key.get("writes", {}):
        out.append({"signal": "baby_dob", "value": (day - timedelta(days=14)).isoformat(), "evidence": text[:60]})
    if "vague_date" in tags and "due_date" not in key.get("writes", {}) and case["profile"].get("stage") != "delivered":
        out.append({"signal": "due_date", "value": (day + timedelta(days=60)).isoformat(), "evidence": text[:60]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=settings.judge_model)
    ap.add_argument("--golden", default=str(HERE / "golden"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    gdir = Path(args.golden)
    cases = load(gdir / "cases.jsonl")
    keys = {k["id"]: k for k in load(gdir / "answer_key.jsonl")}
    if args.limit:
        cases = cases[: args.limit]

    rows, spend = [], 0.0
    for c in cases:
        k = keys[c["id"]]
        props = []
        for sig, val in k.get("writes", {}).items():
            props.append(({"signal": sig, "value": val, "evidence": c["messages"][-1]["text"][:80]}, "correct"))
            props.append(({"signal": sig, "value": corrupt(sig, val), "evidence": c["messages"][-1]["text"][:80]},
                          "corrupted"))
        props += [(p, "tempting") for p in tempting(c, k)]
        if not props:
            continue
        msgs = c["messages"]
        context = [(m["from"], privacy.redact(m["text"])[0]) for m in msgs[:-1]]
        profile = dict(c["profile"])
        r = judge.judge(privacy.redact(msgs[-1]["text"])[0], date.fromisoformat(c["msg_day"]), context, profile,
                        [p for p, _ in props], model=args.model)
        spend += r.cost_usd
        for (p, kind), j in zip(props, r.judgements):
            rows.append({"id": c["id"], "kind": kind, **p, "verdict": j.verdict, "reason": j.reason,
                         "answers": j.answers, "tags": k.get("tags", []), "error": r.error})
        print(f"{c['id']}: " + " ".join(f"{kind[0]}:{j.verdict[0]}" for (_, kind), j in zip(props, r.judgements)),
              flush=True)

    out = HERE / "out"
    out.mkdir(exist_ok=True)
    (out / "judge_runs.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                                          encoding="utf-8")
    report = render(rows, args.model, spend)
    (out / "judge_results.md").write_text(report, encoding="utf-8")
    print(report)


def render(rows: list[dict], model: str, spend: float) -> str:
    by = {kind: Counter(r["verdict"] for r in rows if r["kind"] == kind) for kind in ("correct", "corrupted", "tempting")}
    good, bad = by["correct"], by["corrupted"] + by["tempting"]
    n_good, n_bad = sum(good.values()), sum(bad.values())
    false_confirms = [r for r in rows if r["kind"] != "correct" and r["verdict"] == "confirm"]
    lost = [r for r in rows if r["kind"] == "correct" and r["verdict"] == "reject"]
    pct = lambda a, b: f"{a / b:.0%}" if b else "n/a"
    L = [f"# Judge calibration: {model}", "", f"{len(rows)} proposals from the golden set · cost ${spend:.2f}", "",
         "## Headline", "",
         f"- **Wrong proposals confirmed (the dangerous number): {len(false_confirms)}/{n_bad}** ({pct(len(false_confirms), n_bad)})",
         f"- Correct proposals confirmed (automation rate): {good['confirm']}/{n_good} ({pct(good['confirm'], n_good)})",
         f"- Sent to a nurse: {good['unsure'] + bad['unsure']}/{len(rows)} ({pct(good['unsure'] + bad['unsure'], len(rows))})",
         f"- Correct proposals rejected (facts lost): {len(lost)}/{n_good}", "",
         "| Proposal | confirm | unsure → nurse | reject |", "|---|---|---|---|"]
    for kind in ("correct", "corrupted", "tempting"):
        cnt = by[kind]
        L.append(f"| {kind} | {cnt['confirm']} | {cnt['unsure']} | {cnt['reject']} |")
    L += ["", "## Wrong proposals the judge confirmed", ""]
    L += [f"- {r['id']} · {r['kind']} · {r['signal']}={r['value']} · “{r['reason']}”" for r in false_confirms] or ["None."]
    L += ["", "## Correct proposals the judge rejected", ""]
    L += [f"- {r['id']} · {r['signal']}={r['value']} · “{r['reason']}”" for r in lost] or ["None."]
    unsure_good = [r for r in rows if r["kind"] == "correct" and r["verdict"] == "unsure"]
    L += ["", "## Correct proposals sent to a nurse (nurse time the judge didn't save)", ""]
    L += [f"- {r['id']} · {r['signal']}={r['value']} · “{r['reason']}”" for r in unsure_good] or ["None."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
