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
import hashlib
import json
import os
from pathlib import Path
import traceback
from typing import Any, Dict

from aqt import gui_hooks, mw
from aqt.qt import QApplication, QTimer
from aqt.webview import AnkiWebView

from home_dashboard_overhaul.analytics import representative_preview_snapshot
from home_dashboard_overhaul.config_schema import normalize_config
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
    ("C", "compact", 560, 900),
    ("W", "wide", 1440, 900),
)
REFERENCE_DATE = "2026-08-22"
REPORT: Dict[str, Any] = {
    "schema_version": 1,
    "status": "running",
    "errors": [],
    "scale_policy": {
        "ui_scale_percent": 100,
        "text_scale_percent": 100,
        "excluded_ui_scales_percent": [125, 150, 200],
    },
    "captures": {},
    "states": {},
}
_started = False
_web: Any = None
_cases: list[dict[str, Any]] = []
_case_index = 0


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
        "dom": state,
    }
    REPORT["captures"][name] = record


def _base_config(theme: str, mode: str, view: str) -> dict[str, Any]:
    config = normalize_config({})
    config["appearance"].update(
        preset=theme,
        mode=mode,
        opacity=91,
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
        package = "home_dashboard_overhaul"
        base = "/_addons/{}/web/".format(package)
        _web.stdHtml(
            _html(str(case["theme"]), str(case["mode"]), str(case["view"])),
            css=[base + "dashboard.css"],
            js=[base + "dashboard.js"],
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
  var calendar = root ? root.querySelector('.hdo-calendar-card') : null;
  var metrics = root ? root.querySelector('.hdo-summary-metrics-grid') : null;
  var bible = root ? root.querySelector('.hdo-bible-card') : null;
  if (!root || !calendar || !metrics || !bible || !cells.length) return {ready:false};
  var style = root.getAttribute('style') || '';
  var rootRect = root.getBoundingClientRect();
  var calendarRect = calendar.getBoundingClientRect();
  var metricsRect = metrics.getBoundingClientRect();
  var bibleRect = bible.getBoundingClientRect();
  return {
    ready:true,
    view:root.dataset.hdoCalendarView || '',
    textScale100:style.indexOf('--hdo-scale:1.0') >= 0,
    viewportWidth:window.innerWidth,
    viewportHeight:window.innerHeight,
    rootWidth:Number(rootRect.width.toFixed(2)),
    calendarCells:cells.length,
    monthLabels:root.querySelectorAll('.hdo-year-month-label').length,
    statisticsCards:root.querySelectorAll('.hdo-statistics-card').length,
    bibleAfter:bibleRect.top >= Math.max(calendarRect.bottom, metricsRect.bottom) - 1,
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
                and bool(state.get("textScale100"))
                and state.get("calendarCells") in (
                    {365, 366} if case["view"] == "year" else {28, 35, 42}
                )
                and state.get("statisticsCards") == 4
                and bool(state.get("bibleAfter"))
                and not bool(state.get("overflowX"))
            )
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
        base = "/_addons/home_dashboard_overhaul/web/"
        _web.stdHtml(
            _html("Sapphire Glass", "light", "month"),
            css=[base + "dashboard.css"],
            js=[base + "dashboard.js"],
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
        QTimer.singleShot(250, _capture_full_screen_month)
        return
    case = _cases[_case_index]
    _case_index += 1
    _render(case, lambda: QTimer.singleShot(90, _capture_next_matrix_case))


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


def _begin() -> None:
    global _started, _web, _cases
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
        REPORT["identity"] = {
            "pid": os.getpid(),
            "run_root": str(RUN_ROOT),
            "expected_profile": EXPECTED_PROFILE,
            "profile": actual_profile,
            "profile_matches": True,
            "collection_path": collection_path,
            "collection_inside_run_root": True,
            "sync_auth_present": False,
        }
        _cases = _build_cases()
        _require(len(_cases) == 32, "100% matrix must contain exactly 32 cases")
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
        _web.setAccessibleName("Home Dashboard 100% contact-sheet capture")
        _start_warm_up()
    except Exception as exc:
        _error("begin", exc)


def _profile_opened(*_args: object) -> None:
    QTimer.singleShot(700, _begin)


if ENABLED:
    gui_hooks.profile_did_open.append(_profile_opened)
    QTimer.singleShot(1200, _begin)
