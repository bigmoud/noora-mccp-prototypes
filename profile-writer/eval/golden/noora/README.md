# Noora's de-identified sample messages (private)

This folder is git-ignored (except this README) and left out of every zip and demo. Put
Kripesh's de-identified samples here, in the same two-file format as `eval/golden/`:

- `cases.jsonl`: one chat per line (`id`, `split`, `msg_day`, `profile`, `messages`)
- `answer_key.jsonl`: written by a person (Moud, a native speaker, or Niharika for loss
  cases) BEFORE any run, never shown to the model

Run: `python3 -m eval.run_eval --extractor claude --golden eval/golden/noora --split all`

Rules: no names, numbers or places even in de-identified text; delete the folder when the
fellowship ends or Noora asks; report scores, never quote messages, in slides.
