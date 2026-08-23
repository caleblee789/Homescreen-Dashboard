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
    "qa/calendar_surface_manifest.json",
    "qa/visual_regression_matrix_1_7_0.json",
)
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
FIXED_TIMESTAMP = (2026, 8, 21, 0, 0, 0)


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

    signatures: set[tuple[str, ...]] = set()
    required_heatmap_roles = {
        "heatmap_empty", "on_heatmap_empty", "heatmap_out_of_month",
        "on_heatmap_out_of_month",
        *{"heatmap_{}".format(level) for level in range(1, 6)},
        *{"on_heatmap_{}".format(level) for level in range(1, 6)},
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
            signature: list[str] = []
            for mode in ("light", "dark"):
                tokens = palette[mode]
                if set(tokens) != required_heatmap_roles:
                    raise ValueError("{} / {} / {} has an incomplete authored ladder".format(theme_name, preset_name, mode))
                fills = [tokens["heatmap_{}".format(level)] for level in range(1, 6)]
                distances = [_perceptual_distance(tokens["heatmap_empty"], fill) for fill in fills]
                if any(left >= right for left, right in zip(distances, distances[1:])):
                    raise ValueError("{} / {} / {} intensity is not monotonic".format(theme_name, preset_name, mode))
                if any(_perceptual_distance(left, right) < 6 for left, right in zip(fills, fills[1:])):
                    raise ValueError("{} / {} / {} has indistinguishable adjacent levels".format(theme_name, preset_name, mode))
                for role in ("empty", "1", "2", "3", "4", "5", "out_of_month"):
                    if _contrast(tokens["heatmap_{}".format(role)], tokens["on_heatmap_{}".format(role)]) < 4.5:
                        raise ValueError("{} / {} / {} {} fails text contrast".format(theme_name, preset_name, mode, role))
                resolved = resolver(theme_name, mode, mode == "dark", preset_name)
                for key, value in tokens.items():
                    if resolved.get(key) != value:
                        raise ValueError("resolved heatmap tokens drift from the selected authored preset")
                signature.extend(tokens[key] for key in sorted(tokens))
            frozen = tuple(signature)
            if frozen in signatures:
                raise ValueError("heatmap presets must be independently authored")
            signatures.add(frozen)

    required_semantic = {
        "background", "surface", "panel_surface", "text", "muted", "border",
        "accent", "completion", "review", "success", "event", "forecast",
        "focus", "warning", "danger", "disabled", "due_stripe",
    }
    for theme_name in expected_themes:
        for mode in ("light", "dark"):
            resolved = resolver(theme_name, mode, mode == "dark", defaults[theme_name])
            missing = sorted(required_semantic.difference(resolved))
            if missing:
                raise ValueError("{} {} is missing semantic roles: {}".format(theme_name, mode, ", ".join(missing)))


def _validate_visual_matrix(matrix: dict) -> None:
    axes = {
        "theme": ("Sapphire Glass", "Graphite", "Emerald", "High Contrast"),
        "mode": ("light", "dark"),
        "view": ("month", "year"),
        "layout": ("compact", "wide"),
        "text_scale": (100, 125, 150),
    }
    entries = matrix.get("cases")
    if not isinstance(entries, list) or len(entries) != 96:
        raise ValueError("visual regression matrix must contain exactly 96 cases")
    expected = set(itertools.product(*axes.values()))
    actual = {
        (entry.get("theme"), entry.get("mode"), entry.get("view"), entry.get("layout"), entry.get("text_scale"))
        for entry in entries if isinstance(entry, dict)
    }
    if actual != expected or len(actual) != len(entries):
        raise ValueError("visual regression matrix must cover the exact Cartesian product once")
    if len({entry.get("id") for entry in entries}) != 96:
        raise ValueError("visual regression IDs must be unique")


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
    surface_contract = _json("qa/calendar_surface_manifest.json")
    visual_matrix = _json("qa/visual_regression_matrix_1_7_0.json")
    if manifest.get("package") != "home_dashboard_overhaul" or manifest.get("name") != "Home Screen Dashboard":
        raise ValueError("unexpected add-on identity")
    version = manifest.get("human_version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version) or version != "1.7.0":
        raise ValueError("release artifact must use semantic version 1.7.0")
    if (manifest.get("min_point_version"), manifest.get("max_point_version")) != (260800, 260800):
        raise ValueError("release must be pinned to Anki 26.8")
    if config.get("schema_version") != 6:
        raise ValueError("config schema must be version 6")
    if config.get("layout", {}).get("order") != ["study_calendar", "summary_metrics", "bible_verse"]:
        raise ValueError("default hierarchy must be Calendar, metrics, Bible")
    config_text = json.dumps(config, sort_keys=True)
    for removed in ("selected_date_details", "selected_date_panel", "most_missed", "due_deck_breakdown"):
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
        ),
        "config_schema.py": (
            "SCHEMA_VERSION = 6", "presets_by_theme", "retention_target",
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
            "hdo-calendar-context-bar", "hdo-summary-metrics-grid", "hdo-bible-card",
            "New cards studied", "hdo-progress-segment", "retention_target", "day_insight_payload",
            "hdo-loading-region--calendar", "The dashboard could not finish loading.",
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
            "function getNextUpcomingEvent", "function getDueLoadScale",
            "function getDueOverlayHeight", "function getDueLoadLevel",
            'calendar.addEventListener("pointerover"', 'send("open_most_missed"',
            "function mountLoadingState", "Still loading your study data…",
            'send("diagnostics", {})',
        ),
        "web/dashboard.css": (
            "hdo-calendar-context-bar", "pointer-events: none", "min-width: min(232px",
            "min-width: 1320px", "minmax(760px, 1fr) minmax(500px, .46fr)",
            "height: 6px", "hdo-event-marker", "hdo-loading-layout",
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
        "open_insight_card", "Using sample data",
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
    if not isinstance(criteria, list) or len(criteria) != 28:
        raise ValueError("corrected surface contract must encode all 28 acceptance criteria")

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
