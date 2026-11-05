# Profile writer: first test run

**45 of 49** answer-key items exactly right (value and status).  
**Lasting facts lost:** 0 · **Wrongly stored as permanent:** 0 · **Alerts missed:** 0  
**Loss cases marked as a birth:** 0 of 4 · **Postnatal switch decided right:** 19 of 19 chats · **Births held for a date of birth:** 2  
All outcomes: {"held_too_much": 4, "correct": 45}

| Chat | Field | Expected | Got | Result |
|---|---|---|---|---|
| C01 Husband reports the birth | phone_holder | husband (ready) | husband (review) | held_too_much |
| C01 Husband reports the birth | stage | delivered (ready) | delivered (ready) | correct |
| C01 Husband reports the birth | baby_dob | 2026-11-02 (ready) | 2026-11-02 (ready) | correct |
| C01 Husband reports the birth | delivery_place | government hospital (ready) | government hospital (ready) | correct |
| C01 Husband reports the birth | baby_sex | boy (ready) | boy (ready) | correct |
| C01 Husband reports the birth | num_babies | 1 (ready) | 1 (ready) | correct |
| C01 Husband reports the birth | feeding | breastfeeding (ready) | breastfeeding (ready) | correct |
| C02 Month first, exact date later | edd | 2027-01-14 (ready) | 2027-01-14 (ready) | correct |
| C02 Month first, exact date later | location | Faridpur, Bareilly, Uttar Pradesh (ready) | Faridpur, Bareilly, Uttar Pradesh (ready) | correct |
| C02 Month first, exact date later | symptom | swelling of the feet (alert) | Feet swelling a lot, in the seventh month (alert) | correct |
| C03 Mother-in-law, 'day after tomorrow' | phone_holder | mother-in-law (ready) | mother-in-law (ready) | correct |
| C03 Mother-in-law, 'day after tomorrow' | edd | 2026-11-06 (review) | 2026-11-06 (review) | correct |
| C04 Due date stated, then corrected | edd | 2026-12-02 (ready) | 2026-12-02 (ready) | correct |
| C05 Her sister is the one who's pregnant | feeding | breastfeeding (ready) | breastfeeding (ready) | correct |
| C05 Her sister is the one who's pregnant | baby_sex | boy (ready) | boy (ready) | correct |
| C07 Pregnancy loss | stage | loss (nurse) | loss (nurse) | correct |
| C07 Pregnancy loss | stop_messages | yes (nurse) | yes (nurse) | correct |
| C08 'Last Tuesday', home birth | stage | delivered (ready) | delivered (ready) | correct |
| C08 'Last Tuesday', home birth | baby_dob | 2026-11-03 (review) | 2026-11-03 (review) | correct |
| C08 'Last Tuesday', home birth | delivery_place | home (ready) | home (ready) | correct |
| C08 'Last Tuesday', home birth | baby_sex | girl (ready) | girl (ready) | correct |
| C08 'Last Tuesday', home birth | num_babies | 1 (ready) | 1 (ready) | correct |
| C08 'Last Tuesday', home birth | symptom | home birth, mother and baby not yet checked (alert) | Home delivery by a dai, mother and baby not yet checked by a doctor or nurse (alert) | correct |
| C09 Twins | stage | delivered (ready) | delivered (ready) | correct |
| C09 Twins | baby_dob | 2026-10-28 (ready) | 2026-10-28 (ready) | correct |
| C09 Twins | num_babies | 2 (ready) | 2 (ready) | correct |
| C09 Twins | baby_sex | boys (ready) | boys (ready) | correct |
| C09 Twins | delivery_place | government hospital (ready) | government hospital (ready) | correct |
| C09 Twins | feeding | mixed (ready) | mixed (review) | held_too_much |
| C11 After birth: fever and pain | symptom | fever and lower abdominal pain after delivery (alert) | Fever since yesterday and lower stomach pain after birth (alert) | correct |
| C11 After birth: fever and pain | feeding | mixed (ready) | mixed (review) | held_too_much |
| C12 Language request, staying at her mother's | language | Bhojpuri (ready) | Bhojpuri (review) | held_too_much |
| C12 Language request, staying at her mother's | channel_pref | voice (review) | voice (review) | correct |
| C12 Language request, staying at her mother's | location | Siwan, Bihar (review) | Siwan, Bihar (review) | correct |
| C13 Says outright whose number it is | phone_holder | mother-in-law (ready) | mother-in-law (ready) | correct |
| C13 Says outright whose number it is | symptom | swollen feet (alert) | Feet swelling for two days (alert) | correct |
| C14 The writer changes mid-chat | phone_holder | husband (ready) | husband (ready) | correct |
| C14 The writer changes mid-chat | symptom | back pain at night (alert) | Back pain at night (alert) | correct |
| C15 Born, then passed away | stage | loss (nurse) | loss (nurse) | correct |
| C16 Stillbirth worded as a birth | stage | loss (nurse) | loss (nurse) | correct |
| C17 'I lost the baby' | stage | loss (nurse) | loss (nurse) | correct |
| C18 Birth with no date | stage | delivered (ready) | delivered (ready) | correct |
| C18 Birth with no date | baby_sex | girl (ready) | girl (ready) | correct |
| C18 Birth with no date | num_babies | 1 (ready) | 1 (ready) | correct |
| C19 Hard birth, healthy baby | stage | delivered (ready) | delivered (ready) | correct |
| C19 Hard birth, healthy baby | baby_dob | 2026-11-02 (ready) | 2026-11-02 (ready) | correct |
| C19 Hard birth, healthy baby | baby_sex | boy (ready) | boy (ready) | correct |
| C19 Hard birth, healthy baby | num_babies | 1 (ready) | 1 (ready) | correct |
| C19 Hard birth, healthy baby | symptom | baby admitted to the SNCU (alert) | Baby in the SNCU (alert) | correct |

## Diagnosis
- **C01 phone_holder held for review**: the new rule defines "who holds the phone" as whose phone it is, and Ramesh says who he is but not that the phone is his. Bucket: check. This is a definition question for Kripesh (the phone's owner, or the primary person asking?), so the key is unchanged until he answers.
- **C09 and C11 feeding held for review again**: they flipped back from run 2, which confirms run-to-run variation, not a real change.
- **C12 language held for review**: unchanged; "Bhojpuri, or send audio" reads as one soft request.

## Turn 3: incorporating Kripesh's answers (5 Nov)
What changed: profiles now use the UPE fields (name, language, state, condition_area, EDD, baby DOB, medical notes, high-risk flags, consent, status); 7 new cases (C13–C19) for who holds the phone and loss versus delivery; the extractor prompt got the UPE context and rules for loss vs delivery, births with no date, and whose phone it is; the nurse page now enforces Noora's write rule (ANC_EDD → PNC_DOB only together with a baby DOB).

| Turn | Change | Score | Lasting lost | Wrongly ready | Losses marked as birth | Postnatal switch right | Decision |
|---|---|---|---|---|---|---|---|
| 2 | num_babies rule | 33 / 34 | 0 | 0 | 0 of 1 | — | keep |
| 3 | UPE + new cases + loss/phone rules | 45 / 49 | 0 | 0 | 0 of 4 | 19 of 19 | keep: all 7 new cases correct, all 4 misses are safe "held for review" |

Open: field names and allowed values (onboarding doc); what metadata the intent pipeline writes (Kripesh, cc Shobhit); real de-identified samples in Hindi, Marathi, Telugu, Kannada and Punjabi.
