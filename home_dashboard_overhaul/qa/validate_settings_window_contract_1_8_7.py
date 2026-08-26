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
    opener = controller.split("    def open_settings(", 1)[1].split(
        "    def request_settings_open", 1
    )[0]
    deferred = controller.split("    def request_settings_open(", 1)[1].split(
        "    def save_config", 1
    )[0]
    menu = settings.split("def install_settings_menu", 1)[1]
    placement = controller.split("def _clamped_settings_origin(", 1)[1].split(
        "class DashboardController:", 1
    )[0]

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
        != "one pre-exec parent-centered move clamped to mw.screen().availableGeometry()"
        or contract.get("screen_geometry_queries")
        != "mw.screen().availableGeometry() only"
        or contract.get("primary_screen_fallback") is not False
        or contract.get("reposition_after_open") is not False
        or contract.get("saved_geometry") is not False
        or contract.get("programmatic_lifecycle_focus") is not False
        or contract.get("retained_dialog_object") is not False
    ):
        errors.append("focused contract does not require the native parity dialog")

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
        "_place_settings_dialog(dialog, mw)",
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
    ):
        if marker in opener:
            errors.append("native opener retains custom behavior: {}".format(marker))
    if opener.index("_place_settings_dialog(dialog, mw)") > opener.index("dialog.exec()"):
        errors.append("screen-safe placement must occur immediately before exec")

    for marker in (
        "parent.screen()",
        "screen.availableGeometry()",
        "dialog.move(*origin)",
        "_report_settings_placement_failure(mw)",
    ):
        if marker not in controller:
            errors.append("screen-safe placement is missing: {}".format(marker))
    if placement.count("dialog.move(") != 1:
        errors.append("Settings placement must move the dialog exactly once")
    for marker in (
        "QApplication.primaryScreen",
        "dialog.screen()",
        "setScreen(",
        "showEvent",
        "activateWindow()",
        "raise_()",
        "QTimer",
    ):
        if marker in placement:
            errors.append("screen-safe placement retains forbidden behavior: {}".format(marker))

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
    print("Settings window contract: PASS (1.8.7, screen-safe native QDialog)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
