"""Access rules for the hosted dashboard: bearer token, allowed origins, webhook signature."""
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from app.config import settings
from app import server


class Access(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings.dashboard_token = "tok-123"
        settings.allowed_origins = {"https://fellows.github.io"}
        server.seed(server.store)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def req(self, path, method="GET", headers=None, body=None):
        r = urllib.request.Request(self.base + path, method=method, headers=headers or {}, data=body)
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def test_bearer_token(self):
        self.assertEqual(self.req("/api/state", headers={"Authorization": "Bearer tok-123"})[0], 200)
        self.assertEqual(self.req("/api/state", headers={"Authorization": "Bearer wrong"})[0], 401)
        self.assertEqual(self.req("/api/state")[0], 401)

    def test_cors_only_for_allowed_origin(self):
        code, hdrs, _ = self.req("/api/state", "OPTIONS", {"Origin": "https://fellows.github.io"})
        self.assertEqual(code, 204)
        self.assertEqual(hdrs.get("Access-Control-Allow-Origin"), "https://fellows.github.io")
        self.assertEqual(self.req("/api/state", "OPTIONS", {"Origin": "https://evil.example"})[0], 403)
        _, hdrs, _ = self.req("/api/state", headers={"Origin": "https://evil.example", "Authorization": "Bearer tok-123"})
        self.assertNotIn("Access-Control-Allow-Origin", hdrs)

    def test_post_needs_csrf_header(self):
        body = json.dumps({"rollout_mode": "shadow"}).encode()
        h = {"Authorization": "Bearer tok-123", "Content-Type": "application/json"}
        self.assertEqual(self.req("/api/settings", "POST", h, body)[0], 403)
        self.assertEqual(self.req("/api/settings", "POST", {**h, "X-NPW": "1"}, body)[0], 200)

    def test_unsigned_webhook_rejected(self):
        self.assertEqual(self.req("/webhook", "POST", {"Content-Type": "application/json"}, b"{}")[0], 401)


class AutoAck(unittest.TestCase):
    def setUp(self):
        from app import privacy, whatsapp
        self.sent = []
        self._send = whatsapp.send_text
        whatsapp.send_text = lambda phone, text: (self.sent.append((phone, text)) or (True, "wamid.test"))
        self.addCleanup(setattr, whatsapp, "send_text", self._send)
        self.uid = privacy.pseudonym("919800000001")
        server.store.upsert_family(self.uid, "Live tester", "ANC_EDD")
        server.store.set_contact(self.uid, "919800000001")
        self.addCleanup(server.store.erase_family, self.uid)

    def test_ack_once_per_cooldown_and_never_after_stop(self):
        self.assertFalse(server.auto_ack(self.uid, "STOP", delay=0))
        self.assertTrue(server.auto_ack(self.uid, "Meri delivery ho gayi", delay=0))
        self.assertFalse(server.auto_ack(self.uid, "Aur ek baat", delay=0))  # within the cooldown
        self.assertEqual(len(self.sent), 1)
        self.assertNotIn("doctor", self.sent[0][1].lower())  # fixed text, nothing medical beyond 108
        out = server.store.q("SELECT author FROM messages WHERE uid=? AND direction='out'", (self.uid,))
        self.assertEqual([r["author"] for r in out], ["auto"])

    def test_no_ack_for_numbers_off_the_allowlist(self):
        from app import privacy
        other = privacy.pseudonym("919811111111")
        server.store.upsert_family(other, "Stranger", "ANC_EDD")
        server.store.set_contact(other, "919811111111")
        self.addCleanup(server.store.erase_family, other)
        self.assertFalse(server.auto_ack(other, "hello", delay=0))
        self.assertEqual(self.sent, [])


if __name__ == "__main__":
    unittest.main()
