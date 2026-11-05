# Profile writer

When a family mentions in ordinary WhatsApp chat that she has delivered, the baby's birth
date, her due date, or that the husband holds the phone, that fact never reaches her
profile unless she tapped the right button. So she keeps getting pregnancy messages,
replies go to the wrong person, and the next nurse asks again.

The profile writer reads each message, saves those facts with the family's own words as
the source, and keeps nurses out of data entry. Built for Noora Health's Mobile Care
Companion by Claude Corps fellows. **Synthetic data only.**

## What the nurse sees

The demo is the nurse's inbox: WhatsApp chats on the left, the conversation in the middle,
and the Copilot panel on the right with a short AI-written summary of the family, the
profile fields MSEs already use (condition area, due date, baby DOB, baby age…) and a
drafted reply in Hindi or English. The profile updates on its own as families write;
a nurse only sees a **Check before saving** card when the AI couldn't decide, and a
**Clinical review** card for pregnancy loss or high-risk campaigns.

## How a message is handled

```
message → privacy (pseudonym, redaction) → keyword guards (loss, danger signs, injection)
        → extractor (Claude Haiku 5.5) proposes facts → write rules (code)
        → AI judge (Claude Sonnet 5.5, yes/no rubric) → saved | nurse | ask the family | dropped
        → one profile write record (condition area ANC_EDD → PNC_DOB only together with the baby's DOB)
        → Copilot summary + draft reply (the nurse edits and presses Send)
```

- **Code decides, not the model.** The quote must be in the message, dates are re-checked by
  our own date maths, someone else's baby is dropped, approximate dates become a question in
  the draft reply instead of a write.
- **The judge reviews every write** against a fixed rubric; code turns its answers into a
  verdict. It can't overrule a conflict with what's on file (a five-week due-date change goes
  to a nurse). Every nurse decision becomes a candidate test case.
- **Never automatic:** sending a message, switching a high-risk family's campaign, anything
  after a possible pregnancy loss.

Details: [SAFETY.md](SAFETY.md) · demo script: [DEMO.md](DEMO.md) · hosting:
[docs/DEPLOY.md](docs/DEPLOY.md) · WhatsApp: [docs/WHATSAPP.md](docs/WHATSAPP.md) · eval log:
[eval/findings.md](eval/findings.md)

## Results (46 synthetic cases, Hinglish, Devanagari, English, draft Marathi/Kannada/Telugu/Punjabi)

| | Precision | Recall | Wrong writes | Needed a nurse | Cost / message |
|---|---|---|---|---|---|
| Keyword baseline | 100% | 42% | 0 | — | $0 |
| Haiku extractor + rules | 100% | 83% | 0 | — (human review of every write) | $0.0003 |
| **+ Sonnet judge** | **100%** | **95%** | **0** | 9 of 46 (7 are clinical cases) | ~$0.004 + Copilot $0.0005 |

Judge calibration: shown 116 proposals (correct, deliberately corrupted, and tempting-but-wrong),
it confirmed **0 of 74 wrong ones**, confirmed 95% of correct ones automatically, and sent 3% to
a nurse (`python3 -m eval.run_judge_eval`). Small synthetic set written by us; see the limits in
`eval/findings.md`.

## Run it

Python 3.10+, no packages to install.

```bash
cp .env.example .env              # add ANTHROPIC_API_KEY (the offline baseline runs without one)
python3 -m app.server             # open the link it prints
```

Use **Family phone** (bottom left) to send a message as the family in the open chat. Without
a server, the hosted page (`web/`) runs an **offline demo**: the same screens, playing back
results recorded from the real pipeline for the suggested messages.

| | Command |
|---|---|
| Tests (44) | `python3 -m unittest` |
| Extractor eval | `python3 -m eval.run_eval --extractor claude --split all` |
| Judge calibration | `python3 -m eval.run_judge_eval` |
| Re-record the offline demo | `python3 -m scripts.record_demo` |
| Single-file offline page | `python3 -m scripts.build_offline_page` |
| Signed test webhook | `python3 -m scripts.send_test_webhook "Meri delivery kal hui"` |

Every Claude call checks `SPEND_CAP_USD` (default $5) first; past it, nothing is sent.

## Layout

| Path | What |
|---|---|
| `app/extractor.py` | Claude extractor and keyword baseline |
| `app/rules.py` | Write rules; every decision lists its checks |
| `app/judge.py` | AI judge: rubric, verdict decided in code |
| `app/copilot.py` | Family summary and draft reply (stand-in for Noora's Copilot) |
| `app/pipeline.py` | `assess()` (shared by live and eval), `process_inbound()`, nurse actions |
| `app/privacy.py` | Pseudonyms, redaction, allowlist, loss / danger / injection guards |
| `app/view.py` | What the nurse's screen shows |
| `app/store.py`, `app/server.py`, `app/whatsapp.py` | SQLite store, API + webhook, WhatsApp Cloud API |
| `web/` | The inbox (static) and `demo.json` (offline demo) |
| `eval/` | Golden set, extractor eval, judge calibration, findings |

## Not built here

Noora's real Copilot and FAQ bank, the medical history store, clinical facts, voice notes,
other countries, household IDs.
