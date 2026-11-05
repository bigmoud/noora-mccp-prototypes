"""Checks the Claude extractor's request and response handling against a fake API server,
so it can be tested without a key. Run:  python3 -m unittest -v tests.test_claude_client"""
import json
import threading
import unittest
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.config import settings
from app.extractor import ClaudeExtractor

CAPTURED = {}


class FakeAnthropic(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        CAPTURED["body"], CAPTURED["headers"] = body, dict(self.headers)
        reply = {"content": [{"type": "tool_use", "name": "record_signals", "input": {
            "speaker": "husband", "sensitive_event": False,
            "signals": [{"signal": "stage", "value": "delivered", "subject": "registered_mother",
                         "evidence": "delivery ho gayi", "date_phrase": "", "date_precision": "none", "confidence": "high"},
                        {"signal": "home_address", "value": "x", "subject": "registered_mother", "evidence": "x",
                         "date_precision": "none", "confidence": "high"}]}}],
            "usage": {"input_tokens": 900, "output_tokens": 120}}
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ClaudeClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), FakeAnthropic)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls._saved = (settings.anthropic_base_url, settings.anthropic_api_key)
        settings.anthropic_base_url = f"http://127.0.0.1:{cls.srv.server_port}"
        settings.anthropic_api_key = "test"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        settings.anthropic_base_url, settings.anthropic_api_key = cls._saved

    def test_request_and_parse(self):
        out = ClaudeExtractor("claude-test").extract("Meri wife ki delivery ho gayi", date(2026, 11, 5),
                                                     [("nurse", "Kya delivery ho gayi?")])
        b = CAPTURED["body"]
        self.assertEqual(b["tool_choice"], {"type": "tool", "name": "record_signals"})
        self.assertEqual(len(b["tools"]), 1)  # the model gets exactly one tool and it only records
        self.assertNotIn("temperature", b)  # deprecated on current models
        self.assertIn("TARGET", b["messages"][0]["content"])
        self.assertIn("Message date: 2026-11-05", b["messages"][0]["content"])
        self.assertEqual(out.speaker, "husband")
        self.assertEqual([s["signal"] for s in out.signals], ["stage"])  # unknown signal dropped by code
        self.assertEqual((out.tokens_in, out.tokens_out), (900, 120))
        self.assertEqual(out.error, "")
        hdrs = {k.lower(): v for k, v in CAPTURED["headers"].items()}
        self.assertEqual(hdrs.get("anthropic-workspace-id"), "wrkspc_test")

    def test_spend_cap_blocks_calls(self):
        CAPTURED.clear()
        old = settings.spend_cap_usd
        settings.spend_cap_usd = 0.0
        try:
            out = ClaudeExtractor("claude-test").extract("hello", date(2026, 11, 5))
        finally:
            settings.spend_cap_usd = old
        self.assertIn("spend cap", out.error)
        self.assertNotIn("body", CAPTURED)  # no request left the machine


if __name__ == "__main__":
    unittest.main()
