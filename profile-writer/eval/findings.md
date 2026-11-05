# Eval findings: Claude Haiku 5.5 extractor (Nov 5, 2026)

Model `claude-haiku-5-5`, no temperature control (deprecated on this model), so every
comparison below is the mean of 3 runs. Total API spend for all of this work: about $0.11.
Scores count only what reaches the profile.

## Summary

| Version | Change | Dev precision | Dev recall | Dev cases right | Wrong writes |
|---|---|---|---|---|---|
| Keyword baseline | — | 100% | 44% | 14/20 | 0 |
| v1 | first prompt | 100% | 50% | 14.3/20 | 0 |
| v2 | messages from her number are about her; phone_holder is about her phone | 100% | 65% | 15.0/20 | 0 |
| v3 | a date named as one day is "high"; code checks the arithmetic | 100% | 89% | 19.0/20 | 0 |

Held-out (6 cases, never used to tune the prompt): **100% precision, 75% recall**, 4/6,
stable across 3 runs. All 26: **100% precision, 81% recall**, 22/26.

## Turn by turn (bucket: check → data → context → prompt → model)

**v1 → v2 (prompt).** In g02, g17 and g18 the model had the right birth date but marked it
"medium" with notes like *"Speaker not identified, so confidence is medium."* In g13 it
marked the mother-in-law's phone ownership as `subject: other_person`, so the rule
dropped it. Neither was explained in the prompt. One edit: say that messages come from
her number, and that phone_holder is about her phone. Kept: recall 50% → 65%.

**v2 → v3 (prompt).** Exact dates still came back "medium" (g03 *"28 October ko"*, g17
*"3 tarikh ko"*), apparently hedging the arithmetic. One edit: a date named as one day is
"high"; code re-checks the arithmetic. Kept: recall 65% → 89%, no wrong writes.

**Holdout run 1 (code, not prompt).** g21 *"…a baby **gir**l…"* matched the loss guard's
pattern for *"bachcha gir gaya"* (miscarriage), so the whole message went to the clinical
lane. It failed safe (held, not wrongly written), but it's a bug. Fixed with a whole-word
match, and added a regression test. While fixing it, an inline comment swallowed the next
pattern; the unit tests caught that before any run. Holdout recall 46% → 75% after the fix.
Caveat: the holdout has now influenced one code change.

## Still failing

| Case | What happens | Likely bucket | Next change to try |
|---|---|---|---|
| g15 *"Main khud likh rahi hoon, yeh mera hi number hai"* | No proposal: the mother saying it's her own phone isn't treated as news | prompt | Say that "mother" is a valid phone_holder worth recording |
| g17 *"3 tarikh ko"* (reply to nurse) | Right date, still "medium" | prompt / model | One worked example of a short reply to a nurse's question |
| g22 *"Kal operation se delivery hogi"* | Right date (tomorrow), "medium" | prompt | Example of future "kal" for a due date |
| g25 *"Somvar ko delivery hui"* | Right date, sometimes "medium" | model variance | Try Sonnet on the same set and compare cost against recall |

## Variance seen on the demo message

*"…delivery ho gayi … pichhle mangalvar ko"*: baby_dob written **0/6** times (four
"medium" ratings; once the value was the text *"2026-11-05 minus 'pichhle mangalvar'"*,
rejected by the allowed-value check). The same message with *"3 November"*: written
**6/6**. The rules behaved correctly in every case. A possible code change: when the model's
value isn't a date but code can read the quoted phrase, use the code's date and say so in
the trace. That trades away the two-source check, so it needs Kripesh's answer on whether
a wrong write or a missed write is worse.

## Limits

26 synthetic cases written by the same person who wrote the prompt. Small enough that
one case moves recall by ~4 points. Before anyone relies on these numbers: 100+ cases
written by Moud or a Hindi speaker who hasn't seen the prompt, ideally paraphrased from
real (consented, de-identified) messages once Kripesh agrees.

---

# Update after Kripesh's review (Nov 5, afternoon)

**Changes from his answers.** Campaign = UPE condition area + a date, so the profile now
stores `condition_area` (ANC_EDD, PNC_DOB, HRPW, SNCU…) instead of an ANC/PNC flag. The
switch ANC_EDD → PNC_DOB is written only together with the baby's DOB, in one transaction
and one UPE write record carrying each field's quote, confidence and checks. HRPW, SNCU
and other areas are never switched automatically, and a new due date on PNC_DOB is held.

**20 new cases (split `dev2`), written before any prompt change:** whose phone said
outright, the writer changing mid-chat, 8 loss-vs-delivery cases (including twins where one
died and a NICU baby who is recovering), Marathi/Kannada/Telugu/Punjabi (unverified
translations) and one HRPW family.

| | Precision | Recall | Cases right | Wrong writes |
|---|---|---|---|---|
| Keyword baseline, before guard fix | 67% | 25% | 8/20 | **2** (wrote "delivered" for two babies who died) |
| Keyword baseline, after guard fix | 100% | 25% | 13/20 | 0 |
| Haiku 5.5, no prompt change (2 runs) | 100% | 88% | 18/20 | 0 |

Haiku flagged every loss case, in every language, on its own. The keyword guard is the
backup and missed g31 (*"Baby hua tha par do din baad nahi raha"*, too many words between),
g32 (*"baby bach nahi paya"*, word order) and all non-Hindi loss words. Fixed in code: wider
gap, both word orders, draft word lists for four languages, and a verb check so *"Baby so
nahi raha"* (not sleeping) doesn't raise a false alarm. Native-script digits (९८७…, ೯೮೭…)
are now converted before phone redaction.

**New misses (prompt, not yet changed):**
- g28 *"This is my husband's number. I use it when he is at home."*: no phone_holder.
- g37 *"doctor ne operation ki date 10 November di hai"*: a scheduled C-section date is not
  read as the due date. Is that even the right label? Ask Niharika.
- Speaker (who is writing) 1/4: the model names the phone's owner as the writer (g27, g28)
  and misses the switch to the mother in Devanagari (g30).
