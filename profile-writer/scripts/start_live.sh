#!/usr/bin/env bash
# Live WhatsApp demo: starts the profile-writer server and a free public HTTPS tunnel,
# then prints the webhook address to paste into Meta.   Usage:  ./scripts/start_live.sh
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "No .env file here. Copy .env.example to .env and fill it in."; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || { echo "Python 3.9+ needed (python3 --version)."; exit 1; }

missing=$(python3 - <<'PY'
import re
env = dict(re.findall(r"^\s*([A-Z_]+)\s*=\s*(.*?)\s*$", open(".env").read(), re.M))
need = ["ANTHROPIC_API_KEY", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_APP_SECRET",
        "WHATSAPP_VERIFY_TOKEN", "ALLOWED_TEST_NUMBERS", "DASHBOARD_TOKEN"]
print(" ".join(k for k in need if not env.get(k)))
PY
)
[ -z "$missing" ] || { echo "Fill these in .env first: $missing"; exit 1; }
command -v cloudflared >/dev/null || { echo "Install the tunnel once:  brew install cloudflared"; exit 1; }

PORT=$(grep -E '^PORT=' .env | cut -d= -f2); PORT=${PORT:-8000}
LOG=$(mktemp)
python3 -m app.server & SERVER=$!
cloudflared tunnel --no-autoupdate --url "http://localhost:$PORT" >"$LOG" 2>&1 & TUNNEL=$!
trap 'kill $SERVER $TUNNEL 2>/dev/null; rm -f "$LOG"' EXIT INT TERM

URL=""
for _ in $(seq 1 40); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)
  [ -n "$URL" ] && break; sleep 1
done
[ -n "$URL" ] || { echo "The tunnel didn't start. Details:"; cat "$LOG"; exit 1; }

cat <<MSG

  Meta → WhatsApp → Configuration → Webhook → Edit
    Callback URL:  $URL/webhook
    Verify token:  the WHATSAPP_VERIFY_TOKEN value in .env
  Then subscribe to the "messages" field.

  Nurse inbox (this computer):  the "Dashboard:" link printed above
  The tunnel address changes every time you restart this script: paste the new one into Meta.
  Ctrl+C stops everything.

MSG
wait $SERVER
