"""Fail-closed native production and Settings probe for release 1.8.7.

The disposable helper add-on installs this module as ``__init__.py`` and the
retained 1.8.4 production harness as ``_probe_base.py``.  The retained harness
supplies exact-package identity, scheduler-limit, Deck Browser mounting, and
native capture plumbing.  This module replaces its release matrix and
assertions with the canonical corrected 1.8.7 production and Settings contract.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from aqt import gui_hooks, mw
from aqt.qt import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFont,
    QLineEdit,
    QPainter,
    QPixmap,
    QPoint,
    QRect,
    QScrollArea,
    QSettings,
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
    SETTINGS_GEOMETRY_KEY,
    SETTINGS_GEOMETRY_SCREEN_KEY,
    SettingsDialog,
)
from home_dashboard_overhaul.settings_model import (
    clamp_window_geometry,
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
_settings_cases: list[dict[str, Any]] = []
_settings_index = 0
_settings_dialog: SettingsDialog | None = None
_settings_started = False
_geometry_store = QSettings()
_geometry_preference_was_present = _geometry_store.contains(SETTINGS_GEOMETRY_KEY)
_geometry_preference_before_probe = _geometry_store.value(SETTINGS_GEOMETRY_KEY)
_geometry_screen_preference_was_present = _geometry_store.contains(
    SETTINGS_GEOMETRY_SCREEN_KEY
)
_geometry_screen_preference_before_probe = _geometry_store.value(
    SETTINGS_GEOMETRY_SCREEN_KEY
)
_geometry_restart_marker = OUTPUT_ROOT / "settings-geometry-restart.json"
_preserve_geometry_for_restart = False
_legacy_geometry_key = "home_dashboard_overhaul/settings_dialog_geometry/v2"


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
            (1000, 700)
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
        config["events"]["items"].insert(0, {
            "id": "evt-long",
            "name": "Pediatrics longitudinal review conference with an intentionally long title",
            "date": "2026-08-29",
            "archived": False,
            "created_at": "2026-08-24T09:03:00-05:00",
            "archived_at": "",
        })
    if special == "future-off":
        config["heatmap"]["show_due_forecast"] = False
    elif special == "future-on":
        config["heatmap"]["show_due_forecast"] = True
        config["heatmap"]["forecast_days"] = 90
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
            font_color="#F0E3B2",
            theme_aware_color=False,
            quotes=["The Lord is my strength and my song.<br> - Psalm 118:14 (NLT)"],
        )
    elif special == "bible-long-row":
        config["bible"]["quotes"][0] = (
            "The steadfast love of the Lord never ceases; his mercies never come to an end, "
            "and this deliberately extended excerpt verifies the complete two-line delegate layout."
            "<br> - Lamentations 3:22-23 Extended Reference (NLT)"
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


def _set_geometry_fixture(case: Mapping[str, Any], available: Any) -> None:
    """Prepare only the persisted input; product code performs the clamp."""

    special = str(case.get("special", ""))
    if base.STAGE == "restart" and special == "restart-persistence":
        _geometry_store.sync()
        return
    _geometry_store.remove(SETTINGS_GEOMETRY_KEY)
    _geometry_store.remove(SETTINGS_GEOMETRY_SCREEN_KEY)
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
    marker_rect = _rect_payload(marker.get("original_geometry"))
    marker_present = bool(marker.get("original_was_present"))
    if marker_present and marker_rect is not None:
        _geometry_store.setValue(SETTINGS_GEOMETRY_KEY, QRect(*marker_rect))
        marker_screen = str(marker.get("original_screen") or "")
        if marker_screen:
            _geometry_store.setValue(SETTINGS_GEOMETRY_SCREEN_KEY, marker_screen)
        else:
            _geometry_store.remove(SETTINGS_GEOMETRY_SCREEN_KEY)
    elif marker and not marker_present:
        _geometry_store.remove(SETTINGS_GEOMETRY_KEY)
        _geometry_store.remove(SETTINGS_GEOMETRY_SCREEN_KEY)
    elif _geometry_preference_was_present:
        _geometry_store.setValue(
            SETTINGS_GEOMETRY_KEY,
            _geometry_preference_before_probe,
        )
    else:
        _geometry_store.remove(SETTINGS_GEOMETRY_KEY)
    if not marker:
        if _geometry_screen_preference_was_present:
            _geometry_store.setValue(
                SETTINGS_GEOMETRY_SCREEN_KEY,
                _geometry_screen_preference_before_probe,
            )
        else:
            _geometry_store.remove(SETTINGS_GEOMETRY_SCREEN_KEY)
    _geometry_store.remove(_legacy_geometry_key)
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
        width = min(max(920, int(target_width)), available.width() - 96)
        target_height = 800 if int(target_width) >= 1280 else 760
        height = min(max(640, target_height), available.height() - 96)
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
        if special == "discard":
            dialog._revert_changes()
        elif special == "close-confirmation":
            dialog.request_close()
        elif special == "save-in-progress":
            dialog._saving = True
            dialog.footer.set_error()
            dialog._set_status("saving", "Saving…")
            dialog.save_button.setText("Saving…")
            dialog.save_button.setEnabled(False)
            dialog.close_button.setEnabled(False)
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
                dialog._staged_edited_event_ids.add("evt-a")
                dialog._qa_failure_baseline_before = deepcopy(dialog.draft.baseline)
                dialog._qa_failure_values_before = deepcopy(dialog.draft.values)
                dialog._qa_failure_manual_before = dialog.pending_manual_quote
                dialog._qa_failure_event_ids_before = set(
                    dialog._staged_edited_event_ids
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
                finally:
                    base._controller.save_config = original
            else:
                dialog._latest_stored_config = lambda: deepcopy(dialog.draft.baseline)
                dialog._save()
    elif special == "legacy-route":
        dialog.open_page("calendar")
    return dialog


def _activate_settings_case(case: Mapping[str, Any]) -> None:
    """Finish visible-only setup inside the production-equivalent exec loop."""

    try:
        base._require(_settings_dialog is not None, "Settings dialog disappeared before activation")
        dialog = _settings_dialog
        special = str(case.get("special", ""))
        if case.get("family") == "settings-pages" and case.get("width") == "full":
            dialog.showMaximized()
        if special == "event-editor-open":
            base._require(dialog._select_event_id("evt-a", False), "event fixture is missing")
            event = dialog._selected_event()
            base._require(event is not None, "event editor has no selected event")
            editor = EventEditDialog(dialog, event)
            editor.setModal(True)
            editor.show()
            dialog._qa_event_editor = editor
            editor.raise_()
            editor.activateWindow()
        elif special == "about-bottom":
            scroll = dialog.stack.currentWidget()
            if isinstance(scroll, QScrollArea):
                scroll.verticalScrollBar().setValue(
                    scroll.verticalScrollBar().maximum()
                )
        dialog.raise_()
        dialog.activateWindow()
        QApplication.processEvents()
        editor = getattr(dialog, "_qa_event_editor", None)
        if editor is not None:
            editor.raise_()
            editor.activateWindow()
        QTimer.singleShot(720, lambda: _inspect_settings_case(case))
    except Exception as exc:
        _exit_active_settings_exec()
        base._error("{}-activate".format(case.get("id", "settings")), exc)


def _global_rect(widget: QWidget) -> QRect:
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


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
    for widget in current.widget().findChildren(QWidget):
        if not isinstance(widget, interactive_types) or not widget.isVisibleTo(dialog):
            continue
        rect = _global_rect(widget)
        if rect.bottom() < viewport_rect.top() or rect.top() > viewport_rect.bottom():
            continue
        if rect.left() < viewport_rect.left() - 1 or rect.right() > viewport_rect.right() + 1:
            label = widget.accessibleName() or widget.objectName() or type(widget).__name__
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
    footer_rect = _global_rect(dialog.footer_shell)
    about_item = dialog.nav.item(dialog.nav_rows.get("about_support", -1))
    about_item_height = dialog.nav.visualItemRect(about_item).height() if about_item is not None else 0
    tokens = getattr(dialog, "_hdo_theme_tokens", {})
    status_rect = _global_rect(dialog.status_label) if dialog.status_label.isVisible() else QRect()
    error_rect = _global_rect(dialog.footer.error_panel) if dialog.footer.error_panel.isVisible() else QRect()
    feedback_intersection = status_rect.intersected(error_rect)
    save_rect = _global_rect(dialog.save_button) if dialog.save_button is not None else QRect()
    prompt_titles = [
        str(label.text())
        for label in dialog.findChildren(QWidget, "SettingsPromptTitle")
        if callable(getattr(label, "text", None)) and label.isVisibleTo(dialog)
    ]
    shell_rect = QRect(
        dialog.settings_shell.mapTo(dialog, QPoint(0, 0)),
        dialog.settings_shell.size(),
    )
    event_editor = getattr(dialog, "_qa_event_editor", None)
    rendered_preview_types = {
        "DashboardCardPreview",
        "VerseCardPreview",
        "HeatmapPresetCard",
    }
    visible_add_event_ctas = [
        button
        for button in dialog.findChildren(QAbstractButton)
        if button.text().replace("&", "").strip() == "Add event"
        and button.isVisibleTo(dialog)
    ]
    event_row_height = 0
    if active_tree is not None and active_tree.topLevelItemCount():
        event_row_height = active_tree.topLevelItem(0).sizeHint(0).height()
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
        "nav_width": dialog.nav.width(),
        "nav_visible": dialog.sidebar_panel.isVisible(),
        "compact_nav_visible": dialog.compact_nav.isVisible(),
        "compact_nav_elision_disabled": dialog.compact_nav.elideMode() == Qt.TextElideMode.ElideNone,
        "nav_word_wrap": dialog.nav.wordWrap(),
        "nav_elision_disabled": dialog.nav.textElideMode() == Qt.TextElideMode.ElideNone,
        "nav_about_visual_height": about_item_height,
        "nav_font_line_spacing": dialog.nav.fontMetrics().lineSpacing(),
        "body_width": dialog.body_shell.width(),
        "screen_compact_fallback": bool(dialog._screen_compact_fallback),
        "page_count": dialog.stack.count(),
        "visible_page_scroller_count": sum(
            isinstance(dialog.stack.widget(index), QScrollArea)
            and dialog.stack.widget(index).isVisibleTo(dialog)
            for index in range(dialog.stack.count())
        ),
        "main_page_scroller": isinstance(current, QScrollArea),
        "horizontal_scroll_maximum": current.horizontalScrollBar().maximum() if isinstance(current, QScrollArea) else -1,
        "horizontal_scroll_disabled": isinstance(current, QScrollArea) and current.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        "visible_interactive_overflow": _visible_interactive_overflow(dialog, current),
        "clipped_button_labels": _clipped_button_labels(dialog),
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
        "required_page_bottom_margin": 36,
        "save_text": dialog.save_button.text() if dialog.save_button is not None else "",
        "save_enabled": dialog.save_button.isEnabled() if dialog.save_button is not None else False,
        "close_text": dialog.close_button.text() if dialog.close_button is not None else "",
        "close_enabled": dialog.close_button.isEnabled() if dialog.close_button is not None else False,
        "discard_visible": dialog.revert_button.isVisible(),
        "save_error_visible": dialog.footer.error_panel.isVisible(),
        "save_error_text": dialog.save_error.text(),
        "save_error_label_clipped": (
            dialog.footer.error_panel.isVisible()
            and (
                dialog.save_error.fontMetrics().horizontalAdvance(dialog.save_error.text())
                > dialog.save_error.contentsRect().width()
                or dialog.save_error.fontMetrics().lineSpacing()
                > dialog.save_error.contentsRect().height()
            )
        ),
        "save_error_details": dialog.footer.details_text.text(),
        "save_error_details_collapsed": not dialog.footer.details_text.isVisible(),
        "status": dialog.status_label.text(),
        "status_visible": dialog.status_label.isVisible(),
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
            not hasattr(dialog, "_qa_failure_event_ids_before")
            or dialog._staged_edited_event_ids
            == dialog._qa_failure_event_ids_before
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
        "event_editor_open": bool(getattr(dialog, "_qa_event_editor", None) and dialog._qa_event_editor.isVisible()),
        "event_editor_size": (
            [event_editor.width(), event_editor.height()]
            if event_editor is not None
            else []
        ),
        "event_list_flexible": all(
            view is None
            or (
                260 <= view.minimumHeight()
                and view.maximumHeight() >= 16777215
            )
            for view in (active_tree, archived_tree)
        ),
        "visible_add_event_cta_count": len(visible_add_event_ctas),
        "event_row_height": event_row_height,
        "quote_count": quote_model.rowCount() if quote_model is not None else 0,
        "quote_matching_count": quote_model.matching_count if quote_model is not None else 0,
        "quote_list_flexible": quote_list is None or (
            260 <= quote_list.minimumHeight()
            and quote_list.maximumHeight() >= 16777215
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
        "settings_shell_maximum": dialog.settings_shell.maximumWidth(),
        "settings_shell_width": dialog.settings_shell.width(),
        "settings_shell_center_delta": abs(
            shell_rect.center().x() - dialog.rect().center().x()
        ),
        "rendered_previews_absent": (
            not any(
                hasattr(dialog, attribute)
                for attribute in (
                    "appearance_preview",
                    "verse_preview",
                    "preset_swatch",
                    "heatmap_preset_cards",
                )
            )
            and not any(
                type(widget).__name__ in rendered_preview_types
                for widget in dialog.findChildren(QWidget)
            )
        ),
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
        base._require(state.get("minimum_size") == [920, 640], "Settings minimum size is not 920x640 logical px")
    base._require(state.get("nav_width") == 184, "Settings rail is not 184px")
    base._require(not bool(state.get("nav_word_wrap")), "Settings rail wraps labels")
    base._require(bool(state.get("nav_elision_disabled")), "Settings rail elides long labels")
    base._require(bool(state.get("compact_nav_elision_disabled")), "compact Settings tabs elide labels")
    compact_required = bool(state.get("screen_compact_fallback"))
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
    base._require(state.get("page_count") == 4, "Settings does not own exactly four pages")
    expected_visible_scrollers = 0 if special == "close-confirmation" else 1
    base._require(
        state.get("visible_page_scroller_count") == expected_visible_scrollers,
        "Settings does not expose exactly the expected page-body scroller count",
    )
    base._require(bool(state.get("main_page_scroller")), "active Settings page is not the main scroller")
    base._require(state.get("horizontal_scroll_maximum") == 0, "Settings page has horizontal overflow")
    base._require(bool(state.get("horizontal_scroll_disabled")), "Settings page permits horizontal scrolling")
    base._require(not state.get("visible_interactive_overflow"), "visible Settings controls escape the content viewport: {}".format(state.get("visible_interactive_overflow")))
    base._require(not state.get("clipped_button_labels"), "Settings buttons clip text: {}".format(state.get("clipped_button_labels")))
    if special != "close-confirmation":
        base._require(bool(state.get("footer_after_body")), "Settings footer is not the final layout row")
        base._require(not bool(state.get("footer_overlaps_page_viewport")), "Settings footer overlaps the active page viewport")
    base._require(
        int(state.get("page_bottom_margin", 0)) >= int(state.get("required_page_bottom_margin", 0)),
        "Settings page lacks footer-height bottom clearance",
    )
    base._require(state.get("close_text") == "Close", "Close button label is unstable")
    base._require(state.get("header_height") == 72, "Settings page header is not fixed at 72px")
    base._require(state.get("footer_minimum_height") == 60, "Settings footer is not fixed at a 60px minimum")
    if special != "close-confirmation":
        base._require(bool(state.get("sidebar_spans_shell")), "Settings sidebar does not span header body and footer")
    base._require(state.get("page_maximum_width") == 980, "Settings page is not capped at 980px")
    base._require(state.get("settings_shell_maximum") == 1240, "Settings inner shell is not capped at 1240px")
    expected_shell_width = min(int(state.get("window_size", [0])[0]), 1240)
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
    base._require(float(state.get("minimum_visible_text_pixels", 0)) >= 11.5, "visible Settings text falls below the 12px baseline")
    base._require(float(state.get("selection_primary_contrast", 0)) >= 4.5, "selected-row primary text contrast is insufficient")
    base._require(float(state.get("selection_secondary_contrast", 0)) >= 4.5, "selected-row secondary text contrast is insufficient")
    base._require(bool(state.get("event_list_flexible")), "Events list region is not flexible")
    base._require(bool(state.get("quote_list_flexible")), "Verse list region is not flexible")
    base._require(bool(state.get("rendered_previews_absent")), "a rendered Settings preview remains")
    base._require(bool(state.get("custom_color_well_present")), "the custom color input well is missing")
    if special == "events-empty":
        base._require(state.get("event_active_count") == 0 and state.get("event_archived_count") == 0, "empty Events state is populated")
        base._require(state.get("event_empty_title") == "No events yet", "empty Events copy is incorrect")
    if state.get("section") == "events":
        base._require(state.get("visible_add_event_cta_count") == 1, "Events does not expose exactly one header-level Add event action")
        if int(state.get("event_active_count", 0)):
            base._require(state.get("event_row_height") == 54, "Event rows are not 54px high")
    if special == "events-populated":
        base._require(state.get("event_active_count") == 2, "populated Events state is incomplete")
    if special == "event-editor-open":
        base._require(bool(state.get("event_editor_open")), "event row did not open its editor")
        base._require(state.get("event_editor_size") == [560, 320], "event editor is not 560x320 logical px")
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
    if special == "bible-custom-invalid":
        base._require(bool(state.get("font_color_invalid")), "invalid custom color was accepted")
        base._require(not bool(state.get("save_enabled")), "invalid custom color did not block Save")
        base._require(not bool(state.get("save_error_visible")), "invalid custom color duplicates its inline error in the footer")
        base._require(state.get("font_color_inline_error") == "Enter a valid #RRGGBB color.", "invalid custom color lacks the single inline validation error")
        base._require(state.get("status") == "Fix 1 error to save", "footer validation status is incorrect")
    if special == "bible-long-row":
        base._require(state.get("quote_count") == 483, "complete verse model was capped")
    if special == "future-off":
        base._require(bool(state.get("forecast_range_visible")), "Future range moved when forecasting was disabled")
        base._require(not bool(state.get("forecast_range_enabled")), "Future range remains enabled while forecasting is off")
    if special == "future-on":
        base._require(bool(state.get("forecast_range_visible")), "Future range is hidden while forecasting is on")
        base._require(bool(state.get("forecast_range_enabled")), "Future range is disabled while forecasting is on")
    if special == "advanced-appearance":
        base._require(bool(state.get("advanced_appearance_expanded")), "Advanced appearance did not expand")
    if special == "dirty":
        base._require(bool(state.get("discard_visible")), "dirty Settings does not expose Discard changes")
        base._require(bool(state.get("save_enabled")), "dirty Settings does not enable Save")
        base._require("unsaved change" in str(state.get("status")), "dirty count is missing")
    if special == "discard":
        base._require(not bool(state.get("discard_visible")), "Discard did not restore the saved baseline")
        base._require(not bool(state.get("save_enabled")), "Save remains enabled after Discard")
    if special == "close-confirmation":
        base._require(state.get("close_prompt_titles") == ["Discard unsaved changes?"], "dirty Close did not show the native confirmation page")
    if special == "save-in-progress":
        base._require(state.get("save_text") == "Saving…", "save-in-progress button text is incorrect")
        base._require(not bool(state.get("save_enabled")) and not bool(state.get("close_enabled")), "save-in-progress submission remains enabled")
    if special == "save-success":
        base._require("Saved" in str(state.get("status")), "successful save did not update the baseline/status")
        base._require(not bool(state.get("discard_visible")), "successful save remains dirty")
        base._require(not bool(state.get("save_enabled")), "Save remains enabled after success")
    if special == "save-error-production":
        base._require(bool(state.get("save_error_visible")), "save failure is not local to the footer")
        base._require(not bool(state.get("status_visible")), "save failure overlaps the dirty status")
        base._require(state.get("save_error_text") == "Save failed. Your changes are still available.", "save failure copy is not production-formatted")
        base._require(not bool(state.get("save_error_label_clipped")), "save failure copy is clipped in the fixed footer")
        base._require(state.get("save_error_details") == "fixture write failure detail", "technical save detail is not stored separately")
        base._require(bool(state.get("save_error_details_collapsed")), "technical save detail is exposed by default")
        base._require(bool(state.get("save_enabled")), "Save is disabled after failure")
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
        base._require(state.get("section") == "dashboard", "legacy Calendar route did not activate Dashboard")
        base._require(state.get("normalized_route") == "dashboard#calendar", "legacy Calendar route did not settle on Calendar display")
        base._require(
            0 <= int(state.get("calendar_anchor_viewport_y", -1)) <= 4,
            "legacy Calendar route exposes a clipped preceding card",
        )
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
        expected_window = "#F3F5F7" if expected == "light" else "#0D131A"
        base._require(state.get("settings_window_token") == expected_window, "Settings shell did not follow the Anki theme")
    base._require(bool(state.get("parented_to_anki")), "Settings is not parented to Anki")
    base._require(
        bool(state.get("modal_capture_lifecycle")),
        "Settings capture does not preserve modal ownership",
    )


def _settings_client_capture(dialog: SettingsDialog) -> Any:
    """Render the Settings client and any parented editor into one pixmap."""

    pixmap = dialog.grab()
    editor = getattr(dialog, "_qa_event_editor", None)
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


def _capture_settings(dialog: SettingsDialog, case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    QApplication.processEvents()
    screen = _settings_screen(dialog)
    screen_geometry = screen.geometry()
    capture_parent_with_dialog = str(case.get("special", "")) == "window-fresh-open"
    capture_complete_frame = case.get("family") == "settings-pages"
    if capture_parent_with_dialog:
        frame = mw.frameGeometry()
        expected_width, expected_height = frame.width(), frame.height()
        pixmap = screen.grabWindow(
            0,
            frame.x() - screen_geometry.x(),
            frame.y() - screen_geometry.y(),
            expected_width,
            expected_height,
        )
        method = "QScreen.grabWindow-anki-with-fresh-settings-dialog"
    elif capture_complete_frame:
        frame = dialog.frameGeometry()
        expected_width, expected_height = frame.width(), frame.height()
        pixmap = screen.grabWindow(
            0,
            frame.x() - screen_geometry.x(),
            frame.y() - screen_geometry.y(),
            expected_width,
            expected_height,
        )
        method = "QScreen.grabWindow-complete-decorated-settings-frame"
    else:
        origin = dialog.mapToGlobal(QPoint(0, 0))
        expected_width, expected_height = dialog.width(), dialog.height()
        pixmap = screen.grabWindow(
            0,
            origin.x() - screen_geometry.x(),
            origin.y() - screen_geometry.y(),
            expected_width,
            expected_height,
        )
        method = "QScreen.grabWindow-screen-client-crop"

    reference = _settings_client_capture(dialog)
    if capture_parent_with_dialog or capture_complete_frame:
        reference_origin = dialog.mapToGlobal(QPoint(0, 0)) - frame.topLeft()
    else:
        reference_origin = QPoint(0, 0)
    surface_match_ratio = _settings_surface_match_ratio(
        pixmap,
        reference,
        captured_logical_size=(expected_width, expected_height),
        reference_logical_size=(dialog.width(), dialog.height()),
        reference_origin=reference_origin,
    )

    # Retry after explicitly ordering the asynchronous probe dialog.  Size and
    # color-count checks alone cannot distinguish Settings from the Dashboard
    # pixels underneath it.
    for _attempt in range(3):
        if surface_match_ratio >= 0.55:
            break
        dialog.raise_()
        dialog.activateWindow()
        editor = getattr(dialog, "_qa_event_editor", None)
        if editor is not None:
            editor.raise_()
            editor.activateWindow()
        QApplication.processEvents()
        if capture_parent_with_dialog:
            pixmap = screen.grabWindow(
                0,
                frame.x() - screen_geometry.x(),
                frame.y() - screen_geometry.y(),
                expected_width,
                expected_height,
            )
        elif capture_complete_frame:
            pixmap = screen.grabWindow(
                0,
                frame.x() - screen_geometry.x(),
                frame.y() - screen_geometry.y(),
                expected_width,
                expected_height,
            )
        else:
            origin = dialog.mapToGlobal(QPoint(0, 0))
            pixmap = screen.grabWindow(
                0,
                origin.x() - screen_geometry.x(),
                origin.y() - screen_geometry.y(),
                expected_width,
                expected_height,
            )
        surface_match_ratio = _settings_surface_match_ratio(
            pixmap,
            reference,
            captured_logical_size=(expected_width, expected_height),
            reference_logical_size=(dialog.width(), dialog.height()),
            reference_origin=reference_origin,
        )

    def composite_standard_context() -> Any:
        """Retain the modal context when macOS cannot sample another Space."""

        parent = mw.grab()
        settings = dialog.grab()
        base._require(not parent.isNull(), "native Anki fallback capture is null")
        base._require(not settings.isNull(), "native Settings fallback capture is null")
        dpr = max(
            1.0,
            float(parent.devicePixelRatio()),
            float(settings.devicePixelRatio()),
        )
        composite = QPixmap(
            max(1, round(expected_width * dpr)),
            max(1, round(expected_height * dpr)),
        )
        composite.setDevicePixelRatio(dpr)
        composite.fill(Qt.GlobalColor.transparent)
        frame_origin = frame.topLeft()
        parent_origin = mw.mapToGlobal(QPoint(0, 0)) - frame_origin
        settings_origin = dialog.mapToGlobal(QPoint(0, 0)) - frame_origin
        settings_width = settings.width() / max(1.0, float(settings.devicePixelRatio()))
        settings_height = settings.height() / max(1.0, float(settings.devicePixelRatio()))
        visible_width = (
            min(expected_width, settings_origin.x() + settings_width)
            - max(0, settings_origin.x())
        )
        visible_height = (
            min(expected_height, settings_origin.y() + settings_height)
            - max(0, settings_origin.y())
        )
        base._require(
            visible_width > 0 and visible_height > 0,
            "standard Settings fallback does not intersect the Anki window",
        )
        painter = QPainter(composite)
        try:
            painter.drawPixmap(parent_origin, parent)
            painter.drawPixmap(settings_origin, settings)
        finally:
            painter.end()
        return composite

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
    if capture_parent_with_dialog and (
        pixmap.isNull()
        or color_count < 3
        or abs(logical_width - expected_width) > 4
        or abs(logical_height - expected_height) > 4
        or surface_match_ratio < 0.55
    ):
        pixmap = composite_standard_context()
        color_count = base._sample_color_count(pixmap)
        method = "QWidget.grab-composited-anki-with-standard-settings-dialog-fallback"
        surface_match_ratio = _settings_surface_match_ratio(
            pixmap,
            reference,
            captured_logical_size=(expected_width, expected_height),
            reference_logical_size=(dialog.width(), dialog.height()),
            reference_origin=reference_origin,
        )
    elif not capture_parent_with_dialog and (
        pixmap.isNull()
        or color_count < 3
        or abs(logical_width - expected_width) > 4
        or abs(logical_height - expected_height) > 4
        or surface_match_ratio < 0.55
    ):
        fallback = reference
        fallback_colors = 0 if fallback.isNull() else base._sample_color_count(fallback)
        if not capture_complete_frame and not fallback.isNull() and fallback_colors >= 3:
            pixmap = fallback
            color_count = fallback_colors
            method = "QDialog.grab-composited-client-fallback"
            reference_origin = QPoint(0, 0)
            surface_match_ratio = 1.0

    pixmap, inferred_capture_scale = normalize_backing_scale(pixmap)
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
    base.REPORT["captures"][str(case["id"])] = {
        "file": str(path.relative_to(OUTPUT_ROOT)),
        "sha256": base._sha256(path),
        "component": "canonical-settings",
        "page": state.get("section"),
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
            "anki-window-with-fresh-settings-dialog"
            if capture_parent_with_dialog
            else (
                "complete-decorated-settings-window"
                if capture_complete_frame
                else "settings-dialog"
            )
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
    editor = getattr(dialog, "_qa_event_editor", None)
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
    editor = getattr(dialog, "_qa_event_editor", None)
    if editor is not None:
        editor.close()
        editor.deleteLater()
        dialog._qa_event_editor = None
    dialog.force_close()


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
            "window_fresh_open_capture": "parented-resizable-application-modal-dialog-with-parent",
            "settings_profile_ceiling": {"captures": 41, "contact_sheets": 11},
        }
        base._write_report()
        if not _settings_cases:
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
    base._require(
        not _geometry_preference_was_present or original_geometry is not None,
        "pre-probe Settings geometry is not a logical QRect",
    )
    marker = {
        "schema_version": 2,
        "release": RELEASE,
        "original_was_present": _geometry_preference_was_present,
        "original_geometry": original_geometry,
        "original_screen": original_screen,
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
        if _base_font is not None:
            QApplication.instance().setFont(_base_font)
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
        base.REPORT["capture_completion_status"] = "complete"
        base.REPORT["quality_status"] = (
            "review-failed" if settings_failures else "passed"
        )
        base.REPORT["status"] = "failed" if settings_failures else "passed"
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
        application.aboutToQuit.connect(_restore_geometry_preference)
    gui_hooks.profile_did_open.append(base._profile_opened)
    QTimer.singleShot(1100, base._begin)
