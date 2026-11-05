"""WhatsApp Cloud API: receive (signed webhook) and send (human-approved replies only)."""
from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from .config import settings


def verify_signature(raw_body: bytes, header: str | None) -> bool:
    """Meta signs each POST with HMAC-SHA256 of the raw body, keyed by the app secret."""
    if not settings.wa_app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(settings.wa_app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.split("=", 1)[1])


def parse_messages(payload: dict) -> list[dict]:
    """Pull inbound messages out of a webhook body. Status callbacks are ignored.
    The sender's WhatsApp profile name (contacts[].profile.name) is deliberately not read."""
    out = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for m in value.get("messages", []) or []:
                ts = datetime.fromtimestamp(int(m.get("timestamp", 0)), tz=timezone.utc).isoformat(timespec="seconds")
                kind = m.get("type")
                text = (m.get("text") or {}).get("body", "") if kind == "text" else ""
                if kind == "interactive":
                    inter = m.get("interactive", {})
                    text = (inter.get("button_reply") or inter.get("list_reply") or {}).get("title", "")
                elif kind == "button":
                    text = (m.get("button") or {}).get("text", "")
                out.append({"from": m.get("from", ""), "id": m.get("id"), "ts": ts, "type": kind, "text": text})
    return out


def within_service_window(last_inbound_iso: str | None) -> bool:
    """Free-form replies are only allowed within 24h of the family's last message."""
    if not last_inbound_iso:
        return False
    return datetime.now(timezone.utc) - datetime.fromisoformat(last_inbound_iso) < timedelta(hours=24)


def send_text(phone: str, text: str) -> tuple[bool, str]:
    if not settings.whatsapp_live:
        return False, "live sending is off (WHATSAPP_LIVE=false)"
    url = f"https://graph.facebook.com/{settings.wa_graph_version}/{settings.wa_phone_number_id}/messages"
    body = {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": text[:4096]}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {settings.wa_token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        return True, (data.get("messages") or [{}])[0].get("id", "sent")
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read()).get("error", {})
            return False, f"WhatsApp error {err.get('code')}: {err.get('message', '')[:120]}"
        except Exception:
            return False, f"HTTP {e.code}"
    except Exception as e:
        return False, type(e).__name__
