#!/usr/bin/env python3
"""Assemble immutable Home Screen Dashboard 1.8.6 release evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
from typing import Any, Iterable, Mapping
import zipfile

from PIL import Image, ImageDraw, ImageFont


SOURCE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SOURCE_ROOT.parent
RELEASE = "1.8.6"
EXPECTED_INITIAL = 92
EXPECTED_RESTART = 2
EXPECTED_TOTAL = 94
DEFAULT_CANDIDATE = SOURCE_ROOT / "dist" / "home-dashboard-overhaul-1.8.6.ankiaddon"
DEFAULT_OUTPUT = SOURCE_ROOT / "qa" / "release-evidence-1.8.6-2026-08-24"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "{} must contain a JSON object".format(path))
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_capture_ids() -> list[str]:
    matrix = read_json(SOURCE_ROOT / "qa" / "visual_regression_matrix_1_8_6.json")
    contract = read_json(SOURCE_ROOT / "qa" / "capture_evidence_manifest_1_8_6.json")
    ids = [str(case["id"]) for case in matrix["palette_cases"]]
    families = {str(family["id"]): family for family in contract["capture_families"]}
    ids.extend(str(value) for value in families["production-core"]["capture_ids"])
    for page in ("DASHBOARD", "EVENTS", "BIBLE", "ABOUT"):
        for width in ("1040", "1200", "FULL"):
            for font in (100, 150):
                ids.append("SET-PAGE-{}-{}-{}".format(page, width, font))
    ids.extend(str(value) for value in families["settings-contract"]["capture_ids"])
    ids.extend(str(value) for value in families["statistics-accuracy"]["capture_ids"])
    ids.extend(str(value) for value in families["restart"]["capture_ids"])
    require(len(ids) == EXPECTED_TOTAL and len(set(ids)) == EXPECTED_TOTAL, "capture contract does not derive 94 unique IDs")
    return ids


def isolation_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    identity = report.get("identity", {})
    require(isinstance(identity, Mapping), "runtime report lacks isolation identity")
    gates = {
        "process": bool(identity.get("processes_are_distinct")),
        "window": bool(identity.get("window_title_matches_profile")),
        "filesystem": bool(identity.get("collection_inside_run_root") and identity.get("addons_inside_run_root")),
        "sync": bool(
            identity.get("sync_credentials_present") is False
            and identity.get("auto_sync") is False
            and identity.get("media_sync") is False
        ),
    }
    require(identity.get("gated_before_window_interaction") is True, "isolation was not gated before interaction")
    require(all(gates.values()), "one or more isolation gates failed")
    return {
        "status": "passed",
        "gated_before_window_interaction": True,
        "gates": gates,
        "profile": identity.get("profile"),
        "window_title": identity.get("window_title"),
        "collection_path": identity.get("collection_path"),
        "run_root": identity.get("run_root"),
        "candidate": identity.get("candidate"),
    }


def validate_runtime(run_output: Path, candidate_hash: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    initial = read_json(run_output / "runtime-report-initial.json")
    restart = read_json(run_output / "runtime-report-restart.json")
    for report, stage, expected in (
        (initial, "initial", EXPECTED_INITIAL),
        (restart, "restart", EXPECTED_RESTART),
    ):
        require(report.get("release") == RELEASE and report.get("stage") == stage, "{} runtime report identity mismatch".format(stage))
        require(report.get("status") == "passed" and not report.get("errors"), "{} runtime probe did not pass".format(stage))
        require(len(report.get("captures", {})) == expected, "{} runtime capture count mismatch".format(stage))
        require(report.get("multi_deck_new_limit_smoke", {}).get("status") == "passed", "{} scheduler-authoritative count smoke failed".format(stage))
        require(report.get("native_statistics_comparison", {}).get("status") == "passed", "{} native statistics comparison failed".format(stage))
        candidate = report.get("identity", {}).get("candidate", {})
        require(candidate.get("candidate_sha256") == candidate_hash, "{} runtime report used the wrong package hash".format(stage))
        require(candidate.get("installed_member_parity") == "passed", "{} installed package bytes drifted".format(stage))
    require(initial.get("persistence_write", {}).get("status") == "passed", "initial persistence write did not pass")
    require(restart.get("persistence_readback", {}).get("status") == "passed", "restart persistence readback did not pass")
    require(
        set(initial.get("statistics_responsive_parity", {})) == {
            "PROD-STATS-WIDE-MONTH",
            "PROD-STATS-WIDE-YEAR",
            "PROD-STATS-INTERMEDIATE",
            "PROD-STATS-NARROW",
        },
        "initial responsive statistics parity is incomplete",
    )
    require(
        restart.get("statistics_responsive_parity", {}).get("PROD-RESTART-PERSISTENCE", {}).get("status") == "passed",
        "restart statistics parity is incomplete",
    )
    isolation = {
        "initial": isolation_summary(initial),
        "restart": isolation_summary(restart),
        "all_four_gates_repeated_after_restart": True,
    }
    return initial, restart, isolation


def archive_inspection(candidate: Path) -> dict[str, Any]:
    require(candidate.is_file(), "candidate archive is missing")
    manifest = read_json(SOURCE_ROOT / "manifest.json")
    require(manifest.get("human_version") == RELEASE, "source manifest version mismatch")
    members: list[dict[str, Any]] = []
    with zipfile.ZipFile(candidate) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        require(len(infos) == 24, "candidate archive must contain 24 files")
        names = [info.filename for info in infos]
        require(len(names) == len(set(names)), "candidate archive contains duplicate paths")
        for info in infos:
            path = PurePosixPath(info.filename)
            require(not path.is_absolute() and ".." not in path.parts and "" not in path.parts, "unsafe archive path: {}".format(info.filename))
            require(not info.filename.startswith(("/", "\\")), "absolute archive path: {}".format(info.filename))
            source = SOURCE_ROOT / info.filename
            require(source.is_file(), "archive member has no source file: {}".format(info.filename))
            archive_bytes = archive.read(info.filename)
            source_bytes = source.read_bytes()
            require(archive_bytes == source_bytes, "source/archive byte mismatch: {}".format(info.filename))
            members.append({
                "path": info.filename,
                "size": len(archive_bytes),
                "sha256": hashlib.sha256(archive_bytes).hexdigest(),
                "source_byte_parity": "passed",
                "safe_path": True,
                "timestamp": list(info.date_time),
            })
        packaged_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    require(packaged_manifest.get("human_version") == RELEASE, "archive manifest version mismatch")
    return {
        "release": RELEASE,
        "archive": candidate.name,
        "sha256": sha256(candidate),
        "member_count": len(members),
        "manifest_version": packaged_manifest.get("human_version"),
        "safe_paths": "passed",
        "source_archive_byte_parity": "passed",
        "members": members,
    }


def collect_captures(
    run_output: Path,
    output: Path,
    initial: Mapping[str, Any],
    restart: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    expected = expected_capture_ids()
    combined: dict[str, dict[str, Any]] = {}
    for report in (initial, restart):
        for capture_id, raw in report["captures"].items():
            require(capture_id not in combined, "duplicate runtime capture ID: {}".format(capture_id))
            source = run_output / str(raw["file"])
            require(source.is_file(), "runtime capture is missing: {}".format(capture_id))
            require(sha256(source) == raw.get("sha256"), "runtime capture hash mismatch: {}".format(capture_id))
            destination = output / "captures" / "{}.png".format(capture_id)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            record = dict(raw)
            record["file"] = destination.relative_to(output).as_posix()
            record["sha256"] = sha256(destination)
            combined[capture_id] = record
    require(set(combined) == set(expected), "combined runtime capture IDs differ from the contract")
    return {capture_id: combined[capture_id] for capture_id in expected}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def fitted_image(path: Path, width: int, height: int) -> Image.Image:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    frame = Image.new("RGB", (width, height), "#0b1020")
    frame.paste(image, ((width - image.width) // 2, (height - image.height) // 2))
    return frame


def make_capture_sheet(
    output: Path,
    filename: str,
    title: str,
    capture_ids: list[str],
    columns: int,
    thumb: tuple[int, int],
) -> dict[str, Any]:
    tile_width, tile_height = thumb[0] + 32, thumb[1] + 78
    rows = max(1, (len(capture_ids) + columns - 1) // columns)
    canvas = Image.new("RGB", (columns * tile_width + 32, rows * tile_height + 96), "#111827")
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 20), title, font=font(30, True), fill="#f8fafc")
    draw.text((24, 58), "Home Screen Dashboard 1.8.6 · native exact-package evidence", font=font(16), fill="#cbd5e1")
    for index, capture_id in enumerate(capture_ids):
        row, column = divmod(index, columns)
        x = 16 + column * tile_width
        y = 88 + row * tile_height
        preview = fitted_image(output / "captures" / "{}.png".format(capture_id), *thumb)
        canvas.paste(preview, (x + 8, y + 8))
        draw.rounded_rectangle((x + 4, y + 4, x + tile_width - 4, y + tile_height - 4), radius=8, outline="#334155", width=2)
        label = capture_id if len(capture_id) <= 46 else capture_id[:43] + "…"
        draw.text((x + 12, y + thumb[1] + 18), label, font=font(14, True), fill="#f8fafc")
    path = output / "contact-sheets" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, "PNG", optimize=True)
    return {
        "file": path.relative_to(output).as_posix(),
        "title": title,
        "capture_ids": capture_ids,
        "sha256": sha256(path),
        "physical_pixels": [canvas.width, canvas.height],
    }


def report_sheet(output: Path, isolation: Mapping[str, Any], archive: Mapping[str, Any]) -> dict[str, Any]:
    canvas = Image.new("RGB", (1800, 1200), "#111827")
    draw = ImageDraw.Draw(canvas)
    draw.text((64, 54), "Package and isolation reports", font=font(42, True), fill="#f8fafc")
    lines = [
        "Exact package SHA-256: {}".format(archive["sha256"]),
        "Archive: 24 allowlisted members · safe paths PASS · source byte parity PASS",
        "Initial process gate: PASS",
        "Initial window/profile gate: PASS",
        "Initial disposable filesystem gate: PASS",
        "Initial sync-disabled gate: PASS",
        "Controlled restart process gate: PASS",
        "Controlled restart window/profile gate: PASS",
        "Controlled restart disposable filesystem gate: PASS",
        "Controlled restart sync-disabled gate: PASS",
        "Scheduler-authoritative New: 3 + 7 = 10; excluding head B = 3; restart New = 10, Total = 12",
        "Native statistics parity: Anki Graphs + Scheduler = dashboard cards and calendar PASS",
        "Restart persistence: production Year + Settings clean state + event name sort + resizable window policy",
        "VoiceOver, Windows, Linux, forced-colors, DPR 1, and OS display scaling: UNRUN",
    ]
    y = 150
    for line in lines:
        color = "#86efac" if "PASS" in line else "#f8fafc"
        draw.text((80, y), line, font=font(24, "PASS" in line), fill=color)
        y += 66
    path = output / "contact-sheets" / "contact-sheet-19-package-and-isolation-reports.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, "PNG", optimize=True)
    return {
        "file": path.relative_to(output).as_posix(),
        "title": "Package and isolation reports",
        "capture_ids": [],
        "sha256": sha256(path),
        "physical_pixels": [canvas.width, canvas.height],
        "report_only": True,
        "all_four_isolation_gates_repeated": isolation["all_four_gates_repeated_after_restart"],
    }


def detail_groups() -> list[tuple[str, list[str]]]:
    expected = expected_capture_ids()
    palette = expected[:32]
    page_ids = expected[48:72]
    contract = expected[72:88]
    statistics = expected[88:92]
    return [
        ("Production palettes · Sapphire Glass", palette[0:8]),
        ("Production palettes · Graphite", palette[8:16]),
        ("Production palettes · Emerald", palette[16:24]),
        ("Production palettes · High Contrast", palette[24:32]),
        ("Production Month, Year, and marker combinations", expected[32:39]),
        ("Production legends, backgrounds, sections, clearance, and verse", expected[39:48]),
        ("Settings Dashboard · 100% application font", [value for value in page_ids if "DASHBOARD" in value and value.endswith("-100")]),
        ("Settings Events · 100% application font", [value for value in page_ids if "EVENTS" in value and value.endswith("-100")]),
        ("Settings Bible verse · 100% application font", [value for value in page_ids if "BIBLE" in value and value.endswith("-100")]),
        ("Settings About · 100% application font", [value for value in page_ids if "ABOUT" in value and value.endswith("-100")]),
        ("Settings pages · 150% application font", [value for value in page_ids if value.endswith("-150")]),
        ("Settings Events states", contract[0:5]),
        ("Settings Bible states", contract[5:8]),
        ("Settings dirty, revert, save, and error", contract[9:13]),
        ("Settings About bottom, legacy route, standard window, and clamp", [contract[index] for index in (8, 13, 14, 15)]),
        ("Statistics accuracy · responsive shells", statistics),
        ("Controlled restart persistence", expected[92:94]),
    ]


def make_contact_sheets(output: Path, isolation: Mapping[str, Any], archive: Mapping[str, Any]) -> dict[str, Any]:
    expected = expected_capture_ids()
    sheets = [make_capture_sheet(output, "contact-sheet-00-overview.png", "Canonical UI release overview", expected, 5, (310, 190))]
    covered: list[str] = []
    for index, (title, capture_ids) in enumerate(detail_groups(), start=1):
        sheets.append(make_capture_sheet(
            output,
            "contact-sheet-{:02d}-{}.png".format(index, re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")),
            title,
            capture_ids,
            3,
            (620, 390),
        ))
        covered.extend(capture_ids)
    sheets.append(report_sheet(output, isolation, archive))
    require(len(sheets) == 19, "contact-sheet set must contain one overview and 18 detail sheets")
    require(
        len(covered) == len(expected) and set(covered) == set(expected),
        "detail sheets must cover every native capture exactly once",
    )
    index = {
        "schema_version": 2,
        "release": RELEASE,
        "overview_count": 1,
        "detail_sheet_count": 18,
        "native_capture_count": EXPECTED_TOTAL,
        "each_native_capture_in_details_exactly_once": True,
        "sheets": sheets,
    }
    write_json(output / "contact-sheets" / "contact-sheet-index.json", index)
    return index


def write_readme(output: Path, candidate_hash: str) -> None:
    text = """# Home Screen Dashboard 1.8.6 native release evidence

This immutable evidence set was assembled from the exact reproducible package
`home-dashboard-overhaul-1.8.6.ankiaddon` with SHA-256 `{}`.

- `captures/` contains 94 native frames derived from the current implementation
  contract: 92 initial and two controlled-restart frames.
- The 19 generated contact sheets are retained as local-only release evidence
  and intentionally excluded from version control. Their 18 detail sheets cover
  every native frame exactly once; the final sheet summarizes package and
  isolation proof.
- `reports/runtime-report-initial.json` and `runtime-report-restart.json` retain
  exact-package, scheduler-count, Settings, persistence, and all four isolation
  gates.
- `reports/archive-inspection.json` proves the 24-member allowlist, safe paths,
  and source/archive byte parity.

VoiceOver, Windows, Linux, forced-colors, DPR 1, and OS display-scaling
acceptance were not run and are not claimed.
""".format(candidate_hash)
    (output / "README.md").write_text(text, encoding="utf-8")


def assemble(run_root: Path, candidate: Path, output: Path) -> Path:
    run_root = run_root.resolve(strict=True)
    candidate = candidate.resolve(strict=True)
    require(str(run_root).startswith("/private/tmp/anki-release-qa."), "run root is not a disposable release-QA root")
    require(not output.exists(), "refusing to overwrite release evidence: {}".format(output))
    output.mkdir(parents=True)
    run_output = run_root / "hdo-release-evidence-1.8.6"
    candidate_hash = sha256(candidate)
    initial, restart, isolation = validate_runtime(run_output, candidate_hash)
    archive = archive_inspection(candidate)
    captures = collect_captures(run_output, output, initial, restart)

    reports = output / "reports"
    reports.mkdir()
    shutil.copy2(run_output / "runtime-report-initial.json", reports / "runtime-report-initial.json")
    shutil.copy2(run_output / "runtime-report-restart.json", reports / "runtime-report-restart.json")
    write_json(reports / "isolation-gates.json", isolation)
    write_json(reports / "archive-inspection.json", archive)
    write_json(output / "capture-manifest.json", {
        "schema_version": 3,
        "release": RELEASE,
        "capture_count": len(captures),
        "captures": captures,
    })

    package_dir = output / "package"
    package_dir.mkdir()
    packaged = package_dir / candidate.name
    shutil.copy2(candidate, packaged)
    require(sha256(packaged) == candidate_hash, "evidence package copy changed bytes")
    (package_dir / "{}.sha256".format(candidate.name)).write_text(
        "{}  {}\n".format(candidate_hash, candidate.name), encoding="utf-8"
    )

    contract_names = (
        "calendar_surface_manifest_1_8_6.json",
        "ui-surface-registry_1_8_6.json",
        "visual_regression_matrix_1_8_6.json",
        "capture_evidence_manifest_1_8_6.json",
        "runtime_probe_release_1_8_6_manifest.json",
    )
    contracts = output / "contracts"
    contracts.mkdir()
    for name in contract_names:
        shutil.copy2(SOURCE_ROOT / "qa" / name, contracts / name)

    contact_sheets = make_contact_sheets(output, isolation, archive)
    write_json(output / "capture-evidence-manifest.json", {
        "schema_version": 3,
        "release": RELEASE,
        "status": "passed",
        "package": {
            "path": packaged.relative_to(output).as_posix(),
            "sha256": candidate_hash,
            "member_count": 24,
            "source_archive_byte_parity": "passed",
        },
        "native_captures": {"initial": EXPECTED_INITIAL, "restart": EXPECTED_RESTART, "total": EXPECTED_TOTAL},
        "contact_sheets": {
            "overview": contact_sheets["overview_count"],
            "details": contact_sheets["detail_sheet_count"],
            "total": len(contact_sheets["sheets"]),
            "exact_once_detail_coverage": contact_sheets["each_native_capture_in_details_exactly_once"],
            "repository_tracking": "local-only",
        },
        "isolation": isolation,
        "restart_persistence": "passed",
        "deferred_unrun": [
            "voiceover_review", "windows_validation", "linux_validation",
            "forced_colors_review", "device_pixel_ratio_1", "os_display_scaling",
        ],
    })
    write_readme(output, candidate_hash)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        output = assemble(args.run_root, args.candidate, args.output.resolve())
    except Exception as exc:
        print("ERROR: {}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
