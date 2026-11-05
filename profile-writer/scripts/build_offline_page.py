"""One self-contained offline page (dashboard + embedded demo.json) for single-file hosts,
e.g. a claude.ai artifact.   python3 -m scripts.build_offline_page  ->  dist/offline.html"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
data = json.loads((ROOT / "web" / "demo.json").read_text(encoding="utf-8"))
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
assert "sk-ant-" not in blob
head, body = html.split("<body>", 1)
keep = head[head.index("<title>"):head.index("</style>") + 8]   # title, viewport-fit meta, styles
body = body.replace("</body>", "").replace("</html>", "")
page = (f"{keep}\n<script>window.NPW_OFFLINE_ONLY = true;</script>\n"
        f"<script id=\"demo-data\" type=\"application/json\">{blob}</script>\n{body}")
out = ROOT / "dist" / "offline.html"
out.parent.mkdir(exist_ok=True)
out.write_text(page, encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
