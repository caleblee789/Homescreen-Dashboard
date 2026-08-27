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
        "window_width": [720, 940, "full-screen"],
        "application_font_percent": [100, 150],
    }:
        errors.append("Settings page axes must use 720, 940, full-screen and 100/150 percent")
    if matrix.get("settings_page_case_count") != 24:
        errors.append("Settings page matrix must contain 24 derived cases")


def validate(root: Path = ROOT) -> List[str]:
    del root
    errors: List[str] = []
    surface = _read(CURRENT_AUTHORITIES["surface"])
    matrix = _read(CURRENT_AUTHORITIES["matrix"])
    registry = _read(CURRENT_AUTHORITIES["registry"])
    capture = _read(CURRENT_AUTHORITIES["capture"])
    addon_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    try:
        plan_namespace = runpy.run_path(str(QA_ROOT / "capture_plan.py"))
        plan = plan_namespace["load_capture_plan"](QA_ROOT / "capture_plan.json")
        plan.validate_authorities(QA_ROOT)
    except Exception as exc:
        errors.append("capture execution plan is invalid: {}".format(exc))
        plan = None

    authorities = (surface, matrix, registry, capture)
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

    settings = surface.get("settings_architecture", {})
    expected_settings = {
        "default_window": [940, 680],
        "minimum_normal_window": [720, 520],
        "initial_available_geometry_caps": {"width": .92, "height": .88},
        "maximum_inner_width": 1120,
        "maximum_page_width": 940,
        "rail_width": 152,
        "rail_to_page_gap": 24,
        "compact_navigation_threshold": 760,
    }
    if not isinstance(settings, Mapping) or any(settings.get(key) != value for key, value in expected_settings.items()):
        errors.append("native Settings geometry and responsive architecture drifted")

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
        if plan.counts("full") != {"initial": 104, "restart": 2, "total": 106}:
            errors.append("corrected full capture plan must contain 106 frames")
        platform_matrix = plan.raw.get("native_platform_matrix")
        if capture.get("required_native_platform_profiles") != platform_matrix:
            errors.append("capture platform matrix differs from the execution plan")
        if matrix.get("required_native_platform_profiles") != platform_matrix:
            errors.append("visual platform matrix differs from the execution plan")

    expected_unrun = {"voiceover_review", "forced_colors_review"}
    if set(capture.get("deferred_unrun", [])) != expected_unrun:
        errors.append("only VoiceOver and forced colors may remain nonblocking")
    if set(matrix.get("deferred_unrun", [])) != expected_unrun:
        errors.append("visual nonblocking boundaries are incorrect")
    if capture.get("status") != "required-before-release":
        errors.append("fresh 1.8.7 evidence must remain required before release")

    _require_markers(errors, "settings.py", (
        'self.setWindowTitle("Home Screen Dashboard Settings")',
        "self.setMinimumSize(*SETTINGS_MINIMUM_SIZE)",
        "self._apply_initial_window_geometry(parent)",
        "clamp_window_geometry(saved, available, parent=parent_rect)",
        "self.settings_shell.setMaximumWidth(SETTINGS_SHELL_MAX_WIDTH)",
        "SETTINGS_PAGE_MAX_WIDTH = 940",
        "SETTINGS_COMPACT_BODY_WIDTH = 760",
        "self.compact_nav = QTabBar",
        "ScrollBarPolicy.ScrollBarAlwaysOff",
        "class SettingsFooter(QWidget)",
        'self.revert_button = QPushButton("Discard changes")',
        "class DisclosureHeader(QPushButton)",
        "class VerseLibraryModel(QAbstractListModel)",
        "class VerseLibraryDelegate(QStyledItemDelegate)",
        "DashboardCardPreview",
        "VerseCardPreview",
        "scope_differs_from_defaults",
        "Couldn’t save settings. Your changes are still available. Try again.",
        '"Discard unsaved changes?"',
        '("Keep editing", "primary"',
        '("Discard and close", "danger"',
        'SettingsCard("Study metrics", "", "Reset")',
        '"Advanced appearance"',
        '"Export verse edits"',
    ))
    _require_markers(errors, "settings_model.py", (
        "SETTINGS_DEFAULT_SIZE = (940, 680)",
        "SETTINGS_MINIMUM_SIZE = (720, 520)",
        "def clamp_window_geometry(",
        "def scope_differs_from_defaults(",
        '"calendar_display": (',
        '"calendar_range": (',
        '"local_data": (',
    ))
    _require_markers(errors, "controller.py", (
        "dialog = SettingsDialog(",
        "mw,",
        "dialog.exec()",
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
        "def showEvent",
        "raise_()",
        "activateWindow()",
        "AnkiWebView",
        "QWebEngine",
        "class VerseRowWidget",
        "Showing 100",
        "LOAD_MORE_BATCH",
        "Study calculations",
        "Revert changes",
        "simulated transactional write failure",
    ):
        if retired in settings_source:
            errors.append("retired Settings behavior remains: {}".format(retired))
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
