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
    surface_manifest = json.loads(
        (ROOT / "qa" / "calendar_surface_manifest_1_8_7.json").read_text(
            encoding="utf-8"
        )
    )
    surface_registry = json.loads(
        (ROOT / "qa" / "ui-surface-registry_1_8_7.json").read_text(
            encoding="utf-8"
        )
    )
    evidence_contract = json.loads(
        (ROOT / "qa" / "capture_evidence_manifest_1_8_7.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    settings = (ROOT / "settings.py").read_text(encoding="utf-8")
    model = (ROOT / "settings_model.py").read_text(encoding="utf-8")
    renderer = (ROOT / "renderer.py").read_text(encoding="utf-8")
    dashboard_js = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
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
    _require(errors, contract.get("shell_maximum_width") == 1264, "shell cap differs")
    _require(errors, contract.get("page_maximum_width") == 1080, "page cap differs")
    _require(errors, contract.get("about_page_maximum_width") == 1080, "About cap differs")
    _require(errors, contract.get("rail_width") == 184, "rail width differs")
    _require(errors, contract.get("header_height") == 72, "header height differs")
    _require(errors, contract.get("footer_height") == 56, "footer height differs")
    _require(
        errors,
        contract.get("rendered_previews")
        == "compact five-step calendar palette ramp and live Bible appearance preview only; no embedded dashboard preview",
        "rendered preview contract differs",
    )
    surface_settings = surface_manifest.get("settings_architecture", {})
    _require(
        errors,
        {
            "default_window": surface_settings.get("default_window"),
            "minimum_normal_window": surface_settings.get("minimum_normal_window"),
            "screen_margins": surface_settings.get("screen_margins"),
            "minimum_saved_visible_ratio": surface_settings.get(
                "minimum_saved_visible_ratio"
            ),
            "maximum_inner_width": surface_settings.get("maximum_inner_width"),
            "maximum_page_width": surface_settings.get("maximum_page_width"),
            "maximum_about_width": surface_settings.get("maximum_about_width"),
            "rail_width": surface_settings.get("rail_width"),
            "fixed_header_height": surface_settings.get("fixed_header_height"),
            "fixed_footer_height": surface_settings.get("fixed_footer_height"),
        }
        == {
            "default_window": contract.get("default_size"),
            "minimum_normal_window": contract.get("minimum_size"),
            "screen_margins": contract.get("screen_margins"),
            "minimum_saved_visible_ratio": contract.get(
                "minimum_saved_visible_ratio"
            ),
            "maximum_inner_width": contract.get("shell_maximum_width"),
            "maximum_page_width": contract.get("page_maximum_width"),
            "maximum_about_width": contract.get("about_page_maximum_width"),
            "rail_width": contract.get("rail_width"),
            "fixed_header_height": contract.get("header_height"),
            "fixed_footer_height": contract.get("footer_height"),
        },
        "surface manifest differs from the focused Settings window contract",
    )
    persistence = surface_manifest.get("persistence_contract", {})
    _require(
        errors,
        persistence.get("qt_window_preference")
        == "home_dashboard_overhaul/settings_dialog_geometry/v4 logical geometry screen identity available bounds and informational DPR with valid v3 migration",
        "surface geometry persistence contract differs",
    )
    _require(
        errors,
        persistence.get("settings_preview")
        == "compact five-step calendar palette ramp and live Bible appearance preview only; no embedded dashboard preview",
        "surface rendered-preview contract differs",
    )
    expected_window_fixture = (
        "logical-1080x760-default-860x640-minimum-v4-screen-aware-restored-"
        "clamped-parented-dialog-exec"
    )
    canonical_surfaces = surface_manifest.get("canonical_surfaces", [])
    canonical_by_id = {
        str(surface.get("id")): surface
        for surface in canonical_surfaces
        if isinstance(surface, dict)
    }
    _require(
        errors,
        canonical_by_id.get("SET-WINDOW", {}).get("fixture")
        == expected_window_fixture,
        "SET-WINDOW fixture differs from the implemented minimum",
    )
    _require(
        errors,
        surface_registry.get("surfaces") == canonical_surfaces,
        "surface registry differs from the governing manifest",
    )
    prohibited_fixtures = set(surface_registry.get("prohibited_fixture_kinds", []))
    _require(
        errors,
        "settings-fixed-footer" not in prohibited_fixtures
        and "settings-footer-overlay" in prohibited_fixtures,
        "surface registry footer prohibition contradicts the fixed footer",
    )
    _require(
        errors,
        contract.get("settings_profile_acceptance_gate")
        == "a structured exact-package macOS report must pass both full-screen opening paths with no desktop or Space switch; the 63 PNGs cannot satisfy or waive this gate",
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
        == {"initial": 62, "restart": 1, "total": 63},
        "Settings capture profile is not the locked 62 plus one restart lane",
    )
    _require(
        errors,
        settings_profile.get("maximum_contact_sheets") == 14,
        "Settings capture profile exceeds the 14-sheet ceiling",
    )
    _require(
        errors,
        settings_profile.get("required_application_font_percent") == 100,
        "Settings canonical capture lane is not 100 percent application font",
    )
    settings_contract_family = next(
        (
            family
            for family in capture_plan.get("families", [])
            if family.get("id") == "settings-contract"
        ),
        {},
    )
    long_title = next(
        (
            case
            for case in settings_contract_family.get("cases", [])
            if case.get("id") == "SET-EVENT-LONG-TITLE"
        ),
        {},
    )
    _require(
        errors,
        long_title.get("width") == 860
        and long_title.get("caption")
        == "Events · long title at the 860 px responsive minimum",
        "long-title capture is not labeled at the supported minimum",
    )
    _require(
        errors,
        evidence_contract.get("derived_native_frame_count")
        == {
            "initial": 114,
            "restart": 2,
            "total": 116,
            "derivation": "sum(capture_families.count)",
        },
        "full capture contract is not the derived 116-frame lane",
    )
    statistics_family = next(
        (
            family
            for family in evidence_contract.get("capture_families", [])
            if family.get("id") == "statistics-accuracy"
        ),
        {},
    )
    statistics_requirements = set(statistics_family.get("requirements", []))
    _require(
        errors,
        {
            "active-progress-N-percent-complete-inside-track",
            "initial-cards-due-equals-cards-studied-today-plus-total-remaining",
            "fixed-seven-period-average-cards-per-day-rounded-half-up",
            "86-percent-retention-and-seven-day-time-spent-no-visible-again-rate",
        }
        <= statistics_requirements
        and "86-percent-retention-and-14-percent-again"
        not in statistics_requirements,
        "statistics evidence still permits visible metric drift",
    )

    for source_name, source, markers in (
        (
            "renderer",
            renderer,
            (
                'label = "{}% complete".format(percent)',
                "data-hdo-progress-label",
                '"progress.initial_cards_due"',
                '"last_seven_days.average_cards_per_day"',
                '"last_seven_days.time_spent"',
            ),
        ),
        (
            "live dashboard",
            dashboard_js,
            (
                'Math.round(percent) + "% complete"',
                "[data-hdo-progress-label]",
                '"progress.initial_cards_due"',
                '"last_seven_days.average_cards_per_day"',
                '"last_seven_days.time_spent"',
            ),
        ),
    ):
        for marker in markers:
            _require(
                errors,
                marker in source,
                "{} is missing current visible metric marker: {}".format(
                    source_name, marker
                ),
            )
        _require(
            errors,
            '"last_seven_days.again_rate"' not in source,
            "{} still exposes Last 7 Days Again rate".format(source_name),
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
        "SETTINGS_SHELL_MAX_WIDTH = 1264",
        "SETTINGS_PAGE_MAX_WIDTH = 1080",
        "SETTINGS_ABOUT_MAX_WIDTH = 1080",
        "SETTINGS_COMPACT_BODY_WIDTH = 860",
        "SETTINGS_TWO_COLUMN_CONTENT_WIDTH = 760",
        "self.settings_shell.setMaximumWidth(SETTINGS_SHELL_MAX_WIDTH)",
        "self.sidebar_panel.setFixedWidth(SETTINGS_SIDEBAR_WIDTH)",
        "self.header_stack.setMinimumHeight(SETTINGS_HEADER_HEIGHT)",
        "self.compact_nav = QComboBox(self.header_shell)",
        "shell_width < SETTINGS_COMPACT_BODY_WIDTH",
        "scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)",
        "self.footer = SettingsFooter()",
        "self.footer.setFixedHeight(SETTINGS_FOOTER_MIN_HEIGHT)",
        'self.revert_button = QPushButton("Discard changes")',
        'self._set_status("saving", "Saving changes…")',
        'self.save_button.setText("Save changes")',
        '"Save and close"',
        "self._pending_close_after_save = True",
        '"Could not save changes. Your draft is still available."',
        "class SettingsPromptPage(QWidget):",
        "QStackedLayout.StackingMode.StackAll",
        "class VerseLibraryModel(QAbstractListModel):",
        "class VerseLibraryView(QListView):",
        '"verse" if len(self.quotes) == 1 else "verses"',
        '"{} of {} verses".format(total, len(self.quotes))',
        "self.quote_list.setMinimumHeight(68)",
        "class SuffixNumberField(QWidget):",
        'save_button.setText("Add verse" if title.startswith("Add") else "Update verse")',
        'save_button.setText("Update event" if item else "Save event")',
        "class SettingsEditorDialog(QDialog):",
        "class HeatmapPalettePreview(QWidget):",
        "class BibleAppearancePreview(QWidget):",
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
