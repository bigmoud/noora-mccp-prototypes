# Noora profile writer (prototype)

When a family mentions in ordinary WhatsApp chat that she has delivered, the baby's
birth date, her due date, or that the husband holds the phone, that fact never reaches
her profile unless she tapped the right button. So she keeps getting pregnancy
messages, replies go to the wrong person, and the next nurse asks again.

This prototype reads each message and proposes those four facts. Writes follow Noora's
UPE: the campaign is condition area + a date, so moving her from ANC_EDD to PNC_DOB is
always written together with the baby's DOB, in one recorded UPE write. Plain-code rules write
the confident ones with the exact words they came from, hold the unclear ones, and drop
the rest. Non-clinical reviewers check every write afterwards, so nurses do no data entry.
Built for Noora Health's Mobile Care Companion by Claude Corps fellows. **Synthetic data only.**

- How it stays safe and private: [SAFETY.md](SAFETY.md)
- How to run the demo for reviewers: [DEMO.md](DEMO.md)
- Hosting the dashboard and server: [docs/DEPLOY.md](docs/DEPLOY.md)
- Connecting WhatsApp (test number or your own): [docs/WHATSAPP.md](docs/WHATSAPP.md)

## Three ways to show it

| Mode | Needs | Use when |
|---|---|---|
| **Replay** | Just the hosted page (`web/`) | Backup, or anyone browsing the link. Plays a recorded run of the real pipeline (Claude Haiku 5.5, synthetic chats) step by step |
| **Live, simulator** | Hosted page + server | Type family messages into the dashboard and watch each step happen |
| **Live, WhatsApp** | Hosted page + server + Meta test number | Send from a real phone; the dashboard updates as it's processed |

## Run it (2 minutes, no accounts needed)

Needs Python 3.10+. No packages to install.

```bash
cp .env.example .env          # optional: add ANTHROPIC_API_KEY to use Claude
python3 -m app.server
```

Open the link it prints (it carries an access token). Or open `web/index.html` from any
static host and use **Connect to live server**. Pick a family, use the script
buttons under the chat, and watch the middle column show every step. Without an API key
it uses an offline keyword baseline, so nothing leaves your laptop.

## Live WhatsApp demo

Your own phones and synthetic messages only. Meta's test mode allows up to 5 verified
recipient numbers and needs no company registration.

1. **Meta app.** At developers.facebook.com create an app (type *Business*) and add the
   *WhatsApp* product. On *API Setup* note the **temporary access token**, the
   **Phone number ID**, and the free **test number**. Add your phones as recipients
   and verify each one with the code.
2. **App secret.** *App settings → Basic → App secret.* It signs every webhook.
3. **.env.** Set `WHATSAPP_LIVE=true`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`,
   `WHATSAPP_APP_SECRET`, a `WHATSAPP_VERIFY_TOKEN` you make up, and
   `ALLOWED_TEST_NUMBERS` (your phones, e.g. `919800000001,14155550123`).
4. **Tunnel.** `python3 -m app.server`, then in another terminal `ngrok http 8000`.
5. **Webhook.** In *WhatsApp → Configuration* set the callback URL to
   `https://<your-ngrok-host>/webhook` with your verify token, then subscribe to the
   **messages** field.
6. **Open the chat.** From *API Setup*, send the `hello_world` template to your phone,
   then reply from the phone. Your reply opens WhatsApp's 24-hour window, appears on the
   dashboard as "Live tester ••••0123", and runs through the pipeline in about a second
   (a few seconds with Claude).

The temporary token expires after 24 hours: make a fresh one on demo morning. Messages
from numbers not on the allowlist are dropped without being stored.

Test the live path without Meta: `python3 -m scripts.send_test_webhook "Meri wife ki delivery kal hui"`
sends a correctly signed, Meta-shaped webhook to your local server.

## Eval

```bash
python3 -m eval.run_eval                         # offline baseline, dev split
python3 -m eval.run_eval --extractor claude      # Claude (needs key), dev split
python3 -m eval.run_eval --extractor claude --split holdout   # rarely
```

Writes `eval/out/results.md` (precision, recall, wrong writes, safety cases, worst miss,
cost per message) and `eval/out/runs.jsonl` (one record per case with the full trace).
Scores what reaches the profile, not what the model proposed. The answer key
(`eval/golden/answer_key.jsonl`) is kept apart from the cases and never shown to the model.

Results on 46 synthetic cases (details and the tuning log in `eval/findings.md`):

| Extractor | Precision | Recall | Wrong writes | Cost / message |
|---|---|---|---|---|
| Keyword baseline (all 46) | 100% | 36% | 0 | $0 |
| Claude Haiku 5.5 (all 46) | 100% | 83% | 0 | $0.00033 |
| Haiku, held-out 6 | 100% | 75% | 0 | |
| Haiku, 20 new cases from Kripesh's review (untuned) | 100% | 88% | 0 | |

Noora's real de-identified samples go in `eval/golden/noora/` (git-ignored, kept out of
zips): `python3 -m eval.run_eval --extractor claude --golden eval/golden/noora --split all`.

Every API call is checked against `SPEND_CAP_USD` (default $5) first; past it, no request is sent.

## Tests

```bash
python3 -m unittest -v      # 37 tests: privacy, rules, UPE writes, webhook, pipeline, Claude client, spend cap, access
```

## Layout

| Path | What |
|---|---|
| `app/extractor.py` | Claude extractor (one forced tool, JSON schema) and keyword baseline |
| `app/rules.py` | Write rules. Each decision lists the checks it passed or failed |
| `app/privacy.py` | Pseudonyms, redaction, allowlist, loss / emergency / injection guards |
| `app/dates.py` | Reads Hindi/English date phrases to cross-check the model |
| `app/pipeline.py` | `assess()` (shared by live and eval), `process_inbound()`, reviewer actions |
| `app/store.py` | SQLite: append-only facts, audit log without content, erasure, retention |
| `app/server.py` | API, simulator, signed webhook, live updates; CORS for the hosted dashboard |
| `web/` | The dashboard (static: GitHub Pages / Netlify) and `replay.json` |
| `scripts/record_replay.py` | Re-records `web/replay.json` from the real pipeline |
| `render.yaml`, `netlify.toml`, `.github/workflows/pages.yml` | Hosting |
| `app/assistant.py` | What the next nurse sees (reads the profile only) |
| `eval/` | Golden set (cases and answer key apart) and runner |
| `scripts/send_test_webhook.py` | Signed fake webhook for testing the live path |

## Not built here (on purpose)

Writing replies or suggesting questions (Noora's team is testing that), the medical
history store, clinical facts, voice notes, other countries, household IDs.
