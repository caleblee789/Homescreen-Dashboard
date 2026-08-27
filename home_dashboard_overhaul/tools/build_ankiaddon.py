#!/usr/bin/env python3
"""Build and byte-verify a deterministic Home Screen Dashboard archive."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import re
import runpy
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PACKAGE_FILES = [
    "__init__.py",
    "analytics.py",
    "insights.py",
    "config.json",
    "config.md",
    "config_schema.py",
    "controller.py",
    "default_verses.json",
    "LICENSE.txt",
    "manifest.json",
    "migration.py",
    "models.py",
    "README.md",
    "CHANGELOG.md",
    "renderer.py",
    "settings.py",
    "settings_model.py",
    "themes.py",
    "THIRD_PARTY_NOTICES.md",
    "ui_primitives.py",
    "verse.py",
    "web/dashboard.css",
    "web/dashboard.js",
    "user_files/README.txt",
]
DEFERRED_SOURCE_FILES = frozenset({
    "calendar_manager_model.py",
    "calendar_models.py",
    "calendar_repository.py",
    "event_manager.py",
    "vendor-requirements.lock",
})
DEFERRED_SOURCE_PREFIXES = ("_vendor/",)
RELEASE_CONTRACT_FILES = (
    "qa/settings_window_contract_1_8_7.json",
    "qa/validate_settings_window_contract_1_8_7.py",
    "qa/calendar_surface_manifest_1_8_7.json",
    "qa/visual_regression_matrix_1_8_7.json",
    "qa/ui-surface-registry_1_8_7.json",
    "qa/capture_evidence_manifest_1_8_7.json",
    "qa/runtime_probe_release_1_8_7_manifest.json",
    "qa/runtime_probe_release_1_8_7.py",
    "qa/runtime_probe_release_1_8_4.py",
    "qa/assemble_release_evidence_1_8_7.py",
    "qa/capture_plan.json",
    "qa/capture_plan.py",
    "qa/prepare_capture_helper.py",
    "qa/runtime_probe_profile_entrypoint.py",
    "qa/runtime_probe_fullscreen_profile.py",
)
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
FIXED_TIMESTAMP = (2026, 8, 26, 0, 0, 0)


def _json(relative: str) -> dict:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("{} must contain a JSON object".format(relative))
    return value


def _quoted_verse_count(entries: list[object]) -> int:
    total = 0
    pattern = re.compile(r"<br>\s*-\s*.+?\s+\d+:(\d+)(?:[-–](\d+))?\s+\(NLT\)\s*$")
    for entry in entries:
        if not isinstance(entry, str):
            raise ValueError("default verse entries must be strings")
        match = pattern.search(entry)
        if match is None:
            raise ValueError("default verse entry has an uncountable NLT reference")
        first = int(match.group(1))
        last = int(match.group(2) or first)
        if last < first:
            raise ValueError("default verse entry has a reversed verse range")
        total += last - first + 1
    return total


def _channels(value: str) -> tuple[int, int, int]:
    raw = value.lstrip("#")
    if len(raw) != 6:
        raise ValueError("release colors must use six-digit hexadecimal notation")
    return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))


def _luminance(value: str) -> float:
    channels = [item / 255 for item in _channels(value)]
    linear = [
        item / 12.92 if item <= .04045 else ((item + .055) / 1.055) ** 2.4
        for item in channels
    ]
    return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]


def _contrast(left: str, right: str) -> float:
    high, low = sorted((_luminance(left), _luminance(right)), reverse=True)
    return (high + .05) / (low + .05)


def _lab(value: str) -> tuple[float, float, float]:
    red, green, blue = [item / 255 for item in _channels(value)]
    red, green, blue = [
        item / 12.92 if item <= .04045 else ((item + .055) / 1.055) ** 2.4
        for item in (red, green, blue)
    ]
    x = (red * .4124 + green * .3576 + blue * .1805) / .95047
    y = red * .2126 + green * .7152 + blue * .0722
    z = (red * .0193 + green * .1192 + blue * .9505) / 1.08883

    def pivot(item: float) -> float:
        return item ** (1 / 3) if item > .008856 else 7.787 * item + 16 / 116

    fx, fy, fz = pivot(x), pivot(y), pivot(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _perceptual_distance(left: str, right: str) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(_lab(left), _lab(right))))


def _validate_theme_contract(namespace: dict) -> None:
    expected_themes = {
        "Sapphire Glass": ("Sapphire", "Amethyst", "Glacier", "Sea Glass"),
        "Graphite": ("Slate", "Steel", "Plum", "Mint"),
        "Emerald": ("Emerald", "Jade", "Moss", "Lagoon"),
        "High Contrast": ("Cyan", "Gold", "Magenta", "Monochrome"),
    }
    dashboard_themes = namespace.get("PRESETS")
    heatmaps = namespace.get("HEATMAP_PRESETS")
    defaults = namespace.get("DEFAULT_HEATMAP_PRESETS")
    resolver = namespace.get("resolve_theme")
    if tuple(dashboard_themes or {}) != tuple(expected_themes):
        raise ValueError("release must expose exactly four ordered dashboard themes")
    if not callable(resolver) or not isinstance(heatmaps, dict) or not isinstance(defaults, dict):
        raise ValueError("theme resolver and authored heatmap presets are required")

    required_heatmap_roles = {
        *{"heat_complete_{}".format(level) for level in range(6)},
        *{"heat_complete_text_{}".format(level) for level in range(6)},
    }
    for theme_name, preset_names in expected_themes.items():
        if tuple(heatmaps.get(theme_name, {})) != preset_names:
            raise ValueError("{} has the wrong heatmap preset set/order".format(theme_name))
        if defaults.get(theme_name) != preset_names[0]:
            raise ValueError("{} must default to its first heatmap preset".format(theme_name))
        for preset_name in preset_names:
            palette = heatmaps[theme_name][preset_name]
            if set(palette) != {"light", "dark"}:
                raise ValueError("{} / {} must provide light and dark variants".format(theme_name, preset_name))
            for mode in ("light", "dark"):
                tokens = palette[mode]
                if set(tokens) != required_heatmap_roles:
                    raise ValueError("{} / {} / {} has an incomplete authored ladder".format(theme_name, preset_name, mode))
                fills = [tokens["heat_complete_{}".format(level)] for level in range(6)]
                distances = [_perceptual_distance(fills[0], fill) for fill in fills[1:]]
                if any(left >= right for left, right in zip(distances, distances[1:])):
                    raise ValueError("{} / {} / {} intensity is not monotonic".format(theme_name, preset_name, mode))
                if any(_perceptual_distance(left, right) < 1.5 for left, right in zip(fills, fills[1:])):
                    raise ValueError("{} / {} / {} has indistinguishable adjacent levels".format(theme_name, preset_name, mode))
                for level in range(6):
                    if _contrast(tokens["heat_complete_{}".format(level)], tokens["heat_complete_text_{}".format(level)]) < 4.5:
                        raise ValueError("{} / {} / {} level {} fails text contrast".format(theme_name, preset_name, mode, level))
                resolved = resolver(theme_name, mode, mode == "dark", preset_name)
                for key, value in tokens.items():
                    if resolved.get(key) != value:
                        raise ValueError("resolved heatmap tokens drift from the selected authored preset")

    required_semantic = {
        "ui_canvas", "ui_surface_1", "ui_surface_2", "ui_surface_3",
        "ui_border_subtle", "ui_border_default", "ui_border_strong",
        "ui_text_primary", "ui_text_secondary", "ui_text_tertiary", "ui_text_disabled",
        "ui_eyebrow", "ui_accent", "ui_accent_hover", "ui_accent_pressed",
        "ui_accent_soft", "ui_accent_border", "ui_on_accent", "ui_focus",
        "ui_shadow_card", "ui_shadow_overlay",
        *{"status_{}_{}".format(role, suffix) for role in (
            "new", "learning", "review", "buried", "success", "warning", "danger", "event"
        ) for suffix in ("fill", "text")},
        *{"heat_complete_{}".format(level) for level in range(6)},
        *{"heat_complete_text_{}".format(level) for level in range(6)},
        *{"heat_due_bg_{}".format(level) for level in range(1, 4)},
        *{"heat_due_mark_{}".format(level) for level in range(1, 4)},
        "progress_complete", "calendar_empty_bg",
        "calendar_outside_bg", "calendar_outside_text", "calendar_future_bg",
        "calendar_future_text", "calendar_footer_bg", "calendar_today_ring",
        "calendar_selected_ring", "calendar_ring_halo", "calendar_event_halo",
        "calendar_ring_halo", "ui_disabled_surface", "ui_disabled_border",
        "ui_control_hover", "ui_control_pressed",
    }
    semantic_reference = {mode: None for mode in ("light", "dark")}
    for theme_name in expected_themes:
        for mode in ("light", "dark"):
            resolved = resolver(theme_name, mode, mode == "dark", defaults[theme_name])
            missing = sorted(required_semantic.difference(resolved))
            if missing:
                raise ValueError("{} {} is missing semantic roles: {}".format(theme_name, mode, ", ".join(missing)))
            for level in range(1, 4):
                if _contrast(resolved["heat_due_bg_{}".format(level)], resolved["ui_text_primary"]) < 4.5:
                    raise ValueError("{} {} due level {} fails text contrast".format(theme_name, mode, level))
            for text_role in ("ui_text_primary", "ui_text_secondary", "ui_text_tertiary"):
                for surface_role in ("ui_surface_1", "ui_surface_2", "ui_surface_3"):
                    if _contrast(resolved[text_role], resolved[surface_role]) < 4.5:
                        raise ValueError("{} {} {} fails on {}".format(theme_name, mode, text_role, surface_role))
            for accent_role in ("ui_accent", "ui_accent_hover", "ui_accent_pressed"):
                if _contrast(resolved["ui_on_accent"], resolved[accent_role]) < 4.5:
                    raise ValueError("{} {} button text fails on {}".format(theme_name, mode, accent_role))
            # Strong boundaries are independently gated. Accent borders are a
            # secondary cue paired with contrast-safe accent text and a soft
            # state fill, so their standalone ratio remains advisory.
            for boundary, surface in (("ui_border_strong", "ui_surface_2"),):
                if _contrast(resolved[boundary], resolved[surface]) < 3:
                    raise ValueError("{} {} {} fails graphical contrast".format(theme_name, mode, boundary))
            semantic = {
                key: value for key, value in resolved.items() if key.startswith("status_")
                and not key.endswith("_soft")
            }
            if semantic_reference[mode] is None:
                semantic_reference[mode] = semantic
            elif semantic != semantic_reference[mode]:
                raise ValueError("{} {} recolors stable semantic roles".format(theme_name, mode))
            if theme_name == "High Contrast":
                for surface_role in ("ui_surface_1", "ui_surface_2", "ui_surface_3"):
                    if _contrast(resolved["ui_text_primary"], resolved[surface_role]) < 7:
                        raise ValueError("High Contrast {} primary text misses 7:1".format(mode))


def _validate_visual_matrix(matrix: dict) -> None:
    palette_axes = matrix.get("palette_ids_by_theme")
    modes = matrix.get("modes")
    entries = matrix.get("palette_cases")
    if not isinstance(palette_axes, dict) or not isinstance(modes, list):
        raise ValueError("visual regression matrix palette axes are missing")
    if not isinstance(entries, list):
        raise ValueError("visual regression matrix palette cases are missing")
    expected = {
        (theme, palette, mode)
        for theme, names in palette_axes.items()
        for palette, mode in itertools.product(names, modes)
    }
    actual = {
        (entry.get("theme"), entry.get("palette"), entry.get("mode"))
        for entry in entries if isinstance(entry, dict)
    }
    if not expected or len(entries) != len(expected) or actual != expected or len(actual) != len(entries):
        raise ValueError("visual regression matrix must cover every saved palette ID in both modes once")
    if len({entry.get("id") for entry in entries}) != len(entries):
        raise ValueError("palette visual regression IDs must be unique")
    if any(entry.get("view") != "month" for entry in entries):
        raise ValueError("palette cases must use one shared production Month tree")
    view_ids = [entry.get("id") for entry in matrix.get("view_cases", [])]
    if (
        not {"PROD-MONTH-STABLE", "PROD-YEAR-STABLE"} <= set(view_ids)
        or len(view_ids) != len(set(view_ids))
    ):
        raise ValueError("stable Month and Year cases are incomplete")
    settings_axes = matrix.get("settings_page_axes", {})
    try:
        settings_count = math.prod(len(settings_axes[key]) for key in (
            "page", "window_width", "application_font_percent"
        ))
    except (KeyError, TypeError):
        settings_count = 0
    if settings_count <= 0 or matrix.get("settings_page_case_count") != settings_count:
        raise ValueError("Settings visual matrix count must be derived from its page-width-font axes")
    statistics_cases = matrix.get("statistics_accuracy_cases", [])
    if (
        not isinstance(statistics_cases, list)
        or not statistics_cases
        or len({entry.get("id") for entry in statistics_cases}) != len(statistics_cases)
    ):
        raise ValueError("statistics visual matrix must define unique responsive production shells")


def validate_sources() -> dict:
    deferred = [
        name for name in PACKAGE_FILES
        if name in DEFERRED_SOURCE_FILES or name.startswith(DEFERRED_SOURCE_PREFIXES)
    ]
    if deferred:
        raise ValueError("deferred calendar sources cannot be packaged: {}".format(", ".join(deferred)))
    missing = [
        name for name in (*PACKAGE_FILES, *RELEASE_CONTRACT_FILES)
        if not (ROOT / name).is_file()
    ]
    if missing:
        raise FileNotFoundError("missing release source files: {}".format(", ".join(missing)))

    manifest = _json("manifest.json")
    config = _json("config.json")
    verse_data = _json("default_verses.json")
    surface_contract = _json("qa/calendar_surface_manifest_1_8_7.json")
    visual_matrix = _json("qa/visual_regression_matrix_1_8_7.json")
    capture_contract = _json("qa/capture_evidence_manifest_1_8_7.json")
    probe_contract = _json("qa/runtime_probe_release_1_8_7_manifest.json")
    surface_registry = _json("qa/ui-surface-registry_1_8_7.json")
    capture_plan_namespace = runpy.run_path(str(ROOT / "qa" / "capture_plan.py"))
    capture_plan = capture_plan_namespace["load_capture_plan"](
        ROOT / "qa" / "capture_plan.json"
    )
    capture_plan.validate_authorities(ROOT / "qa")
    settings_window_contract = _json("qa/settings_window_contract_1_8_7.json")
    if manifest.get("package") != "home_dashboard_overhaul" or manifest.get("name") != "Home Screen Dashboard":
        raise ValueError("unexpected add-on identity")
    version = manifest.get("human_version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version) or version != "1.8.7":
        raise ValueError("release artifact must use semantic version 1.8.7")
    if (manifest.get("min_point_version"), manifest.get("max_point_version")) != (260800, 260800):
        raise ValueError("release must be pinned to Anki 26.8")
    if config.get("schema_version") != 8:
        raise ValueError("config schema must be version 8")
    if config.get("layout", {}).get("order") != ["study_calendar", "summary_metrics", "bible_verse"]:
        raise ValueError("default hierarchy must be Calendar, metrics, Bible")
    config_text = json.dumps(config, sort_keys=True)
    for removed in (
        "selected_date_details", "selected_date_panel", "most_missed",
        "due_deck_breakdown", "show_eta", "show_estimate", '"buried"',
    ):
        if removed in config_text:
            raise ValueError("removed layout role remains in config: {}".format(removed))
    if config.get("study", {}).get("retention_target") != 80:
        raise ValueError("retention target must default to 80")
    if config.get("appearance", {}).get("text_scale") != 100:
        raise ValueError("dashboard text scale must default to 100")

    sources = {
        relative: (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "analytics.py", "config_schema.py", "controller.py", "insights.py",
            "models.py", "renderer.py", "settings.py", "themes.py",
            "ui_primitives.py", "web/dashboard.js", "web/dashboard.css",
        )
    }
    packaged_text = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8", errors="ignore")
        for relative in PACKAGE_FILES
        if (ROOT / relative).suffix.casefold() in {".py", ".json", ".md", ".txt", ".js", ".css"}
    )
    if "simulated transactional write failure" in packaged_text:
        raise ValueError("developer-facing save fixture wording must not ship")
    required = {
        "analytics.py": (
            "due_load_reference", "math.ceil(len(forecast_counts) * .90)",
            "queue IN (-2, -3)", "type IN (1, 3)",
            "due = original_due if original_deck else current_due",
            "deck_due_tree", "_limited_new_for_deck_node", "GROUP BY did",
            "def _retention_eligible_condition", "def _history_period_aggregate",
            "def _scheduler_day_index_expression", "REVLOG_RESCHEDULED = 5",
        ),
        "config_schema.py": (
            "SCHEMA_VERSION = 8", "presets_by_theme", "retention_target",
            '{"ascending", "descending", "name"}',
            '_int(appearance.get("opacity"), 96, 94, 100)',
            '_int(appearance.get("blur"), 12, 0, 16)',
            'visibility.pop("buried", None)',
            "summary_metrics", "bible_verse",
        ),
        "controller.py": (
            'page == "calendar_data"', 'page == "events"', "selected_event_id",
            "def _open_browser_target", "browser_will_search", "context.ids = ids",
            'command == "diagnostics"', 'self.request_settings_open("about_support")',
            "def _persist_settings_transaction", "_restore_optional_bytes",
            "from .settings import SettingsDialog", "dialog = SettingsDialog(",
            "dialog.exec()",
            "self._settings_request_token",
            "QTimer.singleShot(0, lambda: self._open_pending_settings(token))",
        ),
        "insights.py": (
            "ORDER BY again_count DESC, total_answers DESC, r.cid ASC",
            "most_missed_target", "def collect_day_insight",
        ),
        "renderer.py": (
            "hdo-calendar-footer", "hdo-date-state-chip", "hdo-event-meta",
            "hdo-edit-event-button", "hdo-summary-metrics-grid", "hdo-bible-card",
            "New cards studied", "Cards buried", "Time spent", "hdo-progress-fill",
            "retention_target", "day_insight_payload",
            "hdo-loading-region--calendar", "Dashboard could not load",
            "hdo-context-action--primary", "dashboard-scroll-surface",
            "No cards scheduled", "All clear", "100% complete", "_ProgressState",
            "today_session", "data-hdo-has-bible",
        ),
        "settings.py": (
            "class SettingsDialog(QDialog):", "class SettingsPromptPage(QWidget):",
            "super().__init__(parent)",
            'self.setWindowTitle("Home Screen Dashboard Settings")',
            "self.setMinimumSize(*SETTINGS_MINIMUM_SIZE)",
            "SETTINGS_GEOMETRY_KEY", "clamp_window_geometry(",
            "self._content_stack.setCurrentWidget(prompt)",
            "def reject(self) -> None:", "def closeEvent(self, event: Any) -> None:",
            "action.triggered.connect(controller.open_settings)",
            "self.settings_shell.setMaximumWidth(SETTINGS_SHELL_MAX_WIDTH)", "self.sidebar_panel.setFixedWidth(SETTINGS_SIDEBAR_WIDTH)",
            "self.compact_nav = QTabBar", "SETTINGS_COMPACT_BODY_WIDTH = 820",
            "SETTINGS_PAGE_MAX_WIDTH = 980", "SETTINGS_HEADER_HEIGHT = 72",
            "SETTINGS_FOOTER_MIN_HEIGHT = 60", "ScrollBarAlwaysOff",
            "host = grid.parentWidget()", "widget.setParent(host)",
            "widget.show()", "if not widget.isHidden():",
            "self.heatmap_preset = QComboBox()", "def _refresh_heatmap_preset_options",
            "def _connect_change_signals(self) -> None:",
            "def _settings_changed(self, *_args: object) -> None:",
            'SettingsCard("Study metrics", "", "Reset")', '"Calendar display",',
            'SettingsCard("Calendar range", "", "Reset")', "class DisclosureHeader",
            "class EventRowWidget", "class VerseLibraryModel", "class VerseLibraryDelegate",
            "def _attach_event_menu", 'self.revert_button = QPushButton("Discard changes")',
            "class SettingsFooter", 'self.error_label.setObjectName("InlineSaveError")',
            "Save failed. Your changes are still available.",
            "scope_differs_from_defaults", 'SettingsCard("Version and support")',
            'SettingsCard("Privacy and legal")',
        ),
        "web/dashboard.js": (
            "function buildCalendarTooltipRows", "function getSelectedDateCapabilities",
            "function getNextUpcomingEvent", "function getContextEvent", "function getDueLoadScale",
            "function getDueLoadLevel", "function applyDocumentTheme", 'relation === "past" ? 0',
            'calendar.addEventListener("pointerover"', 'send("open_most_missed"',
            "function mountLoadingState", "Still loading your study data...",
            "progress.fill_percent", "today.cards_buried", "today.time_spent",
            'send("diagnostics", {})', "document.scrollingElement",
            "function visibleBottomActionContainer(root)",
            "var clearance = footerHeight + 24", "new global.ResizeObserver(update)",
            'relationship: "No event on this date"', 'editEvent.title = "Add event"',
            "setYearScrollPosition", "state.yearScrollLeft = yearScrollFrame.scrollLeft",
            "root.dataset.hdoLastUpdatedAt",
        ),
        "web/dashboard.css": (
            "hdo-calendar-footer", "hdo-calendar-card-action", "hdo-context-action--primary",
            "width: min(1120px, calc(100% - 40px))", "margin: 24px auto 0",
            "padding: 0 0 var(--hdo-bottom-clearance)", "pointer-events: none",
            "min-width: min(190px", "max-width: min(220px",
            "@container hdo-dashboard (min-width: 420px)",
            "@container hdo-dashboard (min-width: 1040px)",
            "@container hdo-calendar (max-width: 419px)",
            "repeat(6, clamp(48px, 4.8cqi, 54px))",
            "28px repeat(var(--hdo-year-weeks, 53), minmax(0, 1fr))",
            "18px repeat(var(--hdo-year-weeks, 53), minmax(0, 1fr))",
            "min-width: 580px",
            "min-block-size: 14px", "var(--heat-due-mark-3)", "var(--progress-complete)",
            "hdo-event-marker", "hdo-loading-layout", "backdrop-filter",
            "hdo-year-weekday-label", "background: transparent",
        ),
    }
    for relative, markers in required.items():
        absent = [marker for marker in markers if marker not in sources[relative]]
        if absent:
            raise ValueError("{} is missing corrected release contracts: {}".format(relative, ", ".join(absent)))

    dialog_source = sources["settings.py"].split(
        "class SettingsDialog(QDialog):", 1
    )[1].split("def _object_name", 1)[0]
    grid_mount_source = dialog_source.split(
        "    def _place_grid_widgets(", 1
    )[1].split("    def _reflow_compact_grids", 1)[0]
    if not (
        grid_mount_source.index("widget.setParent(host)")
        < grid_mount_source.index("widget.show()")
        < grid_mount_source.index("if not widget.isHidden():")
    ):
        raise ValueError(
            "Settings grid fields must be parented before show and visibility filtering"
        )
    apply_theme_source = dialog_source.split("    def _apply_theme(", 1)[1].split(
        "    def _update_forecast_range_visibility", 1
    )[0]
    if "self._refresh_heatmap_preset_options()" in apply_theme_source:
        raise ValueError("generic Settings synchronization must not rebuild heatmap options")
    for forbidden in (
        "clamp_window_size", "self.screen()", "self.move(", "setWindowModality", "setModal(",
        "def showEvent", "AnkiWebView", "QWebEngine", "raise_()",
        "setWindowFlags", "activateWindow()", "setFocus(",
        "setFocusProxy(", "installEventFilter(self)", "super().__init__(parent,",
        "Qt.WindowType.Window", "Qt.WindowType.CustomizeWindowHint",
    ):
        if forbidden in dialog_source:
            raise ValueError(
                "Settings dialog retains custom lifecycle marker: {}".format(forbidden)
            )

    for forbidden in (
        "def _clamped_settings_origin(", "def _place_settings_dialog(",
        "def _report_settings_placement_failure(", "dialog.move(",
        "parent.screen()", "screen.availableGeometry()",
    ):
        if forbidden in sources["controller.py"]:
            raise ValueError(
                "retired pre-exec Settings placement remains: {}".format(forbidden)
            )

    save_tail = sources["settings.py"].split("    def _save(self) -> None:", 1)[1].split(
        "def _object_name", 1
    )[0]
    if "message = QMessageBox(self)" in save_tail or "message.exec()" in save_tail:
        raise ValueError("primary Settings prompts must remain embedded children")

    for retired in (
        "Qt.WindowType.Tool", "self.winId()", "setTransientParent",
        "_attach_transient_parent", "Qt.WindowModality.NonModal", "objc_msgSend",
        "_attach_macos_settings_window", "_detach_macos_settings_window",
        "self.move(",
    ):
        if retired in sources["settings.py"]:
            raise ValueError(
                "retired macOS Settings panel behavior remains: {}".format(retired)
            )

    for retired in (
        "SettingsWorkspace", "_settings_workspace", "_settings_menu_waiting_for_hide",
        "request_settings_open_from_menu", "settings_menu_about_to_hide",
        "QTimer.singleShot(50", "dialog.open()", "dialog.show()",
        "dialog.finished.connect(", "dialog.raise_()", "dialog.activateWindow()",
    ):
        if retired in sources["controller.py"] + sources["settings.py"]:
            raise ValueError("retired Settings lifecycle remains: {}".format(retired))
    for retired in (
        "AnkiWebView", "aqt.webview", "stdHtml", "focusChanged",
        "PreviewDock", "_schedule_preview", "_render_preview", "_open_full_preview",
        "DashboardCardPreview", "VerseCardPreview", "HeatmapPresetCard",
        "heatmap_preset_cards", "preset_swatch",
    ):
        if retired in sources["settings.py"]:
            raise ValueError("retired Settings preview behavior remains: {}".format(retired))

    dashboard_surface_source = sources["renderer.py"] + sources["web/dashboard.js"] + sources["web/dashboard.css"]
    for forbidden in (
        "Outside due forecast", "Outside study history", "No events",
        "Select a date for details", "hdo-selected-date-details",
        "hdo-most-missed-list", "hdo-due-deck-breakdown", "Expand preview",
        "open_insight_card", "Using sample data", "getDueOverlayHeight", "hdo-due-hatch",
        "SettingsLayoutMetrics", "settings_content_mode", "section_selector",
        "section_tabs", "compact_toolbar", 'setText("Discard changes"',
    ):
        if forbidden in dashboard_surface_source:
            raise ValueError("removed dashboard surface/copy remains: {}".format(forbidden))
    if re.search(r"#[0-9a-fA-F]{3,8}\b", sources["web/dashboard.css"]):
        raise ValueError("components must consume tokens rather than hard-coded hex colors")
    if "InsightItem" in sources["models.py"] or "card.question" in sources["insights.py"]:
        raise ValueError("dashboard card-preview models/loading must remain removed")

    _validate_theme_contract(runpy.run_path(str(ROOT / "themes.py")))
    _validate_visual_matrix(visual_matrix)
    criteria = surface_contract.get("acceptance_criteria")
    if (
        not isinstance(criteria, list)
        or len(criteria) < 20
        or len({item.get("id") for item in criteria}) != len(criteria)
        or any(not item.get("tags") or not str(item.get("requirement", "")).strip() for item in criteria)
    ):
        raise ValueError("corrected surface contract must encode unique tagged acceptance criteria")
    if any(contract.get("release") != version for contract in (
        surface_contract, visual_matrix, capture_contract, probe_contract,
        surface_registry,
    )):
        raise ValueError("1.8.7 release authorities use different versions")
    if surface_registry.get("surfaces") != surface_contract.get("canonical_surfaces"):
        raise ValueError("surface registry differs from the canonical surface authority")
    if capture_plan.release != version:
        raise ValueError("capture plan must match the manifest version")
    if (
        probe_contract.get("capture_plan") != "capture_plan.json"
        or probe_contract.get("capture_profile_authority") != "capture_plan.json#profiles"
        or probe_contract.get("capture_count_authority")
        != "capture_plan.json#profiles[id=full]"
        or probe_contract.get("helper_builder") != "prepare_capture_helper.py"
        or probe_contract.get("base_probe") != "runtime_probe_release_1_8_4.py"
        or probe_contract.get("release_probe") != "runtime_probe_release_1_8_7.py"
        or probe_contract.get("required_platform_matrix")
        != "capture_plan.json#native_platform_matrix"
    ):
        raise ValueError("runtime probe metadata does not delegate profiles and counts to the capture plan")
    if settings_window_contract.get("release") != version:
        raise ValueError("focused Settings contract must match the manifest version")
    if (
        settings_window_contract.get("reference_addons") != ["Progress Bar", "PronounceIt"]
        or settings_window_contract.get("minimum_size") != [920, 640]
        or settings_window_contract.get("default_size") != [1080, 760]
        or settings_window_contract.get("screen_margins")
        != {"normal": 48, "small_screen_fallback": 24}
        or settings_window_contract.get("minimum_saved_visible_ratio") != .8
        or settings_window_contract.get("native_window") is not True
        or settings_window_contract.get("logical_coordinates") is not True
        or settings_window_contract.get("movable") is not True
        or settings_window_contract.get("resizable") is not True
        or settings_window_contract.get("default_window_flags") is not True
        or settings_window_contract.get("initial_placement")
        != "restore a valid logical v3 QRect on its connected screen or center on the active parent screen before first visibility"
        or settings_window_contract.get("pre_exec_geometry") is not True
        or settings_window_contract.get("reposition_after_open") is not False
        or settings_window_contract.get("saved_geometry")
        != "versioned UI-only QSettings normal logical QRect plus screen identity; reject undersized offscreen disconnected and compact records"
        or settings_window_contract.get("geometry_key")
        != "home_dashboard_overhaul/settings_dialog_geometry/v3"
        or settings_window_contract.get("geometry_screen_key")
        != "home_dashboard_overhaul/settings_dialog_geometry/v3_screen"
        or settings_window_contract.get("active_screen_order")
        != ["parent window handle", "screen containing parent center", "primary screen"]
        or settings_window_contract.get("shell_maximum_width") != 1240
        or settings_window_contract.get("page_maximum_width") != 980
        or settings_window_contract.get("rail_width") != 184
        or settings_window_contract.get("header_height") != 72
        or settings_window_contract.get("footer_height") != 60
        or settings_window_contract.get("rendered_previews")
        != "none; dashboard verse palette swatch and heatmap preview surfaces are absent"
        or settings_window_contract.get("settings_profile_acceptance_gate")
        != "a structured exact-package macOS report must pass both full-screen opening paths with no desktop or Space switch; the 41 PNGs cannot satisfy or waive this gate"
        or settings_window_contract.get("programmatic_lifecycle_focus") is not False
        or settings_window_contract.get("retained_dialog_object") is not False
    ):
        raise ValueError("focused Settings contract does not require native dialog parity")
    if capture_contract.get("runtime_smoke_requirements") != {
        "active_head_deck": "A",
        "raw_new_cards_per_head_minimum": 40,
        "remaining_limits": {"A": 3, "B": 7},
        "expected_unexcluded_new_remaining": 10,
        "expected_excluding_b_new_remaining": 3,
        "restart_expected_new_remaining": 10,
    }:
        raise ValueError("multi-deck new-limit runtime smoke contract is incomplete")
    full_counts = capture_plan.counts("full")
    wide_counts = capture_plan.counts("wide-100")
    if not (0 < wide_counts["initial"] <= full_counts["initial"] and wide_counts["restart"] <= full_counts["restart"]):
        raise ValueError("wide 100 percent profile is not a valid subset of the full capture plan")
    if full_counts != {"initial": 92, "restart": 2, "total": 94}:
        raise ValueError("corrected 1.8.7 full capture count must be 94")
    settings_counts = capture_plan.counts("settings")
    if settings_counts != {"initial": 40, "restart": 1, "total": 41}:
        raise ValueError("minimal 1.8.7 Settings capture count must be exactly 41")
    if 2 + len(capture_plan.detail_groups("settings")) > 11:
        raise ValueError("minimal 1.8.7 Settings evidence exceeds 11 sheets")
    structured_gate_id = "macos-fullscreen-no-space-switch-menu-and-dashboard-gear"
    if capture_plan.profile("settings").get("required_structured_manual_results") != [
        structured_gate_id
    ]:
        raise ValueError("minimal Settings profile lacks its full-screen no-switch gate")
    if capture_contract.get("settings_profile_structured_manual_gate") != {
        "id": structured_gate_id,
        "required_for_acceptance": True,
        "adds_png_frames": False,
        "opening_paths": ["menu", "dashboard-gear"],
        "required_result": "both paths remain on the native Anki full-screen Space with no desktop switch, including hard-restart recheck",
    }:
        raise ValueError("Settings full-screen structured acceptance contract drifted")
    if (
        "macos-fullscreen-menu-and-dashboard-gear-open-without-desktop-space-switch"
        not in visual_matrix.get("settings_quality_assertions", [])
    ):
        raise ValueError("visual matrix does not prevent the desktop/Space-switch regression")
    if capture_contract.get("required_native_platform_profiles") != capture_plan.raw.get("native_platform_matrix"):
        raise ValueError("release-blocking native platform matrix drifted")

    verses = verse_data.get("quote")
    if (
        not isinstance(verses, list) or len(verses) != 483
        or _quoted_verse_count(verses) != 500
        or verse_data.get("scripture quoted verse count") != 500
    ):
        raise ValueError("bundled NLT library must remain at 483 entries / 500 quoted verses")
    notice = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    scripture_notice = str(verse_data.get("scripture copyright", ""))
    if not scripture_notice or re.sub(r"\s+", " ", scripture_notice).strip() not in re.sub(r"\s+", " ", notice).strip():
        raise ValueError("the complete bundled Scripture notice must ship")
    return manifest


def _zip_info(relative: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(relative, FIXED_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.flag_bits |= 0x800
    return info


def verify_archive(artifact: Path) -> None:
    with zipfile.ZipFile(artifact) as archive:
        names = archive.namelist()
        if names != PACKAGE_FILES:
            raise ValueError("archive contents do not match the package allowlist")
        if archive.testzip() is not None:
            raise ValueError("archive contains corrupt data")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "__pycache__" in path.parts:
                raise ValueError("unsafe archive path: {}".format(name))
            if archive.read(name) != (ROOT / name).read_bytes():
                raise ValueError("archive differs from source: {}".format(name))
            if archive.getinfo(name).date_time != FIXED_TIMESTAMP:
                raise ValueError("archive timestamp is not deterministic")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_artifact() -> tuple[Path, Path, str]:
    manifest = validate_sources()
    artifact = DIST / "home-dashboard-overhaul-{}.ankiaddon".format(manifest["human_version"])
    temporary = Path(str(artifact) + ".tmp")
    checksum_file = Path(str(artifact) + ".sha256")
    DIST.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for relative in PACKAGE_FILES:
                archive.writestr(_zip_info(relative), (ROOT / relative).read_bytes())
        verify_archive(temporary)
        temporary.replace(artifact)
        verify_archive(artifact)
        digest = sha256(artifact)
        checksum_file.write_text("{}  {}\n".format(digest, artifact.name), encoding="ascii")
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    return artifact, checksum_file, digest


def main() -> None:
    artifact, checksum_file, digest = build_artifact()
    print(artifact)
    print("sha256 {}".format(digest))
    print(checksum_file)


if __name__ == "__main__":
    main()
