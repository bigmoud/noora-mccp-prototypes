# Noora Health mCCP prototypes

Claude Corps fellowship work for Noora Health's Mobile Care Companion (mCCP), by Moud ([bigmoud](https://github.com/bigmoud)) and Shaheer ([shaheer2492](https://github.com/shaheer2492)).

These are **prototypes on simulated data**: one small, testable problem we can solve and measure during the fellowship. They are not the year-long objective. The unified household profile stays the long-term goal. No real family data is in this repo.

## What's here

### `profile-writer/`: WhatsApp message → profile, live
A family's WhatsApp message goes through privacy checks, Claude Haiku 5.5 proposes four profile signals (who holds the phone, delivered or not, baby's date of birth, due date), and plain-code rules decide what is written to the profile, held for a person, or dropped. Every write keeps the family's exact words. Following Kripesh's Nov 5 direction, nurses do no data entry: confident writes go live and **non-clinical reviewers check every write afterwards**; anything unclear waits for them, and any mention of a pregnancy loss pauses the family and goes to the **clinical team**.

- **Live demo:** a hosted dashboard shows each step as a message arrives, from a real phone through the WhatsApp Cloud API or typed into a simulator. **Replay** mode plays a recorded run with no server, as the backup.
- Writes follow UPE: `condition_area` moves `ANC_EDD` → `PNC_DOB` only together with the baby's DOB, in one recorded write. High-risk (HRPW) and SNCU families are never switched automatically.
- Eval on 46 synthetic cases (Hinglish, Devanagari, English, draft Marathi/Kannada/Telugu/Punjabi): **100% precision, 83% recall, 0 wrong writes**, $0.00033 per message. 37 tests.
- Start with [`profile-writer/README.md`](profile-writer/README.md); safety and privacy design in [`SAFETY.md`](profile-writer/SAFETY.md); hosting in [`docs/DEPLOY.md`](profile-writer/docs/DEPLOY.md); WhatsApp in [`docs/WHATSAPP.md`](profile-writer/docs/WHATSAPP.md).

```bash
cd profile-writer && python3 -m app.server          # dashboard + simulator (standard library only)
python3 -m eval.run_eval --extractor claude --split all
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
- No profile write without passing the code rules and keeping its source words. Nurses don't validate extractions (Kripesh, Nov 5); non-clinical reviewers check every write afterwards, and pregnancy-loss cases go to the clinical team. Nothing is ever sent to a family without a person pressing Send.
- No API keys in the repo: `.env` is git-ignored, and the Pages and Netlify builds refuse to publish anything that looks like a key.
