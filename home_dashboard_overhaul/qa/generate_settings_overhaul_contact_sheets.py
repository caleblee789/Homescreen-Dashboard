"""Archive exact-package Settings evidence and build native-scale contact sheets."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from PIL import Image, ImageDraw, ImageFont


SHEETS = (
    (
        "01-dashboard-wide-100-percent.png",
        "Dashboard settings · wide rail and persistent preview",
        1,
        (
            ("wide-dashboard-appearance.png", "Appearance"),
            ("wide-dashboard-content-metrics.png", "Content & study metrics"),
            ("wide-dashboard-calendar.png", "Calendar"),
        ),
    ),
    (
        "02-four-pages-intermediate-100-percent.png",
        "All four Settings pages · intermediate tabs",
        2,
        (
            ("intermediate-dashboard.png", "Dashboard"),
            ("intermediate-events-empty.png", "Events · intentional empty state"),
            ("intermediate-bible.png", "Bible verse"),
            ("intermediate-about-support.png", "About & support"),
        ),
    ),
    (
        "03-narrow-responsive-100-percent.png",
        "Narrow Settings · selector, cards, and 150% font",
        2,
        (
            ("narrow-dashboard.png", "Dashboard"),
            ("narrow-events-empty.png", "Events · empty"),
            ("narrow-events-populated.png", "Events · populated cards"),
            ("narrow-bible.png", "Bible verse"),
            ("narrow-about-support.png", "About & support"),
            ("intermediate-dashboard-150-percent-font.png", "Dashboard · 150% application font"),
        ),
    ),
    (
        "04-bible-focused-preview-100-percent.png",
        "Bible verse settings · focused wide preview",
        1,
        (("wide-bible.png", "Bible verse · only the selected verse card is previewed"),),
    ),
    (
        "05-save-and-restart-100-percent.png",
        "Staged changes, save confirmation, and restart persistence",
        2,
        (
            ("narrow-dashboard-dirty.png", "Dirty · Discard changes + Save changes"),
            ("narrow-dashboard-saved.png", "Saved · dialog remains open"),
            ("restart-dashboard-calendar-route.png", "Restart · legacy Calendar route → Dashboard"),
            ("isolated-main-window-initial-rendered.png", "Disposable Anki · initial rendered dashboard"),
            ("isolated-main-window-restart-rendered.png", "Disposable Anki · controlled restart"),
        ),
    ),
    (
        "06-main-window-full-screen-100-percent.png",
        "Rendered Anki home dashboard · Month and Year in true full-screen",
        1,
        (
            (
                "isolated-main-window-initial-full-screen-month-rendered.png",
                "Initial dashboard · Month · true full-screen",
            ),
            (
                "isolated-main-window-restart-full-screen-year-rendered.png",
                "Restarted dashboard · Year · true full-screen",
            ),
        ),
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "/System/Library/Fonts/SFNS.ttf",
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


def render_sheet(
    raw_root: Path,
    destination: Path,
    title: str,
    columns: int,
    entries: tuple[tuple[str, str], ...],
) -> dict[str, Any]:
    margin = 48
    gutter = 48
    heading_height = 136
    caption_height = 62
    frame_padding = 14
    opened: list[tuple[str, str, Image.Image]] = []
    for filename, caption in entries:
        opened.append((filename, caption, Image.open(raw_root / filename).convert("RGB")))

    cell_width = max(image.width for _, _, image in opened) + (2 * frame_padding)
    rows = (len(opened) + columns - 1) // columns
    row_heights: list[int] = []
    for row in range(rows):
        row_images = opened[row * columns : (row + 1) * columns]
        row_heights.append(
            caption_height
            + max(image.height for _, _, image in row_images)
            + (2 * frame_padding)
        )

    width = (2 * margin) + (columns * cell_width) + ((columns - 1) * gutter)
    height = (
        (2 * margin)
        + heading_height
        + sum(row_heights)
        + (max(0, rows - 1) * gutter)
    )
    canvas = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, margin), title, fill="#f8fafc", font=font(42, bold=True))
    draw.text(
        (margin, margin + 58),
        "Native source pixels · 100% scale · no screenshot downsampling",
        fill="#94a3b8",
        font=font(25),
    )

    placements: list[dict[str, Any]] = []
    y = margin + heading_height
    for row in range(rows):
        row_entries = opened[row * columns : (row + 1) * columns]
        row_height = row_heights[row]
        for column, (filename, caption, source) in enumerate(row_entries):
            x = margin + column * (cell_width + gutter)
            draw.rounded_rectangle(
                (x, y, x + cell_width, y + row_height),
                radius=18,
                fill="#e5e7eb",
                outline="#64748b",
                width=3,
            )
            draw.text(
                (x + frame_padding, y + 12),
                caption,
                fill="#172033",
                font=font(27, bold=True),
            )
            image_x = x + (cell_width - source.width) // 2
            image_y = y + caption_height + frame_padding
            canvas.paste(source, (image_x, image_y))
            placements.append(
                {
                    "label": caption,
                    "source": "raw-captures/{}".format(filename),
                    "source_dimensions": [source.width, source.height],
                    "image_bounds": [
                        image_x,
                        image_y,
                        image_x + source.width,
                        image_y + source.height,
                    ],
                    "scale": 1.0,
                }
            )
        y += row_height + gutter

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, "PNG", optimize=True)
    for _, _, source in opened:
        source.close()
    return {
        "title": title,
        "file": "contact-sheets/{}".format(destination.name),
        "width": width,
        "height": height,
        "sha256": sha256_file(destination),
        "placements": placements,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    package = args.package.resolve()
    if output.exists():
        raise SystemExit("refusing to overwrite existing output: {}".format(output))
    output.mkdir(parents=True)
    raw_root = output / "raw-captures"
    reports_root = output / "runtime-reports"
    package_root = output / "package"
    raw_root.mkdir()
    reports_root.mkdir()
    package_root.mkdir()

    requested_images = sorted(
        {filename for _, _, _, entries in SHEETS for filename, _ in entries}
    )
    for filename in requested_images:
        path = source / filename
        if not path.is_file():
            raise SystemExit("missing capture: {}".format(path))
        shutil.copy2(path, raw_root / filename)

    initial_path = source / "runtime-report-initial.json"
    restart_path = source / "runtime-report-restart.json"
    initial = json.loads(initial_path.read_text(encoding="utf-8"))
    restart = json.loads(restart_path.read_text(encoding="utf-8"))
    if initial.get("status") != "passed" or restart.get("status") != "passed":
        raise SystemExit("runtime reports must both pass")
    shutil.copy2(initial_path, reports_root / initial_path.name)
    shutil.copy2(restart_path, reports_root / restart_path.name)
    package_copy = package_root / package.name
    shutil.copy2(package, package_copy)
    checksum_path = package.with_suffix(package.suffix + ".sha256")
    if checksum_path.is_file():
        shutil.copy2(checksum_path, package_root / checksum_path.name)

    capture_meta: dict[str, Any] = {}
    for report in (initial, restart):
        for name, metadata in report.get("captures", {}).items():
            capture_meta["{}.png".format(name)] = metadata

    captures: list[dict[str, Any]] = []
    for filename in requested_images:
        path = raw_root / filename
        with Image.open(path) as image:
            dimensions = [image.width, image.height]
        metadata = capture_meta.get(filename, {})
        captures.append(
            {
                "file": "raw-captures/{}".format(filename),
                "dimensions": dimensions,
                "device_pixel_ratio": metadata.get("device_pixel_ratio"),
                "sha256": sha256_file(path),
            }
        )

    sheet_records = [
        render_sheet(raw_root, output / "contact-sheets" / filename, title, columns, entries)
        for filename, title, columns, entries in SHEETS
    ]
    manifest = {
        "schema_version": 1,
        "release": "1.8.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "Four-page Settings overhaul at native 100% screenshot scale",
        "candidate": {
            "file": "package/{}".format(package_copy.name),
            "sha256": sha256_file(package_copy),
        },
        "anki": {
            "version": "26.08.1",
            "profile": initial.get("identity", {}).get("profile"),
            "collection_inside_disposable_run": initial.get("identity", {}).get(
                "collection_inside_run_root"
            ),
            "sync_auth_present": initial.get("identity", {}).get("sync_auth_present"),
        },
        "runtime_reports": [
            {
                "file": "runtime-reports/runtime-report-initial.json",
                "status": initial.get("status"),
                "sha256": sha256_file(reports_root / "runtime-report-initial.json"),
            },
            {
                "file": "runtime-reports/runtime-report-restart.json",
                "status": restart.get("status"),
                "sha256": sha256_file(reports_root / "runtime-report-restart.json"),
            },
        ],
        "persistence": {
            "previous_status": restart.get("previous_status"),
            "expected": restart.get("expected_restart"),
            "actual": restart.get("actual_restart"),
        },
        "captures": captures,
        "sheets": sheet_records,
        "boundary": (
            "Automated and visually inspected native macOS evidence. "
            "Spoken VoiceOver, Windows/Linux, DPR 1, and OS forced-colors remain separate acceptance gates."
        ),
    }
    manifest_path = output / "capture-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    print("captures {}".format(len(captures)))
    print("sheets {}".format(len(sheet_records)))
    print("candidate_sha256 {}".format(manifest["candidate"]["sha256"]))


if __name__ == "__main__":
    main()
