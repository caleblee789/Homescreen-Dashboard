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
        "class SettingsOverlay(QWidget):", 1
    )[0]
    overlay = settings.split("class SettingsOverlay(QWidget):", 1)[1].split(
        "def _object_name", 1
    )[0]
    opener = controller.split("    def open_settings(", 1)[1].split(
        "    def request_settings_open", 1
    )[0]
    deferred = controller.split("    def request_settings_open(", 1)[1].split(
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
        'self.setObjectName("HomeDashboardSettingsOverlay")',
        "host.installEventFilter(self)",
        "self.setGeometry(self.host.rect())",
        "PREFERRED_WIDTH = 680",
        "PREFERRED_HEIGHT = 620",
        "COMPACT_MIN_HEIGHT = 560",
        "HOST_MARGIN = 12",
        "self.nav.setFixedWidth(152)",
    ):
        if marker not in panel + overlay:
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
        if marker in panel + overlay:
            errors.append("forbidden Settings marker: {}".format(marker))
    for marker in (
        "class SettingsDialog(QDialog):",
        "setWindowModality",
        "setModal(",
        "setWindowFlags",
        "activateWindow()",
    ):
        if marker in overlay or marker == "class SettingsDialog(QDialog):" and marker in settings:
            errors.append("primary Settings remains top-level: {}".format(marker))
    if 'getattr(getattr(mw, "form", None), "centralwidget", None)' not in opener:
        errors.append("native opener does not resolve Anki's central widget")
    if "overlay = SettingsOverlay(" not in opener or "overlay.present()" not in opener:
        errors.append("native opener does not present the child overlay")
    if "dialog.exec()" in opener or "SettingsDialog" in opener:
        errors.append("native opener still creates a dialog")
    if "self._settings_overlay = overlay" not in opener:
        errors.append("controller does not retain one child overlay")
    if "class SettingsPromptOverlay(QWidget):" not in settings:
        errors.append("primary confirmation prompts are not embedded")
    save_tail = settings.split("    def _save(self) -> None:", 1)[1].split(
        "class SettingsOverlay(QWidget):", 1
    )[0]
    if "message = QMessageBox(self)" in save_tail or "message.exec()" in save_tail:
        errors.append("primary Save or Close still creates a message box")
    if "QTimer.singleShot(0, self._open_pending_settings)" not in deferred:
        errors.append("WebEngine bridge opening is not deferred")
    if "SettingsDialog" in deferred or "settings_dialog" in deferred:
        errors.append("deferred bridge path retains or constructs a dialog")

    if errors:
        for error in errors:
            print("ERROR: {}".format(error))
        return 1
    print("Settings window contract: PASS (1.8.7, centered in-Anki child panel)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
