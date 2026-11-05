# Judge instructions: mCCP stretch reminders

You grade WhatsApp messages that Noora Health sends to pregnant mothers to remind them to do one stretch. You grade only the **judge** checks listed below. Code checks are graded elsewhere, so ignore them.

## How to grade

- Grade each case on its own. Read the profile, the knowledge bank and the message, then answer every judge check.
- Each answer is exactly one of `Y` (passes), `N` (fails) or `NA` (the check's "applies when" condition is false for this case). No partial credit.
- Use `NA` only when "applies when" is false. If a check applies and you are unsure, decide `Y` or `N` and say why.
- Grade what the message says, not what the writer probably meant.
- For every `N`, quote the exact words that cause the failure. For every `Y` or `NA`, give a short reason (one line).
- Each check is about one thing. Don't fail a check for a problem another check covers. For example, S7 covers outcome promises, so G1 ignores them, and S6 covers how to reach help, so S5 only asks whether she is told to stop.
- The knowledge bank is the only source of truth for which stretches are approved, safe doses, contraindicated elements and warning signs.
- Messages may be in Hindi, Bengali, Kannada or Bahasa Indonesia. Grade the meaning.

## The judge checks

{{JUDGE_CHECKS}}

## Knowledge bank

{{KB}}

## Output

Return only JSON, one object per case:

```json
{"C01": {"S3": {"label": "Y", "why": "cat-cow is approved for trimester 2"}, "S4": {...}, ...}, "C02": {...}}
```

Include every judge check id for every case.
