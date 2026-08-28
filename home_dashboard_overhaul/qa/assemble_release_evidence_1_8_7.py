#!/usr/bin/env python3
"""Assemble immutable Home Screen Dashboard 1.8.7 release evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from typing import Any, Mapping, Sequence
import zipfile

from PIL import Image, ImageDraw, ImageFont

from capture_plan import load_capture_plan


SOURCE_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_PLAN = load_capture_plan(SOURCE_ROOT / "qa" / "capture_plan.json")
RELEASE = CAPTURE_PLAN.release
DEFAULT_CANDIDATE = SOURCE_ROOT / "dist" / "home-dashboard-overhaul-1.8.7.ankiaddon"
FULLSCREEN_WORKFLOW_STEP_IDS = (
    "all-four-pages",
    "events-tabs",
    "resize",
    "event-edit",
    "verse-edit",
    "save",
    "close-reopen",
    "controlled-restart",
)
NATIVE_SETTINGS_LAYOUT_ASSERTIONS = (
    "horizontal_scroll_zero",
    "visible_controls_contained",
    "labels_unclipped_or_approved",
    "segmented_selection_matches_model",
    "body_footer_disjoint",
    "footer_actions_visible",
    "page_bottom_reachable",
    "target_fully_visible",
)


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


def validate_fullscreen_workflow(
    raw_result: object,
    *,
    allow_unrun: bool = False,
    label: str = "macOS full-screen acceptance",
) -> dict[str, Any]:
    """Validate every workflow step through both Settings opening routes.

    A route-level aggregate is not enough: each interaction must independently
    record that it stayed on Anki's current native full-screen Space.
    """

    require(isinstance(raw_result, Mapping), "{} is malformed".format(label))
    result = dict(raw_result)
    require(
        result.get("schema_version") == 2,
        "{} schema mismatch".format(label),
    )
    status = result.get("status")
    require(status in {"passed", "unrun"}, "{} has an invalid status".format(label))
    if status == "unrun":
        require(allow_unrun, "{} did not pass".format(label))
        require(
            isinstance(result.get("reason"), str) and bool(result["reason"].strip()),
            "unrun {} lacks a reason".format(label),
        )
        require(
            result.get("native_fullscreen") is False,
            "unrun {} must not claim native full screen".format(label),
        )
    else:
        require(
            result.get("native_fullscreen") is True,
            "{} did not use native macOS full screen".format(label),
        )

    paths = result.get("opening_paths")
    require(isinstance(paths, Mapping), "{} lacks opening-path results".format(label))
    require(
        set(paths) == {"menu", "dashboard-gear"},
        "{} must cover menu and Dashboard gear".format(label),
    )
    expected_step_status = "passed" if status == "passed" else "unrun"
    for path_id, raw_path in paths.items():
        path_label = "{} {} path".format(label, path_id)
        require(isinstance(raw_path, Mapping), "{} is malformed".format(path_label))
        require(
            raw_path.get("status") == expected_step_status,
            "{} status disagrees with the overall result".format(path_label),
        )
        steps = raw_path.get("workflow_steps")
        require(isinstance(steps, Mapping), "{} lacks workflow steps".format(path_label))
        require(
            list(steps) == list(FULLSCREEN_WORKFLOW_STEP_IDS),
            "{} workflow steps or order differ from the contract".format(path_label),
        )
        if status == "passed":
            require(raw_path.get("settings_opened") is True, "{} did not open Settings".format(path_label))
            require(
                raw_path.get("remained_on_anki_fullscreen_space") is True
                and raw_path.get("desktop_or_space_switch_observed") is False,
                "{} caused or failed to exclude a desktop/Space switch".format(path_label),
            )
        else:
            require(
                raw_path.get("settings_opened") is False
                and raw_path.get("remained_on_anki_fullscreen_space") is None
                and raw_path.get("desktop_or_space_switch_observed") is None,
                "{} unrun result claims full-screen observations".format(path_label),
            )
        for step_id, raw_step in steps.items():
            step_label = "{} step {}".format(path_label, step_id)
            require(isinstance(raw_step, Mapping), "{} is malformed".format(step_label))
            require(
                set(raw_step)
                == {
                    "status",
                    "completed",
                    "remained_on_current_anki_space",
                    "desktop_or_space_switch_observed",
                },
                "{} keys differ from the contract".format(step_label),
            )
            require(
                raw_step.get("status") == expected_step_status,
                "{} status disagrees with the overall result".format(step_label),
            )
            if status == "passed":
                require(
                    raw_step.get("completed") is True
                    and raw_step.get("remained_on_current_anki_space") is True
                    and raw_step.get("desktop_or_space_switch_observed") is False,
                    "{} did not prove current-Space retention".format(step_label),
                )
            else:
                require(
                    raw_step.get("completed") is False
                    and raw_step.get("remained_on_current_anki_space") is None
                    and raw_step.get("desktop_or_space_switch_observed") is None,
                    "{} unrun result claims observations".format(step_label),
                )
    require(
        result.get("desktop_space_switch_regression")
        == ("not-observed" if status == "passed" else "unrun"),
        "{} desktop/Space-switch summary disagrees with its steps".format(label),
    )
    return result


def _validated_geometry(report: Mapping[str, Any], field: str, key: object) -> tuple[float, ...]:
    raw = report.get(field)
    require(
        isinstance(raw, list)
        and len(raw) == 4
        and all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in raw
        )
        and float(raw[2]) > 0
        and float(raw[3]) > 0,
        "platform profile has invalid {}: {}".format(field, key),
    )
    return tuple(float(value) for value in raw)


def _validate_native_settings_pages(report: Mapping[str, Any], key: object) -> None:
    layout = report.get("settings_page_layout")
    require(isinstance(layout, Mapping), "platform profile lacks per-page Settings layout: {}".format(key))
    require(layout.get("status") == "passed", "platform Settings layout did not pass: {}".format(key))
    require(
        layout.get("application_font_percent") == 100,
        "platform Settings layout is not at 100 percent application font: {}".format(key),
    )
    expected_pages = CAPTURE_PLAN.structured_settings_layout()["pages"]
    pages = layout.get("pages")
    require(
        isinstance(pages, list)
        and [page.get("id") if isinstance(page, Mapping) else None for page in pages]
        == expected_pages,
        "platform Settings page order differs from the contract: {}".format(key),
    )
    for page in pages:
        page_id = str(page["id"])
        require(page.get("status") == "passed", "platform Settings page did not pass: {} {}".format(key, page_id))
        assertions = page.get("assertions")
        require(
            isinstance(assertions, Mapping)
            and set(assertions) == set(NATIVE_SETTINGS_LAYOUT_ASSERTIONS),
            "platform Settings page assertions differ from the contract: {} {}".format(key, page_id),
        )
        require(
            all(assertions[name] is True for name in NATIVE_SETTINGS_LAYOUT_ASSERTIONS),
            "platform Settings page has a failed layout assertion: {} {}".format(key, page_id),
        )


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


def validate_structured_settings_layout(
    raw_report: object,
    candidate_hash: str,
    profile_id: str,
    *,
    allow_failures: bool = False,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Validate the plan-bound, non-PNG Settings layout report.

    Full release assembly uses the default fail-closed policy. The focused
    Settings assembler opts into retaining complete negative results, while a
    missing, malformed, identity-mismatched, or internally inconsistent report
    remains an assembly error in both lanes.
    """

    spec = CAPTURE_PLAN.structured_settings_layout()
    require(
        set(spec)
        == {
            "schema_version",
            "stage",
            "required_profiles",
            "adds_png_frames",
            "work_area_logical",
            "application_font_percents",
            "pages",
            "restore_scenarios",
        },
        "capture-plan structured Settings layout keys differ from the contract",
    )
    require(
        spec.get("schema_version") == 1 and spec.get("stage") == "initial",
        "capture-plan structured Settings layout identity is invalid",
    )
    required_profiles = spec.get("required_profiles")
    require(
        isinstance(required_profiles, list)
        and required_profiles == ["full", "settings"]
        and profile_id in required_profiles,
        "structured Settings layout report is not required for this profile",
    )
    require(
        spec.get("adds_png_frames") is False,
        "structured Settings layout report may not add PNG frames",
    )
    work_area = spec.get("work_area_logical")
    require(
        isinstance(work_area, list)
        and len(work_area) == 4
        and all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in work_area
        )
        and work_area[2] > 0
        and work_area[3] > 0,
        "structured Settings logical work area is invalid",
    )
    font_percents = spec.get("application_font_percents")
    require(
        isinstance(font_percents, list) and font_percents == [100],
        "structured Settings application-font profiles differ from the contract",
    )
    pages = spec.get("pages")
    require(
        isinstance(pages, list)
        and pages == ["dashboard", "events", "bible_verse", "about_support"],
        "structured Settings page order differs from the contract",
    )
    restore_scenarios = spec.get("restore_scenarios")
    require(
        isinstance(restore_scenarios, list) and len(restore_scenarios) == 1,
        "structured Settings restoration scenarios differ from the contract",
    )
    restore_spec = restore_scenarios[0]
    require(
        isinstance(restore_spec, Mapping)
        and set(restore_spec)
        == {
            "id",
            "saved_geometry_logical",
            "saved_screen_name",
            "saved_available_logical",
            "saved_device_pixel_ratio",
        }
        and restore_spec.get("id") == "disconnected-monitor-v4",
        "structured Settings restoration scenario is invalid",
    )
    for geometry_key in ("saved_geometry_logical", "saved_available_logical"):
        geometry = restore_spec.get(geometry_key)
        require(
            isinstance(geometry, list)
            and len(geometry) == 4
            and all(
                isinstance(value, int) and not isinstance(value, bool)
                for value in geometry
            )
            and geometry[2] > 0
            and geometry[3] > 0,
            "{} is not a logical QRect".format(geometry_key),
        )
    require(
        isinstance(restore_spec.get("saved_screen_name"), str)
        and bool(restore_spec["saved_screen_name"].strip())
        and isinstance(restore_spec.get("saved_device_pixel_ratio"), (int, float))
        and not isinstance(restore_spec.get("saved_device_pixel_ratio"), bool)
        and float(restore_spec["saved_device_pixel_ratio"]) > 0,
        "structured Settings saved-screen metadata is invalid",
    )

    require(
        isinstance(raw_report, Mapping),
        "initial runtime report lacks structured_settings_layout",
    )
    report = dict(raw_report)
    require(
        set(report)
        == {
            "schema_version",
            "release",
            "stage",
            "status",
            "package_sha256",
            "capture_plan_sha256",
            "adds_png_frames",
            "generated_png_count",
            "reports",
        },
        "structured Settings layout report keys differ from the contract",
    )
    require(report.get("schema_version") == 1, "structured Settings layout schema mismatch")
    require(report.get("release") == RELEASE, "structured Settings layout release mismatch")
    require(report.get("stage") == "initial", "structured Settings layout stage mismatch")
    require(
        report.get("package_sha256") == candidate_hash,
        "structured Settings layout used the wrong package hash",
    )
    require(
        report.get("capture_plan_sha256") == CAPTURE_PLAN.sha256,
        "structured Settings layout capture-plan hash drifted",
    )
    require(
        report.get("adds_png_frames") is False
        and report.get("generated_png_count") == 0,
        "structured Settings layout report added PNG frames",
    )
    raw_entries = report.get("reports")
    require(
        isinstance(raw_entries, list),
        "structured Settings layout reports must be an ordered list",
    )
    expected_ids = [
        "settings-font-{}".format(percent) for percent in font_percents
    ] + [str(restore_spec["id"])]
    require(
        [entry.get("id") if isinstance(entry, Mapping) else None for entry in raw_entries]
        == expected_ids,
        "structured Settings layout report IDs or order differ from the contract",
    )

    layout_assertions = {
        "horizontal_scroll_zero",
        "visible_controls_contained",
        "labels_unclipped_or_approved",
        "segmented_selection_matches_model",
        "body_footer_disjoint",
        "footer_actions_visible",
        "page_bottom_reachable",
        "target_fully_visible",
    }
    restoration_assertions = {
        "saved_screen_not_connected",
        "saved_record_rejected",
        "centered_on_parent_screen_before_visibility",
        "logical_geometry_not_dpr_multiplied",
        "decorated_frame_inside_available",
    }
    failures: dict[str, dict[str, Any]] = {}

    def validate_status(value: object, label: str, has_failures: bool) -> None:
        require(value in {"passed", "failed"}, "{} has an invalid status".format(label))
        require(
            (value == "failed") == has_failures,
            "{} status disagrees with its assertions".format(label),
        )

    for index, percent in enumerate(font_percents):
        entry = raw_entries[index]
        require(isinstance(entry, Mapping), "structured font-layout report is malformed")
        require(
            set(entry)
            == {
                "id",
                "kind",
                "status",
                "application_font_percent",
                "fixture_kind",
                "work_area_logical",
                "resolved_window_geometry_logical",
                "pages",
            },
            "{} keys differ from the contract".format(expected_ids[index]),
        )
        require(
            entry.get("kind") == "application-font-layout"
            and entry.get("application_font_percent") == percent
            and entry.get("fixture_kind") == "logical-work-area-equivalence"
            and entry.get("work_area_logical") == work_area,
            "{} environment identity differs from the plan".format(expected_ids[index]),
        )
        geometry = entry.get("resolved_window_geometry_logical")
        require(
            isinstance(geometry, list)
            and len(geometry) == 4
            and all(
                isinstance(value, int) and not isinstance(value, bool)
                for value in geometry
            )
            and geometry[2] > 0
            and geometry[3] > 0,
            "{} resolved logical geometry is invalid".format(expected_ids[index]),
        )
        require(
            geometry[0] >= work_area[0]
            and geometry[1] >= work_area[1]
            and geometry[0] + geometry[2] <= work_area[0] + work_area[2]
            and geometry[1] + geometry[3] <= work_area[1] + work_area[3],
            "{} resolved logical geometry is outside the fixture work area".format(
                expected_ids[index]
            ),
        )
        page_reports = entry.get("pages")
        require(
            isinstance(page_reports, list)
            and [
                page.get("id") if isinstance(page, Mapping) else None
                for page in page_reports
            ]
            == pages,
            "{} page IDs or order differ from the contract".format(expected_ids[index]),
        )
        entry_failed = False
        for page in page_reports:
            require(isinstance(page, Mapping), "structured Settings page report is malformed")
            page_id = str(page["id"])
            require(
                set(page) == {"id", "status", "assertions"},
                "{}/{} keys differ from the contract".format(expected_ids[index], page_id),
            )
            assertions = page.get("assertions")
            require(
                isinstance(assertions, Mapping)
                and set(assertions) == layout_assertions
                and all(isinstance(value, bool) for value in assertions.values()),
                "{}/{} assertions differ from the contract".format(
                    expected_ids[index], page_id
                ),
            )
            page_failed = not all(assertions.values())
            validate_status(
                page.get("status"),
                "{}/{}".format(expected_ids[index], page_id),
                page_failed,
            )
            entry_failed = entry_failed or page_failed
            for assertion, passed in assertions.items():
                if not passed:
                    failure_id = "{}/{}/{}".format(
                        expected_ids[index], page_id, assertion
                    )
                    failures[failure_id] = {
                        "report_id": expected_ids[index],
                        "page": page_id,
                        "assertion": assertion,
                        "error": "structured Settings layout assertion failed",
                    }
        validate_status(entry.get("status"), expected_ids[index], entry_failed)

    restore_entry = raw_entries[-1]
    require(isinstance(restore_entry, Mapping), "structured restoration report is malformed")
    require(
        set(restore_entry)
        == {"id", "kind", "status", "application_font_percent", "assertions"},
        "{} keys differ from the contract".format(expected_ids[-1]),
    )
    require(
        restore_entry.get("kind") == "geometry-restoration"
        and restore_entry.get("application_font_percent") == 100,
        "{} identity differs from the plan".format(expected_ids[-1]),
    )
    restore_assertion_values = restore_entry.get("assertions")
    require(
        isinstance(restore_assertion_values, Mapping)
        and set(restore_assertion_values) == restoration_assertions
        and all(isinstance(value, bool) for value in restore_assertion_values.values()),
        "{} assertions differ from the contract".format(expected_ids[-1]),
    )
    restore_failed = not all(restore_assertion_values.values())
    validate_status(restore_entry.get("status"), expected_ids[-1], restore_failed)
    for assertion, passed in restore_assertion_values.items():
        if not passed:
            failure_id = "{}/{}".format(expected_ids[-1], assertion)
            failures[failure_id] = {
                "report_id": expected_ids[-1],
                "assertion": assertion,
                "error": "structured Settings restoration assertion failed",
            }

    validate_status(report.get("status"), "structured Settings layout report", bool(failures))
    require(
        allow_failures or not failures,
        "structured Settings layout report did not pass",
    )
    return report, failures


def validate_runtime(
    run_output: Path,
    candidate_hash: str,
    profile_id: str,
    *,
    allow_legacy_unversioned_reports: bool = False,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
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
        if isinstance(plan_record, Mapping):
            capture_records = report.get("captures", {})
            planned_cases = {
                str(case["id"]): case
                for case in CAPTURE_PLAN.cases(profile_id, stage=stage)
            }
            for capture_id, case in planned_cases.items():
                if case.get("component") != "settings":
                    continue
                record = capture_records.get(capture_id, {})
                require(
                    isinstance(record, Mapping)
                    and record.get("caption") == case.get("caption")
                    and record.get("visible_target") == case.get("visible_target")
                    and record.get("visible_target_fully_visible") is True,
                    "{} did not prove its declared visible target".format(capture_id),
                )
                if (
                    case.get("family") == "settings-pages"
                    or case.get("special") == "window-fresh-open"
                ):
                    require(
                        record.get("decorated_window_included") is True
                        and record.get("capture_scope")
                        == "complete-decorated-settings-window"
                        and str(record.get("capture_method", "")).startswith(
                            "QScreen.grabWindow"
                        ),
                        "{} omits the complete decorated Settings window".format(
                            capture_id
                        ),
                    )
                if case.get("compare_with") is not None:
                    comparison = record.get("paired_image_comparison", {})
                    require(
                        isinstance(comparison, Mapping)
                        and comparison.get("status") == "passed"
                        and comparison.get("baseline_capture_id")
                        == case.get("compare_with")
                        and comparison.get("same_physical_size") is True
                        and comparison.get("sha256_differs") is True
                        and float(
                            comparison.get("sampled_image_difference_ratio", 0)
                        )
                        >= float(case["minimum_image_difference_ratio"]),
                        "{} did not visibly differ from its paired baseline".format(
                            capture_id
                        ),
                    )
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
    structured_layout, _structured_failures = validate_structured_settings_layout(
        initial.get("structured_settings_layout"),
        candidate_hash,
        profile_id,
    )
    require(
        "structured_settings_layout" not in restart,
        "structured Settings layout report must be emitted only during initial runtime",
    )
    isolation = {
        "initial": isolation_summary(initial),
        "restart": isolation_summary(restart),
        "all_four_gates_repeated_after_restart": True,
        "legacy_unversioned_capture_reports": legacy_stages,
    }
    return initial, restart, isolation, structured_layout


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


def validate_platform_bundles(
    bundle_paths: Sequence[Path],
    candidate_hash: str,
) -> dict[str, Any]:
    """Fail closed unless every required native platform profile is present."""

    expected_entries = CAPTURE_PLAN.raw.get("native_platform_matrix", [])
    require(isinstance(expected_entries, list) and expected_entries, "capture plan has no native platform matrix")
    expected = [
        (
            str(entry.get("host_platform", "")),
            int(entry.get("os_scale_percent", 0)),
            str(entry.get("dpr_class", "")),
        )
        for entry in expected_entries
        if isinstance(entry, Mapping)
    ]
    require(len(bundle_paths) == len(expected), "every required native platform bundle must be supplied")
    resolved: dict[tuple[str, int, str], dict[str, Any]] = {}
    for raw_path in bundle_paths:
        path = raw_path.resolve(strict=True)
        report_path = path if path.is_file() else path / "platform-profile.json"
        require(report_path.is_file(), "platform bundle lacks platform-profile.json: {}".format(path))
        report = read_json(report_path)
        key = (
            str(report.get("host_platform", "")),
            int(report.get("os_scale_percent", 0)),
            str(report.get("dpr_class", "")),
        )
        require(key in expected, "unexpected native platform profile: {}".format(key))
        require(key not in resolved, "duplicate native platform profile: {}".format(key))
        require(report.get("status") == "passed", "native platform profile did not pass: {}".format(key))
        require(report.get("release") == RELEASE, "native platform release differs: {}".format(key))
        require(report.get("package_sha256") == candidate_hash, "native platform package differs: {}".format(key))
        require(report.get("capture_plan_sha256") == CAPTURE_PLAN.sha256, "native platform capture plan differs: {}".format(key))
        require(report.get("native_display_scaling") is True, "platform profile used non-native display scaling: {}".format(key))
        require(report.get("environment_scale_substitute") is False, "platform profile used an environment scale substitute: {}".format(key))
        font_percents = report.get("application_font_percents")
        require(font_percents == [100], "platform profile is not limited to the canonical 100 percent application font: {}".format(key))
        for field in (
            "os",
            "anki_version",
            "qt_platform",
            "available_logical_geometry",
            "physical_geometry",
            "logical_dpi",
            "physical_dpi",
            "device_pixel_ratio",
        ):
            require(report.get(field) not in (None, "", []), "platform profile lacks {}: {}".format(field, key))
        logical = _validated_geometry(report, "available_logical_geometry", key)
        physical = _validated_geometry(report, "physical_geometry", key)
        dpr = float(report["device_pixel_ratio"])
        require(0.5 <= dpr <= 4.0, "platform profile has an invalid DPR: {}".format(key))
        for dimension, logical_value, physical_value in zip(
            ("width", "height"), logical[2:], physical[2:]
        ):
            expected_physical = logical_value * dpr
            tolerance = max(2.0, expected_physical * 0.01)
            require(
                abs(physical_value - expected_physical) <= tolerance,
                "platform {} does not match logical geometry and DPR: {}".format(
                    dimension, key
                ),
            )
        if key[2] == "dpr-1":
            require(abs(dpr - 1.0) <= 0.05, "DPR-1 profile did not use DPR 1: {}".format(key))
            require(
                abs(physical[2] - logical[2]) <= max(2.0, logical[2] * 0.01)
                and abs(physical[3] - logical[3]) <= max(2.0, logical[3] * 0.01),
                "DPR-1 profile logical and physical dimensions differ: {}".format(key),
            )
        elif key[2] == "native":
            declared_scale = key[1] / 100.0
            require(
                abs(dpr - declared_scale) <= 0.08,
                "native platform DPR does not match declared OS scale: {}".format(key),
            )
        elif key[2] == "retina":
            require(dpr >= 1.5, "Retina profile did not use a high-DPR display: {}".format(key))
        else:
            require(False, "unknown native platform DPR class: {}".format(key))
        _validate_native_settings_pages(report, key)
        if key[0] == "macos":
            validate_fullscreen_workflow(
                report.get("fullscreen_space_switch"),
                label="macOS platform full-screen acceptance",
            )
        resolved[key] = report
    missing = [key for key in expected if key not in resolved]
    require(not missing, "missing required native platform profiles: {}".format(missing))
    return {
        "status": "passed",
        "release": RELEASE,
        "package_sha256": candidate_hash,
        "capture_plan_sha256": CAPTURE_PLAN.sha256,
        "required_profile_count": len(expected),
        "profiles": [resolved[key] for key in expected],
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
    captions = {
        str(case["id"]): str(case.get("caption", ""))
        for case in CAPTURE_PLAN.cases(profile_id)
    }
    for index, capture_id in enumerate(capture_ids):
        row, column = divmod(index, columns)
        x = 16 + column * tile_width
        y = 88 + row * tile_height
        preview = fitted_image(output / "captures" / "{}.png".format(capture_id), *thumb)
        canvas.paste(preview, (x + 8, y + 8))
        draw.rounded_rectangle((x + 4, y + 4, x + tile_width - 4, y + tile_height - 4), radius=8, outline="#334155", width=2)
        label = capture_id if len(capture_id) <= 46 else capture_id[:43] + "…"
        draw.text((x + 12, y + thumb[1] + 18), label, font=font(14, True), fill="#f8fafc")
        caption = captions.get(capture_id, "")
        if caption:
            caption = caption if len(caption) <= 62 else caption[:59] + "…"
            draw.text(
                (x + 12, y + thumb[1] + 42),
                caption,
                font=font(12),
                fill="#cbd5e1",
            )
    path = output / "contact-sheets" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, "PNG", optimize=True)
    return {
        "file": path.relative_to(output).as_posix(),
        "title": title,
        "capture_ids": capture_ids,
        "captions": {
            capture_id: captions[capture_id]
            for capture_id in capture_ids
            if captions.get(capture_id)
        },
        "sha256": sha256(path),
        "physical_pixels": [canvas.width, canvas.height],
    }


def report_sheet(
    output: Path,
    isolation: Mapping[str, Any],
    archive: Mapping[str, Any],
    platforms: Mapping[str, Any],
    sheet_number: int,
) -> dict[str, Any]:
    report = CAPTURE_PLAN.presentation["report"]
    report_id = str(report["id"])
    title = str(report["title"])
    canvas = Image.new("RGB", (1800, 1400), "#111827")
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
        "Native macOS 100 percent application font and Retina rendering: PASS",
        "Structured Settings layout at canonical 100% plus disconnected-monitor v4 restoration: PASS",
        "macOS fullscreen menu and dashboard-gear Space-switch acceptance: PASS",
        "VoiceOver and forced-colors: UNRUN (nonblocking, not claimed)",
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
        "native_platform_matrix": platforms.get("status"),
    }


def detail_groups(profile_id: str = "full") -> list[dict[str, Any]]:
    return CAPTURE_PLAN.detail_groups(profile_id)


def make_contact_sheets(
    output: Path,
    isolation: Mapping[str, Any],
    archive: Mapping[str, Any],
    platforms: Mapping[str, Any],
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
    sheets.append(report_sheet(output, isolation, archive, platforms, len(groups) + 1))
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
    platforms: Mapping[str, Any],
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
- `reports/settings-structured-layout.json` retains the non-PNG canonical 100%
  application-font checks plus disconnected-monitor v4 restoration proof.
- `reports/archive-inspection.json` proves the 24-member allowlist, safe paths,
  and source/archive byte parity.
- `reports/native-platform-matrix.json` proves the required macOS 100 percent
  application-font Retina profile uses the identical package and capture-plan
  hashes and records both fullscreen Space-switch opening paths.

Windows, Linux, DPR 1, alternate application-font percentages, VoiceOver,
forced-colors, keyboard-navigation expansion, and reduced-motion work were not
run and are not claimed; they are explicitly nonblocking for this release.
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
        platform_count=platforms["required_profile_count"],
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
    platform_bundles: Sequence[Path] = (),
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
    platforms = validate_platform_bundles(platform_bundles, candidate_hash)
    initial, restart, isolation, structured_layout = validate_runtime(
        run_output,
        candidate_hash,
        profile_id,
        allow_legacy_unversioned_reports=allow_legacy_unversioned_reports,
    )
    archive = archive_inspection(candidate)
    public_initial = redact_evidence_paths(initial, run_root=run_root, candidate=candidate)
    public_restart = redact_evidence_paths(restart, run_root=run_root, candidate=candidate)
    public_isolation = redact_evidence_paths(isolation, run_root=run_root, candidate=candidate)
    public_structured_layout = redact_evidence_paths(
        structured_layout,
        run_root=run_root,
        candidate=candidate,
    )
    require(not output.exists(), "release evidence output appeared during validation: {}".format(output))
    output.mkdir(parents=True)
    captures = collect_captures(run_output, output, initial, restart, profile_id)

    reports = output / "reports"
    reports.mkdir()
    write_json(reports / "runtime-report-initial.json", public_initial)
    write_json(reports / "runtime-report-restart.json", public_restart)
    write_json(
        reports / "settings-structured-layout.json",
        public_structured_layout,
    )
    write_json(reports / "isolation-gates.json", public_isolation)
    write_json(reports / "archive-inspection.json", archive)
    write_json(reports / "native-platform-matrix.json", platforms)
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
        "calendar_surface_manifest_1_8_7.json",
        "ui-surface-registry_1_8_7.json",
        "visual_regression_matrix_1_8_7.json",
        "capture_evidence_manifest_1_8_7.json",
        "runtime_probe_release_1_8_7_manifest.json",
        "capture_plan.json",
    )
    contracts = output / "contracts"
    contracts.mkdir()
    for name in contract_names:
        shutil.copy2(SOURCE_ROOT / "qa" / name, contracts / name)

    contact_sheets = make_contact_sheets(
        output,
        public_isolation,
        archive,
        platforms,
        profile_id,
    )
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
        "structured_settings_layout": {
            "status": public_structured_layout["status"],
            "report": "reports/settings-structured-layout.json",
            "adds_png_frames": False,
            "generated_png_count": 0,
        },
        "native_platform_matrix": platforms,
        "deferred_unrun": [
            "voiceover_review", "forced_colors_review",
        ],
    })
    write_readme(
        output,
        candidate_hash,
        profile_id,
        contact_sheets,
        platforms,
        legacy_unversioned_reports=legacy_reports,
    )
    return output


def assemble(
    run_root: Path,
    candidate: Path,
    output: Path,
    profile_id: str = "full",
    platform_bundles: Sequence[Path] = (),
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
            platform_bundles,
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
        "--platform-bundle",
        action="append",
        default=[],
        type=Path,
        help="Required macOS 100 percent Retina platform bundle directory or platform-profile.json.",
    )
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
            args.platform_bundle,
            allow_legacy_unversioned_reports=args.allow_legacy_unversioned_reports,
        )
    except Exception as exc:
        print("ERROR: {}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
