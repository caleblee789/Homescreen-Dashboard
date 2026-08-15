from __future__ import annotations

import argparse
from math import ceil
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont, ImageOps


def label_for(path: Path) -> str:
    value = re.sub(r"^\d{2}-", "", path.stem).replace("-", " ")
    value = re.sub(r"\b(\d+) percent\b", r"\1%", value)
    value = value.replace("3420x2082", "3420×2082")
    return value.title().replace(" High Contrast", " · High Contrast").replace(" Dark", " · Dark").replace(" Light", " · Light")


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
        key = path.name[:2]
        label = label_for(path)
        draw.text((x + 18, y + 12), f"{key}  {label}", fill="#273142", font=font(28, bold=True))
        source = Image.open(path).convert("RGB")
        frame = (cell_width - 28, cell_height - caption_height - 24)
        fitted = ImageOps.contain(source, frame, Image.Resampling.LANCZOS)
        image_x = x + (cell_width - fitted.width) // 2
        image_y = y + caption_height + (cell_height - caption_height - fitted.height) // 2
        canvas.paste(fitted, (image_x, image_y))

    canvas.save(destination, "PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--title",
        default="Home Dashboard 1.5.3 · Exact-package Calendar UI acceptance",
    )
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve()
    output_directory = (args.output_directory or directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    images = sorted(path for path in directory.glob("[0-9][0-9]-*.png") if "contact-sheet" not in path.name)
    if not images:
        raise SystemExit("no numbered captures found")
    overview_rows = ceil(len(images) / 4)
    render_sheet(images, output_directory / "contact-sheet-overview.png", args.title, 4, overview_rows, 800, 560)
    page_count = ceil(len(images) / 4)
    for page, start in enumerate(range(0, len(images), 4), 1):
        render_sheet(
            images[start : start + 4],
            output_directory / f"contact-sheet-detail-{page:02d}.png",
            f"{args.title} · Detail {page}/{page_count}",
            2,
            2,
            1600,
            1040,
        )


if __name__ == "__main__":
    main()
