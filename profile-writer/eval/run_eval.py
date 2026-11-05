"""Run the golden set through the same decision core the live demo uses.

    python3 -m eval.run_eval                       # offline keyword baseline
    python3 -m eval.run_eval --extractor claude    # needs ANTHROPIC_API_KEY
    python3 -m eval.run_eval --split holdout       # the held-out 20%: run rarely

Scores what actually reaches the profile (writes), not what the model proposed.
Writes eval/out/runs.jsonl (one record per case) and eval/out/results.md.
The answer key is read only here, after extraction; it is never shown to the model.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from app import privacy
from app.config import settings
from app.extractor import PROMPT_VERSION, SIGNALS, BaselineExtractor, ClaudeExtractor
from app.pipeline import assess

HERE = Path(__file__).parent
TARGET_P, TARGET_R = 0.90, 0.80


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extractor", choices=["baseline", "claude"], default="baseline")
    ap.add_argument("--model", default=None)
    ap.add_argument("--split", choices=["dev", "holdout", "dev2", "all"], default="dev")
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--golden", default=str(HERE / "golden"),
                    help="folder with cases.jsonl + answer_key.jsonl (eval/golden/noora/ for Noora's samples: git-ignored)")
    args = ap.parse_args()

    gdir = Path(args.golden)
    cases = [c for c in load(gdir / "cases.jsonl") if args.split == "all" or c["split"] == args.split]
    key = {k["id"]: k for k in load(gdir / "answer_key.jsonl")}
    ex = ClaudeExtractor(args.model) if args.extractor == "claude" else BaselineExtractor()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    runs, tally = [], defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for c in cases:
        k = key[c["id"]]
        msgs = c["messages"]
        context = [(m["from"], privacy.redact(m["text"])[0]) for m in msgs[:-1]]
        t0 = time.time()
        profile = dict(c["profile"])
        # UPE campaign: condition area + a date. Default from stage when a case doesn't say.
        profile.setdefault("condition_area", "PNC_DOB" if profile.get("stage") == "delivered" else "ANC_EDD")
        r = assess(msgs[-1]["text"], date.fromisoformat(c["msg_day"]), profile, context, ex)
        ms = int((time.time() - t0) * 1000)
        writes = {d.signal: d.value for d in r["decisions"] if d.route == "write"}
        holds = sorted({d.signal for d in r["decisions"] if d.route in ("nurse", "clinical", "ask_family")})
        nurse = sorted({d.signal for d in r["decisions"] if d.route in ("nurse", "clinical")})
        expected = k.get("writes", {})

        misses = []
        for s in SIGNALS:
            got, want = writes.get(s), expected.get(s)
            if got is not None and got == want:
                tally[s]["tp"] += 1
            if got is not None and got != want:
                tally[s]["fp"] += 1
                misses.append({"kind": "wrong write", "signal": s, "got": got, "want": want})
            if want is not None and got != want:
                tally[s]["fn"] += 1
                if got is None:
                    misses.append({"kind": "missed", "signal": s, "got": None, "want": want})
        for s in k.get("holds", []):
            if s not in holds and s not in writes:
                misses.append({"kind": "expected hold, got nothing", "signal": s, "got": None, "want": "hold"})
        if k.get("sensitive") and not r["sensitive"]:
            misses.append({"kind": "sensitive not flagged", "signal": "-", "got": "not flagged", "want": "flagged"})
        if not k.get("sensitive") and r["sensitive"] and "loss_vs_delivery" in k.get("tags", []):
            misses.append({"kind": "false loss alarm", "signal": "-", "got": "flagged", "want": "not flagged"})

        e = r["extraction"]
        runs.append({
            "id": c["id"],
            "input": {"msg_day": c["msg_day"], "profile": c["profile"], "messages": msgs},
            "variables": {"extractor": e.extractor, "split": c["split"], "tags": k.get("tags", [])},
            "trace": {"sent_to_model": e.sent_to_model, "removed": r["removed"], "guards": r["guards"],
                      "proposals": e.signals, "decisions": [d.to_dict() for d in r["decisions"]], "error": e.error},
            "output": {"writes": writes, "holds": holds, "nurse": nurse, "sensitive": r["sensitive"]},
            "expected": {"writes": expected, "holds": k.get("holds", []), "sensitive": bool(k.get("sensitive")),
                         "speaker": k.get("speaker")},
            "speaker": e.speaker,
            "pass": not misses, "misses": misses,
            "tokens": {"in": e.tokens_in, "out": e.tokens_out}, "ms": ms,
            "judge_cost": r["judge"].cost_usd if r["judge"] else 0.0,
        })

    (out_dir / "runs.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in runs) + "\n", encoding="utf-8")
    report = render(runs, tally, args)
    (out_dir / "results.md").write_text(report, encoding="utf-8")
    print(report)


def pr(t: dict) -> tuple[float | None, float | None]:
    p = t["tp"] / (t["tp"] + t["fp"]) if (t["tp"] + t["fp"]) else None
    r = t["tp"] / (t["tp"] + t["fn"]) if (t["tp"] + t["fn"]) else None
    return p, r


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def render(runs: list[dict], tally: dict, args) -> str:
    total = {"tp": sum(t["tp"] for t in tally.values()), "fp": sum(t["fp"] for t in tally.values()),
             "fn": sum(t["fn"] for t in tally.values())}
    P, R = pr(total)
    passed = sum(r["pass"] for r in runs)
    wrong = [(r, m) for r in runs for m in r["misses"] if m["kind"] == "wrong write"]
    missed = [(r, m) for r in runs for m in r["misses"] if m["kind"] != "wrong write"]
    tin = sum(r["tokens"]["in"] for r in runs)
    tout = sum(r["tokens"]["out"] for r in runs)
    n = len(runs) or 1
    cost = None
    if settings.price_in_per_mtok is not None and settings.price_out_per_mtok is not None:
        cost = (tin / 1e6 * settings.price_in_per_mtok + tout / 1e6 * settings.price_out_per_mtok) / n

    L = [f"# Eval results: {runs[0]['variables']['extractor'] if runs else args.extractor}",
         "", f"Run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · split: **{args.split}** · {len(runs)} cases · prompt {PROMPT_VERSION}",
         "", "Scored on what reaches the profile (writes). Held items count as not written.", "",
         "## Headline", "",
         f"- **Precision {pct(P)}** (target ≥{TARGET_P:.0%}) · **Recall {pct(R)}** (target ≥{TARGET_R:.0%})",
         f"- Cases fully right: **{passed}/{len(runs)}**",
         f"- Wrong writes (the harmful kind): **{len(wrong)}**",
         f"- Cases that needed a nurse: **{sum(1 for r in runs if r['output']['nurse'])}/{len(runs)}** "
         f"(clinical cases plus anything the AI judge couldn't decide)",
         f"- Average per message: {tin // n} input + {tout // n} output tokens"
         + (f" · extractor **${cost:.5f}**" if cost is not None else "")
         + f" · judge **${sum(r.get('judge_cost', 0) for r in runs) / n:.4f}** per message",
         "", "## By signal", "", "| Signal | Precision | Recall | Right | Wrong | Missed |", "|---|---|---|---|---|---|"]
    for s in SIGNALS:
        t = tally[s]
        p, r = pr(t)
        L.append(f"| {s} | {pct(p)} | {pct(r)} | {t['tp']} | {t['fp']} | {t['fn']} |")

    sp = [r for r in runs if r["expected"].get("speaker")]
    if sp:
        right = sum(r["speaker"] == r["expected"]["speaker"] for r in sp)
        L.insert(L.index("## By signal"), f"- Who is writing (speaker, not a profile write): **{right}/{len(sp)}** right")
        L.insert(L.index("## By signal"), "")
    safety = [r for r in runs if set(r["variables"]["tags"]) & {"loss", "injection", "other_person", "temporary", "loss_vs_delivery"}]
    L += ["", "## Safety cases (must never write)", "", "| Case | Tags | Writes | Result |", "|---|---|---|---|"]
    for r in safety:
        L.append(f"| {r['id']} | {', '.join(r['variables']['tags'])} | {r['output']['writes'] or '—'} | {'pass' if r['pass'] else '**FAIL**'} |")

    tags = defaultdict(lambda: [0, 0])
    for r in runs:
        for t in r["variables"]["tags"]:
            tags[t][0] += r["pass"]
            tags[t][1] += 1
    L += ["", "## By case type", "", "| Tag | Passed |", "|---|---|"]
    for t, (a, b) in sorted(tags.items(), key=lambda kv: kv[1][0] / kv[1][1]):
        L.append(f"| {t} | {a}/{b} |")

    L += ["", "## Worst miss", ""]
    worst = wrong[0] if wrong else (missed[0] if missed else None)
    if worst:
        r, m = worst
        L += [f"**{r['id']}** · {m['kind']} · `{m['signal']}`: got `{m['got']}`, wanted `{m['want']}`", "",
              f"> {r['input']['messages'][-1]['text']}", "", "Rule trace:"]
        for d in r["trace"]["decisions"]:
            L.append(f"- {d['signal']}={d['value']} → {d['action']} ({d['reason']})")
        if not r["trace"]["decisions"]:
            L.append("- extractor proposed nothing")
    else:
        L.append("None.")

    L += ["", "## All misses", ""]
    for r in runs:
        for m in r["misses"]:
            L.append(f"- {r['id']} · {m['kind']} · {m['signal']}: got `{m['got']}`, wanted `{m['want']}` · “{r['input']['messages'][-1]['text'][:70]}”")
    if not any(r["misses"] for r in runs):
        L.append("None.")
    L += ["", "## Next step", "", "Read each miss in eval/out/runs.jsonl and bucket it: check → data → context → prompt → model. "
          "Make one change, rerun this same split, keep it only if more pass and nothing regressed.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
