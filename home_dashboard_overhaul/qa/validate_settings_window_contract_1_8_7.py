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
        "def install_settings_menu", 1
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
    for marker in (
        "parent: QWidget",
        "super().__init__(parent)",
        "self.setMinimumSize(680, 560)",
        "self.resize(680, 620)",
        "self.nav.setFixedWidth(152)",
    ):
        if marker not in dialog:
            errors.append("missing Settings marker: {}".format(marker))
    for marker in (
        "availableGeometry",
        "QApplication.primaryScreen",
        "clamp_window_size",
        "self.screen()",
        "self.move(",
        "setWindowModality",
        "setModal(",
        "def showEvent",
        "AnkiWebView",
        "QWebEngine",
    ):
        if marker in dialog:
            errors.append("forbidden Settings marker: {}".format(marker))
    if "dialog = SettingsDialog(mw, self, page_name, date_value, event_value)" not in opener:
        errors.append("native opener does not pass Anki's main window explicitly")
    if "dialog.exec()" not in opener:
        errors.append("native opener does not use local exec")
    if "QTimer.singleShot(0, self._open_pending_settings)" not in deferred:
        errors.append("WebEngine bridge opening is not deferred")
    if "SettingsDialog" in deferred or "settings_dialog" in deferred:
        errors.append("deferred bridge path retains or constructs a dialog")

    if errors:
        for error in errors:
            print("ERROR: {}".format(error))
        return 1
    print("Settings window contract: PASS (1.8.7, 680x620 Progress Bar parity)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
