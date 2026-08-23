#!/usr/bin/env python3
"""Assemble 100%-only Home Dashboard contact sheets from native Anki captures.

The input must be a passed report from ``runtime_probe_contact_sheets_100.py``
and the exact archive fixture prepared for the same disposable Anki run. Raw
Retina captures are copied byte-for-byte. Contact sheets normalize DPR 2
physical pixels to their logical 100% UI dimensions for readable pagination;
that presentation resize is not an alternate application or text scale.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
from typing import Any
import zipfile

from PIL import Image, ImageDraw, ImageFont

PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from home_dashboard_overhaul.qa.color_system_audit import write_release_reports


RELEASE = "1.8.0"
THEMES = (
    ("SG", "Sapphire Glass", "sapphire-glass"),
    ("GR", "Graphite", "graphite"),
    ("EM", "Emerald", "emerald"),
    ("HC", "High Contrast", "high-contrast"),
)
THEME_BY_CODE = {code: (name, slug) for code, name, slug in THEMES}
MODE_BY_CODE = {"L": "light", "D": "dark"}
VIEW_BY_CODE = {"M": "month", "Y": "year"}
LAYOUT_BY_CODE = {"C": "compact", "W": "wide"}
LAYOUT_DIMENSIONS = {"compact": (560, 1050), "wide": (1440, 900)}
CASE_PATTERN = re.compile(r"^VR-(SG|GR|EM|HC)-(L|D)-(M|Y)-(C|W)-100$")
INTERACTION_PATTERN = re.compile(r"^STATE-(SG|GR|EM|HC)-(L|D)-100$")
INTERACTION_DIMENSIONS = (1280, 900)
FULL_SCREEN_NAMES = (
    "exact-package-full-screen-month-100",
    "exact-package-full-screen-year-100",
)
SOURCE_ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return value


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        (
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
            if bold
            else "/System/Library/Fonts/Supplemental/Arial.ttf"
        ),
        "/System/Library/Fonts/Helvetica.ttc",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def png_dimensions(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        dimensions = image.size
        image.verify()
        return dimensions


def png_sample_color_count(path: Path) -> int:
    """Mirror the runtime probe's cheap paint-readiness sample from PNG bytes."""
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        step_x = max(1, width // 24)
        step_y = max(1, height // 18)
        colors: set[tuple[int, int, int, int]] = set()
        for x in range(step_x // 2, width, step_x):
            for y in range(step_y // 2, height, step_y):
                colors.add(rgba.getpixel((x, y)))
                if len(colors) >= 16:
                    return len(colors)
        return len(colors)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def parse_matrix_case(name: str) -> dict[str, str]:
    match = CASE_PATTERN.fullmatch(name)
    if match is None:
        raise RuntimeError(f"invalid 100% matrix case ID: {name}")
    theme_code, mode_code, view_code, layout_code = match.groups()
    theme, theme_slug = THEME_BY_CODE[theme_code]
    return {
        "id": name,
        "theme": theme,
        "theme_slug": theme_slug,
        "mode": MODE_BY_CODE[mode_code],
        "view": VIEW_BY_CODE[view_code],
        "layout": LAYOUT_BY_CODE[layout_code],
    }


def parse_interaction_case(name: str) -> dict[str, str]:
    match = INTERACTION_PATTERN.fullmatch(name)
    if match is None:
        raise RuntimeError(f"invalid 100% interaction case ID: {name}")
    theme_code, mode_code = match.groups()
    theme, theme_slug = THEME_BY_CODE[theme_code]
    return {
        "id": name,
        "theme": theme,
        "theme_slug": theme_slug,
        "mode": MODE_BY_CODE[mode_code],
    }


def validate_source_capture(
    *, capture_root: Path, name: str, record: dict[str, Any], dashboard: bool = True
) -> Path:
    reported_file = str(record.get("file", ""))
    require(
        bool(reported_file) and Path(reported_file).name == reported_file,
        f"{name} has an unsafe capture filename",
    )
    source = capture_root / reported_file
    require(source.is_file(), f"missing native capture: {source}")
    dimensions = png_dimensions(source)
    expected_dimensions = (
        int(record.get("pixel_width", -1)),
        int(record.get("pixel_height", -1)),
    )
    require(
        dimensions == expected_dimensions,
        f"{name} PNG dimensions {dimensions} do not match report {expected_dimensions}",
    )
    source_hash = sha256_file(source)
    require(
        source_hash == record.get("sha256"),
        f"{name} SHA-256 does not match its native runtime report",
    )
    require(record.get("ui_scale_percent") == 100, f"{name} is not UI scale 100%")
    require(record.get("text_scale_percent") == 100, f"{name} is not text scale 100%")
    require(float(record.get("device_pixel_ratio", 0)) == 2.0, f"{name} is not DPR 2")
    require(record.get("saved") is True, f"{name} was not recorded as saved")
    dom = record.get("dom")
    require(isinstance(dom, dict), f"{name} is missing DOM inspection evidence")
    require(dom.get("ready") is True, f"{name} did not reach the ready state")
    require(dom.get("textScale100") is True, f"{name} did not render text scale 100%")
    if dashboard:
        require(dom.get("statisticsCards") == 4, f"{name} did not render four statistics cards")
        require(dom.get("metricColumns") == 2, f"{name} did not render a two-column statistics grid")
        require(dom.get("metricRows") == 2, f"{name} did not render a two-row statistics grid")
        require(dom.get("metricNoOverlap") is True, f"{name} has overlapping metric labels and values")
        require(dom.get("cardsContained") is True, f"{name} has a statistics card overflow")
        require(dom.get("bibleAfter") is True, f"{name} did not place the Bible card after the statistics")
        require(dom.get("completeYearVisible") is True, f"{name} clipped the Year heatmap or month labels")
        require(dom.get("selectedDayVisible") is True, f"{name} clipped the selected calendar day")
        require(int(dom.get("eventMarkers", 0)) >= 1, f"{name} did not render the reference event state")
        require(dom.get("completionLegendSwatches") == 5, f"{name} has an incomplete completion legend")
        require(dom.get("dueLegendSwatches") == 3, f"{name} has an incomplete reviews-due legend")
        require(dom.get("eventLegendMarkers") == 1, f"{name} has an incomplete event legend")
        require(dom.get("layoutContained") is True, f"{name} escaped the dashboard root")
    require(dom.get("overflowX") is False, f"{name} has document-level horizontal overflow")
    require(png_sample_color_count(source) >= 8, f"{name} PNG is visually blank")
    if "sample_color_count" in record:
        require(
            int(record["sample_color_count"]) >= 8,
            f"{name} runtime paint sample is visually blank",
        )
    return source


def validate_evidence(
    *,
    capture_root: Path,
    runtime_report: Path,
    fixture_report: Path,
    package: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
]:
    runtime = read_json(runtime_report)
    fixture = read_json(fixture_report)
    require(runtime.get("status") == "passed", "native runtime report did not pass")
    require(runtime.get("errors") == [], "native runtime report contains errors")
    stress = runtime.get("stress_checks", {})
    require(stress.get("status") == "passed", "native Sapphire stress checks did not pass")
    require(
        set(stress.get("year_widths", {})) == {"319", "439", "440", "939", "940", "1280"},
        "native breakpoint stress matrix is incomplete",
    )
    require(isinstance(stress.get("month_compact"), dict), "native compact Month stress check is missing")
    require(isinstance(stress.get("no_next_event"), dict), "native no-event stress check is missing")
    interaction_report = runtime.get("interaction_fixture", {})
    require(interaction_report.get("status") == "passed", "native interaction-state fixture did not pass")
    require(interaction_report.get("case_count") == 8, "native interaction-state matrix is incomplete")
    scale_policy = runtime.get("scale_policy", {})
    require(scale_policy.get("ui_scale_percent") == 100, "runtime UI scale is not 100%")
    require(scale_policy.get("text_scale_percent") == 100, "runtime text scale is not 100%")
    require(
        scale_policy.get("excluded_ui_scales_percent") == [125, 150, 200],
        "runtime excluded-scale policy is incomplete",
    )
    identity = runtime.get("identity", {})
    require(identity.get("profile_matches") is True, "native profile identity did not match")
    require(
        identity.get("collection_inside_run_root") is True,
        "native collection escaped the disposable run root",
    )
    require(identity.get("sync_auth_present") is False, "native profile has sync credentials")
    require(
        identity.get("candidate_manifest_inside_run_root") is True
        and identity.get("probe_inside_run_root") is True,
        "native candidate or probe escaped the disposable base",
    )

    package_hash = sha256_file(package)
    require(
        fixture.get("archive_sha256") == package_hash,
        "fixture archive hash does not match the supplied package",
    )
    require(
        fixture.get("candidate_payload_matches_archive") is True,
        "installed package payload did not match the archive",
    )
    require(fixture.get("archive_file_count") == 24, "exact package must contain 24 files")
    with zipfile.ZipFile(package) as archive:
        require(archive.testzip() is None, "exact package archive integrity check failed")
        members = [info for info in archive.infolist() if not info.is_dir()]
        member_names = [info.filename for info in members]
        require(len(member_names) == len(set(member_names)), "exact package has duplicate members")
        require(
            all(
                not PurePosixPath(name).is_absolute()
                and ".." not in PurePosixPath(name).parts
                for name in member_names
            ),
            "exact package contains an unsafe member path",
        )
        member_count = len(members)
        archive_manifest = json.loads(archive.read("manifest.json"))
        require(
            archive_manifest.get("package") == "home_dashboard_overhaul",
            "exact package has the wrong package identifier",
        )
        require(
            archive_manifest.get("human_version") == RELEASE,
            f"exact package is not release {RELEASE}",
        )
        for name in member_names:
            source = SOURCE_ROOT.joinpath(*PurePosixPath(name).parts)
            require(source.is_file(), f"exact package member has no current source: {name}")
            require(
                source.read_bytes() == archive.read(name),
                f"exact package member differs from current source: {name}",
            )
    require(member_count == 24, f"exact package contains {member_count} files instead of 24")

    captures = runtime.get("captures")
    require(isinstance(captures, dict), "native runtime report has no capture map")
    require(len(captures) == 42, f"expected 42 native captures, found {len(captures)}")
    states = runtime.get("states")
    require(isinstance(states, dict), "native runtime report has no state map")
    require(set(states) == set(captures), "native state and capture IDs differ")
    capture_files = {path.name for path in capture_root.glob("*.png")}
    reported_files = {
        str(record.get("file", ""))
        for record in captures.values()
        if isinstance(record, dict)
    }
    require(capture_files == reported_files, "native capture directory and report files differ")
    expected_matrix_ids = {
        f"VR-{theme_code}-{mode_code}-{view_code}-{layout_code}-100"
        for theme_code, _theme, _slug in THEMES
        for mode_code in MODE_BY_CODE
        for view_code in VIEW_BY_CODE
        for layout_code in LAYOUT_BY_CODE
    }
    actual_matrix_ids = {name for name in captures if name.startswith("VR-")}
    require(actual_matrix_ids == expected_matrix_ids, "native 100% matrix IDs are incomplete or unexpected")
    expected_interaction_ids = {
        f"STATE-{theme_code}-{mode_code}-100"
        for theme_code, _theme, _slug in THEMES
        for mode_code in MODE_BY_CODE
    }
    actual_interaction_ids = {name for name in captures if name.startswith("STATE-")}
    require(
        actual_interaction_ids == expected_interaction_ids,
        "native interaction-state IDs are incomplete or unexpected",
    )
    require(
        set(captures) == expected_matrix_ids | expected_interaction_ids | set(FULL_SCREEN_NAMES),
        "native report contains a noncanonical or non-100% capture",
    )

    matrix: list[dict[str, Any]] = []
    for name in sorted(actual_matrix_ids):
        metadata = parse_matrix_case(name)
        record = captures[name]
        require(isinstance(record, dict), f"invalid runtime record for {name}")
        source = validate_source_capture(capture_root=capture_root, name=name, record=record)
        require(record.get("dom") == states[name], f"{name} DOM and state records differ")
        expected_logical = LAYOUT_DIMENSIONS[metadata["layout"]]
        actual_logical = (
            int(record.get("logical_width", -1)),
            int(record.get("logical_height", -1)),
        )
        require(
            actual_logical == expected_logical,
            f"{name} logical dimensions {actual_logical} do not match {expected_logical}",
        )
        require(
            (int(record["pixel_width"]), int(record["pixel_height"]))
            == (expected_logical[0] * 2, expected_logical[1] * 2),
            f"{name} Retina dimensions do not equal DPR 2 logical dimensions",
        )
        require(record.get("full_screen") is False, f"{name} was unexpectedly full-screen")
        require(record.get("window_title_matches_profile") is True, f"{name} window identity did not match the disposable profile")
        require(record["dom"].get("view") == metadata["view"], f"{name} rendered the wrong view")
        require(record["dom"].get("themeIdentity") == metadata["theme"], f"{name} rendered the wrong theme")
        require(record["dom"].get("colorModeIdentity") == metadata["mode"], f"{name} rendered the wrong mode")
        require(record["dom"].get("hostCanvasThemed") is True, f"{name} left the host viewport unthemed")
        require(record["dom"].get("colorSchemeApplied") is True, f"{name} did not apply color-scheme")
        if metadata["layout"] == "wide":
            require(record["dom"].get("wideSharedShell") is True, f"{name} did not use the shared wide shell")
            require(record["dom"].get("bottomAligned") is True, f"{name} rail and calendar bottoms did not align")
        else:
            require(record["dom"].get("stackedSharedShell") is True, f"{name} did not stack the rail beneath the calendar")
        matrix.append({**metadata, "record": record, "source": source})

    interaction: list[dict[str, Any]] = []
    interaction_cases = interaction_report.get("cases", {})
    require(
        isinstance(interaction_cases, dict) and set(interaction_cases) == expected_interaction_ids,
        "native interaction-state report and capture matrix differ",
    )
    for name in sorted(actual_interaction_ids):
        metadata = parse_interaction_case(name)
        record = captures[name]
        require(isinstance(record, dict), f"invalid runtime record for {name}")
        source = validate_source_capture(
            capture_root=capture_root,
            name=name,
            record=record,
            dashboard=False,
        )
        dom = record["dom"]
        require(record.get("dom") == states[name], f"{name} DOM and state records differ")
        require(record.get("dom") == interaction_cases[name], f"{name} interaction records differ")
        require(
            (int(record.get("logical_width", -1)), int(record.get("logical_height", -1)))
            == INTERACTION_DIMENSIONS,
            f"{name} has the wrong logical dimensions",
        )
        require(
            (int(record["pixel_width"]), int(record["pixel_height"]))
            == (INTERACTION_DIMENSIONS[0] * 2, INTERACTION_DIMENSIONS[1] * 2),
            f"{name} Retina dimensions do not equal DPR 2 logical dimensions",
        )
        require(record.get("full_screen") is False, f"{name} was unexpectedly full-screen")
        require(record.get("window_title_matches_profile") is True, f"{name} window identity did not match the disposable profile")
        require(dom.get("theme") == metadata["theme"], f"{name} rendered the wrong theme")
        require(dom.get("mode") == metadata["mode"], f"{name} rendered the wrong mode")
        for check in (
            "hostCanvasThemed", "colorSchemeApplied", "completeTokensMatch",
            "dueBackgroundsMatch", "dueIndicatorsMatch", "primaryStatesMatch",
            "segmentStatesMatch", "iconStatesMatch", "selectedVisible", "todayVisible",
            "combinedVisible", "combinedLayersIndependent", "eventLayered",
            "eventDueLayered", "emptyPastState", "emptyFutureState", "outsideState",
            "outsideDueState", "emptyProgressNoSliver", "partialProgressMapped",
            "fullProgressComplete", "surfaceHierarchyDistinct", "currentColorIcons",
        ):
            require(dom.get(check) is True, f"{name} failed {check}")
        require(dom.get("completionLevels") == 6, f"{name} omitted completion levels")
        require(dom.get("dueLevels") == 5, f"{name} omitted reviews-due levels")
        require(dom.get("completionUnique") == 6, f"{name} completion levels are not unique")
        require(dom.get("dueUnique") == 5, f"{name} reviews-due backgrounds are not explicitly ordered")
        require(dom.get("dueIndicatorCount") == 5, f"{name} omitted nonzero due indicators")
        require(
            dom.get("dueIndicatorHeights") == ["4px"] * 5,
            f"{name} due indicator height changes with intensity",
        )
        require(dom.get("primaryStateCount") == 4, f"{name} omitted primary action states")
        require(dom.get("segmentStateCount") == 2, f"{name} omitted segmented-control states")
        require(dom.get("iconStateCount") == 2, f"{name} omitted icon-control states")
        require(dom.get("selectedStateCount") == 6, f"{name} omitted selected heat levels")
        require(dom.get("todayStateCount") == 6, f"{name} omitted today heat levels")
        require(dom.get("eventMarkers") == 3, f"{name} omitted event marker layers")
        require(dom.get("semanticScenarioCount") == 6, f"{name} omitted target-aware metric states")
        interaction.append({**metadata, "record": record, "source": source})

    full_screen: list[dict[str, Any]] = []
    for name in FULL_SCREEN_NAMES:
        record = captures[name]
        require(isinstance(record, dict), f"invalid runtime record for {name}")
        source = validate_source_capture(capture_root=capture_root, name=name, record=record)
        require(record.get("dom") == states[name], f"{name} DOM and state records differ")
        view = "month" if "-month-" in name else "year"
        require(record.get("full_screen") is True, f"{name} is not marked full-screen")
        require(record.get("window_title_matches_profile") is True, f"{name} window identity did not match the disposable profile")
        require(record["dom"].get("view") == view, f"{name} rendered the wrong view")
        require(record["dom"].get("hostCanvasThemed") is True, f"{name} left the full-screen host viewport unthemed")
        require(record["dom"].get("colorSchemeApplied") is True, f"{name} did not apply color-scheme")
        require(record["dom"].get("wideSharedShell") is True, f"{name} did not use the shared wide shell")
        require(record["dom"].get("bottomAligned") is True, f"{name} rail and calendar bottoms did not align")
        require(int(record.get("logical_width", 0)) >= 1600, f"{name} is not a wide full-screen canvas")
        require(int(record.get("logical_height", 0)) >= 1000, f"{name} is not a tall full-screen canvas")
        require(
            int(record.get("frame_logical_width", 0)) >= int(record.get("logical_width", 0)),
            f"{name} frame width is inconsistent",
        )
        require(
            int(record.get("frame_logical_height", 0)) >= int(record.get("logical_height", 0)),
            f"{name} frame height is inconsistent",
        )
        full_screen.append(
            {
                "id": name,
                "view": view,
                "record": record,
                "source": source,
            }
        )
    return runtime, fixture, matrix, interaction, full_screen, package_hash


def sanitized_evidence(
    *, runtime: dict[str, Any], fixture: dict[str, Any], package_name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    published_runtime = deepcopy(runtime)
    published_fixture = deepcopy(fixture)
    run_roots = {
        value
        for value in (
            runtime.get("identity", {}).get("run_root"),
            fixture.get("run_root"),
        )
        if isinstance(value, str) and value
    }

    def sanitize(value: Any) -> Any:
        if isinstance(value, str):
            for run_root in run_roots:
                if value == run_root:
                    return "<disposable-base>"
                if value.startswith(run_root + "/"):
                    return "<disposable-base>" + value[len(run_root) :]
            return value
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: sanitize(item) for key, item in value.items()}
        return value

    published_runtime = sanitize(published_runtime)
    published_fixture = sanitize(published_fixture)
    published_fixture["archive"] = f"../package/{package_name}"
    published_json = json.dumps([published_runtime, published_fixture])
    require("/Users/" not in published_json, "published evidence retains a user path")
    require(
        "/private/tmp/anki-release-qa." not in published_json,
        "published evidence retains a disposable-base path",
    )
    return published_runtime, published_fixture


def copy_evidence(
    *,
    output: Path,
    matrix: list[dict[str, Any]],
    interaction: list[dict[str, Any]],
    full_screen: list[dict[str, Any]],
    runtime: dict[str, Any],
    fixture: dict[str, Any],
    package: Path,
    package_hash: str,
) -> None:
    captures_output = output / "captures"
    reports_output = output / "runtime-reports"
    package_output = output / "package"
    captures_output.mkdir(parents=True)
    reports_output.mkdir(parents=True)
    package_output.mkdir(parents=True)
    for item in [*matrix, *interaction, *full_screen]:
        destination = captures_output / item["source"].name
        shutil.copy2(item["source"], destination)
        require(sha256_file(destination) == item["record"]["sha256"], f"copy mismatch: {destination}")
    (reports_output / "runtime-report.json").write_text(
        json.dumps(runtime, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (reports_output / "fixture-report.json").write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    destination_package = package_output / package.name
    shutil.copy2(package, destination_package)
    require(sha256_file(destination_package) == package_hash, "copied package hash mismatch")
    (package_output / f"{package.name}.sha256").write_text(
        f"{package_hash}  {package.name}\n", encoding="utf-8"
    )


def paint_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str, margin: int) -> None:
    draw.text((margin, margin), title, fill="#f8fafc", font=font(38, bold=True))
    draw.text((margin, margin + 52), subtitle, fill="#a8b4c7", font=font(22))


def logical_image(source_path: Path, record: dict[str, Any]) -> Image.Image:
    logical_size = (int(record["logical_width"]), int(record["logical_height"]))
    with Image.open(source_path) as image:
        rgb = image.convert("RGB")
        if rgb.size == logical_size:
            return rgb.copy()
        return rgb.resize(logical_size, Image.Resampling.LANCZOS)


def render_theme_sheet(
    *, output: Path, theme: str, theme_slug: str, cases: list[dict[str, Any]]
) -> dict[str, Any]:
    margin = 42
    gutter = 32
    row_gutter = 32
    heading_height = 122
    caption_height = 48
    frame_padding = 10
    column_widths = (
        LAYOUT_DIMENSIONS["compact"][0] + 2 * frame_padding,
        LAYOUT_DIMENSIONS["wide"][0] + 2 * frame_padding,
    )
    row_height = caption_height + max(height for _width, height in LAYOUT_DIMENSIONS.values()) + 2 * frame_padding
    rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for mode in ("light", "dark"):
        for view in ("month", "year"):
            matching = {
                case["layout"]: case
                for case in cases
                if case["theme"] == theme and case["mode"] == mode and case["view"] == view
            }
            require(set(matching) == {"compact", "wide"}, f"incomplete row: {theme} {mode} {view}")
            rows.append((matching["compact"], matching["wide"]))

    width = 2 * margin + sum(column_widths) + gutter
    height = 2 * margin + heading_height + len(rows) * row_height + (len(rows) - 1) * row_gutter
    canvas = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(canvas)
    paint_header(
        draw,
        f"Home Dashboard {RELEASE} · {theme}",
        "Month and Year · light and dark · compact and wide · UI/text scale 100% only",
        margin,
    )
    placements: list[dict[str, Any]] = []
    y = margin + heading_height
    for row in rows:
        x = margin
        for column, case in enumerate(row):
            cell_width = column_widths[column]
            draw.rounded_rectangle(
                (x, y, x + cell_width, y + row_height),
                radius=14,
                fill="#e5e7eb",
                outline="#64748b",
                width=2,
            )
            label = f"{case['mode'].title()} · {case['view'].title()} · {case['layout']} · 100%"
            draw.text((x + frame_padding, y + 10), label, fill="#172033", font=font(22, bold=True))
            source_path = output / "captures" / case["source"].name
            source = logical_image(source_path, case["record"])
            image_x = x + frame_padding
            image_y = y + caption_height + frame_padding
            canvas.paste(source, (image_x, image_y))
            placements.append(
                {
                    "case_id": case["id"],
                    "source": f"captures/{source_path.name}",
                    "source_dimensions": [case["record"]["pixel_width"], case["record"]["pixel_height"]],
                    "presented_dimensions": [source.width, source.height],
                    "physical_to_logical_presentation_scale": 0.5,
                    "image_bounds": [image_x, image_y, image_x + source.width, image_y + source.height],
                }
            )
            source.close()
            x += cell_width + gutter
        y += row_height + row_gutter
    theme_number = [name for _code, name, _slug in THEMES].index(theme) + 1
    destination = output / "contact-sheets" / (
        f"0{theme_number}-dashboard-{theme_slug}-100-percent.png"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, "PNG", optimize=True)
    return {
        "title": f"Home Dashboard {RELEASE} · {theme}",
        "file": f"contact-sheets/{destination.name}",
        "dimensions": [canvas.width, canvas.height],
        "sha256": sha256_file(destination),
        "source_capture_count": len(placements),
        "ui_scale_percent": 100,
        "physical_to_logical_presentation_scale": 0.5,
        "placements": placements,
    }


def render_interaction_sheet(
    *, output: Path, captures: list[dict[str, Any]]
) -> dict[str, Any]:
    margin = 42
    gutter = 32
    row_gutter = 32
    heading_height = 122
    caption_height = 48
    frame_padding = 10
    cell_width = INTERACTION_DIMENSIONS[0] + 2 * frame_padding
    row_height = caption_height + INTERACTION_DIMENSIONS[1] + 2 * frame_padding
    width = 2 * margin + 2 * cell_width + gutter
    height = 2 * margin + heading_height + len(THEMES) * row_height + (len(THEMES) - 1) * row_gutter
    canvas = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(canvas)
    paint_header(
        draw,
        f"Home Dashboard {RELEASE} · interaction color states",
        "All four themes · light and dark · controls, heat levels, overlays, semantics, progress extremes · 100%",
        margin,
    )
    placements: list[dict[str, Any]] = []
    y = margin + heading_height
    for _code, theme, _slug in THEMES:
        matching = {
            item["mode"]: item for item in captures if item["theme"] == theme
        }
        require(set(matching) == {"light", "dark"}, f"incomplete interaction row: {theme}")
        x = margin
        for mode in ("light", "dark"):
            item = matching[mode]
            draw.rounded_rectangle(
                (x, y, x + cell_width, y + row_height),
                radius=14,
                fill="#e5e7eb",
                outline="#64748b",
                width=2,
            )
            label = f"{theme} · {mode.title()} · UI/text 100%"
            draw.text((x + frame_padding, y + 10), label, fill="#172033", font=font(22, bold=True))
            source_path = output / "captures" / item["source"].name
            source = logical_image(source_path, item["record"])
            image_x = x + frame_padding
            image_y = y + caption_height + frame_padding
            canvas.paste(source, (image_x, image_y))
            placements.append(
                {
                    "case_id": item["id"],
                    "source": f"captures/{source_path.name}",
                    "source_dimensions": [item["record"]["pixel_width"], item["record"]["pixel_height"]],
                    "presented_dimensions": [source.width, source.height],
                    "physical_to_logical_presentation_scale": 0.5,
                    "image_bounds": [image_x, image_y, image_x + source.width, image_y + source.height],
                }
            )
            source.close()
            x += cell_width + gutter
        y += row_height + row_gutter
    destination = output / "contact-sheets" / "05-interaction-state-fixture-100-percent.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, "PNG", optimize=True)
    return {
        "title": f"Home Dashboard {RELEASE} · interaction color states",
        "file": f"contact-sheets/{destination.name}",
        "dimensions": [canvas.width, canvas.height],
        "sha256": sha256_file(destination),
        "source_capture_count": len(placements),
        "ui_scale_percent": 100,
        "physical_to_logical_presentation_scale": 0.5,
        "placements": placements,
    }


def render_full_screen_sheet(
    *, output: Path, captures: list[dict[str, Any]]
) -> dict[str, Any]:
    margin = 42
    heading_height = 122
    row_gutter = 34
    caption_height = 48
    frame_padding = 10
    logical_images: list[tuple[dict[str, Any], Image.Image]] = []
    for item in captures:
        path = output / "captures" / item["source"].name
        logical_images.append((item, logical_image(path, item["record"])))
    width = 2 * margin + max(image.width for _item, image in logical_images) + 2 * frame_padding
    row_heights = [caption_height + image.height + 2 * frame_padding for _item, image in logical_images]
    height = 2 * margin + heading_height + sum(row_heights) + row_gutter
    canvas = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(canvas)
    paint_header(
        draw,
        f"Exact-package Home Dashboard {RELEASE} · full screen",
        "Native Anki Month and Year · UI/text scale 100% · DPR 2 sources retained",
        margin,
    )
    placements: list[dict[str, Any]] = []
    y = margin + heading_height
    for item, source in logical_images:
        row_height = caption_height + source.height + 2 * frame_padding
        cell_width = source.width + 2 * frame_padding
        x = (width - cell_width) // 2
        draw.rounded_rectangle(
            (x, y, x + cell_width, y + row_height),
            radius=14,
            fill="#e5e7eb",
            outline="#64748b",
            width=2,
        )
        label = f"{item['view'].title()} · full-screen Anki web canvas · 100%"
        draw.text((x + frame_padding, y + 10), label, fill="#172033", font=font(22, bold=True))
        image_x = x + frame_padding
        image_y = y + caption_height + frame_padding
        canvas.paste(source, (image_x, image_y))
        placements.append(
            {
                "case_id": item["id"],
                "source": f"captures/{item['source'].name}",
                "source_dimensions": [item["record"]["pixel_width"], item["record"]["pixel_height"]],
                "presented_dimensions": [source.width, source.height],
                "frame_logical_dimensions": [
                    item["record"]["frame_logical_width"],
                    item["record"]["frame_logical_height"],
                ],
                "physical_to_logical_presentation_scale": 0.5,
                "image_bounds": [image_x, image_y, image_x + source.width, image_y + source.height],
            }
        )
        source.close()
        y += row_height + row_gutter
    destination = output / "contact-sheets" / "06-exact-package-full-screen-dashboard-100-percent.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, "PNG", optimize=True)
    return {
        "title": f"Exact-package Home Dashboard {RELEASE} · full screen",
        "file": f"contact-sheets/{destination.name}",
        "dimensions": [canvas.width, canvas.height],
        "sha256": sha256_file(destination),
        "source_capture_count": len(placements),
        "ui_scale_percent": 100,
        "physical_to_logical_presentation_scale": 0.5,
        "placements": placements,
    }


def manifest_case(item: dict[str, Any]) -> dict[str, Any]:
    record = item["record"]
    return {
        "id": item["id"],
        "file": f"captures/{item['source'].name}",
        "theme": item["theme"],
        "mode": item["mode"],
        "view": item["view"],
        "layout": item["layout"],
        "ui_scale_percent": 100,
        "text_scale_percent": 100,
        "logical_dimensions": [record["logical_width"], record["logical_height"]],
        "physical_dimensions": [record["pixel_width"], record["pixel_height"]],
        "device_pixel_ratio": record["device_pixel_ratio"],
        "sha256": record["sha256"],
        "dom": record["dom"],
    }


def manifest_interaction_case(item: dict[str, Any]) -> dict[str, Any]:
    record = item["record"]
    return {
        "id": item["id"],
        "file": f"captures/{item['source'].name}",
        "theme": item["theme"],
        "mode": item["mode"],
        "ui_scale_percent": 100,
        "text_scale_percent": 100,
        "logical_dimensions": [record["logical_width"], record["logical_height"]],
        "physical_dimensions": [record["pixel_width"], record["pixel_height"]],
        "device_pixel_ratio": record["device_pixel_ratio"],
        "sha256": record["sha256"],
        "dom": record["dom"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--runtime-report", required=True, type=Path)
    parser.add_argument("--fixture-report", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    capture_root = args.capture_root.resolve()
    runtime_report = args.runtime_report.resolve()
    fixture_report = args.fixture_report.resolve()
    package = args.package.resolve()
    output = args.output.resolve()
    require(capture_root.is_dir(), f"capture root not found: {capture_root}")
    require(runtime_report.is_file(), f"runtime report not found: {runtime_report}")
    require(fixture_report.is_file(), f"fixture report not found: {fixture_report}")
    require(package.is_file(), f"package not found: {package}")
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {output}")

    runtime, fixture, matrix, interaction, full_screen, package_hash = validate_evidence(
        capture_root=capture_root,
        runtime_report=runtime_report,
        fixture_report=fixture_report,
        package=package,
    )
    runtime, fixture = sanitized_evidence(
        runtime=runtime,
        fixture=fixture,
        package_name=package.name,
    )
    output.mkdir(parents=True)
    copy_evidence(
        output=output,
        matrix=matrix,
        interaction=interaction,
        full_screen=full_screen,
        runtime=runtime,
        fixture=fixture,
        package=package,
        package_hash=package_hash,
    )
    reports_summary = write_release_reports(output / "reports", SOURCE_ROOT)
    require(
        reports_summary["hardcoded_color_audit"]["status"] == "passed",
        "hardcoded-color audit did not pass",
    )
    require(
        reports_summary["contrast_test_report"]["status"] == "passed",
        "contrast test report did not pass",
    )

    sheets = [
        render_theme_sheet(
            output=output,
            theme=theme,
            theme_slug=theme_slug,
            cases=matrix,
        )
        for _theme_code, theme, theme_slug in THEMES
    ]
    sheets.append(render_interaction_sheet(output=output, captures=interaction))
    sheets.append(render_full_screen_sheet(output=output, captures=full_screen))

    full_screen_manifest = []
    for item in full_screen:
        record = item["record"]
        full_screen_manifest.append(
            {
                "id": item["id"],
                "view": item["view"],
                "file": f"captures/{item['source'].name}",
                "ui_scale_percent": 100,
                "text_scale_percent": 100,
                "logical_web_canvas_dimensions": [record["logical_width"], record["logical_height"]],
                "logical_full_screen_frame_dimensions": [
                    record["frame_logical_width"],
                    record["frame_logical_height"],
                ],
                "physical_dimensions": [record["pixel_width"], record["pixel_height"]],
                "device_pixel_ratio": record["device_pixel_ratio"],
                "sha256": record["sha256"],
                "dom": record["dom"],
            }
        )

    manifest = {
        "schema_version": 2,
        "release": RELEASE,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "Updated native Home Dashboard contact sheets at UI/text scale 100% only",
        "scale_policy": {
            "allowed_ui_scale_percent": [100],
            "allowed_text_scale_percent": [100],
            "excluded_ui_scales_percent": [125, 150, 200],
            "native_qt_scale_factor": 1.0,
            "native_retina_device_pixel_ratio": 2.0,
            "contact_sheet_physical_to_logical_presentation_scale": 0.5,
            "presentation_note": (
                "Raw DPR 2 captures are preserved unchanged. Contact-sheet placements are reduced "
                "to their logical dimensions only; application and text scale remain 100%."
            ),
        },
        "candidate": {
            "file": f"package/{package.name}",
            "sha256": package_hash,
            "archive_file_count": fixture["archive_file_count"],
            "installed_payload_matches_archive": fixture["candidate_payload_matches_archive"],
        },
        "native_anki_run": {
            "capture_kind": "exact package in a disposable sync-disabled native Anki profile",
            "runtime_report": "runtime-reports/runtime-report.json",
            "fixture_report": "runtime-reports/fixture-report.json",
            "status": runtime["status"],
            "errors": runtime["errors"],
            "identity": runtime["identity"],
            "screens": runtime["screens"],
        },
        "raw_capture_count": 42,
        "renderer_matrix": {
            "case_count": len(matrix),
            "themes": [theme for _code, theme, _slug in THEMES],
            "modes": ["light", "dark"],
            "views": ["month", "year"],
            "layouts": {name: list(dimensions) for name, dimensions in LAYOUT_DIMENSIONS.items()},
            "cases": [manifest_case(item) for item in matrix],
        },
        "interaction_state_matrix": {
            "case_count": len(interaction),
            "themes": [theme for _code, theme, _slug in THEMES],
            "modes": ["light", "dark"],
            "logical_dimensions": list(INTERACTION_DIMENSIONS),
            "cases": [manifest_interaction_case(item) for item in interaction],
        },
        "full_screen": full_screen_manifest,
        "contact_sheet_count": len(sheets),
        "contact_sheets": sheets,
        "release_reports": reports_summary,
        "minimal_validation": [
            "runtime report passed with zero errors",
            "42 canonical 100%-only captures present: 32 dashboard, 8 interaction-state, and 2 full-screen",
            "each PNG dimensions and SHA-256 match the runtime report; a nonblank paint sample passes",
            "exact 24-file package archive and installed payload match",
            "each dashboard has four statistics cards, Bible card ordering, and no document-level horizontal overflow",
            "hardcoded-color audit has zero unexplained component-level literals",
            "full viewport theming, integrated footer, soft due backgrounds, fixed due markers, primary actions, text, overlays, and important-boundary checks pass",
        ],
        "quality_status": "clean",
        "acceptance_boundary": (
            "Native macOS exact-package rendering and scripted DOM evidence only. Spoken VoiceOver, "
            "human contact-sheet acceptance, Windows/Linux rendering, forced colors, device-specific behavior, "
            "and non-100% OS display scaling remain separate gates."
        ),
    }
    manifest_path = output / "capture-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    index = {
        "release": RELEASE,
        "ui_scale_percent": 100,
        "raw_capture_count": 42,
        "candidate_sha256": package_hash,
        "contact_sheets": [
            {
                "file": sheet["file"],
                "title": sheet["title"],
                "dimensions": sheet["dimensions"],
                "sha256": sheet["sha256"],
            }
            for sheet in sheets
        ],
    }
    (output / "contact-sheet-index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    readme = [
        f"# Home Dashboard {RELEASE} contact sheets — 100% only",
        "",
        f"Candidate SHA-256: `{package_hash}`",
        "",
        "These sheets were generated from the exact packaged add-on in a fresh, sync-disabled independent Anki profile. Every UI and text render is 100%. No 125%, 150%, or 200% cases are included.",
        "",
        "The 42 original native screenshots remain byte-for-byte in `captures/` at Retina DPR 2. The sheets reduce those physical pixels to their corresponding logical size for pagination; this does not change the UI scale.",
        "",
        "## Contact sheets",
        "",
    ]
    readme.extend(f"- [{sheet['title']}]({sheet['file']})" for sheet in sheets)
    readme.extend(
        [
            "",
            "## Evidence",
            "",
            "- 32 dashboard captures: four themes, light/dark, Month/Year, and compact/wide.",
            "- 8 interaction-state captures: four themes in light/dark with primary and secondary controls, completion and Reviews Due levels, every Today/Selected completion level, event/outside combinations, target-aware rates, and empty/partial/full progress.",
            "- 2 exact-package full-screen dashboard captures: Month and Year.",
            "- Native runtime report: passed with no recorded errors.",
            f"- [Hardcoded-color audit]({reports_summary['hardcoded_color_audit']['markdown']}): passed with zero component-level hardcoding.",
            f"- [Contrast test report]({reports_summary['contrast_test_report']['markdown']}): {reports_summary['contrast_test_report']['check_count']} gated pairs passed.",
            f"- [Changed-file summary]({reports_summary['changed_file_summary']['markdown']}): {reports_summary['changed_file_summary']['file_count']} release-candidate files.",
            "- Exact package: 24 files, installed payload byte-matched to the archive.",
            f"- Disposable profile: `{runtime['identity']['profile']}`.",
            "- Sync credentials: absent.",
            "",
            "## Acceptance boundary",
            "",
            "Spoken VoiceOver, Windows/Linux rendering, device-specific behavior, and non-100% OS display scaling remain separate acceptance gates.",
            "",
        ]
    )
    (output / "README.md").write_text("\n".join(readme), encoding="utf-8")

    print(f"output {output}")
    print(f"raw_captures {len(matrix) + len(interaction) + len(full_screen)}")
    print(f"contact_sheets {len(sheets)}")
    print(f"candidate_sha256 {package_hash}")


if __name__ == "__main__":
    main()
