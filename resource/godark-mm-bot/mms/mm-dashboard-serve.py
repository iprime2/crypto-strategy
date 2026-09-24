#!/usr/bin/env python3
"""Serve tabbed MM dashboard (testnet / devnet) — refresh on load + background interval."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ARTIFACTS_ROOT = Path.home() / "scripts/mms/artifacts"
HTML_PATH = ARTIFACTS_ROOT / "mm-dashboard.html"
JSON_PATH = ARTIFACTS_ROOT / "mm-metrics" / "dashboard-both-latest.json"
DASH_SCRIPT = Path.home() / "scripts/mms/mm-dashboard.py"
CHARTS_JS = Path.home() / "scripts/mms/mm-dashboard-charts.js"

_refresh_lock = threading.Lock()


def refresh_dashboard() -> None:
    with _refresh_lock:
        subprocess.run(
            [sys.executable, str(DASH_SCRIPT)],
            check=False,
            capture_output=True,
        )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        refresh_dashboard()

        if path in ("/", "/index.html"):
            body = HTML_PATH.read_bytes() if HTML_PATH.exists() else b"<h1>Dashboard not ready</h1>"
            self._send_bytes(body, "text/html; charset=utf-8")
            return

        if path == "/api/dashboard.json":
            body = JSON_PATH.read_bytes() if JSON_PATH.exists() else b"{}"
            self._send_bytes(body, "application/json")
            return

        if path == "/health":
            self._send_bytes(b"ok", "text/plain")
            return

        if path == "/dashboard-charts.js":
            body = CHARTS_JS.read_bytes() if CHARTS_JS.exists() else b"console.error('dashboard-charts.js missing');"
            self._send_bytes(body, "application/javascript; charset=utf-8")
            return

        self.send_response(404)
        self.end_headers()

    def _send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def background_refresh(interval_sec: int) -> None:
    while True:
        time.sleep(interval_sec)
        refresh_dashboard()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve MM dashboard HTTP")
    parser.add_argument("--host", default=os.environ.get("MM_DASHBOARD_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MM_DASHBOARD_PORT", "8799")))
    parser.add_argument("--refresh-sec", type=int, default=60)
    args = parser.parse_args()

    ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)
    refresh_dashboard()

    if args.refresh_sec > 0:
        t = threading.Thread(target=background_refresh, args=(args.refresh_sec,), daemon=True)
        t.start()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"MM dashboard: http://127.0.0.1:{args.port}/")
    print(f"  tabs: testnet | devnet (use #devnet in URL to deep-link)")
    print(f"  refresh: every {args.refresh_sec}s + on each request")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
