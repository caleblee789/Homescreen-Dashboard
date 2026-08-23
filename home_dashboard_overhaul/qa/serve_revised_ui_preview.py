#!/usr/bin/env python3
"""Serve the production renderer locally for responsive visual QA."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
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
from home_dashboard_overhaul.models import (  # noqa: E402
    AvailabilityReason,
    BrowseTarget,
    BrowseTargetKind,
    DayDomainState,
    DayRelation,
    EventItem,
    LastSevenDaysStats,
    LongTermStats,
    QueueStats,
    RateMetric,
    TodayStats,
    ValueState,
    VerseContent,
)


def stress_snapshot(reference: date, *, events_enabled: bool = True):
    """Return the release-plan long-value fixture for browser layout QA."""

    snapshot = sample_snapshot(reference)
    now = datetime.now().astimezone()
    eta_target = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), now.tzinfo) + timedelta(minutes=15)
    eta_seconds = max(1, int((eta_target - now).total_seconds()) + 2)
    january_event = EventItem(
        "stress-january",
        "Winter Pediatrics Review Conference",
        "2026-01-05",
        -229,
    )
    december_event = EventItem(
        "stress-december",
        "Comprehensive Pediatric NBME Readiness Assessment and Long-Range Study Planning Session",
        "2026-12-29",
        129,
    )
    events = (january_event, december_event) if events_enabled else ()
    days = {
        iso: replace(day, events=ValueState.available(()))
        for iso, day in snapshot.facts.days.items()
    }
    template = days[reference.isoformat()]
    days["2026-01-05"] = replace(
        template,
        date="2026-01-05",
        relation=DayRelation.PAST,
        reviews_completed=ValueState.available(125),
        new_cards_studied=ValueState.available(18),
        reviews_due=ValueState.unavailable(AvailabilityReason.FORECAST_OUT_OF_RANGE),
        again_count=ValueState.available(7),
        events=ValueState.available((january_event,) if events_enabled else ()),
        browse_target=BrowseTarget(BrowseTargetKind.REVIEWED, "cid:310001", True, (310001,)),
        domain_state=DayDomainState.TROUBLE,
    )
    days["2026-12-29"] = replace(
        template,
        date="2026-12-29",
        relation=DayRelation.FUTURE,
        reviews_completed=ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE),
        new_cards_studied=ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE),
        reviews_due=ValueState.available(88),
        again_count=ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE),
        events=ValueState.available((december_event,) if events_enabled else ()),
        browse_target=BrowseTarget(BrowseTargetKind.DUE, "cid:320001", True, (320001,)),
        domain_state=DayDomainState.FUTURE_DUE,
    )
    facts = replace(
        snapshot.facts,
        today=ValueState.available(TodayStats(12_486, 1_048, 12_486 * 125.4, 125.4)),
        queue=ValueState.available(QueueStats(32, 14, 78, 124, eta_seconds)),
        events=ValueState.available(events),
        last_seven_days=ValueState.available(LastSevenDaysStats(
            cards_studied=12_486,
            new_cards_studied=1_048,
            retention=RateMetric.from_counts(11_237, 12_486),
            again_rate=RateMetric.from_counts(1_249, 12_486),
        )),
        long_term=ValueState.available(LongTermStats(
            average_reviews_per_active_day=12_486,
            active_days_percent=92,
            longest_streak=1_517,
            current_streak=1_024,
            lifetime_retention=RateMetric.from_counts(974_376, 1_082_640),
            lifetime_cards_studied=1_082_640,
        )),
        days=days,
    )
    return replace(
        snapshot,
        facts=facts,
        verse=VerseContent(
            "The steadfast love of the Lord never ceases; his mercies never come to an end; "
            "they are new every morning; great is your faithfulness, and your loving care "
            "continues through every season of patient study and service.",
            "Lamentations 3:22–23",
        ),
    )


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
        fixture = query.get("fixture", ["reference"])[0]
        events_enabled = query.get("events", ["present"])[0] != "none"
        snapshot = (
            stress_snapshot(date(2026, 8, 22), events_enabled=events_enabled)
            if fixture == "stress"
            else sample_snapshot(date(2026, 8, 17))
        )
        selected = query.get("selected", [""])[0]
        if selected:
            config["_preview_selected_date"] = selected
        dashboard = render_dashboard(
            snapshot,
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
