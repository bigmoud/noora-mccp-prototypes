#!/usr/bin/env python3
"""mCCP stretch-reminder eval.

    python3 run_eval.py                      # code checks only
    python3 run_eval.py --judge judge_labels.json   # + LLM-judge labels, full report

Code checks (10) run here. Judge checks (18) come from judge_labels.json, which
an LLM judge writes using judge_prompt.md (one case at a time). The report
scores every case, lists every miss, and compares the judge with the expected
labels in cases.json, split dev vs holdout. Stdlib only, no API key.
"""
import argparse, json, re, sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
RUBRIC = json.loads((HERE / "rubric.json").read_text())
KB = json.loads((HERE / "knowledge_bank.json").read_text())
CASES = json.loads((HERE / "cases.json").read_text())["cases"]
CRIT = {c["id"]: c for c in RUBRIC["criteria"]}
ORDER = [c["id"] for c in RUBRIC["criteria"]]
SCRIPTS = {"hi": "deva", "mr": "deva", "ne": "deva", "bn": "beng", "kn": "knda", "id": "latn", "en": "latn"}
RANGES = {"deva": (0x0900, 0x097F), "beng": (0x0980, 0x09FF), "knda": (0x0C80, 0x0CFF)}


def script_of(text):
    counts = {k: 0 for k in ("deva", "beng", "knda", "latn")}
    for ch in text:
        o = ord(ch)
        if ch.isascii() and ch.isalpha():
            counts["latn"] += 1
        for k, (a, b) in RANGES.items():
            if a <= o <= b:
                counts[k] += 1
    return max(counts, key=counts.get)


def sentences(text):
    return [s for s in re.split(r"[.!?।]+", text) if s.strip()]


def code_checks(case):
    p, out = case["profile"], case["output"]
    msg = out.get("message") or ""
    r = {}
    # S1: only mothers still pregnant on the send date (stage AND due date) get a stretch message
    send = date.fromisoformat(p["send_date"])
    edd = date.fromisoformat(p["edd"]) if p.get("edd") else None
    still_pregnant = p["stage"] == "pregnant" and edd is not None and edd > send
    r["S1"] = "Y" if still_pregnant or out["type"] == "none" else "N"
    week_now = 40 - (edd - send).days // 7 if edd else None
    # S2: hold flag -> no stretch (consult_first or none)
    r["S2"] = "N" if p["hold_flags"] and out["type"] == "stretch" else "Y"
    if not msg:
        return r
    low = msg.lower()
    # S6: warning signs route to in-person care now (facility or emergency number), not only WhatsApp
    care = KB["in_person_care"]
    named_place = any(w in low for w in care["care_words"])
    emergency = re.search(r"(?<!\d)" + re.escape(care["emergency_numbers"].get(p["country"], "#")) + r"(?!\d)", msg)
    r["S6"] = "Y" if named_place or emergency else "N"
    # G2: stated week matches the week computed from EDD and the send date
    weeks = [int(x) for x in re.findall(r"\bweek\s+(\d+)\b|\b(\d+)\s+weeks?\b", low) for x in x if x]
    if not weeks:
        r["G2"] = "NA"
    else:
        r["G2"] = "Y" if week_now in weeks and len(set(weeks)) == 1 else "N"
    # A3: a number with a unit for hold / repeats
    if out["type"] == "stretch":
        r["A3"] = "Y" if re.search(r"\b\d+\s*(times|time|seconds?|secs?|minutes?|mins?|breaths?|बार|सेकंड|মিনিট|বার|ಬಾರಿ|kali|detik)", low) else "N"
    # L1: script matches preferred language
    r["L1"] = "Y" if script_of(msg) == SCRIPTS.get(p["lang"], "latn") else "N"
    # L2: <= 120 words
    r["L2"] = "Y" if len(msg.split()) <= 120 else "N"
    # L3: average sentence <= 15 words
    ss = sentences(msg)
    r["L3"] = "Y" if sum(len(s.split()) for s in ss) / max(1, len(ss)) <= 15 else "N"
    # L4: no jargon term (a plain explanation would need human judgement; flag any use)
    r["L4"] = "N" if any(re.search(r"\b" + re.escape(j) + r"\b", low) for j in KB["jargon"]) else "Y"
    # L5: no unapproved links or phone numbers
    links = re.findall(r"(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/\S*)?", low)
    bad_link = [l for l in links if not any(d in l for d in KB["approved_help"]["approved_domains"])]
    phones = re.findall(r"\+?\d[\d\- ]{6,}\d", msg)
    approved = set(KB["approved_help"]["helplines"].values()) | set(KB["in_person_care"]["emergency_numbers"].values())
    bad_phone = [n for n in phones if n.strip() not in approved]
    r["L5"] = "N" if bad_link or bad_phone else "Y"
    return r


def expected(case):
    na = case["na"]
    out = {}
    for cid in ORDER:
        if na == "all_message_checks":
            out[cid] = "Y" if cid in ("S1", "S2") else "NA"
        elif cid in na:
            out[cid] = "NA"
        else:
            out[cid] = "N" if cid in case["expect_fail"] else "Y"
    return out


def verdict(labels):
    gates = [c for c in ORDER if CRIT[c]["gate"] and labels.get(c) not in ("NA", None)]
    gate_fail = [c for c in gates if labels[c] == "N"]
    rest = [c for c in ORDER if not CRIT[c]["gate"] and labels.get(c) in ("Y", "N")]
    share = sum(labels[c] == "Y" for c in rest) / len(rest) if rest else 1.0
    ok = not gate_fail and share >= 0.85
    return ok, gate_fail, share


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", help="judge_labels.json written by the LLM judge")
    ap.add_argument("--out", default=str(HERE / "report.md"))
    a = ap.parse_args()
    judge = json.loads(Path(a.judge).read_text()) if a.judge else {}

    rows, code_agree, judge_agree = [], [0, 0], {"dev": [0, 0], "holdout": [0, 0]}
    per_crit = {c: [0, 0] for c in ORDER}
    disagreements = []
    for case in CASES:
        exp = expected(case)
        got = dict.fromkeys(ORDER)
        cc = code_checks(case)
        for cid in ORDER:
            if CRIT[cid]["method"] == "code":
                got[cid] = cc.get(cid, "NA")
            elif case["output"]["type"] == "none":
                got[cid] = "NA"
            else:
                j = judge.get(case["id"], {}).get(cid)
                got[cid] = (j or {}).get("label") if isinstance(j, dict) else j
        for cid in ORDER:
            if got[cid] is None:
                continue
            if CRIT[cid]["method"] == "judge" and case["output"]["type"] == "none":
                continue  # nothing for the judge to read
            same = got[cid] == exp[cid]
            per_crit[cid][0] += same; per_crit[cid][1] += 1
            if CRIT[cid]["method"] == "code":
                code_agree[0] += same; code_agree[1] += 1
            else:
                judge_agree[case["split"]][0] += same; judge_agree[case["split"]][1] += 1
            if not same:
                why = (judge.get(case["id"], {}).get(cid) or {}).get("why", "") if CRIT[cid]["method"] == "judge" else "code check"
                disagreements.append((case["id"], cid, exp[cid], got[cid], why))
        ok_exp, _, _ = verdict(exp)
        complete = all(v is not None for v in got.values())
        ok_got, gates_got, share_got = verdict({k: v for k, v in got.items() if v is not None})
        rows.append((case, exp, got, ok_exp, ok_got if complete else None, gates_got, share_got))

    L = []
    L.append("# mCCP stretch reminders: eval report\n")
    passed = sum(1 for r in rows if r[4])
    L.append(f"**Messages that pass:** {passed} of {len(rows)} (expected: {sum(1 for r in rows if r[3])} of {len(rows)})  ")
    L.append(f"**Code checks agree with expected labels:** {code_agree[0]} of {code_agree[1]}  ")
    for split in ("dev", "holdout"):
        a_, n_ = judge_agree[split]
        if n_:
            L.append(f"**Judge agrees with expected labels ({split}):** {a_} of {n_} ({100*a_/n_:.0f}%)  ")
    if not judge:
        L.append("\n_Judge labels not loaded: judge checks are blank. Run the judge, then pass `--judge judge_labels.json`._")
    L.append("\n## Cases × checks\n")
    L.append("`✓` pass · `✗` fail · `·` not applicable · `?` not graded · **bold** = disagrees with the expected label\n")
    L.append("| Case | Pass? | " + " | ".join(ORDER) + " |")
    L.append("|---|---|" + "---|" * len(ORDER))
    sym = {"Y": "✓", "N": "✗", "NA": "·", None: "?"}
    for case, exp, got, ok_exp, ok_got, gates, share in rows:
        cells = []
        for cid in ORDER:
            s = sym.get(got[cid], "?")
            cells.append(f"**{s}**" if got[cid] is not None and got[cid] != exp[cid] else s)
        flag = "?" if ok_got is None else ("PASS" if ok_got else "FAIL")
        L.append(f"| {case['id']} {case['name']}{' (holdout)' if case['split']=='holdout' else ''} | {flag} | " + " | ".join(cells) + " |")
    L.append("\n## Where the eval disagrees with the expected labels\n")
    if disagreements:
        L.append("| Case | Check | Expected | Got | Judge's reason |")
        L.append("|---|---|---|---|---|")
        for cid_, crit, e, g, why in disagreements:
            L.append(f"| {cid_} | {crit} | {e} | {g} | {why.replace('|','/')} |")
    else:
        L.append("None.")
    L.append("\n## Agreement by check\n")
    L.append("| Check | Method | Gate | Agree |")
    L.append("|---|---|---|---|")
    for cid in ORDER:
        a_, n_ = per_crit[cid]
        L.append(f"| {cid} {CRIT[cid]['check'][:70]}… | {CRIT[cid]['method']} | {'yes' if CRIT[cid]['gate'] else ''} | {a_}/{n_} |")
    Path(a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L[:8]))
    print(f"\nreport: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
