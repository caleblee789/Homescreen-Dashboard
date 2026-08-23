"""Native 100%-scale contact-sheet capture probe for a disposable Anki run.

Install this file as ``zz_hdo_contact_sheet_probe/__init__.py`` beside the
unchanged production add-on in a helper-generated sync-disabled profile.  The
probe renders the exact installed production renderer and assets in controlled
AnkiWebView windows, captures the canonical four-theme matrix plus true
full-screen Month and Year dashboards, writes a fail-closed report, and quits
only its own isolated Anki process.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import traceback
from typing import Any, Dict

import home_dashboard_overhaul
from aqt import gui_hooks, mw
from aqt.qt import QApplication, QTimer, Qt
from aqt.webview import AnkiWebView

from home_dashboard_overhaul.analytics import representative_preview_snapshot
from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.models import (
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
from home_dashboard_overhaul.renderer import render_dashboard
from home_dashboard_overhaul.settings_model import preview_snapshot_with_staged_events


RUN_ROOT = Path(os.environ.get("HDO_CONTACT_PROBE_ROOT", ""))
EXPECTED_PROFILE = os.environ.get("HDO_CONTACT_PROBE_PROFILE", "")
ENABLED = (
    str(RUN_ROOT).startswith("/private/tmp/anki-release-qa.")
    and EXPECTED_PROFILE.startswith("Codex QA ")
)
OUTPUT_ROOT = RUN_ROOT / "hdo-contact-sheet-probe"
REPORT_PATH = OUTPUT_ROOT / "runtime-report.json"
THEMES = (
    ("SG", "Sapphire Glass"),
    ("GR", "Graphite"),
    ("EM", "Emerald"),
    ("HC", "High Contrast"),
)
LAYOUTS = (
    ("C", "compact", 560, 1050),
    ("W", "wide", 1440, 900),
)
REFERENCE_DATE = "2026-08-22"
REPORT: Dict[str, Any] = {
    "schema_version": 2,
    "status": "running",
    "errors": [],
    "scale_policy": {
        "ui_scale_percent": 100,
        "text_scale_percent": 100,
        "excluded_ui_scales_percent": [125, 150, 200],
    },
    "captures": {},
    "states": {},
    "stress_checks": {},
}
_started = False
_web: Any = None
_cases: list[dict[str, Any]] = []
_case_index = 0
_interaction_cases: list[dict[str, Any]] = []
_interaction_index = 0
_stress_width_index = 0
STRESS_WIDTHS = (319, 439, 440, 939, 940, 1280)
PACKAGE_ROOT = Path(home_dashboard_overhaul.__file__).resolve().parent


def _web_asset_url(filename: str) -> str:
    digest = hashlib.sha256((PACKAGE_ROOT / "web" / filename).read_bytes()).hexdigest()[:16]
    return "/_addons/home_dashboard_overhaul/web/{}?v={}".format(filename, digest)


DASHBOARD_CSS_URL = _web_asset_url("dashboard.css")
DASHBOARD_JS_URL = _web_asset_url("dashboard.js")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_report() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(REPORT, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _finish(passed: bool) -> None:
    global _web
    if REPORT.get("status") != "running":
        return
    REPORT["status"] = "passed" if passed and not REPORT["errors"] else "failed"
    _write_report()
    try:
        if _web is not None:
            _web.close()
            _web.deleteLater()
            _web = None
    finally:
        QTimer.singleShot(180, QApplication.instance().quit)


def _error(stage: str, exc: BaseException) -> None:
    REPORT["errors"].append(
        {
            "stage": stage,
            "error": "{}: {}".format(type(exc).__name__, exc),
            "traceback": traceback.format_exc(),
        }
    )
    _finish(False)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _sample_color_count(pixmap: Any) -> int:
    """Return a cheap paint-readiness signal without adding image dependencies."""
    image = pixmap.toImage()
    width = image.width()
    height = image.height()
    step_x = max(1, width // 24)
    step_y = max(1, height // 18)
    colors: set[int] = set()
    for x in range(step_x // 2, width, step_x):
        for y in range(step_y // 2, height, step_y):
            colors.add(int(image.pixel(x, y)))
            if len(colors) >= 16:
                return len(colors)
    return len(colors)


def _capture(name: str, state: dict[str, Any], *, full_screen: bool) -> None:
    QApplication.processEvents()
    _web.repaint()
    QApplication.processEvents()
    path = OUTPUT_ROOT / "{}.png".format(name)
    pixmap = _web.grab()
    sample_color_count = _sample_color_count(pixmap)
    _require(
        sample_color_count >= 8,
        "native web capture is visually blank ({} sampled colors)".format(
            sample_color_count
        ),
    )
    saved = pixmap.save(str(path), "PNG")
    _require(bool(saved), "could not save {}".format(path))
    window_title = str(_web.windowTitle())
    _require(
        window_title.startswith(EXPECTED_PROFILE + " · "),
        "capture window title does not identify the disposable profile",
    )
    frame_geometry = _web.frameGeometry()
    record = {
        "file": path.name,
        "sha256": _sha256(path),
        "saved": True,
        "logical_width": _web.width(),
        "logical_height": _web.height(),
        "frame_logical_width": frame_geometry.width(),
        "frame_logical_height": frame_geometry.height(),
        "pixel_width": pixmap.width(),
        "pixel_height": pixmap.height(),
        "device_pixel_ratio": pixmap.devicePixelRatio(),
        "ui_scale_percent": 100,
        "text_scale_percent": 100,
        "full_screen": bool(full_screen),
        "sample_color_count": sample_color_count,
        "window_title": window_title,
        "window_title_matches_profile": True,
        "dom": state,
    }
    REPORT["captures"][name] = record


def _base_config(theme: str, mode: str, view: str) -> dict[str, Any]:
    config = normalize_config({})
    config["appearance"].update(
        preset=theme,
        mode=mode,
        opacity=100,
        text_scale=100,
    )
    config["heatmap"].update(
        calendar_view=view,
        week_start=0,
        history_days=0,
        forecast_days=90,
        show_due_forecast=True,
    )
    config["events"]["items"] = [
        {
            "id": "contact-sheet-pediatric-nbme",
            "name": "Pediatric NBME",
            "date": "2026-08-28",
            "archived": False,
            "created_at": "2026-08-22T12:00:00-05:00",
            "archived_at": "",
        }
    ]
    return config


def _html(theme: str, mode: str, view: str) -> str:
    config = _base_config(theme, mode, view)
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    snapshot = preview_snapshot_with_staged_events(snapshot, config, REFERENCE_DATE)
    return render_dashboard(
        snapshot,
        config,
        anki_dark=mode == "dark",
        preview=True,
    )


def _interaction_html(theme: str, mode: str) -> str:
    """Build a QA-only state board from the production token scope and classes."""

    rendered = _html(theme, mode, "month")
    prefix, separator, _remainder = rendered.partition('<main class="hdo-stack">')
    _require(bool(separator), "could not isolate the dashboard token scope")
    prefix = prefix.replace(
        '<div id="hdo-dashboard"',
        '<div id="hdo-dashboard" data-hdo-state-fixture="true"',
        1,
    )
    state_style = """
<style>
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-board { display:grid; gap:12px; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-heading { align-items:end; display:flex; justify-content:space-between; gap:12px; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-heading h1 { font-size:20px; line-height:1.2; margin:0; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-heading p { color:var(--ui-text-secondary); margin:0; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-columns { display:grid; gap:12px; grid-template-columns:repeat(2, minmax(0, 1fr)); }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-column { display:grid; gap:10px; align-content:start; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-panel { background:var(--ui-card-background); border:1px solid var(--ui-border-subtle); border-radius:8px; padding:10px 11px; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-panel h2 { color:var(--ui-eyebrow); font-size:10px; letter-spacing:.06em; margin:0 0 9px; text-transform:uppercase; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-row { align-items:center; display:flex; flex-wrap:wrap; gap:8px; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-item { color:var(--ui-text-secondary); display:grid; font-size:10px; gap:4px; justify-items:center; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-cell-grid { display:grid; gap:8px; grid-template-columns:repeat(6, minmax(42px, 1fr)); }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-cell-grid .hdo-calendar-day { height:40px; padding:5px; width:100%; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-cell-grid .hdo-date-number { font-size:11px; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-progress-grid { display:grid; gap:10px; grid-template-columns:repeat(2, minmax(0, 1fr)); }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-progress-sample { background:var(--ui-surface-2); border:1px solid var(--ui-border-subtle); border-radius:6px; padding:9px; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-progress-sample p { color:var(--ui-text-secondary); font-size:10px; margin:0 0 5px; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-fixture-primary-hover { background:var(--ui-accent-hover) !important; border-color:var(--ui-accent-hover) !important; color:var(--ui-on-accent) !important; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-fixture-primary-pressed { background:var(--ui-accent-pressed) !important; border-color:var(--ui-accent-pressed) !important; color:var(--ui-on-accent) !important; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-fixture-control-hover { background:var(--ui-control-hover) !important; border-color:var(--ui-accent-border) !important; color:var(--ui-accent) !important; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-fixture-icon { align-items:center; display:inline-flex; justify-content:center; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-fixture-icon svg { fill:none; height:16px; stroke:currentColor; stroke-width:1.8; width:16px; }
#hdo-dashboard[data-hdo-state-fixture="true"] .hdo-state-note { color:var(--ui-text-tertiary); font-size:10px; margin:7px 0 0; }
</style>
"""
    icon = (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"></circle>'
        '<path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"></path></svg>'
    )

    def heat_cells(kind: str) -> str:
        items = []
        levels = range(1, 6) if kind == "due" else range(6)
        for level in levels:
            if kind == "due":
                opening = (
                    '<button type="button" class="hdo-calendar-day is-future" '
                    'data-heat-kind="due" data-due-level="{}">'
                ).format(level)
            else:
                opening = (
                    '<button type="button" class="hdo-calendar-day" '
                    'data-level="{}" data-heat-kind="completion">'
                ).format(level)
            items.append(
                '<span class="hdo-state-item">{}<span class="hdo-date-number">{}</span>'
                '</button><span>L{}</span></span>'.format(
                    opening,
                    level + 1,
                    level,
                )
            )
        return "".join(items)

    full_segments = (
        '<span class="hdo-progress-segment hdo-progress-segment--completed is-populated" style="--hdo-progress-count:100"></span>'
        '<span class="hdo-progress-segment hdo-progress-segment--new" style="--hdo-progress-count:0"></span>'
        '<span class="hdo-progress-segment hdo-progress-segment--learning" style="--hdo-progress-count:0"></span>'
        '<span class="hdo-progress-segment hdo-progress-segment--review" style="--hdo-progress-count:0"></span>'
    )
    empty_segments = (
        '<span class="hdo-progress-segment hdo-progress-segment--completed" style="--hdo-progress-count:0"></span>'
        '<span class="hdo-progress-segment hdo-progress-segment--new" style="--hdo-progress-count:0"></span>'
        '<span class="hdo-progress-segment hdo-progress-segment--learning" style="--hdo-progress-count:0"></span>'
        '<span class="hdo-progress-segment hdo-progress-segment--review" style="--hdo-progress-count:0"></span>'
    )
    partial_segments = (
        '<span class="hdo-progress-segment hdo-progress-segment--completed is-populated" style="--hdo-progress-count:60"></span>'
        '<span class="hdo-progress-segment hdo-progress-segment--new is-populated has-preceding-populated" style="--hdo-progress-count:10"></span>'
        '<span class="hdo-progress-segment hdo-progress-segment--learning is-populated has-preceding-populated" style="--hdo-progress-count:12"></span>'
        '<span class="hdo-progress-segment hdo-progress-segment--review is-populated has-preceding-populated" style="--hdo-progress-count:18"></span>'
    )

    def state_levels(state_class: str, fixture_state: str) -> str:
        return "".join(
            (
                '<span class="hdo-state-item"><button type="button" '
                'class="hdo-calendar-day {}" data-level="{}" data-fixture-state="{}">'
                '<span class="hdo-date-number">{}</span></button><span>L{}</span></span>'
            ).format(state_class, level, fixture_state, level + 1, level)
            for level in range(6)
        )

    base_states = (
        '<span class="hdo-state-item"><button type="button" class="hdo-calendar-day" data-level="0" data-fixture-state="empty-past"><span class="hdo-date-number">11</span></button><span>Past empty</span></span>'
        '<span class="hdo-state-item"><button type="button" class="hdo-calendar-day is-future" data-due-level="0" data-fixture-state="empty-future"><span class="hdo-date-number">12</span></button><span>Future empty</span></span>'
        '<span class="hdo-state-item"><button type="button" class="hdo-calendar-day is-out-of-month" data-level="2" data-fixture-state="outside"><span class="hdo-date-number">13</span></button><span>Outside</span></span>'
        '<span class="hdo-state-item"><button type="button" class="hdo-calendar-day is-future is-out-of-month" data-heat-kind="due" data-due-level="3" data-fixture-state="outside-due"><span class="hdo-date-number">14</span></button><span>Outside due</span></span>'
        '<span class="hdo-state-item"><button type="button" class="hdo-calendar-day is-today is-selected" data-level="3" data-fixture-state="today-selected"><span class="hdo-date-number">15</span></button><span>Today + selected</span></span>'
        '<span class="hdo-state-item"><button type="button" class="hdo-calendar-day" data-level="1" data-fixture-state="event-low"><span class="hdo-date-number">16</span><i class="hdo-event-marker"></i></button><span>Event low</span></span>'
        '<span class="hdo-state-item"><button type="button" class="hdo-calendar-day" data-level="5" data-fixture-state="event-high"><span class="hdo-date-number">17</span><i class="hdo-event-marker"></i></button><span>Event high</span></span>'
        '<span class="hdo-state-item"><button type="button" class="hdo-calendar-day is-future" data-heat-kind="due" data-due-level="4" data-fixture-state="event-due"><span class="hdo-date-number">18</span><i class="hdo-event-marker"></i></button><span>Event due</span></span>'
    )
    board = (
        '<main class="hdo-stack"><section class="hdo-state-board" aria-label="Interaction state fixture">'
        '<header class="hdo-state-heading"><div><p class="hdo-eyebrow">Color System QA</p>'
        '<h1>Interaction state fixture</h1></div><p>{} · {} · UI/text 100%</p></header>'
        '<div class="hdo-state-columns"><div class="hdo-state-column">'
        '<section class="hdo-state-panel"><h2>Button hierarchy</h2><div class="hdo-state-row">'
        '<button class="hdo-context-action hdo-context-action--primary">Default</button>'
        '<button class="hdo-context-action hdo-context-action--primary hdo-fixture-primary-hover">Hover</button>'
        '<button class="hdo-context-action hdo-context-action--primary hdo-fixture-primary-pressed">Pressed</button>'
        '<button class="hdo-context-action hdo-context-action--primary" disabled>Disabled</button>'
        '</div></section>'
        '<section class="hdo-state-panel"><h2>Controls</h2><div class="hdo-state-row">'
        '<div class="hdo-view-switch"><button aria-pressed="true">Month</button><button aria-pressed="false">Year</button></div>'
        '<button class="hdo-settings hdo-fixture-icon" aria-label="Settings default">{}</button>'
        '<button class="hdo-settings hdo-fixture-icon hdo-fixture-control-hover" aria-label="Settings hover">{}</button>'
        '</div></section>'
        '<section class="hdo-state-panel"><h2>Base, combined, and event states</h2><div class="hdo-state-cell-grid hdo-calendar-grid--month" style="--hdo-month-rows:2">{}</div></section>'
        '<section class="hdo-state-panel"><h2>Progress states</h2><div class="hdo-state-progress-grid">'
        '<div class="hdo-state-progress-sample" data-fixture-progress="empty"><p>Empty · 0%</p><div class="hdo-progress-track">{}</div></div>'
        '<div class="hdo-state-progress-sample" data-fixture-progress="partial"><p>Partial · 60%</p><div class="hdo-progress-track">{}</div></div>'
        '<div class="hdo-state-progress-sample" data-fixture-progress="full"><p>Complete · 100%</p><div class="hdo-progress-track">{}</div></div>'
        '</div><p class="hdo-state-note">Completed uses progress-complete; remaining segments retain stable study semantics.</p></section>'
        '</div><div class="hdo-state-column">'
        '<section class="hdo-state-panel"><h2>Completion levels 0–5</h2><div class="hdo-state-cell-grid">{}</div></section>'
        '<section class="hdo-state-panel"><h2>Reviews due levels 1–5</h2><div class="hdo-state-cell-grid">{}</div></section>'
        '<section class="hdo-state-panel"><h2>Today on completion levels</h2><div class="hdo-state-cell-grid">{}</div></section>'
        '<section class="hdo-state-panel"><h2>Selected on completion levels</h2><div class="hdo-state-cell-grid">{}</div></section>'
        '<section class="hdo-state-panel"><h2>Target-aware semantic values</h2><dl class="hdo-metric-list">'
        '<div class="hdo-metric-row hdo-value--new"><dt>New remaining</dt><dd>32</dd></div>'
        '<div class="hdo-metric-row hdo-value--learning"><dt>Learning remaining</dt><dd>14</dd></div>'
        '<div class="hdo-metric-row hdo-value--review"><dt>Reviews remaining</dt><dd>78</dd></div>'
        '<div class="hdo-metric-row hdo-value--buried"><dt>Buried</dt><dd>8</dd></div>'
        '<div class="hdo-metric-row hdo-value--success" data-fixture-metric="retention-success"><dt>Retention success</dt><dd>92.0%</dd></div>'
        '<div class="hdo-metric-row hdo-value--warning" data-fixture-metric="retention-warning"><dt>Retention warning</dt><dd>88.0%</dd></div>'
        '<div class="hdo-metric-row hdo-value--danger" data-fixture-metric="retention-danger"><dt>Retention danger</dt><dd>76.0%</dd></div>'
        '<div class="hdo-metric-row hdo-value--success" data-fixture-metric="again-success"><dt>Again success</dt><dd>8.0%</dd></div>'
        '<div class="hdo-metric-row hdo-value--warning" data-fixture-metric="again-warning"><dt>Again warning</dt><dd>12.0%</dd></div>'
        '<div class="hdo-metric-row hdo-value--danger" data-fixture-metric="again-danger"><dt>Again danger</dt><dd>24.0%</dd></div>'
        '</dl></section>'
        '</div></div></section></main></div>'
    ).format(
        theme,
        mode.title(),
        icon,
        icon,
        base_states,
        empty_segments,
        partial_segments,
        full_segments,
        heat_cells("completion"),
        heat_cells("due"),
        state_levels("is-today", "today"),
        state_levels("is-selected", "selected"),
    )
    return state_style + prefix + board


def _stress_snapshot(events_enabled: bool = True):
    reference = date.fromisoformat(REFERENCE_DATE)
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    now = datetime.now().astimezone()
    eta_target = datetime.combine(
        now.date() + timedelta(days=1),
        datetime.min.time(),
        now.tzinfo,
    ) + timedelta(minutes=15)
    eta_seconds = max(1, int((eta_target - now).total_seconds()) + 2)
    january_event = EventItem(
        "stress-january",
        "Winter Pediatrics Review Conference",
        "2026-01-05",
        (date(2026, 1, 5) - reference).days,
    )
    december_event = EventItem(
        "stress-december",
        "Comprehensive Pediatric NBME Readiness Assessment and Long-Range Study Planning Session",
        "2026-12-29",
        (date(2026, 12, 29) - reference).days,
    )
    events = (january_event, december_event) if events_enabled else ()
    days = {
        iso: replace(day, events=ValueState.available(()))
        for iso, day in snapshot.facts.days.items()
    }
    template = days[REFERENCE_DATE]
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


def _stress_html(view: str, selected: str, events_enabled: bool = True) -> str:
    config = _base_config("Sapphire Glass", "light", view)
    config["_preview_selected_date"] = selected
    return render_dashboard(
        _stress_snapshot(events_enabled),
        config,
        anki_dark=False,
        preview=True,
    )


def _render(case: dict[str, Any], continuation: Any) -> None:
    try:
        _web.setWindowTitle(
            "{} · {} · {}".format(EXPECTED_PROFILE, case["name"], "100%")
        )
        if case.get("full_screen"):
            screen = _web.screen() or QApplication.primaryScreen()
            _require(screen is not None, "no Qt screen is available for full-screen capture")
            geometry = screen.availableGeometry()
            case["screen_available_geometry"] = [
                geometry.x(),
                geometry.y(),
                geometry.width(),
                geometry.height(),
            ]
            _web.setGeometry(geometry)
            _web.show()
            QApplication.processEvents()
            _web.showFullScreen()
        else:
            _web.showNormal()
            _web.resize(int(case["width"]), int(case["height"]))
            _web.show()
        _web.stdHtml(
            _html(str(case["theme"]), str(case["mode"]), str(case["view"])),
            css=[DASHBOARD_CSS_URL],
            js=[DASHBOARD_JS_URL],
            context=_web,
        )
        QTimer.singleShot(
            1600 if case.get("full_screen") else 320,
            lambda: _inspect(case, continuation, 0),
        )
    except Exception as exc:
        _error(str(case.get("name", "render")), exc)


def _inspect(case: dict[str, Any], continuation: Any, attempt: int) -> None:
    script = """
(function () {
  var root = document.getElementById('hdo-dashboard');
  var cells = root ? root.querySelectorAll('.hdo-calendar-day') : [];
  var layout = root ? root.querySelector('.hdo-dashboard-layout') : null;
  var calendar = root ? root.querySelector('.hdo-calendar-card') : null;
  var rail = root ? root.querySelector('.hdo-insight-rail') : null;
  var metrics = root ? root.querySelector('.hdo-summary-metrics-grid') : null;
  var cards = root ? Array.from(root.querySelectorAll('.hdo-statistics-card')) : [];
  var bible = root ? root.querySelector('.hdo-bible-card') : null;
  var frame = root ? root.querySelector('.hdo-calendar-grid-frame') : null;
  var yearGrid = root ? root.querySelector('.hdo-calendar-grid--year') : null;
  var monthLabels = root ? Array.from(root.querySelectorAll('.hdo-year-month-label')) : [];
  if (!root || !layout || !calendar || !rail || !metrics || !bible || !frame || !cells.length) return {ready:false};
  function roundedBands(elements, axis) {
    return Array.from(new Set(elements.map(function (element) {
      return Math.round(element.getBoundingClientRect()[axis]);
    })));
  }
  function inside(inner, outer, tolerance) {
    return inner.left >= outer.left - tolerance && inner.right <= outer.right + tolerance &&
      inner.top >= outer.top - tolerance && inner.bottom <= outer.bottom + tolerance;
  }
  function colorFor(value) {
    var probe = document.createElement('span');
    probe.style.backgroundColor = value;
    root.appendChild(probe);
    var color = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return color;
  }
  function token(name) { return colorFor('var(--' + name + ')'); }
  function background(node) { return getComputedStyle(node).backgroundColor; }
  var style = root.getAttribute('style') || '';
  var rootRect = root.getBoundingClientRect();
  var layoutRect = layout.getBoundingClientRect();
  var calendarRect = calendar.getBoundingClientRect();
  var railRect = rail.getBoundingClientRect();
  var metricsRect = metrics.getBoundingClientRect();
  var bibleRect = bible.getBoundingClientRect();
  var frameRect = frame.getBoundingClientRect();
  var yearGridRect = yearGrid ? yearGrid.getBoundingClientRect() : null;
  var selected = root.querySelector('.hdo-calendar-day.is-selected');
  var selectedRect = selected ? selected.getBoundingClientRect() : null;
  var metricRows = roundedBands(cards, 'top').length;
  var metricColumns = roundedBands(cards, 'left').length;
  var metricNoOverlap = Array.from(root.querySelectorAll('.hdo-metric-row')).every(function (row) {
    var label = row.querySelector('dt');
    var value = row.querySelector('dd');
    if (!label || !value) return false;
    var labelRect = label.getBoundingClientRect();
    var valueRect = value.getBoundingClientRect();
    return labelRect.right <= valueRect.left + 1;
  });
  var cardsContained = cards.every(function (card) {
    var cardRect = card.getBoundingClientRect();
    return inside(cardRect, metricsRect, 1) && card.scrollWidth <= card.clientWidth + 1;
  });
  var yearComplete = !yearGrid || (
    monthLabels.length === 12 &&
    monthLabels.map(function (label) { return label.textContent.trim(); }).join('|') === 'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec' &&
    inside(yearGridRect, frameRect, 1) &&
    Array.from(cells).every(function (cell) { return inside(cell.getBoundingClientRect(), yearGridRect, 1); })
  );
  var yearOutsideCells = !yearGrid ? [] : Array.from(cells).filter(function (cell) {
    return !inside(cell.getBoundingClientRect(), yearGridRect, 1);
  }).map(function (cell) {
    var rect = cell.getBoundingClientRect();
    return {
      date:cell.dataset.date || '',
      column:cell.style.gridColumn || '',
      row:cell.style.gridRow || '',
      left:Number(rect.left.toFixed(2)),
      right:Number(rect.right.toFixed(2)),
      top:Number(rect.top.toFixed(2)),
      bottom:Number(rect.bottom.toFixed(2))
    };
  });
  var yearGridStyle = yearGrid ? window.getComputedStyle(yearGrid) : null;
  function reportRect(rect) {
    if (!rect) return null;
    return {
      left:Number(rect.left.toFixed(2)),
      right:Number(rect.right.toFixed(2)),
      top:Number(rect.top.toFixed(2)),
      bottom:Number(rect.bottom.toFixed(2)),
      width:Number(rect.width.toFixed(2)),
      height:Number(rect.height.toFixed(2))
    };
  }
  return {
    ready:true,
    view:root.dataset.hdoCalendarView || '',
    themeIdentity:root.dataset.hdoTheme || '',
    colorModeIdentity:root.dataset.hdoColorMode || '',
    textScale100:style.indexOf('--hdo-scale:1.0') >= 0,
    hostCanvasThemed:background(document.documentElement) === token('ui-canvas') &&
      background(document.body) === token('ui-canvas') && background(root) === token('ui-canvas'),
    colorSchemeApplied:getComputedStyle(document.documentElement).colorScheme.indexOf(root.dataset.hdoColorMode || '') >= 0 &&
      getComputedStyle(root).colorScheme.indexOf(root.dataset.hdoColorMode || '') >= 0,
    viewportWidth:window.innerWidth,
    viewportHeight:window.innerHeight,
    rootWidth:Number(rootRect.width.toFixed(2)),
    calendarCells:cells.length,
    monthLabels:monthLabels.length,
    monthLabelText:monthLabels.map(function (label) { return label.textContent.trim(); }),
    statisticsCards:cards.length,
    metricColumns:metricColumns,
    metricRows:metricRows,
    metricNoOverlap:metricNoOverlap,
    cardsContained:cardsContained,
    bibleAfter:bibleRect.top >= metricsRect.bottom - 1,
    wideSharedShell:calendarRect.right <= railRect.left + 1 && Math.abs(calendarRect.top - railRect.top) <= 1,
    stackedSharedShell:calendarRect.bottom <= railRect.top + 1,
    bottomAligned:Math.abs(calendarRect.bottom - railRect.bottom) <= 1 && Math.abs(calendarRect.bottom - bibleRect.bottom) <= 1,
    completeYearVisible:yearComplete,
    yearFrameRect:reportRect(frameRect),
    yearGridRect:reportRect(yearGridRect),
    yearGridClientWidth:yearGrid ? yearGrid.clientWidth : 0,
    yearGridScrollWidth:yearGrid ? yearGrid.scrollWidth : 0,
    yearGridColumnGap:yearGridStyle ? yearGridStyle.columnGap : '',
    yearGridTemplateColumns:yearGridStyle ? yearGridStyle.gridTemplateColumns : '',
    yearGridWeekVariable:yearGrid ? yearGrid.style.getPropertyValue('--hdo-year-weeks') : '',
    yearGridInsideFrame:!yearGrid || inside(yearGridRect, frameRect, 1),
    yearOutsideCellCount:yearOutsideCells.length,
    yearOutsideCells:yearOutsideCells,
    selectedDayVisible:!!selectedRect && inside(selectedRect, frameRect, 1),
    eventMarkers:root.querySelectorAll('.hdo-event-marker').length,
    completionLegendSwatches:root.querySelectorAll('.hdo-completion-legend i').length,
    dueLegendSwatches:root.querySelectorAll('.hdo-due-legend i').length,
    eventLegendMarkers:root.querySelectorAll('.hdo-legend-event').length,
    layoutContained:inside(layoutRect, rootRect, 1),
    overflowX:document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    bodyScrollHeight:document.body.scrollHeight,
    rootScrollHeight:root.scrollHeight
  };
})()
"""

    def inspected(value: object) -> None:
        try:
            state = value if isinstance(value, dict) else {"ready": False}
            expected_cells = 365 if case["view"] == "year" else 42
            ready = (
                bool(state.get("ready"))
                and state.get("view") == case["view"]
                and state.get("themeIdentity") == case["theme"]
                and state.get("colorModeIdentity") == case["mode"]
                and bool(state.get("textScale100"))
                and bool(state.get("hostCanvasThemed"))
                and bool(state.get("colorSchemeApplied"))
                and state.get("calendarCells") in (
                    {365, 366} if case["view"] == "year" else {28, 35, 42}
                )
                and state.get("statisticsCards") == 4
                and state.get("metricColumns") == 2
                and state.get("metricRows") == 2
                and bool(state.get("metricNoOverlap"))
                and bool(state.get("cardsContained"))
                and bool(state.get("bibleAfter"))
                and bool(state.get("completeYearVisible"))
                and bool(state.get("selectedDayVisible"))
                and int(state.get("eventMarkers", 0)) >= 1
                and state.get("completionLegendSwatches") == 5
                and state.get("dueLegendSwatches") == 3
                and state.get("eventLegendMarkers") == 1
                and bool(state.get("layoutContained"))
                and not bool(state.get("overflowX"))
            )
            if case.get("layout") == "wide" or case.get("full_screen"):
                ready = ready and bool(state.get("wideSharedShell")) and bool(state.get("bottomAligned"))
            else:
                ready = ready and bool(state.get("stackedSharedShell"))
            if not ready:
                if attempt < 12:
                    QTimer.singleShot(250, lambda: _inspect(case, continuation, attempt + 1))
                    return
                raise RuntimeError(
                    "dashboard did not settle into {} (expected about {} cells): {}".format(
                        case["name"], expected_cells, state
                    )
                )
            if not case.get("full_screen"):
                _require(
                    _web.width() == int(case["width"]) and _web.height() == int(case["height"]),
                    "native capture widget escaped requested logical dimensions",
                )
            else:
                expected_geometry = case.get("screen_available_geometry", [0, 0, 0, 0])
                frame_geometry = _web.frameGeometry()
                _require(_web.isFullScreen(), "Qt did not enter full-screen mode")
                _require(
                    frame_geometry.width() >= int(expected_geometry[2])
                    and frame_geometry.height() >= int(expected_geometry[3]),
                    "full-screen capture did not expand to the selected Qt available area: "
                    "content {}x{}, frame {}x{} expected at least {}x{}".format(
                        _web.width(),
                        _web.height(),
                        frame_geometry.width(),
                        frame_geometry.height(),
                        expected_geometry[2],
                        expected_geometry[3],
                    ),
                )
            REPORT["states"][str(case["name"])] = state
            QTimer.singleShot(240, lambda: _settled_capture(case, state, continuation))
        except Exception as exc:
            _error(str(case.get("name", "inspect")), exc)

    try:
        _web.evalWithCallback(script, inspected)
    except Exception as exc:
        _error(str(case.get("name", "inspect")), exc)


def _settled_capture(
    case: dict[str, Any],
    state: dict[str, Any],
    continuation: Any,
    attempt: int = 0,
) -> None:
    try:
        _capture(
            str(case["name"]),
            state,
            full_screen=bool(case.get("full_screen")),
        )
        continuation()
    except RuntimeError as exc:
        if "visually blank" in str(exc) and attempt < 8:
            _web.repaint()
            QTimer.singleShot(
                450,
                lambda: _settled_capture(case, state, continuation, attempt + 1),
            )
            return
        _error(str(case.get("name", "capture")), exc)
    except Exception as exc:
        _error(str(case.get("name", "capture")), exc)


def _poll_warm_up(attempt: int) -> None:
    try:
        QApplication.processEvents()
        _web.repaint()
        QApplication.processEvents()
        sample_color_count = _sample_color_count(_web.grab())
        if sample_color_count >= 8:
            REPORT["warm_up"] = {
                "status": "passed",
                "attempts": attempt + 1,
                "sample_color_count": sample_color_count,
            }
            _write_report()
            QTimer.singleShot(120, _capture_next_matrix_case)
            return
        if attempt < 10:
            QTimer.singleShot(450, lambda: _poll_warm_up(attempt + 1))
            return
        raise RuntimeError(
            "native Anki web view did not paint during warm-up ({} sampled colors)".format(
                sample_color_count
            )
        )
    except Exception as exc:
        _error("warm-up", exc)


def _start_warm_up() -> None:
    try:
        _web.setWindowTitle("{} · renderer warm-up · 100%".format(EXPECTED_PROFILE))
        _web.showNormal()
        _web.resize(560, 900)
        _web.show()
        _web.stdHtml(
            _html("Sapphire Glass", "light", "month"),
            css=[DASHBOARD_CSS_URL],
            js=[DASHBOARD_JS_URL],
            context=_web,
        )
        REPORT["warm_up"] = {"status": "running"}
        _write_report()
        QTimer.singleShot(1200, lambda: _poll_warm_up(0))
    except Exception as exc:
        _error("warm-up", exc)


def _capture_next_matrix_case() -> None:
    global _case_index
    if _case_index >= len(_cases):
        QTimer.singleShot(250, _start_stress_year)
        return
    case = _cases[_case_index]
    _case_index += 1
    _render(case, lambda: QTimer.singleShot(90, _capture_next_matrix_case))


STRESS_INSPECTION_SCRIPT = """
(function () {
  var root = document.getElementById('hdo-dashboard');
  if (!root) return {ready:false};
  var calendar = root.querySelector('.hdo-calendar-card');
  var rail = root.querySelector('.hdo-insight-rail');
  var metrics = root.querySelector('.hdo-summary-metrics-grid');
  var cards = Array.from(root.querySelectorAll('.hdo-statistics-card'));
  var bible = root.querySelector('.hdo-bible-card');
  var frame = root.querySelector('.hdo-calendar-grid-frame');
  var grid = root.querySelector('.hdo-calendar-grid');
  var selected = root.querySelector('.hdo-calendar-day.is-selected');
  var shell = root.querySelector('.hdo-calendar-shell');
  var heatmap = root.querySelector('.hdo-year-heatmap-content');
  var footer = root.querySelector('.hdo-calendar-footer');
  var contextEvent = root.querySelector('.hdo-next-event-line');
  var contextMarker = root.querySelector('[data-hdo-event-marker]');
  var eventSummary = root.querySelector('.hdo-event-summary');
  var eventMeta = root.querySelector('[data-hdo-event-meta]');
  var eventEmpty = root.querySelector('[data-hdo-event-empty]');
  var editEvent = root.querySelector('[data-hdo-edit-event]');
  var primaryAction = root.querySelector('[data-hdo-primary-action]');
  var dateState = root.querySelector('[data-hdo-date-state]');
  if (!calendar || !rail || !metrics || cards.length !== 4 || !bible || !frame || !grid || !selected || !shell || !heatmap || !footer || !contextEvent || !primaryAction || !dateState) return {ready:false};
  function rect(element) { return element.getBoundingClientRect(); }
  function visible(element) {
    return !!element && !element.hidden && getComputedStyle(element).display !== 'none';
  }
  function inside(inner, outer, tolerance) {
    return inner.left >= outer.left - tolerance && inner.right <= outer.right + tolerance &&
      inner.top >= outer.top - tolerance && inner.bottom <= outer.bottom + tolerance;
  }
  function colorFor(value) {
    var probe = document.createElement('span');
    probe.style.backgroundColor = value;
    root.appendChild(probe);
    var color = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return color;
  }
  function token(name) { return colorFor('var(--' + name + ')'); }
  function bands(elements, axis) {
    return Array.from(new Set(elements.map(function (element) {
      return Math.round(rect(element)[axis]);
    }))).length;
  }
  var calendarRect = rect(calendar);
  var railRect = rect(rail);
  var frameRect = rect(frame);
  var link = root.querySelector('[data-hdo-open-events]');
  var linkStyle = link ? getComputedStyle(link) : null;
  var linkTextHeight = link ? rect(link).height -
    Number(linkStyle.paddingTop.replace('px', '')) - Number(linkStyle.paddingBottom.replace('px', '')) -
    Number(linkStyle.borderTopWidth.replace('px', '')) - Number(linkStyle.borderBottomWidth.replace('px', '')) : 0;
  var linkLineHeight = linkStyle ? Number(linkStyle.lineHeight.replace('px', '')) : 0;
  var metricValues = {};
  root.querySelectorAll('[data-hdo-metric]').forEach(function (node) {
    metricValues[node.dataset.hdoMetric] = node.textContent.trim();
  });
  var cellHeights = Array.from(new Set(Array.from(root.querySelectorAll('.hdo-calendar-day')).map(function (cell) {
    return Number(rect(cell).height.toFixed(1));
  })));
  var editEventAdjacent = true;
  var editEventGap = null;
  if (visible(editEvent) && visible(eventSummary)) {
    var editRect = rect(editEvent);
    var summaryRect = rect(eventSummary);
    var verticalOverlap = editRect.top < summaryRect.bottom && editRect.bottom > summaryRect.top;
    editEventGap = verticalOverlap ? editRect.left - summaryRect.right : editRect.top - summaryRect.bottom;
    editEventAdjacent = editEvent.previousElementSibling === eventSummary && editEventGap >= -1 && editEventGap <= 8;
  }
  return {
    ready:true,
    viewportWidth:window.innerWidth,
    rootWidth:Number(rect(root).width.toFixed(1)),
    view:root.dataset.hdoCalendarView || '',
    title:(root.querySelector('[data-hdo-calendar-title]') || {}).textContent || '',
    metricColumns:bands(cards, 'left'),
    metricRows:bands(cards, 'top'),
    metricNoOverlap:Array.from(root.querySelectorAll('.hdo-metric-row')).every(function (row) {
      var label = row.querySelector('dt');
      var value = row.querySelector('dd');
      return label && value && rect(label).right <= rect(value).left + 1;
    }),
    cardsContained:cards.every(function (card) {
      return inside(rect(card), rect(metrics), 1) && card.scrollWidth <= card.clientWidth + 1;
    }),
    metricValues:metricValues,
    wideSharedShell:calendarRect.right <= railRect.left + 1,
    stackedSharedShell:calendarRect.bottom <= railRect.top + 1,
    bottomAligned:Math.abs(calendarRect.bottom - railRect.bottom) <= 1,
    monthLabels:Array.from(root.querySelectorAll('.hdo-year-month-label')).map(function (node) {
      return node.textContent.trim();
    }),
    calendarCells:root.querySelectorAll('.hdo-calendar-day').length,
    cellHeights:cellHeights,
    yearGridInsideFrame:inside(rect(grid), frameRect, 1),
    selectedDate:selected.dataset.date || '',
    selectedVisible:inside(rect(selected), frameRect, 1),
    frameOverflow:frame.scrollWidth - frame.clientWidth,
    frameScrollLeft:frame.scrollLeft,
    yearHeatmapWidthRatio:Number((rect(heatmap).width / Math.max(1, frameRect.width)).toFixed(3)),
    eventDates:Array.from(root.querySelectorAll('.hdo-calendar-day')).filter(function (cell) {
      return !!cell.querySelector('.hdo-event-marker');
    }).map(function (cell) { return cell.dataset.date; }).sort(),
    dateStateText:dateState.textContent.trim(),
    selectedDateText:(root.querySelector('[data-hdo-context-date]') || {}).textContent || '',
    contextEventTitle:visible(link) ? link.textContent.trim() : '',
    contextEventMeta:visible(eventMeta) ? eventMeta.textContent.trim() : '',
    contextEventEmptyVisible:visible(eventEmpty),
    contextEventMarkerVisible:visible(contextMarker),
    editEventVisible:visible(editEvent),
    editEventAdjacent:editEventAdjacent,
    editEventGap:editEventGap === null ? null : Number(editEventGap.toFixed(1)),
    contextEventLines:linkLineHeight > 0 ? Number((linkTextHeight / linkLineHeight).toFixed(1)) : 0,
    primaryActionText:primaryAction.textContent || '',
    primaryActionHidden:primaryAction.hidden,
    primaryActionHeight:Number(rect(primaryAction).height.toFixed(1)),
    primaryActionSolid:primaryAction.classList.contains('hdo-calendar-card-action') && primaryAction.classList.contains('hdo-context-action--primary'),
    primaryActionOwnRow:rect(primaryAction).top >= rect(contextEvent).bottom - 1,
    footerIntegrated:footer.parentElement === calendar,
    footerSurfaceMapped:getComputedStyle(footer).backgroundColor === token('calendar-footer-bg') &&
      getComputedStyle(shell).backgroundColor === token('ui-surface-2') &&
      getComputedStyle(footer).borderTopColor === token('ui-border-subtle'),
    legendGroupCount:root.querySelectorAll('.hdo-calendar-legend .hdo-legend-group').length,
    legendText:(root.querySelector('.hdo-calendar-legend') || {}).textContent || '',
    verseText:(root.querySelector('.hdo-verse-body') || {}).textContent || '',
    verseOverflow:(root.querySelector('.hdo-verse-body') || {}).scrollHeight > (root.querySelector('.hdo-verse-body') || {}).clientHeight + 1,
    legendFont:getComputedStyle(root.querySelector('.hdo-calendar-legend')).fontSize,
    documentOverflow:document.documentElement.scrollWidth - document.documentElement.clientWidth
  };
})()
"""


def _load_stress_page(
    *,
    view: str,
    selected: str,
    events_enabled: bool,
    continuation: Any,
) -> None:
    try:
        _web.showNormal()
        _web.resize(560, 1100)
        _web.show()
        _web.stdHtml(
            _stress_html(view, selected, events_enabled),
            css=[DASHBOARD_CSS_URL],
            js=[DASHBOARD_JS_URL],
            context=_web,
        )
        QTimer.singleShot(500, continuation)
    except Exception as exc:
        _error("stress-load-{}".format(view), exc)


def _evaluate_stress(stage: str, callback: Any, attempt: int = 0) -> None:
    def inspected(value: object) -> None:
        try:
            state = value if isinstance(value, dict) else {"ready": False}
            if not state.get("ready"):
                if attempt < 10:
                    QTimer.singleShot(200, lambda: _evaluate_stress(stage, callback, attempt + 1))
                    return
                raise RuntimeError("stress dashboard did not settle: {}".format(state))
            callback(state)
        except Exception as exc:
            _error(stage, exc)

    try:
        _web.evalWithCallback(STRESS_INSPECTION_SCRIPT, inspected)
    except Exception as exc:
        _error(stage, exc)


def _require_stress_common(state: dict[str, Any]) -> None:
    expected_values = {
        "today.answers": "12,486",
        "today.new_cards_studied": "1,048",
        "today.pace": "125.4 sec/card",
        "queue.eta": "Tomorrow, 12:15 AM",
        "last_seven_days.cards_studied": "12,486",
        "last_seven_days.new_cards_studied": "1,048",
        "long_term.current_streak": "1,024 days",
        "long_term.longest_streak": "1,517 days",
        "long_term.lifetime_cards_studied": "1,082,640",
    }
    values = state.get("metricValues", {})
    _require(all(values.get(key) == value for key, value in expected_values.items()), "stress metrics differ: {}".format(values))
    _require(bool(state.get("metricNoOverlap")), "stress metric labels overlap values")
    _require(bool(state.get("cardsContained")), "stress metric cards overflow their grid")
    _require(int(state.get("documentOverflow", 1)) <= 0, "stress dashboard has page-level horizontal overflow")
    _require(bool(state.get("footerIntegrated")), "calendar footer is not integrated with the calendar panel")
    _require(bool(state.get("footerSurfaceMapped")), "calendar footer does not use the intended nested neutral tokens")
    _require(state.get("legendGroupCount") == 3, "calendar legend does not expose three explicit groups")
    legend_text = str(state.get("legendText", ""))
    _require(
        all(label in legend_text for label in ("Completion", "Less", "More", "Reviews due", "Event")),
        "calendar legend labels are incomplete",
    )
    _require(bool(state.get("primaryActionSolid")), "calendar card action does not use the primary action hierarchy")
    _require(bool(state.get("editEventAdjacent")), "event edit control is visually separated from the event information")
    _require(
        "continues through every season of patient study and service." in str(state.get("verseText", ""))
        and not bool(state.get("verseOverflow")),
        "long Bible verse was truncated",
    )


def _start_stress_year() -> None:
    REPORT["stress_checks"] = {
        "schema_version": 1,
        "specified_values": {
            "cards_studied": "12,486",
            "new_cards_studied": "1,048",
            "lifetime_cards_studied": "1,082,640",
            "current_streak": "1,024 days",
            "longest_streak": "1,517 days",
            "pace": "125.4 sec/card",
            "eta": "Tomorrow, 12:15 AM",
        },
        "year_widths": {},
    }
    _load_stress_page(
        view="year",
        selected="2026-12-29",
        events_enabled=True,
        continuation=_begin_stress_widths,
    )


def _begin_stress_widths() -> None:
    global _stress_width_index
    _stress_width_index = 0
    _capture_next_stress_width()


def _capture_next_stress_width() -> None:
    global _stress_width_index
    if _stress_width_index >= len(STRESS_WIDTHS):
        QTimer.singleShot(150, _start_stress_month)
        return
    requested = STRESS_WIDTHS[_stress_width_index]
    _stress_width_index += 1
    _web.resize(max(560, requested + 120), 1100)
    _web.show()
    width_script = """
    (function () {
      var root = document.getElementById('hdo-dashboard');
      if (!root) return false;
      root.style.width = '%dpx';
      root.style.maxWidth = '%dpx';
      return true;
    })()
    """ % (requested, requested)
    _web.evalWithCallback(
        width_script,
        lambda _value: QTimer.singleShot(
            260,
            lambda: _evaluate_stress(
                "stress-year-{}".format(requested),
                lambda state: _record_stress_year_width(requested, state),
            ),
        ),
    )


def _record_stress_year_width(requested: int, state: dict[str, Any]) -> None:
    _require_stress_common(state)
    _require(state.get("view") == "year", "stress Year rendered the wrong view")
    _require(state.get("calendarCells") == 365, "stress Year omitted civil dates")
    _require(state.get("monthLabels") == ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], "stress Year omitted month labels")
    _require(state.get("eventDates") == ["2026-01-05", "2026-12-29"], "January/December Year events are incomplete")
    _require(state.get("selectedDate") == "2026-12-29" and bool(state.get("selectedVisible")), "selected December state is not visible")
    _require(state.get("primaryActionText") == "View due cards" and not bool(state.get("primaryActionHidden")), "future-date CTA is incorrect")
    _require("Comprehensive Pediatric NBME" in str(state.get("contextEventTitle", "")), "long event text is missing")
    _require(state.get("contextEventMeta") == "Tue, Dec 29 · in 129 days", "next-event metadata is not explicit")
    _require(bool(state.get("contextEventMarkerVisible")) and bool(state.get("editEventVisible")), "next-event marker or adjacent edit control is missing")
    _require(state.get("dateStateText") == "Selected" and state.get("selectedDateText") == "Tue, Dec 29, 2026", "selected-date chip or date is incorrect")
    _require(abs(float(state.get("rootWidth", 0)) - requested) <= 1.5, "unexpected stress container width")
    if requested == 319:
        _require(state.get("metricColumns") == 1 and state.get("metricRows") == 4, "319px container did not use one metric column")
        _require(bool(state.get("stackedSharedShell")), "319px container did not stack")
        _require(int(state.get("frameOverflow", 0)) > 0 and int(state.get("frameScrollLeft", 0)) > 0, "narrow Year did not use its selected-cell scroller")
    elif requested == 439:
        _require(state.get("metricColumns") == 1 and bool(state.get("stackedSharedShell")), "439px container did not use the narrow matrix state")
    elif requested in (440, 939):
        _require(state.get("metricColumns") == 2 and state.get("metricRows") == 2, "intermediate container did not use 2x2 metrics")
        _require(bool(state.get("stackedSharedShell")), "intermediate container did not stack the rail")
    else:
        _require(state.get("metricColumns") == 2 and state.get("metricRows") == 2, "wide container did not use 2x2 metrics")
        _require(bool(state.get("wideSharedShell")) and bool(state.get("bottomAligned")), "wide shared shell did not align")
    if requested >= 439:
        _require(bool(state.get("yearGridInsideFrame")) and int(state.get("frameOverflow", 1)) <= 0, "supported Year width clipped the heatmap")
    if 439 <= requested <= 939:
        _require(0.89 <= float(state.get("yearHeatmapWidthRatio", 0)) <= 0.95, "Year heatmap does not occupy roughly 90-94 percent of its body")
    REPORT["stress_checks"]["year_widths"][str(requested)] = state
    _write_report()
    QTimer.singleShot(80, _capture_next_stress_width)


def _start_stress_month() -> None:
    _load_stress_page(
        view="month",
        selected="2026-12-29",
        events_enabled=True,
        continuation=lambda: _evaluate_stress("stress-month", _record_stress_month),
    )


def _record_stress_month(state: dict[str, Any]) -> None:
    _require_stress_common(state)
    _require(state.get("view") == "month" and state.get("title") == "December 2026", "stress Month rendered the wrong period")
    _require(state.get("selectedDate") == "2026-12-29", "stress Month lost its selected date")
    _require(state.get("cellHeights") == [34.0], "compact Month cells are not 34px")
    _require(state.get("metricColumns") == 2 and state.get("metricRows") == 2, "compact Month did not retain 2x2 metrics")
    _require(float(state.get("contextEventLines", 99)) <= 2.1, "long compact event exceeded two text lines")
    _require(float(state.get("primaryActionHeight", 0)) in (30.0, 31.0, 32.0), "compact CTA height is outside 30-32px")
    _require(bool(state.get("primaryActionOwnRow")), "compact CTA is not on its own row")
    _require(state.get("legendFont") == "10px", "compact legend text is below the release size")
    REPORT["stress_checks"]["month_compact"] = state
    _write_report()
    QTimer.singleShot(120, _start_no_event_stress)


def _start_no_event_stress() -> None:
    _load_stress_page(
        view="year",
        selected=REFERENCE_DATE,
        events_enabled=False,
        continuation=lambda: _evaluate_stress("stress-no-events", _record_no_event_stress),
    )


def _record_no_event_stress(state: dict[str, Any]) -> None:
    _require_stress_common(state)
    _require(state.get("eventDates") == [], "no-event fixture rendered event markers")
    _require(bool(state.get("contextEventEmptyVisible")), "no-event fixture omitted its empty message")
    _require(not bool(state.get("contextEventMarkerVisible")), "no-event fixture rendered an event marker")
    _require(not bool(state.get("editEventVisible")), "no-event fixture rendered an empty edit control")
    REPORT["stress_checks"]["no_next_event"] = state
    REPORT["stress_checks"]["status"] = "passed"
    _write_report()
    QTimer.singleShot(180, _start_interaction_matrix)


def _start_interaction_matrix() -> None:
    global _interaction_index
    _interaction_index = 0
    REPORT["interaction_fixture"] = {
        "schema_version": 1,
        "status": "running",
        "case_count": len(_interaction_cases),
        "cases": {},
    }
    _write_report()
    _capture_next_interaction_case()


def _capture_next_interaction_case() -> None:
    global _interaction_index
    if _interaction_index >= len(_interaction_cases):
        REPORT["interaction_fixture"]["status"] = "passed"
        _write_report()
        QTimer.singleShot(180, _capture_full_screen_month)
        return
    case = _interaction_cases[_interaction_index]
    _interaction_index += 1
    try:
        _web.setWindowTitle(
            "{} · {} · 100%".format(EXPECTED_PROFILE, case["name"])
        )
        _web.showNormal()
        _web.resize(int(case["width"]), int(case["height"]))
        _web.show()
        _web.stdHtml(
            _interaction_html(str(case["theme"]), str(case["mode"])),
            css=[DASHBOARD_CSS_URL],
            js=[DASHBOARD_JS_URL],
            context=_web,
        )
        QTimer.singleShot(360, lambda: _inspect_interaction(case, 0))
    except Exception as exc:
        _error(str(case.get("name", "interaction-render")), exc)


def _inspect_interaction(case: dict[str, Any], attempt: int) -> None:
    script = """
(function () {
  var root = document.getElementById('hdo-dashboard');
  if (!root || root.dataset.hdoStateFixture !== 'true') return {ready:false};
  function colorFor(value) {
    var probe = document.createElement('span');
    probe.style.backgroundColor = value;
    root.appendChild(probe);
    var color = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return color;
  }
  function token(name) { return colorFor('var(--' + name + ')'); }
  function background(node) { return getComputedStyle(node).backgroundColor; }
  function panelCells(title, selector) {
    var panel = Array.from(root.querySelectorAll('.hdo-state-panel')).find(function (candidate) {
      var heading = candidate.querySelector('h2');
      return heading && heading.textContent.indexOf(title) >= 0;
    });
    return panel ? Array.from(panel.querySelectorAll(selector)) : [];
  }
  function shadowContains(node, color) {
    return !!node && getComputedStyle(node).boxShadow.indexOf(color) >= 0;
  }
  function segmentWidths(sample) {
    var track = sample ? sample.querySelector('.hdo-progress-track') : null;
    var width = track ? track.getBoundingClientRect().width : 0;
    return {
      track:track,
      width:width,
      segments:track ? Array.from(track.children) : [],
      ratios:track && width > 0 ? Array.from(track.children).map(function (node) {
        return Number((node.getBoundingClientRect().width / width).toFixed(3));
      }) : []
    };
  }
  var completion = panelCells('Completion levels', '[data-heat-kind="completion"]');
  var due = panelCells('Reviews due levels', '[data-heat-kind="due"]');
  var duePseudo = due.map(function (node) { return getComputedStyle(node, '::after'); });
  var primary = Array.from(root.querySelectorAll('.hdo-context-action--primary'));
  var segmentButtons = Array.from(root.querySelectorAll('.hdo-view-switch button'));
  var icons = Array.from(root.querySelectorAll('.hdo-fixture-icon'));
  var emptyProgress = segmentWidths(root.querySelector('[data-fixture-progress="empty"]'));
  var partialProgress = segmentWidths(root.querySelector('[data-fixture-progress="partial"]'));
  var fullProgress = segmentWidths(root.querySelector('[data-fixture-progress="full"]'));
  var selected = Array.from(root.querySelectorAll('[data-fixture-state="selected"]'));
  var today = Array.from(root.querySelectorAll('[data-fixture-state="today"]'));
  var both = root.querySelector('.hdo-calendar-day.is-today.is-selected');
  var eventMarkers = Array.from(root.querySelectorAll('.hdo-event-marker'));
  var eventDue = root.querySelector('[data-fixture-state="event-due"]');
  var outsideDue = root.querySelector('[data-fixture-state="outside-due"]');
  var emptyPast = root.querySelector('[data-fixture-state="empty-past"]');
  var emptyFuture = root.querySelector('[data-fixture-state="empty-future"]');
  var outside = root.querySelector('[data-fixture-state="outside"]');
  var semanticScenarios = Array.from(root.querySelectorAll('[data-fixture-metric]'));
  var surfaceValues = [token('ui-canvas'), token('ui-surface-1'), token('ui-surface-2'), token('ui-surface-3')];
  var completeMatch = completion.length === 6 && completion.every(function (node, level) {
    return background(node) === token('heat-complete-' + level);
  });
  var dueBackgroundsMatch = due.length === 5 && due.every(function (node, index) {
    return background(node) === token('heat-due-bg-' + (index + 1));
  });
  var dueIndicatorsMatch = duePseudo.length === 5 && duePseudo.every(function (style, index) {
    return style.content !== 'none' && style.backgroundColor === token('heat-due-mark-' + (index + 1));
  });
  var canvas = token('ui-canvas');
  var scheme = '%s';
  return {
    ready:true,
    theme:'%s',
    mode:'%s',
    textScale100:(root.getAttribute('style') || '').indexOf('--hdo-scale:1.0') >= 0,
    hostCanvasThemed:background(document.documentElement) === canvas && background(document.body) === canvas && background(root) === canvas,
    htmlColorScheme:getComputedStyle(document.documentElement).colorScheme,
    rootColorScheme:getComputedStyle(root).colorScheme,
    colorSchemeApplied:getComputedStyle(document.documentElement).colorScheme.indexOf(scheme) >= 0 && getComputedStyle(root).colorScheme.indexOf(scheme) >= 0,
    completionLevels:completion.length,
    dueLevels:due.length,
    completeTokensMatch:completeMatch,
    dueBackgroundsMatch:dueBackgroundsMatch,
    completionUnique:(new Set(completion.map(background))).size,
    dueUnique:(new Set(due.map(background))).size,
    dueIndicatorCount:duePseudo.length,
    dueIndicatorHeights:duePseudo.map(function (style) { return style.height; }),
    dueIndicatorsMatch:dueIndicatorsMatch,
    primaryStateCount:primary.length,
    primaryStatesMatch:primary.length === 4 &&
      background(primary[0]) === token('ui-accent') &&
      background(primary[1]) === token('ui-accent-hover') &&
      background(primary[2]) === token('ui-accent-pressed') &&
      background(primary[3]) === token('ui-disabled-surface'),
    segmentStateCount:segmentButtons.length,
    segmentStatesMatch:segmentButtons.length === 2 &&
      background(segmentButtons[0]) === token('ui-accent-soft') &&
      background(segmentButtons[1]) === token('ui-surface-2'),
    iconStateCount:icons.length,
    iconStatesMatch:icons.length === 2 &&
      background(icons[0]) === token('ui-surface-2') &&
      background(icons[1]) === token('ui-control-hover'),
    selectedStateCount:selected.length,
    todayStateCount:today.length,
    selectedVisible:selected.length === 6 && selected.every(function (node) { return shadowContains(node, token('calendar-selected-ring')); }),
    todayVisible:today.length === 6 && today.every(function (node) { return shadowContains(node, token('calendar-today-ring')); }),
    combinedVisible:!!both && shadowContains(both, token('calendar-selected-ring')) && shadowContains(both, token('calendar-today-ring')),
    combinedLayersIndependent:!!both && (getComputedStyle(both).boxShadow.match(/rgb/g) || []).length >= 4,
    eventMarkers:eventMarkers.length,
    eventLayered:eventMarkers.every(function (marker) {
      var style = getComputedStyle(marker);
      return style.borderTopColor === token('ui-text-primary') && style.boxShadow !== 'none';
    }),
    eventDueLayered:!!eventDue && background(eventDue) === token('heat-due-bg-4') && getComputedStyle(eventDue, '::after').backgroundColor === token('heat-due-mark-4'),
    emptyPastState:!!emptyPast && background(emptyPast) === token('heat-complete-0'),
    emptyFutureState:!!emptyFuture && background(emptyFuture) === token('calendar-future-bg'),
    outsideState:!!outside && background(outside) === token('calendar-outside-bg'),
    outsideDueState:!!outsideDue && background(outsideDue) === token('heat-due-bg-3') && getComputedStyle(outsideDue).color === token('calendar-outside-text'),
    semanticScenarioCount:semanticScenarios.length,
    emptyProgressNoSliver:emptyProgress.segments.length === 4 && emptyProgress.segments.every(function (segment) { return segment.getBoundingClientRect().width === 0; }),
    partialProgressMapped:partialProgress.segments.length === 4 &&
      Math.abs(partialProgress.ratios[0] - .60) <= .012 &&
      Math.abs(partialProgress.ratios[1] - .10) <= .012 &&
      Math.abs(partialProgress.ratios[2] - .12) <= .012 &&
      Math.abs(partialProgress.ratios[3] - .18) <= .012 &&
      background(partialProgress.segments[0]) === token('progress-complete') &&
      background(partialProgress.segments[1]) === token('status-new-fill') &&
      background(partialProgress.segments[2]) === token('status-learning-fill') &&
      background(partialProgress.segments[3]) === token('status-review-fill'),
    fullProgressComplete:fullProgress.segments.length === 4 && fullProgress.segments[0].getBoundingClientRect().width >= fullProgress.width - 1 && fullProgress.segments.slice(1).every(function (segment) { return segment.getBoundingClientRect().width === 0; }),
    surfaceHierarchyDistinct:(new Set(surfaceValues)).size === 4,
    currentColorIcons:Array.from(root.querySelectorAll('.hdo-fixture-icon svg')).every(function (svg) {
      return svg.querySelectorAll('[fill], [stroke]').length === 0;
    }),
    overflowX:document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    rootOverflowX:root.scrollWidth > root.clientWidth + 1
  };
})()
""" % (case["mode"], case["theme"], case["mode"])

    def inspected(value: object) -> None:
        try:
            state = value if isinstance(value, dict) else {"ready": False}
            passed = (
                bool(state.get("ready"))
                and bool(state.get("textScale100"))
                and bool(state.get("hostCanvasThemed"))
                and bool(state.get("colorSchemeApplied"))
                and state.get("completionLevels") == 6
                and state.get("dueLevels") == 5
                and bool(state.get("completeTokensMatch"))
                and bool(state.get("dueBackgroundsMatch"))
                and state.get("completionUnique") == 6
                and state.get("dueUnique") == 5
                and state.get("dueIndicatorCount") == 5
                and state.get("dueIndicatorHeights") == ["4px"] * 5
                and bool(state.get("dueIndicatorsMatch"))
                and state.get("primaryStateCount") == 4
                and bool(state.get("primaryStatesMatch"))
                and state.get("segmentStateCount") == 2
                and bool(state.get("segmentStatesMatch"))
                and state.get("iconStateCount") == 2
                and bool(state.get("iconStatesMatch"))
                and state.get("selectedStateCount") == 6
                and state.get("todayStateCount") == 6
                and bool(state.get("selectedVisible"))
                and bool(state.get("todayVisible"))
                and bool(state.get("combinedVisible"))
                and bool(state.get("combinedLayersIndependent"))
                and state.get("eventMarkers") == 3
                and bool(state.get("eventLayered"))
                and bool(state.get("eventDueLayered"))
                and bool(state.get("emptyPastState"))
                and bool(state.get("emptyFutureState"))
                and bool(state.get("outsideState"))
                and bool(state.get("outsideDueState"))
                and state.get("semanticScenarioCount") == 6
                and bool(state.get("emptyProgressNoSliver"))
                and bool(state.get("partialProgressMapped"))
                and bool(state.get("fullProgressComplete"))
                and bool(state.get("surfaceHierarchyDistinct"))
                and bool(state.get("currentColorIcons"))
                and not bool(state.get("overflowX"))
                and not bool(state.get("rootOverflowX"))
            )
            if not passed:
                if attempt < 10:
                    QTimer.singleShot(180, lambda: _inspect_interaction(case, attempt + 1))
                    return
                raise RuntimeError("interaction fixture did not pass: {}".format(state))
            REPORT["interaction_fixture"]["cases"][str(case["name"])] = state
            REPORT["states"][str(case["name"])] = state
            _capture(str(case["name"]), state, full_screen=False)
            _write_report()
            QTimer.singleShot(100, _capture_next_interaction_case)
        except Exception as exc:
            _error(str(case.get("name", "interaction-inspect")), exc)

    try:
        _web.evalWithCallback(script, inspected)
    except Exception as exc:
        _error(str(case.get("name", "interaction-inspect")), exc)


def _capture_full_screen_month() -> None:
    _render(
        {
            "name": "exact-package-full-screen-month-100",
            "theme": "Sapphire Glass",
            "mode": "dark",
            "view": "month",
            "full_screen": True,
        },
        lambda: QTimer.singleShot(300, _capture_full_screen_year),
    )


def _capture_full_screen_year() -> None:
    _render(
        {
            "name": "exact-package-full-screen-year-100",
            "theme": "Sapphire Glass",
            "mode": "dark",
            "view": "year",
            "full_screen": True,
        },
        lambda: _finish(True),
    )


def _build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for theme_prefix, theme in THEMES:
        for mode in ("light", "dark"):
            for view in ("month", "year"):
                for layout_prefix, layout, width, height in LAYOUTS:
                    cases.append(
                        {
                            "name": "VR-{}-{}-{}-{}-100".format(
                                theme_prefix,
                                "L" if mode == "light" else "D",
                                "M" if view == "month" else "Y",
                                layout_prefix,
                            ),
                            "theme": theme,
                            "mode": mode,
                            "view": view,
                            "layout": layout,
                            "width": width,
                            "height": height,
                            "text_scale_percent": 100,
                            "full_screen": False,
                        }
                    )
    return cases


def _build_interaction_cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "STATE-{}-{}-100".format(
                theme_prefix,
                "L" if mode == "light" else "D",
            ),
            "theme": theme,
            "mode": mode,
            "width": 1280,
            "height": 900,
            "text_scale_percent": 100,
            "full_screen": False,
        }
        for theme_prefix, theme in THEMES
        for mode in ("light", "dark")
    ]


def _begin() -> None:
    global _started, _web, _cases, _interaction_cases
    if not ENABLED or _started:
        return
    if getattr(mw, "col", None) is None:
        QTimer.singleShot(250, _begin)
        return
    _started = True
    try:
        actual_profile = str(getattr(mw.pm, "name", ""))
        collection_path = str(getattr(mw.col, "path", ""))
        profile = getattr(mw.pm, "profile", {}) or {}
        sync_auth_present = bool(
            profile.get("syncKey")
            or profile.get("sync_key")
            or profile.get("syncUser")
            or profile.get("sync_user")
        )
        _require(actual_profile == EXPECTED_PROFILE, "isolated profile name mismatch")
        _require(
            collection_path.startswith(str(RUN_ROOT) + os.sep),
            "collection path escaped the disposable run",
        )
        _require(not sync_auth_present, "sync credentials are present")
        candidate_manifest = RUN_ROOT / "addons21" / "home_dashboard_overhaul" / "manifest.json"
        probe_path = RUN_ROOT / "addons21" / "zz_hdo_contact_sheet_probe" / "__init__.py"
        _require(candidate_manifest.is_file(), "candidate manifest is missing from the disposable base")
        _require(probe_path.is_file(), "capture probe is missing from the disposable base")
        REPORT["identity"] = {
            "pid": os.getpid(),
            "run_root": str(RUN_ROOT),
            "expected_profile": EXPECTED_PROFILE,
            "profile": actual_profile,
            "profile_matches": True,
            "collection_path": collection_path,
            "collection_inside_run_root": True,
            "sync_auth_present": False,
            "candidate_manifest_inside_run_root": True,
            "probe_inside_run_root": True,
            "capture_window_title_policy": "starts with the unique disposable profile name",
        }
        _cases = _build_cases()
        _interaction_cases = _build_interaction_cases()
        _require(len(_cases) == 32, "100% matrix must contain exactly 32 cases")
        _require(len(_interaction_cases) == 8, "interaction matrix must contain exactly 8 cases")
        _require(
            all(case["name"].endswith("-100") for case in _cases),
            "a non-100% case escaped the native probe",
        )
        REPORT["matrix"] = {
            "case_count": len(_cases),
            "themes": [theme for _prefix, theme in THEMES],
            "modes": ["light", "dark"],
            "views": ["month", "year"],
            "layouts": {
                layout: [width, height]
                for _prefix, layout, width, height in LAYOUTS
            },
        }
        REPORT["interaction_matrix"] = {
            "case_count": len(_interaction_cases),
            "themes": [theme for _prefix, theme in THEMES],
            "modes": ["light", "dark"],
            "logical_dimensions": [1280, 900],
        }
        REPORT["screens"] = [
            {
                "name": screen.name(),
                "geometry": [
                    screen.geometry().x(),
                    screen.geometry().y(),
                    screen.geometry().width(),
                    screen.geometry().height(),
                ],
                "available_geometry": [
                    screen.availableGeometry().x(),
                    screen.availableGeometry().y(),
                    screen.availableGeometry().width(),
                    screen.availableGeometry().height(),
                ],
                "device_pixel_ratio": screen.devicePixelRatio(),
            }
            for screen in QApplication.screens()
        ]
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        _write_report()
        _web = AnkiWebView(None, title="Home Dashboard 100% contact-sheet capture")
        # The compact evidence surface is intentionally taller than a normal
        # dashboard window so the complete Month card fits without a cropped
        # screenshot.  A macOS title bar would push the 1050 px content area
        # past the 1073 px available desktop and Qt would silently clamp the
        # webview.  The evidence image contains only web content, so keep this
        # dedicated probe window frameless and preserve the requested logical
        # dimensions exactly.
        _web.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        _web.setAccessibleName("Home Dashboard 100% contact-sheet capture")
        _start_warm_up()
    except Exception as exc:
        _error("begin", exc)


def _profile_opened(*_args: object) -> None:
    QTimer.singleShot(700, _begin)


if ENABLED:
    gui_hooks.profile_did_open.append(_profile_opened)
    QTimer.singleShot(1200, _begin)
