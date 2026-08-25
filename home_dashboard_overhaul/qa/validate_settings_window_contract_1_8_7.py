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
    panel = settings.split("class SettingsPanel(QWidget):", 1)[1].split(
        "class SettingsWorkspace(QWidget):", 1
    )[0]
    workspace = settings.split("class SettingsWorkspace(QWidget):", 1)[1].split(
        "def _object_name", 1
    )[0]
    opener = controller.split("    def open_settings(", 1)[1].split(
        "    def request_settings_open", 1
    )[0]
    deferred = controller.split("    def request_settings_open(", 1)[1].split(
        "    def request_settings_open_from_menu", 1
    )[0]
    menu_deferred = controller.split(
        "    def request_settings_open_from_menu", 1
    )[1].split(
        "    def save_config", 1
    )[0]

    errors = []
    if manifest.get("human_version") != contract.get("release"):
        errors.append("manifest and Settings window contract versions differ")
    if config.get("schema_version") != contract.get("schema_version"):
        errors.append("configuration schema changed")
    if contract.get("pages") != ["dashboard", "events", "bible_verse", "about_support"]:
        errors.append("focused contract does not cover all four Settings pages")
    if contract.get("native_window") is not False:
        errors.append("Settings contract still permits a native window")
    if contract.get("top_level_fallback") is not False:
        errors.append("Settings contract still permits a top-level fallback")
    if contract.get("preferred_size") != [680, 620]:
        errors.append("Settings preferred size changed")
    if contract.get("compact_min_height") != 560 or contract.get("host_margin") != 12:
        errors.append("Settings compact geometry changed")
    for marker in (
        "super().__init__(host)",
        'self.setObjectName("HomeDashboardSettingsWorkspace")',
        "self.host_layout.insertWidget(self.insert_index, self, 1)",
        "self.host_layout.removeWidget(self)",
        "widget.hide()",
        "widget.setVisible(was_visible)",
        "workspace_layout.addWidget(",
        "Qt.AlignmentFlag.AlignCenter",
        "PREFERRED_WIDTH = 680",
        "PREFERRED_HEIGHT = 620",
        "COMPACT_MIN_HEIGHT = 560",
        "HOST_MARGIN = 12",
        "FOCUS_RETRY_DELAY_MS = 16",
        "FOCUS_RETRY_LIMIT = 2",
        "self.nav.setFixedWidth(152)",
        "self.setFocusProxy(self.panel.nav)",
        "QApplication.activeWindow() is not mw",
        "self.isWindow()",
        "self.window() is not mw",
        "self.setFocus(Qt.FocusReason.OtherFocusReason)",
        "application.installEventFilter(self)",
        "application.removeEventFilter(self)",
        "QEvent.Type.ShortcutOverride",
        "event.matches(QKeySequence.StandardKey.Close)",
        "self._saved_callback = saved_callback",
        "self._saved_callback()",
        "def _settings_saved",
        "def _rehide_after_save",
    ):
        if marker not in panel + workspace:
            errors.append("missing Settings marker: {}".format(marker))
    for marker in (
        "availableGeometry",
        "QApplication.primaryScreen",
        "clamp_window_size",
        "self.screen()",
        "self.move(",
        "def showEvent",
        "AnkiWebView",
        "QWebEngine",
    ):
        if marker in panel + workspace:
            errors.append("forbidden Settings marker: {}".format(marker))
    for marker in (
        "class SettingsDialog(QDialog):",
        "setWindowModality",
        "setModal(",
        "setWindowFlags",
        "activateWindow()",
        "raise_()",
        "setGeometry(",
    ):
        if marker in workspace or marker == "class SettingsDialog(QDialog):" and marker in settings:
            errors.append("primary Settings remains top-level: {}".format(marker))
    if 'getattr(getattr(mw, "form", None), "centralwidget", None)' not in opener:
        errors.append("native opener does not resolve Anki's central widget")
    if "workspace = SettingsWorkspace(" not in opener or "workspace.attach()" not in opener:
        errors.append("native opener does not attach the central workspace")
    if "dialog.exec()" in opener or "SettingsDialog" in opener:
        errors.append("native opener still creates a dialog")
    if "self._settings_workspace = workspace" not in opener:
        errors.append("controller does not retain one central workspace")
    if "class SettingsPromptPage(QWidget):" not in settings:
        errors.append("primary confirmation prompts are not layout-managed")
    save_tail = settings.split("    def _save(self) -> None:", 1)[1].split(
        "class SettingsWorkspace(QWidget):", 1
    )[0]
    if "message = QMessageBox(self)" in save_tail or "message.exec()" in save_tail:
        errors.append("primary Save or Close still creates a message box")
    if "QTimer.singleShot(0, lambda: self._open_pending_settings(token))" not in deferred:
        errors.append("WebEngine bridge opening is not deferred")
    if "SettingsDialog" in deferred or "settings_dialog" in deferred:
        errors.append("deferred bridge path retains or constructs a dialog")
    for marker in (
        "QTimer.singleShot(50, lambda: self._open_pending_settings(token))",
        "def settings_menu_about_to_hide",
        "QTimer.singleShot(0, lambda: self._open_pending_settings(token))",
        "token != self._settings_request_token",
    ):
        if marker not in menu_deferred:
            errors.append("native menu handoff is missing: {}".format(marker))
    for marker in (
        "connect(controller.settings_menu_about_to_hide)",
        "action.triggered.connect(controller.request_settings_open_from_menu)",
    ):
        if marker not in settings:
            errors.append("native menu wiring is missing: {}".format(marker))

    begin_attach = workspace.split("    def _begin_attach", 1)[1].split(
        "    def _verify_attach_focus", 1
    )[0]
    attach_markers = (
        "self.host_layout.insertWidget",
        "self.show()",
        "self.isWindow()",
        "self.setFocus(Qt.FocusReason.OtherFocusReason)",
    )
    if any(marker not in begin_attach for marker in attach_markers) or not all(
        begin_attach.index(left) < begin_attach.index(right)
        for left, right in zip(attach_markers, attach_markers[1:])
    ):
        errors.append("Settings attachment is not insert-show-verify-focus ordered")
    verify_attach = workspace.split("    def _verify_attach_focus", 1)[1].split(
        "    def _hide_backing_widgets", 1
    )[0]
    if (
        "self._owns_widget(focus)" not in verify_attach
        or "self._hide_backing_widgets()" not in verify_attach
        or verify_attach.index("self._owns_widget(focus)")
        > verify_attach.index("self._hide_backing_widgets()")
    ):
        errors.append("backing widgets can be hidden before Settings owns focus")
    close_path = workspace.split("    def close_panel", 1)[1].split(
        "    def _finish_close_focus", 1
    )[0]
    if (
        "self._restore_backing_widgets()" not in close_path
        or "target.setFocus" not in close_path
        or "QTimer.singleShot(0" not in close_path
        or not (
            close_path.index("self._restore_backing_widgets()")
            < close_path.index("target.setFocus")
            < close_path.index("QTimer.singleShot(0")
        )
        or "self.host_layout.removeWidget(self)" in close_path
    ):
        errors.append("Settings close does not restore-focus-then-remove")
    navigation = panel.split("    def _nav_changed", 1)[1].split(
        "    def _schedule_dashboard_anchor", 1
    )[0]
    if "self.stack.setCurrentIndex" not in navigation:
        errors.append("sidebar navigation does not stay inside the existing stack")
    for marker in ("attach(", "hide()", "show()", "setFocus(", "window()"):
        if marker in navigation:
            errors.append("sidebar navigation performs a host lifecycle operation")

    if contract.get("focus_handoff") != "insert show focus then hide backing":
        errors.append("focused contract does not lock the atomic focus handoff")
    if contract.get("close_handoff") != "show backing restore focus then remove workspace":
        errors.append("focused contract does not lock the reverse close handoff")

    if errors:
        for error in errors:
            print("ERROR: {}".format(error))
        return 1
    print("Settings window contract: PASS (1.8.7, focus-safe in-Anki workspace)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
