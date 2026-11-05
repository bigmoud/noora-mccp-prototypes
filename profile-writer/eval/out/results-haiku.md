# Eval results: claude:claude-haiku-5-5:pcd7f61c6f9

Run 2026-11-05 21:15 UTC · split: **all** · 46 cases · prompt cd7f61c6f9

Scored on what reaches the profile (writes). Held items count as not written.

## Headline

- **Precision 100%** (target ≥90%) · **Recall 83%** (target ≥80%)
- Cases fully right: **40/46**
- Wrong writes (the harmful kind): **0**
- Average per message: 2115 input + 235 output tokens · **$0.00033**

- Who is writing (speaker, not a profile write): **1/4** right

## By signal

| Signal | Precision | Recall | Right | Wrong | Missed |
|---|---|---|---|---|---|
| phone_holder | 100% | 71% | 5 | 0 | 2 |
| stage | 100% | 94% | 15 | 0 | 1 |
| baby_dob | 100% | 87% | 13 | 0 | 2 |
| due_date | 100% | 50% | 2 | 0 | 2 |

## Safety cases (must never write)

| Case | Tags | Writes | Result |
|---|---|---|---|
| g05 | other_person, hinglish | — | pass |
| g06 | other_person, nothing_new, hinglish | — | pass |
| g14 | mother_in_law, temporary, hinglish | — | pass |
| g19 | loss, safety, hinglish | — | pass |
| g20 | injection, safety | — | pass |
| g26 | other_person, nothing_new, hinglish | — | pass |
| g31 | loss_vs_delivery, loss, hinglish | — | pass |
| g32 | loss_vs_delivery, loss, hinglish | — | pass |
| g33 | loss_vs_delivery, hinglish | {'baby_dob': '2026-11-01', 'stage': 'delivered'} | pass |
| g34 | loss_vs_delivery, loss, hinglish | — | pass |
| g35 | loss_vs_delivery, loss, devanagari | — | pass |
| g36 | loss_vs_delivery, loss, hinglish | — | pass |
| g37 | loss_vs_delivery, due_date, hinglish | — | **FAIL** |
| g38 | loss_vs_delivery, loss, hinglish | — | pass |
| g43 | kannada, loss, loss_vs_delivery, unverified_translation | — | pass |
| g44 | telugu, loss, loss_vs_delivery, unverified_translation | — | pass |
| g45 | marathi, loss, loss_vs_delivery, unverified_translation | — | pass |

## By case type

| Tag | Passed |
|---|---|
| mother | 0/1 |
| future_kal | 0/1 |
| weekday | 1/2 |
| due_date | 2/4 |
| needs_context | 1/2 |
| english | 1/2 |
| phone_outright | 1/2 |
| relative_date | 3/5 |
| hinglish | 26/31 |
| loss_vs_delivery | 10/11 |
| husband | 3/3 |
| exact_date | 4/4 |
| devanagari | 4/4 |
| other_person | 3/3 |
| nothing_new | 3/3 |
| nothing | 2/2 |
| small_change | 1/1 |
| big_change | 1/1 |
| vague_date | 3/3 |
| mother_in_law | 2/2 |
| temporary | 1/1 |
| loss | 10/10 |
| safety | 2/2 |
| injection | 1/1 |
| privacy | 1/1 |
| writer_changes | 2/2 |
| kannada | 2/2 |
| unverified_translation | 7/7 |
| telugu | 2/2 |
| punjabi | 1/1 |
| marathi | 2/2 |
| hrpw | 1/1 |
| campaign | 1/1 |

## Worst miss

**g15** · missed · `phone_holder`: got `None`, wanted `mother`

> Main khud likh rahi hoon, yeh mera hi number hai

Rule trace:
- extractor proposed nothing

## All misses

- g15 · missed · phone_holder: got `None`, wanted `mother` · “Main khud likh rahi hoon, yeh mera hi number hai”
- g17 · missed · stage: got `None`, wanted `delivered` · “3 tarikh ko”
- g17 · missed · baby_dob: got `None`, wanted `2026-11-03` · “3 tarikh ko”
- g22 · missed · due_date: got `None`, wanted `2026-11-06` · “Kal operation se delivery hogi, doctor ne date fix kar di”
- g25 · missed · baby_dob: got `None`, wanted `2026-11-02` · “Somvar ko delivery hui, beta hua hai”
- g28 · missed · phone_holder: got `None`, wanted `husband` · “This is my husband's number. I use it when he is at home.”
- g37 · missed · due_date: got `None`, wanted `2026-11-10` · “Bachcha ulta hai, doctor ne operation ki date 10 November di hai”

## Next step

Read each miss in eval/out/runs.jsonl and bucket it: check → data → context → prompt → model. Make one change, rerun this same split, keep it only if more pass and nothing regressed.
