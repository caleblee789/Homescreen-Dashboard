from __future__ import annotations

import argparse
import hashlib
import json
from math import ceil
from pathlib import Path
import re
from typing import Mapping

from PIL import Image, ImageDraw, ImageFont, ImageOps


STABLE_CAPTURE = re.compile(r"^(CAL|INS|SET|RST|NFS|THM|OPA)-(\d{2})\.png$")
SUITE_ORDER = {
    "CAL": 0,
    "INS": 1,
    "SET": 2,
    "RST": 3,
    "NFS": 4,
    "THM": 5,
    "OPA": 6,
}
SUPPLEMENTAL_CAPTIONS = {
    "SET-03-deck-exclusions.png": (
        "SET-03 supplement  Deck exclusions tree"
    ),
    "NFS-06-continuation.png": (
        "NFS-06 supplement  Selected date 200% continuation"
    ),
}

CATEGORY_TITLES = {
    "calendar": "Calendar",
    "selected-date-most-missed": "Selected Date and Most Missed",
    "statistics": "Statistics",
    "settings": "Settings",
    "themes": "Four-Theme Matrix",
    "opacity-backgrounds": "Opacity and Backgrounds",
    "restart-persistence": "Restart and Persistence",
}

STATISTICS_SURFACE_IDS = frozenset(
    ["CAL-{:02d}".format(value) for value in (1, 2, 3, 4, 5, 11, 12, 13, 14, 19)]
    + ["SET-{:02d}".format(value) for value in (1, 2, 9, 11, 12, 19, 20)]
    + ["THM-{:02d}".format(value) for value in range(1, 9)]
    + ["OPA-{:02d}".format(value) for value in range(1, 13)]
)


def ordered_images(directory: Path, manifest_path: Path | None = None) -> list[Path]:
    stable = {
        path.stem: path
        for path in directory.glob("*.png")
        if STABLE_CAPTURE.fullmatch(path.name)
    }
    if manifest_path is not None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = manifest.get("records")
        if not isinstance(records, list):
            raise ValueError("manifest records must be an array")
        expected = [record.get("stable_id") for record in records if isinstance(record, dict)]
        if len(expected) != len(records) or any(not isinstance(value, str) for value in expected):
            raise ValueError("every manifest record must have a stable_id")
        if len(expected) != len(set(expected)):
            raise ValueError("manifest stable IDs must be unique")
        missing = [value for value in expected if value not in stable]
        extras = sorted(set(stable) - set(expected))
        if missing or extras:
            raise ValueError(
                "stable capture set differs from manifest (missing: {}; extra: {})".format(
                    ", ".join(missing) or "none", ", ".join(extras) or "none"
                )
            )
        return [stable[value] for value in expected]
    if stable:
        return sorted(
            stable.values(),
            key=lambda path: (
                SUITE_ORDER[STABLE_CAPTURE.fullmatch(path.name).group(1)],
                int(STABLE_CAPTURE.fullmatch(path.name).group(2)),
            ),
        )
    return sorted(
        path for path in directory.glob("[0-9][0-9]-*.png")
        if "contact-sheet" not in path.name
    )


def ordered_supplemental_images(directory: Path, primary_images: list[Path]) -> list[Path]:
    """Return registered-ID supplements without treating them as primaries."""

    primary_names = {path.name for path in primary_images}
    primary_ids = {path.stem for path in primary_images}
    supplements: list[Path] = []
    for path in directory.glob("*.png"):
        if path.name in primary_names or path.name.startswith("contact-sheet-"):
            continue
        matching_id = next(
            (
                stable_id
                for stable_id in primary_ids
                if path.stem.startswith(stable_id + "-")
            ),
            None,
        )
        if matching_id is not None:
            supplements.append(path)
    return sorted(
        supplements,
        key=lambda path: (
            SUITE_ORDER.get(path.stem.split("-", 1)[0], 99),
            path.name,
        ),
    )


def categories_for(stable_id: str) -> tuple[str, ...]:
    namespace = stable_id.split("-", 1)[0]
    categories: list[str] = []
    if namespace == "CAL":
        categories.append("calendar")
    elif namespace in {"INS", "NFS"}:
        categories.append("selected-date-most-missed")
    elif namespace == "SET":
        categories.append("settings")
    elif namespace == "THM":
        categories.append("themes")
    elif namespace == "OPA":
        categories.append("opacity-backgrounds")
    elif namespace == "RST":
        categories.append("restart-persistence")
    if stable_id in STATISTICS_SURFACE_IDS:
        categories.append("statistics")
    return tuple(categories)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_captions(manifest_path: Path) -> dict[str, str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ValueError("manifest records must be an array")
    captions: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("every manifest record must be an object")
        stable_id = record.get("stable_id")
        title = record.get("title")
        if not isinstance(stable_id, str) or not STABLE_CAPTURE.fullmatch(stable_id + ".png"):
            raise ValueError("every manifest record must have a canonical stable_id")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("every manifest record must have a non-empty canonical title")
        if stable_id in captions:
            raise ValueError("manifest stable IDs must be unique")
        captions[stable_id] = title.strip()
    return captions


def label_for(path: Path) -> str:
    if STABLE_CAPTURE.fullmatch(path.name):
        return path.stem
    value = re.sub(r"^\d{2}-", "", path.stem).replace("-", " ")
    value = re.sub(r"\b(\d+) percent\b", r"\1%", value)
    value = value.replace("3420x2082", "3420×2082")
    return value.title().replace(" High Contrast", " · High Contrast").replace(" Dark", " · Dark").replace(" Light", " · Light")


def caption_for(path: Path, captions: Mapping[str, str] | None = None) -> str:
    supplemental = SUPPLEMENTAL_CAPTIONS.get(path.name)
    if supplemental is not None:
        return supplemental
    if STABLE_CAPTURE.fullmatch(path.name):
        stable_id = path.stem
        if captions is not None:
            title = captions.get(stable_id)
            if not isinstance(title, str) or not title.strip():
                raise ValueError("no canonical contact-sheet title for {}".format(stable_id))
            return "{}  {}".format(stable_id, title.strip())
        return stable_id
    supplemental_match = re.match(
        r"^((?:CAL|INS|SET|RST|NFS|THM|OPA)-\d{2})-(.+)\.png$",
        path.name,
    )
    if supplemental_match is not None:
        stable_id, suffix = supplemental_match.groups()
        return "{} supplement  {}".format(
            stable_id,
            suffix.replace("-", " ").title(),
        )
    key = path.name[:2]
    return "{}  {}".format(key, label_for(path))


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_sheet(
    images: list[Path],
    destination: Path,
    title: str,
    columns: int,
    rows: int,
    cell_width: int,
    cell_height: int,
    captions: Mapping[str, str] | None = None,
) -> None:
    margin = 34
    gutter = 26
    title_height = 92
    caption_height = 54
    canvas_width = margin * 2 + columns * cell_width + (columns - 1) * gutter
    canvas_height = margin * 2 + title_height + rows * cell_height + (rows - 1) * gutter
    canvas = Image.new("RGB", (canvas_width, canvas_height), "#dfe5ec")
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, margin), title, fill="#172033", font=font(42, bold=True))

    for index, path in enumerate(images):
        row, column = divmod(index, columns)
        x = margin + column * (cell_width + gutter)
        y = margin + title_height + row * (cell_height + gutter)
        draw.rounded_rectangle(
            (x, y, x + cell_width, y + cell_height),
            radius=16,
            fill="#f8fafc",
            outline="#9aa7b8",
            width=2,
        )
        caption = caption_for(path, captions)
        draw.text((x + 18, y + 12), caption, fill="#273142", font=font(28, bold=True))
        source = Image.open(path).convert("RGB")
        frame = (cell_width - 28, cell_height - caption_height - 24)
        fitted = ImageOps.contain(source, frame, Image.Resampling.LANCZOS)
        image_x = x + (cell_width - fitted.width) // 2
        image_y = y + caption_height + (cell_height - caption_height - fitted.height) // 2
        canvas.paste(fitted, (image_x, image_y))

    canvas.save(destination, "PNG", optimize=True)


def _supplement_parent(path: Path) -> str:
    match = re.match(r"^((?:CAL|INS|SET|RST|NFS|THM|OPA)-\d{2})-", path.name)
    return match.group(1) if match is not None else ""


def build_contact_sheet_index(
    primary_images: list[Path],
    supplemental_images: list[Path],
    captions: Mapping[str, str],
    artifacts: list[Mapping[str, object]],
    *,
    ui_geometry_revision: int,
    candidate_sha256: str | None,
    capture_metadata: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Describe every raw capture and its one authoritative detail-sheet cell."""

    metadata = capture_metadata or {}
    ordered = [("primary", path, path.stem) for path in primary_images]
    ordered.extend(
        ("supplemental", path, _supplement_parent(path))
        for path in supplemental_images
    )
    cells: list[dict[str, object]] = []
    for index, (kind, path, stable_id) in enumerate(ordered):
        page = (index // 4) + 1
        cell = index % 4
        row, column = divmod(cell, 2)
        values = metadata.get(stable_id, {})
        cells.append(
            {
                "source_id": path.stem,
                "stable_id": stable_id,
                "source_kind": kind,
                "raw_capture": path.name,
                "raw_capture_sha256": sha256_file(path),
                "title": caption_for(path, captions),
                "state": values.get("state"),
                "theme": values.get("theme"),
                "mode": values.get("mode"),
                "scale_percent": values.get("scale_percent"),
                "opacity": values.get("opacity"),
                "candidate_sha256": candidate_sha256,
                "ui_geometry_revision": ui_geometry_revision,
                "detail_sheet": "contact-sheet-detail-{:02d}.png".format(page),
                "detail_page": page,
                "detail_row": row,
                "detail_column": column,
                "detail_cell": cell + 1,
                "categories": list(categories_for(stable_id)),
            }
        )
    category_metadata = []
    for category_id, title in CATEGORY_TITLES.items():
        category_artifacts = [
            dict(item)
            for item in artifacts
            if item.get("kind") == "category" and item.get("category_id") == category_id
        ]
        surface_ids = [
            stable_id
            for stable_id in captions
            if category_id in categories_for(stable_id)
        ]
        category_metadata.append(
            {
                "category_id": category_id,
                "title": title,
                "surface_ids": surface_ids,
                "artifacts": category_artifacts,
            }
        )
    return {
        "schema_version": 1,
        "release": "1.8.0",
        "ui_geometry_revision": ui_geometry_revision,
        "candidate_sha256": candidate_sha256,
        "primary_surface_count": len(primary_images),
        "supplemental_capture_count": len(supplemental_images),
        "primary_surface_ids": [path.stem for path in primary_images],
        "supplemental_capture_ids": [path.stem for path in supplemental_images],
        "artifacts": [dict(item) for item in artifacts],
        "categories": category_metadata,
        "detail_cells": cells,
    }


def validate_contact_sheet_index(
    index: Mapping[str, object],
    primary_ids: list[str],
    supplemental_ids: list[str],
    *,
    require_complete_metadata: bool = True,
) -> list[str]:
    """Fail closed unless every raw capture owns exactly one detail cell."""

    errors: list[str] = []
    if index.get("schema_version") != 1:
        errors.append("contact-sheet index schema_version must be 1")
    if index.get("release") != "1.8.0":
        errors.append("contact-sheet index release must be 1.8.0")
    revision = index.get("ui_geometry_revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        errors.append("contact-sheet index needs a positive ui_geometry_revision")
    if index.get("primary_surface_ids") != primary_ids:
        errors.append("contact-sheet index primary IDs are not in registry order")
    if index.get("supplemental_capture_ids") != supplemental_ids:
        errors.append("contact-sheet index supplemental IDs are not canonical")
    cells = index.get("detail_cells")
    if not isinstance(cells, list):
        return errors + ["contact-sheet detail_cells must be an array"]
    expected = primary_ids + supplemental_ids
    actual = [cell.get("source_id") for cell in cells if isinstance(cell, Mapping)]
    if actual != expected:
        errors.append("each primary and supplemental capture must occur in one ordered detail cell")
    if len(actual) != len(set(actual)):
        errors.append("contact-sheet detail cells duplicate a source capture")
    occupied: set[tuple[object, object, object]] = set()
    required_metadata = (
        "raw_capture_sha256",
        "title",
        "state",
        "theme",
        "mode",
        "scale_percent",
        "opacity",
        "candidate_sha256",
        "ui_geometry_revision",
    )
    for cell in cells:
        if not isinstance(cell, Mapping):
            errors.append("every contact-sheet detail cell must be an object")
            continue
        location = (
            cell.get("detail_sheet"),
            cell.get("detail_row"),
            cell.get("detail_column"),
        )
        if location in occupied:
            errors.append("contact-sheet detail cells share a sheet location")
        occupied.add(location)
        digest = cell.get("raw_capture_sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            errors.append("contact-sheet cell raw capture SHA-256 is invalid")
        if require_complete_metadata and any(cell.get(field) in {None, ""} for field in required_metadata):
            errors.append("contact-sheet cell metadata is incomplete for {}".format(cell.get("source_id")))
    artifacts = index.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("contact-sheet artifacts must be an array")
    else:
        kinds = {item.get("kind") for item in artifacts if isinstance(item, Mapping)}
        if not {"overview", "category", "detail"}.issubset(kinds):
            errors.append("contact-sheet artifacts need overview, category, and detail sheets")
    categories = index.get("categories")
    if not isinstance(categories, list) or [
        item.get("category_id") for item in categories if isinstance(item, Mapping)
    ] != list(CATEGORY_TITLES):
        errors.append("contact-sheet category metadata is incomplete or out of order")
    return errors


def write_contact_sheet_set(
    primary_images: list[Path],
    supplemental_images: list[Path],
    output_directory: Path,
    title: str,
    captions: Mapping[str, str],
    *,
    ui_geometry_revision: int,
    candidate_sha256: str | None = None,
    capture_metadata: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Generate organized sheets plus the machine-readable exact-once index."""

    output_directory.mkdir(parents=True, exist_ok=True)
    all_images = primary_images + supplemental_images
    artifacts: list[dict[str, object]] = []
    overview = output_directory / "contact-sheet-overview.png"
    render_sheet(all_images, overview, title, 4, ceil(len(all_images) / 4), 800, 560, captions)
    artifacts.append(
        {
            "kind": "overview",
            "path": overview.name,
            "surface_ids": [path.stem for path in primary_images],
            "supplemental_ids": [path.stem for path in supplemental_images],
        }
    )
    for category_id, category_title in CATEGORY_TITLES.items():
        category_images = [
            path
            for path in all_images
            if category_id in categories_for(
                path.stem if STABLE_CAPTURE.fullmatch(path.name) else _supplement_parent(path)
            )
        ]
        for page, start in enumerate(range(0, len(category_images), 16), 1):
            page_images = category_images[start : start + 16]
            destination = output_directory / "contact-sheet-category-{}-{:02d}.png".format(
                category_id,
                page,
            )
            render_sheet(
                page_images,
                destination,
                "{} · {}".format(title, category_title),
                4,
                ceil(len(page_images) / 4),
                800,
                560,
                captions,
            )
            artifacts.append(
                {
                    "kind": "category",
                    "category_id": category_id,
                    "category_title": category_title,
                    "page": page,
                    "path": destination.name,
                    "surface_ids": [
                        path.stem if STABLE_CAPTURE.fullmatch(path.name) else _supplement_parent(path)
                        for path in page_images
                    ],
                }
            )
    page_count = ceil(len(all_images) / 4)
    for page, start in enumerate(range(0, len(all_images), 4), 1):
        destination = output_directory / "contact-sheet-detail-{:02d}.png".format(page)
        page_images = all_images[start : start + 4]
        render_sheet(
            page_images,
            destination,
            "{} · Detail {}/{}".format(title, page, page_count),
            2,
            2,
            1600,
            1040,
            captions,
        )
        artifacts.append(
            {
                "kind": "detail",
                "page": page,
                "path": destination.name,
                "source_ids": [path.stem for path in page_images],
            }
        )
    index = build_contact_sheet_index(
        primary_images,
        supplemental_images,
        captions,
        artifacts,
        ui_geometry_revision=ui_geometry_revision,
        candidate_sha256=candidate_sha256,
        capture_metadata=capture_metadata,
    )
    (output_directory / "contact-sheet-index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--title",
        default="Home Screen Dashboard 1.8.0 · Offline visual reference",
    )
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--candidate-sha256")
    parser.add_argument("--ui-geometry-revision", type=int, default=1)
    args = parser.parse_args()
    directory = args.directory.resolve()
    output_directory = (args.output_directory or directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    try:
        images = ordered_images(directory, args.manifest)
        captions = manifest_captions(args.manifest) if args.manifest is not None else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    if not images:
        raise SystemExit("no stable-ID or numbered captures found")
    if captions is None:
        captions = {path.stem: path.stem for path in images}
    metadata: Mapping[str, Mapping[str, object]] = {}
    if args.metadata is not None:
        parsed = json.loads(args.metadata.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict) or not all(
            isinstance(key, str) and isinstance(value, dict)
            for key, value in parsed.items()
        ):
            raise SystemExit("metadata must be an object keyed by stable ID")
        metadata = parsed
    supplements = ordered_supplemental_images(directory, images)
    write_contact_sheet_set(
        images,
        supplements,
        output_directory,
        args.title,
        captions,
        ui_geometry_revision=args.ui_geometry_revision,
        candidate_sha256=args.candidate_sha256,
        capture_metadata=metadata,
    )


if __name__ == "__main__":
    main()
