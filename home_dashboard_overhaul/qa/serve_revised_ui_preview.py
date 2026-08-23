#!/usr/bin/env python3
"""Serve the production renderer locally for responsive visual QA."""

from __future__ import annotations

from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from home_dashboard_overhaul.config_schema import normalize_config  # noqa: E402
from home_dashboard_overhaul.renderer import render_dashboard  # noqa: E402
from home_dashboard_overhaul.tests.fixtures import sample_snapshot  # noqa: E402
from home_dashboard_overhaul.themes import PRESETS  # noqa: E402


class PreviewHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        request = urlparse(self.path)
        if request.path in {"/web/dashboard.css", "/web/dashboard.js"}:
            asset = ROOT / request.path.lstrip("/")
            mime = "text/css" if asset.suffix == ".css" else "text/javascript"
            self._send(asset.read_bytes(), mime)
            return
        if request.path != "/":
            self.send_error(404)
            return

        query = parse_qs(request.query)
        theme = query.get("theme", ["Sapphire Glass"])[0]
        if theme not in PRESETS:
            theme = "Sapphire Glass"
        mode = query.get("mode", ["dark"])[0]
        if mode not in {"light", "dark"}:
            mode = "dark"
        view = query.get("view", ["month"])[0]
        if view not in {"month", "year"}:
            view = "month"
        try:
            scale = int(query.get("scale", ["100"])[0])
        except ValueError:
            scale = 100
        config = normalize_config(
            {
                "appearance": {
                    "preset": theme,
                    "mode": mode,
                    "text_scale": max(100, min(150, scale)),
                },
                "heatmap": {"calendar_view": view},
            }
        )
        dashboard = render_dashboard(
            sample_snapshot(date(2026, 8, 17)),
            config,
            anki_dark=mode == "dark",
            preview=True,
        )
        document = (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Home Dashboard revised UI QA</title>"
            "<link rel=\"stylesheet\" href=\"/web/dashboard.css\"></head>"
            "<body>" + dashboard + "<script src=\"/web/dashboard.js\"></script></body></html>"
        )
        self._send(document.encode("utf-8"), "text/html; charset=utf-8")

    def _send(self, payload: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), PreviewHandler)
    print("Revised UI preview: http://127.0.0.1:8765/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
