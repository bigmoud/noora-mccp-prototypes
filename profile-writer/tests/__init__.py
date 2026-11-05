"""Test settings are set before any app module reads its configuration."""
import os
import tempfile

os.environ.update({
    "PSEUDONYM_KEY": "test-key",
    "WHATSAPP_APP_SECRET": "test-secret",
    "ALLOWED_TEST_NUMBERS": "919800000001",
    "WHATSAPP_LIVE": "false",
    "ANTHROPIC_API_KEY": "",
    "DB_PATH": ":memory:",
    "SPEND_LEDGER": os.path.join(tempfile.mkdtemp(), "ledger.json"),
    "ANTHROPIC_WORKSPACE_ID": "wrkspc_test",
})
