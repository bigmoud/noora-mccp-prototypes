# Findings — run 2 (rubric v2: 30 checks; Sonnet judge; 16 messages + 1 withheld)

What changed since run 1: rubric v2 from the "MCCP user engagement strategies" call (S6 in-person care, S1/G2 from EDD, A6 practice question, new H5 and L6), countries updated, 3 new cases (C15–C17), and G1 now says it ignores week claims.

Scores: 6 of 17 pass (expected 6). Code checks 170/170. Judge dev 260/260 (100%), holdout 58/60 (97%).
The run-1 double count (C12 G1 failing a wrong week) is gone: G1 now passes and G2 alone catches it.

### C13 · A2 · expected N, judge Y (holdout)
"spread your yoga mat and do the seated side stretch. Raise one arm and lean gently…"
Run 1's judge said N, run 2's said Y: the check is unstable on this message. "Seated" in the name implies sitting, but the message never says "sit".
bucket: check (A2's wording leaves room)
change: reword A2 to "says the starting position in words (sit, stand, hands and knees)". Holdout case: reword for clarity, don't tune to the case.

### C13 · L6 · expected Y, judge N (holdout)
"contains a link 'bit.ly/stretch-video' that cannot be read aloud"
The link is L5's job; L6 says "(Links are L5.)", but the judge still counted it.
bucket: prompt
change: repeat in the judge prompt that L6 ignores links.

### Open questions for Niharika (clinical owner)
1. C14 (a 20-minute calf stretch) and C09 (husband's phone, never says who it is for) still PASS, because G3 and H1 are not gates. Should either be a gate?
2. Confirm the approved stretches, doses, contraindications and warning signs in knowledge_bank.json.
3. For warning signs, is "nearest health centre or 108/999/119/112" the right instruction in every country?

### next
1. A2 wording + L6 prompt note, then rerun all 17   2. Niharika's answers   3. 30–50 messages labelled by 2–3 clinical reviewers
