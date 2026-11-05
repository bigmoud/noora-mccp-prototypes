# Noora profile writer: notes for Claude Code

Prototype for Noora Health's Mobile Care Companion (Claude Corps). Reads WhatsApp messages,
proposes four profile signals (phone_holder, stage, baby_dob, due_date), and plain-code
rules decide what is written. Python standard library only: do not add dependencies.

## Hard rules
- Synthetic data only. Never add real names, numbers or messages from Noora users to any
  file, prompt, test, screenshot or commit. If a file looks like real data, stop and ask.
- `eval/golden/answer_key.jsonl` is written by people. Never edit it to make a run pass,
  and never put its contents into the extractor prompt.
- Safety behaviour lives in code (`app/rules.py`, `app/privacy.py`), not in the prompt.
  Don't move a check into the prompt, and don't loosen one without a failing test that
  explains why.
- `eval/golden/noora/` holds Noora's real de-identified samples: never copy them into
  other files, prompts, commits, zips, slides or screenshots.
- Writes follow UPE: condition area ANC_EDD → PNC_DOB only together with baby DOB.
- Nothing may send a WhatsApp message without a person pressing Send (`/api/reply`).

## Layout
- `app/extractor.py`: Claude call (one forced tool) and the offline keyword baseline
- `app/rules.py`: write rules; every decision lists its checks
- `app/privacy.py`: pseudonyms, redaction, allowlist, loss/emergency/injection guards
- `app/pipeline.py`: `assess()` (shared by live and eval) and `process_inbound()`
- `app/store.py`: SQLite, append-only facts, audit log without content
- `app/server.py` + `app/static/index.html`: dashboard, simulator, webhook
- `eval/`: golden set (cases and answer key kept apart) and `run_eval.py`
- `tests/`: `python3 -m unittest -v` must pass before any commit

## Changing the extractor
One change at a time, then `python3 -m eval.run_eval --extractor claude` on the dev split.
Keep the change only if more cases pass and nothing regressed. Run the holdout rarely.
