# Noora Health mCCP prototypes

Claude Corps fellowship work for Noora Health's Mobile Care Companion (mCCP), by Moud ([bigmoud](https://github.com/bigmoud)) and Shaheer ([shaheer2492](https://github.com/shaheer2492)).

These are **prototypes on simulated data**: one small, testable problem we can solve and measure during the fellowship. They are not the year-long objective. The unified household profile stays the long-term goal. No real family data is in this repo.

## What's here

### `profile-writer/`: scan a chat, save what lasts
Claude reads a family's WhatsApp conversation and pulls out facts about the mother and baby: stage, baby's date of birth, due date, who holds the phone, language, location and more. Each fact gets a status: one-click **ready**, **check first**, **nurse only**, or **alert** (never saved). Nurses save facts to the profile with one click, with the family's exact words as the source.

- `conversations.json`: 19 simulated English conversations, each built around a trap (husband reports the birth, whose phone it is said outright, the writer changing mid-chat, a sister's pregnancy, a corrected due date, four kinds of pregnancy loss, a birth with no date, twins and more).
- `answer_key.json`: the hidden answer key. The extractor never sees it.
- `extractor_prompt.md`: the extractor's instructions (also used by the page's live scan).
- `score.py`: scores the extractions and writes `scores.json` and `results.md`.
- `profile-writer.html`: the nurse page. It's built from `template.html` with the data embedded.
- `runs/`: earlier runs, kept for comparison.

Latest run (turn 3, 19 chats): **45 of 49** facts exactly right. 0 lasting facts lost, 0 wrong facts marked one-click ready, 0 nurse alerts missed, **0 of 4 pregnancy losses marked as a birth**, and the switch to postnatal decided right in 19 of 19 chats. The full table and turn log are in `profile-writer/results.md`.

Profiles use the fields of Noora's UPE (User Profile) as Kripesh described them. Exact field names and allowed values are still to confirm from the onboarding doc. Following Noora's delivery flow, a birth moves `condition_area` from `ANC_EDD` to `PNC_DOB` only together with the baby's date of birth; the page enforces this, and a birth with no date stays on pregnancy messages until the family gives one.

```bash
cd profile-writer && python3 score.py
```

### `stretch-eval/`: eval for stretch-reminder messages
A 30-check yes/no rubric (7 safety gates) for WhatsApp messages reminding pregnant mothers to stretch. It has 10 code checks and 20 LLM-judge checks, 17 pod-written test cases, and the judge is calibrated against them.

```bash
cd stretch-eval && python3 run_eval.py --judge judge_labels.json
```

`RUBRIC.md` is the readable rubric, and `findings.md` holds the latest diagnosis. `knowledge_bank.json` is a **placeholder** that needs clinical sign-off.

### `model/spine-and-slots.html`: personalization model
An interactive page showing six fictional women moving through one approved, due-date-based timeline. It shows how late, out-of-order or missing answers fill personalization slots without ever holding up approved content.

## Rules we follow
- Simulated, pod-written or de-identified/paraphrased data only. Noora has agreed that de-identified or paraphrased messages can go to Claude; real production messages stay inside Noora's systems.
- Clinical content (stretches, warning signs, emergency numbers) is a placeholder until Noora's clinical team signs it off.
- A human approves every write to a family's profile.
