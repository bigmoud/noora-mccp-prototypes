# Panel deck content: Noora Profile Writer

Source: PRD - Noora Health, the discovery and problem-statement docs, the "MCCP user engagement strategies" call notes, and profile-writer/results.md (turn 2). Presenter split is a suggestion: swap as you like.

## Slide 1: plan (delete before presenting)
| Part | Slides | Presenter | Min |
|---|---|---|---|
| 1. Host organization | 3 | Moud | 0.5 |
| 2. The problem | 4 and 5 | Moud | 2.5 |
| 3. Your approach | 6 | Shaheer | 1.5 |
| 4. The prototype | 7 | Shaheer | 3.5 |
| 5. Measuring success | 8 | Moud | 1 |
| 6. What we learned | 9 | Shaheer | 1 |

## Slide 2: title (already filled)
Noora Profile Writer · Reads WhatsApp convos to build profiles for quicker responses · Moud and Shaheer · Noora Health

## Slide 3: Host organization
**Headline:** Noora Health helps families care for mothers and newborns at home, through nurses on WhatsApp.
- **Who they are:** A nonprofit that trains family caregivers to care for their loved ones in hospital and after they go home.
- **What they do:** The Care Companion Program trains families in hospitals. The Mobile Care Companion continues on WhatsApp in 11 languages. 2 million families have used it; 65–70k get messages every day, and about 1,000 a day send real medical questions to nurses.
- **Who we worked with:** Kripesh (product lead), with Niharika (clinical) and Sreeram (engineering). Our users are the nurses who answer families, and the AI copilot that drafts their replies.
- Footer: About 30 seconds · Presenter: Moud

## Slide 4: The problem
**Statement:** When a nurse asks a family for missing details, what the family shares, like a delivery, a past miscarriage or a medication, stays in that one chat and never reaches her profile. So the nurse and the copilot start from zero next time, ask again, and risk losing her to drop-off.
- **Impact:** The profile holds only 5 fields. Replies in India already average about 69 hours, so every repeat question adds days. 405 families who told Noora they'd delivered still get pregnancy messages.
- **Evidence:** "We know a lot about our users and use almost none of it."  41% of the times the team asked for a basic fact, the profile already had it.
- **Source:** Kripesh, discovery conversation, 2 Nov 2026
- Footer: About 1.5 minutes · Presenter: Moud

## Slide 5: Today's journey
**Headline:** Today, a nurse takes 5 steps to answer one question, and the next nurse starts over.
1. A mother, or her husband on his phone, writes: "My baby isn't feeding well. She was born last Tuesday."
2. The copilot checks for emergencies and drafts a reply from a 5-field profile and the FAQ bank.
3. The nurse asks for missing details: the baby's age, whether she's breastfeeding.
4. The family answers, the nurse replies, and the chat closes.
5. The birth date stays buried in the chat. The profile still says "pregnant".
**Where it breaks:** Step 5. Nothing is written back, so pregnancy messages keep coming and the next nurse asks again.
- Footer: About 1 minute · Presenter: Moud

## Slide 6: Our approach
**Headline:** We built a profile writer because every other fix depends on a profile that remembers.
- **The idea, and why:** Claude reads the conversation, pulls out each fact with the family's exact words, and sorts it: lasting facts are one click for the nurse to save, unclear ones wait for a check, symptoms go to a nurse and are never saved. Personalized messages and AI-direct replies both need this first.
- **The limits:** Simulated chats only until Kripesh confirms what can go to Claude (DPDP consent). Staff-only: nothing messages families. A nurse confirms every save. Niharika signs off anything clinical.
- **Cost to run:** About 1 cent per conversation on Claude Sonnet, about $300 a month at 1,000 chats a day. A smaller model would cut that a lot; we'd only switch if it passes the same test. (Estimate from token counts, not yet measured at scale.)
- **What Noora gets back:** Fewer repeat questions (41% of asks today), faster replies, and families moved to postnatal messages as soon as a birth is mentioned.
- Footer: About 1.5 minutes · Presenter: Shaheer

## Slide 7: The prototype
**Headline:** With the profile writer, a nurse saves what a family said in one click instead of asking again.
- [Live demo: https://claude.ai/artifact/EBMnS7kcrZZy5EgmvtQ5Hf · share it before the panel]
- **The journey we'll demo:**
  1. Open Sunita's chat: her husband writes "She delivered last night… It's a boy!"
  2. Claude fills the table: delivered, born 2 Nov, husband holds the phone, government hospital, breastfeeding, each with his exact words.
  3. Click "Save all ready facts": she moves from pregnancy to postnatal messages.
  4. Open Pooja's chat (a pregnancy loss): nothing can be saved, only "Send to nurse".
  5. Result: 33 of 34 facts right on our 12 test chats, and 0 wrong facts marked ready to save.
- **What's not real:** All 12 conversations, names and places are invented, in English. No real family data. The saved test run replays scored results; live scanning uses your own Claude account.
- Footer: About 3.5 minutes · Presenter: Shaheer

## Slide 8: How we'd measure success
**Headline:** It's working if repeat asks for facts Noora already has fall from 41% to about 20%.
| Signal | Today | Target | How we'd check |
|---|---|---|---|
| Repeat asks for facts already on file | 41% | Halved in the pilot group by Month 6 | Compare nurse questions with the profile, pilot vs. control |
| Lasting facts kept and correct (core signals) | No baseline | ≥90% precision, ≥80% recall by Month 3 | Answer key checked by Niharika's team; our first run: 33 of 34 |
| Wrong facts saved | — | 0 one-click saves of a passing symptom or someone else's fact | Every miss logged; nurses confirm each save |
- Footer: About 1 minute · Presenter: Moud

## Slide 9: What we learned
**Headline:** The hard part isn't reading the chat; it's knowing which facts should last.
- **About the problem:** The copilot already summarizes each chat, then throws the summary away. And who holds the phone matters: 41,520 phones belong to a husband or relative.
- **About the process:** Writing the answer key before building caught our own mistakes. The extractor was right once where our key was wrong. One change at a time took us from 30 to 33 of 34.
- **What we'd change:** Get 20–30 paraphrased real messages from Noora on day one, and a Hindi speaker to check them. We don't yet know how it does in Hindi or Hinglish.
- Footer: About 1 minute · Presenter: Shaheer

## Slide 10: Panel feedback
Questions and feedback · Noora Health pod (Moud and Shaheer) · https://claude.ai/artifact/EBMnS7kcrZZy5EgmvtQ5Hf
