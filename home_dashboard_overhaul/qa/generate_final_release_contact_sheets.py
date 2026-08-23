"""Capture and assemble the final Home Dashboard 1.7.0 contact sheets.

The renderer matrix is restricted to the canonical 100% text-scale cases.
Native Anki captures are copied from an already verified exact-package run.
Every detail sheet preserves source screenshots at a 1:1 pixel scale.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Iterable
from urllib.parse import urlencode

from PIL import Image, ImageDraw, ImageFont


THEME_ORDER = ("Sapphire Glass", "Graphite", "Emerald", "High Contrast")
THEME_SLUGS = {
    "Sapphire Glass": "sapphire-glass",
    "Graphite": "graphite",
    "Emerald": "emerald",
    "High Contrast": "high-contrast",
}
LAYOUT_DIMENSIONS = {
    "compact": (560, 900),
    "wide": (1440, 900),
}
NATIVE_FULLSCREEN_SOURCES = (
    (
        "isolated-main-window-year-maximized.png",
        "exact-package-full-screen-month.png",
        "Month · exact package · full-screen dashboard",
        "month",
    ),
    (
        "isolated-main-window-month-maximized.png",
        "exact-package-full-screen-year.png",
        "Year · exact package · full-screen dashboard",
        "year",
    ),
)
NATIVE_SETTINGS_SOURCES = (
    ("settings-wide-calendar.png", "Calendar settings · wide"),
    ("settings-wide-bible-custom.png", "Bible verse settings · wide"),
    ("settings-medium-preview.png", "Settings · intermediate"),
    ("settings-narrow.png", "Settings · narrow"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "/System/Library/Fonts/SFNS.ttf",
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


def image_dimensions(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        image.load()
        return image.width, image.height


def validate_nonblank(path: Path) -> None:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        extrema = rgb.getextrema()
    if all(low == high for low, high in extrema):
        raise RuntimeError(f"capture is blank: {path}")


def renderer_cases(matrix_path: Path) -> list[dict[str, Any]]:
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    cases = [case for case in matrix.get("cases", []) if case.get("text_scale") == 100]
    if len(cases) != 32:
        raise RuntimeError(f"expected 32 canonical 100% cases, found {len(cases)}")
    if len({case.get("id") for case in cases}) != len(cases):
        raise RuntimeError("100% visual-regression case IDs must be unique")
    invalid = [case.get("id") for case in cases if not str(case.get("id", "")).endswith("-100")]
    if invalid:
        raise RuntimeError(f"non-100% cases escaped the filter: {invalid}")
    return cases


def capture_renderer_case(
    *,
    chrome: Path,
    profile: Path,
    base_url: str,
    case: dict[str, Any],
    destination: Path,
) -> dict[str, Any]:
    layout = str(case["layout"])
    expected = LAYOUT_DIMENSIONS[layout]
    query = urlencode(
        {
            "theme": case["theme"],
            "mode": case["mode"],
            "view": case["view"],
            "scale": "100",
        }
    )
    url = f"{base_url.rstrip('/')}/?{query}"
    command = [
        str(chrome),
        "--headless=new",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-features=MediaRouter,OptimizationHints,Translate",
        "--disable-gpu",
        "--force-device-scale-factor=1",
        "--hide-scrollbars",
        "--no-default-browser-check",
        "--no-first-run",
        f"--user-data-dir={profile}",
        "--virtual-time-budget=750",
        f"--window-size={expected[0]},{expected[1]}",
        f"--screenshot={destination}",
        url,
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 30
    last_size = -1
    stable_ticks = 0
    capture_ready = False
    while time.monotonic() < deadline:
        if destination.is_file():
            current_size = destination.stat().st_size
            stable_ticks = stable_ticks + 1 if current_size > 0 and current_size == last_size else 0
            last_size = current_size
            if stable_ticks >= 2:
                try:
                    image_dimensions(destination)
                    validate_nonblank(destination)
                except (OSError, RuntimeError):
                    pass
                else:
                    capture_ready = True
                    break
        if process.poll() is not None:
            break
        time.sleep(0.1)

    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    stdout, stderr = process.communicate()
    if not capture_ready and destination.is_file():
        try:
            image_dimensions(destination)
            validate_nonblank(destination)
        except (OSError, RuntimeError):
            pass
        else:
            capture_ready = True
    if not capture_ready:
        detail = (stderr or stdout).strip()
        raise RuntimeError(f"Chrome capture failed for {case['id']}: {detail}")
    dimensions = image_dimensions(destination)
    if dimensions != expected:
        raise RuntimeError(
            f"{case['id']} dimensions {dimensions} do not match requested {expected}"
        )
    validate_nonblank(destination)
    return {
        "id": case["id"],
        "file": f"captures/{destination.name}",
        "theme": case["theme"],
        "mode": case["mode"],
        "view": case["view"],
        "layout": layout,
        "text_scale_percent": 100,
        "browser_zoom_percent": 100,
        "device_scale_factor": 1,
        "dimensions": list(dimensions),
        "sha256": sha256_file(destination),
        "url": url,
    }


def paint_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str, margin: int) -> None:
    draw.text((margin, margin), title, fill="#f8fafc", font=font(42, bold=True))
    draw.text((margin, margin + 58), subtitle, fill="#a8b4c7", font=font(24))


def render_theme_sheet(
    *, output: Path, captures: Path, theme: str, cases: list[dict[str, Any]]
) -> dict[str, Any]:
    margin = 48
    gutter = 48
    row_gutter = 42
    heading_height = 144
    caption_height = 58
    frame_padding = 14
    column_widths = (560 + 2 * frame_padding, 1440 + 2 * frame_padding)
    row_height = caption_height + 900 + 2 * frame_padding
    rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for mode in ("light", "dark"):
        for view in ("month", "year"):
            matching = [
                case
                for case in cases
                if case["theme"] == theme and case["mode"] == mode and case["view"] == view
            ]
            by_layout = {case["layout"]: case for case in matching}
            if set(by_layout) != {"compact", "wide"}:
                raise RuntimeError(f"incomplete 100% row for {theme} {mode} {view}")
            rows.append((by_layout["compact"], by_layout["wide"]))

    width = 2 * margin + sum(column_widths) + gutter
    height = 2 * margin + heading_height + len(rows) * row_height + (len(rows) - 1) * row_gutter
    canvas = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(canvas)
    paint_header(
        draw,
        f"Home Dashboard 1.7.0 · {theme}",
        "Month and Year · light and dark · 100% only · native source pixels",
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
                radius=16,
                fill="#e5e7eb",
                outline="#64748b",
                width=3,
            )
            caption = (
                f"{case['mode'].title()} · {case['view'].title()} · "
                f"{case['layout']} · 100%"
            )
            draw.text((x + frame_padding, y + 12), caption, fill="#172033", font=font(25, bold=True))
            source_path = captures / f"{case['id']}.png"
            with Image.open(source_path) as source_image:
                source = source_image.convert("RGB")
                image_x = x + frame_padding
                image_y = y + caption_height + frame_padding
                canvas.paste(source, (image_x, image_y))
                placements.append(
                    {
                        "case_id": case["id"],
                        "source": f"captures/{source_path.name}",
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
            x += cell_width + gutter
        y += row_height + row_gutter
    destination = output / "contact-sheets" / (
        f"0{THEME_ORDER.index(theme) + 1}-dashboard-{THEME_SLUGS[theme]}-100-percent.png"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, "PNG", optimize=True)
    return {
        "title": f"Home Dashboard 1.7.0 · {theme}",
        "file": f"contact-sheets/{destination.name}",
        "dimensions": [width, height],
        "sha256": sha256_file(destination),
        "source_scale": 1.0,
        "placements": placements,
    }


def render_single_column_sheet(
    *,
    output: Path,
    filename: str,
    title: str,
    subtitle: str,
    entries: Iterable[tuple[Path, str, str]],
) -> dict[str, Any]:
    opened: list[tuple[Path, str, str, Image.Image]] = []
    for path, label, manifest_path in entries:
        opened.append((path, label, manifest_path, Image.open(path).convert("RGB")))
    margin = 48
    heading_height = 144
    row_gutter = 42
    caption_height = 58
    frame_padding = 14
    width = 2 * margin + max(image.width for _, _, _, image in opened) + 2 * frame_padding
    row_heights = [caption_height + image.height + 2 * frame_padding for _, _, _, image in opened]
    height = 2 * margin + heading_height + sum(row_heights) + (len(opened) - 1) * row_gutter
    canvas = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(canvas)
    paint_header(draw, title, subtitle, margin)
    placements: list[dict[str, Any]] = []
    y = margin + heading_height
    for (path, label, manifest_path, source), row_height in zip(opened, row_heights):
        cell_width = source.width + 2 * frame_padding
        x = (width - cell_width) // 2
        draw.rounded_rectangle(
            (x, y, x + cell_width, y + row_height),
            radius=16,
            fill="#e5e7eb",
            outline="#64748b",
            width=3,
        )
        draw.text((x + frame_padding, y + 12), label, fill="#172033", font=font(25, bold=True))
        image_x = x + frame_padding
        image_y = y + caption_height + frame_padding
        canvas.paste(source, (image_x, image_y))
        placements.append(
            {
                "label": label,
                "source": manifest_path,
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
        y += row_height + row_gutter
    destination = output / "contact-sheets" / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, "PNG", optimize=True)
    for _, _, _, source in opened:
        source.close()
    return {
        "title": title,
        "file": f"contact-sheets/{destination.name}",
        "dimensions": [width, height],
        "sha256": sha256_file(destination),
        "source_scale": 1.0,
        "placements": placements,
    }


def copy_native_evidence(source: Path, output: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fullscreen_root = output / "native-full-screen"
    settings_root = output / "native-settings"
    fullscreen_root.mkdir(parents=True)
    settings_root.mkdir(parents=True)
    fullscreen: list[dict[str, Any]] = []
    for source_name, output_name, label, observed_view in NATIVE_FULLSCREEN_SOURCES:
        source_path = source / source_name
        if not source_path.is_file():
            raise RuntimeError(f"missing exact-package full-screen capture: {source_path}")
        destination = fullscreen_root / output_name
        shutil.copy2(source_path, destination)
        validate_nonblank(destination)
        fullscreen.append(
            {
                "label": label,
                "observed_view": observed_view,
                "file": f"native-full-screen/{output_name}",
                "source_filename": source_name,
                "dimensions": list(image_dimensions(destination)),
                "sha256": sha256_file(destination),
                "ui_scale_percent": 100,
                "device_pixel_ratio": 2.0,
            }
        )
    settings: list[dict[str, Any]] = []
    for source_name, label in NATIVE_SETTINGS_SOURCES:
        source_path = source / source_name
        if not source_path.is_file():
            raise RuntimeError(f"missing exact-package settings capture: {source_path}")
        destination = settings_root / source_name
        shutil.copy2(source_path, destination)
        validate_nonblank(destination)
        settings.append(
            {
                "label": label,
                "file": f"native-settings/{source_name}",
                "dimensions": list(image_dimensions(destination)),
                "sha256": sha256_file(destination),
                "ui_scale_percent": 100,
                "device_pixel_ratio": 2.0,
            }
        )
    return fullscreen, settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--preview-url", default="http://127.0.0.1:8765")
    parser.add_argument("--chrome", required=True, type=Path)
    parser.add_argument("--native-captures", required=True, type=Path)
    parser.add_argument("--runtime-report", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {output}")
    if not args.chrome.is_file():
        raise SystemExit(f"Chrome executable not found: {args.chrome}")
    output.mkdir(parents=True)
    captures_root = output / "captures"
    captures_root.mkdir()
    cases = renderer_cases(args.matrix.resolve())

    records: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="hdo-contact-capture-chrome-") as profile_name:
        profile = Path(profile_name)
        for index, case in enumerate(cases, start=1):
            destination = captures_root / f"{case['id']}.png"
            records.append(
                capture_renderer_case(
                    chrome=args.chrome.resolve(),
                    profile=profile,
                    base_url=args.preview_url,
                    case=case,
                    destination=destination,
                )
            )
            print(f"renderer capture {index:02d}/{len(cases)} {case['id']}", flush=True)

    runtime = json.loads(args.runtime_report.read_text(encoding="utf-8"))
    if runtime.get("status") != "passed" or runtime.get("errors"):
        raise RuntimeError("exact-package runtime report must pass without errors")
    fullscreen, settings = copy_native_evidence(args.native_captures.resolve(), output)

    package_root = output / "package"
    package_root.mkdir()
    package_copy = package_root / args.package.name
    shutil.copy2(args.package.resolve(), package_copy)
    package_hash = sha256_file(package_copy)
    (package_root / f"{package_copy.name}.sha256").write_text(
        f"{package_hash}  {package_copy.name}\n", encoding="utf-8"
    )
    reports_root = output / "runtime-reports"
    reports_root.mkdir()
    report_copy = reports_root / "runtime-report.json"
    shutil.copy2(args.runtime_report.resolve(), report_copy)

    sheets = [
        render_theme_sheet(
            output=output,
            captures=captures_root,
            theme=theme,
            cases=cases,
        )
        for theme in THEME_ORDER
    ]
    full_screen_entries = [
        (
            output / str(record["file"]),
            str(record["label"]),
            str(record["file"]),
        )
        for record in fullscreen
    ]
    sheets.append(
        render_single_column_sheet(
            output=output,
            filename="05-exact-package-full-screen-dashboard-100-percent.png",
            title="Exact-package Home Dashboard · full screen",
            subtitle="Month and Year · native macOS pixels · application scale 100%",
            entries=full_screen_entries,
        )
    )
    settings_entries = [
        (
            output / str(record["file"]),
            str(record["label"]),
            str(record["file"]),
        )
        for record in settings
    ]
    sheets.append(
        render_single_column_sheet(
            output=output,
            filename="06-exact-package-settings-responsive-100-percent.png",
            title="Exact-package Settings · responsive layouts",
            subtitle="Wide, intermediate, and narrow · application scale 100% only",
            entries=settings_entries,
        )
    )

    manifest = {
        "schema_version": 1,
        "release": "1.7.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "Updated final-release dashboard contact sheets at 100% only",
        "scale_policy": {
            "allowed_ui_scale_percent": [100],
            "renderer_text_scale_percent": 100,
            "renderer_browser_zoom_percent": 100,
            "renderer_device_scale_factor": 1,
            "native_anki_application_scale_percent": 100,
            "native_retina_device_pixel_ratio": 2.0,
            "excluded_ui_scales_percent": [125, 150, 200],
        },
        "candidate": {
            "file": f"package/{package_copy.name}",
            "sha256": package_hash,
        },
        "renderer_matrix": {
            "source": f"../{args.matrix.name}",
            "source_sha256": sha256_file(args.matrix.resolve()),
            "capture_kind": "current production renderer in local headless Chrome",
            "case_count": len(records),
            "cases": records,
        },
        "exact_package": {
            "capture_kind": "native Qt/Anki from verified disposable sync-disabled profile",
            "runtime_report": {
                "file": "runtime-reports/runtime-report.json",
                "status": runtime.get("status"),
                "sha256": sha256_file(report_copy),
            },
            "identity": runtime.get("identity"),
            "full_screen": fullscreen,
            "settings": settings,
            "source_filename_note": (
                "The probe's two maximized source filenames reflected callback order; "
                "the normalized Month/Year names above follow the visually rendered view."
            ),
        },
        "contact_sheet_count": len(sheets),
        "contact_sheets": sheets,
        "quality_status": "clean",
        "boundary": (
            "Renderer matrix and native macOS exact-package evidence only. "
            "Spoken VoiceOver, Windows/Linux rendering, and true OS display scaling remain separate gates."
        ),
    }
    manifest_path = output / "capture-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    index = {
        "release": manifest["release"],
        "scale_percent": 100,
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
    readme_lines = [
        "# Home Dashboard 1.7.0 contact sheets — 100% only",
        "",
        f"Candidate SHA-256: `{package_hash}`",
        "",
        "All UI renders in this set use 100% application/text scale. The native macOS captures retain Retina DPR 2 physical pixels; that is pixel density, not enlarged UI scale. No 125%, 150%, or 200% UI captures are included.",
        "",
        "## Contact sheets",
        "",
    ]
    readme_lines.extend(
        f"- [{sheet['title']}]({sheet['file']})" for sheet in sheets
    )
    readme_lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- Renderer matrix: {len(records)} captures across four themes, light/dark, Month/Year, and compact/wide layouts.",
            "- Exact-package full-screen dashboard: Month and Year.",
            "- Exact-package Settings: wide, intermediate, and narrow layouts.",
            "- Every detail-sheet placement uses the source screenshot at scale `1.0`.",
            "- Runtime report status: passed with no recorded errors in a disposable sync-disabled profile.",
            "",
            "## Acceptance boundary",
            "",
            "Spoken VoiceOver, Windows/Linux rendering, and true OS display scaling remain separate acceptance gates.",
            "",
        ]
    )
    (output / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")

    print(f"output {output}")
    print(f"renderer_captures {len(records)}")
    print(f"contact_sheets {len(sheets)}")
    print(f"candidate_sha256 {package_hash}")


if __name__ == "__main__":
    main()
