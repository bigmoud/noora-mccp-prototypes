"""Local web server: dashboard, simulator, WhatsApp webhook, live updates (SSE).

Standard library only. Run:  python3 -m app.server
"""
from __future__ import annotations

import hmac
import json
import queue
import re
import threading
import time
import uuid
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import pipeline, privacy, view, whatsapp
from .config import settings
from .llm import spend_so_far
from .seed import seed
from .store import Store, now

STATIC = Path(__file__).resolve().parent.parent / "web"  # same files GitHub Pages / Netlify serve
store = Store()
_subscribers: list[queue.Queue] = []
_sub_lock = threading.Lock()


def publish(kind: str, data: dict) -> None:
    with _sub_lock:
        for q in list(_subscribers):
            try:
                q.put_nowait((kind, data))
            except queue.Full:
                pass


PROCESSING: set[str] = set()  # families whose latest message is still going through the pipeline


def _config_view() -> dict:
    return {
        "live_whatsapp": settings.whatsapp_live,
        "rollout_mode": store.get_setting("rollout_mode", settings.rollout_mode),
        "kill_switch": store.get_setting("kill_switch", "off"),
        "spend_usd": round(spend_so_far(), 4), "spend_cap_usd": settings.spend_cap_usd,
    }


def state(uid: str | None) -> dict:
    fams = view.families(store, PROCESSING)
    if not uid or not store.family(uid):
        uid = fams[0]["uid"] if fams else None
    return {"config": _config_view(), "families": fams, "uid": uid,
            "chat": view.chat(store, uid, PROCESSING) if uid else None}


def _process(uid: str, text: str, ts: str | None = None, wa_id: str | None = None) -> None:
    PROCESSING.add(uid)
    publish("processing", {"uid": uid})
    try:
        pipeline.process_inbound(store, uid, text, ts, wa_id, publish=publish)
    except Exception as e:  # never log message content
        store.audit(uid, "pipeline_error", error=type(e).__name__)
    finally:
        PROCESSING.discard(uid)
        publish("profile", {"uid": uid})


class Handler(BaseHTTPRequestHandler):
    server_version = "noora-profile-writer"

    # Request logs carry no bodies, no query strings (they may hold tokens) and no phone numbers.
    def log_message(self, fmt, *args):
        path = urlparse(self.path).path
        print(f"{time.strftime('%H:%M:%S')} {self.command} {path} -> {args[1] if len(args) > 1 else ''}")

    # ------------------------------------------------------------ plumbing
    def _send(self, code: int, body: bytes | str | dict, ctype: str = "application/json", headers: dict | None = None):
        if isinstance(body, dict) or isinstance(body, list):
            body = json.dumps(body, ensure_ascii=False, default=str)
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "text" in ctype else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                         "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        for k, v in {**self._cors(), **(headers or {})}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _cors(self) -> dict:
        """Only the hosted frontend's own origin (ALLOWED_ORIGINS) may call the API from a browser."""
        origin = self.headers.get("Origin", "")
        if origin and origin in settings.allowed_origins:
            return {"Access-Control-Allow-Origin": origin, "Vary": "Origin",
                    "Access-Control-Allow-Headers": "Authorization, Content-Type, X-NPW, ngrok-skip-browser-warning",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Max-Age": "600"}
        return {}

    def do_OPTIONS(self):
        if not self._cors():
            return self._send(403, "origin not allowed", "text/plain")
        self.send_response(204)
        for k, v in self._cors().items():
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _authed(self) -> bool:
        tok = settings.dashboard_token
        same = lambda v: bool(v) and hmac.compare_digest(v.encode(), tok.encode())
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and same(auth[7:].strip()):  # hosted frontend
            return True
        if same(parse_qs(urlparse(self.path).query).get("token", [""])[0]):  # first visit, local dashboard
            return True
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return "npw_token" in c and same(c["npw_token"].value)

    def _json_body(self, limit: int = 100_000) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n > limit:
            raise ValueError("body too large")
        return json.loads(self.rfile.read(n) or b"{}")

    # ------------------------------------------------------------ GET
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/webhook":
            return self._webhook_verify(url)
        if url.path == "/healthz":
            return self._send(200, {"ok": True})
        if not self._authed():
            return self._send(401, "Open the dashboard link printed in the terminal (it carries the access token).",
                              "text/plain")
        if url.path == "/demo.json" and (STATIC / "demo.json").exists():
            return self._send(200, (STATIC / "demo.json").read_bytes(), "application/json")
        if url.path in ("/", "/index.html"):
            cookie = (f"npw_token={settings.dashboard_token}; HttpOnly; SameSite=Strict; Path=/"
                      + ("; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""))
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html", {"Set-Cookie": cookie})
        if url.path == "/api/state":
            uid = parse_qs(url.query).get("uid", [None])[0]
            return self._send(200, state(uid))
        if url.path == "/api/golden/export":
            rows = store.q("SELECT * FROM golden_pending WHERE deidentified=1")
            lines = "\n".join(json.dumps({"id": f"rev-{r['id']}", "msg_day": r["msg_day"], "messages": [r["message_text"]],
                                          "signal": r["signal"], "correct_value": r["correct_value"],
                                          "source": "reviewer_correction"}, ensure_ascii=False) for r in rows)
            return self._send(200, lines, "application/x-ndjson")
        if url.path == "/events":
            return self._sse()
        return self._send(404, {"error": "not found"})

    def _sse(self):
        q: queue.Queue = queue.Queue(maxsize=200)
        with _sub_lock:
            _subscribers.append(q)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        for k, v in self._cors().items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    kind, data = q.get(timeout=15)
                    payload = json.dumps({"kind": kind, "data": data}, ensure_ascii=False, default=str)
                    self.wfile.write(f"data: {payload}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _sub_lock:
                if q in _subscribers:
                    _subscribers.remove(q)

    def _webhook_verify(self, url):
        qs = parse_qs(url.query)
        if (qs.get("hub.mode", [""])[0] == "subscribe" and settings.wa_verify_token
                and qs.get("hub.verify_token", [""])[0] == settings.wa_verify_token):
            return self._send(200, qs.get("hub.challenge", [""])[0], "text/plain")
        return self._send(403, "forbidden", "text/plain")

    # ------------------------------------------------------------ POST
    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/webhook":
            return self._webhook_receive()
        if not self._authed():
            return self._send(401, {"error": "unauthorised"})
        if self.headers.get("X-NPW") != "1":  # simple CSRF guard alongside SameSite=Strict
            return self._send(403, {"error": "missing header"})
        try:
            body = self._json_body()
            return self._route_api(url.path, body)
        except PermissionError as e:
            return self._send(403, {"error": str(e)})
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            return self._send(400, {"error": str(e)})

    def _route_api(self, path: str, body: dict):
        if path == "/api/simulate":
            uid = body["uid"]
            if not store.family(uid):
                raise ValueError("unknown family")
            text = str(body.get("text", "")).strip()
            if not text:
                raise ValueError("empty message")
            threading.Thread(target=_process, args=(uid, text, None, "sim-" + uuid.uuid4().hex), daemon=True).start()
            return self._send(202, {"ok": True})
        if path == "/api/read":
            store.x("UPDATE families SET last_read_id=(SELECT COALESCE(MAX(id),0) FROM messages WHERE uid=?) WHERE uid=?",
                    (body["uid"], body["uid"]))
            return self._send(200, {"ok": True})
        if path == "/api/reply":
            return self._reply(body)
        if path == "/api/review":
            f = pipeline.review(store, int(body["fact_id"]), body["action"], str(body.get("reviewer", "") or "nurse"),
                                body.get("value"), str(body.get("note", "")), publish=publish)
            return self._send(200, {"ok": True, "fact": f})
        if path == "/api/settings":
            if "rollout_mode" in body:
                if body["rollout_mode"] not in ("shadow", "review_first", "auto_with_audit"):
                    raise ValueError("bad rollout mode")
                store.set_setting("rollout_mode", body["rollout_mode"])
                store.audit(None, "rollout_mode", value=body["rollout_mode"])
            if "kill_switch" in body:
                v = "on" if body["kill_switch"] in (True, "on") else "off"
                store.set_setting("kill_switch", v)
                store.audit(None, "kill_switch", value=v)
            publish("settings", {})
            return self._send(200, _config_view())
        if path == "/api/copilot":
            if not store.family(body["uid"]):
                raise ValueError("unknown family")
            pipeline.refresh_copilot_async(store, body["uid"], publish)
            return self._send(202, {"ok": True})
        if path == "/api/golden/deidentified":
            store.x("UPDATE golden_pending SET deidentified=1 WHERE id=?", (int(body["id"]),))
            store.audit(None, "golden_marked_deidentified", id=int(body["id"]), by=str(body.get("by", "")))
            return self._send(200, {"ok": True})
        if path == "/api/reset":
            store.reset()
            seed(store)
            _warm_copilot()
            publish("reset", {})
            return self._send(200, {"ok": True})
        if path == "/api/purge":
            n = store.purge_old_messages(int(body.get("hours", settings.message_retention_hours)))
            publish("reset", {})
            return self._send(200, {"purged": n})
        return self._send(404, {"error": "not found"})

    def _reply(self, body: dict):
        """A nurse types and sends. Nothing is ever sent without a person pressing Send."""
        uid, text = body["uid"], str(body.get("text", "")).strip()
        if not text:
            raise ValueError("empty reply")
        phone = store.contact(uid)
        sent, detail = False, "simulated family: reply stored only"
        if phone:
            if not privacy.is_allowed_number(phone):
                raise PermissionError("number not on the test allowlist")
            if not whatsapp.within_service_window(store.last_inbound_ts(uid)):
                raise PermissionError("outside WhatsApp's 24-hour window: only approved templates may be sent")
            sent, detail = whatsapp.send_text(phone, text)
            if not sent:  # don't show a message as sent when WhatsApp refused it
                store.audit(uid, "nurse_reply_failed", detail=detail[:80])
                return self._send(502, {"error": detail})
        mid = store.add_message(uid, "out", "nurse", text, privacy.redact(text)[0], now(), None)
        store.x("UPDATE copilot SET reply='' WHERE uid=?", (uid,))  # the draft has been used
        store.x("UPDATE families SET last_read_id=(SELECT COALESCE(MAX(id),0) FROM messages WHERE uid=?) WHERE uid=?",
                (uid, uid))
        store.audit(uid, "nurse_reply", sent=sent, detail=detail[:80], by=str(body.get("by", "nurse")))
        publish("message", {"uid": uid, "id": mid, "direction": "out", "author": "nurse", "text": text})
        return self._send(200, {"ok": True, "sent": sent, "detail": detail})

    def _webhook_receive(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n > 256_000:
            return self._send(413, "too large", "text/plain")
        raw = self.rfile.read(n)
        if not whatsapp.verify_signature(raw, self.headers.get("X-Hub-Signature-256")):
            store.audit(None, "webhook_rejected_signature")
            return self._send(401, "bad signature", "text/plain")
        self._send(200, "ok", "text/plain")  # acknowledge fast; Meta retries slow endpoints
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return
        dropped = 0
        for m in whatsapp.parse_messages(payload):
            if not privacy.is_allowed_number(m["from"]):
                dropped += 1  # never stored, never sent anywhere
                continue
            if not m["text"]:
                store.audit(None, "unsupported_message_type", type=m["type"])
                continue
            uid = privacy.pseudonym(m["from"])
            if not store.family(uid):
                store.upsert_family(uid, f"Live tester {privacy.mask_phone(m['from'])}", "ANC_EDD",
                                    name=f"Live tester {privacy.mask_phone(m['from'])}", state="-", language="Hindi")
                store.set_contact(uid, m["from"])
                store.audit(uid, "live_family_created")
                publish("reset", {})
            threading.Thread(target=_process, args=(uid, m["text"], m["ts"], m["id"]), daemon=True).start()
            threading.Thread(target=auto_ack, args=(uid, m["text"]), daemon=True).start()
        if dropped:
            store.audit(None, "dropped_not_allowlisted", count=dropped)


def auto_ack(uid: str, text: str, delay: float = 1.5) -> bool:
    """Send the fixed acknowledgment, at most once per cooldown. Not AI-written, not medical."""
    time.sleep(delay)
    if not settings.auto_ack or privacy.command(text):
        return False
    fam, phone = store.family(uid), store.contact(uid)
    if not fam or not fam["consent"] or not phone or not privacy.is_allowed_number(phone):
        return False
    last_out = store.q("SELECT ts FROM messages WHERE uid=? AND direction='out' ORDER BY id DESC LIMIT 1", (uid,))
    if last_out:
        from datetime import datetime, timezone
        age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(last_out[0]["ts"])).total_seconds() / 3600
        if age_h < (settings.auto_ack_cooldown_hours or 0):
            return False
    sent, detail = whatsapp.send_text(phone, settings.auto_ack_text)
    store.audit(uid, "auto_ack", sent=sent, detail=detail[:80])
    if sent:
        store.add_message(uid, "out", "auto", settings.auto_ack_text, settings.auto_ack_text, now(), None)
        publish("message", {"uid": uid})
    return sent


def _purge_loop():
    while True:
        try:
            if store.purge_old_messages(settings.message_retention_hours):
                publish("reset", {})
        except Exception as e:  # keep the loop alive; never log content
            print("purge error:", type(e).__name__)
        time.sleep(600)


def _warm_copilot() -> None:
    """Write a bio and draft for every family that doesn't have one yet (background, a few cents)."""
    for f in store.families():
        if not store.copilot(f["uid"]):
            pipeline.refresh_copilot_async(store, f["uid"], publish)


def main():
    if not store.families():
        seed(store)
    _warm_copilot()
    threading.Thread(target=_purge_loop, daemon=True).start()
    if settings.whatsapp_live:
        missing = [k for k, v in {"WHATSAPP_TOKEN": settings.wa_token, "WHATSAPP_PHONE_NUMBER_ID": settings.wa_phone_number_id,
                                  "WHATSAPP_APP_SECRET": settings.wa_app_secret, "WHATSAPP_VERIFY_TOKEN": settings.wa_verify_token,
                                  "ALLOWED_TEST_NUMBERS": settings.allowed_numbers}.items() if not v]
        if missing:
            raise SystemExit("Live mode needs: " + ", ".join(missing))
    srv = ThreadingHTTPServer((settings.host, settings.port), Handler)
    srv.daemon_threads = True
    print(f"\nNoora profile writer  ·  mode: {'LIVE WhatsApp' if settings.whatsapp_live else 'simulator'}"
          f"  ·  extractor: {settings.extractor}")
    print(f"Dashboard: http://localhost:{settings.port}/?token={settings.dashboard_token}")
    if settings.whatsapp_live:
        print(f"Webhook path: /webhook  ·  allowlisted numbers: {', '.join(privacy.mask_phone(n) for n in settings.allowed_numbers)}")
    print("Synthetic data only. Ctrl+C to stop.\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
