"""Disposable-PID runtime and capture probe for the four-page Settings UI."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import traceback
from typing import Any, Callable, Dict, Mapping, Optional

from aqt import gui_hooks, mw
from aqt.qt import QApplication, QFont, QLabel, QPoint, QScrollArea, QTimer, Qt, QWidget


RUN_ROOT = Path(os.environ.get("HDO_SETTINGS_PROBE_ROOT", ""))
EXPECTED_PROFILE = os.environ.get("HDO_SETTINGS_PROBE_PROFILE", "")
STAGE = os.environ.get("HDO_SETTINGS_PROBE_STAGE", "initial")
ENABLED = (
    str(RUN_ROOT).startswith("/private/tmp/anki-release-qa.")
    and EXPECTED_PROFILE.startswith("Codex QA ")
)
OUTPUT_ROOT = RUN_ROOT / "hdo-settings-overhaul-probe"
REPORT_PATH = OUTPUT_ROOT / "runtime-report.json"
STAGE_REPORT_PATH = OUTPUT_ROOT / "runtime-report-{}.json".format(STAGE)
REPORT: Dict[str, Any] = {
    "schema_version": 1,
    "status": "running",
    "stage": STAGE,
    "errors": [],
    "captures": {},
    "states": {},
}


def _write_report() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(REPORT, indent=2, sort_keys=True)
    REPORT_PATH.write_text(payload, encoding="utf-8")
    STAGE_REPORT_PATH.write_text(payload, encoding="utf-8")


def _finish(passed: bool) -> None:
    if REPORT.get("status") != "running":
        return
    REPORT["status"] = "passed" if passed and not REPORT["errors"] else "failed"
    _write_report()
    QTimer.singleShot(120, QApplication.instance().quit)


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


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _rotation_state_digest(controller: Any) -> Dict[str, Any]:
    path = Path(controller.rotator.state_path)
    if not path.exists():
        return {"exists": False, "path": str(path), "sha256": ""}
    return {
        "exists": True,
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _preservation_fingerprints(config: Mapping[str, Any], controller: Any) -> Dict[str, Any]:
    return {
        "schema_version": config.get("schema_version"),
        "events": _digest(config.get("events", {}).get("items", [])),
        "verse_library": _digest(config.get("bible", {}).get("quotes", [])),
        "rotation_mode": config.get("bible", {}).get("rotation_mode"),
        "theme": _digest(config.get("appearance", {})),
        "dashboard_preferences": _digest(
            {
                "home_screen": config.get("home_screen", {}),
                "study": config.get("study", {}),
                "new_cards": config.get("new_cards", {}),
                "layout": config.get("layout", {}),
            }
        ),
        "rotation_state": _rotation_state_digest(controller),
        "migration": _digest(config.get("migration", {})),
        "unknown_sentinel": _digest(config.get("qa_preserved_unknown", {})),
    }


def _dashboard_web() -> Any:
    deck_browser = getattr(mw, "deckBrowser", None)
    return getattr(deck_browser, "web", None)


def _wait_for_dashboard_render(
    capture_name: str,
    continuation: Callable[[Dict[str, Any]], None],
    expected: Optional[Mapping[str, Any]] = None,
    attempt: int = 0,
) -> None:
    """Wait for the real dashboard DOM, then capture the complete main window."""

    web = _dashboard_web()
    if web is None:
        if attempt < 50:
            QTimer.singleShot(
                350,
                lambda: _wait_for_dashboard_render(
                    capture_name, continuation, expected, attempt + 1
                ),
            )
            return
        _error(capture_name, RuntimeError("Deck Browser webview was unavailable"))
        return
    script = """
(function () {
  var root = document.getElementById('hdo-dashboard');
  if (!root) return {ready:false, reason:'missing-root'};
  var data = root.querySelector('.hdo-calendar-data, .hdo-dashboard-data');
  var payload = null;
  try { payload = data ? JSON.parse(data.textContent || '{}') : null; } catch (_error) {}
  var shell = root.querySelector('[data-hdo-calendar-view]');
  var cells = root.querySelectorAll('.hdo-calendar-day');
  var loading = root.classList.contains('hdo-dashboard--loading');
  return {
    ready:!loading && !!payload && !!shell && cells.length > 0,
    loading:loading,
    ariaBusy:root.getAttribute('aria-busy'),
    view:shell ? shell.getAttribute('data-hdo-calendar-view') : '',
    weekStart:payload ? Number(payload.week_start) : null,
    calendarCells:cells.length,
    hasProgress:!!root.querySelector('section[aria-labelledby="hdo-progress-title"]'),
    hasSession:!!root.querySelector('section[aria-labelledby="hdo-session-title"]'),
    hasBible:!!root.querySelector('.hdo-bible-card'),
    heatmapFive:getComputedStyle(root).getPropertyValue('--hdo-heatmap-5').trim(),
    bodyWidth:document.body.scrollWidth,
    viewportWidth:document.documentElement.clientWidth,
    overflowX:document.body.scrollWidth > document.documentElement.clientWidth + 1
  };
})()
"""

    def inspected(value: object) -> None:
        try:
            state = value if isinstance(value, dict) else {"ready": False}
            ready = bool(state.get("ready"))
            if expected:
                if expected.get("calendar_view") is not None:
                    ready = ready and state.get("view") == expected.get("calendar_view")
                if expected.get("week_start") is not None:
                    ready = ready and state.get("weekStart") == expected.get("week_start")
                if expected.get("visibility_key") == "remaining":
                    ready = ready and state.get("hasProgress") == expected.get("visibility_value")
            if not ready:
                if attempt < 50:
                    QTimer.singleShot(
                        350,
                        lambda: _wait_for_dashboard_render(
                            capture_name, continuation, expected, attempt + 1
                        ),
                    )
                    return
                raise RuntimeError(
                    "dashboard did not reach the expected rendered state: {}".format(state)
                )
            _require(state.get("ariaBusy") == "false", "rendered dashboard remains busy")
            _require(not state.get("overflowX"), "rendered dashboard has horizontal overflow")
            REPORT["states"][capture_name + "_dom"] = state
            _capture(mw, capture_name)
            continuation(state)
        except Exception as exc:
            _error(capture_name, exc)

    web.evalWithCallback(script, inspected)


def _geometry(widget: Any, parent: Any) -> Dict[str, Any]:
    origin = widget.mapTo(parent, QPoint(0, 0))
    return {
        "visible": widget.isVisible(),
        "x": origin.x(),
        "y": origin.y(),
        "width": widget.width(),
        "height": widget.height(),
    }


def _current_scroll(dialog: Any) -> Any:
    candidate = dialog.stack.currentWidget()
    return candidate if isinstance(candidate, QScrollArea) else None


def _dialog_state(dialog: Any) -> Dict[str, Any]:
    scroll = _current_scroll(dialog)
    badge_index = dialog.header_grid.indexOf(dialog.dirty_badge)
    badge_row = -1
    badge_column = -1
    if badge_index >= 0:
        badge_row, badge_column, _row_span, _column_span = dialog.header_grid.getItemPosition(
            badge_index
        )
    return {
        "size": [dialog.width(), dialog.height()],
        "maximum_width": dialog.maximumWidth(),
        "mode": dialog._responsive_bucket,
        "section": dialog.current_section,
        "page_ids": sorted(dialog.page_indices, key=dialog.page_indices.get),
        "nav_labels": [dialog.nav.item(row).text() for row in range(dialog.nav.count())],
        "selector_labels": [
            dialog.section_selector.itemText(index)
            for index in range(dialog.section_selector.count())
        ],
        "tab_labels": [
            dialog.section_tabs.tabText(index).replace("&&", "&")
            for index in range(dialog.section_tabs.count())
        ],
        "nav": _geometry(dialog.nav, dialog),
        "tabs": _geometry(dialog.section_tabs, dialog),
        "selector": _geometry(dialog.section_selector_wrap, dialog),
        "preview": _geometry(dialog.preview_wrap, dialog),
        "compact_preview": _geometry(dialog.compact_preview_wrap, dialog),
        "footer": _geometry(dialog.footer, dialog),
        "horizontal_scroll_visible": bool(
            scroll is not None and scroll.horizontalScrollBar().isVisible()
        ),
        "vertical_scroll_visible": bool(
            scroll is not None and scroll.verticalScrollBar().isVisible()
        ),
        "close_text": dialog.close_button.text(),
        "save_enabled": dialog.save_button.isEnabled(),
        "status_text": dialog.dirty_badge.text(),
        "status_visible": dialog.dirty_badge.isVisible(),
        "status_grid_position": [badge_row, badge_column],
        "card_titles": [
            label.text()
            for label in dialog.findChildren(QLabel)
            if label.objectName() == "CardTitle" and label.isVisible()
        ],
    }


def _open_and_capture(dialog: Any, section: str, name: str) -> Dict[str, Any]:
    dialog.open_page(section)
    dialog._apply_responsive(force=True)
    QApplication.processEvents()
    _capture(dialog, name)
    state = _dialog_state(dialog)
    REPORT["states"][name] = state
    return state


def _verify_last_card_clearance(dialog: Any, section: str) -> Dict[str, Any]:
    dialog.open_page(section)
    dialog._apply_responsive(force=True)
    QApplication.processEvents()
    scroll = _current_scroll(dialog)
    _require(isinstance(scroll, QScrollArea), "{} page has no body scroll".format(section))
    page = scroll.widget()
    _require(page is not None, "{} page has no body widget".format(section))
    cards = [
        widget
        for widget in page.findChildren(QWidget)
        if widget.objectName() == "SettingsCard" and widget.isVisible()
    ]
    if not cards and section == "events":
        cards = [
            widget
            for widget in (dialog.event_tabs, dialog.event_empty_state)
            if widget.isVisible()
        ]
    _require(cards, "{} page has no visible terminal surface".format(section))
    last = max(cards, key=lambda card: card.mapTo(page, QPoint(0, 0)).y() + card.height())
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    QApplication.processEvents()
    top = last.mapTo(scroll.viewport(), QPoint(0, 0)).y()
    state = {
        "title": getattr(getattr(last, "heading", None), "text", lambda: section)(),
        "top": top,
        "bottom": top + last.height(),
        "viewport_height": scroll.viewport().height(),
        "scroll_value": scroll.verticalScrollBar().value(),
        "scroll_maximum": scroll.verticalScrollBar().maximum(),
    }
    _require(
        state["bottom"] <= state["viewport_height"] + 2,
        "{} final card remains obscured by the footer: {}".format(section, state),
    )
    return state


def _inspect_preview_dom(dialog: Any, attempt: int = 0) -> None:
    script = """
(function () {
  var root = document.getElementById('hdo-dashboard');
  if (!root) return {ready:false};
  return {
    ready:true,
    fit:root.dataset.hdoSettingsPreviewFit || '',
    sampleRevision:root.dataset.hdoRevision || '',
    hasCalendar:!!document.querySelector('.hdo-calendar-card'),
    hasMetrics:!!document.querySelector('.hdo-summary-metrics-grid'),
    hasBible:!!document.querySelector('.hdo-bible-card'),
    overflowX:document.body.scrollWidth > document.documentElement.clientWidth + 1,
    unusedVertical:Math.max(0, document.documentElement.clientHeight - document.body.scrollHeight)
  };
})()
"""

    def inspected(value: object) -> None:
        try:
            if not isinstance(value, dict) or not value.get("ready"):
                if attempt < 6:
                    QTimer.singleShot(
                        350,
                        lambda: _inspect_preview_dom(dialog, attempt + 1),
                    )
                    return
                raise RuntimeError("production preview DOM did not become ready")
            REPORT["states"]["wide_preview_dom"] = value
            _require(value.get("fit") == "fit", "preview did not default to Fit")
            _require(not value.get("overflowX"), "preview has horizontal overflow")
            _require(value.get("unusedVertical", 9999) < 96, "preview retains a large unused region")
            _require(
                value.get("hasCalendar") and value.get("hasMetrics") and value.get("hasBible"),
                "sample preview is missing a dashboard region",
            )
            _inspect_responsive(dialog)
        except Exception as exc:
            _error("preview-dom", exc)

    dialog.preview.evalWithCallback(script, inspected)


def _inspect_wide_bible_preview(dialog: Any) -> None:
    try:
        state = _dialog_state(dialog)
        REPORT["states"]["wide-bible"] = state
        _capture(dialog, "wide-bible")
        _require(state["mode"] == "extra-wide", "wide Bible left extra-wide mode")
        _require(state["section"] == "bible_verse", "wide Bible route missed its page")
        _require(state["preview"]["visible"], "wide Bible preview is hidden")
        _require(not state["horizontal_scroll_visible"], "wide Bible scrolls horizontally")
        _require(not dialog.preview_sample_badge.isVisible(), "Bible preview shows sample-data copy")
        selected_text = " ".join(dialog.quote_detail.text().split())
        script = """
(function () {
  var root = document.getElementById('hdo-dashboard');
  var stack = root && root.querySelector('.hdo-stack');
  var bible = document.querySelector('.hdo-bible-card');
  if (!root || !stack || !bible) return {ready:false};
  var visible = Array.prototype.filter.call(stack.children, function (child) {
    return getComputedStyle(child).display !== 'none';
  });
  return {
    ready:true,
    fit:root.dataset.hdoSettingsPreviewFit || '',
    naturalWidth:root.style.width,
    viewportWidth:document.documentElement.clientWidth,
    visibleStackChildren:visible.length,
    bibleVisible:getComputedStyle(bible).display !== 'none',
    bibleText:(bible.innerText || '').replace(/\\s+/g, ' ').trim(),
    overflowX:document.body.scrollWidth > document.documentElement.clientWidth + 1,
    unusedVertical:Math.max(0, document.documentElement.clientHeight - document.body.scrollHeight)
  };
})()
"""

        def inspected(value: object) -> None:
            try:
                _require(isinstance(value, dict) and value.get("ready"), "focused Bible preview DOM did not become ready")
                REPORT["states"]["wide_bible_preview_dom"] = value
                _require(value.get("fit") == "actual-size", "focused Bible preview did not default to Actual size")
                _require(
                    value.get("naturalWidth") == "{}px".format(value.get("viewportWidth")),
                    "focused Bible preview was scaled instead of rendered at 1x",
                )
                _require(value.get("visibleStackChildren") == 1 and value.get("bibleVisible"), "Bible preview did not hide unrelated dashboard regions")
                _require(not value.get("overflowX"), "focused Bible preview has horizontal overflow")
                _require(value.get("unusedVertical", 9999) < 96, "Bible preview retains a large unused region")
                _require(
                    selected_text and selected_text in str(value.get("bibleText", "")),
                    "Bible preview does not use the selected staged verse",
                )
                dialog.open_page("dashboard")
                dialog._apply_responsive(force=True)
                QTimer.singleShot(500, lambda: _inspect_preview_dom(dialog))
            except Exception as exc:
                _error("wide-bible-preview-dom", exc)

        dialog.preview.evalWithCallback(script, inspected)
    except Exception as exc:
        _error("wide-bible", exc)


def _inspect_wide() -> None:
    try:
        dialog = mw._home_dashboard_overhaul_controller.settings_dialog
        _require(dialog is not None and dialog.isVisible(), "settings dialog did not open")
        dialog.resize(1280, 900)
        dialog.open_page("theme_layout")
        dialog._apply_responsive(force=True)
        QApplication.processEvents()
        wide = _dialog_state(dialog)
        REPORT["states"]["wide"] = wide
        _require(wide["mode"] == "extra-wide", "1280 px did not select wide mode")
        _require(wide["section"] == "dashboard", "legacy appearance route missed Dashboard")
        _require(
            wide["page_ids"] == ["dashboard", "events", "bible_verse", "about_support"],
            "navigation does not contain exactly four pages",
        )
        _require(wide["nav"]["visible"], "wide navigation rail is hidden")
        _require(not wide["tabs"]["visible"] and not wide["selector"]["visible"], "wide navigation duplicated")
        _require(wide["preview"]["visible"], "wide Dashboard preview is hidden")
        _require(wide["maximum_width"] <= 1320, "wide shell exceeds its maximum width")
        _require(58 <= wide["footer"]["height"] <= 62, "wide footer is not approximately 60 px tall")
        _require(wide["nav"]["y"] < 150, "content-sized rail is not top aligned")
        _require(wide["preview"]["y"] < 150, "content-sized preview is not top aligned")
        _require(not dialog.preview_sample_badge.isVisible(), "live Dashboard preview is mislabeled as sample data")
        _require(wide["close_text"] == "Close" and not wide["save_enabled"], "clean footer state is incorrect")
        for title in ("Appearance", "Content & study metrics", "Calendar & data"):
            _require(title in wide["card_titles"], "Dashboard internal area missing: {}".format(title))

        dialog._scroll_dashboard_anchor("appearance")
        _capture(dialog, "wide-dashboard-appearance")
        dialog._scroll_dashboard_anchor("content")
        QApplication.processEvents()
        _capture(dialog, "wide-dashboard-content-metrics")
        dialog._scroll_dashboard_anchor("calendar")
        QApplication.processEvents()
        _capture(dialog, "wide-dashboard-calendar")

        stylesheet_before = dialog.styleSheet()
        preset_index = (dialog.preset.currentIndex() + 1) % dialog.preset.count()
        dialog.preset.setCurrentIndex(preset_index)
        QApplication.processEvents()
        _require(dialog.styleSheet() == stylesheet_before, "dashboard preset recolored Settings chrome")
        dialog._apply_config_to_widgets(dialog.draft.baseline)
        dialog._sync_draft()
        dialog.open_page("bible_verse")
        dialog._apply_responsive(force=True)
        QTimer.singleShot(550, lambda: _inspect_wide_bible_preview(dialog))
    except Exception as exc:
        _error("wide", exc)


def _inspect_responsive(dialog: Any) -> None:
    try:
        controller = mw._home_dashboard_overhaul_controller
        preservation = _preservation_fingerprints(controller.config, controller)
        baseline_events = deepcopy(dialog.draft.baseline["events"]["items"])
        dialog.resize(900, 900)
        dashboard = _open_and_capture(dialog, "dashboard", "intermediate-dashboard")
        _require(dashboard["mode"] == "intermediate", "900x900 did not select intermediate mode")
        _require(not dashboard["nav"]["visible"], "900x900 still shows the rail")
        _require(dashboard["tabs"]["visible"], "900x900 does not show horizontal tabs")
        _require(not dashboard["preview"]["visible"], "900x900 still shows persistent preview")
        _require(dashboard["compact_preview"]["visible"], "900x900 has no preview disclosure")
        _require(not dashboard["horizontal_scroll_visible"], "900x900 Dashboard scrolls horizontally")
        _require(
            dashboard["tab_labels"] == ["Dashboard", "Events", "Bible verse", "About & support"],
            "intermediate tabs lost the About & support ampersand",
        )
        _require(dialog.preset.width() <= 360, "intermediate preset control stretches too wide")
        _require(dialog.history_range.width() <= 360, "intermediate history control stretches too wide")

        dialog.staged["events"]["items"] = []
        dialog._refresh_event_lists()
        events = _open_and_capture(dialog, "events", "intermediate-events-empty")
        _require(not events["preview"]["visible"], "Events has a persistent preview")
        _require(not dialog.event_toolbar_wrap.isVisible(), "empty Events shows search/sort")
        _require(dialog.event_empty_state.isVisible(), "empty Events lacks an intentional empty state")
        _require(dialog.event_empty_title.text() == "No events yet", "Events empty state lacks its title")
        _require(dialog.event_empty_add.text() == "Add event", "Events empty state lacks one Add action")

        bible = _open_and_capture(dialog, "bible_verse", "intermediate-bible")
        _require(not bible["preview"]["visible"], "intermediate Bible shows persistent preview")
        _require(dialog.quote_count.isVisible(), "incremental verse result count is hidden")
        _require(dialog.quote_list.count() <= 100, "verse library rendered more than its first batch")
        _require(dialog.quote_load_more.isVisible(), "large verse library lacks Load more")
        stored_color = dialog.font_color_value
        dialog.theme_color.setValue("custom")
        dialog._sync_draft()
        _require(dialog.custom_color_container.isVisible(), "Custom color did not reveal #RRGGBB field")
        dialog.theme_color.setValue("theme")
        dialog._sync_draft()
        _require(not dialog.custom_color_container.isVisible(), "Theme color did not collapse custom controls")
        _require(dialog.font_color.focusPolicy() == Qt.FocusPolicy.NoFocus, "hidden custom field remains focusable")
        _require(dialog.font_color_swatch.focusPolicy() == Qt.FocusPolicy.NoFocus, "hidden color swatch remains focusable")
        _require(dialog.font_color_value == stored_color, "Theme color erased the custom value")
        dialog._apply_config_to_widgets(dialog.draft.baseline)
        dialog._sync_draft()

        about = _open_and_capture(dialog, "about_support", "intermediate-about-support")
        _require(not about["preview"]["visible"] and not about["compact_preview"]["visible"], "About exposes preview chrome")
        for title in ("Version & compatibility", "Help", "Privacy & legal", "Recovery"):
            _require(title in about["card_titles"], "About card missing: {}".format(title))
        about_cards = [
            widget
            for widget in _current_scroll(dialog).widget().findChildren(QWidget)
            if widget.objectName() == "SettingsCard" and widget.isVisible()
        ]
        _require(
            all(card.minimumHeight() < 100 for card in about_cards),
            "About cards retain an excessive minimum height",
        )

        dialog.resize(620, 900)
        narrow = _open_and_capture(dialog, "dashboard", "narrow-dashboard")
        _require(narrow["mode"] == "narrow", "620 px did not select narrow mode")
        _require(narrow["selector"]["visible"], "narrow selector is hidden")
        _require(not narrow["nav"]["visible"] and not narrow["tabs"]["visible"], "narrow navigation duplicated")
        _require(
            narrow["selector_labels"] == ["Dashboard", "Events", "Bible verse", "About & support"],
            "narrow selector labels are not the four-page contract",
        )
        _require(not narrow["horizontal_scroll_visible"], "narrow Dashboard scrolls horizontally")
        _open_and_capture(dialog, "events", "narrow-events-empty")
        dialog.staged["events"]["items"] = [
            {
                "id": "probe-active",
                "name": "Pediatrics review",
                "date": "2026-08-29",
                "archived": False,
                "created_at": "2026-08-22T12:00:00-05:00",
                "archived_at": "",
            },
            {
                "id": "probe-archived",
                "name": "Completed exam",
                "date": "2026-08-10",
                "archived": True,
                "created_at": "2026-08-01T12:00:00-05:00",
                "archived_at": "2026-08-11T12:00:00-05:00",
            },
        ]
        dialog._refresh_event_lists(select_event_id="probe-active", select_archived=False)
        populated = _open_and_capture(dialog, "events", "narrow-events-populated")
        _require(dialog.active_events.property("narrowCards") is True, "narrow event rows are not cards")
        _require(dialog.active_events.isHeaderHidden(), "narrow event cards still show table headers")
        _require(dialog.active_events.topLevelItemCount() == 1, "active event card missing")
        event_item = dialog.active_events.topLevelItem(0)
        _require("\n" in event_item.text(0), "event card does not stack name and date")
        event_menu = dialog.active_events.itemWidget(event_item, 2)
        _require(event_menu is not None and event_menu.text() == "•••", "event actions are detached from the card")
        _require(not hasattr(dialog, "event_delete"), "Events still exposes a detached destructive action")
        _require(not populated["horizontal_scroll_visible"], "narrow event cards scroll horizontally")
        dialog.staged = deepcopy(dialog.draft.baseline)
        dialog._apply_config_to_widgets(dialog.draft.baseline)
        dialog._sync_draft()
        _open_and_capture(dialog, "bible_verse", "narrow-bible")
        _open_and_capture(dialog, "about_support", "narrow-about-support")

        REPORT["states"]["last_card_clearance"] = {
            section: _verify_last_card_clearance(dialog, section)
            for section in ("dashboard", "events", "bible_verse", "about_support")
        }

        application = QApplication.instance()
        original_font = QFont(application.font())
        enlarged = QFont(original_font)
        if original_font.pointSizeF() > 0:
            enlarged.setPointSizeF(original_font.pointSizeF() * 1.5)
        else:
            enlarged.setPixelSize(max(1, round(original_font.pixelSize() * 1.5)))
        application.setFont(enlarged)
        dialog.resize(900, 900)
        temporary_opacity = dialog.opacity.value() - 1 if dialog.opacity.value() > 70 else dialog.opacity.value() + 1
        dialog.opacity.setValue(temporary_opacity)
        dialog._sync_draft()
        dialog.open_page("dashboard")
        dialog._apply_responsive(force=True)
        dialog._reflow_heatmap_grid()
        QApplication.processEvents()
        large_text = _dialog_state(dialog)
        heatmap_columns = [
            dialog.heatmap_preset_grid.getItemPosition(index)[1]
            for index in range(dialog.heatmap_preset_grid.count())
        ]
        large_text["heatmap_columns"] = heatmap_columns
        REPORT["states"]["intermediate_150_percent"] = large_text
        _capture(dialog, "intermediate-dashboard-150-percent-font")
        _require(not large_text["horizontal_scroll_visible"], "150% font causes horizontal scrolling")
        _require(large_text["status_visible"], "150% font test did not expose header status")
        _require(large_text["status_grid_position"][0] == 1, "150% header status did not wrap below the title")
        _require(heatmap_columns and max(heatmap_columns) == 0, "150% heatmap palettes did not reflow to one column")
        application.setFont(original_font)

        dialog._apply_config_to_widgets(dialog.draft.baseline)
        dialog._sync_draft()
        dialog.resize(620, 900)
        dialog.open_page("dashboard")
        dialog._apply_responsive(force=True)

        # Exercise the requested persistence sequence explicitly: Month → Year,
        # Sunday → Monday, a different heatmap palette, and one visibility change.
        dialog.calendar_view.setValue("month")
        dialog.calendar_view.setValue("year")
        dialog.week_start.setValue("6")
        dialog.week_start.setValue("0")
        dialog._week_start_touched = True
        theme_name = str(dialog.preset.currentData() or dialog.preset.currentText())
        available_palettes = list(dialog.heatmap_preset_buttons)
        current_palette = dialog._heatmap_preset_preferences.get(theme_name)
        next_palette = next(name for name in available_palettes if name != current_palette)
        dialog._select_heatmap_preset(next_palette)
        visibility_key = "remaining"
        visibility_value = not bool(dialog.draft.baseline["visibility"][visibility_key])
        dialog.visibility[visibility_key].setChecked(visibility_value)
        dialog._sync_draft()
        dirty = _dialog_state(dialog)
        REPORT["states"]["dirty"] = dirty
        _capture(dialog, "narrow-dashboard-dirty")
        _require(dirty["close_text"] == "Discard changes" and dirty["save_enabled"], "dirty footer state is incorrect")
        _require("unsaved change" in dirty["status_text"], "dirty count was not announced")
        expected_restart = {
            "calendar_view": "year",
            "week_start": 0,
            "theme_name": theme_name,
            "heatmap_palette": next_palette,
            "visibility_key": visibility_key,
            "visibility_value": visibility_value,
            "preserved": preservation,
            "action_trace": [
                "calendar_view:month",
                "calendar_view:year",
                "week_start:sunday",
                "week_start:monday",
                "heatmap_palette:{}".format(next_palette),
                "visibility.{}:{}".format(visibility_key, visibility_value),
            ],
        }
        REPORT["expected_restart"] = expected_restart
        dialog._save()
        QApplication.processEvents()
        saved = _dialog_state(dialog)
        REPORT["states"]["saved"] = saved
        _capture(dialog, "narrow-dashboard-saved")
        _require(dialog.isVisible(), "Save closed Settings")
        _require(saved["close_text"] == "Close" and not saved["save_enabled"], "saved footer did not return clean")
        _require(saved["status_text"] == "✓ Saved", "saved status was not announced")
        config = controller.config
        _require(config["heatmap"]["calendar_view"] == "year", "saved view was not adopted")
        _require(config["heatmap"]["week_start"] == 0, "saved week start was not adopted")
        _require(config["heatmap"]["presets_by_theme"][theme_name] == next_palette, "saved palette was not adopted")
        _require(config["visibility"][visibility_key] == visibility_value, "saved visibility was not adopted")
        _require(
            _preservation_fingerprints(config, controller)["events"] == _digest(baseline_events),
            "event data changed during unrelated settings save",
        )

        def saved_status_cleared() -> None:
            try:
                _require(not dialog.dirty_badge.isVisible(), "saved confirmation did not clear after two seconds")
                REPORT["states"]["saved_status_cleared"] = _dialog_state(dialog)
                _capture(dialog, "narrow-dashboard-saved-status-cleared")
                expected_restart["preserved"] = _preservation_fingerprints(
                    controller.config, controller
                )
                dialog._allow_close = True
                dialog.reject()
                _wait_for_dashboard_render(
                    "isolated-main-window-after-save-rendered",
                    lambda _state: _finish(True),
                    expected_restart,
                )
            except Exception as exc:
                _error("saved-status-clear", exc)

        QTimer.singleShot(2300, saved_status_cleared)
    except Exception as exc:
        _error("responsive", exc)


def _inspect_restart() -> None:
    try:
        previous = json.loads(
            (OUTPUT_ROOT / "runtime-report-initial.json").read_text(encoding="utf-8")
        )
        expected = previous["expected_restart"]
        controller = mw._home_dashboard_overhaul_controller
        config = controller.config
        _require(config["heatmap"]["calendar_view"] == expected["calendar_view"], "saved view did not survive restart")
        _require(config["heatmap"]["week_start"] == expected["week_start"], "saved week start did not survive restart")
        _require(
            config["heatmap"]["presets_by_theme"][expected["theme_name"]]
            == expected["heatmap_palette"],
            "saved heatmap palette did not survive restart",
        )
        _require(
            config["visibility"][expected["visibility_key"]]
            == expected["visibility_value"],
            "saved visibility did not survive restart",
        )
        actual_preserved = _preservation_fingerprints(config, controller)
        _require(
            actual_preserved == expected["preserved"],
            "events, verse library, rotation state, theme, or dashboard preferences changed across restart",
        )
        REPORT["previous_status"] = previous.get("status")
        REPORT["expected_restart"] = expected
        REPORT["actual_restart"] = {
            "calendar_view": config["heatmap"]["calendar_view"],
            "week_start": config["heatmap"]["week_start"],
            "heatmap_palette": config["heatmap"]["presets_by_theme"][expected["theme_name"]],
            "visibility_value": config["visibility"][expected["visibility_key"]],
            "preserved": actual_preserved,
        }

        def open_restart_settings(_dashboard_state: Dict[str, Any]) -> None:
            controller.open_settings("calendar_data")
            QTimer.singleShot(1100, capture_restart_settings)

        def leave_full_screen(_dashboard_state: Dict[str, Any]) -> None:
            try:
                screen = mw.screen()
                REPORT["states"]["restart_full_screen_year"] = {
                    "is_full_screen": mw.isFullScreen(),
                    "calendar_view": _dashboard_state.get("view"),
                    "window_size": [mw.width(), mw.height()],
                    "screen_size": (
                        [screen.geometry().width(), screen.geometry().height()]
                        if screen is not None
                        else []
                    ),
                }
                _require(mw.isFullScreen(), "full-screen capture was not actually full screen")
                mw.showNormal()
                QTimer.singleShot(900, lambda: open_restart_settings(_dashboard_state))
            except Exception as exc:
                _error("restart-full-screen", exc)

        def enter_full_screen(_dashboard_state: Dict[str, Any]) -> None:
            mw.showFullScreen()
            QTimer.singleShot(
                1200,
                lambda: _wait_for_dashboard_render(
                    "isolated-main-window-restart-full-screen-year-rendered",
                    leave_full_screen,
                    expected,
                ),
            )

        def capture_restart_settings(attempt: int = 0) -> None:
            try:
                dialog = controller.settings_dialog
                _require(dialog is not None and dialog.isVisible(), "restart Settings did not open")
                if attempt == 0:
                    dialog.resize(900, 900)
                    dialog._apply_responsive(force=True)
                    QApplication.processEvents()
                    QTimer.singleShot(420, lambda: capture_restart_settings(1))
                    return
                state = _dialog_state(dialog)
                REPORT["states"]["restart"] = state
                _capture(dialog, "restart-dashboard-calendar-route")
                _require(state["section"] == "dashboard", "legacy calendar route missed Dashboard after restart")
                _require(state["mode"] == "intermediate", "restart geometry is not intermediate")
                _require(dialog._normalized_route == "dashboard#calendar", "legacy route was not normalized")
                _require(dialog.calendar_view.value() == expected["calendar_view"], "Settings readback lost calendar view")
                _require(int(dialog.week_start.value("-1")) == expected["week_start"], "Settings readback lost week start")
                _require(
                    dialog._heatmap_preset_preferences[expected["theme_name"]]
                    == expected["heatmap_palette"],
                    "Settings readback lost heatmap palette",
                )
                _require(
                    dialog.visibility[expected["visibility_key"]].isChecked()
                    == expected["visibility_value"],
                    "Settings readback lost visibility",
                )
                _require(not dialog.draft.dirty, "restart Settings opened dirty")
                _require(state["close_text"] == "Close" and not state["save_enabled"], "restart footer is not clean")
                _require(not state["status_visible"], "restart displays a stale status badge")
                scroll = _current_scroll(dialog)
                heading = dialog.dashboard_anchors["calendar"].heading
                heading_geometry = _geometry(heading, scroll.viewport())
                heading_geometry["viewport_height"] = scroll.viewport().height()
                heading_geometry["scroll_value"] = scroll.verticalScrollBar().value()
                REPORT["states"]["restart_calendar_heading"] = heading_geometry
                _require(heading_geometry["y"] >= 0, "Calendar heading is clipped above the Dashboard body")
                _require(
                    heading_geometry["y"] + heading_geometry["height"] <= heading_geometry["viewport_height"],
                    "Calendar heading is not fully visible after route restoration",
                )
                dialog._allow_close = True
                dialog.reject()
                _finish(True)
            except Exception as exc:
                _error("restart-capture", exc)

        _wait_for_dashboard_render(
            "isolated-main-window-restart-rendered",
            enter_full_screen,
            expected,
        )
    except Exception as exc:
        _error("restart", exc)


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
        _require(REPORT["identity"]["profile_matches"], "profile identity mismatch")
        _require(REPORT["identity"]["collection_inside_run_root"], "collection escaped disposable run")
        _require(not REPORT["identity"]["sync_auth_present"], "disposable profile has sync credentials")
        _require(
            getattr(mw, "_home_dashboard_overhaul_controller", None) is not None,
            "candidate controller was not loaded",
        )
        _capture(mw, "isolated-main-window-{}-initial-state".format(STAGE))
        if STAGE == "restart":
            _inspect_restart()
            return

        initial_expected = {
            "calendar_view": "month",
            "week_start": 6,
            "visibility_key": "remaining",
            "visibility_value": True,
        }

        def open_initial_settings(_dashboard_state: Dict[str, Any]) -> None:
            mw._home_dashboard_overhaul_controller.open_settings("theme_layout")
            QTimer.singleShot(1300, _inspect_wide)

        def leave_initial_full_screen(_dashboard_state: Dict[str, Any]) -> None:
            try:
                screen = mw.screen()
                REPORT["states"]["initial_full_screen_month"] = {
                    "is_full_screen": mw.isFullScreen(),
                    "calendar_view": _dashboard_state.get("view"),
                    "window_size": [mw.width(), mw.height()],
                    "screen_size": (
                        [screen.geometry().width(), screen.geometry().height()]
                        if screen is not None
                        else []
                    ),
                }
                _require(mw.isFullScreen(), "initial full-screen capture was not actually full screen")
                mw.showNormal()
                QTimer.singleShot(900, lambda: open_initial_settings(_dashboard_state))
            except Exception as exc:
                _error("initial-full-screen-month", exc)

        def enter_initial_full_screen(_dashboard_state: Dict[str, Any]) -> None:
            mw.showFullScreen()
            QTimer.singleShot(
                1200,
                lambda: _wait_for_dashboard_render(
                    "isolated-main-window-initial-full-screen-month-rendered",
                    leave_initial_full_screen,
                    initial_expected,
                ),
            )

        _wait_for_dashboard_render(
            "isolated-main-window-initial-rendered",
            enter_initial_full_screen,
            initial_expected,
        )
    except Exception as exc:
        _error("start", exc)


def _profile_opened() -> None:
    QTimer.singleShot(1000, _start)


if ENABLED:
    REPORT["module_loaded"] = True
    _write_report()
    gui_hooks.profile_did_open.append(_profile_opened)
