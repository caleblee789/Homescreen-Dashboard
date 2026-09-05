"""Eight native AnkiWeb presentation captures, with published defaults."""
import os
import subprocess

from aqt import mw
from aqt.qt import QApplication, QPoint, QTimer
from home_dashboard_overhaul.config_schema import normalize_config
from . import _release_probe as release
from . import _probe_base as base


original_gate = base._identity_gate
original_cases = release._build_production_cases
original_config = base._config_for
original_validate = base._validate_dom
original_capture = base._capture


def identity_gate():
    original_gate()
    command = subprocess.check_output(["/bin/ps", "-p", str(os.getpid()), "-o", "args="], text=True).strip()
    base._require(str(base.RUN_ROOT) in command and base.EXPECTED_PROFILE in command, "launch arguments do not identify this isolated base/profile")
    base._require(normalize_config({})["heatmap"]["show_due_forecast"] is False, "published future-due default is not off")
    base.REPORT["identity"]["process_arguments_verified"] = True
    base.REPORT["identity"]["normal_profile_window_excluded"] = "Caleb Meadows - Anki"


def gallery_cases():
    cases = original_cases()
    for case in cases:
        case["special"] = "no-due"
        case["tags"] = list(case.get("tags", [])) + ["ankiweb-presentation", "future-due-default-off"]
    return cases


def gallery_config(case):
    config = original_config(case)
    config["heatmap"]["show_due_forecast"] = normalize_config({})["heatmap"]["show_due_forecast"]
    return config


base.DOM_REPORT_SCRIPT = base.DOM_REPORT_SCRIPT.replace(
    "dueLegendCount:qa('.hdo-legend-due').filter(visible).length,",
    "dueLegendCount:qa('.hdo-legend-due').filter(visible).length,"
    "futureDueMarkerCount:qa('.hdo-calendar-day.is-future[data-due-level]:not([data-due-level=\"0\"])').length,"
    "eventText:qa('[data-hdo-context-event]').map(function(n){return n.textContent.trim();}).join(' '),",
)


def validate(case, state):
    original_validate(case, state)
    base._require(state.get("futureDueMarkerCount") == 0, "future due indicators remain visible")
    base._require(state.get("dueLegendCount") == 0, "Due cards legend remains visible")
    base._require(state.get("completionCount", 0) > 0, "review history is empty")
    base._require(state.get("eventMarkerCount", 0) >= 1, "event calendar marker is absent")
    base._require("Pediatrics review" in state.get("eventText", ""), "named upcoming event is absent")
    base._require(state.get("metricValues", {}).get("today.answers") == "186", "populated study statistics are absent")
    base._require(base._controller.config["heatmap"]["show_due_forecast"] is False, "capture config differs from the published default")


def capture(case, state):
    frame = mw.frameGeometry()
    origin = mw.deckBrowser.web.mapToGlobal(QPoint(0, 0))
    state["nativeWebOffsetInFrame"] = {"x": origin.x() - frame.x(), "y": origin.y() - frame.y()}
    state["showDueForecast"] = False
    original_capture(case, state)


def finish():
    try:
        base._require(set(base.REPORT["captures"]) == set(release.REQUESTED_CAPTURE_IDS), "the eight requested captures are incomplete")
        identity_gate()
        review_rows = mw.col.db.scalar("select count(*) from revlog")
        base._require(review_rows > 0, "isolated collection has no review history")
        base.REPORT.update(
            status="passed", capture_completion_status="complete",
            authority="eight-native-ankiweb-presentation-captures",
            scope="Eight selected themes with the published future-due default off; populated sample study data and an upcoming event.",
            review_history_rows=review_rows,
            default_show_due_forecast=False,
            release_validation_claimed=False,
        )
        base._write_report()
        QTimer.singleShot(450, QApplication.instance().quit)
    except Exception as exc:
        base._error("gallery-finish", exc)


base._identity_gate = identity_gate
release._build_production_cases = gallery_cases
base._config_for = gallery_config
base._validate_dom = validate
base._capture = capture
base._finish_stage = finish
