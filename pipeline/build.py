"""
Inline everything into a single self-contained dashboard file.

Reads  : out/stats.json, out/insights.json, web/dashboard.template.html,
         web/vendor/* (Chart.js + three typefaces -- see web/vendor/README.md)
Writes : out/dashboard.html

The output makes zero external requests: no CDN, no font service, no backend, no
build tooling. Open it with a double click, email it to someone, drop it behind
any static host, or read it on a plane. That costs ~350kb of inlined assets,
which is a fair trade for a dashboard that renders identically everywhere.
"""

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
VENDOR = WEB / "vendor"
OUT = ROOT / "out" / "dashboard.html"

# (css family name, file stem, weight)
FONTS = [
    ("Bricolage Grotesque", "bricolage-grotesque-latin-700-normal", 700),
    ("Bricolage Grotesque", "bricolage-grotesque-latin-800-normal", 800),
    ("Source Serif 4", "source-serif-4-latin-400-normal", 400),
    ("Source Serif 4", "source-serif-4-latin-600-normal", 600),
    ("IBM Plex Mono", "ibm-plex-mono-latin-400-normal", 400),
    ("IBM Plex Mono", "ibm-plex-mono-latin-500-normal", 500),
    ("IBM Plex Mono", "ibm-plex-mono-latin-600-normal", 600),
]


def font_css():
    faces = []
    for family, stem, weight in FONTS:
        b64 = base64.b64encode((VENDOR / "fonts" / f"{stem}.woff2").read_bytes()).decode()
        faces.append(
            f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};"
            f"font-display:swap;src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
        )
    return "\n".join(faces)


def main():
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": json.loads((ROOT / "out" / "stats.json").read_text()),
        "insights": json.loads((ROOT / "out" / "insights.json").read_text()),
    }

    html = (WEB / "dashboard.template.html").read_text()
    html = html.replace("/*__FONTS__*/", font_css())
    # A literal </script> inside injected content would close the tag early.
    html = html.replace("//__CHARTJS__", (VENDOR / "chart.umd.min.js").read_text().replace("</script>", "<\\/script>"))
    html = html.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"built dashboard ({OUT.stat().st_size // 1024}kb, no external requests) -> {OUT}")


if __name__ == "__main__":
    main()
