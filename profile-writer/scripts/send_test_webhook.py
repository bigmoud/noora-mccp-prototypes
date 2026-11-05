"""Send a Meta-shaped, correctly signed webhook to the local server, exactly as WhatsApp
would. Lets you test the live path (signature, allowlist, pseudonym, pipeline) without a
Meta account. Uses WHATSAPP_APP_SECRET from .env.

    python3 -m scripts.send_test_webhook --from 919800000001 "Meri wife ki delivery ho gayi kal"
    python3 -m scripts.send_test_webhook --from 919811111111 "not on the allowlist"   # dropped
    python3 -m scripts.send_test_webhook --bad-signature "rejected"
"""
import argparse
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
import uuid

from app.config import settings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("--from", dest="sender", default=next(iter(settings.allowed_numbers), "919800000001"))
    ap.add_argument("--url", default=f"http://127.0.0.1:{settings.port}/webhook")
    ap.add_argument("--bad-signature", action="store_true")
    a = ap.parse_args()
    payload = {"object": "whatsapp_business_account", "entry": [{"id": "WABA_TEST", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"display_phone_number": "15550000000", "phone_number_id": "TEST"},
        "contacts": [{"profile": {"name": "Test Sender"}, "wa_id": a.sender}],
        "messages": [{"from": a.sender, "id": "wamid.TEST" + uuid.uuid4().hex, "timestamp": str(int(time.time())),
                      "type": "text", "text": {"body": a.text}}]}}]}]}
    raw = json.dumps(payload, ensure_ascii=False).encode()
    secret = b"wrong" if a.bad_signature else settings.wa_app_secret.encode()
    sig = "sha256=" + hmac.new(secret, raw, hashlib.sha256).hexdigest()
    req = urllib.request.Request(a.url, data=raw, headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig})
    try:
        with urllib.request.urlopen(req) as r:
            print(r.status, r.read().decode())
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode())


if __name__ == "__main__":
    main()
