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
import tempfile
from typing import Any, Mapping
import zipfile

from PIL import Image, ImageDraw, ImageFont

from capture_plan import load_capture_plan


SOURCE_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_PLAN = load_capture_plan(SOURCE_ROOT / "qa" / "capture_plan.json")
RELEASE = CAPTURE_PLAN.release
DEFAULT_CANDIDATE = SOURCE_ROOT / "dist" / "home-dashboard-overhaul-1.8.6.ankiaddon"


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


def redact_evidence_paths(value: Any, *, run_root: Path, candidate: Path) -> Any:
    """Remove machine-local paths while preserving useful report structure."""

    if isinstance(value, Mapping):
        return {
            key: redact_evidence_paths(item, run_root=run_root, candidate=candidate)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            redact_evidence_paths(item, run_root=run_root, candidate=candidate)
            for item in value
        ]
    if isinstance(value, str):
        return value.replace(str(candidate), "<candidate-package>").replace(
            str(run_root), "<disposable-run-root>"
        )
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_capture_ids(profile_id: str = "full") -> list[str]:
    return list(CAPTURE_PLAN.ids(profile_id))


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


def validate_runtime(
    run_output: Path,
    candidate_hash: str,
    profile_id: str,
    *,
    allow_legacy_unversioned_reports: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    initial = read_json(run_output / "runtime-report-initial.json")
    restart = read_json(run_output / "runtime-report-restart.json")
    counts = CAPTURE_PLAN.counts(profile_id)
    legacy_stages: list[str] = []
    for report, stage, expected in (
        (initial, "initial", counts["initial"]),
        (restart, "restart", counts["restart"]),
    ):
        require(report.get("release") == RELEASE and report.get("stage") == stage, "{} runtime report identity mismatch".format(stage))
        require(report.get("status") == "passed" and not report.get("errors"), "{} runtime probe did not pass".format(stage))
        require(len(report.get("captures", {})) == expected, "{} runtime capture count mismatch".format(stage))
        plan_record = report.get("capture_plan")
        if isinstance(plan_record, Mapping):
            require(plan_record.get("profile") == profile_id, "{} runtime capture profile mismatch".format(stage))
            require(plan_record.get("sha256") == CAPTURE_PLAN.sha256, "{} runtime capture plan changed".format(stage))
            require(
                tuple(plan_record.get("resolved_stage_capture_ids", ()))
                == CAPTURE_PLAN.ids(profile_id, stage=stage),
                "{} runtime capture order differs from the plan".format(stage),
            )
        else:
            require(
                allow_legacy_unversioned_reports and profile_id == "full",
                "runtime report lacks capture-plan identity; use the explicit legacy flag only to reconstruct retained full-profile evidence",
            )
            legacy_stages.append(stage)
        require(report.get("multi_deck_new_limit_smoke", {}).get("status") == "passed", "{} scheduler-authoritative count smoke failed".format(stage))
        require(report.get("native_statistics_comparison", {}).get("status") == "passed", "{} native statistics comparison failed".format(stage))
        candidate = report.get("identity", {}).get("candidate", {})
        require(candidate.get("candidate_sha256") == candidate_hash, "{} runtime report used the wrong package hash".format(stage))
        require(candidate.get("installed_member_parity") == "passed", "{} installed package bytes drifted".format(stage))
    require(initial.get("persistence_write", {}).get("status") == "passed", "initial persistence write did not pass")
    require(restart.get("persistence_readback", {}).get("status") == "passed", "restart persistence readback did not pass")
    for report, stage in ((initial, "initial"), (restart, "restart")):
        expected_statistics = set(CAPTURE_PLAN.tagged_ids(
            "statistics_accuracy", profile_id, stage=stage
        ))
        if expected_statistics:
            require(
                set(report.get("statistics_responsive_parity", {})) == expected_statistics,
                "{} responsive statistics parity is incomplete".format(stage),
            )
    isolation = {
        "initial": isolation_summary(initial),
        "restart": isolation_summary(restart),
        "all_four_gates_repeated_after_restart": True,
        "legacy_unversioned_capture_reports": legacy_stages,
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
    profile_id: str,
) -> dict[str, dict[str, Any]]:
    expected = expected_capture_ids(profile_id)
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
    profile_id: str,
) -> dict[str, Any]:
    tile_width, tile_height = thumb[0] + 32, thumb[1] + 78
    rows = max(1, (len(capture_ids) + columns - 1) // columns)
    canvas = Image.new("RGB", (columns * tile_width + 32, rows * tile_height + 96), "#111827")
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 20), title, font=font(30, True), fill="#f8fafc")
    draw.text(
        (24, 58),
        "Home Screen Dashboard {} · {} · native exact-package evidence".format(RELEASE, profile_id),
        font=font(16),
        fill="#cbd5e1",
    )
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


def report_sheet(
    output: Path,
    isolation: Mapping[str, Any],
    archive: Mapping[str, Any],
    sheet_number: int,
) -> dict[str, Any]:
    report = CAPTURE_PLAN.presentation["report"]
    report_id = str(report["id"])
    title = str(report["title"])
    canvas = Image.new("RGB", (1800, 1200), "#111827")
    draw = ImageDraw.Draw(canvas)
    draw.text((64, 54), title, font=font(42, True), fill="#f8fafc")
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
    path = output / "contact-sheets" / "contact-sheet-{:02d}-{}.png".format(
        sheet_number, report_id
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, "PNG", optimize=True)
    return {
        "file": path.relative_to(output).as_posix(),
        "title": title,
        "capture_ids": [],
        "sha256": sha256(path),
        "physical_pixels": [canvas.width, canvas.height],
        "report_only": True,
        "all_four_isolation_gates_repeated": isolation["all_four_gates_repeated_after_restart"],
    }


def detail_groups(profile_id: str = "full") -> list[dict[str, Any]]:
    return CAPTURE_PLAN.detail_groups(profile_id)


def make_contact_sheets(
    output: Path,
    isolation: Mapping[str, Any],
    archive: Mapping[str, Any],
    profile_id: str,
) -> dict[str, Any]:
    expected = expected_capture_ids(profile_id)
    overview = CAPTURE_PLAN.presentation["overview"]
    sheets = [make_capture_sheet(
        output,
        "contact-sheet-00-overview.png",
        str(overview["title"]),
        expected,
        int(overview["columns"]),
        tuple(int(value) for value in overview["thumbnail"]),
        profile_id,
    )]
    covered: list[str] = []
    groups = detail_groups(profile_id)
    for index, group in enumerate(groups, start=1):
        title = str(group["title"])
        capture_ids = list(group["capture_ids"])
        sheets.append(make_capture_sheet(
            output,
            "contact-sheet-{:02d}-{}.png".format(index, re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")),
            title,
            capture_ids,
            int(group["columns"]),
            tuple(int(value) for value in group["thumbnail"]),
            profile_id,
        ))
        covered.extend(capture_ids)
    sheets.append(report_sheet(output, isolation, archive, len(groups) + 1))
    require(
        len(covered) == len(expected) and set(covered) == set(expected),
        "detail sheets must cover every native capture exactly once",
    )
    index = {
        "schema_version": 2,
        "release": RELEASE,
        "profile": profile_id,
        "capture_plan_sha256": CAPTURE_PLAN.sha256,
        "overview_count": 1,
        "capture_detail_sheet_count": len(groups),
        "report_sheet_count": 1,
        "detail_sheet_count": len(groups) + 1,
        "non_overview_sheet_count": len(groups) + 1,
        "native_capture_count": len(expected),
        "each_native_capture_in_details_exactly_once": True,
        "sheets": sheets,
    }
    write_json(output / "contact-sheets" / "contact-sheet-index.json", index)
    return index


def write_readme(
    output: Path,
    candidate_hash: str,
    profile_id: str,
    contact_sheets: Mapping[str, Any],
    *,
    legacy_unversioned_reports: bool,
) -> None:
    counts = CAPTURE_PLAN.counts(profile_id)
    text = """# Home Screen Dashboard {release} native capture evidence ({profile})

This immutable evidence set was assembled from the exact reproducible package
`home-dashboard-overhaul-{release}.ankiaddon` with SHA-256 `{candidate_hash}`.

- `captures/` contains {total} native frames derived from the `{profile}` capture
  profile: {initial} initial and {restart} controlled-restart frames.
- The {sheet_total} generated contact sheets are retained with this current evidence set.
- The {details} capture-detail sheets cover every native frame exactly once;
  the final sheet summarizes package and isolation proof.
- `reports/runtime-report-initial.json` and `runtime-report-restart.json` retain
  exact-package, scheduler-count, Settings, persistence, and all four isolation
  gates.
- `reports/archive-inspection.json` proves the 24-member allowlist, safe paths,
  and source/archive byte parity.

VoiceOver, Windows, Linux, forced-colors, DPR 1, and OS display-scaling
acceptance were not run and are not claimed.
{legacy_note}
""".format(
        release=RELEASE,
        profile=profile_id,
        candidate_hash=candidate_hash,
        total=counts["total"],
        initial=counts["initial"],
        restart=counts["restart"],
        sheet_total=len(contact_sheets["sheets"]),
        details=contact_sheets["capture_detail_sheet_count"],
        legacy_note=(
            "\n> Archival reconstruction: the retained runtime reports predate plan hashes. "
            "This is not new plan-bound acceptance."
            if legacy_unversioned_reports
            else ""
        ),
    )
    (output / "README.md").write_text(text.rstrip() + "\n", encoding="utf-8")


def _assemble_to_directory(
    run_root: Path,
    candidate: Path,
    output: Path,
    profile_id: str = "full",
    *,
    allow_legacy_unversioned_reports: bool = False,
) -> Path:
    run_root = run_root.resolve(strict=True)
    candidate = candidate.resolve(strict=True)
    CAPTURE_PLAN.profile(profile_id)
    CAPTURE_PLAN.validate_authorities(SOURCE_ROOT / "qa")
    counts = CAPTURE_PLAN.counts(profile_id)
    require(str(run_root).startswith("/private/tmp/anki-release-qa."), "run root is not a disposable release-QA root")
    require(not output.exists(), "refusing to overwrite release evidence: {}".format(output))
    run_output = run_root / str(CAPTURE_PLAN.profile(profile_id)["output_directory"])
    candidate_hash = sha256(candidate)
    initial, restart, isolation = validate_runtime(
        run_output,
        candidate_hash,
        profile_id,
        allow_legacy_unversioned_reports=allow_legacy_unversioned_reports,
    )
    archive = archive_inspection(candidate)
    public_initial = redact_evidence_paths(initial, run_root=run_root, candidate=candidate)
    public_restart = redact_evidence_paths(restart, run_root=run_root, candidate=candidate)
    public_isolation = redact_evidence_paths(isolation, run_root=run_root, candidate=candidate)
    require(not output.exists(), "release evidence output appeared during validation: {}".format(output))
    output.mkdir(parents=True)
    captures = collect_captures(run_output, output, initial, restart, profile_id)

    reports = output / "reports"
    reports.mkdir()
    write_json(reports / "runtime-report-initial.json", public_initial)
    write_json(reports / "runtime-report-restart.json", public_restart)
    write_json(reports / "isolation-gates.json", public_isolation)
    write_json(reports / "archive-inspection.json", archive)
    write_json(output / "capture-manifest.json", {
        "schema_version": 3,
        "release": RELEASE,
        "profile": profile_id,
        "capture_plan_sha256": CAPTURE_PLAN.sha256,
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
        "capture_plan.json",
    )
    contracts = output / "contracts"
    contracts.mkdir()
    for name in contract_names:
        shutil.copy2(SOURCE_ROOT / "qa" / name, contracts / name)

    contact_sheets = make_contact_sheets(output, public_isolation, archive, profile_id)
    legacy_reports = bool(isolation["legacy_unversioned_capture_reports"])
    write_json(output / "capture-evidence-manifest.json", {
        "schema_version": 3,
        "release": RELEASE,
        "profile": profile_id,
        "capture_plan_sha256": CAPTURE_PLAN.sha256,
        "status": "reconstructed-legacy" if legacy_reports else "passed",
        "package": {
            "path": packaged.relative_to(output).as_posix(),
            "sha256": candidate_hash,
            "member_count": 24,
            "source_archive_byte_parity": "passed",
        },
        "native_captures": counts,
        "contact_sheets": {
            "overview": contact_sheets["overview_count"],
            "details": contact_sheets["detail_sheet_count"],
            "capture_details": contact_sheets["capture_detail_sheet_count"],
            "reports": contact_sheets["report_sheet_count"],
            "total": len(contact_sheets["sheets"]),
            "exact_once_detail_coverage": contact_sheets["each_native_capture_in_details_exactly_once"],
            "repository_tracking": "current-only",
        },
        "runtime_plan_identity": (
            "legacy-unversioned-explicitly-accepted"
            if legacy_reports
            else "passed"
        ),
        "isolation": public_isolation,
        "restart_persistence": "passed",
        "deferred_unrun": [
            "voiceover_review", "windows_validation", "linux_validation",
            "forced_colors_review", "device_pixel_ratio_1", "os_display_scaling",
        ],
    })
    write_readme(
        output,
        candidate_hash,
        profile_id,
        contact_sheets,
        legacy_unversioned_reports=legacy_reports,
    )
    return output


def assemble(
    run_root: Path,
    candidate: Path,
    output: Path,
    profile_id: str = "full",
    *,
    allow_legacy_unversioned_reports: bool = False,
) -> Path:
    """Assemble off to the side, then publish the complete directory atomically."""

    run_root = run_root.resolve(strict=True)
    candidate = candidate.resolve(strict=True)
    output = output.resolve()
    require(not output.exists(), "refusing to overwrite release evidence: {}".format(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(
        prefix=".{}-assembling-".format(output.name),
        dir=str(output.parent),
    ))
    staged_output = staging_root / "evidence"
    try:
        _assemble_to_directory(
            run_root,
            candidate,
            staged_output,
            profile_id,
            allow_legacy_unversioned_reports=allow_legacy_unversioned_reports,
        )
        require(
            not output.exists(),
            "release evidence output appeared during assembly: {}".format(output),
        )
        staged_output.rename(output)
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise
    try:
        staging_root.rmdir()
    except OSError:
        pass
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--profile", choices=CAPTURE_PLAN.profile_ids, default="full")
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Fresh destination; existing or partially published evidence is never overwritten.",
    )
    parser.add_argument(
        "--allow-legacy-unversioned-reports",
        action="store_true",
        help="Reconstruct externally archived full-profile evidence created before plan hashes; never use for a new capture.",
    )
    args = parser.parse_args()
    try:
        output = assemble(
            args.run_root,
            args.candidate,
            args.output.resolve(),
            args.profile,
            allow_legacy_unversioned_reports=args.allow_legacy_unversioned_reports,
        )
    except Exception as exc:
        print("ERROR: {}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
