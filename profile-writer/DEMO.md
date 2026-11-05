# Demo runbook (about 6 minutes of the 10-minute talk)

Audience: Anthropic and CodePath reviewers. Goal: show the step the idea depends on
(message → profile write) working for real, and show where people and code stop the model.

## Before you start (15 minutes ahead)

- [ ] Fresh WhatsApp temporary token in `.env`; `WHATSAPP_LIVE=true`; both phones on `ALLOWED_TEST_NUMBERS`
- [ ] `python3 -m app.server` running; `ngrok http 8000` running; webhook URL updated in Meta if ngrok changed
- [ ] Send `hello_world` to the demo phone and reply "hi" from it, so the 24h window is open and "Live tester" appears
- [ ] Hosted dashboard open → **Connect to live server** (Render URL + token); zoomed to 125%; **Audit & privacy → Reset demo data** pressed
- [ ] A second tab with the same link left in **Replay** mode, ready as the backup
- [ ] Reviewer name filled in on the Reviewer tab
- [ ] Backup: a screen recording of this whole run, in case Wi-Fi or Meta fails
- [ ] Say up front: "Every message, name and number you'll see was written by us. No Noora family data."

## 1. A husband reports the birth (live, from a real phone)

On the demo phone, type into WhatsApp:

> Namaste, main Sunita ka pati bol raha hoon, yeh mera phone hai. Uski delivery 3 November ko ho gayi, beti hui hai. Baby theek se doodh nahi pi rahi.

(Use a named date like this. With Haiku it wrote all three facts 6/6 times. The relative
version, "pichhle mangalvar ko", was held 6/6 times: Haiku often rates its own date maths
"medium" or returns a non-date, and the rules hold both. That makes a good second beat:
send it for another family, then approve it in the Reviewer tab and watch the program flip.)

Point at, in order:
1. **Middle column, Privacy:** the number became a pseudonym; the WhatsApp profile name was discarded.
2. **"Exactly what left this machine":** open it. Only redacted text and the date went to Claude.
3. **Write rules:** each fact shows its quote, highlighted in the message, and every check
   it passed. Note *date maths agree*: our own code read the date independently and
   matched the model.
4. **Profile:** program badge flips **ANC → PNC**. She now gets postnatal messages.
5. **What the next nurse sees:** "Baby's age: 2 days old… don't ask again", and "this phone is usually held by her husband".
6. Type a nurse reply and press Send. It arrives on the phone. Say: "A person pressed Send. There is no other way out."

Then open **6 · Outcome → UPE write record**: condition area ANC_EDD → PNC_DOB and
the baby's DOB in one record, each with its quote and checks. Say: "This is the same
switch Noora's delivery flow makes: condition area and DOB together."

## 2. Unclear means held (simulator, Families B and D)

Family D is on the high-risk campaign (HRPW). Click **High-risk family reports birth** →
Send. Held: "condition area HRPW: no automatic rule yet". People decide high-risk switches.


Click **Vague due date** → Send. Nothing is written: approximate date.
Click **Sister's birth** → Send. Dropped: about someone else.
Click **Sensitive: loss** → Send. Say: "If we got this wrong, a grieving mother gets
newborn-care tips. So code, not the model, catches these words. Everything for this
family pauses and goes to the clinical lane, which our non-clinical reviewers can't clear."

## 3. A reviewer fixes a wrong write, and it becomes a test (Reviewer tab)

Find **Family C · Who holds the phone = mother_in_law** (pre-loaded and labelled as a
seeded example). Read the message aloud: "aaj uska phone mere paas hai" means she only
has the phone *today*. Correct it to **mother**. Scroll down: it is now a candidate
test case, and it can't be exported until someone confirms it's de-identified.

## 4. Controls (10 seconds each)

- **Prompt-injection attempt** (Family A script) → held; "reads like instructions: yes".
- **Kill switch** on → send anything → "extraction paused". Turn it off.
- **Audit & privacy** tab: what leaves the machine, retention, the content-free audit log.

## 5. Results slide

From `eval/out/results-haiku.md` and `eval/findings.md`:

| | Precision | Recall | Wrong writes | Cost / message |
|---|---|---|---|---|
| Keyword baseline (all 26) | 100% | 42% | 0 | $0 |
| Haiku 5.5, all 26 cases | 100% | 81% | 0 | $0.00033 |
| Haiku 5.5, held-out 6 only | 100% | 75% | 0 | |

Say: 26 synthetic cases is small, and we tuned the prompt on 20 of them. The honest
number is the held-out one, and the next step is 100+ cases written by someone else.
At $0.00033 per message, reading every reply from the ~10,000 families who write in each
day would cost about $3.30/day (assuming one message each; more if they send several).

## What isn't real (say it)

Synthetic families; SQLite on a laptop instead of BigQuery and UPE; our golden set is a
draft not yet checked by a Hindi speaker or Niharika; the reviewer roles are a name
prefix, not real access control; Family C's wrong write was pre-loaded.

## If something breaks

| Symptom | Fix |
|---|---|
| Phone message doesn't appear | Check ngrok is up and the webhook URL matches; check the number is on the allowlist; Audit tab shows `dropped_not_allowlisted` or `webhook_rejected_signature` |
| "WhatsApp error 131047" on reply | 24h window closed: reply from the phone first |
| "WhatsApp error 190" | Token expired: paste a new one in `.env`, restart |
| Extractor error in trace | API key or network; switch to `EXTRACTOR=baseline` and say so |
| Anything else | Switch to the Replay tab: same steps, recorded from the real pipeline |
