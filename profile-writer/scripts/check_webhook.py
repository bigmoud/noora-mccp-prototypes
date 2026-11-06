"""Check (and fix) where Meta sends incoming WhatsApp messages. Never prints a secret.

    python3 scripts/check_webhook.py                                  # show what Meta has now
    python3 scripts/check_webhook.py https://<words>.trycloudflare.com   # point Meta at this tunnel

Run it from the profile-writer folder while start_live.sh is running in another window.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

env = {}
for line in Path(".env").read_text().splitlines():
    m = re.match(r"^\s*([A-Z_]+)=(.*)$", line)
    if m:
        env[m.group(1)] = m.group(2).strip()
G = f"https://graph.facebook.com/{env.get('WHATSAPP_GRAPH_VERSION') or 'v23.0'}"
TOKEN, SECRET = env["WHATSAPP_TOKEN"], env["WHATSAPP_APP_SECRET"]


def call(method: str, path: str, **params) -> dict:
    data = urllib.parse.urlencode(params).encode()
    url = f"{G}/{path}" + (f"?{data.decode()}" if method == "GET" else "")
    req = urllib.request.Request(url, data=None if method == "GET" else data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except ValueError:
            return {"error": {"message": f"HTTP {e.code}"}}


def ok(label: str, good: bool, detail: str = "") -> None:
    print(f"  {'OK ' if good else 'NO '} {label}" + (f": {detail}" if detail else ""))


app = call("GET", "app", access_token=TOKEN)
if "id" not in app:
    sys.exit(f"Access token problem: {app.get('error', {}).get('message', app)}\n"
             "Make a new one (Step 1. Try it out → Generate token), put it in .env, restart start_live.sh.")
app_id, app_token = app["id"], f"{app['id']}|{SECRET}"
print(f"App: {app.get('name')}")

phone = call("GET", env["WHATSAPP_PHONE_NUMBER_ID"], fields="display_phone_number", access_token=TOKEN)
waba = None
debug = call("GET", "debug_token", input_token=TOKEN, access_token=app_token).get("data", {})
for scope in debug.get("granular_scopes", []):
    if scope.get("scope") == "whatsapp_business_management" and scope.get("target_ids"):
        waba = scope["target_ids"][0]
ok("access token works", "display_phone_number" in phone, phone.get("display_phone_number", ""))

if len(sys.argv) > 1:
    base = urllib.parse.urlparse(sys.argv[1].strip())
    callback = f"{base.scheme}://{base.netloc}/webhook"
    r = call("POST", f"{app_id}/subscriptions", object="whatsapp_business_account", callback_url=callback,
             verify_token=env["WHATSAPP_VERIFY_TOKEN"], fields="messages", access_token=app_token)
    ok(f"pointed Meta at {callback}", r.get("success") is True, r.get("error", {}).get("message", ""))
    if waba:
        r = call("POST", f"{waba}/subscribed_apps", access_token=TOKEN)
        ok("WhatsApp account linked to the app", r.get("success") is True, r.get("error", {}).get("message", ""))

subs = call("GET", f"{app_id}/subscriptions", access_token=app_token).get("data", [])
wa = next((s for s in subs if s.get("object") == "whatsapp_business_account"), None)
fields = [f.get("name") for f in (wa or {}).get("fields", [])]
ok("Meta sends to", bool(wa and wa.get("active")), (wa or {}).get("callback_url", "nothing set"))
ok("subscribed to messages", "messages" in fields, ", ".join(fields) or "none")
if waba:
    linked = call("GET", f"{waba}/subscribed_apps", access_token=TOKEN).get("data", [])
    ok("WhatsApp account linked to the app", any(a.get("whatsapp_business_api_data", {}).get("id") == app_id
                                                  for a in linked) or bool(linked))
print("\nThe address above must match the Callback URL start_live.sh printed this time.")
