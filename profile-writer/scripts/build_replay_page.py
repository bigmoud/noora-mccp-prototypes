"""Build one self-contained Replay page (dashboard + embedded replay.json, no server calls)
for hosts that serve a single file, e.g. a claude.ai artifact.

    python3 -m scripts.build_replay_page   ->  dist/replay-only.html
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
data = json.loads((ROOT / "web" / "replay.json").read_text(encoding="utf-8"))
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
assert "sk-ant-" not in blob
head, body = html.split("<body>", 1)
title = head[head.index("<title>"):head.index("</title>") + 8]
style = head[head.index("<style>"):head.index("</style>") + 8]
body = body.replace("</body>", "").replace("</html>", "")
page = (f"{title}\n<meta name=\"claude:viewport-fit-sides\" content=\"cover\">\n{style}\n"
        f"<script>window.NPW_REPLAY_ONLY = true;</script>\n"
        f"<script id=\"replay-data\" type=\"application/json\">{blob}</script>\n{body}")
out = ROOT / "dist" / "replay-only.html"
out.parent.mkdir(exist_ok=True)
out.write_text(page, encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
