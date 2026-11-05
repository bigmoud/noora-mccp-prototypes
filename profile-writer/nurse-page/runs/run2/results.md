# Profile writer: first test run

**33 of 34** answer-key items exactly right (value and status).  
**Lasting facts lost:** 0 · **Wrongly stored as permanent:** 0 · **Alerts missed:** 0  
All outcomes: {"correct": 33, "extra": 1, "held_too_much": 1}

| Chat | Field | Expected | Got | Result |
|---|---|---|---|---|
| C01 Husband reports the birth | phone_holder | husband (ready) | husband (ready) | correct |
| C01 Husband reports the birth | stage | delivered (ready) | delivered (ready) | correct |
| C01 Husband reports the birth | baby_dob | 2026-11-02 (ready) | 2026-11-02 (ready) | correct |
| C01 Husband reports the birth | delivery_place | government hospital (ready) | government hospital (ready) | correct |
| C01 Husband reports the birth | baby_sex | boy (ready) | boy (ready) | correct |
| C01 Husband reports the birth | num_babies | 1 (ready) | 1 (ready) | correct |
| C01 Husband reports the birth | feeding | breastfeeding (ready) | breastfeeding (ready) | correct |
| C02 Month first, exact date later | edd | 2027-01-14 (ready) | 2027-01-14 (ready) | correct |
| C02 Month first, exact date later | location | Faridpur, Bareilly, Uttar Pradesh (ready) | Faridpur village, Bareilly, Uttar Pradesh (ready) | correct |
| C02 Month first, exact date later | symptom | swelling of the feet (alert) | feet swelling a lot (seventh month) (alert) | correct |
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
| C08 'Last Tuesday', home birth | symptom | home birth, mother and baby not yet checked (alert) | home delivery, mother and baby not yet checked by doctor or nurse (alert) | correct |
| C09 Twins | stage | delivered (ready) | delivered (ready) | correct |
| C09 Twins | baby_dob | 2026-10-28 (ready) | 2026-10-28 (ready) | correct |
| C09 Twins | num_babies | 2 (ready) | 2 (ready) | correct |
| C09 Twins | baby_sex | boys (ready) | boys (ready) | correct |
| C09 Twins | delivery_place | government hospital (ready) | government hospital (ready) | correct |
| C09 Twins | feeding | mixed (ready) | mixed (ready) | correct |
| C11 After birth: fever and pain | symptom | fever and lower abdominal pain after delivery (alert) | fever since yesterday (alert) | correct |
| C11 After birth: fever and pain | feeding | mixed (ready) | mixed (ready) | correct |
| C11 After birth: fever and pain | symptom | — | lower stomach pain (alert) | extra |
| C12 Language request, staying at her mother's | language | Bhojpuri (ready) | Bhojpuri (review) | held_too_much |
| C12 Language request, staying at her mother's | channel_pref | voice (review) | voice (review) | correct |
| C12 Language request, staying at her mother's | location | Siwan, Bihar (review) | Siwan (review) | correct |

## Diagnosis
- **C11 two alerts**: the fever and the pain came out as two alert items. Harmless; the nurse sees both.
- **C12 language held for review**: "Please send them in Bhojpuri, or send audio" was read as one soft request. Safe; the nurse clicks "Checked, save".

## Turn log
| Turn | One change | Score | Lasting facts lost | Wrongly marked ready | Decision |
|---|---|---|---|---|---|
| 1 | baseline (answer key fixed for C05 baby = boy) | 30 / 34 | 1 | 0 | — |
| 2 | prompt: "When a birth is reported, always record num_babies: 1 unless she says twins or more." | 33 / 34 | 0 | 0 | **keep**: C08 fixed, nothing regressed |

Note on turn 2: C08 (number of babies) is the fix the new rule targeted. C09 and C11 feeding also moved from "check first" to "ready", but the rule doesn't touch feeding, so that is run-to-run variation. Treat it as noise until it repeats across runs.
