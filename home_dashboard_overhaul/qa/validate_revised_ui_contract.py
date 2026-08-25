#!/usr/bin/env python3
"""Validate the machine-readable Home Screen Dashboard 1.8.6 UI contract."""

from __future__ import annotations

from itertools import product
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, List, Mapping


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
RELEASE = "1.8.6"


def _read(name: str) -> dict[str, Any]:
    value = json.loads((ROOT / "qa" / name).read_text(encoding="utf-8"))
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
    if len(expected) != 32 or actual != expected or len(ids) != len(set(ids)):
        errors.append("palette matrix must cover all 16 saved IDs in light and dark exactly once")
    if any(case.get("view") != "month" for case in cases if isinstance(case, Mapping)):
        errors.append("palette comparison cases must use the same production Month tree")
    view_ids = [case.get("id") for case in matrix.get("view_cases", [])]
    if view_ids != ["PROD-MONTH-STABLE", "PROD-YEAR-STABLE"]:
        errors.append("stable Month and Year comparison cases are incomplete")
    settings_axes = matrix.get("settings_page_axes", {})
    try:
        settings_count = (
            len(settings_axes["page"])
            * len(settings_axes["window_width"])
            * len(settings_axes["application_font_percent"])
        )
    except (KeyError, TypeError):
        settings_count = 0
    if settings_count != 24 or matrix.get("settings_page_case_count") != 24:
        errors.append("Settings page matrix must derive 24 page-width-font cases")
    statistics = matrix.get("statistics_accuracy_cases", [])
    if {
        case.get("id") for case in statistics if isinstance(case, Mapping)
    } != {
        "PROD-STATS-WIDE-MONTH",
        "PROD-STATS-WIDE-YEAR",
        "PROD-STATS-INTERMEDIATE",
        "PROD-STATS-NARROW",
        "SET-STATS-PREVIEW",
    }:
        errors.append("statistics matrix must cover Month, Year, responsive shells, and Settings preview")


def _validate_capture_plan(errors: List[str], capture: Mapping[str, Any]) -> None:
    families = capture.get("capture_families", [])
    if not isinstance(families, list):
        errors.append("capture families are missing")
        return
    counts = {
        family.get("id"): family.get("count")
        for family in families if isinstance(family, Mapping)
    }
    if counts != {
        "production-palettes": 32,
        "production-core": 16,
        "settings-pages": 24,
        "settings-contract": 23,
        "statistics-accuracy": 5,
        "restart": 2,
    }:
        errors.append("capture families do not match the implemented 1.8.6 contract")
    total = sum(value for value in counts.values() if isinstance(value, int))
    derived = capture.get("derived_native_frame_count", {})
    if total != 102 or derived.get("total") != total or derived.get("initial") != 100 or derived.get("restart") != 2:
        errors.append("native evidence count must derive to 100 initial plus 2 restart frames")
    explicit = [
        capture_id
        for family in families if isinstance(family, Mapping)
        for capture_id in family.get("capture_ids", [])
    ]
    if len(explicit) != len(set(explicit)):
        errors.append("explicit capture IDs are not unique")
    restart = next(
        (family for family in families if family.get("id") == "restart"),
        {},
    )
    if restart.get("capture_ids") != ["PROD-RESTART-PERSISTENCE", "SET-RESTART-PERSISTENCE"]:
        errors.append("production and Settings restart frames are required")
    if "no-waiver" not in restart.get("requirements", []):
        errors.append("restart evidence cannot be waived")
    references = capture.get("reference_inputs", [])
    if not references or any(
        reference.get("may_count_as_acceptance_evidence") is not False
        or reference.get("must_not_be_overwritten") is not True
        for reference in references if isinstance(reference, Mapping)
    ):
        errors.append("historical and user-owned references must stay immutable and non-acceptance")
    user_owned = next(
        (item for item in references if item.get("id") == "USER-OWNED-SETTINGS-CONTACT-SHEETS-1.8.3"),
        {},
    )
    if user_owned.get("must_not_receive_new_staging") is not True:
        errors.append("the user-owned 1.8.3 contact-sheet directory lacks the no-stage guard")


def validate(root: Path = ROOT) -> List[str]:
    del root
    errors: List[str] = []
    manifest = _read("calendar_surface_manifest_1_8_6.json")
    matrix = _read("visual_regression_matrix_1_8_6.json")
    registry = _read("ui-surface-registry_1_8_6.json")
    capture = _read("capture_evidence_manifest_1_8_6.json")
    addon_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    if addon_manifest.get("human_version") != RELEASE:
        errors.append("add-on manifest must target release 1.8.6")
    if config.get("schema_version") != 8:
        errors.append("configuration schema must remain 8")
    if manifest.get("release") != RELEASE or manifest.get("schema_version") != 8:
        errors.append("surface authority must describe release 1.8.6 / schema 8")
    if manifest.get("contract") != "canonical-settings-and-production-dashboard-final-ui-2026-08-24":
        errors.append("surface authority has the wrong governing contract")
    if matrix.get("release") != RELEASE or capture.get("release") != RELEASE or registry.get("release") != RELEASE:
        errors.append("all current QA contracts must match release 1.8.6")

    surfaces = manifest.get("canonical_surfaces", [])
    ids = [surface.get("id") for surface in surfaces if isinstance(surface, Mapping)]
    if len(ids) < 30 or len(ids) != len(set(ids)):
        errors.append("canonical surface IDs must be unique and complete")
    if registry.get("surfaces") != surfaces or registry.get("exact_once") is not True:
        errors.append("surface registry must exactly mirror the governing authority")

    criteria = manifest.get("acceptance_criteria", [])
    criteria_ids = [item.get("id") for item in criteria if isinstance(item, Mapping)]
    if len(criteria_ids) < 20 or len(criteria_ids) != len(set(criteria_ids)):
        errors.append("acceptance criteria must contain unique implementation-owned IDs")
    if any(not item.get("tags") or not str(item.get("requirement", "")).strip() for item in criteria):
        errors.append("every acceptance criterion needs tags and a requirement")

    _validate_palette_matrix(errors, matrix)
    _validate_capture_plan(errors, capture)

    _require_markers(errors, "settings.py", (
        "self.setFixedSize(1200, 800)",
        "self.setFixedSize(width, height)",
        "super().__init__(mw)",
        "self.settings_shell.setMaximumWidth(1240)",
        "self.nav.setFixedWidth(152)",
        'self.preview_wrap.setObjectName("PreviewDock")',
        "def _update_preview_canvas_height(self) -> None:",
        "value = max(0, target_y - 2)",
        '[("Section", "context"), ("Full dashboard", "full")]',
        '[("Fit", "fit"), ("100%", "actual")]',
        'self.revert_button = QPushButton("Revert changes")',
        'self.save_error.setObjectName("InlineSaveError")',
        "class EventRowWidget(QWidget)",
        "class VerseRowWidget(QWidget)",
        'SettingsCard("Calendar display")',
        'SettingsCard("Calendar range")',
        'SettingsCard("Data and reset"',
        'SettingsCard("Backup and recovery")',
    ))
    _require_markers(errors, "settings_model.py", (
        "def clamp_window_size(",
        '"calendar": ("dashboard", "calendar")',
        "item.name.casefold(), item.date, item.event_id",
    ))
    _require_markers(errors, "config_schema.py", (
        "SCHEMA_VERSION = 8",
        '{"ascending", "descending", "name"}',
        "presets_by_theme",
    ))
    _require_markers(errors, "controller.py", (
        "dialog.setWindowModality(SETTINGS_WINDOW_MODALITY)",
        "dialog.finished.connect(",
        "dialog.open()",
        "def _settings_dialog_finished",
        "if self.settings_dialog is dialog:",
        "def _persist_settings_transaction(",
        "previous_config = deepcopy(",
        "_restore_optional_bytes(ROTATION_STATE_PATH, previous_rotation)",
        "rotation_persisted=prepared_rotation is not _ROTATION_UNCHANGED",
    ))
    _require_markers(errors, "verse.py", (
        "def prepare_quote(",
        "def persist_prepared(",
        "os.replace(str(temporary), str(self.state_path))",
    ))
    _require_markers(errors, "renderer.py", (
        "start + timedelta(days=41)",
        "show_due_forecast",
        'config.get("visibility", {}).get("events", True)',
        "--hdo-verse-size",
        "100 - int(stats.retention.percent)",
    ))
    _require_markers(errors, "web/dashboard.css", (
        "width: min(1120px, calc(100% - 40px))",
        "margin: 24px auto 0",
        "repeat(6, clamp(48px, 4.8cqi, 54px))",
        "28px repeat(var(--hdo-year-weeks, 53), minmax(0, 1fr))",
        "18px repeat(var(--hdo-year-weeks, 53), minmax(0, 1fr))",
        "min-width: 580px",
        "outline: 2px solid var(--calendar-today-ring)",
        "var(--status-event-fill)",
    ))
    _require_markers(errors, "web/dashboard.js", (
        "function visibleBottomActionContainer(root)",
        "function applyDocumentScrollClearance(root)",
        "var clearance = footerHeight + 24",
        "new global.ResizeObserver(update)",
        "rows: 6",
        "100 - Number(recent.retention.percent)",
    ))
    _require_markers(errors, "analytics.py", (
        "def _scheduler_day_index_expression(",
        "def _history_period_aggregate(",
        "def _retention_eligible_condition(",
        "REVLOG_RESCHEDULED = 5",
        "due = original_due if original_deck else current_due",
        "queue IN (-2, -3)",
    ))
    _require_markers(errors, "models.py", (
        "queue total must equal new + learning + review",
    ))

    settings_source = _source("settings.py")
    _require_markers(errors, "settings.py", (
        "SETTINGS_WINDOW_MODALITY = Qt.WindowModality.WindowModal",
        "self.preview: Optional[AnkiWebView] = None",
        "QTimer.singleShot(0, self._initialize_preview)",
        "def _initialize_preview(self) -> None:",
    ))
    for retired in (
        "HomeScreenDashboard/settingsWindowSize", "def _settle_window_to_screen",
        "Qt.WindowType.Tool", "self.winId()", "setTransientParent",
        "_attach_transient_parent", "Qt.WindowModality.NonModal", "objc_msgSend",
        "_attach_macos_settings_window", "_detach_macos_settings_window",
        "self.move(",
    ):
        if retired in settings_source:
            errors.append("retired Settings window behavior remains: {}".format(retired))
    controller_source = _source("controller.py")
    for retired in (
        "self.settings_dialog.exec()", "self.settings_dialog.show()",
        "dialog.exec()", "dialog.show()",
        "self.settings_dialog.raise_()", "self.settings_dialog.activateWindow()",
    ):
        if retired in controller_source:
            errors.append("retired top-level Settings lifecycle remains: {}".format(retired))
    for retired in (
        "SettingsLayoutMetrics", "settings_content_mode", "section_selector",
        "section_tabs", "compact_toolbar", 'setText("Discard changes"',
    ):
        if retired in settings_source:
            errors.append("retired Settings composition remains: {}".format(retired))
    dashboard_source = "\n".join(
        _source(path) for path in ("renderer.py", "web/dashboard.js", "web/dashboard.css")
    ).casefold()
    for retired in (
        "hdo-selected-date-panel", "hdo-date-details", "hdo-due-deck",
        "hdo-insight-preview", "card-answer-preview", "expand preview",
    ):
        if retired in dashboard_source:
            errors.append("retired dashboard surface remains: {}".format(retired))

    for version, dated in (
        ("1.8.0", "2026-08-23"), ("1.8.1", "2026-08-23"),
        ("1.8.2", "2026-08-23"), ("1.8.3", "2026-08-23"),
        ("1.8.4", "2026-08-24"), ("1.8.5", "2026-08-24"),
    ):
        if not (ROOT / "qa" / "release-evidence-{}-{}".format(version, dated)).is_dir():
            errors.append("retained {} release evidence is missing".format(version))

    protected = "home_dashboard_overhaul/qa/settings-menu-contact-sheets-1.8.3-2026-08-23-2222"
    if (REPO / ".git").exists():
        try:
            protected_changes = subprocess.run(
                ["git", "status", "--short", "--untracked-files=no", "--", protected],
                cwd=REPO,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            errors.append("could not verify protected contact-sheet immutability: {}".format(exc))
        else:
            if protected_changes:
                errors.append("frozen 1.8.3 contact sheets contain tracked or staged changes")

    expected_unrun = {
        "voiceover_review", "windows_validation", "linux_validation",
        "forced_colors_review", "device_pixel_ratio_1", "os_display_scaling",
    }
    if set(capture.get("deferred_unrun", [])) != expected_unrun:
        errors.append("capture acceptance boundaries are incomplete")
    if set(matrix.get("deferred_unrun", [])) != expected_unrun:
        errors.append("visual acceptance boundaries are incomplete")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print("ERROR: {}".format(error))
        return 1
    print("Canonical UI contract: PASS (1.8.6 schema 8, 102 derived native frames, no restart waiver)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
