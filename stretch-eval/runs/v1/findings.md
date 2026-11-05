# Findings — run 1 (Sonnet judge, 13 messages, 18 judge checks)

Judge agreement: dev 178/180 (99%), holdout 53/54 (98%). Code checks: 140/140.

### C10 · G1 · expected Y, judge N
"pelvic floor exercises, which many women find useful" — a health claim not in the knowledge bank.
bucket: check (the expected label was wrong)
change: relabel C10 G1 = N. DONE in this turn.

### C13 · G1/A2 · expected Y, judge N (holdout)
"Raise one arm and lean gently to the other side" — never says to sit or how to start.
bucket: check (the expected label was wrong)
change: relabel C13 A2 = N. DONE in this turn. (Label fix only; the judge was not tuned on the holdout.)

### C12 · G1 · expected Y, judge N
"You are in week 12 now" — failed G1 as a wrong health statement, but the wrong week is G2's job.
bucket: prompt (the judge was never told G1 excludes stage claims)
change: add to judge_prompt.md: "G2 covers the week or stage; G1 ignores them." NEXT TURN, then rerun all 13.

### Open questions for Niharika (clinical owner)
1. C14 holds the calf stretch 2 minutes × 10 (20 min, over the 15-min session cap) yet the message still PASSES, because G3 is not a gate. Should a dose outside the range be a gate?
2. C09 is on the husband's phone and never says who it is for, yet it PASSES (H1 is not a gate). Given 41,520 shared phones, should H1 be a gate?
3. Confirm the approved stretches, dose ranges, contraindications and warning signs in knowledge_bank.json.

### next
1. judge prompt: G1 vs G2   2. answers to the questions above   3. grow to 30–50 messages labelled by 2–3 clinical reviewers
