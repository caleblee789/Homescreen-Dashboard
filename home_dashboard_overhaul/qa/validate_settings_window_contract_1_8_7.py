#!/usr/bin/env python3
"""Validate the responsive Home Screen Dashboard 1.8.7 Settings contract."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    contract = json.loads(
        (ROOT / "qa" / "settings_window_contract_1_8_7.json").read_text(
            encoding="utf-8"
        )
    )
    capture_plan = json.loads(
        (ROOT / "qa" / "capture_plan.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    settings = (ROOT / "settings.py").read_text(encoding="utf-8")
    model = (ROOT / "settings_model.py").read_text(encoding="utf-8")
    controller = (ROOT / "controller.py").read_text(encoding="utf-8")
    dialog = settings.split("class SettingsDialog(QDialog):", 1)[1].split(
        "def _object_name", 1
    )[0]
    grid_mount = dialog.split("    def _place_grid_widgets(", 1)[1].split(
        "    def _reflow_compact_grids", 1
    )[0]
    opener = controller.split("    def open_settings(", 1)[1].split(
        "    def request_settings_open", 1
    )[0]
    deferred = controller.split("    def request_settings_open(", 1)[1].split(
        "    def save_config", 1
    )[0]
    errors: list[str] = []

    _require(errors, manifest.get("human_version") == "1.8.7", "manifest release is not 1.8.7")
    _require(errors, contract.get("release") == "1.8.7", "window contract release differs")
    _require(errors, capture_plan.get("release") == "1.8.7", "capture plan release differs")
    _require(errors, config.get("schema_version") == 8, "configuration schema changed")
    _require(errors, contract.get("minimum_size") == [720, 520], "minimum geometry differs")
    _require(errors, contract.get("default_size") == [940, 680], "default geometry differs")
    _require(
        errors,
        contract.get("initial_size_caps")
        == {"available_width_ratio": 0.92, "available_height_ratio": 0.88},
        "initial geometry caps differ",
    )
    _require(errors, contract.get("logical_coordinates") is True, "geometry is not logical")
    _require(errors, contract.get("pre_exec_geometry") is True, "geometry is not pre-exec")
    _require(errors, contract.get("reposition_after_open") is False, "post-show geometry remains")
    _require(errors, contract.get("shell_maximum_width") == 1120, "shell cap differs")
    _require(errors, contract.get("page_maximum_width") == 940, "page cap differs")
    _require(errors, contract.get("rail_width") == 152, "rail width differs")
    _require(errors, contract.get("rail_gap") == 24, "rail gap differs")

    for marker in (
        "SETTINGS_DEFAULT_SIZE = (940, 680)",
        "SETTINGS_MINIMUM_SIZE = (720, 520)",
        "SETTINGS_MAXIMUM_WIDTH_RATIO = .92",
        "SETTINGS_MAXIMUM_HEIGHT_RATIO = .88",
        "def clamp_window_geometry(",
    ):
        _require(errors, marker in model, "missing logical geometry marker: {}".format(marker))
    for marker in (
        "super().__init__(parent)",
        'self.setWindowTitle("Home Screen Dashboard Settings")',
        "self.setMinimumSize(*SETTINGS_MINIMUM_SIZE)",
        "self._apply_initial_window_geometry(parent)",
        "self.settings_shell.setMaximumWidth(SETTINGS_SHELL_MAX_WIDTH)",
        "self.compact_nav = QTabBar(self.body_shell)",
        "body_width < SETTINGS_COMPACT_BODY_WIDTH or not self.nav.labels_fit()",
        "scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)",
        "self.footer = SettingsFooter()",
        'self.revert_button = QPushButton("Discard changes")',
        'self.save_button.setText("Saving…")',
        '"Discard and close"',
        "class SettingsPromptPage(QWidget):",
        "class VerseLibraryModel(QAbstractListModel):",
        "class VerseLibraryView(QListView):",
        '"{} verses".format(len(self.quotes))',
    ):
        _require(errors, marker in settings, "missing responsive Settings marker: {}".format(marker))

    for marker in (
        "host = grid.parentWidget()",
        "widget.setParent(host)",
        "widget.show()",
        "if not widget.isHidden():",
    ):
        _require(errors, marker in grid_mount, "safe initial grid mount is missing: {}".format(marker))
    if all(marker in grid_mount for marker in ("widget.setParent(host)", "widget.show()", "if not widget.isHidden():")):
        _require(
            errors,
            grid_mount.index("widget.setParent(host)")
            < grid_mount.index("widget.show()")
            < grid_mount.index("if not widget.isHidden():"),
            "grid fields are not parented before visibility changes",
        )

    for forbidden in (
        "def showEvent",
        "activateWindow()",
        "raise_()",
        "self.move(",
        "winId()",
        "AnkiWebView",
        "QWebEngine",
        "_quote_render_limit",
        "quote_load_more",
        "class VerseRowWidget",
        "Could not save changes:",
    ):
        _require(errors, forbidden not in dialog, "forbidden Settings marker remains: {}".format(forbidden))

    for marker in (
        "from .settings import SettingsDialog",
        "dialog = SettingsDialog(",
        "            mw,",
        "dialog.exec()",
    ):
        _require(errors, marker in opener, "native opener is missing: {}".format(marker))
    for marker in (
        "dialog.show()",
        "dialog.open()",
        "dialog.finished",
        "dialog.raise_()",
        "dialog.activateWindow()",
        "dialog.move(",
    ):
        _require(errors, marker not in opener, "opener retains custom lifecycle: {}".format(marker))
    for marker in (
        "self._pending_settings_request",
        "self._settings_open_pending",
        "QTimer.singleShot(0, lambda: self._open_pending_settings(token))",
    ):
        _require(errors, marker in deferred, "WebEngine handoff deferral is missing: {}".format(marker))

    if errors:
        for error in errors:
            print("ERROR: {}".format(error))
        return 1
    print("Settings window contract: PASS (1.8.7 responsive parented QDialog)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
