#!/usr/bin/env python3
"""Validate the corrected Home Screen Dashboard 1.8.7 UI authorities."""

from __future__ import annotations

from itertools import product
import json
from pathlib import Path
import runpy
import sys
from typing import Any, List, Mapping


ROOT = Path(__file__).resolve().parents[1]
QA_ROOT = ROOT / "qa"
RELEASE = "1.8.7"
CURRENT_AUTHORITIES = {
    "surface": "calendar_surface_manifest_1_8_7.json",
    "matrix": "visual_regression_matrix_1_8_7.json",
    "registry": "ui-surface-registry_1_8_7.json",
    "capture": "capture_evidence_manifest_1_8_7.json",
    "settings": "settings_window_contract_1_8_7.json",
}


def _read(name: str) -> dict[str, Any]:
    value = json.loads((QA_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("{} must contain one JSON object".format(name))
    return value


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _require_markers(
    errors: List[str],
    relative: str,
    markers: tuple[str, ...],
) -> None:
    source = _source(relative)
    for marker in markers:
        if marker not in source:
            errors.append("{} is missing release marker: {}".format(relative, marker))


def _validate_palette_matrix(errors: List[str], matrix: Mapping[str, Any]) -> None:
    palettes = matrix.get("palette_ids_by_theme", {})
    modes = matrix.get("modes", [])
    expected = {
        (theme, palette, mode)
        for theme, names in palettes.items()
        for palette, mode in product(names, modes)
    } if isinstance(palettes, Mapping) else set()
    cases = matrix.get("palette_cases", [])
    actual = {
        (case.get("theme"), case.get("palette"), case.get("mode"))
        for case in cases if isinstance(case, Mapping)
    }
    ids = [case.get("id") for case in cases if isinstance(case, Mapping)]
    if not expected or actual != expected or len(ids) != len(set(ids)) or len(ids) != len(expected):
        errors.append("palette matrix must cover every saved ID and mode exactly once")
    axes = matrix.get("settings_page_axes", {})
    if axes != {
        "page": ["dashboard", "events", "bible_verse", "about_support"],
        "window_width": [1080, 1280, "full-screen"],
        "application_font_percent": [100],
    }:
        errors.append("Settings page axes must use 1080, 1280, full-screen and 100 percent")
    if matrix.get("settings_page_case_count") != 12:
        errors.append("Settings page matrix must contain 12 derived cases")


def validate(root: Path = ROOT) -> List[str]:
    del root
    errors: List[str] = []
    surface = _read(CURRENT_AUTHORITIES["surface"])
    matrix = _read(CURRENT_AUTHORITIES["matrix"])
    registry = _read(CURRENT_AUTHORITIES["registry"])
    capture = _read(CURRENT_AUTHORITIES["capture"])
    settings = _read(CURRENT_AUTHORITIES["settings"])
    addon_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    try:
        plan_namespace = runpy.run_path(str(QA_ROOT / "capture_plan.py"))
        plan = plan_namespace["load_capture_plan"](QA_ROOT / "capture_plan.json")
        plan.validate_authorities(QA_ROOT)
    except Exception as exc:
        errors.append("capture execution plan is invalid: {}".format(exc))
        plan = None

    authorities = (surface, matrix, registry, capture, settings)
    if addon_manifest.get("human_version") != RELEASE:
        errors.append("add-on manifest must target release {}".format(RELEASE))
    if config.get("schema_version") != 8:
        errors.append("configuration schema must remain 8")
    if any(authority.get("release") != RELEASE for authority in authorities):
        errors.append("all current UI authorities must target release {}".format(RELEASE))
    if surface.get("schema_version") != 8:
        errors.append("surface authority schema must remain 8")
    if surface.get("contract") != "corrected-native-settings-and-production-dashboard-release-ui-2026-08-26":
        errors.append("surface authority has the wrong governing contract")
    if registry.get("surfaces") != surface.get("canonical_surfaces") or registry.get("exact_once") is not True:
        errors.append("surface registry must exactly mirror the governing authority")

    expected_settings = {
        "default_size": [1080, 760],
        "minimum_size": [860, 640],
        "screen_margins": {"normal": 48, "small_screen_fallback": 24},
        "minimum_saved_visible_ratio": .8,
        "geometry_version": 4,
        "previous_geometry_version": 3,
        "shell_maximum_width": 1120,
        "page_maximum_width": 920,
        "about_page_maximum_width": 840,
        "rail_width": 184,
        "header_height": 72,
        "footer_height": 56,
        "compact_navigation": "single-line synchronized QTabBar whenever retaining the 184 px rail would leave less than 680 logical pixels for the main region; the 860 px supported minimum is compact",
        "reposition_after_open": "one decoration-only clamp when the decorated frame is outside the active screen; never move an already-contained frame",
    }
    if not isinstance(settings, Mapping) or any(settings.get(key) != value for key, value in expected_settings.items()):
        errors.append("focused v4 Settings geometry and responsive architecture drifted")

    criteria = surface.get("acceptance_criteria", [])
    criteria_ids = [item.get("id") for item in criteria if isinstance(item, Mapping)]
    if len(criteria_ids) < 20 or len(criteria_ids) != len(set(criteria_ids)):
        errors.append("acceptance criteria must contain unique implementation-owned IDs")
    if any(not item.get("tags") or not str(item.get("requirement", "")).strip() for item in criteria):
        errors.append("every acceptance criterion needs tags and a requirement")

    _validate_palette_matrix(errors, matrix)
    if plan is not None:
        families = {
            item.get("id"): item for item in capture.get("capture_families", [])
            if isinstance(item, Mapping)
        }
        expected_counts = {
            str(family["id"]): len(plan.family_ids(str(family["id"])))
            for family in plan.raw["families"]
        }
        actual_counts = {key: item.get("count") for key, item in families.items()}
        if actual_counts != expected_counts:
            errors.append("capture family counts differ from the declarative plan")
        derived = capture.get("derived_native_frame_count", {})
        if {key: derived.get(key) for key in ("initial", "restart", "total")} != plan.counts("full"):
            errors.append("derived native frame counts differ from the declarative plan")
        if plan.counts("full") != {"initial": 92, "restart": 2, "total": 94}:
            errors.append("corrected full capture plan must contain 94 frames")
        if plan.counts("settings") != {"initial": 40, "restart": 1, "total": 41}:
            errors.append("minimal Settings capture plan must contain exactly 41 frames")
        if 2 + len(plan.detail_groups("settings")) > 11:
            errors.append("minimal Settings capture plan exceeds 11 sheets")
        required_manual_results = [
            "macos-fullscreen-no-space-switch-menu-and-dashboard-gear"
        ]
        if (
            plan.profile("settings").get("required_structured_manual_results")
            != required_manual_results
        ):
            errors.append("Settings profile does not require the no-Space-switch result")
        gate = capture.get("settings_profile_structured_manual_gate")
        if gate != {
            "id": required_manual_results[0],
            "report_schema_version": 2,
            "required_for_acceptance": True,
            "adds_png_frames": False,
            "opening_paths": ["menu", "dashboard-gear"],
            "workflow_steps_per_path": [
                "all-four-pages",
                "events-tabs",
                "resize",
                "event-edit",
                "verse-edit",
                "save",
                "close-reopen",
                "controlled-restart",
            ],
            "required_result": "every workflow step through both paths remains on the current native Anki full-screen Space with no desktop switch",
        }:
            errors.append("Settings structured full-screen acceptance gate drifted")
        if capture.get("native_platform_profile_contract") != {
            "geometry": "physical width and height equal available logical width and height multiplied by the declared device pixel ratio within one percent or two pixels",
            "dpr_1": "DPR is within 0.05 of 1.0 and physical and logical dimensions match",
            "native_scale": "native-class DPR matches declared OS scale within 0.08; environment scale substitutes are forbidden",
            "settings_pages": ["dashboard", "events", "bible_verse", "about_support"],
            "settings_page_assertions": [
                "horizontal_scroll_zero",
                "visible_controls_contained",
                "labels_unclipped_or_approved",
                "segmented_selection_matches_model",
                "body_footer_disjoint",
                "footer_actions_visible",
                "page_bottom_reachable",
                "target_fully_visible",
            ],
            "macos_fullscreen_schema_version": 2,
        }:
            errors.append("native platform profile validation contract drifted")
        if (
            "macos-fullscreen-menu-and-dashboard-gear-open-without-desktop-space-switch"
            not in matrix.get("settings_quality_assertions", [])
        ):
            errors.append("visual matrix does not prohibit the desktop/Space-switch regression")
        if (
            "every-png-sample-matches-live-settings-surface"
            not in matrix.get("settings_quality_assertions", [])
        ):
            errors.append("visual matrix does not reject background-only Settings PNGs")
        settings_families = {
            item.get("id"): item
            for item in capture.get("capture_families", [])
        }
        for family_id in ("settings-pages", "settings-contract"):
            if "live-settings-surface-sample-match" not in settings_families.get(
                family_id, {}
            ).get("requirements", []):
                errors.append("{} lacks live Settings surface verification".format(family_id))
        platform_matrix = plan.raw.get("native_platform_matrix")
        if capture.get("required_native_platform_profiles") != platform_matrix:
            errors.append("capture platform matrix differs from the execution plan")
        if matrix.get("required_native_platform_profiles") != platform_matrix:
            errors.append("visual platform matrix differs from the execution plan")

    expected_unrun = {
        "windows-native-settings-validation",
        "linux-native-settings-validation",
        "alternate-os-scaling-settings-validation",
        "alternate-application-font-settings-validation",
        "voiceover_review",
        "forced_colors_review",
    }
    if set(capture.get("deferred_unrun", [])) != expected_unrun:
        errors.append("Settings unrun gates are not explicit")
    if set(matrix.get("deferred_unrun", [])) != expected_unrun:
        errors.append("visual nonblocking boundaries are incorrect")
    if capture.get("status") != "required-before-release":
        errors.append("fresh 1.8.7 evidence must remain required before release")

    _require_markers(errors, "settings.py", (
        'self.setWindowTitle("Home Screen Dashboard Settings")',
        "self.setMinimumSize(\n            min(SETTINGS_MINIMUM_SIZE[0], geometry[2])",
        "self._apply_initial_window_geometry(parent)",
        "migrated = migrate_saved_window_geometry(",
        "saved_valid = migrated is not None",
        "SETTINGS_GEOMETRY_SCREEN_KEY",
        "self.settings_shell.setMaximumWidth(SETTINGS_SHELL_MAX_WIDTH)",
        "SETTINGS_SHELL_MAX_WIDTH = 1120",
        "SETTINGS_PAGE_MAX_WIDTH = 920",
        "SETTINGS_ABOUT_MAX_WIDTH = 840",
        "SETTINGS_COMPACT_BODY_WIDTH = SETTINGS_SIDEBAR_WIDTH + 680",
        "SETTINGS_SIDEBAR_WIDTH = 184",
        "SETTINGS_HEADER_HEIGHT = 72",
        "SETTINGS_FOOTER_MIN_HEIGHT = 56",
        "self.compact_nav = QTabBar",
        "ScrollBarPolicy.ScrollBarAlwaysOff",
        "class SettingsFooter(QWidget)",
        'self.revert_button = QPushButton("Discard changes")',
        "class DisclosureHeader(QPushButton)",
        "class VerseLibraryModel(QAbstractListModel)",
        "class VerseLibraryDelegate(QStyledItemDelegate)",
        "self.heatmap_preset = QComboBox()",
        'SettingsCard("Version and support")',
        "scope_differs_from_defaults",
        "Could not save changes. Your draft is still available.",
        '"Unsaved changes"',
        '("Cancel", "secondary", lambda: None)',
        '("Discard", "danger", self._close_dialog)',
        '("Save and close", "primary", self._save_and_close)',
        'self._set_status("saving", "Saving changes...")',
        'self.save_button.setText("Save changes")',
        "self._set_mutation_controls_enabled(False)",
        'SettingsCard("Study metrics", "", "Reset")',
        '"Advanced appearance"',
        '"Export verse library edits"',
        "def showEvent(self, event: Any) -> None:",
        "QTimer.singleShot(0, self._correct_decorated_frame_if_needed)",
        "if available.contains(frame):",
        "self.move(self.pos() + QPoint(dx, dy))",
    ))
    _require_markers(errors, "settings_model.py", (
        "SETTINGS_DEFAULT_SIZE = (1080, 760)",
        "SETTINGS_MINIMUM_SIZE = (860, 640)",
        "SETTINGS_NORMAL_SCREEN_MARGIN = 48",
        "SETTINGS_SMALL_SCREEN_MARGIN = 24",
        "SETTINGS_GEOMETRY_VERSION = 4",
        "SETTINGS_PREVIOUS_GEOMETRY_VERSION = 3",
        "def saved_window_geometry_is_valid(",
        "def migrate_saved_window_geometry(",
        "def clamp_window_geometry(",
        "def scope_differs_from_defaults(",
        "def scope_snapshot(",
        "def restore_scope(",
        '"calendar_display": _CALENDAR_DISPLAY_RESET_PATHS',
        '"calendar_range": _CALENDAR_RANGE_RESET_PATHS',
        '"local_data": _LOCAL_DATA_RESET_PATHS',
    ))
    _require_markers(errors, "controller.py", (
        "dialog = SettingsDialog(",
        "mw,",
        "active_dialog = self._active_settings_dialog",
        "self._route_active_settings_dialog(active_dialog, request)",
        "self._active_settings_dialog = dialog",
        "dialog.exec()",
        "if self._active_settings_dialog is dialog:",
        "self._active_settings_dialog = None",
        "QTimer.singleShot(0, lambda: self._open_pending_settings(token))",
        "def _persist_settings_transaction(",
    ))
    _require_markers(errors, "themes.py", (
        '"ui_sidebar": "#0A1016"',
        '"ui_accent_soft": "#263B4D"',
        '"ui_sidebar": "#E9EEF3"',
        '"ui_accent_soft": "#DFEAF3"',
    ))

    settings_source = _source("settings.py")
    dialog_source = settings_source.split("class SettingsDialog(QDialog):", 1)[1].split("def _object_name", 1)[0]
    for retired in (
        "Qt.WindowType.Tool",
        "self.winId()",
        "setTransientParent",
        "Qt.WindowModality.NonModal",
        "objc_msgSend",
        "raise_()",
        "activateWindow()",
        "AnkiWebView",
        "QWebEngine",
        "DashboardCardPreview",
        "VerseCardPreview",
        "HeatmapPresetCard",
        "heatmap_preset_cards",
        "preset_swatch",
        "class VerseRowWidget",
        "Showing 100",
        "LOAD_MORE_BATCH",
        "Study calculations",
        "Revert changes",
        "simulated transactional write failure",
    ):
        if retired in settings_source:
            errors.append("retired Settings behavior remains: {}".format(retired))
    if dialog_source.count("self.move(") != 1:
        errors.append(
            "Settings may move only in the one guarded decorated-frame correction"
        )
    if dialog_source.index("self._apply_initial_window_geometry(parent)") > dialog_source.index("self._build_dashboard_page()"):
        errors.append("Settings geometry must be applied before the first page is built or shown")
    controller_source = _source("controller.py")
    for retired in (
        "dialog.open()",
        "dialog.show()",
        "dialog.finished.connect(",
        "dialog.raise_()",
        "dialog.activateWindow()",
    ):
        if retired in controller_source:
            errors.append("retired top-level Settings lifecycle remains: {}".format(retired))

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print("ERROR: {}".format(error))
        return 1
    derived = _read(CURRENT_AUTHORITIES["capture"])["derived_native_frame_count"]
    print(
        "Corrected UI contract: PASS ({} schema 8, {} planned native frames; release evidence still required)".format(
            RELEASE, derived["total"]
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
