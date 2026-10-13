"""Embed data/latest.json into site/template.html -> site/index.new.html (plain Python, no packages).

Run from the repo root:  python site/build_page.py
Then test:               node site/test_page.mjs site/index.new.html
On success the workflow renames index.new.html to index.html.
"""
import datetime, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(ROOT, "site", "template.html")
out = os.path.join(ROOT, "site", sys.argv[1] if len(sys.argv) > 1 else "index.new.html")

with open(os.path.join(ROOT, "data", "latest.json"), encoding="utf-8") as f:
    data = json.load(f)
for key in ("settings", "classes", "assets", "correlation", "monthly", "checks"):
    if key not in data:
        sys.exit(f"latest.json is missing '{key}'")

blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
html = open(src, encoding="utf-8").read()
html, n = re.subn(r"/\*__DATA_START__\*/.*?/\*__DATA_END__\*/",
                  lambda m: "/*__DATA_START__*/" + blob + "/*__DATA_END__*/", html, count=1, flags=re.S)
if n != 1:
    sys.exit("data marker not found in template")
html = html.replace("__PAGE_BUILT__", datetime.date.today().isoformat())
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"wrote {out}: {len(html)/1024:.0f} KB, window {data['settings']['window']['start']}..{data['settings']['window']['end']}")
