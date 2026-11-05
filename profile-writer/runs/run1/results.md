# Profile writer: first test run

**30 of 34** answer-key items exactly right (value and status).  
**Lasting facts lost:** 1 · **Wrongly stored as permanent:** 0 · **Alerts missed:** 0  
All outcomes: {"correct": 30, "missed": 1, "held_too_much": 3, "extra": 1}

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
| C02 Month first, exact date later | symptom | swelling of the feet (alert) | Feet swelling a lot in seventh month of pregnancy (alert) | correct |
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
| C08 'Last Tuesday', home birth | num_babies | 1 (ready) | — (—) | missed |
| C08 'Last Tuesday', home birth | symptom | home birth, mother and baby not yet checked (alert) | Home delivery with no check yet of mother and newborn by a doctor or nurse (alert) | correct |
| C09 Twins | stage | delivered (ready) | delivered (ready) | correct |
| C09 Twins | baby_dob | 2026-10-28 (ready) | 2026-10-28 (ready) | correct |
| C09 Twins | num_babies | 2 (ready) | 2 (ready) | correct |
| C09 Twins | baby_sex | boys (ready) | boys (ready) | correct |
| C09 Twins | delivery_place | government hospital (ready) | government hospital (ready) | correct |
| C09 Twins | feeding | mixed (ready) | mixed (review) | held_too_much |
| C11 After birth: fever and pain | symptom | fever and lower abdominal pain after delivery (alert) | Fever since yesterday (alert) | correct |
| C11 After birth: fever and pain | feeding | mixed (ready) | mixed (review) | held_too_much |
| C11 After birth: fever and pain | symptom | — | Lower stomach pain after delivery (alert) | extra |
| C12 Language request, staying at her mother's | language | Bhojpuri (ready) | Bhojpuri (review) | held_too_much |
| C12 Language request, staying at her mother's | channel_pref | voice (review) | voice (review) | correct |
| C12 Language request, staying at her mother's | location | Siwan, Bihar (review) | Siwan (review) | correct |

## Diagnosis (Eval 201 buckets)
- **C05 baby_sex = boy**: the extractor was right ("My son is feeding well" is her own baby). Bucket: check. The answer key was wrong and is now fixed.
- **C08 num_babies missed**: "a baby girl" implies one baby, but the prompt never says to record singletons. Bucket: prompt. Next change: "If a birth is reported, always record num_babies."
- **Held for review (C09 and C11 feeding, C12 language)**: safe but slower; the nurse clicks "Checked, save". Bucket: prompt. Only loosen this if the clinical team agrees.
- **C11 two alerts**: the fever-and-pain alert came out as two items. Harmless; the nurse sees both.

Traps passed: the sister's pregnancy (C05), the mother's own birth date (C10), the pregnancy loss (C07), "last night" (C01), the corrected due date (C04), "day after tomorrow" (C03), "last Tuesday" (C08), the temporary location (C12), and the month-only due dates (C02, C10).
