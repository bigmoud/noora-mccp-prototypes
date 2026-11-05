"""Settings, read once from environment variables (or a .env file).

Every safety-relevant switch lives here so a reviewer can see them in one place.
Defaults are the *safe* choice: simulator mode, no live sending, writes held.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float(name: str, default: float | None) -> float | None:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class Settings:
    # --- where things live
    db_path = Path(os.environ.get("DB_PATH", ROOT / "data" / "profile.db"))

    # --- extractor
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_base_url = os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com").rstrip("/")
    # Needed only when the key is not scoped to one workspace (Console → Settings → Workspaces).
    anthropic_workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID", "")
    # Hard ceiling on total API spend, checked before every call (server and eval share it).
    spend_cap_usd = _float("SPEND_CAP_USD", 5.0)
    spend_ledger = Path(os.environ.get("SPEND_LEDGER", ROOT / "data" / "spend_ledger.json"))
    extractor_model = os.environ.get("EXTRACTOR_MODEL", "claude-haiku-5-5")
    # The judge is a different, stronger model so its mistakes are less likely to match the extractor's.
    judge_model = os.environ.get("JUDGE_MODEL", "claude-sonnet-5-5")
    copilot_model = os.environ.get("COPILOT_MODEL", "claude-haiku-5-5")
    # "claude" uses the API; "baseline" is the keyword extractor (no data leaves the laptop).
    extractor = os.environ.get("EXTRACTOR", "claude" if anthropic_api_key else "baseline")
    # Claude Haiku 5.5 list prices (prompts under 100k tokens), Nov 2026. Override if you change model.
    price_in_per_mtok = _float("PRICE_INPUT_PER_MTOK", 0.10)
    price_out_per_mtok = _float("PRICE_OUTPUT_PER_MTOK", 0.50)

    # --- cost and abuse limits (enforced in code, not in the prompt)
    daily_token_cap = _int("DAILY_TOKEN_CAP", 200_000)
    max_extractions_per_family_per_hour = _int("MAX_EXTRACTIONS_PER_FAMILY_PER_HOUR", 20)
    max_message_chars = _int("MAX_MESSAGE_CHARS", 1500)

    # --- rollout: shadow (extract, never write) | review_first (every write held)
    #     | auto_with_audit (confident writes go live, all reviewed afterwards)
    rollout_mode = os.environ.get("ROLLOUT_MODE", "auto_with_audit")

    # --- privacy
    pseudonym_key = os.environ.get("PSEUDONYM_KEY", "")  # HMAC key; set a long random value
    message_retention_hours = _int("MESSAGE_RETENTION_HOURS", 72)

    # --- WhatsApp Cloud API (live mode only)
    whatsapp_live = _bool("WHATSAPP_LIVE", False)
    wa_token = os.environ.get("WHATSAPP_TOKEN", "")
    wa_phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    wa_app_secret = os.environ.get("WHATSAPP_APP_SECRET", "")
    wa_verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
    wa_graph_version = os.environ.get("WHATSAPP_GRAPH_VERSION", "v23.0")
    # Fixed, non-clinical acknowledgment sent automatically on a family's message (never AI-written,
    # never medical). Medical replies always wait for a nurse to press Send.
    auto_ack = _bool("AUTO_ACK", True)
    auto_ack_cooldown_hours = _float("AUTO_ACK_COOLDOWN_HOURS", 2.0)
    auto_ack_text = os.environ.get("AUTO_ACK_TEXT",
        "Namaste. Aapka sandesh mil gaya hai, hamari nurse jald hi jawab dengi. "
        "Thank you, we have received your message and a nurse will reply soon. "
        "In an emergency, please call 108.")
    # Comma-separated E.164 numbers without "+". Only these numbers are ever processed.
    allowed_numbers = {
        n.strip().lstrip("+") for n in os.environ.get("ALLOWED_TEST_NUMBERS", "").split(",") if n.strip()
    }

    # --- dashboard
    host = os.environ.get("HOST", "127.0.0.1")
    port = _int("PORT", 8000)  # hosting platforms set PORT
    dashboard_token = os.environ.get("DASHBOARD_TOKEN", "") or secrets.token_urlsafe(16)
    # Hosted frontend origins allowed to call this server, e.g. https://you.github.io (no trailing slash)
    allowed_origins = {o.strip().rstrip("/") for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()}


settings = Settings()

if not settings.pseudonym_key:
    # No key given: make one on first run and keep it in data/ (git-ignored, owner-only).
    # Production keeps this key in Noora's secret store, never next to the database.
    _key_file = ROOT / "data" / ".pseudonym_key"
    _key_file.parent.mkdir(parents=True, exist_ok=True)
    if not _key_file.exists():
        _key_file.write_text(secrets.token_hex(32), encoding="utf-8")
        os.chmod(_key_file, 0o600)
    settings.pseudonym_key = _key_file.read_text(encoding="utf-8").strip()
