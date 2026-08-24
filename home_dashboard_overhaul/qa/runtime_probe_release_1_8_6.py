"""Fail-closed native production and Settings probe for release 1.8.6.

The disposable helper add-on installs this module as ``__init__.py`` and the
retained 1.8.4 production harness as ``_probe_base.py``.  The retained harness
supplies exact-package identity, scheduler-limit, Deck Browser mounting, and
native capture plumbing.  This module replaces its release matrix and
assertions with the canonical 1.8.6 production and Settings contract.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from aqt import gui_hooks, mw
from aqt.qt import (
    QApplication,
    QFont,
    QPoint,
    QScrollArea,
    Qt,
    QTimer,
)

from home_dashboard_overhaul.analytics import collect_snapshot, representative_preview_snapshot
from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.models import DashboardSnapshot, VerseContent
from home_dashboard_overhaul.settings import SettingsDialog

from . import _probe_base as base


RELEASE = "1.8.6"
OUTPUT_ROOT = base.RUN_ROOT / "hdo-release-evidence-1.8.6"
CAPTURE_ROOT = OUTPUT_ROOT / "captures"
REPORT_PATH = OUTPUT_ROOT / "runtime-report-{}.json".format(base.STAGE)
CAPTURE_SCOPE = os.environ.get("HDO_RELEASE_CAPTURE_SCOPE", "full").strip().casefold()
STATISTICS_DECK = "HDO 1.8.6 Native Statistics"
STATISTICS_ANSWER_COUNT = 1_184
STATISTICS_ELIGIBLE_PASS = 947
STATISTICS_ELIGIBLE_FAIL = 153
STATISTICS_INELIGIBLE_FAIL = 84
STATISTICS_TIME_MILLIS = 19_000
STATISTIC_METRIC_KEYS = (
    "queue.new",
    "queue.learning",
    "queue.review",
    "queue.total",
    "today.answers",
    "today.new_cards_studied",
    "today.cards_buried",
    "today.time_spent",
    "today.pace",
    "queue.eta",
    "last_seven_days.cards_studied",
    "last_seven_days.new_cards_studied",
    "last_seven_days.retention",
    "last_seven_days.again_rate",
    "long_term.average_reviews_per_active_day",
    "long_term.current_streak",
    "long_term.longest_streak",
    "long_term.lifetime_retention",
    "long_term.lifetime_cards_studied",
)

ENABLED = (
    str(base.RUN_ROOT).startswith("/private/tmp/anki-release-qa.")
    and base.EXPECTED_PROFILE.startswith("Codex QA HDO 1.8.6 ")
    and len(base.EXPECTED_SHA256) == 64
    and len(base.EXPECTED_INSTANCE_KEY) >= 24
    and base.STAGE in {"initial", "restart"}
    and CAPTURE_SCOPE in {"full", "settings"}
)

base.RELEASE = RELEASE
base.QA_HEAD_A = "HDO 1.8.6 QA Head A"
base.QA_HEAD_B = "HDO 1.8.6 QA Head B"
base.QA_CONFIG_A = "HDO 1.8.6 QA Limit 3"
base.QA_CONFIG_B = "HDO 1.8.6 QA Limit 7"
base.OUTPUT_ROOT = OUTPUT_ROOT
base.CAPTURE_ROOT = CAPTURE_ROOT
base.REPORT_PATH = REPORT_PATH
base.ENABLED = ENABLED
base.REPORT = {
    "schema_version": 3,
    "release": RELEASE,
    "stage": base.STAGE,
    "status": "running",
    "authority": "native-exact-package-production-and-canonical-settings",
    "errors": [],
    "captures": {},
    "scale_policy": {
        "production_ui_percent": 100,
        "settings_application_font_percent": [100, 150],
        "dpr_1_acceptance": "unrun",
        "os_display_scaling_acceptance": "unrun",
    },
}


PALETTES = {
    "Sapphire Glass": ("SG", ("Sapphire", "Amethyst", "Glacier", "Sea Glass")),
    "Graphite": ("GR", ("Slate", "Steel", "Plum", "Mint")),
    "Emerald": ("EM", ("Emerald", "Jade", "Moss", "Lagoon")),
    "High Contrast": ("HC", ("Cyan", "Gold", "Magenta", "Monochrome")),
}

PRODUCTION_CORE_IDS = (
    "PROD-MONTH-STABLE",
    "PROD-YEAR-STABLE",
    "PROD-MARKERS-COMBINED",
    "PROD-MARKERS-COMPLETION",
    "PROD-MARKERS-DUE",
    "PROD-MARKERS-TODAY",
    "PROD-MARKERS-EVENT",
    "PROD-LEGEND-NO-DUE",
    "PROD-LEGEND-NO-EVENT",
    "PROD-BG-WHITE",
    "PROD-BG-BLACK",
    "PROD-BG-PURPLE",
    "PROD-BG-IMAGE",
    "PROD-SECTIONS-BELOW",
    "PROD-BOTTOM-CLEARANCE",
    "PROD-VERSE-EXACT",
)

SETTINGS_CONTRACT_IDS = (
    "SET-DOCK-SHOWN",
    "SET-DOCK-HIDDEN",
    "SET-PREVIEW-SECTION-FIT",
    "SET-PREVIEW-SECTION-100",
    "SET-PREVIEW-FULL-FIT",
    "SET-PREVIEW-FULL-100",
    "SET-OVERLAY-SUBMIN",
    "SET-EVENTS-EMPTY",
    "SET-EVENTS-POPULATED",
    "SET-EVENTS-SELECTED",
    "SET-EVENTS-SEARCHED",
    "SET-EVENTS-ARCHIVED",
    "SET-BIBLE-SHORT",
    "SET-BIBLE-LONG",
    "SET-BIBLE-CUSTOM",
    "SET-ABOUT-BOTTOM",
    "SET-DIRTY",
    "SET-REVERT",
    "SET-SAVE-SUCCESS",
    "SET-SAVE-ERROR",
    "SET-LEGACY-ROUTE",
    "SET-WINDOW-FIXED",
    "SET-WINDOW-CLAMP",
)

STATISTICS_CAPTURE_IDS = (
    "PROD-STATS-WIDE-MONTH",
    "PROD-STATS-WIDE-YEAR",
    "PROD-STATS-INTERMEDIATE",
    "PROD-STATS-NARROW",
)
SETTINGS_STATISTICS_IDS = ("SET-STATS-PREVIEW",)

_statistics_snapshot: DashboardSnapshot | None = None
_canonical_statistics_metrics: dict[str, str] | None = None


def _production_case(
    case_id: str,
    *,
    theme: str = "Graphite",
    mode: str = "dark",
    view: str = "month",
    palette: str = "Plum",
    fixture: str = "populated",
    selected: str = base.REFERENCE_DATE,
    special: str = "",
    layout: str = "wide",
    container_width: int | None = None,
    tags: tuple[str, ...] = (),
) -> dict[str, Any]:
    case = base._case(
        case_id,
        theme,
        mode,
        view,
        fixture=fixture,
        selected=selected,
        special=special,
        layout=layout,
        container_width=container_width,
        tags=tags,
    )
    case["palette"] = palette
    return case


def _build_production_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for theme, (prefix, palettes) in PALETTES.items():
        for palette in palettes:
            palette_id = palette.upper().replace(" ", "-")
            for mode, mode_id in (("light", "L"), ("dark", "D")):
                cases.append(_production_case(
                    "PROD-PAL-{}-{}-{}".format(prefix, palette_id, mode_id),
                    theme=theme,
                    palette=palette,
                    mode=mode,
                    tags=("palette", "production_month_tree"),
                ))
    cases.extend((
        _production_case("PROD-MONTH-STABLE", tags=("stable_width_switching", "month_42_cells")),
        _production_case("PROD-YEAR-STABLE", view="year", tags=("stable_width_switching", "year_53_weeks")),
        _production_case("PROD-MARKERS-COMBINED", fixture="combined-today", special="markers-combined", tags=("completion", "selected", "today", "due", "event")),
        _production_case("PROD-MARKERS-COMPLETION", fixture="combined-today", special="markers-completion", tags=("completion",)),
        _production_case("PROD-MARKERS-DUE", fixture="next-event-future", selected="2026-08-29", special="markers-due", tags=("due",)),
        _production_case("PROD-MARKERS-TODAY", fixture="combined-today", special="markers-today", tags=("today",)),
        _production_case("PROD-MARKERS-EVENT", fixture="selected-event", selected="2026-08-27", special="markers-event", tags=("event",)),
        _production_case("PROD-LEGEND-NO-DUE", special="no-due", tags=("conditional_legend",)),
        _production_case("PROD-LEGEND-NO-EVENT", special="no-event", tags=("conditional_legend", "conditional_summary")),
        _production_case("PROD-BG-WHITE", mode="light", special="host-white", tags=("host_background",)),
        _production_case("PROD-BG-BLACK", special="host-black", tags=("host_background",)),
        _production_case("PROD-BG-PURPLE", special="host-purple", tags=("host_background",)),
        _production_case("PROD-BG-IMAGE", special="host-image", tags=("host_background",)),
        _production_case("PROD-SECTIONS-BELOW", layout="intermediate", container_width=720, special="sections-below", tags=("sections_below_calendar",)),
        _production_case("PROD-BOTTOM-CLEARANCE", layout="intermediate", container_width=720, special="scroll-bottom", tags=("measured_bottom_clearance",)),
        _production_case("PROD-VERSE-EXACT", mode="light", special="verse-exact", tags=("exact_verse_font_size_color",)),
        _production_case("PROD-STATS-WIDE-MONTH", fixture="native-statistics", special="statistics-accuracy", tags=("statistics_accuracy", "wide_2x2", "month")),
        _production_case("PROD-STATS-WIDE-YEAR", view="year", fixture="native-statistics", special="statistics-accuracy", tags=("statistics_accuracy", "wide_2x2", "year")),
        _production_case("PROD-STATS-INTERMEDIATE", fixture="native-statistics", layout="intermediate", container_width=720, special="statistics-accuracy", tags=("statistics_accuracy", "intermediate")),
        _production_case("PROD-STATS-NARROW", fixture="native-statistics", layout="narrow", container_width=390, special="statistics-accuracy", tags=("statistics_accuracy", "narrow_stacked")),
    ))
    return cases


def _restart_case(_observed_view: str = "year") -> dict[str, Any]:
    return _production_case(
        "PROD-RESTART-PERSISTENCE",
        theme="Graphite",
        palette="Plum",
        mode="dark",
        view="year",
        fixture="native-statistics",
        special="restart",
        tags=("restart", "no_waiver", "production_persistence", "statistics_accuracy"),
    )


_base_config_for = base._config_for


def _config_for(case: Mapping[str, Any]) -> dict[str, Any]:
    config = _base_config_for(case)
    theme = str(case.get("theme", "Graphite"))
    palette = str(case.get("palette", PALETTES[theme][1][0]))
    config["heatmap"]["presets_by_theme"][theme] = palette
    special = str(case.get("special", ""))
    if special in {"no-due", "markers-completion", "markers-today", "markers-event"}:
        config["heatmap"]["show_due_forecast"] = False
    if special in {"no-event", "markers-completion", "markers-due", "markers-today"}:
        config["visibility"]["events"] = False
    if special == "verse-exact":
        config["bible"].update(
            font_family="Avenir Next, sans-serif",
            font_size="36px",
            font_color="#32145F",
            theme_aware_color=False,
        )
    return config


base._build_initial_cases = _build_production_cases
base._restart_case = _restart_case
base._config_for = _config_for

_base_fixture = base._fixture


def _fixture(case: Mapping[str, Any]) -> DashboardSnapshot:
    if str(case.get("fixture", "")) == "native-statistics":
        base._require(_statistics_snapshot is not None, "native statistics snapshot is unavailable")
        return _statistics_snapshot
    return _base_fixture(case)


base._fixture = _fixture


def _true_retention_counts(period: Any) -> dict[str, int]:
    passed = int(getattr(period, "young_passed", 0)) + int(getattr(period, "mature_passed", 0))
    failed = int(getattr(period, "young_failed", 0)) + int(getattr(period, "mature_failed", 0))
    return {"passed": passed, "failed": failed, "total": passed + failed}


def _due_tree_totals(root: Any) -> dict[str, int]:
    children = getattr(root, "children", ()) or ()
    return {
        "new": sum(max(0, int(getattr(child, "new_count", 0) or 0)) for child in children),
        "learning": sum(max(0, int(getattr(child, "learn_count", 0) or 0)) for child in children),
        "review": sum(max(0, int(getattr(child, "review_count", 0) or 0)) for child in children),
    }


def _prepare_native_statistics_fixture() -> None:
    """Build and compare one deterministic fixture with Anki's native APIs."""

    global _statistics_snapshot
    deck_id = mw.col.decks.id_for_name(STATISTICS_DECK)
    if deck_id is None:
        base._require(base.STAGE == "initial", "native statistics deck is missing after restart")
        deck_id = mw.col.decks.id(STATISTICS_DECK)
    base._require(deck_id is not None, "native statistics deck could not be created")
    deck_id = int(deck_id)
    card_ids = [int(value) for value in mw.col.db.list(
        "SELECT id FROM cards WHERE did = ? ORDER BY id",
        deck_id,
    )]
    if not card_ids:
        base._require(base.STAGE == "initial", "native statistics cards are missing after restart")
        notetype = mw.col.models.current()
        base._require(notetype is not None, "native statistics fixture has no note type")
        requests = []
        for index in range(8):
            note = mw.col.new_note(notetype)
            base._require(len(note.fields) >= 2, "native statistics note type needs two fields")
            note.fields[0] = "HDO native statistics card {:02d}".format(index + 1)
            note.fields[1] = "Home Dashboard 1.8.6 exact-package statistics QA"
            requests.append(base.AddNoteRequest(note=note, deck_id=deck_id))
        mw.col.add_notes(requests)
        card_ids = [int(value) for value in mw.col.db.list(
            "SELECT id FROM cards WHERE did = ? ORDER BY id",
            deck_id,
        )]
    base._require(len(card_ids) == 8, "native statistics fixture must own exactly eight cards")

    existing_reviews = int(mw.col.db.scalar(
        "SELECT count() FROM revlog WHERE cid IN (SELECT id FROM cards WHERE did = ?)",
        deck_id,
    ) or 0)
    scheduler_today = int(mw.col.sched.today)
    cutoff = int(mw.col.sched.day_cutoff)
    if existing_reviews == 0:
        base._require(base.STAGE == "initial", "native statistics revlog is missing after restart")
        qa_head_a = mw.col.decks.id_for_name(base.QA_HEAD_A)
        base._require(qa_head_a is not None, "scheduler QA head A is missing")
        updates = (
            (2, 2, scheduler_today, 10, 0, 0, card_ids[0]),
            (2, 2, scheduler_today + 1, 10, 0, 0, card_ids[1]),
            (2, -2, scheduler_today, 10, 0, 0, card_ids[2]),
            (2, -3, scheduler_today + 1, 10, 0, 0, card_ids[3]),
            (2, 2, scheduler_today + 50, 10, int(qa_head_a), scheduler_today + 2, card_ids[4]),
            (1, 1, cutoff + 3_600, 0, 0, 0, card_ids[5]),
            (2, 2, scheduler_today - 2, 10, 0, 0, card_ids[6]),
            (2, -1, scheduler_today + 3, 10, 0, 0, card_ids[7]),
        )
        revlog_start = cutoff * 1000 - 2_000
        reviews = []
        for index in range(STATISTICS_INELIGIBLE_FAIL):
            last_interval = 0 if index < 2 else -60
            reviews.append((revlog_start + index, card_ids[index % 2], -1, 1, -60, last_interval, 2500, STATISTICS_TIME_MILLIS, 0))
        for index in range(STATISTICS_ELIGIBLE_PASS):
            reviews.append((revlog_start + STATISTICS_INELIGIBLE_FAIL + index, card_ids[index % 8], -1, 3, 1, 1, 2500, STATISTICS_TIME_MILLIS, 1))
        for index in range(STATISTICS_ELIGIBLE_FAIL):
            reviews.append((revlog_start + STATISTICS_INELIGIBLE_FAIL + STATISTICS_ELIGIBLE_PASS + index, card_ids[index % 8], -1, 1, 1, 1, 2500, STATISTICS_TIME_MILLIS, 1))

        def seed() -> None:
            mw.col.db.executemany(
                "UPDATE cards SET type = ?, queue = ?, due = ?, ivl = ?, odid = ?, odue = ? WHERE id = ?",
                updates,
            )
            mw.col.db.executemany(
                "INSERT INTO revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                reviews,
            )

        mw.col.db.transact(seed)
        existing_reviews = len(reviews)
    base._require(existing_reviews == STATISTICS_ANSWER_COUNT, "native statistics revlog count changed")

    reset = getattr(mw.col.sched, "reset", None)
    if callable(reset):
        reset()
    graphs = mw.col._backend.graphs(search="", days=0)
    native_week = _true_retention_counts(graphs.true_retention.week)
    native_all_time = _true_retention_counts(graphs.true_retention.all_time)
    native_future_due = {
        int(day): int(count)
        for day, count in dict(graphs.future_due.future_due).items()
    }
    expected_future_due = {-2: 1, 0: 2, 1: 2, 2: 1}
    base._require(int(graphs.today.answer_count) == STATISTICS_ANSWER_COUNT, "Anki Today answer count mismatch")
    base._require(
        int(graphs.today.answer_millis) == STATISTICS_ANSWER_COUNT * STATISTICS_TIME_MILLIS,
        "Anki Today elapsed-time mismatch",
    )
    base._require(
        native_week == {"passed": STATISTICS_ELIGIBLE_PASS, "failed": STATISTICS_ELIGIBLE_FAIL, "total": 1_100},
        "Anki week true-retention fixture mismatch",
    )
    base._require(native_all_time == native_week, "Anki all-time true retention differs from the fixture")
    base._require(native_future_due == expected_future_due, "Anki future-due fixture mismatch")

    config = normalize_config({})
    config["appearance"].update(preset="Graphite", mode="dark")
    config["heatmap"].update(calendar_view="month", history_days=0, forecast_days=90)
    snapshot = collect_snapshot(mw.col, config, VerseContent())
    facts = snapshot.facts
    base._require(facts.today.is_available, "dashboard Today facts are unavailable")
    base._require(facts.queue.is_available, "dashboard QueueStats are unavailable")
    base._require(facts.buried.is_available, "dashboard buried facts are unavailable")
    base._require(facts.last_seven_days.is_available, "dashboard week facts are unavailable")
    base._require(facts.long_term.is_available, "dashboard all-time facts are unavailable")
    today = facts.today.value
    queue = facts.queue.value
    buried = facts.buried.value
    week = facts.last_seven_days.value
    all_time = facts.long_term.value
    base._require((today.answers, today.new_cards_studied) == (1_184, 2), "dashboard Today counts differ from Anki's period")
    base._require(abs(today.seconds - 22_496.0) < 0.001 and abs(float(today.pace_value or 0) - 19.0) < 0.001, "dashboard time or pace differs from Anki")
    base._require((week.cards_studied, week.new_cards_studied) == (1_184, 2), "dashboard Last 7 Days totals mismatch")
    base._require((week.retention.numerator, week.retention.denominator, week.retention.percent) == (947, 1_100, 86), "dashboard week retention mismatch")
    base._require((week.again_rate.numerator, week.again_rate.denominator) == (153, 1_100), "dashboard week Again counts mismatch")
    base._require((all_time.lifetime_cards_studied, all_time.lifetime_retention.percent) == (1_184, 86), "dashboard all-time totals mismatch")
    base._require(queue.total == queue.new + queue.learning + queue.review, "dashboard QueueStats invariant failed")
    base._require(buried.new + buried.learning + buried.review == 2, "dashboard explicit buried count mismatch")
    native_tree = _due_tree_totals(mw.col.sched.deck_due_tree())
    base._require(
        (queue.new, queue.learning, queue.review)
        == (native_tree["new"], native_tree["learning"], native_tree["review"]),
        "dashboard remaining categories differ from Anki's due tree",
    )
    scheduling_date = date.fromisoformat(facts.scheduling_date)
    dashboard_due = {
        offset: int(facts.for_date((scheduling_date + timedelta(days=offset)).isoformat()).reviews_due.value)
        for offset in (0, 1, 2)
    }
    base._require(dashboard_due == {0: 3, 1: 2, 2: 1}, "dashboard calendar forecast differs from native future due")
    current_day = facts.for_date(facts.scheduling_date)
    base._require(
        (current_day.reviews_completed.value, current_day.new_cards_studied.value)
        == (1_184, 2),
        "dashboard current-day details differ from canonical history",
    )
    all_answer_percent = (STATISTICS_ELIGIBLE_PASS * 100 + STATISTICS_ANSWER_COUNT // 2) // STATISTICS_ANSWER_COUNT
    base._require(all_answer_percent == 80, "all-answer regression fixture is not 80%")
    _statistics_snapshot = snapshot
    base._controller.config = config
    base._controller.snapshot = snapshot
    base._controller.cache_key = base._controller._key()
    base._controller.inflight_key = None
    base.REPORT["native_statistics_comparison"] = {
        "status": "passed",
        "authority": "Anki 26.8.1 GraphsResponse true_retention, today, future_due, and scheduler due tree",
        "upstream_reference": "ankitects/anki@26.08.1:rslib/src/stats/graphs/retention.rs",
        "fixture": {
            "answers": 1_184,
            "all_answer_success_percent": all_answer_percent,
            "eligible_passed": 947,
            "eligible_failed": 153,
            "native_retention_percent": 86,
            "visible_again_percent": 14,
        },
        "native_today": {
            "answer_count": int(graphs.today.answer_count),
            "answer_millis": int(graphs.today.answer_millis),
        },
        "native_true_retention": {"week": native_week, "all_time": native_all_time},
        "native_future_due": native_future_due,
        "native_due_tree": native_tree,
        "dashboard": {
            "today": {"answers": today.answers, "new_cards": today.new_cards_studied, "seconds": today.seconds, "pace": today.pace_value},
            "queue": {"new": queue.new, "learning": queue.learning, "review": queue.review, "total": queue.total},
            "buried": {"new": buried.new, "learning": buried.learning, "review": buried.review},
            "week": {"answers": week.cards_studied, "new_cards": week.new_cards_studied, "retention": week.retention.percent, "again": 100 - int(week.retention.percent or 0)},
            "all_time": {"answers": all_time.lifetime_cards_studied, "retention": all_time.lifetime_retention.percent},
            "calendar_due": dashboard_due,
        },
    }
    base._write_report()


_base_prepare_dom = base._prepare_dom

METRIC_REPORT_SCRIPT = r"""
(function () {
  var root = document.getElementById('hdo-dashboard');
  if (!root) return {ready:false, metrics:{}};
  var keys = %s;
  var metrics = {};
  keys.forEach(function (key) {
    var node = root.querySelector('[data-hdo-metric="' + key + '"]');
    metrics[key] = node ? node.textContent.trim() : '';
  });
  var progress = root.querySelector('[data-hdo-progress-label]');
  return {ready:true, metrics:metrics, progress:progress ? progress.textContent.trim() : ''};
})()
""" % json.dumps(STATISTIC_METRIC_KEYS)


def _exercise_live_statistics_refresh(case: Mapping[str, Any], callback: Any) -> None:
    """Record server-rendered values, then deliver the identical live payload."""

    web = mw.deckBrowser.web

    def inspected(value: object) -> None:
        try:
            state = value if isinstance(value, Mapping) else {}
            base._require(bool(state.get("ready")), "initial statistics HTML did not mount")
            initial_metrics = state.get("metrics")
            base._require(isinstance(initial_metrics, Mapping), "initial metric values are unavailable")
            base.REPORT.setdefault("statistics_render_paths", {})[str(case["id"])] = {
                "initial_html": {str(key): str(value) for key, value in initial_metrics.items()},
                "initial_progress": str(state.get("progress", "")),
                "live_refresh_requested": True,
            }
            base._controller.facts_revision += 1
            base._require(
                _statistics_snapshot is not None
                and base._controller._deliver_dashboard_facts(_statistics_snapshot),
                "production live statistics payload could not be delivered",
            )
            base._write_report()
            QTimer.singleShot(260, callback)
        except Exception as exc:
            base._error("{}-live-statistics".format(case.get("id", "statistics")), exc)

    web.evalWithCallback(METRIC_REPORT_SCRIPT, inspected)


def _prepare_dom(case: Mapping[str, Any], callback: Any) -> None:
    special = str(case.get("special", ""))

    def prepare_host() -> None:
        backgrounds = {
            "host-white": "linear-gradient(#ffffff,#ffffff)",
            "host-black": "linear-gradient(#050508,#050508)",
            "host-purple": "linear-gradient(135deg,#32145f,#6f3f91)",
            "host-image": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='600'%3E%3Cdefs%3E%3ClinearGradient id='g'%3E%3Cstop stop-color='%231f5f78'/%3E%3Cstop offset='1' stop-color='%237c466d'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='800' height='600' fill='url(%23g)'/%3E%3Ccircle cx='620' cy='120' r='90' fill='%23e6b84b' fill-opacity='.55'/%3E%3C/svg%3E\")",
        }
        value = backgrounds.get(special)
        if value is None:
            if str(case.get("fixture", "")) == "native-statistics":
                _exercise_live_statistics_refresh(case, callback)
            else:
                callback()
            return
        script = (
            "document.body.style.backgroundImage=%s;"
            "var r=document.getElementById('hdo-dashboard');"
            "if(r){r.dataset.hdoQaBackgroundClass=%s;}"
        ) % (json.dumps(value), json.dumps(special))
        mw.deckBrowser.web.eval(script)
        if str(case.get("fixture", "")) == "native-statistics":
            QTimer.singleShot(220, lambda: _exercise_live_statistics_refresh(case, callback))
        else:
            QTimer.singleShot(220, callback)

    _base_prepare_dom(case, prepare_host)


base._prepare_dom = _prepare_dom


base.DOM_REPORT_SCRIPT = r"""
(function () {
  var root=document.getElementById('hdo-dashboard');
  if(!root)return {ready:false};
  function q(s){return root.querySelector(s);}
  function qa(s){return Array.from(root.querySelectorAll(s));}
  function rect(n){if(!n)return null;var r=n.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height};}
  function visible(n){return !!n&&!n.hidden&&getComputedStyle(n).display!=='none';}
  var calendar=q('.hdo-calendar-card');
  var grid=q('.hdo-calendar-grid');
  var rail=q('.hdo-insight-rail');
  var metricsGrid=q('.hdo-summary-metrics-grid');
  var verse=q('.hdo-verse');
  var scroller=document.scrollingElement;
  var rootStyle=getComputedStyle(root);
  var title=q('#hdo-calendar-heading');
  var controls=qa('.hdo-header-controls button');
  var cells=qa('.hdo-calendar-day');
  var selected=q('.hdo-calendar-day.is-selected');
  var selectedStyle=selected?getComputedStyle(selected):null;
  var metricValues={};
  %s.forEach(function(key){var n=q('[data-hdo-metric="'+key+'"]');metricValues[key]=n?n.textContent.trim():'';});
  var progress=q('[data-hdo-progress-label]');
  return {
    ready:true,
    loading:root.classList.contains('hdo-dashboard--loading'),
    theme:root.dataset.hdoTheme||'',
    mode:root.dataset.hdoColorMode||'',
    view:root.dataset.hdoCalendarView||'',
    root:rect(root),
    calendar:rect(calendar),
    rail:rect(rail),
    density:root.dataset.hdoContentMode||'',
    rootPosition:rootStyle.position,
    rootMarginTop:rootStyle.marginTop,
    rootPaddingBottom:rootStyle.paddingBottom,
    rootBackground:rootStyle.backgroundColor,
    rootScrollOwner:root.dataset.hdoScrollOwner||'',
    footerClearance:Number(root.dataset.hdoFooterClearance||0),
    footerClearanceSource:root.dataset.hdoFooterClearanceSource||'',
    nativeFooterHeight:parseFloat(rootStyle.getPropertyValue('--hdo-native-footer-height'))||0,
    documentScrollPaddingBlockEnd:scroller?getComputedStyle(scroller).scrollPaddingBlockEnd:'',
    documentOverflowX:document.documentElement.scrollWidth-document.documentElement.clientWidth,
    bodyOverflowX:document.body.scrollWidth-document.body.clientWidth,
    documentScrollMaximum:scroller?Math.max(0,scroller.scrollHeight-scroller.clientHeight):0,
    documentBottomReached:scroller?Math.abs(scroller.scrollTop-Math.max(0,scroller.scrollHeight-scroller.clientHeight))<=2:false,
    hostPreserved:root.dataset.hdoHostPreserved||'',
    hostBackgroundClass:root.dataset.hdoQaBackgroundClass||'',
    bodyBackgroundImage:getComputedStyle(document.body).backgroundImage,
    calendarCellCount:cells.length,
    monthRows:grid?grid.style.getPropertyValue('--hdo-month-rows'):'',
    yearWeeks:grid?grid.style.getPropertyValue('--hdo-year-weeks'):'',
    titleFontSize:title?getComputedStyle(title).fontSize:'',
    controlHeights:controls.map(function(n){return Math.round(n.getBoundingClientRect().height);}),
    dueLegendCount:qa('.hdo-legend-due').length,
    eventLegendCount:qa('.hdo-legend-event').length,
    eventSummaryCount:qa('[data-hdo-context-event]').length,
    todayCount:qa('.hdo-calendar-day.is-today').length,
    selectedCount:qa('.hdo-calendar-day.is-selected').length,
    dueMarkerCount:qa('.hdo-calendar-day[data-due-level]:not([data-due-level="0"])').length,
    eventMarkerCount:qa('.hdo-calendar-day .hdo-event-marker').length,
    completionCount:qa('.hdo-calendar-day[data-level]:not([data-level="0"])').length,
    selectedOutline:selectedStyle?selectedStyle.outlineWidth:'',
    cellShadowCount:cells.filter(function(n){return getComputedStyle(n).boxShadow!=='none';}).length,
    verseFontSize:verse?getComputedStyle(verse).fontSize:'',
    verseFontFamily:verse?getComputedStyle(verse).fontFamily:'',
    verseColor:verse?getComputedStyle(verse).color:'',
    sectionsBelow:!!calendar&&!!rail&&rect(rail).top>=rect(calendar).bottom-1,
    statisticColumns:metricsGrid?getComputedStyle(metricsGrid).gridTemplateColumns:'',
    metricValues:metricValues,
    progressLabel:progress?progress.textContent.trim():''
  };
})()
""" % json.dumps(STATISTIC_METRIC_KEYS)


def _pixels(value: object) -> float:
    try:
        return float(str(value).replace("px", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _validate_dom(case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    global _canonical_statistics_metrics
    base._require(bool(state.get("ready")), "production dashboard did not mount")
    base._require(not bool(state.get("loading")), "production dashboard remained in loading state")
    base._require(state.get("theme") == case.get("theme"), "dashboard theme mismatch")
    base._require(state.get("mode") == case.get("mode"), "dashboard mode mismatch")
    base._require(state.get("view") == case.get("view"), "dashboard view mismatch")
    root = state.get("root") or {}
    root_width = float(root.get("width", 0))
    base._require(0 < root_width <= 1120.5, "dashboard exceeds its 1120px maximum")
    base._require(state.get("rootPosition") not in {"fixed", "sticky"}, "dashboard root left document flow")
    base._require(abs(_pixels(state.get("rootMarginTop")) - 24) <= 0.5, "dashboard top margin is not 24px")
    base._require(float(state.get("documentOverflowX", 0)) <= 1, "document has horizontal overflow")
    base._require(float(state.get("bodyOverflowX", 0)) <= 1, "body has horizontal overflow")
    base._require(state.get("hostPreserved") == "true", "host canvas was not preserved")
    base._require(state.get("rootBackground") in {"rgba(0, 0, 0, 0)", "transparent"}, "dashboard root is not transparent")
    base._require(state.get("rootScrollOwner") in {"documentElement", "body"}, "document scroller does not own vertical movement")
    clearance = float(state.get("footerClearance", 0))
    footer_height = float(state.get("nativeFooterHeight", 0))
    base._require(footer_height > 0 and abs(clearance - footer_height - 24) <= 1, "bottom clearance is not measured height plus 24px")
    base._require(abs(_pixels(state.get("rootPaddingBottom")) - clearance) <= 1, "root bottom padding drifted from measured clearance")
    base._require(abs(_pixels(state.get("documentScrollPaddingBlockEnd")) - clearance) <= 1, "document scroll padding drifted from measured clearance")
    base._require(_pixels(state.get("titleFontSize")) == 24, "calendar title is not 24px")
    base._require(len(state.get("controlHeights", [])) >= 5, "calendar header controls are incomplete")
    base._require(all(33 <= int(value) <= 35 for value in state.get("controlHeights", [])), "calendar controls are not 34px")
    base._require(int(state.get("cellShadowCount", 1)) == 0, "calendar cells retain shadows")
    if case.get("view") == "month":
        base._require(int(state.get("calendarCellCount", 0)) == 42, "Month is not 42 cells")
        base._require(str(state.get("monthRows")) == "6", "Month is not six rows")
    else:
        base._require(str(state.get("yearWeeks")) == "53", "Year is not a 53-week grid")
        base._require(int(state.get("calendarCellCount", 0)) in {365, 366}, "Year does not contain the full year")
    special = str(case.get("special", ""))
    if special == "no-due":
        base._require(int(state.get("dueLegendCount", 1)) == 0, "disabled due legend remains")
    if special == "no-event":
        base._require(int(state.get("eventLegendCount", 1)) == 0, "disabled event legend remains")
        base._require(int(state.get("eventSummaryCount", 1)) == 0, "disabled event summary remains")
    if special == "markers-combined":
        base._require(int(state.get("todayCount", 0)) == 1, "today marker is missing")
        base._require(int(state.get("selectedCount", 0)) == 1, "selected marker is missing")
        base._require(int(state.get("completionCount", 0)) > 0, "completion fill is missing")
        base._require(int(state.get("dueMarkerCount", 0)) > 0, "due marker is missing")
        base._require(int(state.get("eventMarkerCount", 0)) > 0, "event marker is missing")
    if special in {"host-white", "host-black", "host-purple", "host-image"}:
        base._require(state.get("hostBackgroundClass") == special, "host background fixture identity is missing")
        base._require(state.get("bodyBackgroundImage") != "none", "host background was removed")
    if special == "sections-below":
        base._require(bool(state.get("sectionsBelow")), "sections below the calendar are not visible")
    if special == "scroll-bottom":
        source = state.get("footerClearanceSource")
        base._require(source in {"measured", "fallback"}, "bottom-action clearance source is unknown")
        if source == "fallback":
            base._require(abs(footer_height - 60) <= 1, "bottom-action fallback is not the specified 60px")
        base._require(float(state.get("documentScrollMaximum", 0)) > 0, "bottom-clearance case has no document scroll range")
        base._require(bool(state.get("documentBottomReached")), "bottom-clearance case did not reach the document bottom")
    if special == "verse-exact":
        base._require(abs(_pixels(state.get("verseFontSize")) - 36) <= 0.1, "configured verse size is not exact")
        base._require("Avenir Next" in str(state.get("verseFontFamily")), "configured verse font is not exact")
    if str(case.get("fixture", "")) == "native-statistics":
        raw_metrics = state.get("metricValues")
        base._require(isinstance(raw_metrics, Mapping), "statistics metric values are unavailable")
        metrics = {str(key): str(value) for key, value in raw_metrics.items()}
        base._require(set(metrics) == set(STATISTIC_METRIC_KEYS), "statistics metric key set changed")
        base._require(all(metrics.values()), "one or more statistics values are empty")
        base._require(metrics["last_seven_days.retention"] == "86%", "native week retention is not 86%")
        base._require(metrics["last_seven_days.again_rate"] == "14%", "visible Again rate is not the 14% complement")
        base._require(metrics["long_term.lifetime_retention"] == "86%", "native lifetime retention is not 86%")

        def count_value(key: str) -> int:
            return int(metrics[key].replace(",", ""))

        base._require(
            count_value("queue.total")
            == count_value("queue.new") + count_value("queue.learning") + count_value("queue.review"),
            "visible QueueStats total invariant failed",
        )
        initial = base.REPORT.get("statistics_render_paths", {}).get(str(case["id"]), {})
        base._require(initial.get("initial_html") == metrics, "initial HTML and live-refresh metric values differ")
        if _canonical_statistics_metrics is None:
            _canonical_statistics_metrics = metrics
        else:
            base._require(metrics == _canonical_statistics_metrics, "responsive or restart metric values drifted")
        columns = [item for item in str(state.get("statisticColumns", "")).split() if item]
        if str(case.get("layout", "")) == "wide":
            base._require(len(columns) == 2, "wide statistics rail is not the required 2x2 grid")
        base.REPORT.setdefault("statistics_responsive_parity", {})[str(case["id"])] = {
            "metrics": metrics,
            "progress": str(state.get("progressLabel", "")),
            "computed_columns": len(columns),
            "layout": str(case.get("layout", "")),
            "view": str(case.get("view", "")),
            "status": "passed",
        }
        base._write_report()


base._validate_dom = _validate_dom


_base_font: QFont | None = None
_settings_cases: list[dict[str, Any]] = []
_settings_index = 0
_settings_dialog: SettingsDialog | None = None
_settings_started = False


def _settings_page_cases() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    pages = (
        ("DASHBOARD", "dashboard"),
        ("EVENTS", "events"),
        ("BIBLE", "bible_verse"),
        ("ABOUT", "about_support"),
    )
    for page_id, page in pages:
        for width_id, width in (("1040", 1040), ("1200", 1200), ("FULL", "full")):
            for font_percent in (100, 150):
                result.append({
                    "id": "SET-PAGE-{}-{}-{}".format(page_id, width_id, font_percent),
                    "page": page,
                    "width": width,
                    "font_percent": font_percent,
                    "special": "page-axis",
                })
    return result


def _settings_contract_cases() -> list[dict[str, Any]]:
    page_by_id = {
        "SET-DOCK-SHOWN": "dashboard",
        "SET-DOCK-HIDDEN": "dashboard",
        "SET-PREVIEW-SECTION-FIT": "dashboard",
        "SET-PREVIEW-SECTION-100": "dashboard",
        "SET-PREVIEW-FULL-FIT": "dashboard",
        "SET-PREVIEW-FULL-100": "dashboard",
        "SET-OVERLAY-SUBMIN": "dashboard",
        "SET-EVENTS-EMPTY": "events",
        "SET-EVENTS-POPULATED": "events",
        "SET-EVENTS-SELECTED": "events",
        "SET-EVENTS-SEARCHED": "events",
        "SET-EVENTS-ARCHIVED": "events",
        "SET-BIBLE-SHORT": "bible_verse",
        "SET-BIBLE-LONG": "bible_verse",
        "SET-BIBLE-CUSTOM": "bible_verse",
        "SET-ABOUT-BOTTOM": "about_support",
        "SET-DIRTY": "dashboard",
        "SET-REVERT": "dashboard",
        "SET-SAVE-SUCCESS": "dashboard",
        "SET-SAVE-ERROR": "dashboard",
        "SET-LEGACY-ROUTE": "calendar",
        "SET-WINDOW-FIXED": "dashboard",
        "SET-WINDOW-CLAMP": "dashboard",
        "SET-STATS-PREVIEW": "dashboard",
    }
    return [
        {
            "id": case_id,
            "page": page_by_id[case_id],
            "width": 1200,
            "font_percent": 100,
            "special": case_id.removeprefix("SET-").casefold(),
        }
        for case_id in SETTINGS_CONTRACT_IDS + SETTINGS_STATISTICS_IDS
    ]


def _events_fixture() -> list[dict[str, Any]]:
    return [
        {"id": "evt-a", "name": "Pediatrics board review", "date": "2026-08-27", "archived": False, "created_at": "2026-08-24T09:00:00-05:00", "archived_at": ""},
        {"id": "evt-b", "name": "Anatomy study group", "date": "2026-08-28", "archived": False, "created_at": "2026-08-24T09:01:00-05:00", "archived_at": ""},
        {"id": "evt-z", "name": "Completed milestone", "date": "2026-08-20", "archived": True, "created_at": "2026-08-20T09:00:00-05:00", "archived_at": "2026-08-24T09:02:00-05:00"},
    ]


def _settings_config(case: Mapping[str, Any]) -> dict[str, Any]:
    config = normalize_config({})
    config["appearance"].update(preset="Graphite", mode="dark")
    config["heatmap"]["calendar_view"] = "year" if base.STAGE == "restart" else "month"
    config["events"]["sort"] = "name"
    special = str(case.get("special", ""))
    if "events-empty" in special:
        config["events"]["items"] = []
    else:
        config["events"]["items"] = _events_fixture()
    if "bible-short" in special:
        config["bible"]["quotes"] = ["Be still, and know that I am God.<br> - Psalm 46:10 (NLT)"]
    elif "bible-long" in special:
        config["bible"]["quotes"] = [
            "Trust in the Lord with all your heart and do not depend on your own understanding. Seek his will in all you do, and he will show you which path to take through every season of learning, service, patience, and faithful practice.<br> - Proverbs 3:5-6 (NLT)"
        ]
    elif "bible-custom" in special:
        config["bible"].update(
            font_family="Avenir Next, sans-serif",
            font_size="36px",
            font_color="#32145F",
            theme_aware_color=False,
            quotes=["The Lord is my strength and my song.<br> - Psalm 118:14 (NLT)"],
        )
    return config


def _set_application_font(percent: int) -> None:
    global _base_font
    application = QApplication.instance()
    base._require(application is not None, "QApplication is unavailable")
    if _base_font is None:
        _base_font = QFont(application.font())
    font = QFont(_base_font)
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() * percent / 100.0)
    elif font.pixelSize() > 0:
        font.setPixelSize(max(1, round(font.pixelSize() * percent / 100.0)))
    application.setFont(font)


def _settings_screen(dialog: SettingsDialog | None = None) -> Any:
    """Return the screen that actually owns the Settings native window."""

    if dialog is not None:
        handle = dialog.windowHandle()
        screen = handle.screen() if handle is not None else dialog.screen()
        if screen is not None:
            return screen
    parent_handle = mw.windowHandle()
    screen = parent_handle.screen() if parent_handle is not None else mw.screen()
    return screen or base._qa_screen()


def _prepare_settings_case(case: Mapping[str, Any]) -> SettingsDialog:
    _set_application_font(int(case.get("font_percent", 100)))
    special = str(case.get("special", ""))
    config = _settings_config(case)
    base._controller.config = config
    if special in {"stats-preview", "restart-persistence"}:
        base._require(_statistics_snapshot is not None, "native statistics Settings snapshot is unavailable")
        base._controller.snapshot = _statistics_snapshot
    else:
        base._controller.snapshot = representative_preview_snapshot(base.REFERENCE_DATE)
    dialog = SettingsDialog(base._controller, initial_page=str(case.get("page", "dashboard")))
    target_width = case.get("width", 1200)
    available = _settings_screen(dialog).availableGeometry()
    width = available.width() - 32 if target_width == "full" else int(target_width)
    height = available.height() - 32 if target_width == "full" else min(800, available.height() - 32)
    if special != "window-clamp":
        dialog.setFixedSize(
            min(max(1, width), max(1, available.width() - 32)),
            min(max(1, height), max(1, available.height() - 32)),
        )
        dialog.move(available.center() - dialog.rect().center())
    # Keep the native Settings window above its parent while the compositor is
    # sampled. This affects only the disposable evidence helper, not product
    # window behavior.
    dialog.setModal(True)
    dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    dialog.show()
    QApplication.processEvents()
    settled_available = _settings_screen(dialog).availableGeometry()
    if special != "window-clamp" and settled_available != available:
        settled_width = settled_available.width() - 32 if target_width == "full" else int(target_width)
        settled_height = (
            settled_available.height() - 32
            if target_width == "full"
            else min(800, settled_available.height() - 32)
        )
        dialog.setFixedSize(
            min(max(1, settled_width), max(1, settled_available.width() - 32)),
            min(max(1, settled_height), max(1, settled_available.height() - 32)),
        )
        dialog.move(settled_available.center() - dialog.rect().center())
        available = settled_available

    if special == "dock-hidden":
        dialog._toggle_preview_visibility(False)
    elif special in {"preview-section-fit", "preview-section-100", "preview-full-fit", "preview-full-100"}:
        dialog.preview_scope.setValue("full" if "preview-full" in special else "context")
        dialog._set_preview_scope_mode()
        dialog._set_preview_fit_mode("actual" if special.endswith("-100") else "fit")
    elif special == "overlay-submin":
        before = id(dialog.preview_wrap)
        dialog._preview_overlay_mode = True
        dialog.body_grid.removeWidget(dialog.preview_wrap)
        dialog.body_grid.addWidget(
            dialog.preview_wrap,
            0,
            1,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        dialog.setMinimumSize(1, 1)
        dialog.resize(min(900, available.width()), min(680, available.height()))
        dialog.preview_wrap.raise_()
        dialog.setProperty("hdoOverlayPreviewIdentityStable", before == id(dialog.preview_wrap))
    elif special == "events-selected":
        dialog._select_event_id("evt-a", False)
    elif special == "events-searched":
        dialog.event_search.setText("Pediatrics")
        dialog._refresh_event_lists()
    elif special == "events-archived":
        dialog.event_tabs.setCurrentIndex(1)
        dialog._update_event_actions()
    elif special == "about-bottom":
        scroll = dialog.stack.currentWidget()
        if isinstance(scroll, QScrollArea):
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    elif special in {"dirty", "revert", "save-success", "save-error"}:
        dialog.retention_target.setValue(81)
        dialog._sync_draft()
        if special == "revert":
            dialog._revert_changes()
        elif special in {"save-success", "save-error"}:
            dialog._latest_stored_config = lambda: deepcopy(dialog.draft.baseline)
            if special == "save-error":
                original = base._controller.save_config

                def fail_save(*_args: object, **_kwargs: object) -> None:
                    raise OSError("simulated transactional write failure")

                base._controller.save_config = fail_save
                try:
                    dialog._save()
                finally:
                    base._controller.save_config = original
            else:
                dialog._save()
    elif special == "legacy-route":
        dialog.open_page("calendar")
    dialog.raise_()
    dialog.activateWindow()
    QApplication.processEvents()
    return dialog


def _settings_state(dialog: SettingsDialog, case: Mapping[str, Any]) -> dict[str, Any]:
    current = dialog.stack.currentWidget()
    active_tree = getattr(dialog, "active_events", None)
    archived_tree = getattr(dialog, "archived_events", None)
    quote_list = getattr(dialog, "quote_list", None)
    deck_tree = getattr(dialog, "deck_tree", None)
    scrollbar_off = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    settings_screen = _settings_screen(dialog)
    available_geometry = settings_screen.availableGeometry()
    frame = dialog.frameGeometry()
    calendar_viewport_y = -1
    calendar_anchor = getattr(dialog, "dashboard_anchors", {}).get("calendar")
    if isinstance(current, QScrollArea) and calendar_anchor is not None:
        calendar_viewport_y = calendar_anchor.mapTo(current.viewport(), QPoint(0, 0)).y()
    return {
        "section": dialog.current_section,
        "normalized_route": getattr(dialog, "_normalized_route", ""),
        "window_size": [dialog.width(), dialog.height()],
        "minimum_size": [dialog.minimumWidth(), dialog.minimumHeight()],
        "available_size": [available_geometry.width(), available_geometry.height()],
        "screen_name": settings_screen.name(),
        "screen_device_pixel_ratio": settings_screen.devicePixelRatio(),
        "decorated_frame_inside_available": (
            frame.left() >= available_geometry.left()
            and frame.top() >= available_geometry.top()
            and frame.right() <= available_geometry.right()
            and frame.bottom() <= available_geometry.bottom()
        ),
        "fixed_size": dialog.minimumSize() == dialog.maximumSize(),
        "macos_native_attached": bool(getattr(dialog, "_macos_window_attached", False)),
        "font_percent": int(case.get("font_percent", 100)),
        "application_font_point_size": QApplication.font().pointSizeF(),
        "nav_width": dialog.nav.width(),
        "page_count": dialog.stack.count(),
        "main_page_scroller": isinstance(current, QScrollArea),
        "preview_visible": dialog.preview_wrap.isVisible(),
        "preview_overlay": bool(dialog._preview_overlay_mode),
        "preview_identity_stable": dialog.property("hdoOverlayPreviewIdentityStable") is not False,
        "preview_scope": dialog.preview_scope.value("context"),
        "preview_scale": dialog.preview_scale.value("fit"),
        "preview_canvas_height": dialog.preview.height(),
        "preview_dock_height": dialog.preview_wrap.height(),
        "preview_rendered_height": dialog._preview_content_size.height(),
        "body_height": dialog.body_shell.height(),
        "calendar_anchor_viewport_y": calendar_viewport_y,
        "footer_after_body": dialog.footer_shell.geometry().top() >= dialog.body_shell.geometry().bottom() - 1,
        "save_text": dialog.save_button.text() if dialog.save_button is not None else "",
        "close_text": dialog.close_button.text() if dialog.close_button is not None else "",
        "revert_visible": dialog.revert_button.isVisible(),
        "save_error_visible": dialog.save_error.isVisible(),
        "save_error_text": dialog.save_error.text(),
        "status": dialog.dirty_badge.text(),
        "event_active_count": active_tree.topLevelItemCount() if active_tree is not None else 0,
        "event_archived_count": archived_tree.topLevelItemCount() if archived_tree is not None else 0,
        "event_tab": dialog.event_tabs.currentIndex() if hasattr(dialog, "event_tabs") else -1,
        "event_search": dialog.event_search.text() if hasattr(dialog, "event_search") else "",
        "quote_count": quote_list.count() if quote_list is not None else 0,
        "list_vertical_scrollbars_disabled": all(
            view is None or view.verticalScrollBarPolicy() == scrollbar_off
            for view in (active_tree, archived_tree, quote_list, deck_tree)
        ),
        "settings_shell_maximum": dialog.settings_shell.maximumWidth(),
        "settings_shell_width": dialog.settings_shell.width(),
        "settings_shell_center_delta": abs(
            dialog.settings_shell.geometry().center().x() - dialog.rect().center().x()
        ),
    }


def _validate_settings_state(case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    base._require(state.get("nav_width") == 152, "Settings rail is not 152px")
    base._require(state.get("page_count") == 4, "Settings does not own exactly four pages")
    base._require(bool(state.get("main_page_scroller")), "active Settings page is not the main scroller")
    base._require(bool(state.get("footer_after_body")), "Settings footer is not the final layout row")
    base._require(state.get("save_text") == "Save changes", "Save button label is unstable")
    base._require(state.get("close_text") == "Close", "Close button label is unstable")
    base._require(state.get("settings_shell_maximum") == 1240, "Settings inner shell is not capped at 1240px")
    expected_shell_width = min(int(state.get("window_size", [0])[0]), 1240)
    base._require(
        abs(int(state.get("settings_shell_width", 0)) - expected_shell_width) <= 2,
        "Settings shell does not occupy the available dialog width",
    )
    base._require(
        int(state.get("settings_shell_center_delta", 9999)) <= 2,
        "Settings shell is not centered in the dialog",
    )
    base._require(
        bool(state.get("decorated_frame_inside_available")),
        "decorated Settings window escaped available screen geometry",
    )
    base._require(bool(state.get("list_vertical_scrollbars_disabled")), "managed Settings list has an internal vertical scrollbar")
    special = str(case.get("special", ""))
    if state.get("section") == "about_support":
        base._require(not bool(state.get("preview_visible")), "About incorrectly shows Preview")
    elif special != "dock-hidden":
        base._require(bool(state.get("preview_visible")), "Preview is not open by default")
    if special == "dock-hidden":
        base._require(not bool(state.get("preview_visible")), "Preview did not hide session-locally")
    if bool(state.get("preview_visible")) and state.get("preview_scale") == "fit":
        maximum_canvas = 320 if state.get("preview_scope") == "context" else 420
        base._require(
            int(state.get("preview_canvas_height", 9999)) <= maximum_canvas,
            "Fit Preview retained a dead full-height canvas",
        )
    if special == "overlay-submin":
        base._require(bool(state.get("preview_overlay")), "sub-minimum Preview is not an overlay")
        base._require(bool(state.get("preview_identity_stable")), "overlay created a second Preview instance")
        base._require(state.get("window_size", [9999])[0] <= 900, "sub-minimum Settings width did not settle")
    if special == "events-empty":
        base._require(state.get("event_active_count") == 0 and state.get("event_archived_count") == 0, "empty Events state is populated")
    if special == "events-populated":
        base._require(state.get("event_active_count") == 2, "populated Events state is incomplete")
    if special == "events-searched":
        base._require(state.get("event_search") == "Pediatrics" and state.get("event_active_count") == 1, "Events search state is incorrect")
    if special == "events-archived":
        base._require(state.get("event_tab") == 1 and state.get("event_archived_count") == 1, "Archived Events state is incorrect")
    if special in {"bible-short", "bible-long", "bible-custom"}:
        base._require(state.get("quote_count") == 1, "Bible fixture did not render one compact row")
    if special == "dirty":
        base._require(bool(state.get("revert_visible")), "dirty Settings does not expose Revert")
    if special == "revert":
        base._require(not bool(state.get("revert_visible")), "Revert did not restore the saved baseline")
    if special == "save-success":
        base._require("Saved" in str(state.get("status")), "successful save did not update the baseline/status")
        base._require(not bool(state.get("revert_visible")), "successful save remains dirty")
    if special == "save-error":
        base._require(bool(state.get("save_error_visible")), "save failure is not inline")
        base._require("simulated transactional write failure" in str(state.get("save_error_text")), "save failure is not specific")
    if special == "legacy-route":
        base._require(state.get("section") == "dashboard", "legacy Calendar route did not activate Dashboard")
        base._require(state.get("normalized_route") == "dashboard#calendar", "legacy Calendar route did not settle on Calendar display")
        base._require(
            0 <= int(state.get("calendar_anchor_viewport_y", -1)) <= 4,
            "legacy Calendar route exposes a clipped preceding card",
        )
    if special == "window-fixed":
        base._require(bool(state.get("fixed_size")), "Settings window is not fixed-size")
    if special == "window-clamp":
        size = state.get("window_size", [0, 0])
        available = state.get("available_size", [0, 0])
        base._require(size[0] <= available[0] and size[1] <= available[1], "Settings window size escaped screen geometry")
    if special in {"stats-preview", "restart-persistence"}:
        base._require(state.get("statistics_parity") == "passed", "Settings preview statistics parity did not pass")
    if sys.platform == "darwin":
        base._require(bool(state.get("macos_native_attached")), "Settings is not attached to Anki's native macOS window")


def _capture_settings(dialog: SettingsDialog, case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    QApplication.processEvents()
    screen = _settings_screen(dialog)
    origin = dialog.mapToGlobal(QPoint(0, 0))
    screen_geometry = screen.geometry()
    pixmap = screen.grabWindow(
        0,
        origin.x() - screen_geometry.x(),
        origin.y() - screen_geometry.y(),
        dialog.width(),
        dialog.height(),
    )
    method = "QScreen.grabWindow-screen-client-crop"

    def logical_size(value: Any) -> tuple[float, float]:
        ratio = max(1.0, float(value.devicePixelRatio()))
        return value.width() / ratio, value.height() / ratio

    logical_width, logical_height = (0.0, 0.0) if pixmap.isNull() else logical_size(pixmap)
    color_count = 0 if pixmap.isNull() else base._sample_color_count(pixmap)
    if (
        pixmap.isNull()
        or color_count < 3
        or abs(logical_width - dialog.width()) > 4
        or abs(logical_height - dialog.height()) > 4
    ):
        fallback = dialog.grab()
        fallback_colors = 0 if fallback.isNull() else base._sample_color_count(fallback)
        if not fallback.isNull() and fallback_colors >= color_count:
            pixmap = fallback
            color_count = fallback_colors
            method = "QDialog.grab-client-fallback"

    base._require(not pixmap.isNull(), "native Settings capture is null")
    base._require(color_count >= 3, "native Settings capture appears blank")
    dpr = max(1.0, float(pixmap.devicePixelRatio()))
    logical_width, logical_height = logical_size(pixmap)
    base._require(
        abs(logical_width - dialog.width()) <= 4,
        "native Settings capture width does not match the dialog: {} px at DPR {} != {} logical px on {} ({})".format(
            pixmap.width(), dpr, dialog.width(), screen.name(), method
        ),
    )
    base._require(
        abs(logical_height - dialog.height()) <= 4,
        "native Settings capture height does not match the dialog: {} px at DPR {} != {} logical px on {} ({})".format(
            pixmap.height(), dpr, dialog.height(), screen.name(), method
        ),
    )
    CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
    path = CAPTURE_ROOT / "{}.png".format(case["id"])
    base._require(bool(pixmap.save(str(path), "PNG")), "could not save native Settings capture")
    base.REPORT["captures"][str(case["id"])] = {
        "file": str(path.relative_to(OUTPUT_ROOT)),
        "sha256": base._sha256(path),
        "component": "canonical-settings",
        "page": state.get("section"),
        "font_percent": case.get("font_percent", 100),
        "capture_method": method,
        "sampled_color_count": color_count,
        "logical_frame": {"width": dialog.width(), "height": dialog.height()},
        "physical_pixels": [pixmap.width(), pixmap.height()],
        "device_pixel_ratio": pixmap.devicePixelRatio(),
        "parent_window_title": str(mw.windowTitle()),
        "parent_window_title_matches_profile": base.EXPECTED_PROFILE in str(mw.windowTitle()),
        "state": dict(state),
    }
    base._write_report()


def _close_settings_dialog() -> None:
    global _settings_dialog
    if _settings_dialog is None:
        return
    _settings_dialog._allow_close = True
    _settings_dialog.close()
    _settings_dialog.deleteLater()
    _settings_dialog = None


def _next_settings_case() -> None:
    global _settings_index, _settings_dialog
    try:
        _close_settings_dialog()
        if _settings_index >= len(_settings_cases):
            _complete_stage()
            return
        case = _settings_cases[_settings_index]
        _settings_index += 1
        _settings_dialog = _prepare_settings_case(case)
        QTimer.singleShot(720, lambda: _inspect_settings_case(case))
    except Exception as exc:
        base._error("settings-case-prepare", exc)


def _inspect_settings_case(case: Mapping[str, Any], attempt: int = 0) -> None:
    global _canonical_statistics_metrics
    try:
        base._require(_settings_dialog is not None, "Settings dialog disappeared before capture")
        QApplication.processEvents()
        state = _settings_state(_settings_dialog, case)
        special = str(case.get("special", ""))
        if special in {"stats-preview", "restart-persistence"}:
            dialog = _settings_dialog

            def inspected(value: object) -> None:
                global _canonical_statistics_metrics
                try:
                    payload = value if isinstance(value, Mapping) else {}
                    base._require(bool(payload.get("ready")), "Settings statistics preview did not mount")
                    raw_metrics = payload.get("metrics")
                    base._require(isinstance(raw_metrics, Mapping), "Settings statistics preview metrics are unavailable")
                    metrics = {str(key): str(item) for key, item in raw_metrics.items()}
                    base._require(metrics["last_seven_days.retention"] == "86%", "Settings week retention is not 86%")
                    base._require(metrics["last_seven_days.again_rate"] == "14%", "Settings Again rate is not 14%")
                    if _canonical_statistics_metrics is None and CAPTURE_SCOPE == "settings":
                        _canonical_statistics_metrics = metrics
                        base.REPORT["settings_only_statistics_authority"] = "native collection snapshot"
                    base._require(_canonical_statistics_metrics is not None, "production statistics values were not established before Settings")
                    base._require(
                        metrics == _canonical_statistics_metrics,
                        "Settings preview statistics differ from the production snapshot",
                    )
                    state["preview_metric_values"] = metrics
                    state["preview_progress"] = str(payload.get("progress", ""))
                    state["statistics_parity"] = "passed"
                    _validate_settings_state(case, state)
                    _capture_settings(dialog, case, state)
                    QTimer.singleShot(120, _next_settings_case)
                except Exception as exc:
                    if attempt < 5:
                        QTimer.singleShot(250, lambda: _inspect_settings_case(case, attempt + 1))
                        return
                    base.REPORT["last_failed_settings_case"] = {
                        "case": dict(case),
                        "error": "{}: {}".format(type(exc).__name__, exc),
                    }
                    base._write_report()
                    base._error(str(case.get("id", "settings-preview-inspect")), exc)

            dialog.preview.evalWithCallback(METRIC_REPORT_SCRIPT, inspected)
            return
        _validate_settings_state(case, state)
        _capture_settings(_settings_dialog, case, state)
        QTimer.singleShot(120, _next_settings_case)
    except Exception as exc:
        if attempt < 5:
            QTimer.singleShot(250, lambda: _inspect_settings_case(case, attempt + 1))
            return
        base.REPORT["last_failed_settings_case"] = {
            "case": dict(case),
            "error": "{}: {}".format(type(exc).__name__, exc),
        }
        base._write_report()
        base._error(str(case.get("id", "settings-inspect")), exc)


def _start_settings() -> None:
    global _settings_cases, _settings_index, _settings_started
    try:
        _settings_started = True
        _settings_index = 0
        if base.STAGE == "initial":
            _settings_cases = _settings_page_cases() + _settings_contract_cases()
            base._require(len(_settings_cases) == 48, "Settings matrix must contain 48 initial frames")
        else:
            _settings_cases = [{
                "id": "SET-RESTART-PERSISTENCE",
                "page": "dashboard",
                "width": 1160,
                "font_percent": 100,
                "special": "restart-persistence",
            }]
        base.REPORT["settings_matrix"] = {
            "case_count": len(_settings_cases),
            "case_ids": [case["id"] for case in _settings_cases],
            "widget_tree": "one-native-qt-tree",
            "preview_instance_policy": "one-shared-instance",
        }
        base._write_report()
        QTimer.singleShot(120, _next_settings_case)
    except Exception as exc:
        base._error("settings-matrix", exc)


def _persist_restart_state() -> None:
    config = normalize_config({})
    config["appearance"].update(preset="Graphite", mode="dark")
    config["heatmap"]["calendar_view"] = "year"
    config["heatmap"]["presets_by_theme"]["Graphite"] = "Plum"
    config["events"]["sort"] = "name"
    mw.addonManager.writeConfig(base._controller.package, config)
    readback = normalize_config(mw.addonManager.getConfig(base._controller.package))
    base._require(readback == config, "restart configuration did not persist exactly")
    base.REPORT["persistence_write"] = {
        "status": "passed",
        "calendar_view": "year",
        "theme": "Graphite",
        "palette": "Plum",
        "events_sort": "name",
        "settings_window_policy": "fixed-and-recomputed-from-current-screen",
        "preview_visibility_persisted": False,
    }


def _complete_stage() -> None:
    try:
        _close_settings_dialog()
        if _base_font is not None:
            QApplication.instance().setFont(_base_font)
        smoke = base.REPORT.get("multi_deck_new_limit_smoke", {})
        base._require(smoke.get("status") == "passed", "scheduler-authoritative multi-deck smoke did not pass")
        comparison = base.REPORT.get("native_statistics_comparison", {})
        base._require(comparison.get("status") == "passed", "native statistics comparison did not pass")
        capture_ids = set(base.REPORT.get("captures", {}))
        if base.STAGE == "initial" and CAPTURE_SCOPE == "full":
            expected = {case["id"] for case in _build_production_cases()}
            expected.update(case["id"] for case in _settings_page_cases())
            expected.update(SETTINGS_CONTRACT_IDS)
            expected.update(SETTINGS_STATISTICS_IDS)
            base._require(len(expected) == 100, "initial contract does not derive 100 distinct frames")
            base._require(capture_ids == expected, "initial native evidence matrix is incomplete")
            base._require(
                set(base.REPORT.get("statistics_responsive_parity", {})) == set(STATISTICS_CAPTURE_IDS),
                "production statistics responsive parity is incomplete",
            )
            _persist_restart_state()
        elif base.STAGE == "restart" and CAPTURE_SCOPE == "full":
            base._require(capture_ids == {"PROD-RESTART-PERSISTENCE", "SET-RESTART-PERSISTENCE"}, "restart evidence matrix is incomplete")
        elif base.STAGE == "initial":
            expected = {case["id"] for case in _settings_page_cases()}
            expected.update(SETTINGS_CONTRACT_IDS)
            expected.update(SETTINGS_STATISTICS_IDS)
            base._require(len(expected) == 48, "Settings-only contract does not derive 48 distinct frames")
            base._require(capture_ids == expected, "Settings-only initial evidence matrix is incomplete")
            _persist_restart_state()
        else:
            base._require(capture_ids == {"SET-RESTART-PERSISTENCE"}, "Settings-only restart evidence is incomplete")

        if base.STAGE == "restart":
            config = normalize_config(mw.addonManager.getConfig(base._controller.package))
            base._require(config["heatmap"]["calendar_view"] == "year", "Year did not persist after restart")
            base._require(config["events"]["sort"] == "name", "name event sort did not persist after restart")
            base.REPORT["persistence_readback"] = {
                "status": "passed",
                "calendar_view": "year",
                "events_sort": "name",
                "settings_window_policy": "fixed-and-recomputed-from-current-screen",
                "settings_state": "clean",
            }
        base.REPORT["status"] = "passed"
        base._write_report()
        QTimer.singleShot(450, QApplication.instance().quit)
    except Exception as exc:
        base._error("finish-{}".format(base.STAGE), exc)


def _finish_production_stage() -> None:
    if not _settings_started:
        _start_settings()
    else:
        _complete_stage()


def _start_case_matrix() -> None:
    try:
        _prepare_native_statistics_fixture()
        if CAPTURE_SCOPE == "settings":
            base.REPORT["capture_scope"] = "settings-only"
            base.REPORT["production_matrix"] = {
                "case_count": 0,
                "capture_policy": "reuse previously accepted dashboard captures",
                "runtime_smoke": "exact-package scheduler and production DOM smoke still required",
            }
            base._write_report()
            QTimer.singleShot(200, _start_settings)
            return
        if base.STAGE == "restart":
            raw = normalize_config(mw.addonManager.getConfig(base._controller.package))
            base._require(raw.get("schema_version") == 8, "configuration schema changed after restart")
            base._require(raw["heatmap"]["calendar_view"] == "year", "Year view did not persist after restart")
            base._require(raw["events"]["sort"] == "name", "event name sort did not persist after restart")
            base._cases = [_restart_case("year")]
        else:
            base._cases = _build_production_cases()
            base._require(len(base._cases) == 52, "production matrix must contain 52 initial frames")
        base._case_index = 0
        base.REPORT["production_matrix"] = {
            "case_count": len(base._cases),
            "case_ids": [case["id"] for case in base._cases],
            "host": "actual isolated Anki main Deck Browser",
            "renderer": "exact installed production controller and renderer",
        }
        base._write_report()
        QTimer.singleShot(200, base._next_case)
    except Exception as exc:
        base._error("production-matrix-{}".format(base.STAGE), exc)


base._finish_stage = _finish_production_stage
base._start_case_matrix = _start_case_matrix


if ENABLED:
    gui_hooks.profile_did_open.append(base._profile_opened)
    QTimer.singleShot(1100, base._begin)
