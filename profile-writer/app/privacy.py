"""Privacy and safety checks that run in plain code, before and around the model.

Nothing here asks the model to behave. Each function enforces a rule:
- the phone number becomes a pseudonym before anything is stored or sent;
- obvious identifiers are removed from text before it goes to Claude;
- numbers outside the test allowlist are dropped on arrival;
- pregnancy-loss and emergency words are caught by keyword, not by the model.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata

from .config import settings

# ---------------------------------------------------------------- identity

def pseudonym(phone: str) -> str:
    """Stable, non-reversible ID for a phone number (HMAC-SHA256 with a secret key)."""
    digits = re.sub(r"\D", "", phone) or phone  # simulator families use a text key
    mac = hmac.new(settings.pseudonym_key.encode(), digits.encode(), hashlib.sha256).hexdigest()
    return "fam_" + mac[:12]


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return "••••" + digits[-4:] if len(digits) >= 4 else "••••"


def is_allowed_number(phone: str) -> bool:
    """Live mode only processes numbers the fellows registered as test phones."""
    return re.sub(r"\D", "", phone) in settings.allowed_numbers


# ---------------------------------------------------------------- redaction
# Order matters: longer, more specific patterns first.
_REDACTIONS = [
    ("aadhaar", re.compile(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)")),
    ("phone", re.compile(r"(?<!\d)(?:\+?91[ -]?)?[6-9]\d{4}[ -]?\d{5}(?!\d)")),
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("pincode", re.compile(r"(?<!\d)[1-9]\d{2} ?\d{3}(?!\d)")),
    ("url", re.compile(r"https?://\S+")),
]


_DIGITS = {cp: str(unicodedata.digit(chr(cp))) for cp in range(0x0900, 0x0D80)
           if unicodedata.category(chr(cp)) == "Nd"}


def redact(text: str) -> tuple[str, list[str]]:
    """Replace identifiers with typed placeholders. Returns (clean_text, kinds_removed).

    Limits (written down in SAFETY.md): names and village names inside free text are NOT
    removed; that needs a reviewed NER step in Noora's own pipeline.
    """
    found: list[str] = []
    # Numbers typed in Devanagari, Kannada, Telugu, Gurmukhi etc. digits (९८७…) become ASCII
    # first, so a phone number can't slip past redaction by script.
    text = text.translate(_DIGITS)
    for kind, pattern in _REDACTIONS:
        if pattern.search(text):
            found.append(kind)
            text = pattern.sub(f"[{kind.upper()}]", text)
    return text, found


def clip(text: str) -> tuple[str, bool]:
    limit = settings.max_message_chars
    return (text[:limit], True) if len(text) > limit else (text, False)


# ---------------------------------------------------------------- keyword guards
# These are deliberately broad. A false alarm costs a reviewer a minute;
# a miss could send newborn-care messages to a mother whose baby died.
_CHILD = r"(?:bachcha|bacha|baccha|bachha|bachchi|bachi|baby|shishu)"
LOSS_WORDS = [
    r"miscarri", r"still ?birth", r"stillborn", r"baby (?:died|passed|expired|is no more)",
    r"lost (?:the|my|our|her) baby", r"abortion", r"\bnicu\b.*\b(?:died|expired)\b",
    # \b below: "baby girl" must not match "bachcha gir gaya" (found by the holdout eval, g21)
    r"garbh ?pat", r"garbh gir", rf"{_CHILD} gir\b",
    # Child word, then up to 8 words, then "didn't survive / is no more" (g31: "Baby hua tha par do din baad nahi raha")
    rf"{_CHILD}(?:\s+\S+){{0,8}}\s+bach (?:nahi|nahin|nhi|na) (?:paya|payi|saka|saki)",  # g32: "baby bach nahi paya"
    rf"{_CHILD} (?:mar|guzar|khatam)", r"mara hua", r"mari hui", rf"mri?t (?:{_CHILD}|shishu)",
    r"(?:dhadkan|heartbeat) (?:nahi|nahin|band|stopped)",
    r"गर्भपात", r"गर्भ गिर", r"मृत", r"नहीं रहा", r"नहीं रही", r"गुज़र", r"गुजर", r"बच नहीं",
    # Live languages beyond Hindi (Kripesh, Nov 5). DRAFT word lists: a native speaker and
    # Niharika must review before anyone relies on them. Words for "died / passed away /
    # miscarriage". Broad on purpose: a false alarm costs a reviewer a minute.
    r"दगाव", r"बाळ गेल",                                   # Marathi: died; the baby is gone
    r"ತೀರಿಕೊಂಡ", r"ಸತ್ತ", r"ಗರ್ಭಪಾತ", r"ಮರಣ",              # Kannada: passed away; died; miscarriage; death
    r"చనిపోయ", r"మరణించ", r"గర్భస్రావ", r"చచ్చిపో",          # Telugu: died; passed away; miscarriage; died
    r"ਮਰ ਗਿਆ", r"ਮਰ ਗਈ", r"ਗੁਜ਼ਰ", r"ਗੁਜਰ", r"ਗਰਭਪਾਤ", r"ਮੌਤ",  # Punjabi: died (m/f); passed; miscarriage; death
]
DANGER_WORDS = [
    r"bleed", r"khoon", r"खून", r"convuls", r"\bfits?\b", r"jhatk", r"दौरा", r"behosh", r"बेहोश",
    r"unconscious", r"not breathing", r"saans nahi", r"सांस नहीं", r"high fever", r"tez bukhar",
    r"तेज बुखार", r"blurred vision", r"severe (?:pain|headache)", r"\bemergency\b", r"आपात",
    # Newborn danger signs (WHO/IMNCI list the Copilot prompt already uses). Found live on Nov 5:
    # "My baby is blue and he was born yesterday" raised no flag.
    rf"(?:{_CHILD}|he|she|lips|hoth|honth)\b(?:\s+\S+){{0,4}}\s+(?:is |looks |turned |ho gaya |pad gaya |pad gayi )?(?:blue|neela|nila|neeli|nili)\b"
    r"(?!\s+(?:dress|kapd|shirt|frock|blanket|kambal|cloth|colou?r|rang|toy|khilona|cap|topi|socks|jacket|sweater))",
    r"नीला", r"नीली", r"(?:baby|bachcha|bacha|shishu|बच्चा)\S*(?:\s+\S+){0,3}\s+(?:is )?(?:cold|thanda|thandi|ठंडा)",
    r"not feeding", r"(?:doodh|dudh|feed)\S*(?:\s+\S+){0,2}\s+(?:nahi|nahin|nhi) (?:pee|pi|le) ?(?:raha|rahi)",
    r"दूध नहीं", r"very sleepy", r"bahut sust", r"सुस्त", r"(?:saans|breathing)\S*(?:\s+\S+){0,3}\s+(?:tez|fast)",
    r"(?:fast|tez) (?:breathing|saans)", r"(?:aankh\S*|eyes|skin|twacha|hathel\S*|palms?|soles?|talv\S*|talw\S*|body|sharir)(?:\s+\S+){0,2}\s+(?:peel\S*|yellow)",
    r"yellow (?:eyes|skin|palms|soles)|peeliya|piliya|jaundice|पीलिया|आंखें पीली|आँखें पीली",
]
OPT_OUT = re.compile(r"^\s*(stop|unsubscribe|band karo|बंद करो)\s*[.!]*\s*$", re.I)
ERASE = re.compile(r"^\s*(delete my data|mera data (?:delete|hatao|mitao)|मेरा डेटा (?:हटाओ|मिटाओ))\s*[.!]*\s*$", re.I)

_loss_re = re.compile("|".join(LOSS_WORDS), re.I)

# "<child> … nahi raha" means "is no more" (g31: "Baby hua tha par do din baad nahi raha"),
# unless a verb sits right before "nahi": "baby so nahi raha" = the baby isn't sleeping.
_NO_MORE = re.compile(rf"{_CHILD}((?:\s+\S+){{0,8}}?)\s+(?:nahi|nahin|nhi|na) (?:raha|rahi|bacha|bachi|bach paya|bach payi|bach sak)",
                      re.I)
_VERB_BEFORE_NAHI = {"so", "soo", "pi", "pee", "piya", "kha", "ro", "uth", "chal", "bol", "sun", "dekh", "jaag", "jag",
                     "has", "hans", "le", "de", "kar", "ho", "badh", "ruk", "chup", "sambhal", "thak", "hil", "chus",
                     "choos", "pakad", "khel", "muskura", "saans", "nahaa", "naha", "doodh", "theek", "thik", "sahi"}
_danger_re = re.compile("|".join(DANGER_WORDS), re.I)


def mentions_loss(text: str) -> bool:
    if _loss_re.search(text):
        return True
    for m in _NO_MORE.finditer(text):
        words = m.group(1).split()
        if not words or words[-1].lower().strip(",.") not in _VERB_BEFORE_NAHI:
            return True
    return False


def mentions_danger(text: str) -> bool:
    return bool(_danger_re.search(text))


# Asking for other people's data or for the system's internals. The models can't see either
# (each call holds one family's chat and an output-only tool), but the request itself is a signal:
# the draft becomes a fixed, human-written reply and any profile write waits for a nurse.
_OTHERS = r"(?:other|others'?|another|all(?: the)?|every) (?:users?|famil(?:y|ies)|mothers?|mums?|moms?|patients?|people|members?|chats?|women|numbers?|persons?)"
_DATA_REQUEST = re.compile(
    rf"{_OTHERS}|(?:numbers?|details|data|information|info|messages|chats|addresses?) (?:of|from) (?:the )?(?:other|others|another|everyone|all)|"
    r"(?:doosr|dusr)(?:e|on|o)(?: logon| log| mahilaon| mahila| parivar| users| families| mothers)\b(?:\s+\S+){0,2}\s+(?:ka|ki|ke|number|data|details|baat)|"
    r"kisi aur (?:ka|ki|ke) (?:number|data|details|jaankari)|sab(?:hi)? (?:logon|mahilaon|users) (?:ka|ki|ke)|"
    r"दूसरों|दूसरे लोग|दूसरी महिला|सबका नंबर|"
    r"(?:system|your) (?:prompt|instructions|rules|database|code)|\bdatabase\b|api[ _-]?key|password|\badmin(?:istrator)?\b|"
    r"(?:list|dump|export|show) (?:of )?(?:all|every)", re.I)


def asks_for_others_data(text: str) -> bool:
    return bool(_DATA_REQUEST.search(text))


# Text that reads like orders to the system rather than a family talking. Not a complete
# defence (none exists); it is one enforcing layer on top of the model having no tools
# and every write passing the rules.
_INJECTION = re.compile(
    r"ignore (?:all |any )?(?:previous|prior|above|earlier) (?:instructions|rules)|you are now|system prompt|"
    r"\bas an? (?:ai|admin|administrator|developer)\b|set (?:the |her |my )?(?:due date|dob|date of birth|stage|profile)\s+to|"
    r"mark (?:everyone|all|her|me) (?:as )?(?:delivered|pregnant)|\bjailbreak\b|developer mode|"
    r"forget (?:your|all|the|previous|these) (?:rules|instructions)|\bact as\b|pretend (?:you|to be)|"
    r"new instructions|\boverride\b|^\s*(?:system|assistant)\s*:|</?(?:system|instructions?)>|"
    r"niyam (?:bhool|bhul|tod)|नियम (?:भूल|तोड़)", re.I | re.M)


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION.search(text))


def command(text: str) -> str | None:
    if ERASE.match(text):
        return "erase"
    if OPT_OUT.match(text):
        return "opt_out"
    return None
