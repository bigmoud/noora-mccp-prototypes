"""Turn date phrases into dates in code, so the model's date maths can be checked.

The model also resolves dates. When this module can read the phrase too, the two
answers must agree (within a day) or the write is held. When this module can't read
the phrase, the rules fall back to the model's answer but demand more evidence.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

WEEKDAYS = {
    0: ["monday", "mon", "somvar", "somwar", "सोमवार"],
    1: ["tuesday", "tue", "mangalvar", "mangalwar", "मंगलवार"],
    2: ["wednesday", "wed", "budhvar", "budhwar", "बुधवार"],
    3: ["thursday", "thu", "guruvar", "guruwar", "veervar", "brihaspativar", "गुरुवार", "बृहस्पतिवार"],
    4: ["friday", "fri", "shukravar", "shukrawar", "शुक्रवार"],
    5: ["saturday", "sat", "shanivar", "shaniwar", "शनिवार"],
    6: ["sunday", "sun", "ravivar", "raviwar", "itvaar", "itwar", "रविवार"],
}
MONTHS = {
    1: ["january", "jan", "जनवरी"], 2: ["february", "feb", "फरवरी"], 3: ["march", "mar", "मार्च"],
    4: ["april", "apr", "अप्रैल"], 5: ["may", "मई"], 6: ["june", "jun", "जून"],
    7: ["july", "jul", "जुलाई"], 8: ["august", "aug", "अगस्त"], 9: ["september", "sep", "sept", "सितंबर"],
    10: ["october", "oct", "अक्टूबर"], 11: ["november", "nov", "नवंबर"], 12: ["december", "dec", "दिसंबर"],
}
_NUM_WORDS = {"ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "che": 6,
              "saat": 7, "aath": 8, "nau": 9, "das": 10, "a": 1, "an": 1,
              "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
              "ten": 10, "eleven": 11, "twelve": 12,
              "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "सात": 7, "आठ": 8}


def _num(token: str) -> int | None:
    token = token.lower()
    if token.isdigit():
        return int(token)
    return _NUM_WORDS.get(token)


def resolve(phrase: str, msg_day: date, past: bool = True) -> date | None:
    """Best-effort reading of a date phrase. Returns None when unsure."""
    p = phrase.lower().strip()
    if not p:
        return None

    # ISO / numeric dates: 2026-11-03, 3/11/2026, 3-11-26, 3/11
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", p)
    if m:
        return _safe(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?(?!\d)", p)
    if m:
        d, mo = int(m[1]), int(m[2])
        y = int(m[3]) if m[3] else None
        if y is not None and y < 100:
            y += 2000
        return _with_year(d, mo, y, msg_day, past)

    # "15 november", "nov 15", "15 नवंबर"
    for mo, names in MONTHS.items():
        for name in names:
            if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", p):
                dm = re.search(r"(?<!\d)(\d{1,2})(?!\d)", p)
                ym = re.search(r"(20\d{2})", p)
                if dm:
                    return _with_year(int(dm[1]), mo, int(ym[1]) if ym else None, msg_day, past)
                return None  # month only: too vague to be a date

    if re.search(r"\b(today|aaj)\b|आज", p):
        return msg_day
    if re.search(r"\b(day before yesterday|parso|parson)\b|परसों", p):
        return msg_day - timedelta(days=2) if past else msg_day + timedelta(days=2)
    if re.search(r"\b(yesterday|kal)\b|कल", p):
        return msg_day - timedelta(days=1) if past else msg_day + timedelta(days=1)

    m = re.search(r"(\w+)\s*(din|days?|दिन)\s*(pehle|pahle|ago|पहले)", p)
    if m and _num(m[1]):
        return msg_day - timedelta(days=_num(m[1]))
    m = re.search(r"(\w+)\s*(hafte|hafta|weeks?|हफ्ते|सप्ताह)\s*(pehle|pahle|ago|पहले)", p)
    if m and _num(m[1]):
        return None  # "2 weeks ago" is a range, not a day: let the rules treat it as approximate

    m = re.search(r"(\d{1,2})\s*(tarikh|tareekh|तारीख)", p)
    if m:
        return _with_year(int(m[1]), msg_day.month, msg_day.year, msg_day, past, roll_month=True)

    for wd, names in WEEKDAYS.items():
        for name in names:
            if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", p):
                if past:
                    delta = (msg_day.weekday() - wd) % 7 or 7  # most recent, not today
                    return msg_day - timedelta(days=delta)
                delta = (wd - msg_day.weekday()) % 7 or 7
                return msg_day + timedelta(days=delta)
    return None


def _safe(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _with_year(d: int, m: int, y: int | None, msg_day: date, past: bool, roll_month: bool = False) -> date | None:
    if y is not None:
        return _safe(y, m, d)
    cand = _safe(msg_day.year, m, d)
    if cand is None:
        return None
    if roll_month:
        # "15 tarikh" means the 15th of this month, or last month if that is still ahead.
        if past and cand > msg_day:
            pm = msg_day.month - 1 or 12
            py = msg_day.year if msg_day.month > 1 else msg_day.year - 1
            return _safe(py, pm, d)
        if not past and cand < msg_day:
            nm = msg_day.month % 12 + 1
            ny = msg_day.year + (1 if msg_day.month == 12 else 0)
            return _safe(ny, nm, d)
        return cand
    if past and cand > msg_day:
        return _safe(msg_day.year - 1, m, d)
    if not past and cand < msg_day - timedelta(days=30):
        return _safe(msg_day.year + 1, m, d)
    return cand


# A baby's age ("one day old", "10 din ka", "3 months old", "teen mahine ki") read as a birth date.
# Days pin down one day; weeks and months are ranges, so they come with a tolerance in days.
_AGE_UNITS = [
    (r"din|days?|दिन", 1, 0),
    (r"hafte|hafta|haftay|weeks?|wks?|हफ्ते|हफ़्ते|सप्ताह", 7, 4),
    (r"mahine|mahina|maheene|months?|महीने|महीना|महिने", 30, 15),
]
_AGE_TAIL = r"(?:ka|ki|ke|old|ka hai|ki hai|का|की|के|pehle|pahle|ago|पहले)"


def age_to_dob(phrase: str, msg_day: date) -> tuple[date, int] | None:
    """(birth date, tolerance in days) for an age or 'N units ago' phrase, or None."""
    p = phrase.lower().strip()
    for unit, days, tol in _AGE_UNITS:
        m = re.search(rf"(?<!\w)(\w+)\s*(?:{unit})\s*{_AGE_TAIL}", p)
        if m and _num(m[1]) is not None:
            n = _num(m[1])
            if days == 30:  # calendar months: "3 months old" on 6 Nov is about 6 Aug
                y, mo = divmod(msg_day.year * 12 + msg_day.month - 1 - n, 12)
                return _safe(y, mo + 1, min(msg_day.day, 28)) or msg_day - timedelta(days=30 * n), tol
            return msg_day - timedelta(days=n * days), tol
    return None
