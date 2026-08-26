#!/usr/bin/env python3
"""Validate the focused Home Screen Dashboard 1.8.7 window contract."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    contract = json.loads(
        (ROOT / "qa" / "settings_window_contract_1_8_7.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    settings = (ROOT / "settings.py").read_text(encoding="utf-8")
    controller = (ROOT / "controller.py").read_text(encoding="utf-8")
    dialog = settings.split("class SettingsDialog(QDialog):", 1)[1].split(
        "def _object_name", 1
    )[0]
    grid_mount = dialog.split("    def _place_grid_widgets(", 1)[1].split(
        "    def _reflow_compact_grids", 1
    )[0]
    heatmap_refresh = dialog.split(
        "    def _refresh_heatmap_preset_cards(", 1
    )[1].split("    def _update_color_swatch", 1)[0]
    apply_theme = dialog.split("    def _apply_theme(", 1)[1].split(
        "    def _update_forecast_range_visibility", 1
    )[0]
    verse_row = settings.split("class VerseRowWidget(QWidget):", 1)[1].split(
        "class ContextualActionGroup", 1
    )[0]
    opener = controller.split("    def open_settings(", 1)[1].split(
        "    def request_settings_open", 1
    )[0]
    deferred = controller.split("    def request_settings_open(", 1)[1].split(
        "    def save_config", 1
    )[0]
    menu = settings.split("def install_settings_menu", 1)[1]
    errors = []
    if manifest.get("human_version") != contract.get("release"):
        errors.append("manifest and Settings window contract versions differ")
    if config.get("schema_version") != contract.get("schema_version"):
        errors.append("configuration schema changed")
    if contract.get("pages") != [
        "dashboard",
        "events",
        "bible_verse",
        "about_support",
    ]:
        errors.append("focused contract does not cover all four Settings pages")
    if contract.get("reference_addons") != ["Progress Bar", "PronounceIt"]:
        errors.append("working reference add-ons are not locked")
    if (
        contract.get("native_window") is not True
        or contract.get("parent") != "Anki mw"
        or contract.get("minimum_size") != [680, 560]
        or contract.get("initial_size") != [680, 620]
        or contract.get("movable") is not True
        or contract.get("resizable") is not True
        or contract.get("default_window_flags") is not True
        or contract.get("initial_placement")
        != "Qt parent-aware QDialog placement at exec()"
        or contract.get("screen_geometry_queries")
        != "none for the primary Settings dialog"
        or contract.get("pre_exec_move") is not False
        or contract.get("primary_screen_fallback") is not False
        or contract.get("reposition_after_open") is not False
        or contract.get("saved_geometry") is not False
        or contract.get("initial_grid_mount")
        != "parent every new field to its Settings card before showing or visibility filtering"
        or contract.get("temporary_field_windows") is not False
        or contract.get("dynamic_badge_mount")
        != "parent heatmap and verse badges before visibility changes"
        or contract.get("generic_theme_sync_rebuilds_heatmap") is not False
        or contract.get("programmatic_lifecycle_focus") is not False
        or contract.get("retained_dialog_object") is not False
    ):
        errors.append("focused contract does not require the native parity dialog")

    for marker in (
        "host = grid.parentWidget()",
        "widget.setParent(host)",
        "widget.show()",
        "if not widget.isHidden():",
    ):
        if marker not in grid_mount:
            errors.append("safe initial grid mount is missing: {}".format(marker))
    if all(
        marker in grid_mount
        for marker in (
            "widget.setParent(host)",
            "widget.show()",
            "if not widget.isHidden():",
        )
    ) and not (
        grid_mount.index("widget.setParent(host)")
        < grid_mount.index("widget.show()")
        < grid_mount.index("if not widget.isHidden():")
    ):
        errors.append("grid fields must be parented before show and visibility filtering")

    heatmap_markers = (
        'selected_indicator = QLabel("✓", button)',
        "swatches.addWidget(selected_indicator)",
        "selected_indicator.setVisible(preset_name == selected)",
    )
    if not all(marker in heatmap_refresh for marker in heatmap_markers):
        errors.append("heatmap indicator is not explicitly parented before visibility")
    elif not (
        heatmap_refresh.index(heatmap_markers[0])
        < heatmap_refresh.index(heatmap_markers[1])
        < heatmap_refresh.index(heatmap_markers[2])
    ):
        errors.append("heatmap indicator visibility precedes child mounting")
    for marker in (
        'self.current_badge = QLabel("Current", self)',
        'self.selected_badge = QLabel("Selected", self)',
    ):
        if marker not in verse_row:
            errors.append("verse badge is missing an explicit row parent: {}".format(marker))
    if "self._refresh_heatmap_preset_cards()" in apply_theme:
        errors.append("generic theme synchronization still rebuilds heatmap cards")

    for marker in (
        "super().__init__(parent)",
        'self.setObjectName("HomeDashboardSettings")',
        'self.setWindowTitle("Home Screen Dashboard settings")',
        "self.setMinimumSize(680, 560)",
        "self.resize(680, 620)",
        "self.settings_shell.setMaximumWidth(1240)",
        "self.nav.setFixedWidth(152)",
        "scroll.setWidgetResizable(True)",
        "class SettingsPromptPage(QWidget):",
        "def reject(self) -> None:",
        "def closeEvent(self, event: Any) -> None:",
        "super().reject()",
    ):
        if marker not in settings:
            errors.append("missing native Settings marker: {}".format(marker))

    for marker in (
        "availableGeometry",
        "QApplication.primaryScreen",
        "clamp_window_size",
        "self.screen()",
        "self.move(",
        "def showEvent",
        "setWindowModality",
        "setModal(",
        "setWindowFlags",
        "super().__init__(parent,",
        "Qt.WindowType.Window",
        "Qt.WindowType.CustomizeWindowHint",
        "activateWindow()",
        "raise_()",
        "setGeometry(",
        "setFocus(",
        "setFocusProxy(",
        "installEventFilter(self)",
        "AnkiWebView",
        "QWebEngine",
    ):
        if marker in dialog:
            errors.append("primary dialog retains custom lifecycle marker: {}".format(marker))

    for marker in (
        "class SettingsWorkspace(QWidget):",
        "HomeDashboardSettingsWorkspace",
        "_settings_workspace",
        "_settings_menu_waiting_for_hide",
        "request_settings_open_from_menu",
        "settings_menu_about_to_hide",
        "aboutToHide",
        "QTimer.singleShot(50",
    ):
        if marker in settings + controller:
            errors.append("retired workspace or menu handoff remains: {}".format(marker))

    for marker in (
        "from .settings import SettingsDialog",
        "dialog = SettingsDialog(",
        "            mw,",
        "dialog.exec()",
    ):
        if marker not in opener:
            errors.append("native opener is missing: {}".format(marker))
    for marker in (
        "dialog.show()",
        "dialog.open()",
        "dialog.finished",
        "dialog.raise_()",
        "dialog.activateWindow()",
        "centralwidget",
        "host_layout",
        "dialog.move(",
        "parent.screen()",
        "availableGeometry()",
    ):
        if marker in opener:
            errors.append("native opener retains custom behavior: {}".format(marker))
    for marker in (
        "def _clamped_settings_origin(",
        "def _place_settings_dialog(",
        "def _report_settings_placement_failure(",
        "dialog.move(",
        "parent.screen()",
        "screen.availableGeometry()",
    ):
        if marker in controller:
            errors.append("retired pre-exec placement remains: {}".format(marker))

    if "action.triggered.connect(controller.open_settings)" not in menu:
        errors.append("native menu does not open Settings directly")
    if "QTimer" in menu or "aboutToHide" in menu:
        errors.append("native menu opening is still deferred")
    for marker in (
        "self._pending_settings_request",
        "self._settings_open_pending",
        "self._settings_request_token",
        "QTimer.singleShot(0, lambda: self._open_pending_settings(token))",
        "token != self._settings_request_token",
    ):
        if marker not in deferred:
            errors.append("WebEngine bridge deferral is missing: {}".format(marker))
    if "SettingsDialog" in deferred or "dialog.exec()" in deferred:
        errors.append("bridge callback constructs the dialog before its queued turn")

    navigation = dialog.split("    def _nav_changed", 1)[1].split(
        "    def _schedule_dashboard_anchor", 1
    )[0]
    if "self.stack.setCurrentIndex" not in navigation:
        errors.append("sidebar navigation does not stay inside the existing stack")
    for marker in (
        "QTimer",
        "setFocus(",
        "show()",
        "hide()",
        "activateWindow",
        "open_settings",
    ):
        if marker in navigation:
            errors.append("sidebar navigation performs lifecycle work: {}".format(marker))

    if errors:
        for error in errors:
            print("ERROR: {}".format(error))
        return 1
    print("Settings window contract: PASS (1.8.7, Qt-owned parented QDialog)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
