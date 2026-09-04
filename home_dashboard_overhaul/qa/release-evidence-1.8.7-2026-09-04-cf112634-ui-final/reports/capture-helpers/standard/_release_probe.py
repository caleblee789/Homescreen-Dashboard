"""Fail-closed native production and Settings probe for release 1.8.7.

The disposable helper add-on installs this module as ``__init__.py`` and the
retained 1.8.4 production harness as ``_probe_base.py``.  The retained harness
supplies exact-package identity, scheduler-limit, Deck Browser mounting, and
native capture plumbing.  This module replaces its release matrix and
assertions with the canonical corrected 1.8.7 production and Settings contract.
"""

from __future__ import annotations

from copy import deepcopy
import ctypes
from datetime import date, timedelta
import json
import os
import platform
from pathlib import Path
import sys
from typing import Any, Callable, Mapping

from aqt import gui_hooks, mw
from aqt.qt import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QBuffer,
    QByteArray,
    QComboBox,
    QDate,
    QFont,
    QImageReader,
    QIODevice,
    QLabel,
    QLineEdit,
    QPainter,
    QPixmap,
    QPoint,
    QRect,
    QScrollArea,
    QSettings,
    QSize,
    QSlider,
    QSpinBox,
    Qt,
    QTimer,
    QWidget,
)

from home_dashboard_overhaul.analytics import collect_snapshot
from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.models import DashboardSnapshot, VerseContent
from home_dashboard_overhaul.settings import (
    EventEditDialog,
    SETTINGS_GEOMETRY_AVAILABLE_KEY,
    SETTINGS_GEOMETRY_DPR_KEY,
    SETTINGS_GEOMETRY_KEY,
    SETTINGS_GEOMETRY_SCREEN_KEY,
    SETTINGS_PREVIOUS_GEOMETRY_KEY,
    SETTINGS_PREVIOUS_GEOMETRY_SCREEN_KEY,
    SettingsDialog,
    TextEditDialog,
    _combo_value,
)
from home_dashboard_overhaul.settings_model import (
    clamp_window_geometry,
    migrate_saved_window_geometry,
    saved_window_geometry_is_valid,
    settings_screen_uses_compact_fallback,
)
from home_dashboard_overhaul.themes import contrast_ratio

from . import _capture_plan as capture_plan
from . import _probe_base as base


CAPTURE_PLAN = capture_plan.load_capture_plan()
PROFILE_REQUEST = capture_plan.load_profile_request(Path(__file__), plan=CAPTURE_PLAN)
CAPTURE_PROFILE = str(PROFILE_REQUEST.get("id", "full"))
LEGACY_CAPTURE_SCOPE = os.environ.get("HDO_RELEASE_CAPTURE_SCOPE", "full").strip().casefold()
if CAPTURE_PROFILE == "full" and LEGACY_CAPTURE_SCOPE == "settings":
    CAPTURE_PROFILE = "settings"
REQUESTED_CAPTURE_IDS = (
    tuple(str(value) for value in PROFILE_REQUEST["include_ids"])
    if PROFILE_REQUEST.get("include_ids") is not None
    else None
)
PROFILE_SPEC = CAPTURE_PLAN.profile(CAPTURE_PROFILE)
PROFILE_COUNTS = CAPTURE_PLAN.counts(
    CAPTURE_PROFILE,
    include_ids=REQUESTED_CAPTURE_IDS,
)

RELEASE = CAPTURE_PLAN.release
OUTPUT_ROOT = base.RUN_ROOT / str(PROFILE_SPEC["output_directory"])
CAPTURE_ROOT = OUTPUT_ROOT / "captures"
REPORT_PATH = OUTPUT_ROOT / "runtime-report-{}.json".format(base.STAGE)
STATISTICS_DECK = "HDO {} Native Statistics".format(RELEASE)
STATISTICS_ANSWER_COUNT = 1_184
STATISTICS_ELIGIBLE_PASS = 947
STATISTICS_ELIGIBLE_FAIL = 153
STATISTICS_INELIGIBLE_FAIL = 84
STATISTICS_TIME_MILLIS = 19_000
STATISTIC_METRIC_KEYS = (
    "progress.initial_cards_due",
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
    "last_seven_days.average_cards_per_day",
    "last_seven_days.new_cards_studied",
    "last_seven_days.retention",
    "last_seven_days.time_spent",
    "long_term.average_reviews_per_active_day",
    "long_term.current_streak",
    "long_term.longest_streak",
    "long_term.lifetime_retention",
    "long_term.lifetime_cards_studied",
)
STATISTIC_METRIC_ORDER = {
    "hdo-progress": (
        "progress.initial_cards_due",
        "queue.total",
        "queue.new",
        "queue.learning",
        "queue.review",
    ),
    "hdo-session": (
        "today.answers",
        "today.new_cards_studied",
        "today.cards_buried",
        "today.time_spent",
        "today.pace",
        "queue.eta",
    ),
    "hdo-last-seven": (
        "last_seven_days.cards_studied",
        "last_seven_days.average_cards_per_day",
        "last_seven_days.retention",
        "last_seven_days.new_cards_studied",
        "last_seven_days.time_spent",
    ),
    "hdo-all-time": (
        "long_term.lifetime_cards_studied",
        "long_term.average_reviews_per_active_day",
        "long_term.lifetime_retention",
        "long_term.current_streak",
        "long_term.longest_streak",
    ),
}
CLOCK_RELATIVE_METRIC_KEYS = frozenset({"queue.eta"})

ENABLED = (
    str(base.RUN_ROOT).startswith("/private/tmp/anki-release-qa.")
    and base.EXPECTED_PROFILE.startswith("Codex QA HDO {} ".format(RELEASE))
    and len(base.EXPECTED_SHA256) == 64
    and len(base.EXPECTED_INSTANCE_KEY) >= 24
    and base.STAGE in {"initial", "restart"}
    and CAPTURE_PROFILE in CAPTURE_PLAN.profile_ids
    and LEGACY_CAPTURE_SCOPE in {"full", "settings"}
    and PROFILE_COUNTS[base.STAGE] > 0
)

base.RELEASE = RELEASE
base.REFERENCE_DATE = CAPTURE_PLAN.reference_date
base.QA_HEAD_A = "HDO {} QA Head A".format(RELEASE)
base.QA_HEAD_B = "HDO {} QA Head B".format(RELEASE)
base.QA_CONFIG_A = "HDO {} QA Limit 3".format(RELEASE)
base.QA_CONFIG_B = "HDO {} QA Limit 7".format(RELEASE)
base.RESTART_PRE_FIXTURE_EXPECTED_NEW = None
base.RESTART_MULTI_DECK_EXPECTED_TOTAL = 12
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
    "capture_plan": {
        "schema_version": CAPTURE_PLAN.schema_version,
        "sha256": CAPTURE_PLAN.sha256,
        "profile": CAPTURE_PROFILE,
        "profile_counts": PROFILE_COUNTS,
        "selected_capture_ids": (
            list(REQUESTED_CAPTURE_IDS)
            if REQUESTED_CAPTURE_IDS is not None
            else list(CAPTURE_PLAN.ids(CAPTURE_PROFILE))
        ),
    },
    "capture_profile": {
        "id": CAPTURE_PROFILE,
        "description": str(PROFILE_SPEC.get("description", "")),
        "full_screen": bool(PROFILE_SPEC.get("full_screen")),
        "resolved_counts": PROFILE_COUNTS,
    },
    "errors": [],
    "captures": {},
    "scale_policy": {
        "production_ui_percent": 100,
        "settings_application_font_percent": [100],
        "structured_settings_application_font_percent": list(
            CAPTURE_PLAN.structured_settings_layout().get(
                "application_font_percents", []
            )
        ),
        "native_only": True,
        "environment_variable_scale_substitutes": False,
        "required_native_profiles": deepcopy(
            CAPTURE_PLAN.raw.get("native_platform_matrix", [])
        ),
    },
}


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
    for planned in CAPTURE_PLAN.cases(
        CAPTURE_PROFILE,
        stage="initial",
        component="production",
        include_ids=REQUESTED_CAPTURE_IDS,
    ):
        case = _production_case(
            str(planned["id"]),
            theme=str(planned.get("theme", "Graphite")),
            palette=str(planned.get("palette", "Plum")),
            mode=str(planned.get("mode", "dark")),
            view=str(planned.get("view", "month")),
            fixture=str(planned.get("fixture", "populated")),
            selected=str(planned.get("selected", base.REFERENCE_DATE)),
            special=str(planned.get("special", "")),
            layout=str(planned.get("layout", "wide")),
            container_width=planned.get("container_width"),
            tags=tuple(str(value) for value in planned.get("tags", ())),
        )
        case["week_start"] = int(planned.get("week_start", 0))
        case["capture_family"] = str(planned["family"])
        case["sheet_group"] = str(planned["sheet_group"])
        cases.append(case)
    return cases


def _restart_case(_observed_view: str = "year") -> dict[str, Any]:
    planned_cases = CAPTURE_PLAN.cases(
        CAPTURE_PROFILE,
        stage="restart",
        component="production",
        include_ids=REQUESTED_CAPTURE_IDS,
    )
    base._require(len(planned_cases) == 1, "production restart plan must contain one frame")
    planned = planned_cases[0]
    case = _production_case(
        str(planned["id"]),
        theme=str(planned.get("theme", "Graphite")),
        palette=str(planned.get("palette", "Plum")),
        mode=str(planned.get("mode", "dark")),
        view=str(planned.get("view", "year")),
        fixture=str(planned.get("fixture", "native-statistics")),
        selected=str(planned.get("selected", base.REFERENCE_DATE)),
        special=str(planned.get("special", "restart")),
        layout=str(planned.get("layout", "wide")),
        container_width=planned.get("container_width"),
        tags=tuple(str(value) for value in planned.get("tags", ())),
    )
    case["capture_family"] = str(planned["family"])
    case["sheet_group"] = str(planned["sheet_group"])
    return case


_base_config_for = base._config_for


def _config_for(case: Mapping[str, Any]) -> dict[str, Any]:
    config = _base_config_for(case)
    theme = str(case.get("theme", "Graphite"))
    palette = str(case.get("palette", "Plum"))
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
            note.fields[1] = "Home Dashboard {} exact-package statistics QA".format(RELEASE)
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
    base._require(abs(week.seconds - 22_496.0) < 0.001, "dashboard Last 7 Days time differs from Anki")
    base._require((week.retention.numerator, week.retention.denominator, week.retention.percent) == (947, 1_100, 86), "dashboard week retention mismatch")
    base._require((week.again_rate.numerator, week.again_rate.denominator) == (153, 1_100), "dashboard week Again counts mismatch")
    base._require((all_time.lifetime_cards_studied, all_time.lifetime_retention.percent) == (1_184, 86), "dashboard all-time totals mismatch")
    base._require(queue.total == queue.new + queue.learning + queue.review, "dashboard QueueStats invariant failed")
    base._require(
        buried.new + buried.learning + buried.review == 1,
        "dashboard due-or-new explicit buried count mismatch",
    )
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
            "week_seconds": 22_496.0,
            "visible_week_time": "6 hr 15 min",
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
            "queue": {"new": queue.new, "learning": queue.learning, "review": queue.review, "total": queue.total, "initial_cards_due": today.answers + queue.total},
            "buried": {"new": buried.new, "learning": buried.learning, "review": buried.review},
            "week": {"answers": week.cards_studied, "average_cards_per_day": (2 * week.cards_studied + 7) // 14, "new_cards": week.new_cards_studied, "seconds": week.seconds, "retention": week.retention.percent, "internal_again": 100 - int(week.retention.percent or 0)},
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
  function inside(inner,outer,tolerance){return !!inner&&!!outer&&inner.left>=outer.left-tolerance&&inner.right<=outer.right+tolerance&&inner.top>=outer.top-tolerance&&inner.bottom<=outer.bottom+tolerance;}
  function bands(nodes,key){return Array.from(new Set(nodes.map(function(n){return Math.round(rect(n)[key]);}))).length;}
  function previousVisibleBox(node){
    var current=node;
    while(current&&current!==document.body){
      var candidate=current.previousElementSibling;
      while(candidate){
        var candidateRect=rect(candidate);
        if(visible(candidate)&&candidateRect&&candidateRect.height>0)return candidate;
        candidate=candidate.previousElementSibling;
      }
      current=current.parentElement;
    }
    return null;
  }
  function overflowAmount(n){return n?Math.max(0,n.scrollWidth-n.clientWidth):0;}
  var calendar=q('.hdo-calendar-card');
  var grid=q('.hdo-calendar-grid');
  var layout=q('.hdo-dashboard-layout');
  var rail=q('.hdo-insight-rail');
  var metricsGrid=q('.hdo-summary-metrics-grid');
  var statisticCards=qa('.hdo-statistics-card');
  var bible=q('.hdo-bible-card');
  var frame=q('.hdo-calendar-grid-frame');
  var heatmap=q('.hdo-year-heatmap-content');
  var yearGrid=q('.hdo-calendar-grid--year');
  var yearCells=qa('.hdo-calendar-grid--year .hdo-calendar-day');
  var yearOccupiedNodes=yearCells.concat(qa('.hdo-year-weekday-label'));
  var verse=q('.hdo-verse');
  var progressTrack=q('[data-hdo-progress-track]');
  var progressLabels=[q('[data-hdo-progress-label]'),q('[data-hdo-progress-label-fill]')].filter(Boolean);
  var scroller=document.scrollingElement;
  var rootStyle=getComputedStyle(root);
  var title=q('#hdo-calendar-heading');
  var controls=qa('.hdo-header-controls button');
  var cells=qa('.hdo-calendar-day');
  var selected=q('.hdo-calendar-day.is-selected');
  var selectedStyle=selected?getComputedStyle(selected):null;
  var metricValues={};
  %s.forEach(function(key){var n=q('[data-hdo-metric="'+key+'"]');metricValues[key]=n?n.textContent.trim():'';});
  var metricOrder={};
  var expectedMetricOrder=%s;
  Object.keys(expectedMetricOrder).forEach(function(group){
    var card=q('[aria-labelledby="'+group+'-title"]');
    metricOrder[group]=card?qa('[aria-labelledby="'+group+'-title"] [data-hdo-metric]').map(function(n){return n.dataset.hdoMetric||'';}):[];
  });
  var rootRect=rect(root);
  var calendarRect=rect(calendar);
  var layoutRect=rect(layout);
  var railRect=rect(rail);
  var metricsRect=rect(metricsGrid);
  var bibleRect=rect(bible);
  var frameRect=rect(frame);
  var previousBox=previousVisibleBox(root);
  var previousBoxRect=rect(previousBox);
  var metricGaps=qa('.hdo-metric-row').map(function(row){
    var label=row.querySelector('dt');var value=row.querySelector('dd');
    return label&&value?rect(value).left-rect(label).right:-1;
  });
  var metricTextSingleLine=qa('.hdo-metric-row').every(function(row){
    var label=row.querySelector('dt');var value=row.querySelector('dd');
    if(!label||!value)return false;
    var labelStyle=getComputedStyle(label);var valueStyle=getComputedStyle(value);
    return labelStyle.whiteSpace==='nowrap'&&valueStyle.whiteSpace==='nowrap'&&
      label.scrollWidth<=label.clientWidth+1&&value.scrollWidth<=value.clientWidth+1;
  });
  var cardWidths=statisticCards.map(function(card){return rect(card).width;});
  var cardHeights=statisticCards.map(function(card){return rect(card).height;});
  var yearCellWidths=yearCells.map(function(cell){return rect(cell).width;});
  var yearCellHeights=yearCells.map(function(cell){return rect(cell).height;});
  var occupiedLeft=yearOccupiedNodes.length?Math.min.apply(null,yearOccupiedNodes.map(function(node){return rect(node).left;})):0;
  var occupiedRight=yearOccupiedNodes.length?Math.max.apply(null,yearOccupiedNodes.map(function(node){return rect(node).right;})):0;
  var componentNodes=[root,layout,calendar,rail,metricsGrid,bible,frame,grid].concat(statisticCards).filter(Boolean);
  var componentOverflowMax=componentNodes.length?Math.max.apply(null,componentNodes.map(overflowAmount)):0;
  var progressTrackRect=rect(progressTrack);
  var progressLabelCentered=!!progressTrackRect&&progressLabels.length===2&&progressLabels.every(function(label){
    var labelRect=rect(label);
    return Math.abs((labelRect.left+labelRect.right)/2-(progressTrackRect.left+progressTrackRect.right)/2)<=.75;
  });
  var progressLabelPadding=progressLabels.length?Math.min.apply(null,progressLabels.map(function(label){
    var style=getComputedStyle(label);return Math.min(parseFloat(style.paddingLeft)||0,parseFloat(style.paddingRight)||0);
  })):0;
  var progressHeader=q('.hdo-progress-card .hdo-stat-card-header');
  var progressFirstMetric=q('.hdo-progress-card .hdo-metric-row');
  var progress=q('[data-hdo-progress-label]');
  return {
    ready:true,
    loading:root.classList.contains('hdo-dashboard--loading'),
    theme:root.dataset.hdoTheme||'',
    mode:root.dataset.hdoColorMode||'',
    view:root.dataset.hdoCalendarView||'',
    root:rootRect,
    layout:layoutRect,
    calendar:calendarRect,
    rail:railRect,
    metricsGrid:metricsRect,
    bible:bibleRect,
    frame:frameRect,
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
    componentOverflowX:componentOverflowMax,
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
    progressTrackVisible:visible(progressTrack),
    progressTrackHeight:visible(progressTrack)?rect(progressTrack).height:0,
    dueLegendCount:qa('.hdo-legend-due').length,
    eventLegendCount:qa('.hdo-legend-event').length,
    eventSummaryCount:qa('[data-hdo-context-event]').length,
    todayCount:qa('.hdo-calendar-day.is-today').length,
    selectedCount:qa('.hdo-calendar-day.is-selected').length,
    dueMarkerCount:qa('.hdo-calendar-day[data-due-level]:not([data-due-level="0"])').length,
    eventMarkerCount:qa('.hdo-calendar-day .hdo-event-marker').length,
    completionCount:qa('.hdo-calendar-day[data-level]:not([data-level="0"])').length,
    selectedBoxShadow:selectedStyle?selectedStyle.boxShadow:'',
    nonSelectedCellShadowCount:cells.filter(function(n){
      return !n.classList.contains('is-selected') && getComputedStyle(n).boxShadow!=='none';
    }).length,
    verseFontSize:verse?getComputedStyle(verse).fontSize:'',
    verseFontFamily:verse?getComputedStyle(verse).fontFamily:'',
    verseColor:verse?getComputedStyle(verse).color:'',
    sectionsBelow:!!calendar&&!!rail&&rect(rail).top>=rect(calendar).bottom-1,
    statisticsCardCount:statisticCards.length,
    statisticColumns:metricsGrid?getComputedStyle(metricsGrid).gridTemplateColumns:'',
    statisticColumnCount:bands(statisticCards,'left'),
    statisticRowCount:bands(statisticCards,'top'),
    equalStatisticCardGeometry:statisticCards.length===4&&(
      bands(statisticCards,'left')!==2||(
        Math.max.apply(null,cardWidths)-Math.min.apply(null,cardWidths)<=1&&
        Math.max.apply(null,cardHeights)-Math.min.apply(null,cardHeights)<=1
      )
    ),
    metricMinimumGap:metricGaps.length?Math.min.apply(null,metricGaps):-1,
    metricTextSingleLine:metricTextSingleLine,
    layoutSideBySide:!!calendarRect&&!!railRect&&calendarRect.right<=railRect.left+1,
    layoutStacked:!!calendarRect&&!!railRect&&calendarRect.bottom<=railRect.top+1,
    layoutColumnGap:!!calendarRect&&!!railRect?railRect.left-calendarRect.right:0,
    topEdgeDelta:!!calendarRect&&!!railRect?Math.abs(calendarRect.top-railRect.top):0,
    railWidth:railRect?railRect.width:0,
    monthBottomDelta:!!calendarRect&&!!bibleRect?Math.abs(calendarRect.bottom-bibleRect.bottom):null,
    yearBottomDelta:!!calendarRect&&!!metricsRect?Math.abs(calendarRect.bottom-metricsRect.bottom):null,
    deckDashboardGap:previousBoxRect?rootRect.top-previousBoxRect.bottom:null,
    deckGapAnchor:previousBox?{tag:previousBox.tagName,id:previousBox.id||'',className:String(previousBox.className||'')}:null,
    yearMonthLabels:qa('.hdo-year-month-label').map(function(node){return node.textContent.trim();}),
    yearWeekdayLabels:qa('.hdo-year-weekday-label').map(function(node){return node.textContent.trim();}),
    yearGridInsideFrame:!yearGrid||inside(rect(yearGrid),frameRect,1),
    yearFrameOverflowX:frame?frame.scrollWidth-frame.clientWidth:0,
    yearFrameScrollLeft:frame?frame.scrollLeft:0,
    yearHeatmapWidthRatio:yearGrid&&frameRect?((occupiedRight-occupiedLeft)/Math.max(1,frameRect.width)):0,
    yearCellsSquare:yearCells.every(function(cell){return Math.abs(rect(cell).width-rect(cell).height)<=.5;}),
    yearCellWidthMin:yearCellWidths.length?Math.min.apply(null,yearCellWidths):0,
    yearCellWidthMax:yearCellWidths.length?Math.max.apply(null,yearCellWidths):0,
    yearCellHeightMin:yearCellHeights.length?Math.min.apply(null,yearCellHeights):0,
    yearCellHeightMax:yearCellHeights.length?Math.max.apply(null,yearCellHeights):0,
    progressLabelCentered:progressLabelCentered,
    progressLabelPadding:progressLabelPadding,
    progressHeaderToBarGap:progressHeader&&progressTrack?rect(progressTrack).top-rect(progressHeader).bottom:null,
    progressBarToMetricsGap:progressTrack&&progressFirstMetric?rect(progressFirstMetric).top-rect(progressTrack).bottom:null,
    metricValues:metricValues,
    metricOrder:metricOrder,
    progressLabel:progress?progress.textContent.trim():''
  };
})()
""" % (json.dumps(STATISTIC_METRIC_KEYS), json.dumps(STATISTIC_METRIC_ORDER))


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
    base._require(0 < root_width <= 1160.5, "dashboard exceeds its 1160px maximum")
    base._require(state.get("rootPosition") not in {"fixed", "sticky"}, "dashboard root left document flow")
    base._require(abs(_pixels(state.get("rootMarginTop")) - 30) <= 0.5, "dashboard top margin is not the calibrated 30px")
    base._require(float(state.get("documentOverflowX", 0)) <= 1, "document has horizontal overflow")
    base._require(float(state.get("bodyOverflowX", 0)) <= 1, "body has horizontal overflow")
    base._require(float(state.get("componentOverflowX", 0)) <= 1, "dashboard component has horizontal overflow")
    base._require(state.get("hostPreserved") == "true", "host canvas was not preserved")
    base._require(state.get("rootBackground") in {"rgba(0, 0, 0, 0)", "transparent"}, "dashboard root is not transparent")
    base._require(state.get("rootScrollOwner") in {"documentElement", "body"}, "document scroller does not own vertical movement")
    clearance = float(state.get("footerClearance", 0))
    footer_height = float(state.get("nativeFooterHeight", 0))
    base._require(footer_height > 0 and abs(clearance - footer_height - 24) <= 1, "bottom clearance is not measured height plus 24px")
    base._require(abs(_pixels(state.get("rootPaddingBottom")) - clearance) <= 1, "root bottom padding drifted from measured clearance")
    base._require(abs(_pixels(state.get("documentScrollPaddingBlockEnd")) - clearance) <= 1, "document scroll padding drifted from measured clearance")
    base._require(_pixels(state.get("titleFontSize")) == 18, "calendar title is not 18px")
    base._require(len(state.get("controlHeights", [])) >= 5, "calendar header controls are incomplete")
    base._require(
        all(28 <= int(value) <= 34 for value in state.get("controlHeights", [])),
        "calendar controls escaped the approved 28-34px range",
    )
    if bool(state.get("progressTrackVisible")):
        base._require(
            abs(float(state.get("progressTrackHeight", 0)) - 18) <= 0.5,
            "numeric progress track is not 18px",
        )
        base._require(bool(state.get("progressLabelCentered")), "progress labels are not centered over the full track")
        base._require(float(state.get("progressLabelPadding", 0)) >= 6, "progress labels have less than 6px horizontal padding")
        base._require(
            abs(float(state.get("progressHeaderToBarGap", -99)) - 8) <= 1,
            "progress heading-to-bar gap is not 8px",
        )
        base._require(
            abs(float(state.get("progressBarToMetricsGap", -99)) - 10) <= 1,
            "progress bar-to-first-metric gap is not 10px",
        )
    expected_width = case.get("container_width")
    if isinstance(expected_width, int):
        base._require(abs(root_width - expected_width) <= 1, "exact dashboard container width did not settle")
    elif str(case.get("layout", "")) == "wide":
        base._require(abs(root_width - 1160) <= 1, "wide dashboard did not settle at 1160px")

    base._require(int(state.get("statisticsCardCount", 0)) == 4, "dashboard did not render four statistic cards")
    expected_metric_columns = 1 if root_width <= 588.5 else 2
    expected_metric_rows = 4 if expected_metric_columns == 1 else 2
    base._require(
        int(state.get("statisticColumnCount", 0)) == expected_metric_columns
        and int(state.get("statisticRowCount", 0)) == expected_metric_rows,
        "statistic grid does not match the 588/589px responsive boundary",
    )
    base._require(bool(state.get("equalStatisticCardGeometry")), "2x2 statistic cards do not have equal geometry")
    base._require(float(state.get("metricMinimumGap", -1)) >= 8, "metric label/value gap is below 8px")
    base._require(bool(state.get("metricTextSingleLine")), "metric text wrapped or clipped")

    expected_density = "wide" if root_width >= 1009 else "intermediate" if root_width >= 589 else "narrow"
    base._require(state.get("density") == expected_density, "dashboard density differs from the 588/589 and 1008/1009 boundaries")
    calendar = state.get("calendar") or {}
    metrics_grid = state.get("metricsGrid") or {}
    bible = state.get("bible") or {}
    if root_width >= 1009:
        base._require(bool(state.get("layoutSideBySide")), "wide dashboard did not place calendar and rail side by side")
        base._require(abs(float(state.get("railWidth", 0)) - 360) <= 1, "wide statistics rail is not 360px")
        base._require(abs(float(state.get("layoutColumnGap", 0)) - 14) <= 1, "wide dashboard column gap is not 14px")
        base._require(float(state.get("topEdgeDelta", 99)) <= 1, "wide calendar and statistics rail do not share a top edge")
        gap = state.get("deckDashboardGap")
        base._require(gap is not None and 28 <= float(gap) <= 30.5, "native deck-to-dashboard gap is not 28-30px")
        base._require(float(metrics_grid.get("height", 0)) >= 351, "wide summary grid is below its 352px target")
        if case.get("view") == "month":
            base._require(float(calendar.get("height", 0)) >= 545, "wide Month calendar is below its 546px target")
            base._require(float(bible.get("height", 0)) >= 181, "wide Bible card is below its 182px target")
            base._require(float(state.get("monthBottomDelta", 99)) <= 2, "Month calendar and Bible card bottoms do not align")
        else:
            base._require(float(calendar.get("height", 0)) >= 351, "wide Year calendar is below its 352px target")
            base._require(float(state.get("yearBottomDelta", 99)) <= 2, "Year calendar and summary grid bottoms do not align")
    else:
        base._require(bool(state.get("layoutStacked")), "1008px-or-narrower dashboard did not stack")
    base._require(
        int(state.get("nonSelectedCellShadowCount", 1)) == 0,
        "unselected calendar cells retain shadows",
    )
    if int(state.get("selectedCount", 0)):
        selected_shadow = str(state.get("selectedBoxShadow", ""))
        base._require(
            "inset" in selected_shadow and "2px" in selected_shadow,
            "selected date is missing its 2px inset ring",
        )
    if case.get("view") == "month":
        base._require(int(state.get("calendarCellCount", 0)) == 42, "Month is not 42 cells")
        base._require(str(state.get("monthRows")) == "6", "Month is not six rows")
    else:
        base._require(str(state.get("yearWeeks")) == "53", "Year is not a 53-week grid")
        base._require(int(state.get("calendarCellCount", 0)) in {365, 366}, "Year does not contain the full year")
        base._require(
            state.get("yearMonthLabels") == ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
            "Year month labels are incomplete or out of order",
        )
        base._require(state.get("yearWeekdayLabels") == ["Mon", "Wed", "Fri"], "Year weekday labels are incomplete or out of order")
        base._require(bool(state.get("yearGridInsideFrame")), "Year grid is outside its frame")
        base._require(float(state.get("yearFrameOverflowX", 1)) <= 1, "Year grid requires internal horizontal scrolling")
        base._require(abs(float(state.get("yearFrameScrollLeft", 1))) <= 1, "Year grid retained a horizontal scroll offset")
        base._require(bool(state.get("yearCellsSquare")), "Year heatmap cells are not square")
        if root_width >= 1009:
            ratio = float(state.get("yearHeatmapWidthRatio", 0))
            base._require(ratio >= .85, "wide Year heatmap occupies less than 85 percent of its body")
        if root_width >= 1159:
            base._require(
                9 <= float(state.get("yearCellWidthMin", 0))
                and float(state.get("yearCellWidthMax", 99)) <= 10.5,
                "1160px Year cells are outside the 9-10px target",
            )
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
        metric_order = state.get("metricOrder")
        base._require(
            isinstance(metric_order, Mapping)
            and {
                str(group): tuple(str(key) for key in keys)
                for group, keys in metric_order.items()
            } == STATISTIC_METRIC_ORDER,
            "statistics row order differs from the visible contract",
        )
        base._require(metrics["last_seven_days.retention"] == "86%", "native week retention is not 86%")
        base._require(metrics["last_seven_days.time_spent"] == "6 hr 15 min6h 15m", "visible Last 7 Days time is not 6 hr 15 min")
        base._require(metrics["long_term.lifetime_retention"] == "86%", "native lifetime retention is not 86%")

        def count_value(key: str) -> int:
            return int(metrics[key].replace(",", ""))

        base._require(
            count_value("queue.total")
            == count_value("queue.new") + count_value("queue.learning") + count_value("queue.review"),
            "visible QueueStats total invariant failed",
        )
        base._require(
            count_value("progress.initial_cards_due")
            == count_value("today.answers") + count_value("queue.total"),
            "visible Initial cards due differs from the progress denominator",
        )
        week_cards = count_value("last_seven_days.cards_studied")
        base._require(
            count_value("last_seven_days.average_cards_per_day")
            == (2 * week_cards + 7) // 14,
            "visible Last 7 Days average is not the half-up fixed seven-period average",
        )
        initial = base.REPORT.get("statistics_render_paths", {}).get(str(case["id"]), {})
        initial_metrics = initial.get("initial_html")
        base._require(
            isinstance(initial_metrics, Mapping),
            "initial HTML statistics values are unavailable",
        )
        base._require(
            all(
                str(initial_metrics.get(key, ""))
                and str(metrics.get(key, ""))
                for key in CLOCK_RELATIVE_METRIC_KEYS
            ),
            "clock-relative statistics presentation is empty",
        )
        stable_initial = {
            key: value
            for key, value in initial_metrics.items()
            if key not in CLOCK_RELATIVE_METRIC_KEYS
        }
        stable_live = {
            key: value
            for key, value in metrics.items()
            if key not in CLOCK_RELATIVE_METRIC_KEYS
        }
        base._require(
            stable_initial == stable_live,
            "initial HTML and live-refresh stable metric values differ",
        )
        base._require(
            initial.get("initial_progress") == state.get("progressLabel"),
            "initial HTML and live-refresh progress values differ",
        )
        if _canonical_statistics_metrics is None:
            _canonical_statistics_metrics = metrics
        else:
            canonical_stable = {
                key: value
                for key, value in _canonical_statistics_metrics.items()
                if key not in CLOCK_RELATIVE_METRIC_KEYS
            }
            base._require(
                stable_live == canonical_stable,
                "responsive or restart stable metric values drifted",
            )
        columns = [item for item in str(state.get("statisticColumns", "")).split() if item]
        if str(case.get("layout", "")) == "wide":
            base._require(len(columns) == 2, "wide statistics rail is not the required 2x2 grid")
        base.REPORT.setdefault("statistics_responsive_parity", {})[str(case["id"])] = {
            "metrics": metrics,
            "progress": str(state.get("progressLabel", "")),
            "computed_columns": len(columns),
            "layout": str(case.get("layout", "")),
            "view": str(case.get("view", "")),
            "clock_relative_metrics": {
                key: {
                    "initial_html": str(initial_metrics.get(key, "")),
                    "live_refresh": str(metrics.get(key, "")),
                    "parity_policy": "nonempty-clock-relative-presentation",
                }
                for key in sorted(CLOCK_RELATIVE_METRIC_KEYS)
            },
            "status": "passed",
        }
        base._write_report()


base._validate_dom = _validate_dom


_base_font: QFont | None = None
_font_restore_hook_connected = False
_settings_cases: list[dict[str, Any]] = []
_settings_index = 0
_settings_dialog: SettingsDialog | None = None
_settings_started = False
_structured_settings_cases: list[dict[str, Any]] = []
_structured_settings_index = 0
_structured_settings_started = False
_structured_settings_pngs_before: dict[str, str] = {}
_structured_settings_reports: dict[int, dict[str, Any]] = {}
_structured_settings_geometry_snapshot: dict[str, tuple[bool, object]] | None = None
_geometry_store = QSettings()
_geometry_preference_was_present = _geometry_store.contains(SETTINGS_GEOMETRY_KEY)
_geometry_preference_before_probe = _geometry_store.value(SETTINGS_GEOMETRY_KEY)
_geometry_screen_preference_was_present = _geometry_store.contains(
    SETTINGS_GEOMETRY_SCREEN_KEY
)
_geometry_screen_preference_before_probe = _geometry_store.value(
    SETTINGS_GEOMETRY_SCREEN_KEY
)
_geometry_available_preference_was_present = _geometry_store.contains(
    SETTINGS_GEOMETRY_AVAILABLE_KEY
)
_geometry_available_preference_before_probe = _geometry_store.value(
    SETTINGS_GEOMETRY_AVAILABLE_KEY
)
_geometry_dpr_preference_was_present = _geometry_store.contains(
    SETTINGS_GEOMETRY_DPR_KEY
)
_geometry_dpr_preference_before_probe = _geometry_store.value(
    SETTINGS_GEOMETRY_DPR_KEY
)
_previous_geometry_preference_was_present = _geometry_store.contains(
    SETTINGS_PREVIOUS_GEOMETRY_KEY
)
_previous_geometry_preference_before_probe = _geometry_store.value(
    SETTINGS_PREVIOUS_GEOMETRY_KEY
)
_previous_geometry_screen_preference_was_present = _geometry_store.contains(
    SETTINGS_PREVIOUS_GEOMETRY_SCREEN_KEY
)
_previous_geometry_screen_preference_before_probe = _geometry_store.value(
    SETTINGS_PREVIOUS_GEOMETRY_SCREEN_KEY
)
_geometry_restart_marker = OUTPUT_ROOT / "settings-geometry-restart.json"
_preserve_geometry_for_restart = False
_legacy_geometry_key = "home_dashboard_overhaul/settings_dialog_geometry/v2"
_legacy_geometry_preference_was_present = _geometry_store.contains(
    _legacy_geometry_key
)
_legacy_geometry_preference_before_probe = _geometry_store.value(
    _legacy_geometry_key
)

_ALL_SETTINGS_GEOMETRY_KEYS = (
    SETTINGS_GEOMETRY_KEY,
    SETTINGS_GEOMETRY_SCREEN_KEY,
    SETTINGS_GEOMETRY_AVAILABLE_KEY,
    SETTINGS_GEOMETRY_DPR_KEY,
    SETTINGS_PREVIOUS_GEOMETRY_KEY,
    SETTINGS_PREVIOUS_GEOMETRY_SCREEN_KEY,
    _legacy_geometry_key,
)


def _snapshot_geometry_preferences() -> dict[str, tuple[bool, object]]:
    """Capture every geometry-generation value for exact temporary restore."""

    snapshot: dict[str, tuple[bool, object]] = {}
    for key in _ALL_SETTINGS_GEOMETRY_KEYS:
        present = _geometry_store.contains(key)
        value = _geometry_store.value(key) if present else None
        if isinstance(value, QRect):
            value = QRect(value)
        snapshot[key] = (present, value)
    return snapshot


def _restore_geometry_snapshot(
    snapshot: Mapping[str, tuple[bool, object]],
) -> None:
    """Restore a temporary native geometry fixture without leaving drift."""

    for key in _ALL_SETTINGS_GEOMETRY_KEYS:
        present, value = snapshot.get(key, (False, None))
        if present:
            _geometry_store.setValue(key, value)
        else:
            _geometry_store.remove(key)
    _geometry_store.sync()


def _rect_payload(value: object) -> list[int] | None:
    if isinstance(value, QRect):
        return [value.x(), value.y(), value.width(), value.height()]
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        try:
            return [int(value[index]) for index in range(4)]
        except (TypeError, ValueError):
            return None
    return None


def _read_geometry_restart_marker() -> dict[str, Any]:
    if not _geometry_restart_marker.exists():
        return {}
    try:
        payload = json.loads(_geometry_restart_marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _record_geometry_contract_assertions() -> None:
    """Prove non-PNG geometry cases inside the disposable native run."""

    primary = (0, 0, 1600, 1000)
    secondary = (1600, 0, 1920, 1080)
    checks = {
        "legacy_720x520_v2_record_ignored": (
            _legacy_geometry_key != SETTINGS_GEOMETRY_KEY
            and not saved_window_geometry_is_valid((100, 100, 720, 520), [primary])
        ),
        "legacy_940x680_v2_record_ignored": (
            _legacy_geometry_key != SETTINGS_GEOMETRY_KEY
            and saved_window_geometry_is_valid((100, 100, 940, 680), [primary])
        ),
        "valid_940x680_v3_record_migrates": migrate_saved_window_geometry(
            (100, 100, 940, 680),
            [primary],
            source_version=3,
        ) == (100, 100, 940, 680),
        "valid_1180x800_restore_accepted": saved_window_geometry_is_valid(
            (100, 100, 1180, 800), [primary]
        ),
        "secondary_monitor_restore_accepted": saved_window_geometry_is_valid(
            (1700, 100, 1180, 800), [primary, secondary],
            saved_screen_exists=True,
        ),
        "disconnected_monitor_restore_rejected": not saved_window_geometry_is_valid(
            (1700, 100, 1180, 800), [primary],
            saved_screen_exists=False,
        ),
        "eighty_percent_visibility_accepted": saved_window_geometry_is_valid(
            (-236, 100, 1180, 800), [primary]
        ),
        "below_eighty_percent_visibility_rejected": not saved_window_geometry_is_valid(
            (-237, 100, 1180, 800), [primary]
        ),
        "normal_screen_keeps_vertical_navigation": not settings_screen_uses_compact_fallback(
            (1440, 900)
        ),
        "small_screen_activates_compact_fallback": settings_screen_uses_compact_fallback(
            (900, 650)
        ),
        "normal_geometry_keeps_48px_margins": clamp_window_geometry(
            None, primary
        ) == (260, 120, 1080, 760),
    }
    for label, passed in checks.items():
        base._require(passed, "Settings geometry assertion failed: {}".format(label))
    base.REPORT["settings_geometry_assertions"] = {
        "status": "passed",
        "checks": checks,
        "png_count": 0,
        "legacy_geometry_key_read": False,
        "space_switching": "manual-result-required",
    }


def _settings_page_cases() -> list[dict[str, Any]]:
    return [
        case
        for case in CAPTURE_PLAN.cases(
            CAPTURE_PROFILE,
            stage="initial",
            component="settings",
            include_ids=REQUESTED_CAPTURE_IDS,
        )
        if case["family"] == "settings-pages"
    ]


def _settings_contract_cases() -> list[dict[str, Any]]:
    return [
        case
        for case in CAPTURE_PLAN.cases(
            CAPTURE_PROFILE,
            stage="initial",
            component="settings",
            include_ids=REQUESTED_CAPTURE_IDS,
        )
        if case["family"] == "settings-contract"
    ]


def _events_fixture() -> list[dict[str, Any]]:
    return [
        {"id": "evt-a", "name": "Pediatrics board review", "date": "2026-08-27", "archived": False, "created_at": "2026-08-24T09:00:00-05:00", "archived_at": ""},
        {"id": "evt-b", "name": "Anatomy study group", "date": "2026-08-28", "archived": False, "created_at": "2026-08-24T09:01:00-05:00", "archived_at": ""},
        {"id": "evt-z", "name": "Completed milestone", "date": "2026-08-20", "archived": True, "created_at": "2026-08-20T09:00:00-05:00", "archived_at": "2026-08-24T09:02:00-05:00"},
    ]


def _settings_config(case: Mapping[str, Any]) -> dict[str, Any]:
    special = str(case.get("special", ""))
    if base.STAGE == "restart" and special == "restart-persistence":
        return normalize_config(
            mw.addonManager.getConfig(base._controller.package)
        )
    config = normalize_config({})
    config["appearance"].update(preset="Graphite", mode="dark")
    config["heatmap"]["calendar_view"] = "year" if base.STAGE == "restart" else "month"
    config["events"]["sort"] = "name"
    if "events-empty" in special:
        config["events"]["items"] = []
    else:
        config["events"]["items"] = _events_fixture()
    if special == "events-no-results":
        config["events"]["items"] = [
            item for item in _events_fixture()
            if "pediatrics" not in str(item.get("name", "")).casefold()
        ]
    if special == "event-long-title":
        config["events"]["items"].extend([
            {
                "id": "evt-long",
                "name": "Pediatrics longitudinal review conference with an intentionally long title",
                "date": "2026-08-29",
                "archived": False,
                "created_at": "2026-08-24T09:03:00-05:00",
                "archived_at": "",
            },
            {
                "id": "evt-c",
                "name": "Cardiology review",
                "date": "2026-08-30",
                "archived": False,
                "created_at": "2026-08-24T09:04:00-05:00",
                "archived_at": "",
            },
            {
                "id": "evt-d",
                "name": "Dermatology review",
                "date": "2026-08-31",
                "archived": False,
                "created_at": "2026-08-24T09:05:00-05:00",
                "archived_at": "",
            },
            {
                "id": "evt-e",
                "name": "Endocrinology review",
                "date": "2026-09-01",
                "archived": False,
                "created_at": "2026-08-24T09:06:00-05:00",
                "archived_at": "",
            },
            {
                "id": "evt-f",
                "name": "Family medicine review",
                "date": "2026-09-02",
                "archived": False,
                "created_at": "2026-08-24T09:07:00-05:00",
                "archived_at": "",
            },
        ])
    if special == "future-off":
        config["heatmap"]["show_due_forecast"] = False
    elif special == "future-on":
        config["heatmap"]["show_due_forecast"] = True
        config["heatmap"]["forecast_days"] = 90
    elif special == "advanced-appearance":
        config["appearance"].update(preset="Sapphire Glass", opacity=96, blur=12)
    if "bible-short" in special:
        config["bible"]["quotes"] = ["Be still, and know that I am God.<br> - Psalm 46:10 (NLT)"]
    elif special == "bible-long":
        config["bible"]["quotes"] = [
            "Trust in the Lord with all your heart and do not depend on your own understanding. Seek his will in all you do, and he will show you which path to take through every season of learning, service, patience, and faithful practice.<br> - Proverbs 3:5-6 (NLT)"
        ]
    elif special == "bible-custom-valid":
        config["bible"].update(
            font_family="Avenir Next, sans-serif",
            font_size="36px",
            font_color="#151D25",
            theme_aware_color=False,
            quotes=["The Lord is my strength and my song.<br> - Psalm 118:14 (NLT)"],
        )
    elif special == "bible-long-row":
        config["bible"]["quotes"][-1] = (
            "The steadfast love of the Lord never ceases; his mercies never come to an end, "
            "and this deliberately extended excerpt verifies the complete two-line delegate layout."
            "<br> - Lamentations 3:22-23 Extended Reference (NLT)"
        )
    if special == "save-error-production":
        # Exercise a real staged manual selection. Injecting a pending quote
        # while the model remains in Daily mode is not a valid product state:
        # the normal dependency refresh correctly clears it.
        config["bible"]["rotation_mode"] = "manual"
    return config


def _set_application_font(percent: int) -> None:
    global _base_font, _font_restore_hook_connected
    application = QApplication.instance()
    base._require(application is not None, "QApplication is unavailable")
    if _base_font is None:
        _base_font = QFont(application.font())
    if not _font_restore_hook_connected:
        application.aboutToQuit.connect(_restore_application_font)
        _font_restore_hook_connected = True
    font = QFont(_base_font)
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() * percent / 100.0)
    elif font.pixelSize() > 0:
        font.setPixelSize(max(1, round(font.pixelSize() * percent / 100.0)))
    application.setFont(font)


def _restore_application_font() -> None:
    application = QApplication.instance()
    if application is not None and _base_font is not None:
        application.setFont(QFont(_base_font))


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


def _set_geometry_fixture(case: Mapping[str, Any], available: Any) -> None:
    """Prepare only the persisted input; product code performs the clamp."""

    special = str(case.get("special", ""))
    if base.STAGE == "restart" and special == "restart-persistence":
        _geometry_store.sync()
        return
    _geometry_store.remove(SETTINGS_GEOMETRY_KEY)
    _geometry_store.remove(SETTINGS_GEOMETRY_SCREEN_KEY)
    _geometry_store.remove(SETTINGS_GEOMETRY_AVAILABLE_KEY)
    _geometry_store.remove(SETTINGS_GEOMETRY_DPR_KEY)
    _geometry_store.remove(SETTINGS_PREVIOUS_GEOMETRY_KEY)
    _geometry_store.remove(SETTINGS_PREVIOUS_GEOMETRY_SCREEN_KEY)
    _geometry_store.remove(_legacy_geometry_key)
    if special == "window-fresh-open":
        _geometry_store.setValue(
            _legacy_geometry_key,
            QRect(available.x() + 20, available.y() + 20, 940, 680),
        )
    if special == "window-clamp":
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_KEY,
            QRect(
                available.x() - available.width(),
                available.y() - available.height(),
                available.width() * 2,
                available.height() * 2,
            ),
        )
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_SCREEN_KEY,
            _settings_screen().name(),
        )
    elif special == "window-offscreen-restore":
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_KEY,
            QRect(
                available.right() + 2400,
                available.bottom() + 1600,
                1080,
                760,
            ),
        )
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_SCREEN_KEY,
            _settings_screen().name(),
        )
    _geometry_store.sync()


def _restore_geometry_preference() -> None:
    if base.STAGE == "initial" and _preserve_geometry_for_restart:
        return
    marker = _read_geometry_restart_marker() if base.STAGE == "restart" else {}

    def restore_value(
        key: str,
        present: bool,
        value: object,
        *,
        rectangle: bool = False,
    ) -> None:
        if not present:
            _geometry_store.remove(key)
            return
        restored = _rect_payload(value) if rectangle else value
        if rectangle:
            if restored is None:
                _geometry_store.remove(key)
                return
            restored = QRect(*restored)
        _geometry_store.setValue(key, restored)

    if marker:
        restore_value(
            SETTINGS_GEOMETRY_KEY,
            bool(marker.get("original_was_present")),
            marker.get("original_geometry"),
            rectangle=True,
        )
        restore_value(
            SETTINGS_GEOMETRY_SCREEN_KEY,
            bool(marker.get("original_screen_was_present")),
            str(marker.get("original_screen") or ""),
        )
        restore_value(
            SETTINGS_GEOMETRY_AVAILABLE_KEY,
            bool(marker.get("original_available_was_present")),
            marker.get("original_available"),
            rectangle=True,
        )
        restore_value(
            SETTINGS_GEOMETRY_DPR_KEY,
            bool(marker.get("original_dpr_was_present")),
            marker.get("original_dpr"),
        )
        restore_value(
            SETTINGS_PREVIOUS_GEOMETRY_KEY,
            bool(marker.get("original_previous_geometry_was_present")),
            marker.get("original_previous_geometry"),
            rectangle=True,
        )
        restore_value(
            SETTINGS_PREVIOUS_GEOMETRY_SCREEN_KEY,
            bool(marker.get("original_previous_screen_was_present")),
            str(marker.get("original_previous_screen") or ""),
        )
        restore_value(
            _legacy_geometry_key,
            bool(marker.get("original_legacy_was_present")),
            marker.get("original_legacy_geometry"),
            rectangle=True,
        )
    else:
        for key, present, value, rectangle in (
            (
                SETTINGS_GEOMETRY_KEY,
                _geometry_preference_was_present,
                _geometry_preference_before_probe,
                True,
            ),
            (
                SETTINGS_GEOMETRY_SCREEN_KEY,
                _geometry_screen_preference_was_present,
                _geometry_screen_preference_before_probe,
                False,
            ),
            (
                SETTINGS_GEOMETRY_AVAILABLE_KEY,
                _geometry_available_preference_was_present,
                _geometry_available_preference_before_probe,
                True,
            ),
            (
                SETTINGS_GEOMETRY_DPR_KEY,
                _geometry_dpr_preference_was_present,
                _geometry_dpr_preference_before_probe,
                False,
            ),
            (
                SETTINGS_PREVIOUS_GEOMETRY_KEY,
                _previous_geometry_preference_was_present,
                _previous_geometry_preference_before_probe,
                True,
            ),
            (
                SETTINGS_PREVIOUS_GEOMETRY_SCREEN_KEY,
                _previous_geometry_screen_preference_was_present,
                _previous_geometry_screen_preference_before_probe,
                False,
            ),
            (
                _legacy_geometry_key,
                _legacy_geometry_preference_was_present,
                _legacy_geometry_preference_before_probe,
                True,
            ),
        ):
            restore_value(key, present, value, rectangle=rectangle)
    _geometry_store.sync()
    if base.STAGE == "restart" and _geometry_restart_marker.exists():
        try:
            _geometry_restart_marker.unlink()
        except OSError:
            pass


def _previsibility_capture_resize(
    dialog: SettingsDialog,
    case: Mapping[str, Any],
    available: Any,
) -> None:
    """Apply requested matrix geometry before show without fixing the window."""

    structured_work_area = case.get("structured_work_area_logical")
    if isinstance(structured_work_area, (list, tuple)) and len(structured_work_area) == 4:
        resolved = clamp_window_geometry(None, tuple(int(value) for value in structured_work_area))
        width = min(resolved[2], available.width())
        height = min(resolved[3], available.height())
        dialog.resize(width, height)
        dialog.move(
            available.x() + max(0, (available.width() - width) // 2),
            available.y() + max(0, (available.height() - height) // 2),
        )
        return
    special = str(case.get("special", ""))
    if special in {
        "window-fresh-open",
        "window-clamp",
        "window-offscreen-restore",
        "restart-persistence",
    }:
        return
    target_width = case.get("width", 1080)
    if target_width == "full":
        return
    else:
        width = min(max(860, int(target_width)), available.width() - 96)
        target_height = int(case.get("height", 800 if int(target_width) >= 1280 else 760))
        height = min(max(600, target_height), available.height() - 96)
    dialog.resize(width, height)
    dialog.move(
        available.x() + max(0, (available.width() - width) // 2),
        available.y() + max(0, (available.height() - height) // 2),
    )


def _prepare_settings_case(case: Mapping[str, Any]) -> SettingsDialog:
    _set_application_font(int(case.get("font_percent", 100)))
    special = str(case.get("special", ""))
    config = _settings_config(case)
    base._controller.config = config
    base._controller.snapshot = None
    available = _settings_screen().availableGeometry()
    preserve_geometry_fixture = bool(case.get("preserve_geometry_fixture"))
    if not preserve_geometry_fixture:
        _set_geometry_fixture(case, available)
    original_is_dark = base._controller.is_dark
    expected_anki_theme = str(case.get("anki_theme", "dark"))
    base._controller.is_dark = lambda: expected_anki_theme == "dark"
    dialog = SettingsDialog(
        mw,
        base._controller,
        initial_page=str(case.get("page", "dashboard")),
    )
    dialog._qa_original_is_dark = original_is_dark
    dialog._qa_anki_theme = expected_anki_theme
    if not preserve_geometry_fixture:
        _previsibility_capture_resize(dialog, case, available)
    dialog.setModal(True)

    if special == "events-searched":
        dialog.event_search.setText("Pediatrics")
        dialog._refresh_event_lists()
    elif special == "events-no-results":
        dialog.event_search.setText("Pediatrics")
        dialog._refresh_event_lists()
    elif special == "events-archived":
        dialog.event_tabs.setCurrentIndex(1)
        dialog._update_event_actions()
    elif special == "bible-custom-invalid":
        dialog.theme_color.setValue("custom")
        dialog._settings_changed()
        dialog.font_color.setText("#12ZZ99")
        dialog._font_color_edited()
    elif special == "advanced-appearance":
        dialog.appearance_advanced_button.setChecked(True)
    elif special in {
        "dirty",
        "discard",
        "close-confirmation",
        "save-in-progress",
        "save-success",
        "save-error-production",
    }:
        dialog.retention_target.setValue(81)
        dialog._sync_draft()
        if special == "close-confirmation":
            dialog.request_close()
        elif special == "save-in-progress":
            dialog._saving = True
            dialog.footer.set_error()
            dialog._set_status("saving", "Saving changes…")
            dialog.save_button.setText("Save changes")
            dialog.save_button.setEnabled(False)
            dialog.close_button.setEnabled(False)
            dialog._set_mutation_controls_enabled(False)
        elif special in {"save-success", "save-error-production"}:
            if special == "save-error-production":
                pending = next(
                    (
                        quote
                        for quote in dialog.quotes
                        if quote != dialog._saved_current_quote
                    ),
                    dialog.quotes[0] if dialog.quotes else None,
                )
                dialog.pending_manual_quote = pending
                dialog._pending_manual_quote_index = (
                    dialog.quotes.index(pending)
                    if pending in dialog.quotes
                    else None
                )
                staged_event = next(
                    item
                    for item in dialog.staged["events"]["items"]
                    if str(item.get("id", "")) == "evt-a"
                )
                staged_event["name"] = "{} (edited)".format(staged_event["name"])
                dialog._sync_draft()
                dialog._qa_failure_baseline_before = deepcopy(dialog.draft.baseline)
                dialog._qa_failure_values_before = deepcopy(dialog.draft.values)
                dialog._qa_failure_manual_before = dialog.pending_manual_quote
                dialog._qa_failure_events_before = deepcopy(
                    dialog.staged["events"]["items"]
                )
                external_latest = deepcopy(dialog.draft.baseline)
                current_sort = str(external_latest["events"].get("sort", "ascending"))
                external_latest["events"]["sort"] = (
                    "descending" if current_sort == "ascending" else "ascending"
                )
                dialog._latest_stored_config = lambda: deepcopy(external_latest)
                original = base._controller.save_config

                def fail_save(*_args: object, **_kwargs: object) -> None:
                    raise OSError("fixture write failure detail")

                base._controller.save_config = fail_save
                try:
                    dialog._save()
                    dialog._continue_save()
                finally:
                    base._controller.save_config = original
            else:
                dialog._latest_stored_config = lambda: deepcopy(dialog.draft.baseline)
    elif special == "legacy-route":
        dialog.open_page("calendar")
    return dialog


def _focus_capture_window(dialog: SettingsDialog) -> None:
    """Focus only the gated QA window before native sheet/compositor work."""
    base._require(base.REPORT.get("identity", {}).get("gated_before_window_interaction") is True,
                  "capture focus requires the disposable identity gate")
    if sys.platform == "darwin":
        objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        selector = objc.sel_registerName
        selector.argtypes = (ctypes.c_char_p,)
        selector.restype = ctypes.c_void_p
        get_class = objc.objc_getClass
        get_class.argtypes = (ctypes.c_char_p,)
        get_class.restype = ctypes.c_void_p
        send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
        activate = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(("objc_msgSend", objc))
        application = send(get_class(b"NSRunningApplication"), selector(b"currentApplication"))
        base._require(activate(application, selector(b"activateWithOptions:"), 2), "could not activate the disposable capture app")
    dialog.raise_()
    dialog.activateWindow()


def _activate_settings_case(case: Mapping[str, Any], focus_ready: bool = False) -> None:
    """Finish visible-only setup inside the production-equivalent exec loop."""

    try:
        base._require(_settings_dialog is not None, "Settings dialog disappeared before activation")
        dialog = _settings_dialog
        special = str(case.get("special", ""))
        if special in {"event-editor-open", "bible-long", "save-error-production"} and not focus_ready:
            _focus_capture_window(dialog)
            QTimer.singleShot(400, lambda: _activate_settings_case(case, True))
            return
        if case.get("family") == "settings-pages" and case.get("width") == "full":
            dialog.showMaximized()
        if special == "event-editor-open":
            base._require(dialog._select_event_id("evt-a", False), "event fixture is missing")
            event = dialog._selected_event()
            base._require(event is not None, "event editor has no selected event")
            editor = EventEditDialog(dialog, event)
            editor.show()
            dialog._qa_event_editor = editor
        elif special == "bible-long":
            base._require(bool(dialog.quotes), "long verse fixture is missing")
            editor = TextEditDialog("Edit verse", dialog.quotes[0], dialog)
            editor.show()
            dialog._qa_verse_editor = editor
        elif special == "discard":
            dialog._revert_changes()
        elif special == "save-success":
            dialog._save()
            dialog._continue_save()
        elif special == "about-bottom":
            scroll = dialog.stack.currentWidget()
            if isinstance(scroll, QScrollArea):
                scroll.verticalScrollBar().setValue(
                    scroll.verticalScrollBar().maximum()
                )
        _position_visible_target(dialog, case)
        QApplication.processEvents()
        delay_ms = 720
        if _settings_index == 1:
            delay_ms = max(
                delay_ms,
                int(os.environ.get("HDO_RELEASE_FIRST_SETTINGS_DELAY_MS", "0") or 0),
            )
        QTimer.singleShot(delay_ms, lambda: _inspect_settings_case(case))
    except Exception as exc:
        _exit_active_settings_exec()
        base._error("{}-activate".format(case.get("id", "settings")), exc)


def _global_rect(widget: QWidget) -> QRect:
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def _attribute_path(root: object, path: str) -> object | None:
    value: object | None = root
    for part in path.split("."):
        if value is None or not hasattr(value, part):
            return None
        value = getattr(value, part)
    return value


def _target_item_index(view: QAbstractItemView, selector: object) -> Any:
    model = view.model()
    if model is None or model.rowCount() <= 0:
        return None
    if selector == "current":
        index = view.currentIndex()
        return index if index.isValid() else None
    if selector == "first":
        row = 0
    elif selector == "last":
        row = model.rowCount() - 1
    elif isinstance(selector, int) and not isinstance(selector, bool):
        row = selector
    else:
        return None
    index = model.index(row, 0)
    return index if index.isValid() else None


def _position_visible_target(dialog: SettingsDialog, case: Mapping[str, Any]) -> None:
    """Place the declaratively named proof target inside its real viewport."""

    def ensure_page_widget(scroll: QScrollArea, widget: QWidget) -> None:
        page = scroll.widget()
        if page is None or not page.isAncestorOf(widget):
            return
        viewport_height = scroll.viewport().height()
        widget_top = widget.mapTo(page, QPoint(0, 0)).y()
        widget_bottom = widget_top + widget.height()
        margin = 12
        bar = scroll.verticalScrollBar()
        if widget.height() + (2 * margin) > viewport_height:
            scroll.ensureWidgetVisible(widget, margin, margin)
        elif widget_top - margin < bar.value():
            bar.setValue(max(bar.minimum(), widget_top - margin))
        elif widget_bottom + margin > bar.value() + viewport_height:
            bar.setValue(
                min(
                    bar.maximum(),
                    widget_bottom + margin - viewport_height,
                )
            )
        QApplication.processEvents()

    target = case.get("visible_target")
    if not isinstance(target, Mapping):
        return
    current = dialog.stack.currentWidget()
    kind = str(target.get("kind", ""))
    scroll_mode = str(target.get("scroll", "nearest"))
    if kind == "active-page" and isinstance(current, QScrollArea):
        bar = current.verticalScrollBar()
        if scroll_mode == "top":
            bar.setValue(bar.minimum())
        elif scroll_mode == "bottom":
            bar.setValue(bar.maximum())
        return
    attribute = str(target.get("attribute", ""))
    resolved = _attribute_path(dialog, attribute) if attribute else None
    if kind == "item" and isinstance(resolved, QAbstractItemView):
        if isinstance(current, QScrollArea):
            ensure_page_widget(current, resolved)
        index = _target_item_index(resolved, target.get("item"))
        if index is not None:
            hint = QAbstractItemView.ScrollHint.EnsureVisible
            if scroll_mode == "top":
                hint = QAbstractItemView.ScrollHint.PositionAtTop
            elif scroll_mode == "bottom":
                hint = QAbstractItemView.ScrollHint.PositionAtBottom
            resolved.scrollTo(index, hint)
            QApplication.processEvents()
        if isinstance(current, QScrollArea):
            ensure_page_widget(current, resolved)
        return
    if isinstance(resolved, QWidget) and isinstance(current, QScrollArea):
        ensure_page_widget(current, resolved)


def _visible_target_state(
    dialog: SettingsDialog,
    case: Mapping[str, Any],
) -> dict[str, Any]:
    target = case.get("visible_target")
    if not isinstance(target, Mapping):
        return {"declared": False, "fully_visible": False}
    current = dialog.stack.currentWidget()
    kind = str(target.get("kind", ""))
    widget: QWidget | None = None
    target_rect = QRect()
    container_rect = QRect()
    resolved_item_row: int | None = None
    elision_fallback_available = False
    target_text_elided = False
    if kind == "active-page" and isinstance(current, QScrollArea):
        widget = current.viewport()
        target_rect = _global_rect(widget)
        container_rect = QRect(target_rect)
    elif kind == "dialog":
        widget = dialog
        target_rect = dialog.frameGeometry()
        available = _settings_screen(dialog).availableGeometry()
        container_rect = QRect(available)
    elif kind == "prompt":
        active_prompt = getattr(dialog, "_active_prompt", None)
        widget = (
            active_prompt
            if isinstance(active_prompt, QWidget)
            and active_prompt.isVisibleTo(dialog)
            else None
        )
    else:
        resolved = _attribute_path(dialog, str(target.get("attribute", "")))
        widget = resolved if isinstance(resolved, QWidget) else None
        if kind == "item" and isinstance(widget, QAbstractItemView):
            index = _target_item_index(widget, target.get("item"))
            if index is not None:
                resolved_item_row = index.row()
                tooltip = index.data(Qt.ItemDataRole.ToolTipRole)
                elision_fallback_available = bool(str(tooltip or "").strip())
                index_widget_getter = getattr(widget, "indexWidget", None)
                index_widget = (
                    index_widget_getter(index)
                    if callable(index_widget_getter)
                    else None
                )
                if isinstance(index_widget, QWidget):
                    elision_labels = [
                        label
                        for label in index_widget.findChildren(QLabel)
                        if hasattr(label, "_full_text")
                    ]
                    elision_fallback_available = (
                        elision_fallback_available
                        or any(
                            bool(label.toolTip().strip())
                            or str(getattr(label, "_full_text", ""))
                            == str(label.text())
                            for label in elision_labels
                        )
                    )
                    target_text_elided = any(
                        bool(label.toolTip().strip())
                        for label in elision_labels
                    )
                local_rect = widget.visualRect(index)
                target_rect = QRect(
                    widget.viewport().mapToGlobal(local_rect.topLeft()),
                    local_rect.size(),
                )
                container_rect = _global_rect(widget.viewport())
    if widget is not None and target_rect.isNull():
        target_rect = (
            widget.frameGeometry()
            if kind == "editor" and widget.isWindow()
            else _global_rect(widget)
        )
    if widget is not None and container_rect.isNull():
        page = current.widget() if isinstance(current, QScrollArea) else None
        if page is not None and (page is widget or page.isAncestorOf(widget)):
            container_rect = _global_rect(current.viewport())
        elif kind == "editor":
            container_rect = dialog.frameGeometry()
        else:
            container_rect = _global_rect(dialog)
    visible = bool(
        widget is not None
        and widget.isVisible()
        and not target_rect.isNull()
        and target_rect.width() > 0
        and target_rect.height() > 0
    )
    page_container_rect = QRect()
    container_inside_page = True
    page = current.widget() if isinstance(current, QScrollArea) else None
    if (
        widget is not None
        and page is not None
        and (page is widget or page.isAncestorOf(widget))
    ):
        page_container_rect = _global_rect(current.viewport())
        container_inside_page = bool(
            container_rect.left() >= page_container_rect.left() - 1
            and container_rect.top() >= page_container_rect.top() - 1
            and container_rect.right() <= page_container_rect.right() + 1
            and container_rect.bottom() <= page_container_rect.bottom() + 1
        )
    fully_visible = bool(
        visible
        and not container_rect.isNull()
        and target_rect.left() >= container_rect.left() - 1
        and target_rect.top() >= container_rect.top() - 1
        and target_rect.right() <= container_rect.right() + 1
        and target_rect.bottom() <= container_rect.bottom() + 1
        and container_inside_page
    )
    return {
        "declared": True,
        "spec": dict(target),
        "kind": kind,
        "resolved": widget is not None,
        "visible": visible,
        "fully_visible": fully_visible,
        "target_rect": [
            target_rect.x(),
            target_rect.y(),
            target_rect.width(),
            target_rect.height(),
        ],
        "container_rect": [
            container_rect.x(),
            container_rect.y(),
            container_rect.width(),
            container_rect.height(),
        ],
        "page_viewport_rect": [
            page_container_rect.x(),
            page_container_rect.y(),
            page_container_rect.width(),
            page_container_rect.height(),
        ],
        "container_inside_page_viewport": container_inside_page,
        "resolved_item_row": resolved_item_row,
        "allow_elision": bool(target.get("allow_elision", False)),
        "elision_fallback_available": elision_fallback_available,
        "text_elided": target_text_elided,
    }


def _visible_interactive_overflow(
    dialog: SettingsDialog,
    current: Any,
) -> list[str]:
    if not isinstance(current, QScrollArea) or current.widget() is None:
        return []
    viewport_rect = _global_rect(current.viewport())
    interactive_types = (
        QAbstractButton,
        QAbstractItemView,
        QComboBox,
        QLineEdit,
        QSlider,
        QSpinBox,
    )
    failures: list[str] = []
    content = current.widget()
    vertical_scroll = current.verticalScrollBar()
    for widget in current.widget().findChildren(QWidget):
        if not isinstance(widget, interactive_types) or not widget.isVisibleTo(dialog):
            continue
        rect = _global_rect(widget)
        if rect.bottom() < viewport_rect.top() or rect.top() > viewport_rect.bottom():
            continue
        label = widget.accessibleName() or widget.objectName() or type(widget).__name__
        horizontally_escaped = (
            rect.left() < viewport_rect.left() - 1
            or rect.right() > viewport_rect.right() + 1
        )
        vertically_clipped = (
            rect.top() < viewport_rect.top() - 1
            or rect.bottom() > viewport_rect.bottom() + 1
        )
        # The page body is intentionally scrollable, so a control may meet the
        # viewport's top or bottom edge while the user scrolls.  Permit that
        # only when the vertical-only page scroller can place the entire
        # control inside the viewport.  Horizontal escape is never recoverable.
        vertically_reachable = True
        if vertically_clipped:
            content_origin = widget.mapTo(content, QPoint(0, 0))
            content_top = content_origin.y()
            content_bottom = content_top + widget.height()
            minimum_scroll = max(0, content_bottom - current.viewport().height())
            maximum_scroll = min(vertical_scroll.maximum(), content_top)
            vertically_reachable = bool(
                vertical_scroll.maximum() > 0
                and widget.height() <= current.viewport().height()
                and minimum_scroll <= maximum_scroll + 1
            )
        if horizontally_escaped or not vertically_reachable:
            failures.append(str(label))
    return failures


def _clipped_button_labels(dialog: SettingsDialog) -> list[str]:
    failures: list[str] = []
    for button in dialog.findChildren(QAbstractButton):
        text = str(button.text()).replace("&", "").strip()
        if not text or not button.isVisibleTo(dialog):
            continue
        required = button.fontMetrics().horizontalAdvance(text) + 16
        if button.width() + 1 < required:
            failures.append(text)
    return failures


def _clipped_plain_labels(dialog: SettingsDialog) -> list[str]:
    failures: list[str] = []
    for label in dialog.findChildren(QLabel):
        text = str(label.text()).strip()
        if (
            not text
            or not label.isVisibleTo(dialog)
            or label.wordWrap()
            or bool(label.property("hdoAllowElision"))
            or label.textFormat() == Qt.TextFormat.RichText
            or ("<" in text and ">" in text)
        ):
            continue
        if label.fontMetrics().horizontalAdvance(text) > label.contentsRect().width() + 1:
            failures.append(label.accessibleName() or label.objectName() or text[:48])
    return failures


def _clipped_wrapped_labels(dialog: SettingsDialog) -> list[str]:
    """Detect wrapped copy whose layout height does not contain its text."""

    failures: list[str] = []
    for label in dialog.findChildren(QLabel):
        text = str(label.text()).strip()
        if (
            not text
            or not label.isVisibleTo(dialog)
            or not label.wordWrap()
            or bool(label.property("hdoAllowElision"))
            or label.textFormat() == Qt.TextFormat.RichText
            or ("<" in text and ">" in text)
        ):
            continue
        # QLabel.heightForWidth() accounts for stylesheet padding when it is
        # given the widget width. Comparing it with contentsRect() counts that
        # padding twice and falsely reports fully visible banners as clipped.
        width = max(1, label.width())
        required_height = label.heightForWidth(width)
        if required_height > label.height() + 1:
            identifier = (
                label.accessibleName()
                or text[:48]
                or label.objectName()
            )
            failures.append(
                "{} ({}x{}, needs {}px)".format(
                    identifier,
                    label.width(),
                    label.height(),
                    required_height,
                )
            )
    return failures


def _segmented_model_failures(dialog: SettingsDialog) -> list[str]:
    failures: list[str] = []
    values = dialog.draft.values
    model_values = {
        "mode": str(values.get("appearance", {}).get("mode", "auto")),
        "calendar_view": str(
            values.get("heatmap", {}).get("calendar_view", "year")
        ),
        "week_start": str(values.get("heatmap", {}).get("week_start", 0)),
        "rotation": str(
            values.get("bible", {}).get("rotation_mode", "daily")
        ),
        "theme_color": (
            "theme"
            if bool(values.get("bible", {}).get("theme_aware_color", True))
            else "custom"
        ),
    }
    for control in dialog.findChildren(QWidget):
        if type(control).__name__ != "SegmentedControl" or not control.isVisibleTo(dialog):
            continue
        buttons = getattr(control, "_buttons", None)
        value_getter = getattr(control, "value", None)
        if not isinstance(buttons, Mapping) or not callable(value_getter):
            failures.append(control.accessibleName() or "SegmentedControl")
            continue
        checked = [
            (str(value), button)
            for value, button in buttons.items()
            if isinstance(button, QAbstractButton) and button.isChecked()
        ]
        current = str(value_getter(""))
        attribute = next(
            (
                name
                for name in model_values
                if getattr(dialog, name, None) is control
            ),
            "",
        )
        expected = model_values.get(attribute)
        if (
            len(checked) != 1
            or checked[0][0] != current
            or expected is None
            or current != expected
        ):
            failures.append(
                "{} (widget={}, model={})".format(
                    control.accessibleName() or "SegmentedControl",
                    current,
                    expected,
                )
            )
    return failures


def _minimum_visible_text_pixels(dialog: SettingsDialog, screen: Any) -> float:
    values: list[float] = []
    for widget in dialog.findChildren(QWidget):
        if not widget.isVisibleTo(dialog):
            continue
        text_getter = getattr(widget, "text", None)
        text = str(text_getter()) if callable(text_getter) else ""
        if not text.strip():
            continue
        font = widget.font()
        if font.pixelSize() > 0:
            values.append(float(font.pixelSize()))
        elif font.pointSizeF() > 0:
            values.append(float(font.pointSizeF()) * float(screen.logicalDotsPerInchY()) / 72.0)
    return min(values) if values else 0.0


def _editor_state(editor: object, settings_dialog: SettingsDialog) -> dict[str, Any]:
    if not isinstance(editor, QWidget):
        return {
            "open": False,
            "window_title": "",
            "explicit_header_count": 0,
            "explicit_header_texts": [],
            "window_modal": False,
            "application_modal": False,
            "modal": False,
            "parented_to_settings": False,
            "size": [],
            "native_frame_decoration": {"width": 0, "height": 0},
            "required_fields_visible": False,
        }
    title = str(editor.windowTitle())
    frame = editor.frameGeometry()
    header = getattr(editor, "header", None)
    explicit_header_texts = [
        str(label.text()).strip()
        for label in (
            header.findChildren(QLabel)
            if isinstance(header, QWidget)
            else []
        )
        if label.objectName() == "PageTitle"
        and label.isVisibleTo(editor)
        and str(label.text()).strip()
    ]
    return {
        "open": editor.isVisible(),
        "window_title": title,
        "explicit_header_count": len(explicit_header_texts),
        "explicit_header_texts": explicit_header_texts,
        "window_modal": (
            editor.windowModality() == Qt.WindowModality.WindowModal
        ),
        "application_modal": (
            editor.windowModality() == Qt.WindowModality.ApplicationModal
        ),
        "modal": editor.isModal(),
        "parented_to_settings": editor.parentWidget() is settings_dialog,
        "size": [editor.width(), editor.height()],
        "required_fields_visible": all(
            widget.isVisibleTo(editor)
            and _global_rect(editor.scroll.viewport()).contains(_global_rect(widget))
            for widget in (
                (editor.name, editor.date)
                if isinstance(editor, EventEditDialog)
                else (editor.reference, editor.editor)
            )
        ),
        "native_frame_decoration": {
            "width": max(0, frame.width() - editor.width()),
            "height": max(0, frame.height() - editor.height()),
        },
    }


def _settings_state(dialog: SettingsDialog, case: Mapping[str, Any]) -> dict[str, Any]:
    current = dialog.stack.currentWidget()
    active_tree = getattr(dialog, "active_events", None)
    archived_tree = getattr(dialog, "archived_events", None)
    quote_list = getattr(dialog, "quote_list", None)
    quote_model = getattr(dialog, "quote_model", None)
    settings_screen = _settings_screen(dialog)
    available_geometry = settings_screen.availableGeometry()
    geometry = settings_screen.geometry()
    frame = dialog.frameGeometry()
    client_geometry = dialog.geometry()
    restart_marker = _read_geometry_restart_marker()
    restart_expected_geometry = _rect_payload(
        restart_marker.get("expected_geometry")
    )
    calendar_viewport_y = -1
    calendar_anchor = getattr(dialog, "dashboard_anchors", {}).get("calendar")
    if isinstance(current, QScrollArea) and calendar_anchor is not None:
        calendar_viewport_y = (
            _global_rect(calendar_anchor).top()
            - _global_rect(current.viewport()).top()
        )
    page_layout = current.widget().layout() if isinstance(current, QScrollArea) and current.widget() is not None else None
    page_bottom_margin = page_layout.contentsMargins().bottom() if page_layout is not None else 0
    viewport_rect = _global_rect(current.viewport()) if isinstance(current, QScrollArea) else QRect()
    page_content = current.widget() if isinstance(current, QScrollArea) else None
    page_scroll = current.verticalScrollBar() if isinstance(current, QScrollArea) else None
    page_content_height = page_content.height() if page_content is not None else 0
    page_viewport_height = current.viewport().height() if isinstance(current, QScrollArea) else 0
    page_scroll_maximum = page_scroll.maximum() if page_scroll is not None else -1
    page_scroll_value = page_scroll.value() if page_scroll is not None else -1
    page_bottom_reachable = False
    if page_scroll is not None and page_content is not None:
        page_scroll.setValue(page_scroll.maximum())
        QApplication.processEvents()
        page_bottom_reachable = bool(
            _global_rect(page_content).bottom()
            <= _global_rect(current.viewport()).bottom() + 1
        )
        page_scroll.setValue(page_scroll_value)
        QApplication.processEvents()
    footer_rect = _global_rect(dialog.footer_shell)
    about_item = dialog.nav.item(dialog.nav_rows.get("about_support", -1))
    about_item_height = dialog.nav.visualItemRect(about_item).height() if about_item is not None else 0
    tokens = getattr(dialog, "_hdo_theme_tokens", {})
    status_rect = _global_rect(dialog.status_label) if dialog.status_label.isVisible() else QRect()
    error_rect = _global_rect(dialog.footer.error_panel) if dialog.footer.error_panel.isVisible() else QRect()
    feedback_intersection = status_rect.intersected(error_rect)
    save_rect = _global_rect(dialog.save_button) if dialog.save_button is not None else QRect()
    footer_action_buttons = [
        button
        for button in (
            dialog.revert_button,
            dialog.close_button,
            dialog.save_button,
        )
        if button is not None and button.isVisibleTo(dialog)
    ]
    footer_action_order = [
        button.text().replace("&", "").strip()
        for button in sorted(
            footer_action_buttons,
            key=lambda candidate: _global_rect(candidate).center().x(),
        )
    ]
    prompt_titles = [
        str(label.text())
        for label in dialog.findChildren(QWidget, "SettingsPromptTitle")
        if callable(getattr(label, "text", None)) and label.isVisibleTo(dialog)
    ]
    active_prompt = getattr(dialog, "_active_prompt", None)
    prompt_actions = [
        button.text().replace("&", "").strip()
        for button in (
            active_prompt.findChildren(QAbstractButton)
            if isinstance(active_prompt, QWidget)
            else []
        )
        if button.isVisibleTo(dialog) and button.text().strip()
    ]
    enabled_mutation_controls = [
        widget.accessibleName() or widget.objectName() or type(widget).__name__
        for widget in getattr(dialog, "_mutation_enabled_states", {})
        if widget.isEnabled()
    ]
    shell_rect = QRect(
        dialog.settings_shell.mapTo(dialog, QPoint(0, 0)),
        dialog.settings_shell.size(),
    )
    event_editor = getattr(dialog, "_qa_event_editor", None)
    verse_editor = getattr(dialog, "_qa_verse_editor", None)
    event_editor_state = _editor_state(event_editor, dialog)
    verse_editor_state = _editor_state(verse_editor, dialog)
    heatmap_palette_preview = getattr(dialog, "heatmap_palette_preview", None)
    bible_appearance_preview = getattr(dialog, "bible_appearance_preview", None)
    visible_add_event_ctas = [
        button
        for button in dialog.findChildren(QAbstractButton)
        if button.text().replace("&", "").strip() == "Add event"
        and button.isVisibleTo(dialog)
    ]
    event_header_add_visible = bool(
        hasattr(dialog, "event_add") and dialog.event_add.isVisibleTo(dialog)
    )
    event_toolbar_add_visible = bool(
        hasattr(dialog, "event_toolbar_add")
        and dialog.event_toolbar_add.isVisibleTo(dialog)
    )
    event_row_height = 0
    if active_tree is not None and active_tree.topLevelItemCount():
        event_row_height = active_tree.topLevelItem(0).sizeHint(0).height()
    manual_quote_dirty = (
        dialog.pending_manual_quote is not None
        and dialog.pending_manual_quote != dialog._saved_current_quote
    )
    has_unsaved_changes = bool(
        dialog.draft.dirty
        or manual_quote_dirty
        or getattr(dialog, "_font_color_invalid", False)
        or not dialog._number_fields_are_valid()
    )
    return {
        "section": dialog.current_section,
        "normalized_route": getattr(dialog, "_normalized_route", ""),
        "window_title": dialog.windowTitle(),
        "window_size": [dialog.width(), dialog.height()],
        "window_geometry": [
            client_geometry.x(),
            client_geometry.y(),
            client_geometry.width(),
            client_geometry.height(),
        ],
        "restart_expected_geometry": restart_expected_geometry,
        "restart_geometry_matches": (
            restart_expected_geometry is not None
            and restart_expected_geometry
            == [
                client_geometry.x(),
                client_geometry.y(),
                client_geometry.width(),
                client_geometry.height(),
            ]
        ),
        "minimum_size": [dialog.minimumWidth(), dialog.minimumHeight()],
        "window_maximized": dialog.isMaximized(),
        "available_size": [available_geometry.width(), available_geometry.height()],
        "available_geometry": [available_geometry.x(), available_geometry.y(), available_geometry.width(), available_geometry.height()],
        "screen_geometry": [geometry.x(), geometry.y(), geometry.width(), geometry.height()],
        "screen_physical_pixels": [round(geometry.width() * settings_screen.devicePixelRatio()), round(geometry.height() * settings_screen.devicePixelRatio())],
        "decorated_frame": [frame.x(), frame.y(), frame.width(), frame.height()],
        "native_frame_decoration": {
            "width": max(0, frame.width() - dialog.width()),
            "height": max(0, frame.height() - dialog.height()),
        },
        "screen_name": settings_screen.name(),
        "screen_device_pixel_ratio": settings_screen.devicePixelRatio(),
        "screen_logical_dpi": [settings_screen.logicalDotsPerInchX(), settings_screen.logicalDotsPerInchY()],
        "screen_physical_dpi": [settings_screen.physicalDotsPerInchX(), settings_screen.physicalDotsPerInchY()],
        "host_platform": sys.platform,
        "os_version": platform.platform(),
        "qt_platform": QApplication.platformName(),
        "declared_host_platform": case.get("host_platform"),
        "declared_os_scale_percent": case.get("os_scale_percent"),
        "declared_dpr_class": case.get("dpr_class"),
        "decorated_frame_inside_available": (
            frame.left() >= available_geometry.left() and frame.top() >= available_geometry.top()
            and frame.right() <= available_geometry.right() and frame.bottom() <= available_geometry.bottom()
        ),
        "fixed_size": dialog.minimumSize() == dialog.maximumSize(),
        "parented_to_anki": dialog.parentWidget() is mw,
        "modal_capture_lifecycle": dialog.isModal(),
        "window_modal": dialog.windowModality() == Qt.WindowModality.WindowModal,
        "application_modal": dialog.windowModality() == Qt.WindowModality.ApplicationModal,
        "font_percent": int(case.get("font_percent", 100)),
        "application_font_point_size": QApplication.font().pointSizeF(),
        "minimum_visible_text_pixels": _minimum_visible_text_pixels(dialog, settings_screen),
        "nav_width": dialog.sidebar_panel.width(),
        "nav_visible": dialog.sidebar_panel.isVisible(),
        "compact_nav_visible": dialog.compact_nav.isVisible(),
        "compact_nav_labelled": bool(dialog.compact_nav.accessibleName()),
        "nav_word_wrap": dialog.nav.wordWrap(),
        "nav_elision_disabled": dialog.nav.textElideMode() == Qt.TextElideMode.ElideNone,
        "nav_about_visual_height": about_item_height,
        "nav_font_line_spacing": dialog.nav.fontMetrics().lineSpacing(),
        "body_width": dialog.body_shell.width(),
        "screen_compact_fallback": bool(dialog._screen_compact_fallback),
        "compact_layout": bool(getattr(dialog, "_compact_layout", False)),
        "page_count": dialog.stack.count(),
        "visible_page_scroller_count": sum(
            isinstance(dialog.stack.widget(index), QScrollArea)
            and dialog.stack.widget(index).isVisibleTo(dialog)
            for index in range(dialog.stack.count())
        ),
        "main_page_scroller": isinstance(current, QScrollArea),
        "horizontal_scroll_maximum": current.horizontalScrollBar().maximum() if isinstance(current, QScrollArea) else -1,
        "horizontal_scroll_disabled": isinstance(current, QScrollArea) and current.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        "page_content_height": page_content_height,
        "page_viewport_height": page_viewport_height,
        "page_scroll_maximum": page_scroll_maximum,
        "page_scroll_value": page_scroll_value,
        "page_bottom_reachable": page_bottom_reachable,
        "visible_interactive_overflow": _visible_interactive_overflow(dialog, current),
        "clipped_button_labels": _clipped_button_labels(dialog),
        "clipped_plain_labels": _clipped_plain_labels(dialog),
        "clipped_wrapped_labels": _clipped_wrapped_labels(dialog),
        "segmented_model_failures": _segmented_model_failures(dialog),
        "visible_target": _visible_target_state(dialog, case),
        "body_height": dialog.body_shell.height(),
        "header_height": dialog.header_stack.height(),
        "footer_minimum_height": dialog.footer.minimumHeight(),
        "sidebar_spans_shell": (
            dialog.sidebar_panel.geometry().top() == 0
            and dialog.sidebar_panel.geometry().bottom()
            >= dialog.settings_shell.rect().bottom() - 1
        ),
        "page_maximum_width": (
            current.widget().maximumWidth()
            if isinstance(current, QScrollArea) and current.widget() is not None
            else 0
        ),
        "calendar_anchor_viewport_y": calendar_viewport_y,
        "footer_after_body": dialog.footer_shell.geometry().top() >= dialog.body_shell.geometry().bottom() - 1,
        "footer_overlaps_page_viewport": not viewport_rect.isNull() and footer_rect.top() <= viewport_rect.bottom(),
        "page_bottom_margin": page_bottom_margin,
        "required_page_bottom_margin": 20 if dialog._compact_layout else 24,
        "save_text": dialog.save_button.text() if dialog.save_button is not None else "",
        "save_enabled": dialog.save_button.isEnabled() if dialog.save_button is not None else False,
        "close_text": dialog.close_button.text() if dialog.close_button is not None else "",
        "close_enabled": dialog.close_button.isEnabled() if dialog.close_button is not None else False,
        "discard_visible": dialog.revert_button.isVisible(),
        "discard_enabled": dialog.revert_button.isEnabled(),
        "has_unsaved_changes": has_unsaved_changes,
        "expected_unsaved_count": (
            dialog.draft.changed_leaf_count + (1 if manual_quote_dirty else 0)
        ),
        "save_error_visible": dialog.footer.error_panel.isVisible(),
        "save_error_text": dialog.save_error.text(),
        "save_error_label_clipped": (
            dialog.footer.error_panel.isVisible()
            and (
                (
                    dialog.save_error.wordWrap()
                    and dialog.save_error.heightForWidth(
                        max(1, dialog.save_error.contentsRect().width())
                    )
                    > dialog.save_error.contentsRect().height() + 1
                )
                or (
                    not dialog.save_error.wordWrap()
                    and dialog.save_error.fontMetrics().horizontalAdvance(
                        dialog.save_error.text()
                    )
                    > dialog.save_error.contentsRect().width()
                )
            )
        ),
        "save_error_details": dialog.footer.details_text.text(),
        "save_error_details_collapsed": not dialog.footer.details_text.isVisible(),
        "save_error_actions": [
            button.text().replace("&", "").strip()
            for button in (
                dialog.footer.details_button,
                dialog.footer.copy_error_button,
            )
            if button.isVisibleTo(dialog)
        ],
        "status": dialog.status_label.text(),
        "status_visible": dialog.status_label.isVisible(),
        "status_indicator_state": str(dialog.footer.status_icon._state),
        "status_indicator_timer_active": dialog.footer.status_icon._timer.isActive(),
        "visible_status_indicator_count": sum(
            type(widget).__name__ == "SettingsStatusIndicator"
            and widget.isVisibleTo(dialog)
            for widget in dialog.findChildren(QWidget)
        ),
        "footer_action_order": footer_action_order,
        "footer_feedback_exclusive": not (
            dialog.status_label.isVisible()
            and dialog.footer.error_panel.isVisible()
        ),
        "footer_feedback_overlap_area": max(0, feedback_intersection.width())
        * max(0, feedback_intersection.height()),
        "status_and_save_inside_footer": (
            (status_rect.isNull() or footer_rect.contains(status_rect))
            and (save_rect.isNull() or footer_rect.contains(save_rect))
        ),
        "failure_baseline_retained": (
            not hasattr(dialog, "_qa_failure_baseline_before")
            or dialog.draft.baseline == dialog._qa_failure_baseline_before
        ),
        "failure_values_retained": (
            not hasattr(dialog, "_qa_failure_values_before")
            or dialog.draft.values == dialog._qa_failure_values_before
        ),
        "failure_manual_retained": (
            not hasattr(dialog, "_qa_failure_manual_before")
            or dialog.pending_manual_quote == dialog._qa_failure_manual_before
        ),
        "failure_event_stage_retained": (
            not hasattr(dialog, "_qa_failure_events_before")
            or dialog.staged["events"]["items"]
            == dialog._qa_failure_events_before
        ),
        "event_active_count": active_tree.topLevelItemCount() if active_tree is not None else 0,
        "event_archived_count": archived_tree.topLevelItemCount() if archived_tree is not None else 0,
        "event_tab": dialog.event_tabs.currentIndex() if hasattr(dialog, "event_tabs") else -1,
        "event_search": dialog.event_search.text() if hasattr(dialog, "event_search") else "",
        "event_sort": (
            str(dialog.event_sort.currentData() or "")
            if hasattr(dialog, "event_sort")
            else ""
        ),
        "calendar_view": (
            dialog.calendar_view.value("")
            if hasattr(dialog, "calendar_view")
            else ""
        ),
        "appearance_preset": (
            str(dialog.preset.currentData() or "")
            if hasattr(dialog, "preset")
            else ""
        ),
        "heatmap_preset": str(
            getattr(dialog, "_heatmap_preset_preferences", {}).get(
                "Graphite", ""
            )
        ),
        "event_result_summary": dialog.event_result_summary.text() if hasattr(dialog, "event_result_summary") else "",
        "event_empty_title": dialog.event_empty_title.text() if hasattr(dialog, "event_empty_title") and dialog.event_empty_state.isVisible() else "",
        "event_editor_open": event_editor_state["open"],
        "event_editor_title": event_editor_state["window_title"],
        "event_editor_explicit_header_count": event_editor_state[
            "explicit_header_count"
        ],
        "event_editor_explicit_header_texts": event_editor_state[
            "explicit_header_texts"
        ],
        "event_editor_window_modal": event_editor_state["window_modal"],
        "event_editor_application_modal": event_editor_state[
            "application_modal"
        ],
        "event_editor_modal": event_editor_state["modal"],
        "event_editor_parented_to_settings": event_editor_state[
            "parented_to_settings"
        ],
        "event_editor_size": event_editor_state["size"],
        "event_editor_fields_visible": event_editor_state["required_fields_visible"],
        "verse_editor_fields_visible": verse_editor_state["required_fields_visible"],
        "event_editor_native_frame_decoration": event_editor_state[
            "native_frame_decoration"
        ],
        "verse_editor_open": verse_editor_state["open"],
        "verse_editor_title": verse_editor_state["window_title"],
        "verse_editor_explicit_header_count": verse_editor_state[
            "explicit_header_count"
        ],
        "verse_editor_explicit_header_texts": verse_editor_state[
            "explicit_header_texts"
        ],
        "verse_editor_window_modal": verse_editor_state["window_modal"],
        "verse_editor_application_modal": verse_editor_state[
            "application_modal"
        ],
        "verse_editor_modal": verse_editor_state["modal"],
        "verse_editor_parented_to_settings": verse_editor_state[
            "parented_to_settings"
        ],
        "verse_editor_size": verse_editor_state["size"],
        "verse_editor_native_frame_decoration": verse_editor_state[
            "native_frame_decoration"
        ],
        "verse_editor_body": (
            verse_editor.editor.toPlainText()
            if verse_editor is not None
            else ""
        ),
        "verse_editor_reference": (
            verse_editor.reference.text()
            if verse_editor is not None
            else ""
        ),
        "event_lists_bounded": all(
            view is None
            or view.topLevelItemCount() == 0
            or (
                view.minimumHeight() == view.maximumHeight()
                and 50 <= view.maximumHeight() <= (5 * 60) + 4
            )
            for view in (active_tree, archived_tree)
        ),
        "event_list_scroll_policy": all(
            view is None
            or view.verticalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAsNeeded
            for view in (active_tree, archived_tree)
        ),
        "visible_add_event_cta_count": len(visible_add_event_ctas),
        "event_header_add_visible": event_header_add_visible,
        "event_toolbar_add_visible": event_toolbar_add_visible,
        "event_empty_height": (
            dialog.event_empty_state.height()
            if hasattr(dialog, "event_empty_state")
            and dialog.event_empty_state.isVisible()
            else 0
        ),
        "event_row_height": event_row_height,
        "event_active_scroll_maximum": (
            active_tree.verticalScrollBar().maximum()
            if active_tree is not None
            else 0
        ),
        "quote_count": quote_model.rowCount() if quote_model is not None else 0,
        "quote_matching_count": quote_model.matching_count if quote_model is not None else 0,
        "quote_list_bounded": quote_list is None or (
            not quote_list.isVisibleTo(dialog)
            or (quote_list.height() >= 68
                and all(_global_rect(current.viewport()).contains(_global_rect(widget))
                        for widget in (quote_list, dialog.quote_search, dialog.quote_add,
                                       dialog.quote_actions, dialog.quote_current_actions)))
        ),
        "quote_list_scroll_policy": (
            quote_list is None
            or quote_list.verticalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        ),
        "font_color_invalid": bool(getattr(dialog, "_font_color_invalid", False)),
        "font_color_inline_error": (
            dialog.font_color_warning.text()
            if hasattr(dialog, "font_color_warning")
            and dialog.font_color_warning.isVisible()
            else ""
        ),
        "forecast_range_visible": bool(
            getattr(dialog, "forecast_days", None)
            and not dialog.forecast_days.isHidden()
        ),
        "forecast_range_enabled": bool(
            getattr(dialog, "forecast_days", None)
            and dialog.forecast_days.isEnabled()
        ),
        "advanced_appearance_expanded": bool(getattr(dialog, "appearance_advanced_button", None) and dialog.appearance_advanced_button.isChecked()),
        "close_prompt_titles": prompt_titles,
        "close_prompt_actions": prompt_actions,
        "enabled_mutation_controls_while_saving": enabled_mutation_controls,
        "settings_shell_maximum": dialog.settings_shell.maximumWidth(),
        "settings_shell_width": dialog.settings_shell.width(),
        "settings_shell_center_delta": abs(
            shell_rect.center().x() - dialog.rect().center().x()
        ),
        "settings_previews": {
            "heatmap_palette_present": (
                heatmap_palette_preview is not None
                and type(heatmap_palette_preview).__name__
                == "HeatmapPalettePreview"
            ),
            "heatmap_palette_steps": len(
                getattr(heatmap_palette_preview, "_colors", ())
            ),
            "heatmap_palette_compact": (
                heatmap_palette_preview is not None
                and heatmap_palette_preview.minimumHeight() == 34
                and heatmap_palette_preview.maximumWidth() == 168
            ),
            "bible_appearance_present": (
                bible_appearance_preview is not None
                and type(bible_appearance_preview).__name__
                == "BibleAppearancePreview"
            ),
            "bible_appearance_complete": (
                bible_appearance_preview is not None
                and bool(getattr(bible_appearance_preview, "body", None))
                and bool(getattr(bible_appearance_preview, "reference", None))
                and bool(bible_appearance_preview.body.text().strip())
                and bool(bible_appearance_preview.reference.text().strip())
            ),
        },
        "custom_color_well_present": hasattr(dialog, "font_color_swatch"),
        "anki_theme": getattr(dialog, "_qa_anki_theme", ""),
        "settings_window_token": tokens.get("window", ""),
        "selection_primary_contrast": contrast_ratio(tokens.get("text", "#000000"), tokens.get("accent_soft", "#FFFFFF")),
        "selection_secondary_contrast": contrast_ratio(tokens.get("secondary", "#000000"), tokens.get("accent_soft", "#FFFFFF")),
    }


def _validate_settings_state(case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    special = str(case.get("special", ""))
    base._require(state.get("window_title") == "Home Screen Dashboard Settings", "Settings window title is incorrect")
    if not bool(state.get("screen_compact_fallback")):
        base._require(state.get("minimum_size") == [860, 640], "Settings minimum size is not 860x640 logical px")
    base._require(state.get("nav_width") == 184, "Settings rail is not 184px")
    base._require(not bool(state.get("nav_word_wrap")), "Settings rail wraps labels")
    base._require(bool(state.get("nav_elision_disabled")), "Settings rail elides long labels")
    base._require(bool(state.get("compact_nav_labelled")), "compact Settings selector lacks a label")
    compact_required = bool(state.get("compact_layout"))
    if special != "close-confirmation":
        if compact_required:
            base._require(bool(state.get("compact_nav_visible")), "compact navigation did not replace the rail")
            base._require(not bool(state.get("nav_visible")), "desktop rail remains visible in compact mode")
        else:
            base._require(
                bool(state.get("nav_visible")) != bool(state.get("compact_nav_visible")),
                "Settings navigation has zero or two visible representations",
            )
    if bool(state.get("nav_visible")):
        expected_single_line_height = max(
            36,
            int(state.get("nav_font_line_spacing", 0)) + 12,
        )
        base._require(
            abs(
                int(state.get("nav_about_visual_height", 0))
                - expected_single_line_height
            )
            <= 2,
            "About & support wrapped in the desktop rail",
        )
    base._require(state.get("page_count") == 6, "Settings does not own exactly six pages")
    # The in-window prompt deliberately leaves the shell visible beneath its
    # scrim, so the active page retains its single body scroller.
    expected_visible_scrollers = 1
    base._require(
        state.get("visible_page_scroller_count") == expected_visible_scrollers,
        "Settings does not expose exactly the expected page-body scroller count",
    )
    visible_target = state.get("visible_target", {})
    if bool(visible_target.get("allow_elision")):
        base._require(
            bool(visible_target.get("elision_fallback_available")),
            "approved target elision has no full-text tooltip or editor path",
        )
    base._require(bool(state.get("main_page_scroller")), "active Settings page is not the main scroller")
    base._require(state.get("horizontal_scroll_maximum") == 0, "Settings page has horizontal overflow")
    base._require(bool(state.get("horizontal_scroll_disabled")), "Settings page permits horizontal scrolling")
    base._require(not state.get("visible_interactive_overflow"), "visible Settings controls escape the content viewport: {}".format(state.get("visible_interactive_overflow")))
    base._require(not state.get("clipped_button_labels"), "Settings buttons clip text: {}".format(state.get("clipped_button_labels")))
    base._require(not state.get("clipped_plain_labels"), "Settings labels clip without an approved elision policy: {}".format(state.get("clipped_plain_labels")))
    base._require(not state.get("clipped_wrapped_labels"), "wrapped Settings labels clip vertically: {}".format(state.get("clipped_wrapped_labels")))
    base._require(not state.get("segmented_model_failures"), "Settings segmented selection differs from its model: {}".format(state.get("segmented_model_failures")))
    base._require(
        isinstance(visible_target, Mapping)
        and visible_target.get("spec") == case.get("visible_target")
        and bool(visible_target.get("fully_visible")),
        "declared Settings proof target is not fully visible: {}".format(
            visible_target
        ),
    )
    if special != "close-confirmation":
        base._require(bool(state.get("footer_after_body")), "Settings footer is not the final layout row")
        base._require(not bool(state.get("footer_overlaps_page_viewport")), "Settings footer overlaps the active page viewport")
    base._require(
        int(state.get("page_bottom_margin", 0)) >= int(state.get("required_page_bottom_margin", 0)),
        "Settings page lacks footer-height bottom clearance",
    )
    base._require(state.get("close_text") == "Close", "Close button label is unstable")
    if (
        not bool(state.get("has_unsaved_changes"))
        and special not in {"discard", "save-success"}
    ):
        base._require(
            state.get("save_text") == "Save changes"
            and not bool(state.get("save_enabled"))
            and not bool(state.get("discard_visible"))
            and not bool(state.get("status_visible")),
            "clean Settings does not expose only Close and disabled Save changes",
        )
    if bool(state.get("discard_visible")):
        base._require(
            state.get("footer_action_order")
            == ["Discard changes", "Close", state.get("save_text")],
            "Settings footer actions are out of order: {}".format(
                state.get("footer_action_order")
            ),
        )
    base._require(state.get("header_height") == 72, "Settings page header is not fixed at 72px")
    base._require(state.get("footer_minimum_height") == 56, "Settings footer is not fixed at a 56px minimum")
    if special != "close-confirmation" and bool(state.get("nav_visible")):
        base._require(bool(state.get("sidebar_spans_shell")), "Settings sidebar does not span header body and footer")
    expected_page_maximum = 1080
    base._require(state.get("page_maximum_width") == expected_page_maximum, "Settings page cap differs from the approved responsive contract")
    base._require(state.get("settings_shell_maximum") == 1264, "Settings inner shell is not capped at 1264px")
    expected_shell_width = min(int(state.get("window_size", [0])[0]), 1264)
    if special != "close-confirmation":
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
    base._require(bool(state.get("status_and_save_inside_footer")), "Settings feedback is not local to the footer actions")
    base._require(bool(state.get("footer_feedback_exclusive")), "Settings status and save-error feedback are visible together")
    base._require(int(state.get("footer_feedback_overlap_area", 0)) == 0, "Settings footer feedback overlaps")
    base._require(
        float(state.get("minimum_visible_text_pixels", 0)) >= 10.0,
        "visible Settings text falls below the 10px shipping minimum",
    )
    base._require(float(state.get("selection_primary_contrast", 0)) >= 4.5, "selected-row primary text contrast is insufficient")
    base._require(float(state.get("selection_secondary_contrast", 0)) >= 4.5, "selected-row secondary text contrast is insufficient")
    base._require(bool(state.get("event_lists_bounded")), "Events list does not auto-size for one through five rows")
    base._require(bool(state.get("event_list_scroll_policy")), "Events list does not scroll only when needed")
    base._require(bool(state.get("quote_list_bounded")), "Verse list escaped the Library viewport")
    base._require(bool(state.get("quote_list_scroll_policy")), "Verse list does not use bounded internal scrolling")
    previews = state.get("settings_previews", {})
    base._require(
        isinstance(previews, Mapping)
        and previews.get("heatmap_palette_present") is True
        and previews.get("heatmap_palette_steps") == 5
        and previews.get("heatmap_palette_compact") is True,
        "the compact five-step Calendar heatmap palette preview is incomplete",
    )
    base._require(
        isinstance(previews, Mapping)
        and previews.get("bible_appearance_present") is True
        and previews.get("bible_appearance_complete") is True,
        "the compact Bible appearance preview is incomplete",
    )
    base._require(bool(state.get("custom_color_well_present")), "the custom color input well is missing")
    if special == "events-empty":
        base._require(state.get("event_active_count") == 0 and state.get("event_archived_count") == 0, "empty Events state is populated")
        base._require(state.get("event_empty_title") == "No events yet", "empty Events copy is incorrect")
        base._require(150 <= int(state.get("event_empty_height", 0)) <= 200, "empty Events state is not compact")
        base._require(state.get("visible_add_event_cta_count") == 1, "empty Events state does not expose exactly one Add event action")
        base._require(state.get("event_header_add_visible") is False, "empty Events state exposes a duplicate page-header Add event action")
        base._require(state.get("event_toolbar_add_visible") is False, "empty Events state exposes the populated-list Add event action")
    if state.get("section") == "events":
        if special != "events-empty":
            base._require(state.get("visible_add_event_cta_count") == 1, "populated Events does not expose exactly one list-toolbar Add event action")
            base._require(state.get("event_header_add_visible") is False, "populated Events still exposes the empty-state-only header Add event action")
            base._require(state.get("event_toolbar_add_visible") is True, "populated Events hides its list-toolbar Add event action")
        if int(state.get("event_active_count", 0)):
            base._require(50 <= int(state.get("event_row_height", 0)) <= 56, "Event rows escaped their compact 52px target")
    if special == "events-populated":
        base._require(state.get("event_active_count") == 2, "populated Events state is incomplete")
    if special == "event-editor-open":
        base._require(bool(state.get("event_editor_open")), "event row did not open its editor")
        base._require(bool(state.get("event_editor_fields_visible")), "event name or date is clipped")
        base._require(
            state.get("event_editor_title") == "Edit event"
            and state.get("event_editor_explicit_header_count") == 1
            and state.get("event_editor_explicit_header_texts")
            == ["Edit event"],
            "event editor lacks its stable native title or one explicit internal header",
        )
        base._require(
            bool(state.get("event_editor_window_modal"))
            and bool(state.get("event_editor_modal"))
            and not bool(state.get("event_editor_application_modal"))
            and bool(state.get("event_editor_parented_to_settings")),
            "event editor is not a parented WindowModal dialog",
        )
        editor_size = state.get("event_editor_size", [0, 0])
        base._require(
            480 <= int(editor_size[0]) <= 540
            and 280 <= int(editor_size[1]) <= 360,
            "event editor escaped its compact responsive bounds",
        )
    if special == "events-searched":
        base._require(state.get("event_search") == "Pediatrics" and state.get("event_active_count") == 1, "Events search state is incorrect")
        base._require(state.get("event_result_summary") == "1 matching event", "Events result summary is incorrect")
    if special == "events-no-results":
        base._require(state.get("event_search") == "Pediatrics" and state.get("event_active_count") == 0, "Events no-results search is incorrect")
        base._require(state.get("event_empty_title") == "No events match “Pediatrics”.", "Events no-results copy is incorrect")
    if special == "events-archived":
        base._require(state.get("event_tab") == 1 and state.get("event_archived_count") == 1, "Archived Events state is incorrect")
    if special in {"bible-short", "bible-long", "bible-custom-valid"}:
        base._require(state.get("quote_count") == 1, "Bible fixture did not render one compact row")
    if special == "bible-long":
        base._require(bool(state.get("verse_editor_open")), "long verse did not open its editor")
        base._require(bool(state.get("verse_editor_fields_visible")), "verse reference or body is clipped")
        base._require(
            state.get("verse_editor_title") == "Edit verse"
            and state.get("verse_editor_explicit_header_count") == 1
            and state.get("verse_editor_explicit_header_texts")
            == ["Edit verse"],
            "verse editor lacks its stable native title or one explicit internal header",
        )
        base._require(
            bool(state.get("verse_editor_window_modal"))
            and bool(state.get("verse_editor_modal"))
            and not bool(state.get("verse_editor_application_modal"))
            and bool(state.get("verse_editor_parented_to_settings")),
            "verse editor is not a parented WindowModal dialog",
        )
        base._require(
            len(str(state.get("verse_editor_body", ""))) > 120
            and state.get("verse_editor_reference") == "Proverbs 3:5-6 (NLT)",
            "verse editor does not visibly expose separate long Body and Reference fields",
        )
    if special == "bible-custom-valid":
        warning = str(state.get("font_color_inline_error", ""))
        base._require(
            warning
            == "This color is difficult to read on the current dark dashboard. Choose a lighter color or keep it anyway.",
            "low-contrast warning is not concise and user-facing",
        )
    if special == "bible-custom-invalid":
        base._require(bool(state.get("font_color_invalid")), "invalid custom color was accepted")
        base._require(not bool(state.get("save_enabled")), "invalid custom color did not block Save")
        base._require(not bool(state.get("save_error_visible")), "invalid custom color duplicates its inline error in the footer")
        base._require(state.get("font_color_inline_error") == "Enter a valid #RRGGBB color.", "invalid custom color lacks the single inline validation error")
        base._require(state.get("status") == "Fix 1 error to save", "footer validation status is incorrect")
    if special == "bible-long-row":
        base._require(state.get("quote_count") == 483, "complete verse model was capped")
        target = state.get("visible_target", {})
        base._require(
            isinstance(target, Mapping)
            and target.get("resolved_item_row") == 482
            and bool(target.get("fully_visible")),
            "the final long verse row is not fully visible above the footer",
        )
    if special == "future-off":
        base._require(bool(state.get("forecast_range_visible")), "Future range moved when forecasting was disabled")
        base._require(not bool(state.get("forecast_range_enabled")), "Future range remains enabled while forecasting is off")
        base._require(
            bool(state.get("visible_target", {}).get("fully_visible")),
            "disabled Future range is not visible in its assigned capture",
        )
    if special == "future-on":
        base._require(bool(state.get("forecast_range_visible")), "Future range is hidden while forecasting is on")
        base._require(bool(state.get("forecast_range_enabled")), "Future range is disabled while forecasting is on")
        base._require(
            bool(state.get("visible_target", {}).get("fully_visible")),
            "enabled Future range is not visible in its assigned capture",
        )
    if special == "advanced-appearance":
        base._require(bool(state.get("advanced_appearance_expanded")), "Advanced appearance did not expand")
        base._require(
            state.get("appearance_preset") == "Sapphire Glass",
            "Advanced appearance is not visibly bound to Sapphire Glass",
        )
    if special == "event-long-title":
        target = state.get("visible_target", {})
        base._require(
            state.get("window_size", [0, 0])[0] == 860
            and bool(state.get("nav_visible"))
            and not bool(state.get("compact_layout")),
            "long event title is not proven at the 860px responsive minimum",
        )
        base._require(
            int(state.get("event_active_count", 0)) == 7
            and int(state.get("event_active_scroll_maximum", 0)) > 0
            and isinstance(target, Mapping)
            and target.get("resolved_item_row") == 6
            and bool(target.get("fully_visible")),
            "the final Event row is not reachable through the bounded list",
        )
        text_elided = target.get("text_elided")
        base._require(
            isinstance(text_elided, bool)
            and (
                not text_elided
                or bool(target.get("elision_fallback_available"))
            ),
            "the long Event title is neither fully rendered nor tooltip-backed when elided",
        )
    if special == "dirty":
        base._require(bool(state.get("discard_visible")), "dirty Settings does not expose Discard changes")
        base._require(bool(state.get("save_enabled")), "dirty Settings does not enable Save")
        expected_count = int(state.get("expected_unsaved_count", 0))
        base._require(
            state.get("status")
            == "{} unsaved change{}".format(
                expected_count,
                "" if expected_count == 1 else "s",
            ),
            "dirty count is inaccurate",
        )
        base._require(
            state.get("status_indicator_state") == "dirty",
            "dirty Settings lacks its amber warning indicator",
        )
    if special == "discard":
        base._require(not bool(state.get("discard_visible")), "Discard did not restore the saved baseline")
        base._require(not bool(state.get("save_enabled")), "Save remains enabled after Discard")
        base._require(state.get("status") == "Changes discarded", "Discard confirmation is missing")
    if special == "close-confirmation":
        base._require(state.get("close_prompt_titles") == ["Unsaved changes"], "dirty Close did not show the native confirmation layer")
        base._require(
            state.get("close_prompt_actions") == ["Cancel", "Discard changes", "Save and close"],
            "dirty Close does not expose the three approved actions",
        )
    if special == "save-in-progress":
        base._require(state.get("save_text") == "Save changes", "save-in-progress changed the stable action label")
        base._require(state.get("status") == "Saving changes…", "save-in-progress status is missing")
        base._require(
            not bool(state.get("save_enabled"))
            and not bool(state.get("close_enabled"))
            and not bool(state.get("discard_enabled")),
            "save-in-progress footer mutations remain enabled",
        )
        base._require(
            bool(state.get("discard_visible"))
            and state.get("status_indicator_state") == "saving"
            and bool(state.get("status_indicator_timer_active"))
            and state.get("visible_status_indicator_count") == 1,
            "save-in-progress does not expose exactly one animated status spinner",
        )
        base._require(
            not state.get("enabled_mutation_controls_while_saving"),
            "save-in-progress page mutations remain enabled: {}".format(
                state.get("enabled_mutation_controls_while_saving")
            ),
        )
    if special == "save-success":
        base._require("Saved" in str(state.get("status")), "successful save did not update the baseline/status")
        base._require(not bool(state.get("discard_visible")), "successful save remains dirty")
        base._require(not bool(state.get("save_enabled")), "Save remains enabled after success")
        base._require(
            state.get("status_indicator_state") == "saved",
            "successful save lacks its vector success indicator",
        )
    if special == "save-error-production":
        base._require(bool(state.get("save_error_visible")), "save failure is not local to the footer")
        base._require(not bool(state.get("status_visible")), "save failure overlaps the dirty status")
        base._require(state.get("save_error_text") == "Could not save changes. Your draft is still available.", "save failure copy is not production-formatted")
        base._require(not bool(state.get("save_error_label_clipped")), "save failure copy is clipped in the fixed footer")
        base._require(state.get("save_error_details") == "fixture write failure detail", "technical save detail is not stored separately")
        base._require(bool(state.get("save_error_details_collapsed")), "technical save detail is exposed by default")
        base._require(bool(state.get("save_enabled")), "Save is disabled after failure")
        base._require(
            state.get("save_text") == "Retry"
            and bool(state.get("close_enabled"))
            and state.get("save_error_actions") == ["View details", "Copy error"],
            "save failure does not expose View details, Copy error, Close, and Retry",
        )
        base._require(bool(state.get("discard_visible")), "failed save lost the dirty state")
        base._require(bool(state.get("failure_baseline_retained")), "failed save changed the draft baseline")
        base._require(bool(state.get("failure_values_retained")), "failed save changed staged values")
        base._require(bool(state.get("failure_manual_retained")), "failed save changed the selected manual verse")
        base._require(bool(state.get("failure_event_stage_retained")), "failed save changed staged event lists")
    if special == "restart-persistence":
        base._require(
            bool(state.get("restart_geometry_matches")),
            "Settings did not restore the persisted logical window rectangle",
        )
        base._require(
            state.get("event_sort") == "name",
            "Settings did not restore the persisted event sort order",
        )
        base._require(
            state.get("calendar_view") == "year"
            and state.get("appearance_preset") == "Graphite"
            and state.get("heatmap_preset") == "Plum",
            "Settings did not visibly restore its saved dashboard values",
        )
        base._require(
            not bool(state.get("save_enabled"))
            and not bool(state.get("discard_visible")),
            "restarted Settings is not clean",
        )
        base._require(
            not bool(state.get("status_visible")) and not str(state.get("status", "")),
            "restarted Settings retained stale footer status",
        )
        base._require(
            not bool(state.get("save_error_visible"))
            and not str(state.get("save_error_text", "")),
            "restarted Settings retained stale save failure feedback",
        )
    if special == "legacy-route":
        base._require(state.get("section") == "calendar", "legacy Calendar route did not activate Calendar")
        base._require(bool(state.get("visible_target", {}).get("fully_visible")), "Calendar controls are not fully visible after legacy routing")
    if special == "window-fresh-open":
        base._require(not bool(state.get("fixed_size")), "Settings window is unexpectedly fixed-size")
        default_size = state.get("window_size", [0, 0])
        available = state.get("available_size", [0, 0])
        expected_default = clamp_window_geometry(
            None,
            (0, 0, int(available[0]), int(available[1])),
        )[2:]
        base._require(default_size == list(expected_default), "fresh Settings geometry is not the 1080x760 logical default")
        base._require(not bool(state.get("window_modal")), "Settings still uses window-modal sheet behavior")
        base._require(bool(state.get("application_modal")), "Settings capture is not application-modal")
        decoration = state.get("native_frame_decoration", {})
        base._require(
            int(decoration.get("width", 0)) > 0
            or int(decoration.get("height", 0)) > 0,
            "fresh-open capture lacks native Settings window decoration",
        )
    if special in {"window-clamp", "window-offscreen-restore"}:
        size = state.get("window_size", [0, 0])
        available = state.get("available_size", [0, 0])
        base._require(size[0] <= available[0] - 96 and size[1] <= available[1] - 96, "Settings restored size escaped its 48px screen margins")
    if case.get("family") == "settings-pages":
        decoration = state.get("native_frame_decoration", {})
        base._require(
            int(decoration.get("width", 0)) > 0
            or int(decoration.get("height", 0)) > 0,
            "Settings page capture lacks native window decoration",
        )
        if case.get("width") == "full":
            base._require(bool(state.get("window_maximized")), "full-screen Settings page capture is not maximized")
        else:
            expected_height = 800 if int(case.get("width", 0)) >= 1280 else 760
            base._require(
                state.get("window_size") == [int(case["width"]), expected_height],
                "Settings page capture geometry differs from the 100% matrix",
            )
    if special in {"anki-light", "anki-dark"}:
        expected = "light" if special == "anki-light" else "dark"
        base._require(state.get("anki_theme") == expected, "Settings theme fixture differs from the Anki theme")
        expected_window = "#F3F6F8" if expected == "light" else "#0B1118"
        base._require(state.get("settings_window_token") == expected_window, "Settings shell did not follow the Anki theme")
    base._require(bool(state.get("parented_to_anki")), "Settings is not parented to Anki")
    base._require(
        bool(state.get("modal_capture_lifecycle")),
        "Settings capture does not preserve modal ownership",
    )


def _active_qa_editor(dialog: SettingsDialog) -> QWidget | None:
    for attribute in ("_qa_event_editor", "_qa_verse_editor"):
        editor = getattr(dialog, attribute, None)
        if isinstance(editor, QWidget) and editor.isVisible():
            return editor
    return None


def _settings_client_capture(dialog: SettingsDialog) -> Any:
    """Render the Settings client and any parented editor into one pixmap."""

    pixmap = dialog.grab()
    editor = _active_qa_editor(dialog)
    if pixmap.isNull() or editor is None or not editor.isVisible():
        return pixmap
    editor_pixmap = editor.grab()
    if editor_pixmap.isNull():
        return pixmap
    origin = editor.mapToGlobal(QPoint(0, 0)) - dialog.mapToGlobal(QPoint(0, 0))
    painter = QPainter(pixmap)
    try:
        painter.drawPixmap(origin, editor_pixmap)
    finally:
        painter.end()
    return pixmap


def _settings_surface_match_ratio(
    captured: Any,
    reference: Any,
    *,
    captured_logical_size: tuple[int, int],
    reference_logical_size: tuple[int, int],
    reference_origin: QPoint,
) -> float:
    """Compare sampled client pixels so a same-sized background cannot pass."""

    if captured.isNull() or reference.isNull():
        return 0.0
    captured_image = captured.toImage()
    reference_image = reference.toImage()
    captured_width, captured_height = captured_logical_size
    reference_width, reference_height = reference_logical_size
    if min(captured_width, captured_height, reference_width, reference_height) <= 0:
        return 0.0
    captured_scale_x = captured_image.width() / captured_width
    captured_scale_y = captured_image.height() / captured_height
    reference_scale_x = reference_image.width() / reference_width
    reference_scale_y = reference_image.height() / reference_height
    fractions = (0.07, 0.18, 0.31, 0.44, 0.57, 0.70, 0.83, 0.94)
    matched = 0
    sampled = 0
    for y_fraction in fractions:
        reference_y = min(reference_height - 1, round(reference_height * y_fraction))
        captured_y = reference_origin.y() + reference_y
        if not 0 <= captured_y < captured_height:
            continue
        for x_fraction in fractions:
            reference_x = min(reference_width - 1, round(reference_width * x_fraction))
            captured_x = reference_origin.x() + reference_x
            if not 0 <= captured_x < captured_width:
                continue
            captured_color = captured_image.pixelColor(
                min(captured_image.width() - 1, round(captured_x * captured_scale_x)),
                min(captured_image.height() - 1, round(captured_y * captured_scale_y)),
            )
            reference_color = reference_image.pixelColor(
                min(reference_image.width() - 1, round(reference_x * reference_scale_x)),
                min(reference_image.height() - 1, round(reference_y * reference_scale_y)),
            )
            difference = (
                abs(captured_color.red() - reference_color.red())
                + abs(captured_color.green() - reference_color.green())
                + abs(captured_color.blue() - reference_color.blue())
            )
            matched += int(difference <= 90)
            sampled += 1
    return matched / sampled if sampled else 0.0


def _settings_image_difference_ratio(left: QPixmap, right: QPixmap) -> float:
    """Return a stable sampled RGB difference ratio for paired proof states."""

    if left.isNull() or right.isNull():
        return 0.0
    left_image = left.toImage()
    right_image = right.toImage()
    if left_image.size() != right_image.size():
        return 0.0
    width = left_image.width()
    height = left_image.height()
    if width <= 0 or height <= 0:
        return 0.0
    stride = 4
    different = 0
    sampled = 0
    for y in range(0, height, stride):
        for x in range(0, width, stride):
            left_color = left_image.pixelColor(x, y)
            right_color = right_image.pixelColor(x, y)
            delta = (
                abs(left_color.red() - right_color.red())
                + abs(left_color.green() - right_color.green())
                + abs(left_color.blue() - right_color.blue())
            )
            different += int(delta >= 12)
            sampled += 1
    return different / sampled if sampled else 0.0


def _grab_screen_logical_rect(screen: Any, rect: QRect) -> QPixmap:
    """Capture a screen-local logical rectangle on multi-display macOS.

    ``QScreen.grabWindow(0, x, y, width, height)`` is inconsistent across Qt
    platform plugins when the selected display has a negative virtual-desktop
    origin.  Grabbing that QScreen first and cropping its backing pixels keeps
    the display identity explicit and avoids accidentally sampling the Anki
    parent on another screen.
    """

    screen_geometry = screen.geometry()
    full_screen = screen.grabWindow(0)
    if full_screen.isNull():
        return full_screen
    dpr = max(1.0, float(full_screen.devicePixelRatio()))
    width_scale = full_screen.width() / max(1, screen_geometry.width())
    height_scale = full_screen.height() / max(1, screen_geometry.height())
    inferred_scale = (width_scale + height_scale) / 2.0
    if (
        abs(width_scale - height_scale) <= 0.03
        and abs(inferred_scale - round(inferred_scale)) <= 0.03
        and inferred_scale > dpr + 0.25
    ):
        dpr = float(round(inferred_scale))
    local_x = rect.x() - screen_geometry.x()
    local_y = rect.y() - screen_geometry.y()
    physical_rect = QRect(
        round(local_x * dpr),
        round(local_y * dpr),
        round(rect.width() * dpr),
        round(rect.height() * dpr),
    )
    physical_bounds = QRect(0, 0, full_screen.width(), full_screen.height())
    if not physical_bounds.contains(physical_rect):
        return QPixmap()
    cropped = full_screen.copy(physical_rect)
    cropped.setDevicePixelRatio(dpr)
    return cropped


def _grab_macos_decorated_window(dialog: SettingsDialog, width: int, height: int) -> QPixmap:
    """Render the dialog's native AppKit frame without screen-recording access.

    macOS may deny ``QScreen.grabWindow()`` to an isolated Anki process even
    though that process owns the target window.  The Qt ``winId()`` is the
    window's native ``NSView``; its frame-view parent includes the title bar
    and traffic-light controls.  AppKit can render that owned view hierarchy
    to PDF without sampling another process or Space, and Qt's PDF image
    reader rasterizes it at the dialog's retained DPR.

    This is a capture fallback only.  It does not replace the separate native
    full-screen/Space acceptance workflow.
    """

    if sys.platform != "darwin" or width <= 0 or height <= 0:
        return QPixmap()

    diagnostic = base.REPORT.setdefault("capture_diagnostics", {}).setdefault(
        "appkit_decorated_capture", {}
    )

    def failed(reason: str) -> QPixmap:
        diagnostic["failure"] = reason
        base._write_report()
        return QPixmap()

    class NSPoint(ctypes.Structure):
        _fields_ = (("x", ctypes.c_double), ("y", ctypes.c_double))

    class NSSize(ctypes.Structure):
        _fields_ = (("width", ctypes.c_double), ("height", ctypes.c_double))

    class NSRect(ctypes.Structure):
        _fields_ = (("origin", NSPoint), ("size", NSSize))

    try:
        objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        selector = objc.sel_registerName
        selector.argtypes = (ctypes.c_char_p,)
        selector.restype = ctypes.c_void_p
        class_name = objc.object_getClassName
        class_name.argtypes = (ctypes.c_void_p,)
        class_name.restype = ctypes.c_char_p
        send_pointer = ctypes.CFUNCTYPE(
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )(("objc_msgSend", objc))
        send_rect_pointer = ctypes.CFUNCTYPE(
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            NSRect,
        )(("objc_msgSend", objc))
        send_length = ctypes.CFUNCTYPE(
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )(("objc_msgSend", objc))
        send_rect_void = ctypes.CFUNCTYPE(
            None,
            ctypes.c_void_p,
            ctypes.c_void_p,
            NSRect,
            ctypes.c_void_p,
        )(("objc_msgSend", objc))
        send_integer_pointer = ctypes.CFUNCTYPE(
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_long,
            ctypes.c_void_p,
        )(("objc_msgSend", objc))
        objc_class = objc.objc_getClass
        objc_class.argtypes = (ctypes.c_char_p,)
        objc_class.restype = ctypes.c_void_p

        native_view = ctypes.c_void_p(int(dialog.winId()))
        diagnostic["native_view"] = hex(int(dialog.winId()))
        diagnostic["native_view_class"] = (
            class_name(native_view).decode("utf-8", "replace")
            if native_view
            else None
        )
        native_window = send_pointer(native_view, selector(b"window"))
        diagnostic["native_window"] = hex(native_window) if native_window else None
        diagnostic["native_window_class"] = (
            class_name(native_window).decode("utf-8", "replace")
            if native_window
            else None
        )
        content_view = send_pointer(native_window, selector(b"contentView"))
        diagnostic["content_view_class"] = (
            class_name(content_view).decode("utf-8", "replace")
            if content_view
            else None
        )
        frame_view = send_pointer(content_view, selector(b"superview"))
        diagnostic["frame_view_class"] = (
            class_name(frame_view).decode("utf-8", "replace")
            if frame_view
            else None
        )
        if not native_window:
            return failed("native-view-window-is-null")
        if not content_view:
            return failed("native-window-content-view-is-null")
        if not frame_view:
            return failed("content-view-superview-is-null")

        capture_rect = NSRect(
            NSPoint(0.0, 0.0),
            NSSize(float(width), float(height)),
        )
        bitmap_rep = send_rect_pointer(
            frame_view,
            selector(b"bitmapImageRepForCachingDisplayInRect:"),
            capture_rect,
        )
        diagnostic["bitmap_rep_class"] = (
            class_name(bitmap_rep).decode("utf-8", "replace")
            if bitmap_rep
            else None
        )
        if bitmap_rep:
            send_rect_void(
                frame_view,
                selector(b"cacheDisplayInRect:toBitmapImageRep:"),
                capture_rect,
                bitmap_rep,
            )
            dictionary_class = objc_class(b"NSDictionary")
            empty_properties = send_pointer(
                dictionary_class,
                selector(b"dictionary"),
            )
            png_data = send_integer_pointer(
                bitmap_rep,
                selector(b"representationUsingType:properties:"),
                4,  # NSBitmapImageFileTypePNG
                empty_properties,
            )
            if png_data:
                png_byte_count = int(send_length(png_data, selector(b"length")))
                png_byte_pointer = send_pointer(png_data, selector(b"bytes"))
                diagnostic["bitmap_png_byte_count"] = png_byte_count
                if png_byte_count > 0 and png_byte_pointer:
                    bitmap = QPixmap()
                    if bitmap.loadFromData(
                        ctypes.string_at(png_byte_pointer, png_byte_count),
                        "PNG",
                    ):
                        dpr = max(1.0, float(dialog.devicePixelRatioF()))
                        target_width = round(width * dpr)
                        target_height = round(height * dpr)
                        if (
                            bitmap.width() != target_width
                            or bitmap.height() != target_height
                        ):
                            bitmap = bitmap.scaled(
                                target_width,
                                target_height,
                                Qt.AspectRatioMode.IgnoreAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        bitmap.setDevicePixelRatio(dpr)
                        diagnostic["bitmap_rendered_pixels"] = [
                            bitmap.width(),
                            bitmap.height(),
                        ]
                        diagnostic["status"] = "bitmap-rendered"
                        diagnostic.pop("failure", None)
                        base._write_report()
                        return bitmap

        pdf_data = send_rect_pointer(
            frame_view,
            selector(b"dataWithPDFInsideRect:"),
            capture_rect,
        )
        if not pdf_data:
            return failed("frame-view-pdf-data-is-null")
        byte_count = int(send_length(pdf_data, selector(b"length")))
        byte_pointer = send_pointer(pdf_data, selector(b"bytes"))
        diagnostic["pdf_byte_count"] = byte_count
        if byte_count <= 0 or not byte_pointer:
            return failed("frame-view-pdf-data-is-empty")
        pdf_bytes = ctypes.string_at(byte_pointer, byte_count)

        dpr = max(1.0, float(dialog.devicePixelRatioF()))
        buffer = QBuffer()
        buffer.setData(QByteArray(pdf_bytes))
        if not buffer.open(QIODevice.OpenModeFlag.ReadOnly):
            return failed("pdf-buffer-did-not-open")
        reader = QImageReader(buffer, b"pdf")
        reader.setScaledSize(QSize(round(width * dpr), round(height * dpr)))
        image = reader.read()
        diagnostic["pdf_reader_error"] = reader.errorString()
        diagnostic["pdf_rendered_pixels"] = [image.width(), image.height()]
        buffer.close()
        if image.isNull():
            return failed("qt-pdf-reader-returned-null-image")
        rendered = QPixmap.fromImage(image)
        rendered.setDevicePixelRatio(dpr)
        diagnostic["status"] = "rendered"
        diagnostic.pop("failure", None)
        base._write_report()
        return rendered
    except Exception as exc:
        base.REPORT.setdefault("capture_diagnostics", {}).setdefault(
            "appkit_decorated_capture", {}
        )["error"] = "{}: {}".format(type(exc).__name__, exc)
        base._write_report()
        return QPixmap()


def _capture_settings(dialog: SettingsDialog, case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    QApplication.processEvents()
    screen = _settings_screen(dialog)
    require_compositor = str(case.get("special", "")) in {
        "event-editor-open", "bible-long", "save-error-production",
    }
    capture_complete_frame = (
        case.get("family") == "settings-pages"
        or str(case.get("special", "")) == "window-fresh-open"
    )
    reference = _settings_client_capture(dialog)
    if require_compositor:
        expected_width, expected_height = dialog.width(), dialog.height()
        origin = dialog.mapToGlobal(QPoint(0, 0))
        pixmap = _grab_screen_logical_rect(
            screen, QRect(origin.x(), origin.y(), expected_width, expected_height)
        )
        method = "QScreen.grabWindow-native-compositor-client"
        base._require(not pixmap.isNull(), "native compositor capture is required for editor and save-error acceptance")
    elif capture_complete_frame:
        frame = dialog.frameGeometry()
        expected_width, expected_height = frame.width(), frame.height()
        appkit_window = _grab_macos_decorated_window(
            dialog,
            expected_width,
            expected_height,
        )
        if not appkit_window.isNull():
            pixmap = appkit_window
            appkit_status = str(
                base.REPORT.get("capture_diagnostics", {})
                .get("appkit_decorated_capture", {})
                .get("status", "")
            )
            method = (
                "NSView.cacheDisplayInRect-complete-decorated-settings-frame"
                if appkit_status == "bitmap-rendered"
                else "NSView.dataWithPDFInsideRect-complete-decorated-settings-frame"
            )
        else:
            pixmap = _grab_screen_logical_rect(screen, frame)
            method = "QScreen.grabWindow-full-display-crop-complete-decorated-settings-frame"
    else:
        expected_width, expected_height = dialog.width(), dialog.height()
        # QScreen.grabWindow(dialog.winId()) is not a trustworthy macOS client
        # capture: the returned pixmap can have the requested dimensions while
        # containing another window's screen pixels. Capture the owned Qt tree
        # directly for client-only review states so unrelated applications can
        # never contaminate the evidence.
        pixmap = reference
        method = "QDialog.grab-composited-client-fallback"

    if capture_complete_frame:
        reference_origin = dialog.mapToGlobal(QPoint(0, 0)) - frame.topLeft()
    else:
        reference_origin = QPoint(0, 0)
    if (
        method.startswith("NSView.")
        and not pixmap.isNull()
        and not reference.isNull()
    ):
        # The AppKit frame view supplies the native title-bar geometry while
        # Qt owns the layer-backed client surface.  AppKit's PDF renderer does
        # not include that Qt layer, so composite the dialog-owned client at
        # its measured frame offset.  This never samples another process or
        # substitutes for the separate Space-switch workflow.
        painter = QPainter(pixmap)
        try:
            painter.drawPixmap(reference_origin, reference)
        finally:
            painter.end()
        method = method.replace(
            "-complete-decorated-settings-frame",
            "+QDialog.grab-composited-complete-decorated-settings-frame",
        )
    surface_match_ratio = _settings_surface_match_ratio(
        pixmap,
        reference,
        captured_logical_size=(expected_width, expected_height),
        reference_logical_size=(dialog.width(), dialog.height()),
        reference_origin=reference_origin,
    )

    # Retry after native expose/paint events settle. Size and color-count
    # checks alone cannot distinguish Settings from the Dashboard underneath;
    # the probe deliberately avoids raise/activate calls that can change Spaces.
    for _attempt in range(3):
        if surface_match_ratio >= 0.55:
            break
        if method.startswith("NSView."):
            # Preserve the owned native-frame rendering for diagnostics instead
            # of replacing it with the known-null full-screen compositor path.
            break
        QApplication.processEvents()
        if capture_complete_frame:
            pixmap = _grab_screen_logical_rect(screen, frame)
        else:
            origin = dialog.mapToGlobal(QPoint(0, 0))
            pixmap = _grab_screen_logical_rect(
                screen,
                QRect(origin.x(), origin.y(), expected_width, expected_height),
            )
        surface_match_ratio = _settings_surface_match_ratio(
            pixmap,
            reference,
            captured_logical_size=(expected_width, expected_height),
            reference_logical_size=(dialog.width(), dialog.height()),
            reference_origin=reference_origin,
        )

    def logical_size(value: Any) -> tuple[float, float]:
        ratio = max(1.0, float(value.devicePixelRatio()))
        return value.width() / ratio, value.height() / ratio

    def normalize_backing_scale(value: Any) -> tuple[Any, float | None]:
        """Normalize macOS captures whose backing pixels omit their 2x DPR tag."""

        if value.isNull() or expected_width <= 0 or expected_height <= 0:
            return value, None
        reported = max(1.0, float(value.devicePixelRatio()))
        width_scale = value.width() / expected_width
        height_scale = value.height() / expected_height
        inferred = (width_scale + height_scale) / 2.0
        scales_match = abs(width_scale - height_scale) <= 0.03
        logical_mismatch = (
            abs(value.width() / reported - expected_width) > 4
            or abs(value.height() / reported - expected_height) > 4
        )
        if (
            logical_mismatch
            and scales_match
            and 1.25 <= inferred <= 4.0
            and abs(inferred - round(inferred)) <= 0.03
        ):
            value.setDevicePixelRatio(float(round(inferred)))
            return value, float(round(inferred))
        return value, None

    logical_width, logical_height = (0.0, 0.0) if pixmap.isNull() else logical_size(pixmap)
    color_count = 0 if pixmap.isNull() else base._sample_color_count(pixmap)
    if (
        pixmap.isNull()
        or color_count < 3
        or abs(logical_width - expected_width) > 4
        or abs(logical_height - expected_height) > 4
        or surface_match_ratio < 0.55
    ):
        fallback = reference
        fallback_colors = 0 if fallback.isNull() else base._sample_color_count(fallback)
        if not require_compositor and not capture_complete_frame and not fallback.isNull() and fallback_colors >= 3:
            pixmap = fallback
            color_count = fallback_colors
            method = "QDialog.grab-composited-client-fallback"
            reference_origin = QPoint(0, 0)
            surface_match_ratio = 1.0

    pixmap, inferred_capture_scale = normalize_backing_scale(pixmap)
    if pixmap.isNull() or surface_match_ratio < 0.55:
        diagnostic_root = OUTPUT_ROOT / "capture-diagnostics"
        diagnostic_root.mkdir(parents=True, exist_ok=True)
        pixmap_path = diagnostic_root / "{}-screen.png".format(case["id"])
        reference_path = diagnostic_root / "{}-client.png".format(case["id"])
        if not pixmap.isNull():
            pixmap.save(str(pixmap_path), "PNG")
        if not reference.isNull():
            reference.save(str(reference_path), "PNG")
        base.REPORT.setdefault("capture_diagnostics", {})[str(case["id"])] = {
            "surface_match_ratio": surface_match_ratio,
            "untrusted_direct_window_capture_disabled": True,
            "screen_capture": str(pixmap_path),
            "screen_capture_pixels": [pixmap.width(), pixmap.height()],
            "screen_capture_dpr": float(pixmap.devicePixelRatio()) if not pixmap.isNull() else None,
            "client_reference": str(reference_path),
            "client_reference_pixels": [reference.width(), reference.height()],
            "client_reference_dpr": float(reference.devicePixelRatio()) if not reference.isNull() else None,
            "dialog_frame": [frame.x(), frame.y(), frame.width(), frame.height()] if capture_complete_frame else None,
            "dialog_client": [dialog.x(), dialog.y(), dialog.width(), dialog.height()],
            "screen_geometry": [screen.geometry().x(), screen.geometry().y(), screen.geometry().width(), screen.geometry().height()],
        }
        base._write_report()
    base._require(not pixmap.isNull(), "native Settings capture is null")
    base._require(color_count >= 3, "native Settings capture appears blank")
    base._require(
        surface_match_ratio >= 0.55,
        "native Settings capture sampled the parent background instead of the Settings surface",
    )
    dpr = max(1.0, float(pixmap.devicePixelRatio()))
    logical_width, logical_height = logical_size(pixmap)
    base._require(
        abs(logical_width - expected_width) <= 4,
        "native Settings capture width is incorrect: {} px at DPR {} != {} logical px on {} ({})".format(
            pixmap.width(), dpr, expected_width, screen.name(), method
        ),
    )
    base._require(
        abs(logical_height - expected_height) <= 4,
        "native Settings capture height is incorrect: {} px at DPR {} != {} logical px on {} ({})".format(
            pixmap.height(), dpr, expected_height, screen.name(), method
        ),
    )
    CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
    path = CAPTURE_ROOT / "{}.png".format(case["id"])
    base._require(bool(pixmap.save(str(path), "PNG")), "could not save native Settings capture")
    capture_sha256 = base._sha256(path)
    comparison: dict[str, Any] | None = None
    compare_with = case.get("compare_with")
    if compare_with is not None:
        baseline_path = CAPTURE_ROOT / "{}.png".format(compare_with)
        base._require(
            baseline_path.is_file(),
            "paired Settings baseline is missing: {}".format(compare_with),
        )
        baseline_pixmap = QPixmap(str(baseline_path))
        same_physical_size = (
            not baseline_pixmap.isNull()
            and baseline_pixmap.toImage().size() == pixmap.toImage().size()
        )
        difference_ratio = _settings_image_difference_ratio(
            baseline_pixmap,
            pixmap,
        )
        minimum_difference = float(case["minimum_image_difference_ratio"])
        comparison = {
            "status": "passed",
            "baseline_capture_id": str(compare_with),
            "baseline_sha256": base._sha256(baseline_path),
            "capture_sha256": capture_sha256,
            "sha256_differs": base._sha256(baseline_path) != capture_sha256,
            "same_physical_size": same_physical_size,
            "sampled_image_difference_ratio": round(difference_ratio, 6),
            "minimum_image_difference_ratio": minimum_difference,
        }
        base._require(
            comparison["same_physical_size"]
            and comparison["sha256_differs"]
            and difference_ratio >= minimum_difference,
            "paired Settings states are not visibly different: {} and {} ({:.6f} < {:.6f})".format(
                compare_with,
                case["id"],
                difference_ratio,
                minimum_difference,
            ),
        )
    base.REPORT["captures"][str(case["id"])] = {
        "file": str(path.relative_to(OUTPUT_ROOT)),
        "sha256": capture_sha256,
        "component": "canonical-settings",
        "page": state.get("section"),
        "caption": case.get("caption"),
        "visible_target": dict(case.get("visible_target", {})),
        "visible_target_fully_visible": bool(
            state.get("visible_target", {}).get("fully_visible")
        ),
        "paired_image_comparison": comparison,
        "font_percent": case.get("font_percent", 100),
        "anki_theme": case.get("anki_theme"),
        "host_platform": case.get("host_platform"),
        "os_scale_percent": case.get("os_scale_percent"),
        "dpr_class": case.get("dpr_class"),
        "capture_method": method,
        "sampled_color_count": color_count,
        "settings_surface_match_ratio": round(surface_match_ratio, 4),
        "settings_surface_verified": True,
        "decorated_window_included": bool(
            capture_complete_frame
            and (
                expected_width > dialog.width()
                or expected_height > dialog.height()
            )
        ),
        "native_frame_decoration": dict(
            state.get("native_frame_decoration", {})
        ),
        "logical_frame": {"width": expected_width, "height": expected_height},
        "dialog_logical_frame": {"width": dialog.width(), "height": dialog.height()},
        "capture_scope": (
            "complete-decorated-settings-window"
            if capture_complete_frame
            else "settings-dialog"
        ),
        "physical_pixels": [pixmap.width(), pixmap.height()],
        "device_pixel_ratio": pixmap.devicePixelRatio(),
        "inferred_capture_scale": inferred_capture_scale,
        "parent_window_title": str(mw.windowTitle()),
        "parent_window_title_matches_profile": base.EXPECTED_PROFILE in str(mw.windowTitle()),
        "state": dict(state),
    }
    base._write_report()


def _close_settings_dialog() -> None:
    global _settings_dialog
    if _settings_dialog is None:
        return
    dialog = _settings_dialog
    for attribute in ("_qa_event_editor", "_qa_verse_editor"):
        editor = getattr(dialog, attribute, None)
        if editor is not None:
            editor.close()
            editor.deleteLater()
    original_is_dark = getattr(dialog, "_qa_original_is_dark", None)
    dialog.force_close()
    if original_is_dark is not None:
        base._controller.is_dark = original_is_dark
    dialog.deleteLater()
    QApplication.processEvents()
    _settings_dialog = None


def _exit_active_settings_exec() -> None:
    """Close nested child dialogs before ending the Settings exec loop."""

    if _settings_dialog is None:
        return
    dialog = _settings_dialog
    for attribute in ("_qa_event_editor", "_qa_verse_editor"):
        editor = getattr(dialog, attribute, None)
        if editor is not None:
            editor.close()
            editor.deleteLater()
            setattr(dialog, attribute, None)
    dialog.force_close()


_STRUCTURED_LAYOUT_ASSERTION_KEYS = (
    "horizontal_scroll_zero",
    "visible_controls_contained",
    "labels_unclipped_or_approved",
    "segmented_selection_matches_model",
    "body_footer_disjoint",
    "footer_actions_visible",
    "page_bottom_reachable",
    "target_fully_visible",
)

_STRUCTURED_RESTORATION_ASSERTION_KEYS = (
    "saved_screen_not_connected",
    "saved_record_rejected",
    "centered_on_parent_screen_before_visibility",
    "logical_geometry_not_dpr_multiplied",
    "decorated_frame_inside_available",
)


def _structured_settings_required() -> bool:
    spec = CAPTURE_PLAN.structured_settings_layout()
    return bool(
        base.STAGE == str(spec.get("stage", ""))
        and CAPTURE_PROFILE in spec.get("required_profiles", [])
    )


def _structured_settings_case_matrix() -> list[dict[str, Any]]:
    """Return the no-PNG native layout matrix in authoritative plan order."""

    spec = CAPTURE_PLAN.structured_settings_layout()
    work_area = list(spec["work_area_logical"])
    page_fixtures: dict[str, tuple[str, dict[str, Any]]] = {
        "appearance": ("advanced-appearance", {"kind": "widget", "attribute": "appearance_advanced", "scroll": "bottom"}),
        "calendar": ("future-on", {"kind": "widget", "attribute": "calendar_range_card"}),
        "bible_display": ("", {"kind": "widget", "attribute": "bible_appearance_preview"}),
        "dashboard": (
            "structured-dashboard",
            {
                "kind": "widget",
                "attribute": "local_data_card",
                "scroll": "bottom",
            },
        ),
        "events": (
            "event-long-title",
            {
                "kind": "item",
                "attribute": "active_events",
                "item": "last",
                "scroll": "bottom",
                "allow_elision": True,
            },
        ),
        "bible_verse": (
            "bible-long-row",
            {
                "kind": "item",
                "attribute": "quote_list",
                "item": "last",
                "scroll": "bottom",
                "allow_elision": True,
            },
        ),
        "about_support": (
            "about-bottom",
            {
                "kind": "widget",
                "attribute": "about_recovery_card",
                "scroll": "bottom",
            },
        ),
    }
    cases: list[dict[str, Any]] = []
    for percent in spec["application_font_percents"]:
        for page in spec["pages"]:
            special, target = page_fixtures[str(page)]
            cases.append(
                {
                    "id": "settings-font-{}-{}".format(percent, page),
                    "report_id": "settings-font-{}".format(percent),
                    "page": str(page),
                    "special": special,
                    "font_percent": int(percent),
                    "anki_theme": "dark",
                    "structured_work_area_logical": list(work_area),
                    "visible_target": dict(target),
                    "structured_layout_page": True,
                }
            )
    restore_spec = dict(spec["restore_scenarios"][0])
    cases.append(
        {
            "id": str(restore_spec["id"]),
            "page": "dashboard",
            "special": "structured-disconnected-monitor",
            "font_percent": 100,
            "anki_theme": "dark",
            "preserve_geometry_fixture": True,
            "restore_spec": restore_spec,
            "structured_geometry_restore": True,
        }
    )
    return cases


def _footer_actions_are_visible_and_contained(dialog: SettingsDialog) -> bool:
    footer = _global_rect(dialog.footer_shell)
    actions = (dialog.revert_button, dialog.close_button, dialog.save_button)
    expected_labels = ("Discard changes", "Close", "Save changes")
    return bool(
        all(
            button is not None
            and button.isVisibleTo(dialog)
            and footer.contains(_global_rect(button))
            and button.width()
            >= button.fontMetrics().horizontalAdvance(
                button.text().replace("&", "").strip()
            )
            + 16
            for button in actions
        )
        and tuple(
            button.text().replace("&", "").strip()
            for button in actions
        )
        == expected_labels
        and [
            button
            for button in sorted(
                actions,
                key=lambda candidate: _global_rect(candidate).center().x(),
            )
        ]
        == list(actions)
    )


def _structured_page_assertions(
    dialog: SettingsDialog,
    case: Mapping[str, Any],
    state: Mapping[str, Any],
) -> dict[str, bool]:
    """Project generic native state into the strict structured report."""

    work_area = tuple(int(value) for value in case["structured_work_area_logical"])
    resolved = clamp_window_geometry(None, work_area)
    expected_page_cap = 1080
    navigation_is_unique = bool(state.get("nav_visible")) != bool(
        state.get("compact_nav_visible")
    )
    visible_controls_contained = bool(
        not state.get("visible_interactive_overflow")
        and state.get("visible_page_scroller_count") == 1
        and state.get("main_page_scroller") is True
        and state.get("decorated_frame_inside_available") is True
        and navigation_is_unique
        and int(state.get("header_height", 0)) >= 72
        and int(state.get("footer_minimum_height", 0)) >= 56
        and int(state.get("page_maximum_width", 0)) == expected_page_cap
        and int(state.get("settings_shell_maximum", 0)) == 1264
        and list(state.get("window_size", [])) == [resolved[2], resolved[3]]
    )
    return {
        "horizontal_scroll_zero": bool(
            state.get("horizontal_scroll_maximum") == 0
            and state.get("horizontal_scroll_disabled") is True
        ),
        "visible_controls_contained": visible_controls_contained,
        "labels_unclipped_or_approved": bool(
            not state.get("clipped_button_labels")
            and not state.get("clipped_plain_labels")
            and not state.get("clipped_wrapped_labels")
            and (
                not bool(case.get("visible_target", {}).get("allow_elision"))
                or bool(
                    state.get("visible_target", {}).get(
                        "elision_fallback_available"
                    )
                )
            )
        ),
        "segmented_selection_matches_model": not bool(
            state.get("segmented_model_failures")
        ),
        "body_footer_disjoint": bool(
            state.get("footer_after_body") is True
            and state.get("footer_overlaps_page_viewport") is False
        ),
        "footer_actions_visible": _footer_actions_are_visible_and_contained(dialog),
        "page_bottom_reachable": bool(state.get("page_bottom_reachable")),
        "target_fully_visible": bool(
            isinstance(state.get("visible_target"), Mapping)
            and state["visible_target"].get("spec") == case.get("visible_target")
            and state["visible_target"].get("fully_visible") is True
            and (
                not bool(case.get("visible_target", {}).get("allow_elision"))
                or state["visible_target"].get("elision_fallback_available") is True
            )
        ),
    }


def _assert_scoped_settings_resets(dialog: SettingsDialog) -> None:
    """Exercise native card Reset behavior without adding or capturing a case."""

    initial_values = deepcopy(dialog.draft.values)
    initial_quotes = list(dialog.quotes)
    initial_pending_quote = dialog.pending_manual_quote
    initial_pending_index = dialog._pending_manual_quote_index
    initial_current_quote = dialog._saved_current_quote
    initial_view_state = dialog._capture_transient_view_state()

    def context_state() -> dict[str, Any]:
        state = dialog._capture_transient_view_state()
        state.update(
            event_search=dialog.event_search.text(),
            deck_search=dialog.deck_search.text(),
            quote_search=dialog.quote_search.text(),
            bible_view=dialog.bible_view_tabs.currentIndex(),
        )
        return state

    def exercise(
        scope: str,
        label: str,
        stage: Callable[[], None],
        checks: Mapping[str, Callable[[], bool]],
        *,
        prechecks: Mapping[str, Callable[[], bool]] | None = None,
        later_edit: Callable[[], None] | None = None,
        undo_checks: Mapping[str, Callable[[], bool]] | None = None,
    ) -> None:
        stage()
        dialog._sync_draft()
        QApplication.processEvents()
        for name, predicate in (prechecks or {}).items():
            base._require(predicate(), "{} reset precondition failed: {}".format(scope, name))
        context_before = context_state()
        dialog._reset_card(scope, label)
        QApplication.processEvents()
        for name, predicate in checks.items():
            base._require(predicate(), "{} reset failed: {}".format(scope, name))
        base._require(
            context_state() == context_before,
            "{} reset changed unrelated Settings view context".format(scope),
        )
        if later_edit is not None:
            later_edit()
            dialog._sync_draft()
        dialog._undo_reset()
        QApplication.processEvents()
        for name, predicate in (undo_checks or {}).items():
            base._require(predicate(), "{} reset undo failed: {}".format(scope, name))

    defaults = dialog.draft.defaults
    try:
        default_opacity = int(defaults["appearance"]["opacity"])
        staged_opacity = 94 if default_opacity != 94 else 95
        later_retention = min(
            100,
            max(50, int(defaults["study"]["retention_target"]) + 3),
        )
        exercise(
            "appearance",
            "Appearance",
            lambda: dialog.opacity.setValue(staged_opacity),
            {
                "native opacity control repainted": lambda: dialog.opacity.value()
                == default_opacity,
            },
            later_edit=lambda: dialog.retention_target.setValue(later_retention),
            undo_checks={
                "later Study edit preserved": lambda: dialog.retention_target.value()
                == later_retention,
            },
        )

        event_marker = not bool(defaults["visibility"]["events"])

        def stage_dashboard_sections() -> None:
            dialog.visibility["today"].setChecked(
                not bool(defaults["visibility"]["today"])
            )
            dialog.visibility["events"].setChecked(event_marker)

        exercise(
            "dashboard_sections",
            "Dashboard sections",
            stage_dashboard_sections,
            {
                "owned Today control repainted": lambda: dialog.visibility[
                    "today"
                ].isChecked()
                == bool(defaults["visibility"]["today"]),
                "Calendar event marker preserved": lambda: dialog.visibility[
                    "events"
                ].isChecked()
                == event_marker,
            },
        )

        def stage_invalid_retention() -> None:
            dialog.retention_target.setValue(
                int(defaults["study"]["retention_target"])
            )
            dialog.retention_target.editor.setText("")

        exercise(
            "study_metrics",
            "Study metrics",
            stage_invalid_retention,
            {
                "invalid input cleared": dialog.retention_target.is_valid,
                "retention control repainted": lambda: dialog.retention_target.value()
                == int(defaults["study"]["retention_target"]),
            },
            prechecks={
                "invalid input exposes Reset": lambda: not dialog.study_metrics_card.reset_button.isHidden(),
            },
        )

        default_calendar_view = str(defaults["heatmap"]["calendar_view"])
        staged_calendar_view = (
            "month" if default_calendar_view != "month" else "year"
        )

        def stage_calendar_display() -> None:
            dialog._set_combo_data(dialog.calendar_view, staged_calendar_view)
            dialog.visibility["events"].setChecked(event_marker)

        exercise(
            "calendar_display",
            "Calendar view",
            stage_calendar_display,
            {
                "calendar view repainted": lambda: _combo_value(
                    dialog.calendar_view,
                    "year",
                )
                == default_calendar_view,
                "owned event marker repainted": lambda: dialog.visibility[
                    "events"
                ].isChecked()
                == bool(defaults["visibility"]["events"]),
            },
        )

        def stage_invalid_forecast() -> None:
            dialog.forecast_days.setValue(int(defaults["heatmap"]["forecast_days"]))
            dialog.forecast_days.editor.setText("")

        exercise(
            "calendar_range",
            "Calendar range",
            stage_invalid_forecast,
            {
                "invalid forecast cleared": dialog.forecast_days.is_valid,
                "forecast control repainted": lambda: dialog.forecast_days.value()
                == int(defaults["heatmap"]["forecast_days"]),
                "blank default date uses today": lambda: dialog.ignore_before.date()
                == QDate.currentDate(),
            },
            prechecks={
                "invalid forecast exposes Reset": lambda: not dialog.calendar_range_card.reset_button.isHidden(),
            },
        )

        exercise(
            "local_data",
            "Deck exclusions and filters",
            lambda: dialog.exclude_deleted.setChecked(
                not bool(defaults["heatmap"]["exclude_deleted_cards"])
            ),
            {
                "local filter repainted": lambda: dialog.exclude_deleted.isChecked()
                == bool(defaults["heatmap"]["exclude_deleted_cards"]),
            },
        )

        def stage_invalid_verse_appearance() -> None:
            dialog.font_size.setValue(
                int(str(defaults["bible"]["font_size"]).replace("px", ""))
            )
            dialog.font_size.editor.setText("")

        exercise(
            "bible_appearance",
            "Verse appearance",
            stage_invalid_verse_appearance,
            {
                "invalid verse size cleared": dialog.font_size.is_valid,
                "verse size repainted": lambda: dialog.font_size.value()
                == int(str(defaults["bible"]["font_size"]).replace("px", "")),
            },
            prechecks={
                "invalid verse size exposes Reset": lambda: not dialog.bible_display_card.reset_button.isHidden(),
            },
        )

        base._require(bool(dialog.quotes), "rotation reset requires a verse fixture")
        pending_quote = dialog.quotes[0]

        def stage_manual_rotation() -> None:
            dialog._set_combo_data(dialog.rotation, "manual")
            dialog.pending_manual_quote = pending_quote
            dialog._pending_manual_quote_index = 0
            dialog._refresh_quote_list()

        exercise(
            "bible_rotation",
            "Verse rotation",
            stage_manual_rotation,
            {
                "rotation control repainted": lambda: _combo_value(
                    dialog.rotation,
                    "daily",
                )
                == str(defaults["bible"]["rotation_mode"]),
                "pending manual verse cleared by Reset": lambda: dialog.pending_manual_quote
                is None,
            },
            undo_checks={
                "pending manual verse restored": lambda: dialog.pending_manual_quote
                == pending_quote,
                "pending manual verse index restored": lambda: dialog._pending_manual_quote_index
                == 0,
            },
        )
    finally:
        dialog._clear_undo_state()
        dialog.draft.replace_values(initial_values)
        dialog.staged = deepcopy(dialog.draft.values)
        dialog.quotes = list(initial_quotes)
        dialog._saved_current_quote = initial_current_quote
        dialog._apply_config_to_widgets(dialog.staged)
        dialog.pending_manual_quote = initial_pending_quote
        dialog._pending_manual_quote_index = initial_pending_index
        dialog._sync_draft()
        dialog._restore_transient_view_state(initial_view_state)
        QApplication.processEvents()


def _prepare_structured_settings_case(
    case: Mapping[str, Any],
) -> SettingsDialog:
    """Create one real parented dialog without capturing an image."""

    global _structured_settings_geometry_snapshot
    if case.get("structured_geometry_restore"):
        restore_spec = case["restore_spec"]
        _structured_settings_geometry_snapshot = _snapshot_geometry_preferences()
        for key in _ALL_SETTINGS_GEOMETRY_KEYS:
            _geometry_store.remove(key)
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_KEY,
            QRect(*restore_spec["saved_geometry_logical"]),
        )
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_SCREEN_KEY,
            str(restore_spec["saved_screen_name"]),
        )
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_AVAILABLE_KEY,
            QRect(*restore_spec["saved_available_logical"]),
        )
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_DPR_KEY,
            float(restore_spec["saved_device_pixel_ratio"]),
        )
        _geometry_store.sync()

    dialog = _prepare_settings_case(case)
    if case.get("structured_geometry_restore"):
        screen = _settings_screen()
        available_rect = screen.availableGeometry()
        parent_rect = mw.frameGeometry()
        available = (
            available_rect.x(),
            available_rect.y(),
            available_rect.width(),
            available_rect.height(),
        )
        parent = (
            parent_rect.x(),
            parent_rect.y(),
            parent_rect.width(),
            parent_rect.height(),
        )
        dialog._qa_structured_expected_geometry = clamp_window_geometry(
            None,
            available,
            parent=parent,
        )
        dialog._qa_structured_previsibility_geometry = (
            dialog.geometry().x(),
            dialog.geometry().y(),
            dialog.geometry().width(),
            dialog.geometry().height(),
        )
        dialog._qa_structured_connected_screen_names = [
            str(candidate.name() or "")
            for candidate in QApplication.instance().screens()
        ]
        return dialog

    # The structured layout lane intentionally proves all three fixed footer
    # actions. It stages one ordinary draft change and never persists it.
    if case.get("id") == "settings-font-100-dashboard":
        _assert_scoped_settings_resets(dialog)
    dialog.retention_target.setValue(81)
    dialog._sync_draft()
    return dialog


def _structured_restoration_assertions(
    dialog: SettingsDialog,
    case: Mapping[str, Any],
) -> dict[str, bool]:
    restore_spec = case["restore_spec"]
    saved = tuple(int(value) for value in restore_spec["saved_geometry_logical"])
    expected = tuple(dialog._qa_structured_expected_geometry)
    previsibility = tuple(dialog._qa_structured_previsibility_geometry)
    saved_dpr = float(restore_spec["saved_device_pixel_ratio"])
    frame = dialog.frameGeometry()
    available = _settings_screen(dialog).availableGeometry()
    return {
        "saved_screen_not_connected": str(restore_spec["saved_screen_name"])
        not in dialog._qa_structured_connected_screen_names,
        "saved_record_rejected": previsibility == expected and previsibility != saved,
        "centered_on_parent_screen_before_visibility": previsibility == expected,
        "logical_geometry_not_dpr_multiplied": bool(
            previsibility[2:] == expected[2:]
            and previsibility[2:]
            != (round(saved[2] * saved_dpr), round(saved[3] * saved_dpr))
        ),
        "decorated_frame_inside_available": available.contains(frame),
    }


def _record_structured_page_result(
    case: Mapping[str, Any],
    assertions: Mapping[str, bool],
) -> None:
    percent = int(case["font_percent"])
    entry = _structured_settings_reports[percent]
    normalized = {
        key: bool(assertions.get(key, False))
        for key in _STRUCTURED_LAYOUT_ASSERTION_KEYS
    }
    entry["pages"].append(
        {
            "id": str(case["page"]),
            "status": "passed" if all(normalized.values()) else "failed",
            "assertions": normalized,
        }
    )


def _record_structured_restoration_result(
    case: Mapping[str, Any],
    assertions: Mapping[str, bool],
) -> None:
    normalized = {
        key: bool(assertions.get(key, False))
        for key in _STRUCTURED_RESTORATION_ASSERTION_KEYS
    }
    base.REPORT["_structured_settings_restoration_pending"] = {
        "id": str(case["id"]),
        "kind": "geometry-restoration",
        "status": "passed" if all(normalized.values()) else "failed",
        "application_font_percent": 100,
        "assertions": normalized,
    }


def _activate_structured_settings_case(case: Mapping[str, Any]) -> None:
    try:
        base._require(
            _settings_dialog is not None,
            "structured Settings dialog disappeared before activation",
        )
        if case.get("structured_layout_page"):
            _position_visible_target(_settings_dialog, case)
        QApplication.processEvents()
        QTimer.singleShot(
            720,
            lambda: _inspect_structured_settings_case(case),
        )
    except Exception as exc:
        _record_structured_case_exception(case, exc)


def _record_structured_case_exception(
    case: Mapping[str, Any],
    exc: Exception,
) -> None:
    diagnostics = base.REPORT.setdefault(
        "structured_settings_layout_diagnostics", {}
    )
    diagnostics[str(case.get("id", "structured-settings"))] = {
        "error": "{}: {}".format(type(exc).__name__, exc),
    }
    if case.get("structured_geometry_restore"):
        _record_structured_restoration_result(case, {})
    else:
        _record_structured_page_result(case, {})
    base._write_report()
    _exit_active_settings_exec()
    QTimer.singleShot(120, _next_structured_settings_case)


def _inspect_structured_settings_case(
    case: Mapping[str, Any],
    attempt: int = 0,
) -> None:
    try:
        base._require(
            _settings_dialog is not None,
            "structured Settings dialog disappeared before inspection",
        )
        dialog = _settings_dialog
        QApplication.processEvents()
        if case.get("structured_geometry_restore"):
            assertions = _structured_restoration_assertions(dialog, case)
            if not all(assertions.values()) and attempt < 5:
                QTimer.singleShot(
                    250,
                    lambda: _inspect_structured_settings_case(case, attempt + 1),
                )
                return
        else:
            _position_visible_target(dialog, case)
            QApplication.processEvents()
            state = _settings_state(dialog, case)
            assertions = _structured_page_assertions(dialog, case, state)
            if not all(assertions.values()) and attempt < 5:
                QTimer.singleShot(
                    250,
                    lambda: _inspect_structured_settings_case(case, attempt + 1),
                )
                return
            if not all(assertions.values()):
                base.REPORT.setdefault(
                    "structured_settings_layout_diagnostics", {}
                )[str(case["id"])] = {
                    "assertions": dict(assertions),
                    "state": dict(state),
                }
        if case.get("structured_geometry_restore"):
            _record_structured_restoration_result(case, assertions)
        else:
            _record_structured_page_result(case, assertions)
        base._write_report()
        _exit_active_settings_exec()
        QTimer.singleShot(120, _next_structured_settings_case)
    except Exception as exc:
        if attempt < 5:
            QTimer.singleShot(
                250,
                lambda: _inspect_structured_settings_case(case, attempt + 1),
            )
            return
        _record_structured_case_exception(case, exc)


def _finish_structured_settings_layout() -> None:
    global _structured_settings_geometry_snapshot
    try:
        _close_settings_dialog()
        if _structured_settings_geometry_snapshot is not None:
            _restore_geometry_snapshot(_structured_settings_geometry_snapshot)
            _structured_settings_geometry_snapshot = None
        _restore_application_font()
        pngs_after = {
            str(path.relative_to(CAPTURE_ROOT)): base._sha256(path)
            for path in CAPTURE_ROOT.rglob("*.png")
        } if CAPTURE_ROOT.exists() else {}
        mutated_png_paths = {
            path
            for path in set(pngs_after) | set(_structured_settings_pngs_before)
            if pngs_after.get(path) != _structured_settings_pngs_before.get(path)
        }
        generated_png_count = len(mutated_png_paths)
        spec = CAPTURE_PLAN.structured_settings_layout()
        ordered_reports: list[dict[str, Any]] = []
        for percent in spec["application_font_percents"]:
            entry = _structured_settings_reports[int(percent)]
            entry["status"] = (
                "passed"
                if len(entry["pages"]) == len(spec["pages"])
                and all(page["status"] == "passed" for page in entry["pages"])
                else "failed"
            )
            ordered_reports.append(entry)
        restoration = base.REPORT.pop(
            "_structured_settings_restoration_pending",
            None,
        )
        if not isinstance(restoration, Mapping):
            restore_spec = spec["restore_scenarios"][0]
            fallback_case = {
                "id": restore_spec["id"],
                "restore_spec": restore_spec,
            }
            _record_structured_restoration_result(fallback_case, {})
            restoration = base.REPORT.pop(
                "_structured_settings_restoration_pending"
            )
        ordered_reports.append(dict(restoration))
        report_failed = bool(
            generated_png_count
            or any(entry.get("status") != "passed" for entry in ordered_reports)
        )
        candidate = base.REPORT.get("identity", {}).get("candidate", {})
        base.REPORT["structured_settings_layout"] = {
            "schema_version": 1,
            "release": RELEASE,
            "stage": "initial",
            "status": "failed" if report_failed else "passed",
            "package_sha256": str(candidate.get("candidate_sha256", "")),
            "capture_plan_sha256": CAPTURE_PLAN.sha256,
            "adds_png_frames": False,
            "generated_png_count": generated_png_count,
            "reports": ordered_reports,
        }
        base.REPORT["structured_settings_layout_matrix"] = {
            "status": "failed" if report_failed else "passed",
            "case_ids": [case["id"] for case in _structured_settings_cases],
            "adds_png_frames": False,
            "png_count_before": len(_structured_settings_pngs_before),
            "png_count_after": len(pngs_after),
            "generated_png_count": generated_png_count,
            "mutated_png_paths": sorted(mutated_png_paths),
        }
        base._write_report()
        QTimer.singleShot(0, _complete_stage)
    except Exception as exc:
        base._error("structured-settings-finish", exc)


def _next_structured_settings_case() -> None:
    global _settings_dialog, _structured_settings_index
    global _structured_settings_geometry_snapshot
    try:
        _close_settings_dialog()
        if _structured_settings_geometry_snapshot is not None:
            _restore_geometry_snapshot(_structured_settings_geometry_snapshot)
            _structured_settings_geometry_snapshot = None
        if _structured_settings_index >= len(_structured_settings_cases):
            _finish_structured_settings_layout()
            return
        case = _structured_settings_cases[_structured_settings_index]
        _structured_settings_index += 1
        try:
            _settings_dialog = _prepare_structured_settings_case(case)
        except Exception as exc:
            if _structured_settings_geometry_snapshot is not None:
                _restore_geometry_snapshot(_structured_settings_geometry_snapshot)
                _structured_settings_geometry_snapshot = None
            _record_structured_case_exception(case, exc)
            return
        active_dialog = _settings_dialog
        QTimer.singleShot(
            120,
            lambda: _activate_structured_settings_case(case),
        )
        active_dialog.exec()
        if _settings_dialog is active_dialog:
            _close_settings_dialog()
        if _structured_settings_geometry_snapshot is not None:
            _restore_geometry_snapshot(_structured_settings_geometry_snapshot)
            _structured_settings_geometry_snapshot = None
    except Exception as exc:
        base._error("structured-settings-case", exc)


def _start_structured_settings_layout() -> None:
    global _structured_settings_cases, _structured_settings_index
    global _structured_settings_started, _structured_settings_pngs_before
    global _structured_settings_reports
    try:
        if not _structured_settings_required():
            _complete_stage()
            return
        spec = CAPTURE_PLAN.structured_settings_layout()
        _structured_settings_started = True
        _structured_settings_index = 0
        _structured_settings_cases = _structured_settings_case_matrix()
        _structured_settings_pngs_before = {
            str(path.relative_to(CAPTURE_ROOT)): base._sha256(path)
            for path in CAPTURE_ROOT.rglob("*.png")
        } if CAPTURE_ROOT.exists() else {}
        resolved = list(
            clamp_window_geometry(None, tuple(spec["work_area_logical"]))
        )
        _structured_settings_reports = {
            int(percent): {
                "id": "settings-font-{}".format(percent),
                "kind": "application-font-layout",
                "status": "failed",
                "application_font_percent": int(percent),
                "fixture_kind": "logical-work-area-equivalence",
                "work_area_logical": list(spec["work_area_logical"]),
                "resolved_window_geometry_logical": list(resolved),
                "pages": [],
            }
            for percent in spec["application_font_percents"]
        }
        base.REPORT["structured_settings_layout_matrix"] = {
            "status": "running",
            "case_ids": [case["id"] for case in _structured_settings_cases],
            "adds_png_frames": False,
            "png_count_before": len(_structured_settings_pngs_before),
        }
        base._write_report()
        QTimer.singleShot(120, _next_structured_settings_case)
    except Exception as exc:
        base._error("structured-settings-start", exc)


def _next_settings_case() -> None:
    global _settings_index, _settings_dialog
    try:
        _close_settings_dialog()
        if _settings_index >= len(_settings_cases):
            if _structured_settings_required():
                _start_structured_settings_layout()
            else:
                _complete_stage()
            return
        case = _settings_cases[_settings_index]
        _settings_index += 1
        _settings_dialog = _prepare_settings_case(case)
        active_dialog = _settings_dialog
        QTimer.singleShot(120, lambda: _activate_settings_case(case))
        # Match the production controller exactly: the local parented QDialog
        # owns an application-modal nested event loop until this case's capture
        # closes it.  This preserves macOS native decoration and Space behavior.
        active_dialog.exec()
        if _settings_dialog is active_dialog:
            _close_settings_dialog()
    except Exception as exc:
        base._error("settings-case-prepare", exc)


def _inspect_settings_case(case: Mapping[str, Any], attempt: int = 0) -> None:
    try:
        base._require(_settings_dialog is not None, "Settings dialog disappeared before capture")
        QApplication.processEvents()
        _position_visible_target(_settings_dialog, case)
        QApplication.processEvents()
        state = _settings_state(_settings_dialog, case)
    except Exception as exc:
        if attempt < 5:
            QTimer.singleShot(250, lambda: _inspect_settings_case(case, attempt + 1))
            return
        base.REPORT["last_failed_settings_case"] = {
            "case": dict(case),
            "error": "{}: {}".format(type(exc).__name__, exc),
        }
        base._write_report()
        _exit_active_settings_exec()
        base._error(str(case.get("id", "settings-inspect")), exc)
        return

    validation_error: Exception | None = None
    try:
        _validate_settings_state(case, state)
    except Exception as exc:
        if attempt < 5:
            QTimer.singleShot(250, lambda: _inspect_settings_case(case, attempt + 1))
            return
        validation_error = exc
        base.REPORT.setdefault("settings_case_failures", {})[
            str(case.get("id", "settings-inspect"))
        ] = {
            "error": "{}: {}".format(type(exc).__name__, exc),
            "case": dict(case),
            "state": dict(state),
        }
        base.REPORT["last_failed_settings_case"] = {
            "case": dict(case),
            "error": "{}: {}".format(type(exc).__name__, exc),
        }
        base._write_report()

    capture_state = dict(state)
    capture_state["layout_assertions"] = (
        "failed" if validation_error is not None else "passed"
    )
    if validation_error is not None:
        capture_state["layout_assertion_error"] = "{}: {}".format(
            type(validation_error).__name__,
            validation_error,
        )
    try:
        _capture_settings(_settings_dialog, case, capture_state)
    except Exception as exc:
        _exit_active_settings_exec()
        base._error(str(case.get("id", "settings-capture")), exc)
        return
    _exit_active_settings_exec()
    QTimer.singleShot(120, _next_settings_case)


def _start_settings() -> None:
    global _settings_cases, _settings_index, _settings_started
    try:
        _settings_started = True
        _record_geometry_contract_assertions()
        _settings_index = 0
        if base.STAGE == "initial":
            _settings_cases = _settings_page_cases() + _settings_contract_cases()
        else:
            _settings_cases = CAPTURE_PLAN.cases(
                CAPTURE_PROFILE,
                stage="restart",
                component="settings",
                include_ids=REQUESTED_CAPTURE_IDS,
            )
        expected_count = len(CAPTURE_PLAN.ids(
            CAPTURE_PROFILE,
            stage=base.STAGE,
            component="settings",
            include_ids=REQUESTED_CAPTURE_IDS,
        ))
        base._require(
            len(_settings_cases) == expected_count,
            "Settings matrix differs from the resolved capture plan",
        )
        base.REPORT["settings_matrix"] = {
            "case_count": len(_settings_cases),
            "case_ids": [case["id"] for case in _settings_cases],
            "widget_tree": "one-native-qt-tree",
            "embedded_web_content": "none",
            "window_fresh_open_capture": "complete-decorated-parented-resizable-application-modal-dialog",
            "settings_profile_ceiling": {"captures": 41, "contact_sheets": 11},
        }
        base._write_report()
        if not _settings_cases:
            if _structured_settings_required():
                _start_structured_settings_layout()
            else:
                _complete_stage()
            return
        QTimer.singleShot(120, _next_settings_case)
    except Exception as exc:
        base._error("settings-matrix", exc)


def _persist_restart_state() -> None:
    global _preserve_geometry_for_restart
    config = normalize_config({})
    config["appearance"].update(preset="Graphite", mode="dark")
    config["heatmap"]["calendar_view"] = "year"
    config["heatmap"]["presets_by_theme"]["Graphite"] = "Plum"
    config["events"]["sort"] = "name"
    mw.addonManager.writeConfig(base._controller.package, config)
    readback = normalize_config(mw.addonManager.getConfig(base._controller.package))
    base._require(readback == config, "restart configuration did not persist exactly")

    screen = _settings_screen()
    available_rect = screen.availableGeometry()
    parent_rect = mw.frameGeometry()
    available = (
        available_rect.x(),
        available_rect.y(),
        available_rect.width(),
        available_rect.height(),
    )
    parent = (
        parent_rect.x(),
        parent_rect.y(),
        parent_rect.width(),
        parent_rect.height(),
    )
    requested = (
        parent_rect.center().x() - 590,
        parent_rect.center().y() - 400,
        1180,
        800,
    )
    expected_geometry = clamp_window_geometry(
        requested,
        available,
        parent=parent,
    )
    original_geometry = _rect_payload(_geometry_preference_before_probe)
    original_screen = (
        str(_geometry_screen_preference_before_probe or "")
        if _geometry_screen_preference_was_present
        else ""
    )
    original_available = _rect_payload(
        _geometry_available_preference_before_probe
    )
    original_previous_geometry = _rect_payload(
        _previous_geometry_preference_before_probe
    )
    original_legacy_geometry = _rect_payload(
        _legacy_geometry_preference_before_probe
    )
    base._require(
        not _geometry_preference_was_present or original_geometry is not None,
        "pre-probe Settings geometry is not a logical QRect",
    )
    base._require(
        not _geometry_available_preference_was_present
        or original_available is not None,
        "pre-probe Settings available bounds are not a logical QRect",
    )
    base._require(
        not _previous_geometry_preference_was_present
        or original_previous_geometry is not None,
        "pre-probe v3 Settings geometry is not a logical QRect",
    )
    base._require(
        not _legacy_geometry_preference_was_present
        or original_legacy_geometry is not None,
        "pre-probe legacy Settings geometry is not a logical QRect",
    )
    marker = {
        "schema_version": 3,
        "release": RELEASE,
        "original_was_present": _geometry_preference_was_present,
        "original_geometry": original_geometry,
        "original_screen_was_present": _geometry_screen_preference_was_present,
        "original_screen": original_screen,
        "original_available_was_present": _geometry_available_preference_was_present,
        "original_available": original_available,
        "original_dpr_was_present": _geometry_dpr_preference_was_present,
        "original_dpr": (
            _geometry_dpr_preference_before_probe
            if _geometry_dpr_preference_was_present
            else None
        ),
        "original_previous_geometry_was_present": _previous_geometry_preference_was_present,
        "original_previous_geometry": original_previous_geometry,
        "original_previous_screen_was_present": _previous_geometry_screen_preference_was_present,
        "original_previous_screen": (
            str(_previous_geometry_screen_preference_before_probe or "")
            if _previous_geometry_screen_preference_was_present
            else ""
        ),
        "original_legacy_was_present": _legacy_geometry_preference_was_present,
        "original_legacy_geometry": original_legacy_geometry,
        "expected_geometry": list(expected_geometry),
        "available_geometry": list(available),
        "logical_coordinates_only": True,
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        _geometry_restart_marker.write_text(
            json.dumps(marker, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_KEY,
            QRect(*expected_geometry),
        )
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_SCREEN_KEY,
            screen.name(),
        )
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_AVAILABLE_KEY,
            QRect(*available),
        )
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_DPR_KEY,
            float(screen.devicePixelRatio()),
        )
        _geometry_store.sync()
        stored_geometry = _rect_payload(
            _geometry_store.value(SETTINGS_GEOMETRY_KEY)
        )
        base._require(
            stored_geometry == list(expected_geometry),
            "Settings logical geometry did not persist exactly",
        )
        base._require(
            expected_geometry[2:] == (1180, 800),
            "1180x800 Settings restore fixture does not fit the native screen",
        )
    except Exception:
        try:
            _geometry_restart_marker.unlink()
        except OSError:
            pass
        raise
    _preserve_geometry_for_restart = True
    base.REPORT["persistence_write"] = {
        "status": "passed",
        "calendar_view": "year",
        "theme": "Graphite",
        "palette": "Plum",
        "events_sort": "name",
        "settings_window_policy": "resizable-clamped-parented-dialog-exec",
        "settings_window_geometry": list(expected_geometry),
        "settings_window_geometry_units": "logical-css-pixels",
    }


def _complete_stage() -> None:
    try:
        _close_settings_dialog()
        _restore_application_font()
        smoke = base.REPORT.get("multi_deck_new_limit_smoke", {})
        base._require(smoke.get("status") == "passed", "scheduler-authoritative multi-deck smoke did not pass")
        comparison = base.REPORT.get("native_statistics_comparison", {})
        base._require(comparison.get("status") == "passed", "native statistics comparison did not pass")
        capture_ids = set(base.REPORT.get("captures", {}))
        expected = set(CAPTURE_PLAN.ids(
            CAPTURE_PROFILE,
            stage=base.STAGE,
            include_ids=REQUESTED_CAPTURE_IDS,
        ))
        base._require(
            capture_ids == expected,
            "{} {} native evidence matrix differs from the resolved capture plan".format(
                CAPTURE_PROFILE, base.STAGE
            ),
        )
        expected_statistics = set(CAPTURE_PLAN.tagged_ids(
            "statistics_accuracy",
            CAPTURE_PROFILE,
            stage=base.STAGE,
        ))
        if REQUESTED_CAPTURE_IDS is not None:
            expected_statistics.intersection_update(REQUESTED_CAPTURE_IDS)
        if expected_statistics:
            base._require(
                set(base.REPORT.get("statistics_responsive_parity", {})) == expected_statistics,
                "production statistics responsive parity is incomplete",
            )
        if base.STAGE == "initial":
            _persist_restart_state()

        if base.STAGE == "restart":
            config = normalize_config(mw.addonManager.getConfig(base._controller.package))
            base._require(config["heatmap"]["calendar_view"] == "year", "Year did not persist after restart")
            base._require(config["events"]["sort"] == "name", "name event sort did not persist after restart")
            base.REPORT["persistence_readback"] = {
                "status": "passed",
                "calendar_view": "year",
                "events_sort": "name",
                "settings_window_policy": "restored-and-clamped-on-current-screen",
                "settings_window_geometry": _read_geometry_restart_marker().get(
                    "expected_geometry"
                ),
                "settings_state": "clean",
            }
        base.REPORT["capture_plan"]["resolved_stage_capture_ids"] = list(
            CAPTURE_PLAN.ids(
                CAPTURE_PROFILE,
                stage=base.STAGE,
                include_ids=REQUESTED_CAPTURE_IDS,
            )
        )
        settings_failures = base.REPORT.get("settings_case_failures", {})
        structured_layout = base.REPORT.get("structured_settings_layout", {})
        structured_layout_failed = bool(
            _structured_settings_required()
            and (
                not isinstance(structured_layout, Mapping)
                or structured_layout.get("status") != "passed"
            )
        )
        base.REPORT["capture_completion_status"] = "complete"
        base.REPORT["quality_status"] = (
            "review-failed"
            if settings_failures or structured_layout_failed
            else "passed"
        )
        base.REPORT["status"] = (
            "failed"
            if settings_failures or structured_layout_failed
            else "passed"
        )
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
        # Focused Settings profiles may omit every production frame, so they
        # must establish the requested monitor themselves after isolation.
        available = base._qa_screen().availableGeometry()
        mw.move(available.center().x() - mw.width() // 2,
                available.center().y() - mw.height() // 2)
        _prepare_native_statistics_fixture()
        planned_production = CAPTURE_PLAN.cases(
            CAPTURE_PROFILE,
            stage=base.STAGE,
            component="production",
            include_ids=REQUESTED_CAPTURE_IDS,
        )
        if not planned_production:
            base.REPORT["capture_scope"] = "{}-no-production-frames".format(CAPTURE_PROFILE)
            base.REPORT["production_matrix"] = {
                "case_count": 0,
                "case_ids": [],
                "capture_policy": "omitted by the resolved capture profile",
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
        base._require(
            len(base._cases) == len(planned_production),
            "production matrix differs from the resolved capture plan",
        )
        base._case_index = 0
        base.REPORT["production_matrix"] = {
            "case_count": len(base._cases),
            "case_ids": [case["id"] for case in base._cases],
            "host": "actual isolated Anki main Deck Browser",
            "renderer": "exact installed production controller and renderer",
            "capture_profile": CAPTURE_PROFILE,
            "capture_plan_sha256": CAPTURE_PLAN.sha256,
        }
        base._write_report()
        QTimer.singleShot(200, base._next_case)
    except Exception as exc:
        base._error("production-matrix-{}".format(base.STAGE), exc)


base._finish_stage = _finish_production_stage
base._start_case_matrix = _start_case_matrix


if ENABLED:
    application = QApplication.instance()
    if application is not None:
        application.setQuitOnLastWindowClosed(False)
        application.aboutToQuit.connect(_restore_geometry_preference)
    gui_hooks.profile_did_open.append(base._profile_opened)
    QTimer.singleShot(1100, base._begin)
