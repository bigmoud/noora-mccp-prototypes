"""Five synthetic demo families (history kept inside the 72-hour retention window). Every name, number and message was written by the fellows;
none comes from Noora's users."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import privacy
from .store import Store


def _fact(store: Store, uid: str, signal: str, value: str, source: str) -> None:
    store.add_fact(uid, signal, value, "active", None, None, source, "", "source-of-record", [],
                   "from onboarding / government record", "onboarding", review_status="approved")


def _msg(store: Store, uid: str, author: str, text: str, ago: timedelta) -> int:
    ts = (datetime.now(timezone.utc) - ago).isoformat(timespec="seconds")
    return store.add_message(uid, "in" if author == "family" else "out", author, text, privacy.redact(text)[0], ts)


def seed(store: Store) -> None:
    today = datetime.now(timezone.utc).date()
    d = timedelta(days=1)

    a = privacy.pseudonym("sim-family-a")
    store.upsert_family(a, "Sunita Devi", "ANC_EDD", name="Sunita Devi", state="Bihar", language="Hindi",
                        noora_program="MCH Bihar", onboarding_method="Hospital class", onboarding_date="2026-07-14")
    _fact(store, a, "stage", "pregnant", "(onboarding form)")
    _fact(store, a, "due_date", (today + 3 * d).isoformat(), "(government RCH record)")
    _msg(store, a, "nurse", "Namaste! Aapki delivery ki tareekh paas aa rahi hai. Hospital bag taiyaar rakhein aur "
                            "koi bhi pareshani ho toh humein yahan likhein.", timedelta(hours=50))
    _msg(store, a, "family", "Ji theek hai, dhanyavaad", timedelta(hours=47))

    b = privacy.pseudonym("sim-family-b")
    store.upsert_family(b, "Meena Kumari", "ANC_EDD", name="Meena Kumari", state="Uttar Pradesh", language="Hindi",
                        noora_program="MCH UP", onboarding_method="QR code", onboarding_date="2026-09-02")
    _fact(store, b, "stage", "pregnant", "(onboarding form)")
    _fact(store, b, "due_date", (today + 75 * d).isoformat(), "(onboarding form)")
    _msg(store, b, "family", "Didi pair mein sujan hai thodi si, kya karein?", timedelta(hours=44))
    _msg(store, b, "nurse", "Namaste Meena ji. Pair upar rakh kar aaram karein aur namak kam khayein. Agar sujan "
                            "achanak badhe ya sir dard ho toh turant hospital jayein.", timedelta(hours=42))

    c = privacy.pseudonym("sim-family-c")
    store.upsert_family(c, "Pooja Sharma", "PNC_DOB", name="Pooja Sharma", state="Rajasthan", language="Hindi",
                        noora_program="MCH Rajasthan", onboarding_method="Hospital class", onboarding_date="2026-06-20")
    _fact(store, c, "stage", "delivered", "(tapped “Yes, I've delivered”)")
    _fact(store, c, "baby_dob", (today - 20 * d).isoformat(), "(delivery flow reply)")
    mid = _msg(store, c, "family", "Main Pooja ki saas hoon, aaj uska phone mere paas hai. Baby ko teeka kab "
                                   "lagwana hai?", timedelta(hours=20))
    # An item the AI judge couldn't settle, pre-loaded so the nurse step can be shown on demand.
    store.add_fact(c, "phone_holder", "mother_in_law", "held", "nurse", mid, "Main Pooja ki saas hoon",
                   "mother_in_law", "medium", [], "She may only have the phone today; whose phone is it usually?",
                   "seeded:demo")

    k = privacy.pseudonym("sim-family-d")
    store.upsert_family(k, "Kavya R", "HRPW", name="Kavya R", state="Karnataka", language="Kannada",
                        noora_program="HRPW Karnataka", onboarding_method="ANM referral", onboarding_date="2026-08-30",
                        high_risk="Yes")
    _fact(store, k, "stage", "pregnant", "(onboarding form)")
    _fact(store, k, "due_date", (today + 5 * d).isoformat(), "(government RCH record)")
    _msg(store, k, "nurse", "Namaste Kavya ji. Aapki agli jaanch kab hai? BP check zaroor karwayein.", timedelta(hours=30))
    e = privacy.pseudonym("sim-family-e")
    store.upsert_family(e, "Rekha Yadav", "ANC_EDD", name="Rekha Yadav", state="Madhya Pradesh", language="Hindi",
                        noora_program="MCH MP", onboarding_method="QR code", onboarding_date="2026-08-11")
    _fact(store, e, "stage", "pregnant", "(onboarding form)")
    _fact(store, e, "due_date", (today + 10 * d).isoformat(), "(government RCH record)")
    _msg(store, e, "nurse", "Namaste Rekha ji! Is hafte baby ki harkat (movement) par dhyan dein. Kam lage toh turant "
                            "hospital jayein.", timedelta(hours=60))
    _msg(store, e, "family", "Ji didi", timedelta(hours=59))
    store.audit(None, "demo_seeded", families=5)
