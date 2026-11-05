# Noora Health mCCP prototypes

Claude Corps fellowship work for Noora Health's Mobile Care Companion (mCCP), by Moud ([bigmoud](https://github.com/bigmoud)) and Shaheer ([shaheer2492](https://github.com/shaheer2492)).

These are **prototypes on simulated data**: one small, testable problem we can solve and measure during the fellowship. They are not the year-long objective. The unified household profile stays the long-term goal. No real family data is in this repo.

## What's here

### `profile-writer/`: the nurse's inbox, with a profile that writes itself
A WhatsApp-style inbox for MSEs. As families write, the profile updates on its own: Claude Haiku 5.5 proposes four facts (who holds the phone, delivered or not, baby's DOB, due date), plain-code rules check them, and an **AI judge** (Claude Sonnet 5.5, a yes/no rubric calibrated against our golden set) confirms each write. Nurses only see a **Check before saving** card when the judge can't decide, and a **Clinical review** card for pregnancy loss or high-risk campaigns. The Copilot panel mirrors the UPE fields MSEs use today, with an AI-written summary of the family and a drafted reply in Hindi or English that the nurse edits and sends.

- Writes follow UPE: `condition_area` moves `ANC_EDD` → `PNC_DOB` only together with the baby's DOB, in one recorded write. HRPW and SNCU families are never switched automatically.
- Eval on 46 synthetic cases: **100% precision, 95% recall, 0 wrong writes**; 9 cases needed a nurse (7 of them clinical). Judge calibration: **0 of 74** wrong proposals confirmed.
- Works offline (recorded results from the real pipeline) on GitHub Pages, or live against the server with the WhatsApp Cloud API.
- Start with [`profile-writer/README.md`](profile-writer/README.md); safety in [`SAFETY.md`](profile-writer/SAFETY.md); demo script in [`DEMO.md`](profile-writer/DEMO.md).

```bash
cd profile-writer && python3 -m app.server          # inbox + Family phone simulator (standard library only)
python3 -m eval.run_eval --extractor claude --split all
python3 -m eval.run_judge_eval
```

### `profile-writer/nurse-page/`: the earlier nurse-facing version
Moud's first profile writer: Claude reads a whole conversation and pulls out a wider set of facts (stage, baby's DOB, due date, who holds the phone, language, location, delivery place, feeding, symptom alerts). Each fact gets a status (one-click **ready**, **check first**, **nurse only**, **alert**) and a nurse saves it with one click. 19 simulated English conversations built around traps, a hidden answer key and `score.py`. Latest run: **45 of 49** facts exactly right, 0 of 4 pregnancy losses marked as a birth. See `nurse-page/results.md`.

```bash
cd profile-writer/nurse-page && python3 score.py
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
- Simulated, pod-written or de-identified/paraphrased data only. Noora has agreed that de-identified or paraphrased messages can go to Claude; real production messages stay inside Noora's systems. Noora's de-identified samples go only in the git-ignored `profile-writer/eval/golden/noora/`.
- Clinical content (stretches, warning signs, emergency numbers) is a placeholder until Noora's clinical team signs it off.
- No profile write without passing the code rules and the AI judge, and keeping its source words. Nurses don't validate routine extractions (Kripesh, Nov 5); they see only what the judge couldn't decide and clinical cases. Nothing is ever sent to a family without a person pressing Send.
- No API keys in the repo: `.env` is git-ignored, and the Pages and Netlify builds refuse to publish anything that looks like a key.
