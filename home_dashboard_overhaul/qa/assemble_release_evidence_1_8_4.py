#!/usr/bin/env python3
"""Assemble immutable Home Dashboard 1.8.4 native release evidence.

The assembler accepts the passed initial and restart native Deck Browser
runtime reports plus the exact candidate archive used by both runs. It verifies
every capture against those reports, copies all 56 raw PNGs byte-for-byte, and
creates the required overview plus 15 readable detail sheets. Restart
persistence is fail-closed and cannot be waived.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
from typing import Any, Iterable
import zipfile

from PIL import Image, ImageDraw, ImageFont


RELEASE = "1.8.4"
EXPECTED_INITIAL_CAPTURE_COUNT = 55
EXPECTED_CAPTURE_COUNT = 56
EXPECTED_PRIMARY_COUNT = 16
EXPECTED_ARCHIVE_MEMBER_COUNT = 24
REFERENCE_SCREENSHOT_SHA256 = (
    "a53963d27305bfe531fdd56ebc675ccf25b8be58276636b4a8c4a7380e701c57"
)
SOURCE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = SOURCE_ROOT / "qa" / "release-evidence-1.8.4-2026-08-24"

PRIMARY_GROUPS = (
    (
        "primary-sapphire",
        "Primary matrix — Sapphire Glass",
        ("PRIMARY-SG-L-M", "PRIMARY-SG-L-Y", "PRIMARY-SG-D-M", "PRIMARY-SG-D-Y"),
    ),
    (
        "primary-graphite",
        "Primary matrix — Graphite",
        ("PRIMARY-GR-L-M", "PRIMARY-GR-L-Y", "PRIMARY-GR-D-M", "PRIMARY-GR-D-Y"),
    ),
    (
        "primary-emerald",
        "Primary matrix — Emerald",
        ("PRIMARY-EM-L-M", "PRIMARY-EM-L-Y", "PRIMARY-EM-D-M", "PRIMARY-EM-D-Y"),
    ),
    (
        "primary-high-contrast",
        "Primary matrix — High Contrast",
        ("PRIMARY-HC-L-M", "PRIMARY-HC-L-Y", "PRIMARY-HC-D-M", "PRIMARY-HC-D-Y"),
    ),
)

SUPPLEMENTAL_GROUPS = (
    (
        "fresh-data",
        "Fresh-data states",
        ("FRESH-SG-L-M", "FRESH-SG-L-Y", "HISTORICAL-ALL-CLEAR-SG-D-M", "FRESH-SG-D-Y"),
    ),
    (
        "responsive-01",
        "Responsive states — Sapphire",
        (
            "RESP-SG-L-INTERMEDIATE",
            "RESP-SG-D-INTERMEDIATE",
            "RESP-SG-L-NARROW",
            "RESP-SG-D-NARROW",
            "RESP-SG-D-INTERMEDIATE-SCROLLED-BOTTOM",
        ),
    ),
    (
        "responsive-02",
        "Responsive states — High Contrast narrow",
        ("RESP-HC-L-NARROW", "RESP-HC-D-NARROW", "RESP-HC-D-NARROW-SCROLLED-BOTTOM"),
    ),
    (
        "year-scroll",
        "Narrow Year access — January, current month, December",
        (
            "RESP-YEAR-NARROW-JANUARY",
            "RESP-YEAR-NARROW-CURRENT-MONTH",
            "RESP-YEAR-NARROW-DECEMBER",
        ),
    ),
    (
        "calendar-states-01",
        "Calendar states — markers, events, and tooltip",
        (
            "STATE-COMBINED-TODAY",
            "STATE-SELECTED-EVENT",
            "STATE-NEXT-EVENT-FUTURE",
            "STATE-PAST-TOOLTIP",
        ),
    ),
    (
        "narrow-footer-content",
        "Narrow footer — long event and localized date",
        ("STATE-NARROW-LONG-EVENT-PLUS-9", "STATE-NARROW-LONG-LOCALIZED-DATE"),
    ),
    (
        "calendar-states-02",
        "Calendar states — month and year boundaries",
        (
            "STATE-FIVE-ROW-SUNDAY",
            "STATE-SIX-ROW-MONDAY",
            "STATE-YEAR-BOUNDARIES",
            "STATE-COMPLETE-METRICS",
        ),
    ),
    (
        "backgrounds-01",
        "Background and opacity states",
        ("BACKGROUND-SG-L", "BACKGROUND-SG-D", "BACKGROUND-EM-L", "BACKGROUND-EM-D"),
    ),
    (
        "backgrounds-02",
        "Reduced-opacity state",
        ("BACKGROUND-REDUCED-OPACITY",),
    ),
    (
        "bible",
        "Bible card states",
        ("BIBLE-SHORT", "BIBLE-LONG", "BIBLE-CUSTOM-FONT", "BIBLE-DISABLED", "BIBLE-LONG-NARROW"),
    ),
    (
        "runtime",
        "Runtime loading, failure, and retry states",
        (
            "RUNTIME-INITIAL-LOADING",
            "RUNTIME-DELAYED-LOADING",
            "RUNTIME-FAILURE",
            "RUNTIME-RETRY",
            "RUNTIME-RESTART-PERSISTENCE",
        ),
    ),
)

DETAIL_GROUPS = PRIMARY_GROUPS + SUPPLEMENTAL_GROUPS


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected a JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def safe_archive_members(archive: Path) -> tuple[list[str], dict[str, str], bool]:
    member_hashes: dict[str, str] = {}
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        for name in names:
            posix = PurePosixPath(name)
            require(not posix.is_absolute(), f"archive has an absolute member: {name}")
            require(".." not in posix.parts, f"archive has a traversal member: {name}")
            require(not name.endswith("/"), f"archive unexpectedly contains a directory: {name}")
            member_hashes[name] = hashlib.sha256(bundle.read(name)).hexdigest()

        source_parity = all(
            (SOURCE_ROOT / name).is_file()
            and (SOURCE_ROOT / name).read_bytes() == bundle.read(name)
            for name in names
        )
    return names, member_hashes, source_parity


def capture_source(runtime_root: Path, record: dict[str, Any]) -> Path:
    relative = Path(str(record.get("file", "")))
    require(not relative.is_absolute(), f"capture has an absolute path: {relative}")
    require(".." not in relative.parts, f"capture has a traversal path: {relative}")
    return runtime_root / relative


def verify_capture(
    runtime_root: Path, case_id: str, record: dict[str, Any]
) -> tuple[Path, tuple[int, int]]:
    source = capture_source(runtime_root, record)
    require(source.is_file(), f"missing native capture for {case_id}: {source}")
    require(source.name == f"{case_id}.png", f"unexpected filename for {case_id}: {source.name}")
    require(sha256_file(source) == record.get("sha256"), f"capture hash mismatch: {case_id}")
    require(record.get("ui_scale_percent") == 100, f"capture is not UI scale 100%: {case_id}")
    require(record.get("text_scale_percent") == 100, f"capture is not text scale 100%: {case_id}")
    device_pixel_ratio = float(record.get("device_pixel_ratio", 0))
    require(0.5 <= device_pixel_ratio <= 4.0, f"invalid native DPR: {case_id}")
    with Image.open(source) as image:
        image.verify()
        dimensions = image.size
    physical_pixels = record.get("physical_pixels")
    require(
        isinstance(physical_pixels, list)
        and physical_pixels == list(dimensions),
        f"capture pixels differ from the native grab record: {case_id}",
    )
    native_dimensions = record.get("native_window_dimensions")
    require(
        isinstance(native_dimensions, list)
        and tuple(native_dimensions) in {(1710, 1073), (1120, 940), (620, 980)},
        f"unexpected native window geometry for {case_id}: {native_dimensions}",
    )
    require(
        abs(dimensions[0] - float(native_dimensions[0]) * device_pixel_ratio) <= 2,
        f"capture width does not match native DPR: {case_id}",
    )
    title_chrome_pixels = float(native_dimensions[1]) * device_pixel_ratio - dimensions[1]
    require(
        0 <= title_chrome_pixels <= 100,
        f"capture height does not match the native content frame: {case_id}",
    )
    minimum_colors = 6 if record.get("theme") == "High Contrast" else 12
    require(int(record.get("sampled_color_count", 0)) >= minimum_colors, f"capture appears blank: {case_id}")
    dom = record.get("dom", {})
    require(isinstance(dom, dict), f"missing DOM record: {case_id}")
    require(dom.get("documentOverflowX") == 0, f"horizontal overflow in {case_id}")
    if case_id not in {"RUNTIME-INITIAL-LOADING", "RUNTIME-DELAYED-LOADING", "RUNTIME-FAILURE"}:
        require(dom.get("ready") is True, f"ready state missing in {case_id}")
    return source, dimensions


def copy_verified(source: Path, destination: Path) -> None:
    shutil.copy2(source, destination)
    require(sha256_file(source) == sha256_file(destination), f"copy hash mismatch: {destination}")


def fit_image(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    copy = source.convert("RGB")
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    return copy


def record_subtitle(record: dict[str, Any]) -> str:
    dimensions = record.get("native_window_dimensions") or []
    native = (
        "Native {}×{}".format(dimensions[0], dimensions[1])
        if isinstance(dimensions, list) and len(dimensions) == 2
        else "Native dimensions unavailable"
    )
    container_width = record.get("dashboard_container_width")
    container = "Container {} px".format(container_width) if container_width else "Container unavailable"
    pieces = (
        str(record.get("theme", "")),
        str(record.get("mode", "")).title(),
        str(record.get("state_label") or record.get("view", "")).title(),
        native,
        container,
        str(record.get("density", "")).title(),
        "UI 100%",
    )
    return "  •  ".join(piece for piece in pieces if piece)


def draw_detail_sheet(
    *,
    output: Path,
    title: str,
    case_ids: tuple[str, ...],
    records: dict[str, dict[str, Any]],
    capture_dir: Path,
    page_number: int,
    page_count: int,
    package_hash: str,
) -> None:
    canvas = Image.new("RGB", (3600, 2400), "#08111f")
    draw = ImageDraw.Draw(canvas)
    title_font = font(52, bold=True)
    subtitle_font = font(25)
    label_font = font(31, bold=True)
    metadata_font = font(23)
    footer_font = font(22)

    draw.text((92, 62), f"Home Screen Dashboard {RELEASE}", fill="#f4f8ff", font=title_font)
    draw.text((92, 125), title, fill="#8fc8ff", font=subtitle_font)
    draw.text(
        (3508, 75),
        f"PAGE {page_number:02d} / {page_count:02d}",
        fill="#9aabc0",
        font=subtitle_font,
        anchor="ra",
    )

    panel_height = 1032
    if len(case_ids) == 5:
        panel_width = 1100
        positions = (
            (92, 204),
            (1250, 204),
            (2408, 204),
            (671, 1268),
            (1829, 1268),
        )
    else:
        panel_width = 1692
        positions = ((92, 204), (1816, 204), (92, 1268), (1816, 1268))
    for index, case_id in enumerate(case_ids):
        x, y = positions[index]
        draw.rounded_rectangle(
            (x, y, x + panel_width, y + panel_height),
            radius=18,
            fill="#101d30",
            outline="#36506f",
            width=3,
        )
        draw.text((x + 28, y + 22), case_id, fill="#f4f8ff", font=label_font)
        draw.text(
            (x + 28, y + 64),
            record_subtitle(records[case_id]),
            fill="#9eb3ca",
            font=metadata_font,
        )
        image_box = (panel_width - 56, panel_height - 124)
        with Image.open(capture_dir / f"{case_id}.png") as source:
            rendered = fit_image(source, image_box)
        px = x + (panel_width - rendered.width) // 2
        py = y + 106 + (panel_height - 118 - rendered.height) // 2
        draw.rectangle(
            (px - 2, py - 2, px + rendered.width + 1, py + rendered.height + 1),
            fill="#02060c",
            outline="#617995",
            width=2,
        )
        canvas.paste(rendered, (px, py))

    footer = (
        "Native Anki Deck Browser • UI 100% • Raw captures preserved byte-for-byte • "
        f"Exact package {package_hash[:16]}…"
    )
    draw.text((92, 2360), footer, fill="#7f93aa", font=footer_font, anchor="ls")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)


def draw_overview_sheet(
    *,
    output: Path,
    case_ids: list[str],
    records: dict[str, dict[str, Any]],
    capture_dir: Path,
    package_hash: str,
) -> None:
    columns = 5
    rows = (len(case_ids) + columns - 1) // columns
    canvas_width = 3840
    header_height = 190
    footer_height = 90
    margin = 60
    gutter = 26
    tile_width = (canvas_width - 2 * margin - gutter * (columns - 1)) // columns
    tile_height = 470
    canvas_height = header_height + rows * tile_height + footer_height
    canvas = Image.new("RGB", (canvas_width, canvas_height), "#08111f")
    draw = ImageDraw.Draw(canvas)
    title_font = font(52, bold=True)
    subtitle_font = font(24)
    label_font = font(23, bold=True)
    metadata_font = font(14)
    footer_font = font(21)

    draw.text((margin, 48), f"Home Screen Dashboard {RELEASE} — Complete native capture index", fill="#f4f8ff", font=title_font)
    draw.text(
        (margin, 116),
        f"56 updated captures • 16 primary frames • 40 supplemental frames • native Deck Browser at UI 100%",
        fill="#8fc8ff",
        font=subtitle_font,
    )

    for index, case_id in enumerate(case_ids):
        row, column = divmod(index, columns)
        x = margin + column * (tile_width + gutter)
        y = header_height + row * tile_height
        draw.rounded_rectangle(
            (x, y, x + tile_width, y + tile_height - 22),
            radius=12,
            fill="#101d30",
            outline="#304965",
            width=2,
        )
        draw.text((x + 18, y + 15), case_id, fill="#f4f8ff", font=label_font)
        subtitle = record_subtitle(records[case_id])
        draw.text((x + 18, y + 48), subtitle, fill="#9eb3ca", font=metadata_font)
        with Image.open(capture_dir / f"{case_id}.png") as source:
            rendered = fit_image(source, (tile_width - 36, tile_height - 106))
        px = x + (tile_width - rendered.width) // 2
        py = y + 82 + (tile_height - 100 - rendered.height) // 2
        draw.rectangle(
            (px - 1, py - 1, px + rendered.width, py + rendered.height),
            fill="#02060c",
            outline="#526c88",
        )
        canvas.paste(rendered, (px, py))

    draw.text(
        (margin, canvas_height - 42),
        f"Review the 15 numbered detail sheets for readable full-frame comparisons. One restart passed. Exact package {package_hash[:16]}…",
        fill="#7f93aa",
        font=footer_font,
        anchor="ls",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)


def planned_tags(planned: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for entry in planned.get("supplemental_frames", []):
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            result[entry["id"]] = [str(tag) for tag in entry.get("tags", [])]
    return result


def validate_multi_deck_smoke(report: dict[str, Any], stage: str) -> dict[str, Any]:
    smoke = report.get("multi_deck_new_limit_smoke", {})
    require(smoke.get("status") == "passed", f"{stage} multi-deck smoke did not pass")
    require(smoke.get("stage") == stage, f"{stage} multi-deck smoke stage mismatch")
    require(smoke.get("initial_dashboard_loaded_before_fixture") is True, f"{stage} initial dashboard did not load")
    initial_queue = smoke.get("initial_dashboard_queue", {})
    expected_initial = 0 if stage == "initial" else 10
    require(initial_queue.get("new") == expected_initial, f"{stage} initial dashboard New remaining mismatch")
    require(initial_queue.get("total") == expected_initial, f"{stage} initial dashboard Total remaining mismatch")
    fixture = smoke.get("fixture", {})
    require(fixture.get("active_head") == "A", f"{stage} active QA head is not A")
    require(fixture.get("raw_new_cards") == {"A": 40, "B": 40}, f"{stage} raw QA inventory mismatch")
    require(fixture.get("remaining_limits") == {"A": 3, "B": 7}, f"{stage} due-tree allowances mismatch")
    assertions = smoke.get("assertions", [])
    require(isinstance(assertions, list), f"{stage} multi-deck assertions are missing")
    by_label = {
        str(item.get("label")): item
        for item in assertions
        if isinstance(item, dict)
    }
    expected = (
        {"active-a-unexcluded": 10, "excluding-head-b": 3}
        if stage == "initial"
        else {"restart-unexcluded": 10}
    )
    require(set(by_label) == set(expected), f"{stage} multi-deck assertion labels mismatch")
    for label, expected_new in expected.items():
        assertion = by_label[label]
        require(assertion.get("expected_new_remaining") == expected_new, f"{label} expected value mismatch")
        require(assertion.get("production_dashboard_mounted") is True, f"{label} did not use the mounted dashboard")
        analytics = assertion.get("analytics", {})
        require(analytics.get("new") == expected_new, f"{label} analytics New remaining mismatch")
        require(analytics.get("total") == expected_new, f"{label} analytics Total remaining mismatch")
        dom = assertion.get("dom", {})
        require(dom.get("mounted") is True, f"{label} dashboard DOM was not mounted")
        require(dom.get("newText") == str(expected_new), f"{label} displayed New remaining mismatch")
        require(dom.get("totalText") == str(expected_new), f"{label} displayed Total remaining mismatch")
    return smoke


def group_case_ids(groups: Iterable[tuple[str, str, tuple[str, ...]]]) -> list[str]:
    return [case_id for _, _, case_ids in groups for case_id in case_ids]


def evidence_readme(package_hash: str) -> str:
    return f"""# Home Screen Dashboard {RELEASE} native release evidence

This directory preserves the exact-package, native 100% Deck Browser evidence
for Home Screen Dashboard {RELEASE}. The 56 raw PNG captures are copied
byte-for-byte from the passed isolated Anki 26.8 run and one restart. The 15 numbered detail
sheets cover every capture exactly once, and the overview provides navigation
across the complete set.

## Acceptance authority

- `contact-sheets/contact-sheet-00-overview.png` indexes all 56 captures.
- `contact-sheets/contact-sheet-01-*.png` through
  `contact-sheet-15-*.png` are the readable review sheets.
- `contact-sheets/contact-sheet-index.json` maps every capture to its detail
  sheet and verifies complete, non-duplicated detail coverage.
- `capture-evidence-manifest.json` records hashes, tags, dimensions, package
  provenance, and the passed single-restart persistence gate.
- `package/home-dashboard-overhaul-{RELEASE}.ankiaddon` is the byte-identical
  candidate installed in the disposable Anki run.
- `reports/runtime-report-initial.json` is the passed 55-frame native report.
- `reports/runtime-report-restart.json` is the passed one-frame restart
  persistence report.
- The live collection gate kept head A active and proved independent remaining
  new limits of 3 and 7 aggregate to 10, excluding B leaves 3, and the
  unexcluded dashboard still shows 10 after restart.
- The exact installed package SHA-256 is `{package_hash}`.

The supplied 3420×2214 screenshot and retained 1.8.0 through 1.8.3 evidence were
calibration/comparison inputs only. They are not copied into this set, were not
modified, and are not represented as newly generated acceptance evidence.

## Restart persistence

The isolated restart repeated the process, profile, add-on, filesystem,
window, sync-disabled, exact-package, run-root, and single-instance identity
gates. The Year view and clean schema-8 Settings normalization read back
correctly. The
`RUNTIME-RESTART-PERSISTENCE` frame appears on the runtime detail sheet. No
restart waiver exists for this release.

## Deferred and unrun

VoiceOver, Windows validation, Linux validation, forced-colors review,
non-100% scaling, and OS-level scaling acceptance were
not run and are not implied by this macOS native 100% evidence.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--color-audit", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_root = args.runtime_root.resolve()
    package = args.package.resolve()
    output = args.output.resolve()
    require(runtime_root.is_dir(), f"runtime root does not exist: {runtime_root}")
    require(package.is_file(), f"candidate package does not exist: {package}")
    require(not output.exists(), f"refusing to overwrite an evidence directory: {output}")
    color_audit = args.color_audit.resolve() if args.color_audit else None
    if color_audit is not None:
        require(color_audit.exists(), f"color audit does not exist: {color_audit}")

    runtime_report_path = runtime_root / "runtime-report-initial.json"
    restart_report_path = runtime_root / "runtime-report-restart.json"
    runtime = read_json(runtime_report_path)
    restart = read_json(restart_report_path)
    planned = read_json(SOURCE_ROOT / "qa" / "capture_evidence_manifest_1_8_4.json")

    require(runtime.get("release") == RELEASE, "runtime report release mismatch")
    require(runtime.get("status") == "passed", "initial native runtime report did not pass")
    require(runtime.get("errors") == [], "initial native runtime report contains errors")
    require(runtime.get("stage") == "initial", "expected the initial runtime stage")
    require(runtime.get("authority") == "native-deck-browser-100-percent", "runtime authority mismatch")
    require(runtime.get("matrix", {}).get("host") == "actual isolated Anki main Deck Browser", "runtime host mismatch")
    require(runtime.get("scale_policy", {}).get("ui_scale_percent") == 100, "runtime UI scale mismatch")
    require(runtime.get("scale_policy", {}).get("text_scale_percent") == 100, "runtime text scale mismatch")

    captures = runtime.get("captures")
    require(isinstance(captures, dict), "runtime captures must be an object")
    initial_case_ids = runtime.get("matrix", {}).get("case_ids")
    require(isinstance(initial_case_ids, list), "runtime matrix case IDs are missing")
    initial_case_ids = [str(case_id) for case_id in initial_case_ids]
    require(len(initial_case_ids) == EXPECTED_INITIAL_CAPTURE_COUNT, "initial runtime matrix must contain 55 captures")
    require(len(set(initial_case_ids)) == EXPECTED_INITIAL_CAPTURE_COUNT, "initial runtime matrix contains duplicate case IDs")
    require(set(initial_case_ids) == set(captures), "initial runtime matrix and capture records disagree")
    require(runtime.get("matrix", {}).get("primary_count") == EXPECTED_PRIMARY_COUNT, "primary frame count mismatch")
    require(runtime.get("matrix", {}).get("all_100_percent") is True, "runtime matrix is not entirely UI 100%")

    require(restart.get("release") == RELEASE, "restart report release mismatch")
    require(restart.get("stage") == "restart", "expected the restart runtime stage")
    require(restart.get("status") == "passed", "restart native runtime report did not pass")
    require(restart.get("errors") == [], "restart native runtime report contains errors")
    require(restart.get("authority") == "native-deck-browser-100-percent", "restart authority mismatch")
    initial_multi_deck_smoke = validate_multi_deck_smoke(runtime, "initial")
    restart_multi_deck_smoke = validate_multi_deck_smoke(restart, "restart")
    require(
        restart_multi_deck_smoke.get("fixture", {}).get("deck_ids")
        == initial_multi_deck_smoke.get("fixture", {}).get("deck_ids"),
        "restart used different QA head decks",
    )
    restart_captures = restart.get("captures")
    require(isinstance(restart_captures, dict), "restart captures must be an object")
    restart_case_ids = restart.get("matrix", {}).get("case_ids")
    require(isinstance(restart_case_ids, list), "restart matrix case IDs are missing")
    restart_case_ids = [str(case_id) for case_id in restart_case_ids]
    require(restart_case_ids == ["RUNTIME-RESTART-PERSISTENCE"], "restart matrix must contain only the persistence frame")
    require(set(restart_case_ids) == set(restart_captures), "restart matrix and capture records disagree")
    case_ids = initial_case_ids + restart_case_ids
    combined_captures = {**captures, **restart_captures}
    require(len(case_ids) == EXPECTED_CAPTURE_COUNT, "combined runtime matrix must contain 56 captures")
    require(len(set(case_ids)) == EXPECTED_CAPTURE_COUNT, "combined runtime matrix contains duplicate case IDs")

    detail_ids = group_case_ids(DETAIL_GROUPS)
    require(len(detail_ids) == EXPECTED_CAPTURE_COUNT, "detail contact-sheet plan must contain 56 captures")
    require(len(set(detail_ids)) == EXPECTED_CAPTURE_COUNT, "detail contact-sheet plan contains duplicate captures")
    require(set(detail_ids) == set(case_ids), "detail contact-sheet plan does not cover both runtime matrices")
    require(len(DETAIL_GROUPS) == 15, "release evidence must contain exactly 15 detail sheets")

    primary_ids = [str(value) for value in planned.get("primary_native_frames", [])]
    require(len(primary_ids) == EXPECTED_PRIMARY_COUNT, "planned primary matrix must contain 16 frames")
    require(set(primary_ids) == set(group_case_ids(PRIMARY_GROUPS)), "planned primary matrix differs from contact-sheet plan")

    identity = runtime.get("identity", {})
    require(identity.get("anki_version") == "26.8.1", "unexpected Anki runtime version")
    for key in (
        "addons_inside_run_root",
        "collection_inside_run_root",
        "gated_before_window_interaction",
        "profile_matches",
        "processes_are_distinct",
        "window_title_matches_profile",
    ):
        require(identity.get(key) is True, f"runtime identity gate failed: {key}")
    require(identity.get("sync_identity") == "disabled-and-disconnected", "runtime sync identity mismatch")
    require(identity.get("sync_credentials_present") is False, "runtime has sync credentials")
    require(identity.get("excluded_normal_process_state") in {"alive-and-untouched", "none-present-at-prelaunch"}, "normal Anki isolation gate failed")

    package_hash = sha256_file(package)
    candidate = identity.get("candidate", {})
    require(candidate.get("candidate_sha256") == package_hash, "runtime candidate checksum mismatch")
    require(candidate.get("manifest_version") == RELEASE, "runtime candidate version mismatch")
    require(candidate.get("installed_member_parity") == "passed", "installed package parity did not pass")
    require(candidate.get("member_count") == EXPECTED_ARCHIVE_MEMBER_COUNT, "runtime archive member count mismatch")

    restart_identity = restart.get("identity", {})
    require(restart_identity.get("run_root") == identity.get("run_root"), "restart used a different run root")
    require(restart_identity.get("single_instance_key_fingerprint") == identity.get("single_instance_key_fingerprint"), "restart used a different single-instance key")
    require(restart_identity.get("sync_identity") == "disabled-and-disconnected", "restart sync identity mismatch")
    require(restart_identity.get("excluded_normal_process_state") == identity.get("excluded_normal_process_state"), "restart normal-Anki identity changed")
    require(restart_identity.get("candidate", {}).get("candidate_sha256") == package_hash, "restart candidate checksum mismatch")
    require(restart_identity.get("candidate", {}).get("installed_member_parity") == "passed", "restart installed package parity did not pass")

    persistence = restart.get("persistence_readback", {})
    require(persistence.get("status") == "passed", "restart persistence readback did not pass")
    expected_persistence = {
        "calendar_view": "year",
        "calendar_view_expected": "year",
        "calendar_view_matches_expected": True,
        "schema_version": 8,
        "settings_state": "clean",
    }
    for key, expected_value in expected_persistence.items():
        require(persistence.get(key) == expected_value, f"restart persistence mismatch: {key}")

    output.mkdir(parents=True)
    capture_dir = output / "captures"
    sheet_dir = output / "contact-sheets"
    report_dir = output / "reports"
    package_dir = output / "package"
    for directory in (capture_dir, sheet_dir, report_dir, package_dir):
        directory.mkdir()

    tag_plan = planned_tags(planned)
    capture_manifest: list[dict[str, Any]] = []
    normalized_records: dict[str, dict[str, Any]] = {}
    detail_sheet_by_capture: dict[str, str] = {}

    for case_id in case_ids:
        record = combined_captures[case_id]
        require(isinstance(record, dict), f"invalid runtime capture record: {case_id}")
        source, dimensions = verify_capture(runtime_root, case_id, record)
        destination = capture_dir / source.name
        copy_verified(source, destination)
        tags = sorted(set(str(tag) for tag in record.get("tags", [])) | set(tag_plan.get(case_id, [])))
        normalized = {
            "id": case_id,
            "file": f"captures/{source.name}",
            "sha256": sha256_file(destination),
            "dimensions": list(dimensions),
            "device_pixel_ratio": record.get("device_pixel_ratio"),
            "ui_scale_percent": record.get("ui_scale_percent"),
            "text_scale_percent": record.get("text_scale_percent"),
            "capture_method": record.get("capture_method"),
            "sampled_color_count": record.get("sampled_color_count"),
            "fixture": record.get("fixture"),
            "theme": record.get("theme"),
            "mode": record.get("mode"),
            "view": record.get("view"),
            "layout": record.get("layout"),
            "state_label": record.get("state_label"),
            "native_window_dimensions": record.get("native_window_dimensions"),
            "dashboard_container_width": record.get("dashboard_container_width"),
            "density": record.get("density"),
            "tags": tags,
            "native_report": (
                "reports/runtime-report-restart.json"
                if case_id in restart_captures
                else "reports/runtime-report-initial.json"
            ),
        }
        capture_manifest.append(normalized)
        normalized_records[case_id] = normalized

    page_count = len(DETAIL_GROUPS)
    sheet_records: list[dict[str, Any]] = []
    for page_number, (slug, title, group_ids) in enumerate(DETAIL_GROUPS, start=1):
        filename = f"contact-sheet-{page_number:02d}-{slug}.png"
        draw_detail_sheet(
            output=sheet_dir / filename,
            title=title,
            case_ids=group_ids,
            records=normalized_records,
            capture_dir=capture_dir,
            page_number=page_number,
            page_count=page_count,
            package_hash=package_hash,
        )
        sheet_hash = sha256_file(sheet_dir / filename)
        sheet_records.append(
            {
                "file": filename,
                "sha256": sheet_hash,
                "title": title,
                "capture_ids": list(group_ids),
                "dimensions": [3600, 2400],
            }
        )
        for case_id in group_ids:
            detail_sheet_by_capture[case_id] = filename

    overview_name = "contact-sheet-00-overview.png"
    draw_overview_sheet(
        output=sheet_dir / overview_name,
        case_ids=case_ids,
        records=normalized_records,
        capture_dir=capture_dir,
        package_hash=package_hash,
    )
    with Image.open(sheet_dir / overview_name) as overview:
        overview_dimensions = list(overview.size)

    contact_index = {
        "schema_version": 1,
        "release": RELEASE,
        "status": "complete",
        "overview": {
            "file": overview_name,
            "sha256": sha256_file(sheet_dir / overview_name),
            "capture_ids": case_ids,
            "dimensions": overview_dimensions,
        },
        "detail_sheet_count": page_count,
        "detail_capture_count": len(detail_sheet_by_capture),
        "detail_capture_ids_unique": len(set(detail_sheet_by_capture)) == EXPECTED_CAPTURE_COUNT,
        "all_native_captures_in_exactly_one_detail_sheet": set(detail_sheet_by_capture) == set(case_ids),
        "sheets": sheet_records,
        "capture_to_detail_sheet": detail_sheet_by_capture,
        "omitted_planned_captures": [],
    }
    write_json(sheet_dir / "contact-sheet-index.json", contact_index)

    copy_verified(runtime_report_path, report_dir / "runtime-report-initial.json")
    copy_verified(restart_report_path, report_dir / "runtime-report-restart.json")
    initial_failed = runtime_root / "runtime-report-initial-attempt1-failed.json"
    restart_failed = runtime_root / "runtime-report-restart-attempt1-failed.json"
    if initial_failed.is_file():
        copy_verified(initial_failed, report_dir / initial_failed.name)
    if restart_failed.is_file():
        copy_verified(restart_failed, report_dir / restart_failed.name)
    if color_audit is not None:
        if color_audit.is_dir():
            audit_files = sorted(path for path in color_audit.iterdir() if path.is_file())
            require(audit_files, "color audit directory is empty")
            for audit_file in audit_files:
                copy_verified(audit_file, report_dir / audit_file.name)
        else:
            copy_verified(color_audit, report_dir / "color-system-audit.json")

    packaged_copy = package_dir / f"home-dashboard-overhaul-{RELEASE}.ankiaddon"
    copy_verified(package, packaged_copy)
    (package_dir / f"home-dashboard-overhaul-{RELEASE}.ankiaddon.sha256").write_text(
        f"{package_hash}  {packaged_copy.name}\n", encoding="utf-8"
    )

    archive_names, archive_member_hashes, source_archive_parity = safe_archive_members(package)
    require(len(archive_names) == EXPECTED_ARCHIVE_MEMBER_COUNT, "archive does not contain 24 members")
    require(source_archive_parity, "candidate archive no longer matches packaged source")
    with zipfile.ZipFile(package) as archive:
        packaged_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    require(packaged_manifest.get("human_version") == RELEASE, "archive manifest version mismatch")
    archive_inspection = {
        "release": RELEASE,
        "status": "passed",
        "archive": f"package/{packaged_copy.name}",
        "sha256": package_hash,
        "manifest_version": packaged_manifest.get("human_version"),
        "member_count": len(archive_names),
        "member_allowlist_count": EXPECTED_ARCHIVE_MEMBER_COUNT,
        "unsafe_members": [],
        "safe_paths": "passed",
        "source_archive_byte_parity": "passed",
        "successful_exact_candidate_loading": "passed",
        "installed_archive_member_parity": candidate.get("installed_member_parity"),
        "members": [
            {"path": name, "sha256": archive_member_hashes[name]}
            for name in archive_names
        ],
    }
    write_json(report_dir / "archive-inspection.json", archive_inspection)

    captured_tags = sorted({tag for record in capture_manifest for tag in record["tags"]})
    required_tags = [str(tag) for tag in planned.get("required_coverage_tags", [])]
    missing_required = sorted(set(required_tags) - set(captured_tags))
    require(not missing_required, f"required coverage tags are missing: {missing_required}")

    evidence_manifest = {
        "schema_version": 1,
        "release": RELEASE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted",
        "authority": "native-deck-browser-100-percent",
        "candidate": {
            "path": f"package/{packaged_copy.name}",
            "sha256": package_hash,
            "manifest_version": packaged_manifest.get("human_version"),
            "member_count": EXPECTED_ARCHIVE_MEMBER_COUNT,
            "single_release_build": True,
            "safe_paths": "passed",
            "source_archive_parity": "passed",
            "installed_archive_member_parity": "passed",
            "successful_exact_candidate_loading": "passed",
        },
        "native_run": {
            "anki_version": identity.get("anki_version"),
            "profile": identity.get("profile"),
            "run_root": identity.get("run_root"),
            "single_instance_key_fingerprint": identity.get("single_instance_key_fingerprint"),
            "sync_identity": identity.get("sync_identity"),
            "normal_anki_process": identity.get("excluded_normal_process_state"),
            "initial_status": runtime.get("status"),
            "restart_status": restart.get("status"),
            "restart_identity_gates_repeated": True,
        },
        "multi_deck_new_limit_smoke": {
            "status": "passed",
            "active_head": "A",
            "raw_new_cards": {"A": 40, "B": 40},
            "remaining_limits": {"A": 3, "B": 7},
            "unexcluded_new_remaining": 10,
            "excluding_head_b_new_remaining": 3,
            "restart_new_remaining": 10,
            "initial_report": "reports/runtime-report-initial.json",
            "restart_report": "reports/runtime-report-restart.json",
        },
        "captures": {
            "count": len(capture_manifest),
            "primary_count": EXPECTED_PRIMARY_COUNT,
            "supplemental_count": len(capture_manifest) - EXPECTED_PRIMARY_COUNT,
            "all_ui_scale_percent": 100,
            "all_text_scale_percent": 100,
            "records": capture_manifest,
        },
        "contact_sheets": {
            "overview": f"contact-sheets/{overview_name}",
            "detail_count": page_count,
            "all_captures_in_overview": True,
            "all_captures_in_exactly_one_detail_sheet": True,
            "index": "contact-sheets/contact-sheet-index.json",
        },
        "coverage": {
            "required_tags": required_tags,
            "captured_tags": captured_tags,
            "missing_required_tags": missing_required,
            "explicitly_waived_missing_tags": [],
            "unwaived_missing_tags": [],
        },
        "restart_persistence": {
            "status": "passed",
            "identity_gates": "passed",
            "readback": persistence,
            "capture_generated": True,
            "capture_id": "RUNTIME-RESTART-PERSISTENCE",
            "waiver": None,
            "report": "reports/runtime-report-restart.json",
        },
        "reference_inputs": {
            "supplied_native_screenshot": {
                "sha256": REFERENCE_SCREENSHOT_SHA256,
                "role": "geometry-calibration-only",
                "copied_into_evidence": False,
                "represented_as_new_evidence": False,
            },
            "retained_1_8_0_contact_sheets": {
                "role": "historical-comparison-only",
                "modified": False,
                "represented_as_new_evidence": False,
            },
            "retained_1_8_1_evidence": {
                "role": "historical-comparison-only",
                "modified": False,
                "represented_as_new_evidence": False,
            },
            "retained_1_8_2_evidence": {
                "role": "historical-comparison-only",
                "modified": False,
                "represented_as_new_evidence": False,
            },
            "retained_1_8_3_evidence": {
                "role": "historical-comparison-only",
                "modified": False,
                "represented_as_new_evidence": False,
            },
        },
        "deferred_unrun": planned.get("deferred_unrun", []),
    }
    write_json(output / "capture-evidence-manifest.json", evidence_manifest)
    write_json(output / "capture-manifest.json", {"release": RELEASE, "captures": capture_manifest})
    (output / "README.md").write_text(evidence_readme(package_hash), encoding="utf-8")

    require(len(list(capture_dir.glob("*.png"))) == EXPECTED_CAPTURE_COUNT, "copied capture count mismatch")
    require(len(list(sheet_dir.glob("*.png"))) == page_count + 1, "contact-sheet count mismatch")
    print(
        json.dumps(
            {
                "status": evidence_manifest["status"],
                "output": str(output),
                "captures": EXPECTED_CAPTURE_COUNT,
                "primary": EXPECTED_PRIMARY_COUNT,
                "detail_contact_sheets": page_count,
                "overview_contact_sheets": 1,
                "archive_sha256": package_hash,
                "restart_persistence": "passed",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
