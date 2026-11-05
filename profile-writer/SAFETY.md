# Safety and privacy design

This prototype handles maternal and child health conversations from families in India,
many with low literacy, on shared phones. Below: how data moves, what can go wrong, and
which defences only *ask* (a prompt) versus *enforce* (code, permissions, schema). Every
serious risk has at least one enforcing layer.

Status: prototype on synthetic data. Nothing here has been reviewed by Noora's clinical,
legal or data-protection owners yet; open questions are listed at the end. **This is
not legal advice.**

## 1. What it does, and what it never does

**Does:** reads a family's WhatsApp message and proposes up to four profile fields: who
usually holds the phone, whether she has delivered, the baby's birth date, and her due
date. Plain-code rules decide whether each proposal is written, held for a person, or
dropped. Every value keeps the exact words it came from and can be undone.

**Never:** replies to a family; gives medical advice; writes clinical facts (conditions,
medications, loss); changes anything when a pregnancy loss or death is mentioned; sends
a message without a person pressing Send; processes a number that is not on the test
allowlist.

## 2. How data moves

```
 Family phone ──WhatsApp──▶ Meta Cloud API ──signed POST──▶ /webhook
                                                            │ 1 signature check (reject if unsigned)
                                                            │ 2 allowlist check (drop unread if not a test phone)
                                                            │ 3 phone → keyed pseudonym; WhatsApp profile name dropped
                                                            ▼
                                                    store message (kept 72h)
                                                            │ 4 redact numbers, Aadhaar, email, PIN, links
                                                            │ 5 keyword guards: loss, emergency, instruction-like text
                                                            │ 6 gates: consent, kill switch, token cap, hourly limit
                              ┌─────────────────────────────┘
          leaves the machine: │ redacted message + ≤3 earlier redacted messages + message date
                              ▼
                       Claude (one forced tool: record_signals; no other tools)
                              │ JSON proposals → schema check in code
                              ▼
                       write rules (code) ──▶ write / hold / discard
                              │
             profile store (append-only, with quote) ──▶ program ANC→PNC (code)
                              │
     ┌────────────────────────┼─────────────────────────────┐
  nurse view (reads only)   reviewer queue (non-clinical,   clinical lane (loss / death
                            sees 1 redacted message)         mentions; pauses the family)
                              │
                     corrections → candidate test cases (exported only once marked de-identified)
```

## 3. Harm check (Claude Corps five failure modes)

| Failure mode | Risk | Harm to | Mitigation (E = enforced, A = asked) | Next step |
|---|---|---|---|---|
| **Exposed private data** | Phone numbers, names or health details leak through logs, prompts, screenshots or the reviewer view | Families; Noora's trust and legal standing | E: pseudonym on arrival; number stored in one table, shown masked. E: regex redaction before the API. E: WhatsApp profile name never read. E: audit log has no message text. E: messages deleted after 72h; erase-on-request. E: reviewers see one redacted message, not the chat. E: dashboard token, `HttpOnly` cookie, CSRF header, bound to localhost. | Names and villages in free text are **not** redacted: ask Sreeram whether Noora has an NER step; confirm zero-data-retention terms for Noora's API account. |
| | Real family data gets into the demo, eval or slides | Families | E: live mode only processes allowlisted test phones; others dropped unread. E: golden candidates can't be exported until marked de-identified. A: CLAUDE.md rule for coding agents. | Kripesh (Nov 5, in writing): de-identified or paraphrased messages may go to Claude; real production messages stay inside Noora's systems. His real samples go in the git-ignored `eval/golden/noora/`, never in a zip or slide. [ASK] Does "inside our systems" allow Claude under Noora's own API account or cloud, or does production need another route? |
| **Said the wrong thing** | Wrong birth date or stage written → wrong messages for weeks | Mother and baby | E: quote must be found in the message. E: our own date maths must agree with the model's within 1 day. E: approximate dates held. E: plausibility (birth not in the future, not >1 year ago, within -10/+4 weeks of due date). E: conflicts with the profile held. E: medium confidence held, low dropped. E: every write reviewed afterwards; revert restores the program. | Kripesh/Niharika: per signal, is a wrong write or a missed write worse? This sets the thresholds. |
| | Facts about someone else (a sister's delivery) land on her profile | Mother | E: `subject` must be the registered mother, else dropped. Eval has 4 such cases. | Add more relative/neighbour phrasings once real examples exist. |
| | Baby-care messages after a stillbirth or neonatal death (Kripesh: "the mistake that actually hurts") | Mother, at her most vulnerable | E: keyword guard (Hinglish, Devanagari, English; **draft** Marathi, Kannada, Telugu, Punjabi) **plus** model flag; 14 loss-vs-delivery eval cases, including twins where one died; either one holds everything in a clinical lane and pauses automatic updates for that family. Non-clinical reviewers can't clear it. | Niharika to review the word list and the clinical-lane process; decide what the program should do. |
| | Wrong campaign switch | Mother | E: only ANC_EDD → PNC_DOB, and only written together with the baby's DOB in one transaction, as Noora's delivery flow does. HRPW, SNCU and others are never switched; a new due date on PNC_DOB is held (may be a new pregnancy). E: every switch is in a UPE write record and undone if the DOB is reverted. | MSEs confirm with the family before switching by hand (SOP). Here the family's own words are the confirmation; vague ones are held. Kripesh to agree. |
| **Did the wrong thing** | Auto-sends to a family | Families | E: no code path sends without `/api/reply` from a person; 24h window and allowlist checked again at send time. | Keep as a hard rule in production. |
| | Prompt injection in a message changes the profile | Mother | E: model has one tool that only records; schema check in code; every proposal passes the same rules. E: instruction-like text → any write held. A: prompt says the chat is data. | Red-team set of 20 injections in Hindi and English. |
| | Forged webhook calls inject fake messages | Families | E: `X-Hub-Signature-256` HMAC check with constant-time compare; duplicates ignored by message ID. | Rotate the app secret after the demo. |
| **Didn't do what it should** | Extractor down → profile silently stale | Families | E: errors logged and shown in the trace; nothing written on error; existing flows still work (the tool only adds). | Alert on error rate in production. |
| | Emergency message gets only extraction | Mother, baby | E: emergency words flagged in the trace; this tool never replies and leaves triage to Noora's existing pipeline. | Confirm with Sreeram that the existing emergency pipeline runs first and independently. |
| | Family wants out | Families | E: `STOP` stops processing; `delete my data` erases everything except a content-free audit line. | Align with Noora's existing opt-out flow and consent text. |
| **Cost too much** | Loops, floods or long messages run up the bill | Noora | E: one retry max; daily token cap; per-family hourly limit; message length cap; 800 max output tokens. | Spend cap and alert on the Console account; named budget owner. |

### Hosted dashboard

| Risk | Mitigation |
|---|---|
| Public page exposes data | The page holds no secrets. Replay is a recorded run on synthetic chats; the build refuses to publish anything that looks like a key. |
| Someone else's site calls our server | E: CORS only for `ALLOWED_ORIGINS`; every API call needs the access token in a header (constant-time compare); POSTs also need a custom header. |
| Token leaks | Typed in at demo time, kept in that browser tab only (sessionStorage), sent in a header, never in a URL; the server never logs query strings. Rotate it after the demo. |

## 4. Defence layers

Only **asks:** the system prompt (chat is data, copy exact words, be unsure when unsure).

**Enforces:** forced single tool and JSON schema; schema validation in code; quote check;
date cross-check; plausibility and conflict rules; subject rule; keyword guards for loss,
emergency and injection; rollout mode (shadow / review-first / auto + audit); kill switch;
allowlist; webhook signature; pseudonyms; redaction; retention purge; erasure; token cap
and rate limits; reviewer roles (clinical lane); human-only sending.

## 5. Rollout ladder

1. **Shadow:** extract and log, write nothing. Compare with what MSEs asked and the families answered.
2. **Review first:** every write waits for a reviewer. Measures reviewer load and agreement.
3. **Auto + audit:** confident writes go live, every write reviewed afterwards; held items wait.

Move up a step only when the eval meets the target on a held-out set written by someone
other than the person tuning the prompt (target from Kripesh: ≥90% precision, ≥80%
recall on core signals), **and** the safety cases (loss, someone else, injection,
temporary phone) pass 100%.

## 6. India's DPDP law

The DPDP Act 2023 is in force, and the DPDP Rules 2025 were notified on 14 Nov 2025 in
phases. Most duties (Rules 3, 5–16) start 18 months after publication, around May 2027.
Building to them now is cheaper than retrofitting.

| Topic | What the Rules say (summary) | What the prototype does | Open |
|---|---|---|---|
| Consent and notice (Rule 3) | Clear notice: what data, purpose, how to withdraw | Assumes Noora's onboarding consent; `STOP` honoured | Does Noora's consent text cover building a profile from chat? [ASK Kripesh] |
| Security (Rule 6) | Encryption, access control, logging, backups | Pseudonyms, access token, audit log | Encryption at rest is Noora's infra (BigQuery) |
| Retention and erasure (Rule 8) | Delete when purpose served; keep logs ≥1 year | 72h message retention; erasure; content-free audit | Retention period for chat text [ASK] |
| Children's data (Sec. 9, Rules 10 and 12) | Verifiable parental consent; no tracking or behavioural monitoring of children. Healthcare providers have a narrow exemption, limited to what's needed for health services | Baby DOB is a child's data, used only to time health messages; no other use | Does Noora's exemption cover this use? Mothers may themselves be under 18; the profile must not infer age [ASK Noora legal] |
| Cross-border transfer (Rule 15) | Allowed except where restricted by government | Redacted text goes to the Anthropic API | Confirm processing location and terms for Noora's account [ASK] |
| Breach notice (Rule 7) | Tell affected people and the Board promptly | Not in prototype | Noora's existing breach process |

## 7. Anthropic Usage Policy

The current policy (effective 12 Nov 2026) lists Medical among high-risk areas. For
*high-risk AI recommendations* (diagnosing, recommending or changing treatment), a
qualified person must meaningfully review before delivery, and people must be told AI
was used. This extractor makes no recommendations: it records facts for the profile. The
Copilot that reads the profile does draft advice, and Noora's MSE approval of every reply
is the qualified human review. **Ask Kripesh** how families are told that AI helps draft
replies.

## 8. Known limits (say these in the demo before anyone asks)

- Keyword guards for Marathi, Kannada, Telugu and Punjabi are drafts written without a
  native speaker. Haiku's own flag caught every loss case in those languages in our eval,
  but the code backup needs review before it counts.
- Code date cross-checks only read English and Hindi; in other scripts the rules fall back
  to the model's date, which must still be "exact day" and "high".
- Who is *writing* (not who owns the phone) is right only 1 time in 4 in our eval: the model
  confuses the owner named in the message with the writer. Not used for any write.

- Synthetic chats written by us. The golden set is a draft until Moud and a Hindi
  speaker check it, and the held-out part should be written by someone who never sees
  the prompt.
- Text messages only (no voice, which many families use). India, Hindi/Hinglish only.
- One phone = one family. Households that share or switch numbers aren't handled.
- Keyword guards will miss some phrasings and raise some false alarms.
- Reviewer fatigue and bias are not measured yet. Track agreement between two reviewers on a sample.
- SQLite and a laptop server: fine for a demo, not for 65k daily users.

## 9. Sources

- DPDP Rules 2025 phasing and duties: [SCC Online, key highlights](https://www.scconline.com/blog/post/2025/12/26/digital-personal-data-protection-rules-2025-key-highlights/)
- Healthcare exemption for children's data: [Storyboard18](https://www.storyboard18.com/digital/dpdp-rules-carve-out-key-exemptions-for-healthcare-providers-schools-and-childcare-services-processing-childrens-data-84208.htm)
- Anthropic Usage Policy: [anthropic.com/legal/aup](https://www.anthropic.com/legal/aup)
- WhatsApp webhook signing and payloads: [Webhook Relay guide](https://webhookrelay.com/blog/whatsapp-cloud-api-webhooks/)
