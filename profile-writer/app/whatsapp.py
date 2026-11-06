"""WhatsApp Cloud API: receive (signed webhook) and send (human-approved replies only)."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


_media_cache: dict[str, tuple[str, float]] = {}


def _upload_media(path, mime: str) -> tuple[str | None, str]:
    """Upload a file once and reuse its media ID (Meta keeps uploads for 30 days; we refresh after 20)."""
    key = f"{settings.wa_phone_number_id}:{path}"
    hit = _media_cache.get(key)
    if hit and time.time() - hit[1] < 20 * 86400:
        return hit[0], "cached"
    boundary = "npw" + uuid.uuid4().hex
    data = Path(path).read_bytes()
    parts = []
    for name, value in (("messaging_product", "whatsapp"), ("type", mime)):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{Path(path).name}"\r\n'
                 f"Content-Type: {mime}\r\n\r\n".encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    url = f"https://graph.facebook.com/{settings.wa_graph_version}/{settings.wa_phone_number_id}/media"
    req = urllib.request.Request(url, data=b"".join(parts), headers={
        "Authorization": f"Bearer {settings.wa_token}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            media_id = json.loads(resp.read()).get("id")
    except urllib.error.HTTPError as e:
        return None, f"upload failed: HTTP {e.code}"
    except Exception as e:
        return None, f"upload failed: {type(e).__name__}"
    if media_id:
        _media_cache[key] = (media_id, time.time())
    return media_id, "uploaded"


def send_sticker(phone: str, path) -> tuple[bool, str]:
    """Send a static WebP sticker (512x512, under 100 KB). Only ever called after a nurse presses Send."""
    if not settings.whatsapp_live:
        return False, "live sending is off (WHATSAPP_LIVE=false)"
    media_id, detail = _upload_media(path, "image/webp")
    if not media_id:
        return False, detail
    url = f"https://graph.facebook.com/{settings.wa_graph_version}/{settings.wa_phone_number_id}/messages"
    body = {"messaging_product": "whatsapp", "to": phone, "type": "sticker", "sticker": {"id": media_id}}
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
