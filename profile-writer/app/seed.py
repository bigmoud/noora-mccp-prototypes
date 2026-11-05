"""Three synthetic demo families. Every name, number and message here was written by the
fellows; none comes from Noora's users."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import privacy
from .store import Store, now


def _onboarding_fact(store: Store, uid: str, signal: str, value: str, source: str) -> None:
    store.add_fact(uid, signal, value, "active", None, None, source, "", "source-of-record", [],
                   "from onboarding / government record", "onboarding", review_status="approved")


def seed(store: Store) -> None:
    today = datetime.now(timezone.utc).date()

    a = privacy.pseudonym("sim-family-a")
    store.upsert_family(a, "Family A · Sunita (synthetic)", "ANC_EDD")
    _onboarding_fact(store, a, "stage", "pregnant", "(onboarding form)")
    _onboarding_fact(store, a, "due_date", (today + timedelta(days=3)).isoformat(), "(government RCH record)")

    b = privacy.pseudonym("sim-family-b")
    store.upsert_family(b, "Family B · Meena (synthetic)", "ANC_EDD")
    _onboarding_fact(store, b, "stage", "pregnant", "(onboarding form)")
    _onboarding_fact(store, b, "due_date", (today + timedelta(days=75)).isoformat(), "(onboarding form)")

    c = privacy.pseudonym("sim-family-c")
    store.upsert_family(c, "Family C · Pooja (synthetic)", "PNC_DOB")
    _onboarding_fact(store, c, "stage", "delivered", "(tapped “Yes, I've delivered”)")
    _onboarding_fact(store, c, "baby_dob", (today - timedelta(days=20)).isoformat(), "(delivery flow reply)")
    ts = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
    text = "Main Pooja ki saas hoon, aaj uska phone mere paas hai. Baby ko teeka kab lagwana hai?"
    mid = store.add_message(c, "in", "family", text, text, ts)
    # A deliberately wrong write, labelled as seeded, so the reviewer-correction step can be
    # shown live without depending on the model making a mistake on stage.
    store.add_fact(c, "phone_holder", "mother_in_law", "active", "reviewer", mid, "Main Pooja ki saas hoon",
                   "mother_in_law", "high", [{"name": "seeded for demo", "ok": True, "detail": "pre-loaded example of a wrong write"}],
                   "seeded example", "seeded:demo-mistake", review_status="pending")
    d = privacy.pseudonym("sim-family-d")
    store.upsert_family(d, "Family D · Kavya, high-risk (synthetic)", "HRPW")
    _onboarding_fact(store, d, "stage", "pregnant", "(onboarding form)")
    _onboarding_fact(store, d, "due_date", (today + timedelta(days=5)).isoformat(), "(government RCH record)")
    store.audit(None, "demo_seeded", families=4)
