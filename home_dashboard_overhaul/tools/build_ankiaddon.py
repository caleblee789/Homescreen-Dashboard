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
    "qa/calendar_surface_manifest_1_8_4.json",
    "qa/visual_regression_matrix_1_8_4.json",
    "qa/ui-surface-registry_1_8_4.json",
    "qa/capture_evidence_manifest_1_8_4.json",
    "qa/runtime_probe_release_1_8_4_manifest.json",
)
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
FIXED_TIMESTAMP = (2026, 8, 24, 0, 0, 0)


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
    axes = {
        "theme": ("Sapphire Glass", "Graphite", "Emerald", "High Contrast"),
        "mode": ("light", "dark"),
        "view": ("month", "year"),
    }
    entries = matrix.get("cases")
    if not isinstance(entries, list) or len(entries) != 16:
        raise ValueError("visual regression matrix must contain exactly 16 primary cases")
    expected = set(itertools.product(*axes.values()))
    actual = {
        (entry.get("theme"), entry.get("mode"), entry.get("view"))
        for entry in entries if isinstance(entry, dict)
    }
    if actual != expected or len(actual) != len(entries):
        raise ValueError("visual regression matrix must cover the exact Cartesian product once")
    if len({entry.get("id") for entry in entries}) != 16:
        raise ValueError("visual regression IDs must be unique")
    if any(entry.get("text_scale") != 100 for entry in entries):
        raise ValueError("visual regression matrix must be calibrated only at 100 percent")
    if matrix.get("deferred_scales_percent") != [125, 150]:
        raise ValueError("125 and 150 percent visual calibration must stay deferred")


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
    surface_contract = _json("qa/calendar_surface_manifest_1_8_4.json")
    visual_matrix = _json("qa/visual_regression_matrix_1_8_4.json")
    capture_contract = _json("qa/capture_evidence_manifest_1_8_4.json")
    if manifest.get("package") != "home_dashboard_overhaul" or manifest.get("name") != "Home Screen Dashboard":
        raise ValueError("unexpected add-on identity")
    version = manifest.get("human_version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version) or version != "1.8.4":
        raise ValueError("release artifact must use semantic version 1.8.4")
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
    required = {
        "analytics.py": (
            "due_load_reference", "math.ceil(len(forecast_counts) * .90)",
            "queue IN (-2, -3)", "type IN (1, 3)", "due < 1000000000",
            "deck_due_tree", "_limited_new_for_deck_node", "GROUP BY did",
        ),
        "config_schema.py": (
            "SCHEMA_VERSION = 8", "presets_by_theme", "retention_target",
            '_int(appearance.get("opacity"), 96, 94, 100)',
            '_int(appearance.get("blur"), 12, 0, 16)',
            'visibility.pop("buried", None)',
            "summary_metrics", "bible_verse",
        ),
        "controller.py": (
            'page == "calendar_data"', 'page == "events"', "selected_event_id",
            "def _open_browser_target", "browser_will_search", "context.ids = ids",
            'command == "diagnostics"', 'self.open_settings("about_support")',
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
            "Dashboard preview", "Open full preview", 'QLabel("Sample data")',
            '[("Current section", "context"), ("Full dashboard", "full")]',
            '[("Fit", "fit"), ("Actual size", "actual")]',
            'SettingsCard(\n            "Content & study metrics"',
            'SettingsCard(\n            "Calendar & data"',
            "class SelectChevron", "class SettingsSwitch", "def _attach_event_menu",
            "SettingsCard", "HEATMAP_PRESETS", "_heatmap_preset_preferences",
            "Qt.FocusPolicy.NoFocus",
        ),
        "web/dashboard.js": (
            "function buildCalendarTooltipRows", "function getSelectedDateCapabilities",
            "function getNextUpcomingEvent", "function getContextEvent", "function getDueLoadScale",
            "function getDueLoadLevel", "function applyDocumentTheme", 'relation === "past" ? 0',
            'calendar.addEventListener("pointerover"', 'send("open_most_missed"',
            "function mountLoadingState", "Still loading your study data...",
            "progress.fill_percent", "today.cards_buried", "today.time_spent",
            'send("diagnostics", {})', "document.scrollingElement",
            'relationship: "No event on this date"', 'editEvent.title = "Add event"',
            "setYearScrollPosition", "state.yearScrollLeft = yearScrollFrame.scrollLeft",
            "root.dataset.hdoLastUpdatedAt",
        ),
        "web/dashboard.css": (
            "hdo-calendar-footer", "hdo-calendar-card-action", "hdo-context-action--primary",
            "width: min(1240px, calc(100% - 32px))", "margin: 22px auto 0",
            "padding: 0 0 var(--hdo-bottom-clearance)", "pointer-events: none",
            "min-width: min(190px", "max-width: min(220px",
            "@container hdo-dashboard (min-width: 420px)",
            "@container hdo-dashboard (min-width: 1040px)",
            "@container hdo-dashboard (max-width: 419px)",
            "@container hdo-dashboard (max-width: 479px)", "min-width: 580px",
            "min-block-size: 14px", "var(--heat-due-mark-3)", "var(--progress-complete)",
            "hdo-event-marker", "hdo-loading-layout", "backdrop-filter",
            "hdo-year-weekday-label", "background: transparent",
        ),
    }
    for relative, markers in required.items():
        absent = [marker for marker in markers if marker not in sources[relative]]
        if absent:
            raise ValueError("{} is missing corrected release contracts: {}".format(relative, ", ".join(absent)))

    dashboard_surface_source = sources["renderer.py"] + sources["web/dashboard.js"] + sources["web/dashboard.css"]
    for forbidden in (
        "Outside due forecast", "Outside study history", "No events",
        "Select a date for details", "hdo-selected-date-details",
        "hdo-most-missed-list", "hdo-due-deck-breakdown", "Expand preview",
        "open_insight_card", "Using sample data", "getDueOverlayHeight", "hdo-due-hatch",
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
    if not isinstance(criteria, list) or [item.get("id") for item in criteria] != list(range(1, 43)):
        raise ValueError("corrected surface contract must encode criteria 1 through 42")
    if any(contract.get("release") != version for contract in (
        surface_contract, visual_matrix, capture_contract
    )):
        raise ValueError("release contracts must match the manifest version")
    if capture_contract.get("runtime_smoke_requirements") != {
        "active_head_deck": "A",
        "raw_new_cards_per_head_minimum": 40,
        "remaining_limits": {"A": 3, "B": 7},
        "expected_unexcluded_new_remaining": 10,
        "expected_excluding_b_new_remaining": 3,
        "restart_expected_new_remaining": 10,
    }:
        raise ValueError("multi-deck new-limit runtime smoke contract is incomplete")
    if capture_contract.get("primary_native_frames") != [
        entry.get("id") for entry in visual_matrix.get("cases", [])
    ]:
        raise ValueError("capture contract primary IDs differ from the visual matrix")

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
