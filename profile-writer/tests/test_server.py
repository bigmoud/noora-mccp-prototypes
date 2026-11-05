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


if __name__ == "__main__":
    unittest.main()
