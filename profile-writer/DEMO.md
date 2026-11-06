# Demo runbook (about 6 minutes)

Show it as the product: this is the nurse's screen. Keep the explanations for the slides.

## Before you start

- [ ] Server running (Render or laptop) with `ANTHROPIC_API_KEY`; hosted page connected (gear → server address + token)
- [ ] Gear → **Reset demo**, so all six families start fresh
- [ ] For WhatsApp: fresh token, `WHATSAPP_LIVE=true`, your phone allowlisted, `hello_world` sent and replied to
- [ ] A second tab with the hosted page **not** connected: it runs the offline demo, as the backup
- [ ] Browser zoom 110–125%

## 1. Sunita: the husband reports the birth (about 10 seconds to process)

Open **Sunita Devi**. From the demo phone on WhatsApp (or **Family phone** → first suggestion):

> Namaste, main Sunita ka pati bol raha hoon, yeh mera phone hai. Uski delivery 3 November ko ho gayi, beti hui hai. Baby theek se doodh nahi pi rahi.

Watch: "Copilot is reading" → the **Profile updated** notice in the chat → Health Information
now shows *pnc*, Baby DOB, baby age, *Who holds the phone: Husband* (each "from chat") → the
summary at the top rewrites itself → a draft reply in Hindi that treats poor feeding as a
reason to go to hospital and doesn't ask for anything the family already said.
Press **Use reply** → **Send**. A person always presses Send.

Optional: **How it was processed** tab → each fact, the rules it passed, the AI judge's answer.

## 2. Meena: unclear, then clear

**Family phone**: "Doctor ne bola delivery shayad January end tak hogi…" → nothing saved;
the draft asks for the exact date. Then "Doctor ne ab 25 January ki date di hai" → due date
saved. Then "Meri behen ki delivery kal hui…" → nothing changes: it's her sister.

## 3. Pooja: the AI wasn't sure, so the nurse decides

**Needs check** filter → **Pooja Sharma** → *Check before saving: Who holds the phone:
Mother-in-law*, with the words highlighted and the reason. **Confirm** (or **Edit**). Her
decision becomes a new test case for the judge. Then "Baby ko kal raat se bukhar hai…" → the
draft tells them to go to hospital today.

## 4. Kavya and Rekha: never automatic

**Kavya R** (high-risk campaign) reports a birth → **Clinical review**: the campaign isn't
switched by the system. **Rekha Yadav**: "Doctor ne bataya bachcha pet mein hi nahi raha…" →
**Possible pregnancy loss**, updates paused, and the draft offers condolences only.

## Say before anyone asks

Synthetic families and messages. The Copilot reply is a stand-in for Noora's own Copilot and
its clinical wording isn't signed off. Pooja's open check was pre-loaded. The eval set is small
and written by us.

## If something breaks

| Symptom | Fix |
|---|---|
| Phone message never appears | Webhook URL / allowlist; gear shows the connection |
| "Copilot is reading" for more than 30 s | Model call failed or spend cap hit; carry on in the offline tab |
| WhatsApp error 131047 on Send | 24-hour window closed: reply from the phone first |
| Anything else | Switch to the offline tab: same screens, recorded from the real pipeline |
