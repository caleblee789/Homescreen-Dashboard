#!/usr/bin/env python3
"""Assemble complete 100%-font Settings review sheets, retaining failures.

This is intentionally not a release-evidence assembler. It accepts a complete
focused Settings run whose per-frame layout assertions may have failed, keeps
those failures attached to the affected captures, and labels the resulting
evidence as non-release review material.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from typing import Any, Mapping, Sequence
import zipfile

from PIL import Image, ImageDraw

from assemble_release_evidence_1_8_7 import (
    CAPTURE_PLAN,
    RELEASE,
    font,
    make_capture_sheet,
    read_json,
    redact_evidence_paths,
    require,
    sha256,
    write_json,
)


SOURCE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = (
    SOURCE_ROOT / "dist" / "home-dashboard-overhaul-1.8.7.ankiaddon"
)


def _selected_ids(initial: Mapping[str, Any]) -> list[str]:
    plan_record = initial.get("capture_plan", {})
    require(isinstance(plan_record, Mapping), "initial report lacks capture-plan identity")
    selected = plan_record.get("selected_capture_ids")
    require(isinstance(selected, list) and selected, "review run has no Settings selection")
    ordered = list(CAPTURE_PLAN.ids("settings", include_ids=selected))
    require(len(ordered) == len(set(ordered)), "selected Settings IDs are not unique")
    require(
        ordered == list(CAPTURE_PLAN.ids("settings"))
        and len(ordered) == 41,
        "review run must contain the exact 41-case Settings profile",
    )
    cases = CAPTURE_PLAN.cases("settings", include_ids=ordered)
    require(
        all(int(case.get("font_percent", 100)) == 100 for case in cases),
        "review selection contains a non-100%-font case",
    )
    return ordered


def _validate_report(
    report: Mapping[str, Any],
    *,
    stage: str,
    selected: Sequence[str],
    candidate_hash: str,
) -> None:
    require(report.get("release") == RELEASE, "{} report release mismatch".format(stage))
    require(report.get("stage") == stage, "{} report stage mismatch".format(stage))
    require(
        report.get("capture_completion_status") == "complete",
        "{} Settings capture run is incomplete".format(stage),
    )
    plan_record = report.get("capture_plan", {})
    require(isinstance(plan_record, Mapping), "{} report lacks plan identity".format(stage))
    require(plan_record.get("profile") == "settings", "{} report is not the Settings profile".format(stage))
    require(plan_record.get("sha256") == CAPTURE_PLAN.sha256, "{} report plan hash drifted".format(stage))
    expected_stage = list(
        CAPTURE_PLAN.ids(
            "settings",
            stage=stage,
            include_ids=selected,
        )
    )
    require(
        list(plan_record.get("resolved_stage_capture_ids", ())) == expected_stage,
        "{} report capture order differs from the selected plan".format(stage),
    )
    require(
        set(report.get("captures", {})) == set(expected_stage),
        "{} report does not contain every selected capture".format(stage),
    )
    captures = report.get("captures", {})
    cases = {
        str(case["id"]): case
        for case in CAPTURE_PLAN.cases(
            "settings",
            stage=stage,
            include_ids=selected,
        )
    }
    for capture_id in expected_stage:
        record = captures.get(capture_id, {})
        require(isinstance(record, Mapping), "{} capture record is malformed".format(capture_id))
        require(
            record.get("settings_surface_verified") is True
            and float(record.get("settings_surface_match_ratio", 0)) >= 0.55,
            "{} did not visibly capture the Settings surface".format(capture_id),
        )
        if cases[capture_id].get("family") == "settings-pages":
            require(
                record.get("decorated_window_included") is True
                and record.get("capture_scope") == "complete-decorated-settings-window"
                and str(record.get("capture_method", "")).startswith("QScreen.grabWindow"),
                "{} does not contain the complete decorated Settings window".format(capture_id),
            )
    identity = report.get("identity", {})
    require(isinstance(identity, Mapping), "{} report lacks isolation identity".format(stage))
    candidate = identity.get("candidate", {})
    require(isinstance(candidate, Mapping), "{} report lacks candidate identity".format(stage))
    require(candidate.get("candidate_sha256") == candidate_hash, "{} report used another package".format(stage))
    require(candidate.get("member_count") == 24, "{} report package member count is not 24".format(stage))
    require(candidate.get("installed_member_parity") == "passed", "{} installed bytes drifted".format(stage))
    require(identity.get("processes_are_distinct") is True, "{} process isolation failed".format(stage))
    require(identity.get("window_title_matches_profile") is True, "{} window isolation failed".format(stage))
    require(
        identity.get("collection_inside_run_root") is True
        and identity.get("addons_inside_run_root") is True,
        "{} filesystem isolation failed".format(stage),
    )
    require(
        identity.get("sync_credentials_present") is False
        and identity.get("auto_sync") is False
        and identity.get("media_sync") is False,
        "{} sync isolation failed".format(stage),
    )


def _archive_summary(candidate: Path) -> dict[str, Any]:
    with zipfile.ZipFile(candidate) as archive:
        members = [info.filename for info in archive.infolist() if not info.is_dir()]
        require(len(members) == 24, "candidate archive does not have 24 members")
        for member in members:
            path = PurePosixPath(member)
            require(not path.is_absolute() and ".." not in path.parts, "unsafe archive path")
    return {
        "status": "passed",
        "sha256": sha256(candidate),
        "member_count": len(members),
        "safe_paths": True,
        "members": members,
    }


def _validate_fullscreen_report(
    path: Path,
    *,
    candidate_hash: str,
    allow_unrun: bool = False,
) -> dict[str, Any]:
    report = read_json(path.resolve(strict=True))
    expected_gate_ids = CAPTURE_PLAN.profile("settings").get(
        "required_structured_manual_results"
    )
    require(
        expected_gate_ids
        == ["macos-fullscreen-no-space-switch-menu-and-dashboard-gear"],
        "Settings profile full-screen acceptance requirement drifted",
    )
    require(report.get("schema_version") == 1, "full-screen report schema mismatch")
    require(report.get("id") == expected_gate_ids[0], "full-screen report id mismatch")
    require(report.get("release") == RELEASE, "full-screen report release mismatch")
    require(report.get("host_platform") == "macos", "full-screen report is not native macOS evidence")
    require(report.get("candidate_sha256") == candidate_hash, "full-screen report used another package")
    require(report.get("capture_plan_sha256") == CAPTURE_PLAN.sha256, "full-screen report plan hash drifted")
    paths = report.get("opening_paths")
    require(isinstance(paths, Mapping), "full-screen report lacks opening-path results")
    require(set(paths) == {"menu", "dashboard-gear"}, "full-screen report must cover menu and Dashboard gear")
    if report.get("status") == "unrun":
        require(
            allow_unrun,
            "macOS full-screen Space-switch acceptance did not pass",
        )
        require(
            isinstance(report.get("reason"), str) and report["reason"].strip(),
            "unrun full-screen report lacks a reason",
        )
        require(
            report.get("native_fullscreen") is False,
            "unrun full-screen report must not claim native full screen",
        )
        for path_id, result in paths.items():
            require(isinstance(result, Mapping), "{} full-screen result is malformed".format(path_id))
            require(
                result.get("status") == "unrun"
                and result.get("settings_opened") is False
                and result.get("remained_on_anki_fullscreen_space") is None
                and result.get("desktop_or_space_switch_observed") is None,
                "{} unrun result claims full-screen observations".format(path_id),
            )
        for check in (
            "all_four_pages",
            "events_tabs",
            "resize",
            "save_close_reopen",
            "hard_restart_recheck",
        ):
            require(
                report.get(check) is False,
                "unrun full-screen report claims {}".format(check),
            )
        require(
            report.get("desktop_space_switch_regression") == "unrun",
            "unrun desktop/Space-switch result is not explicit",
        )
        return report
    require(report.get("status") == "passed", "macOS full-screen Space-switch acceptance did not pass")
    require(report.get("native_fullscreen") is True, "full-screen report did not use native macOS full screen")
    for path_id, result in paths.items():
        require(isinstance(result, Mapping), "{} full-screen result is malformed".format(path_id))
        require(result.get("status") == "passed", "{} full-screen opening did not pass".format(path_id))
        require(result.get("settings_opened") is True, "{} did not open Settings".format(path_id))
        require(
            result.get("remained_on_anki_fullscreen_space") is True
            and result.get("desktop_or_space_switch_observed") is False,
            "{} caused or failed to exclude a desktop/Space switch".format(path_id),
        )
    for check in (
        "all_four_pages",
        "events_tabs",
        "resize",
        "save_close_reopen",
        "hard_restart_recheck",
    ):
        require(report.get(check) is True, "full-screen report did not pass {}".format(check))
    require(
        report.get("desktop_space_switch_regression") == "not-observed",
        "desktop/Space-switch regression was not explicitly excluded",
    )
    return report


def _copy_captures(
    output: Path,
    run_output: Path,
    reports: Sequence[Mapping[str, Any]],
    selected: Sequence[str],
) -> dict[str, dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    for report in reports:
        captures = report.get("captures", {})
        require(isinstance(captures, Mapping), "runtime captures must be an object")
        for capture_id, raw_record in captures.items():
            require(capture_id in selected, "runtime report contains an unselected capture")
            require(isinstance(raw_record, Mapping), "capture record must be an object")
            relative = PurePosixPath(str(raw_record.get("file", "")))
            require(
                not relative.is_absolute()
                and ".." not in relative.parts
                and relative.name == "{}.png".format(capture_id),
                "unsafe capture path for {}".format(capture_id),
            )
            source = run_output.joinpath(*relative.parts)
            require(source.is_file(), "missing native capture {}".format(capture_id))
            require(sha256(source) == raw_record.get("sha256"), "capture hash drifted")
            destination = output / "captures" / "{}.png".format(capture_id)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            record = dict(raw_record)
            record["file"] = destination.relative_to(output).as_posix()
            record["sha256"] = sha256(destination)
            combined[str(capture_id)] = record
    require(set(combined) == set(selected), "combined captures differ from the selection")
    return {capture_id: combined[capture_id] for capture_id in selected}


def _review_report_sheet(
    output: Path,
    *,
    sheet_number: int,
    candidate_hash: str,
    capture_count: int,
    failures: Mapping[str, Any],
    fullscreen_report: Mapping[str, Any],
) -> dict[str, Any]:
    canvas = Image.new("RGB", (1800, 1180), "#111827")
    draw = ImageDraw.Draw(canvas)
    draw.text((64, 54), "Settings review status", font=font(42, True), fill="#f8fafc")
    fullscreen_passed = fullscreen_report["status"] == "passed"
    lines = [
        ("Exact package SHA-256: {}".format(candidate_hash), "#f8fafc"),
        ("Archive: 24 allowlisted members and safe paths PASS", "#86efac"),
        ("Native Settings captures: {}/{} complete at 100% application font".format(capture_count, capture_count), "#86efac"),
        ("Initial and restart process, window, filesystem, and sync gates PASS", "#86efac"),
        ("Per-frame layout assertion failures: {}".format(len(failures)), "#fbbf24" if failures else "#86efac"),
        ("Alternate application-font capture: UNRUN by request", "#fbbf24"),
        ("Windows, Linux, DPR 1, and native OS scaling: UNRUN · RELEASE BLOCKED", "#f87171"),
        (
            "macOS full-screen menu + Dashboard gear: NO DESKTOP/SPACE SWITCH · PASS"
            if fullscreen_passed
            else "macOS full-screen menu + Dashboard gear: UNRUN BY USER DIRECTION · RELEASE BLOCKED",
            "#86efac" if fullscreen_passed else "#f87171",
        ),
        ("This sheet set is review evidence, not release approval.", "#f8fafc"),
    ]
    y = 145
    for line, color in lines:
        draw.text((80, y), line, font=font(23, "PASS" in line), fill=color)
        y += 62
    if failures:
        draw.text((80, y + 12), "Failed frame assertions", font=font(25, True), fill="#fbbf24")
        y += 62
        for capture_id, failure in list(failures.items())[:7]:
            message = str(failure.get("error", "")) if isinstance(failure, Mapping) else str(failure)
            if len(message) > 96:
                message = message[:93] + "…"
            draw.text((94, y), "{} · {}".format(capture_id, message), font=font(18), fill="#fde68a")
            y += 48
    path = output / "contact-sheets" / "contact-sheet-{:02d}-settings-review-status.png".format(sheet_number)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, "PNG", optimize=True)
    return {
        "file": path.relative_to(output).as_posix(),
        "title": "Settings review status",
        "capture_ids": [],
        "sha256": sha256(path),
        "physical_pixels": [canvas.width, canvas.height],
        "report_only": True,
    }


def _make_sheets(
    output: Path,
    *,
    selected: Sequence[str],
    candidate_hash: str,
    failures: Mapping[str, Any],
    fullscreen_report: Mapping[str, Any],
) -> dict[str, Any]:
    quality_status = (
        "review-failed"
        if failures
        else (
            "review-complete-nonrelease"
            if fullscreen_report["status"] == "passed"
            else "review-incomplete-nonrelease"
        )
    )
    overview = CAPTURE_PLAN.presentation["overview"]
    sheets = [
        make_capture_sheet(
            output,
            "contact-sheet-00-overview.png",
            "Settings 100% native review overview",
            list(selected),
            int(overview["columns"]),
            tuple(int(value) for value in overview["thumbnail"]),
            "settings-100-review",
        )
    ]
    selected_set = set(selected)
    covered: list[str] = []
    detail_number = 1
    for group in CAPTURE_PLAN.detail_groups("settings"):
        capture_ids = [
            capture_id
            for capture_id in group["capture_ids"]
            if capture_id in selected_set
        ]
        if not capture_ids:
            continue
        slug = "".join(
            character if character.isalnum() else "-"
            for character in str(group["title"]).casefold()
        ).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        sheets.append(
            make_capture_sheet(
                output,
                "contact-sheet-{:02d}-{}.png".format(detail_number, slug),
                str(group["title"]),
                capture_ids,
                int(group["columns"]),
                tuple(int(value) for value in group["thumbnail"]),
                "settings-100-review",
            )
        )
        covered.extend(capture_ids)
        detail_number += 1
    coverage = Counter(covered)
    require(
        set(coverage) == set(selected)
        and all(coverage[capture_id] == 1 for capture_id in selected),
        "detail sheets do not cover selected captures exactly once",
    )
    sheets.append(
        _review_report_sheet(
            output,
            sheet_number=detail_number,
            candidate_hash=candidate_hash,
            capture_count=len(selected),
            failures=failures,
            fullscreen_report=fullscreen_report,
        )
    )
    maximum_sheets = int(CAPTURE_PLAN.profile("settings")["maximum_contact_sheets"])
    require(
        len(sheets) <= maximum_sheets,
        "Settings review exceeds its {}-sheet ceiling".format(maximum_sheets),
    )
    index = {
        "schema_version": 2,
        "release": RELEASE,
        "profile": "settings-100-review",
        "capture_plan_sha256": CAPTURE_PLAN.sha256,
        "candidate_sha256": candidate_hash,
        "application_font_percent": [100],
        "native_capture_count": len(selected),
        "overview_count": 1,
        "capture_detail_sheet_count": detail_number - 1,
        "report_sheet_count": 1,
        "each_native_capture_in_details_exactly_once": True,
        "quality_status": quality_status,
        "release_ready": False,
        "settings_assertion_failure_count": len(failures),
        "manual_fullscreen_acceptance": {
            "status": fullscreen_report["status"],
            "opening_paths": sorted(fullscreen_report["opening_paths"]),
            "desktop_space_switch_regression": fullscreen_report[
                "desktop_space_switch_regression"
            ],
        },
        "sheets": sheets,
    }
    write_json(output / "contact-sheets" / "contact-sheet-index.json", index)
    return index


def assemble(
    run_root: Path,
    candidate: Path,
    fullscreen_report_path: Path,
    output: Path,
    *,
    allow_unrun_fullscreen: bool = False,
) -> dict[str, Any]:
    run_root = run_root.resolve(strict=True)
    candidate = candidate.resolve(strict=True)
    output = output.resolve()
    require(str(run_root).startswith("/private/tmp/anki-release-qa."), "run root is not disposable")
    require(not output.exists(), "refusing to overwrite review evidence")
    run_output = run_root / str(CAPTURE_PLAN.profile("settings")["output_directory"])
    initial = read_json(run_output / "runtime-report-initial.json")
    restart = read_json(run_output / "runtime-report-restart.json")
    selected = _selected_ids(initial)
    archive = _archive_summary(candidate)
    candidate_hash = str(archive["sha256"])
    fullscreen_report = _validate_fullscreen_report(
        fullscreen_report_path,
        candidate_hash=candidate_hash,
        allow_unrun=allow_unrun_fullscreen,
    )
    _validate_report(initial, stage="initial", selected=selected, candidate_hash=candidate_hash)
    _validate_report(restart, stage="restart", selected=selected, candidate_hash=candidate_hash)
    failures: dict[str, Any] = {}
    for report in (initial, restart):
        raw = report.get("settings_case_failures", {})
        if isinstance(raw, Mapping):
            failures.update({str(key): value for key, value in raw.items()})

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".hdo-settings-review-", dir=output.parent) as temporary:
        staging = Path(temporary) / output.name
        staging.mkdir()
        captures = _copy_captures(staging, run_output, (initial, restart), selected)
        reports = staging / "reports"
        reports.mkdir()
        write_json(reports / "archive-inspection.json", archive)
        write_json(reports / "settings-fullscreen-acceptance.json", fullscreen_report)
        write_json(
            reports / "runtime-report-initial.json",
            redact_evidence_paths(initial, run_root=run_root, candidate=candidate),
        )
        write_json(
            reports / "runtime-report-restart.json",
            redact_evidence_paths(restart, run_root=run_root, candidate=candidate),
        )
        quality_status = (
            "review-failed"
            if failures
            else (
                "review-complete-nonrelease"
                if fullscreen_report["status"] == "passed"
                else "review-incomplete-nonrelease"
            )
        )
        manifest = {
            "schema_version": 1,
            "release": RELEASE,
            "profile": "settings-100-review",
            "capture_plan_sha256": CAPTURE_PLAN.sha256,
            "candidate_sha256": candidate_hash,
            "application_font_percent": [100],
            "capture_count": len(captures),
            "capture_ids": list(captures),
            "settings_case_failures": failures,
            "manual_fullscreen_acceptance": fullscreen_report,
            "quality_status": quality_status,
            "release_ready": False,
            "captures": captures,
        }
        write_json(staging / "capture-manifest.json", manifest)
        sheets = _make_sheets(
            staging,
            selected=selected,
            candidate_hash=candidate_hash,
            failures=failures,
            fullscreen_report=fullscreen_report,
        )
        fullscreen_summary = (
            "The required exact-package macOS full-screen menu and Dashboard-gear checks "
            "passed without a desktop or Space switch."
            if fullscreen_report["status"] == "passed"
            else "The required exact-package macOS full-screen menu and Dashboard-gear checks "
            "were skipped by explicit user direction and remain unrun; no desktop/Space-switch "
            "pass is claimed."
        )
        (staging / "README.md").write_text(
            "# Home Screen Dashboard 1.8.7 Settings review evidence\n\n"
            "This directory contains {} native Settings captures at 100% application font "
            "and {} generated contact sheets for exact package `{}`.\n\n"
            "It is visual review evidence, not release approval. {} Alternate-font "
            "Settings capture was not run by request. Windows, Linux, DPR 1, and native OS scaling remain "
            "release-blocking and unclaimed. Per-frame failures "
            "are retained in `capture-manifest.json` and the runtime reports.\n".format(
                len(captures),
                len(sheets["sheets"]),
                candidate_hash,
                fullscreen_summary,
            ),
            encoding="utf-8",
        )
        staging.replace(output)
    return {
        "status": (
            "assembled-review"
            if fullscreen_report["status"] == "passed"
            else "assembled-review-incomplete"
        ),
        "output": str(output),
        "candidate_sha256": candidate_hash,
        "capture_count": len(selected),
        "contact_sheet_count": len(sheets["sheets"]),
        "settings_assertion_failure_count": len(failures),
        "fullscreen_space_switch_status": fullscreen_report["status"],
        "release_ready": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--fullscreen-report", required=True, type=Path)
    parser.add_argument(
        "--allow-unrun-fullscreen",
        action="store_true",
        help=(
            "Assemble explicitly non-release review sheets when the structured "
            "macOS full-screen acceptance result is unrun"
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = assemble(
            args.run_root,
            args.candidate,
            args.fullscreen_report,
            args.output,
            allow_unrun_fullscreen=args.allow_unrun_fullscreen,
        )
    except Exception as exc:
        print("ERROR: {}: {}".format(type(exc).__name__, exc))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
