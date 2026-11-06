"""The latest thing the family says about the baby's birth wins (Shaheer, Nov 6).

"My baby is one day old" on Monday, then "sorry, my baby is actually 3 months old" on
Tuesday: the profile must move to the newer answer, not keep the old one. A wrong birth date
sends the wrong newborn messages for weeks, so a known-wrong exact date is worse than an
honest approximate one. Approximate dates are marked as such and the family is still asked
for the exact day. What still goes to a nurse: a big due-date change (g10) and a
"delivered" profile told the baby isn't born yet."""
import os
import unittest
from datetime import date

os.environ.setdefault("PSEUDONYM_KEY", "test-key")

from app import dates, judge, privacy, rules  # noqa: E402
from app.extractor import Extraction  # noqa: E402
from app.pipeline import NEEDED_TEXT, process_inbound, route_of  # noqa: E402
from app.store import Store  # noqa: E402

FRI = date(2026, 11, 6)


def prop(signal, value, evidence, **kw):
    p = dict(signal=signal, value=value, subject="registered_mother", evidence=evidence, date_phrase=evidence,
             date_precision="exact_day", confidence="high", note="")
    p.update(kw)
    return p


def decide(props, text, profile):
    return {d.signal: d for d in rules.decide(props, text, FRI, profile, sensitive=False, family_paused=False,
                                              rollout_mode="auto_with_audit")}


class AgePhrases(unittest.TestCase):
    def test_ages_become_birth_dates(self):
        self.assertEqual(dates.age_to_dob("my baby is one day old", FRI), (date(2026, 11, 5), 0))
        self.assertEqual(dates.age_to_dob("10 din ka hai", FRI), (date(2026, 10, 27), 0))
        self.assertEqual(dates.age_to_dob("actually 3 months old", FRI), (date(2026, 8, 6), 15))
        self.assertEqual(dates.age_to_dob("beti teen mahine ki hai", FRI)[0], date(2026, 8, 6))
        self.assertIsNone(dates.age_to_dob("I am 24 years old", FRI))
        self.assertIsNone(dates.age_to_dob("3 mahine mein miscarriage", FRI))


class Rules(unittest.TestCase):
    def test_approximate_age_replaces_a_birth_date_that_no_longer_fits(self):
        text = "Sorry, my baby is actually 3 months old"
        d = decide([prop("baby_dob", "2026-08-06", "3 months old", date_precision="approximate")], text,
                   {"stage": "delivered", "baby_dob": "2026-11-05"})["baby_dob"]
        self.assertEqual(d.action, "write")
        self.assertEqual(d.value, "2026-08-06")  # code's own reading of "3 months old"
        self.assertEqual(d.precision, "approximate")
        self.assertEqual(route_of(d), "judge")  # still checked by the judge, not written blind

    def test_an_age_code_cannot_read_is_never_written(self):
        # Found by a spot check on Nov 6: the judge once confirmed a value 3 months off. The date
        # for a correction is code's own reading of the age; if code can't read it, ask the family.
        d = decide([prop("baby_dob", "2026-05-06", "a few months old", date_precision="approximate")],
                   "Sorry, she is a few months old", {"stage": "delivered", "baby_dob": "2026-11-05"})["baby_dob"]
        self.assertEqual(route_of(d), "ask_family")

    def test_approximate_age_that_fits_the_date_on_file_changes_nothing(self):  # golden g23
        d = decide([prop("baby_dob", "2026-10-05", "ek mahine ki", date_precision="approximate")],
                   "Beti ab ek mahine ki ho gayi", {"stage": "delivered", "baby_dob": "2026-10-04"})["baby_dob"]
        self.assertEqual(d.action, "same")

    def test_approximate_with_nothing_on_file_still_asks_for_the_day(self):  # golden g12
        d = decide([prop("baby_dob", "2026-10-23", "2 hafte pehle", date_precision="approximate")],
                   "Baby 2 hafte pehle hua", {"stage": "pregnant"})["baby_dob"]
        self.assertEqual(route_of(d), "ask_family")

    def test_exact_correction_goes_to_the_judge_not_the_nurse(self):
        text = "Sorry galat bataya tha, baby 3 August ko hua tha"
        d = decide([prop("baby_dob", "2026-08-03", "3 August")], text,
                   {"stage": "delivered", "baby_dob": "2026-11-05"})["baby_dob"]
        self.assertEqual(route_of(d), "judge")

    def test_one_day_old_is_an_exact_day(self):
        d = decide([prop("baby_dob", "2026-11-05", "one day old")], "My baby is one day old", {"stage": "pregnant"})
        self.assertEqual(d["baby_dob"].action, "write")
        self.assertIn("code reads", " ".join(c[2] for c in d["baby_dob"].checks))

    def test_big_due_date_change_still_goes_to_a_nurse(self):  # golden g10
        d = decide([prop("due_date", "2027-01-15", "15 January")], "Asli due date 15 January hai",
                   {"stage": "pregnant", "due_date": "2026-12-10"})["due_date"]
        self.assertEqual(route_of(d), "nurse")

    def test_delivered_back_to_pregnant_still_goes_to_a_nurse(self):
        d = decide([prop("stage", "pregnant", "he will be born next month", date_precision="none")],
                   "he will be born next month", {"stage": "delivered", "baby_dob": "2026-11-05"})["stage"]
        self.assertEqual(route_of(d), "nurse")


class Scripted:
    """Stands in for the extractor: returns the signals a test gives it."""
    def __init__(self, *signals):
        self.signals = list(signals)

    def extract(self, text, msg_day, context=None):
        return Extraction("mother", False, self.signals, "scripted")


def confirm_all(text, msg_day, context, profile, proposals, model=None):
    return judge.JudgeRun([judge.Judgement("confirm", reason="test") for _ in proposals], judge="judge:test")


class Pipeline(unittest.TestCase):
    def setUp(self):
        real = judge.judge
        judge.judge = confirm_all
        self.addCleanup(setattr, judge, "judge", real)
        self.s = Store(":memory:")
        self.uid = privacy.pseudonym("sim-correction")
        self.s.upsert_family(self.uid, "C", "ANC_EDD")

    def test_next_day_correction_updates_the_profile(self):
        process_inbound(self.s, self.uid, "My baby is one day old", ts="2026-11-05T10:00:00+00:00",
                        extractor=Scripted(prop("baby_dob", "2026-11-04", "one day old")))
        self.assertEqual(self.s.profile(self.uid)["baby_dob"], "2026-11-04")

        process_inbound(self.s, self.uid, "Sorry, my baby is actually 3 months old", ts="2026-11-06T10:00:00+00:00",
                        extractor=Scripted(prop("baby_dob", "2026-08-06", "3 months old", date_precision="approximate")))
        self.assertEqual(self.s.profile(self.uid)["baby_dob"], "2026-08-06")
        self.assertEqual(self.s.family(self.uid)["condition_area"], "PNC_DOB")
        old = self.s.q("SELECT status FROM facts WHERE uid=? AND signal='baby_dob' AND value='2026-11-04'", (self.uid,))
        self.assertEqual(old[0]["status"], "superseded")  # kept for the audit trail, not deleted
        self.assertIn(NEEDED_TEXT["baby_dob"], self.s.copilot(self.uid)["still_needed"])  # still ask for the day
        upe = self.s.upe_writes(self.uid)[0]["payload"]["upe_fields"]["baby_dob"]
        self.assertEqual((upe["to"], upe.get("precision")), ("2026-08-06", "approximate"))


if __name__ == "__main__":
    unittest.main()
