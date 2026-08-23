"""PID-local native QA probe for a disposable Anki release run.

Install this file as ``zz_hdo_revised_ui_probe/__init__.py`` only inside a
validated ``/private/tmp/anki-release-qa.*`` base.  It never saves settings or
touches collection content; it records native layout state, captures the
isolated windows, and quits its own Anki process when complete.
"""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import traceback
from typing import Any, Dict

from aqt import gui_hooks, mw
from aqt.qt import QApplication, QFont, QPoint, QScrollArea, QTimer, Qt


RUN_ROOT = Path(os.environ.get("HDO_REVISED_UI_PROBE_ROOT", ""))
EXPECTED_PROFILE = os.environ.get("HDO_REVISED_UI_PROBE_PROFILE", "")
ENABLED = (
    str(RUN_ROOT).startswith("/private/tmp/anki-release-qa.")
    and EXPECTED_PROFILE.startswith("Codex QA ")
)
OUTPUT_ROOT = RUN_ROOT / "hdo-revised-ui-probe"
REPORT_PATH = OUTPUT_ROOT / "runtime-report.json"
REPORT: Dict[str, Any] = {
    "schema_version": 1,
    "status": "running",
    "errors": [],
    "captures": {},
    "states": {},
}


def _write_report() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(REPORT, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _error(stage: str, exc: BaseException) -> None:
    REPORT["errors"].append(
        {
            "stage": stage,
            "error": "{}: {}".format(type(exc).__name__, exc),
            "traceback": traceback.format_exc(),
        }
    )
    _finish(False)


def _capture(widget: Any, name: str) -> None:
    QApplication.processEvents()
    widget.repaint()
    QApplication.processEvents()
    path = OUTPUT_ROOT / "{}.png".format(name)
    pixmap = widget.grab()
    saved = pixmap.save(str(path), "PNG")
    REPORT["captures"][name] = {
        "path": str(path),
        "saved": bool(saved),
        "width": pixmap.width(),
        "height": pixmap.height(),
        "device_pixel_ratio": pixmap.devicePixelRatio(),
    }


def _visible_geometry(widget: Any, parent: Any) -> Dict[str, Any]:
    origin = widget.mapTo(parent, QPoint(0, 0))
    return {
        "visible": widget.isVisible(),
        "x": origin.x(),
        "y": origin.y(),
        "width": widget.width(),
        "height": widget.height(),
    }


def _dialog_state(dialog: Any) -> Dict[str, Any]:
    current_scroll = dialog.stack.currentWidget()
    scroll_state: Dict[str, Any] = {}
    if isinstance(current_scroll, QScrollArea):
        scroll_state = {
            "vertical_scroll_visible": current_scroll.verticalScrollBar().isVisible(),
            "horizontal_scroll_visible": current_scroll.horizontalScrollBar().isVisible(),
            "footer_clearance": int(current_scroll.property("hdoFooterClearance") or 0),
            "viewport_width": current_scroll.viewport().width(),
            "viewport_height": current_scroll.viewport().height(),
        }
    return {
        "object_id": id(dialog),
        "window_title": dialog.windowTitle(),
        "size": [dialog.width(), dialog.height()],
        "minimum_size": [dialog.minimumWidth(), dialog.minimumHeight()],
        "mode": dialog._responsive_bucket,
        "current_section": dialog.current_section,
        "sidebar": _visible_geometry(dialog.nav, dialog),
        "section_selector": _visible_geometry(dialog.section_selector_wrap, dialog),
        "preview": _visible_geometry(dialog.preview_wrap, dialog),
        "footer": _visible_geometry(dialog.footer, dialog),
        "preview_requested": dialog.preview_wrap.isVisible(),
        "preview_toggle_checked": dialog.preview_wrap.isVisible(),
        "preview_toggle_text": dialog.compact_preview_button.text(),
        "scroll": scroll_state,
    }


def _process_preview_result(dialog: Any, value: object, attempt: int) -> None:
    if not isinstance(value, dict) or not value.get("ready"):
        if attempt < 5:
            QTimer.singleShot(450, lambda: _inspect_wide(attempt + 1))
            return
        _error("wide-preview", RuntimeError("production preview DOM did not become ready"))
        return
    REPORT["states"]["wide_preview_dom"] = value
    if value.get("fit") != "fit":
        _error("wide-preview", RuntimeError("production preview did not default to fit width"))
        return
    if value.get("overflowX"):
        _error("wide-preview", RuntimeError("production preview has horizontal overflow"))
        return
    if not value.get("order"):
        _error("wide-preview", RuntimeError("production preview hierarchy is incorrect"))
        return
    if value.get("forbidden"):
        _error("wide-preview", RuntimeError("production preview contains forbidden placeholder copy"))
        return
    if value.get("hasMetrics") and value.get("metricGroupCount") != 4:
        _error("wide-preview", RuntimeError("production preview metric grid is incomplete"))
        return
    try:
        _capture(dialog, "settings-wide-calendar")
        REPORT["states"]["wide"] = _dialog_state(dialog)
        expected_presets = {"Sapphire", "Amethyst", "Glacier", "Sea Glass"}
        actual_presets = set(dialog.heatmap_preset_buttons)
        REPORT["states"]["wide"]["heatmap_presets"] = sorted(actual_presets)
        REPORT["states"]["wide"]["heatmap_presets_exact"] = actual_presets == expected_presets
        dialog.open_page("bible_verse")
        QTimer.singleShot(500, _inspect_bible)
    except Exception as exc:
        _error("wide", exc)


def _inspect_wide(attempt: int = 0) -> None:
    try:
        controller = mw._home_dashboard_overhaul_controller
        dialog = controller.settings_dialog
        if dialog is None or not dialog.isVisible():
            raise RuntimeError("settings dialog did not open")
        dialog.resize(1440, 900)
        dialog._apply_responsive(force=True)
        QApplication.processEvents()
        script = """
(function () {
  var root = document.getElementById('hdo-dashboard');
  var calendar = document.querySelector('.hdo-calendar-card');
  var metrics = document.querySelector('.hdo-summary-metrics-grid');
  var bible = document.querySelector('.hdo-bible-card');
  var warning = document.querySelector('.hdo-data-warning');
  if (!root || !calendar || !bible) return {ready:false};
  var metricsOmittedForUnavailable = !metrics && !!warning;
  return {
    ready:true,
    fit:root.dataset.hdoSettingsPreviewFit || '',
    width:root.getBoundingClientRect().width,
    bodyScrollHeight:document.body.scrollHeight,
    bodyScrollWidth:document.body.scrollWidth,
    viewportWidth:document.documentElement.clientWidth,
    overflowX:document.body.scrollWidth > document.documentElement.clientWidth + 1,
    background:getComputedStyle(document.body).backgroundColor,
    hasMetrics:!!metrics,
    metricGroupCount:metrics ? metrics.querySelectorAll('.hdo-statistics-card').length : 0,
    metricsOmittedForUnavailable:metricsOmittedForUnavailable,
    order:metrics
      ? Boolean(calendar.compareDocumentPosition(metrics) & Node.DOCUMENT_POSITION_FOLLOWING) &&
        Boolean(metrics.compareDocumentPosition(bible) & Node.DOCUMENT_POSITION_FOLLOWING)
      : metricsOmittedForUnavailable &&
        Boolean(calendar.compareDocumentPosition(bible) & Node.DOCUMENT_POSITION_FOLLOWING),
    forbidden:/Outside due forecast|Outside study history|No events|Placeholder —/i.test(root.innerText)
  };
})()
"""
        dialog.preview.evalWithCallback(
            script,
            lambda value: _process_preview_result(dialog, value, attempt),
        )
    except Exception as exc:
        _error("wide-preview", exc)


def _inspect_bible() -> None:
    try:
        controller = mw._home_dashboard_overhaul_controller
        dialog = controller.settings_dialog
        before_id = id(dialog)
        dialog.theme_color.setValue("custom")
        dialog._sync_draft()
        dialog._update_dependencies()
        QApplication.processEvents()
        _capture(dialog, "settings-wide-bible-custom")
        bible_state = _dialog_state(dialog)
        bible_state.update(
            {
                "hex_enabled": dialog.font_color.isEnabled(),
                "swatch_enabled": dialog.font_color_swatch.isEnabled(),
                "hex_focus_policy": int(dialog.font_color.focusPolicy().value),
                "swatch_focus_policy": int(dialog.font_color_swatch.focusPolicy().value),
                "stored_custom_color": dialog.font_color_value,
            }
        )
        controller.open_settings("bible_verse")
        QApplication.processEvents()
        bible_state["same_dialog_after_reopen"] = (
            controller.settings_dialog is dialog and id(controller.settings_dialog) == before_id
        )
        bible_state["section_after_reopen"] = controller.settings_dialog.current_section
        REPORT["states"]["bible"] = bible_state
        dialog.resize(900, 900)
        dialog._apply_responsive(force=True)
        QApplication.processEvents()
        REPORT["states"]["medium_preview_hidden"] = _dialog_state(dialog)
        QTimer.singleShot(650, _inspect_medium)
    except Exception as exc:
        _error("bible", exc)


def _inspect_medium() -> None:
    try:
        dialog = mw._home_dashboard_overhaul_controller.settings_dialog
        QApplication.processEvents()
        _capture(dialog, "settings-medium-preview")
        REPORT["states"]["medium_preview_visible"] = _dialog_state(dialog)
        dialog.resize(620, 780)
        dialog._apply_responsive(force=True)
        QApplication.processEvents()
        _capture(dialog, "settings-narrow")
        REPORT["states"]["narrow"] = _dialog_state(dialog)
        _inspect_large_text(dialog)
    except Exception as exc:
        _error("medium", exc)


def _inspect_large_text(dialog: Any) -> None:
    try:
        application = QApplication.instance()
        original_font = QFont(application.font())
        enlarged = QFont(original_font)
        size = original_font.pointSizeF()
        enlarged.setPointSizeF(max(1.0, size * 1.5))
        application.setFont(enlarged)
        dialog.resize(620, 780)
        dialog._apply_responsive(force=True)
        QApplication.processEvents()
        _capture(dialog, "settings-narrow-150-percent-font")
        large_state = _dialog_state(dialog)
        large_state["font_point_size"] = application.font().pointSizeF()
        large_state["horizontal_overflow"] = bool(
            large_state.get("scroll", {}).get("horizontal_scroll_visible", False)
        )
        REPORT["states"]["narrow_150_percent"] = large_state
        application.setFont(original_font)
        dialog._allow_close = True
        dialog.reject()
        QTimer.singleShot(300, lambda: _finish(True))
    except Exception as exc:
        _error("large-text", exc)


def _process_main_month(value: object, attempt: int) -> None:
    if not isinstance(value, dict) or not value.get("ready"):
        if attempt < 5:
            QTimer.singleShot(450, lambda: _inspect_main_month(attempt + 1))
            return
        _error("main-month", RuntimeError("production Month dashboard did not become ready"))
        return
    REPORT["states"]["main_month"] = value
    if value.get("view") != "month" or value.get("day_count") not in {28, 35, 42}:
        _error("main-month", RuntimeError("Month did not render one complete calendar grid"))
        return
    if value.get("cell_min", 0) < 56 or value.get("cell_max", 999) > 72:
        _error("main-month", RuntimeError("Month cells escaped the 56 to 72 pixel release range"))
        return
    if value.get("metric_group_count") != 4 or not value.get("layout_matches_width"):
        _error("main-month", RuntimeError("Month calendar/statistics layout does not match its container"))
        return
    if value.get("overflow_x") or not value.get("bible_after"):
        _error("main-month", RuntimeError("Month has horizontal overflow or an invalid Bible position"))
        return
    if value.get("switch_ms", 9999) > 250:
        _error("main-month", RuntimeError("Month switching exceeded the live 250 ms budget"))
        return
    try:
        _capture(mw, "isolated-main-window-month-maximized")
        QTimer.singleShot(250, _inspect_main_year)
    except Exception as exc:
        _error("main-month-capture", exc)


def _inspect_main_month(attempt: int = 0) -> None:
    script = """
(function () {
  var root = document.getElementById('hdo-dashboard');
  var month = root && root.querySelector('[data-hdo-view="month"]');
  if (!root || !month) return {ready:false};
  var started = performance.now();
  if (root.dataset.hdoCalendarView !== 'month') month.click();
  var switchMs = performance.now() - started;
  var calendar = root.querySelector('.hdo-calendar-card');
  var metrics = root.querySelector('.hdo-summary-metrics-grid');
  var bible = root.querySelector('.hdo-bible-card');
  var cells = Array.from(root.querySelectorAll('.hdo-calendar-day'));
  if (!calendar || !metrics || !bible || !cells.length) return {ready:false};
  root.scrollIntoView({block:'start'});
  var rootRect = root.getBoundingClientRect();
  var calendarRect = calendar.getBoundingClientRect();
  var metricsRect = metrics.getBoundingClientRect();
  var bibleRect = bible.getBoundingClientRect();
  var heights = cells.map(function (cell) { return cell.getBoundingClientRect().height; });
  var sideBySide = metricsRect.left >= calendarRect.right - 1 &&
    Math.abs(metricsRect.top - calendarRect.top) <= 2;
  var stacked = metricsRect.top >= calendarRect.bottom - 1;
  return {
    ready:true,
    view:root.dataset.hdoCalendarView,
    root_width:Math.round(rootRect.width),
    day_count:cells.length,
    cell_min:Math.round(Math.min.apply(null, heights)),
    cell_max:Math.round(Math.max.apply(null, heights)),
    metric_group_count:metrics.querySelectorAll('.hdo-statistics-card').length,
    side_by_side:sideBySide,
    stacked:stacked,
    layout_matches_width:rootRect.width >= 1320 ? sideBySide : stacked,
    bible_after:bibleRect.top >= Math.max(calendarRect.bottom, metricsRect.bottom) - 1,
    overflow_x:document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    switch_ms:Number(switchMs.toFixed(2))
  };
})()
"""
    try:
        mw.web.evalWithCallback(script, lambda value: _process_main_month(value, attempt))
    except Exception as exc:
        _error("main-month", exc)


def _process_main_year(value: object) -> None:
    if not isinstance(value, dict) or not value.get("ready"):
        _error("main-year", RuntimeError("production Year dashboard did not become ready"))
        return
    REPORT["states"]["main_year"] = value
    if value.get("view") != "year" or value.get("day_count") not in {365, 366}:
        _error("main-year", RuntimeError("Year did not render the complete civil year"))
        return
    if value.get("month_label_count") != 12 or value.get("max_square_error", 999) > 1:
        _error("main-year", RuntimeError("Year month labels or square-cell geometry failed"))
        return
    if value.get("overflow_x") or value.get("switch_ms", 9999) > 250:
        _error("main-year", RuntimeError("Year overflowed the page or switching exceeded 250 ms"))
        return
    try:
        _capture(mw, "isolated-main-window-year-maximized")
        controller = mw._home_dashboard_overhaul_controller
        controller.open_settings("calendar_data")
        QTimer.singleShot(1400, _inspect_wide)
    except Exception as exc:
        _error("main-year-capture", exc)


def _inspect_main_year() -> None:
    script = """
(function () {
  var root = document.getElementById('hdo-dashboard');
  var year = root && root.querySelector('[data-hdo-view="year"]');
  if (!root || !year) return {ready:false};
  var started = performance.now();
  if (root.dataset.hdoCalendarView !== 'year') year.click();
  var switchMs = performance.now() - started;
  var cells = Array.from(root.querySelectorAll('.hdo-calendar-day'));
  var labels = root.querySelectorAll('.hdo-year-month-label');
  var shell = root.querySelector('.hdo-calendar-shell');
  if (!cells.length || !shell) return {ready:false};
  root.scrollIntoView({block:'start'});
  var squareErrors = cells.map(function (cell) {
    var rect = cell.getBoundingClientRect();
    return Math.abs(rect.width - rect.height);
  });
  return {
    ready:true,
    view:root.dataset.hdoCalendarView,
    day_count:cells.length,
    month_label_count:labels.length,
    max_square_error:Number(Math.max.apply(null, squareErrors).toFixed(2)),
    shell_scrollable:shell.scrollWidth > shell.clientWidth + 1,
    overflow_x:document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    switch_ms:Number(switchMs.toFixed(2))
  };
})()
"""
    try:
        mw.web.evalWithCallback(script, _process_main_year)
    except Exception as exc:
        _error("main-year", exc)


def _start() -> None:
    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        profile_name = str(getattr(mw.pm, "name", ""))
        collection_path = str(getattr(mw.col, "path", ""))
        sync_auth_method = getattr(mw.pm, "sync_auth", None)
        try:
            sync_auth = sync_auth_method() if callable(sync_auth_method) else None
        except Exception:
            sync_auth = None
        REPORT["identity"] = {
            "pid": os.getpid(),
            "profile": profile_name,
            "expected_profile": EXPECTED_PROFILE,
            "profile_matches": profile_name == EXPECTED_PROFILE,
            "collection_path": collection_path,
            "collection_inside_run_root": collection_path.startswith(str(RUN_ROOT)),
            "run_root": str(RUN_ROOT),
            "sync_auth_present": bool(sync_auth),
            "main_window_title": mw.windowTitle(),
        }
        if not REPORT["identity"]["profile_matches"]:
            raise RuntimeError("profile identity mismatch")
        if not REPORT["identity"]["collection_inside_run_root"]:
            raise RuntimeError("collection path escaped disposable run")
        if REPORT["identity"]["sync_auth_present"]:
            raise RuntimeError("disposable profile unexpectedly has sync credentials")
        controller = getattr(mw, "_home_dashboard_overhaul_controller", None)
        if controller is None:
            raise RuntimeError("candidate controller was not loaded")
        _capture(mw, "isolated-main-window")
        mw.showMaximized()
        QApplication.processEvents()
        QTimer.singleShot(800, _inspect_main_month)
    except Exception as exc:
        _error("start", exc)


def _finish(passed: bool) -> None:
    if REPORT.get("status") != "running":
        return
    REPORT["status"] = "passed" if passed and not REPORT["errors"] else "failed"
    _write_report()
    QTimer.singleShot(100, QApplication.instance().quit)


def _profile_opened() -> None:
    QTimer.singleShot(1200, _start)


if ENABLED:
    gui_hooks.profile_did_open.append(_profile_opened)
