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
    release_probe = (ROOT / "qa" / "runtime_probe_release_1_8_7.py").read_text(
        encoding="utf-8"
    )
    review_assembler = (
        ROOT / "qa" / "assemble_settings_review_evidence_1_8_7.py"
    ).read_text(encoding="utf-8")
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
    _require(errors, contract.get("minimum_size") == [860, 640], "minimum geometry differs")
    _require(errors, contract.get("default_size") == [1080, 760], "default geometry differs")
    _require(
        errors,
        contract.get("screen_margins")
        == {"normal": 48, "small_screen_fallback": 24},
        "screen margins differ",
    )
    _require(errors, contract.get("minimum_saved_visible_ratio") == 0.8, "saved visibility threshold differs")
    _require(errors, contract.get("logical_coordinates") is True, "geometry is not logical")
    _require(errors, contract.get("pre_exec_geometry") is True, "geometry is not pre-exec")
    _require(
        errors,
        contract.get("reposition_after_open")
        == "one decoration-only clamp when the decorated frame is outside the active screen; never move an already-contained frame",
        "post-show geometry policy differs",
    )
    _require(errors, contract.get("geometry_version") == 4, "geometry version differs")
    _require(errors, contract.get("previous_geometry_version") == 3, "geometry migration source differs")
    _require(
        errors,
        contract.get("geometry_key")
        == "home_dashboard_overhaul/settings_dialog_geometry/v4",
        "geometry key differs",
    )
    _require(
        errors,
        contract.get("geometry_screen_key")
        == "home_dashboard_overhaul/settings_dialog_geometry/v4_screen",
        "geometry screen key differs",
    )
    _require(
        errors,
        contract.get("geometry_available_key")
        == "home_dashboard_overhaul/settings_dialog_geometry/v4_available",
        "geometry available-bounds key differs",
    )
    _require(
        errors,
        contract.get("geometry_dpr_key")
        == "home_dashboard_overhaul/settings_dialog_geometry/v4_dpr",
        "geometry DPR key differs",
    )
    _require(errors, contract.get("shell_maximum_width") == 1120, "shell cap differs")
    _require(errors, contract.get("page_maximum_width") == 920, "page cap differs")
    _require(errors, contract.get("about_page_maximum_width") == 840, "About cap differs")
    _require(errors, contract.get("rail_width") == 184, "rail width differs")
    _require(errors, contract.get("header_height") == 72, "header height differs")
    _require(errors, contract.get("footer_height") == 56, "footer height differs")
    _require(
        errors,
        contract.get("settings_profile_acceptance_gate")
        == "a structured exact-package macOS report must pass both full-screen opening paths with no desktop or Space switch; the 41 PNGs cannot satisfy or waive this gate",
        "full-screen no-Space-switch acceptance gate differs",
    )
    settings_profile = next(
        (
            profile
            for profile in capture_plan.get("profiles", [])
            if profile.get("id") == "settings"
        ),
        {},
    )
    _require(
        errors,
        settings_profile.get("required_structured_manual_results")
        == ["macos-fullscreen-no-space-switch-menu-and-dashboard-gear"],
        "Settings capture profile does not require the full-screen no-switch result",
    )
    _require(
        errors,
        settings_profile.get("expected_capture_counts")
        == {"initial": 40, "restart": 1, "total": 41},
        "Settings capture profile is not the locked 40 plus one restart lane",
    )
    _require(
        errors,
        settings_profile.get("maximum_contact_sheets") == 11,
        "Settings capture profile exceeds the 11-sheet ceiling",
    )
    _require(
        errors,
        settings_profile.get("required_application_font_percent") == 100,
        "Settings canonical capture lane is not 100 percent application font",
    )

    for marker in (
        "SETTINGS_DEFAULT_SIZE = (1080, 760)",
        "SETTINGS_MINIMUM_SIZE = (860, 640)",
        "SETTINGS_NORMAL_SCREEN_MARGIN = 48",
        "SETTINGS_SMALL_SCREEN_MARGIN = 24",
        "SETTINGS_MINIMUM_VISIBLE_RATIO = .80",
        "SETTINGS_GEOMETRY_VERSION = 4",
        "SETTINGS_PREVIOUS_GEOMETRY_VERSION = 3",
        "def saved_window_geometry_is_valid(",
        "def migrate_saved_window_geometry(",
        "def settings_screen_uses_compact_fallback(",
        "def clamp_window_geometry(",
    ):
        _require(errors, marker in model, "missing logical geometry marker: {}".format(marker))
    for marker in (
        "super().__init__(parent)",
        'self.setWindowTitle("Home Screen Dashboard Settings")',
        "self.setMinimumSize(\n            min(SETTINGS_MINIMUM_SIZE[0], geometry[2])",
        "self._apply_initial_window_geometry(parent)",
        "SETTINGS_SHELL_MAX_WIDTH = 1120",
        "SETTINGS_PAGE_MAX_WIDTH = 920",
        "SETTINGS_ABOUT_MAX_WIDTH = 840",
        "SETTINGS_COMPACT_BODY_WIDTH = SETTINGS_SIDEBAR_WIDTH + 680",
        "self.settings_shell.setMaximumWidth(SETTINGS_SHELL_MAX_WIDTH)",
        "self.sidebar_panel.setFixedWidth(SETTINGS_SIDEBAR_WIDTH)",
        "self.header_stack.setMinimumHeight(SETTINGS_HEADER_HEIGHT)",
        "self.compact_nav = QTabBar(self.header_shell)",
        "shell_width < SETTINGS_COMPACT_BODY_WIDTH",
        "scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)",
        "self.footer = SettingsFooter()",
        "self.setMinimumHeight(SETTINGS_FOOTER_MIN_HEIGHT)",
        'self.revert_button = QPushButton("Discard changes")',
        'self._set_status("saving", "Saving changes...")',
        'self.save_button.setText("Save changes")',
        '"Save and close"',
        "self._pending_close_after_save = True",
        '"Could not save changes. Your draft is still available."',
        "class SettingsPromptPage(QWidget):",
        "QStackedLayout.StackingMode.StackAll",
        "class VerseLibraryModel(QAbstractListModel):",
        "class VerseLibraryView(QListView):",
        '"{} verses".format(len(self.quotes))',
        '"{} of {} verses".format(total, len(self.quotes))',
        "target = max(180, min(520, viewport_height - 300))",
        "class SuffixNumberField(QWidget):",
        'save_button.setText("Add verse" if title.startswith("Add") else "Update verse")',
        'save_button.setText("Update event" if item else "Add event")',
        'SETTINGS_GEOMETRY_KEY = "home_dashboard_overhaul/settings_dialog_geometry/v4"',
        'SETTINGS_GEOMETRY_SCREEN_KEY = "home_dashboard_overhaul/settings_dialog_geometry/v4_screen"',
        'SETTINGS_GEOMETRY_AVAILABLE_KEY = "home_dashboard_overhaul/settings_dialog_geometry/v4_available"',
        'SETTINGS_GEOMETRY_DPR_KEY = "home_dashboard_overhaul/settings_dialog_geometry/v4_dpr"',
        'SETTINGS_PREVIOUS_GEOMETRY_KEY = "home_dashboard_overhaul/settings_dialog_geometry/v3"',
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
        "activateWindow()",
        "raise_()",
        "winId()",
        "AnkiWebView",
        "QWebEngine",
        "_quote_render_limit",
        "quote_load_more",
        "class VerseRowWidget",
        "Could not save changes:",
        "class DashboardCardPreview",
        "class VerseCardPreview",
        "HeatmapPresetCard",
        "settings_dialog_geometry/v2",
    ):
        _require(errors, forbidden not in dialog, "forbidden Settings marker remains: {}".format(forbidden))

    for marker in (
        "def showEvent(self, event: Any) -> None:",
        "if not self._post_show_clamp_done:",
        "QTimer.singleShot(0, self._correct_decorated_frame_if_needed)",
        "def _correct_decorated_frame_if_needed(self) -> None:",
        "if available.contains(frame):",
        "if dx or dy:",
        "self.move(self.pos() + QPoint(dx, dy))",
    ):
        _require(errors, marker in dialog, "decorated-frame guard is missing: {}".format(marker))
    _require(
        errors,
        dialog.count("self.move(") == 1,
        "Settings may move only in the one guarded decorated-frame correction",
    )

    for marker in (
        "from .settings import SettingsDialog",
        "dialog = SettingsDialog(",
        "            mw,",
        "self._active_settings_dialog = dialog",
        "finally:",
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
        "active_dialog = self._active_settings_dialog",
        "self._route_active_settings_dialog(active_dialog, request)",
        "if self._active_settings_dialog is dialog:",
        "self._active_settings_dialog = None",
    ):
        _require(errors, marker in opener, "single active-dialog routing is missing: {}".format(marker))
    for marker in (
        "settings_surface_match_ratio",
        "settings_surface_verified",
        "decorated_window_included",
        "native_frame_decoration",
        "active_dialog.exec()",
        "Settings page capture lacks native window decoration",
        "native Settings capture sampled the parent background instead of the Settings surface",
    ):
        _require(errors, marker in release_probe, "Settings capture verification is missing: {}".format(marker))
    _require(
        errors,
        "record.get(\"settings_surface_verified\") is True" in review_assembler,
        "Settings evidence assembler does not reject background-only PNGs",
    )
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
