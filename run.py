import argparse
import http.server
import os
import socketserver
import subprocess
import sys
import webbrowser
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
PORT = int(os.environ.get("PORT", 8000))


def step(n, total, label, script):
    print(f"\n[{n}/{total}] {label}")
    r = subprocess.run([PY, str(ROOT / "pipeline" / script)])
    if r.returncode != 0:
        sys.exit(f"\n{script} failed. Stopping.")


def serve():
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "out"))
    socketserver.TCPServer.allow_reuse_address = True
    url = f"http://localhost:{PORT}/dashboard.html"
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"\n  Dashboard ready → {url}")
        print("  Ctrl+C to stop\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-serve", action="store_true", help="build but don't start the server")
    ap.add_argument("--keep-data", action="store_true", help="reuse the existing CSV")
    a = ap.parse_args()

    try:
        import pandas  # noqa: F401
    except ImportError:
        sys.exit("pandas is missing. Run:  pip install -r requirements.txt")

    mode = "live (ANTHROPIC_API_KEY found)" if os.environ.get("ANTHROPIC_API_KEY") else "cached (no API key set)"
    print(f"Pyngyn AI Insights\nInsight mode: {mode}")

    steps = [("Simulating task data", "generate_data.py")] if not a.keep_data else []
    steps += [
        ("Analyzing for bottlenecks", "analyze.py"),
        ("Writing insights", "insights.py"),
        ("Building dashboard", "build.py"),
    ]
    for i, (label, script) in enumerate(steps, 1):
        step(i, len(steps), label, script)

    if a.no_serve:
        print(f"\n  Open → {ROOT / 'out' / 'dashboard.html'}\n")
    else:
        serve()


if __name__ == "__main__":
    main()
