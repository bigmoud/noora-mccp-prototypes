You read one WhatsApp conversation between a family and Noora Health's nurses, plus the mother's current profile. List every fact the conversation gives about THIS mother or her baby that belongs on her profile, and every symptom a nurse should see now.

## Fields (use these names and value formats exactly)
- phone_holder: mother | husband | mother-in-law | other relative
- stage: pregnant | delivered | loss
- baby_dob: YYYY-MM-DD
- edd: YYYY-MM-DD (expected due date)
- language: the language she wants messages in (e.g. Hindi, Bengali, Bhojpuri, English)
- channel_pref: text | voice
- location: Village, District, State (as much as is given)
- delivery_place: government hospital | private hospital | home
- baby_sex: boy | girl | boys | girls | boy and girl
- num_babies: 1 | 2 | 3
- feeding: breastfeeding | formula | mixed
- stop_messages: yes
- symptom: a short description (only for the "alert" status)

## Status for each item
- ready: clearly stated about her or her baby and lasting. Safe for a nurse to save with one click.
- review: probably right but a person should check first: relative or ambiguous dates, soft preferences, temporary situations, or a value that disagrees with her profile and isn't clearly a correction.
- nurse: sensitive. Never saved automatically: a pregnancy loss, a request to stop messages.
- alert: a current symptom or situation a nurse should act on now. Never saved to the profile.

## Rules
- Only facts about THIS mother and her baby. Facts about other people (a sister, a neighbour) are not hers.
- Work out dates from the message's own timestamp. "Last night" or "yesterday" in a message sent on 3 Nov means 2 Nov. "Day after tomorrow" and "last Tuesday" are relative, so mark them review.
- "Seventh month" or "six months done" is not a due date. Don't invent one.
- If she corrects herself, use the latest value only.
- The mother's own date of birth is not the baby's date of birth and is not a field.
- A clear new value from her or her doctor that replaces what's on file is ready. Put the old value in "replaces".
- Temporary situations (staying at her mother's house for the birth) are review, never ready.
- Today's symptoms (fever, pain, swelling) are alerts, never profile facts.
- When a birth is reported, always record num_babies: 1 unless she says twins or more.
- If there is nothing to extract, return an empty list.

## Output
Return only JSON:
{"items":[{"field":"...","value":"...","status":"ready|review|nurse|alert","speaker":"mother|husband|mother-in-law|other relative|unknown","evidence":"exact words from the message","msg":<message number>,"confidence":"high|medium|low","why":"one short sentence","replaces":"old value or null"}]}
