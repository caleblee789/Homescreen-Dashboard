#!/usr/bin/env python3
"""Validate the machine-readable Home Dashboard 1.8.1 UI contract.

This is a source-contract check. Exact-package native evidence is validated by
the release evidence assembler after the disposable Anki run.
"""

from __future__ import annotations

from itertools import product
import json
from pathlib import Path
import sys
from typing import List


ROOT = Path(__file__).resolve().parents[1]


def _read(root: Path, name: str) -> dict:
    value = json.loads((root / "qa" / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("{} must contain one JSON object".format(name))
    return value


def validate(root: Path = ROOT) -> List[str]:
    errors: List[str] = []
    manifest = _read(root, "calendar_surface_manifest_1_8_1.json")
    matrix = _read(root, "visual_regression_matrix_1_8_1.json")
    registry = _read(root, "ui-surface-registry_1_8_1.json")
    capture = _read(root, "capture_evidence_manifest_1_8_1.json")

    if manifest.get("release") != "1.8.1" or manifest.get("schema_version") != 7:
        errors.append("surface manifest must describe release 1.8.1 / schema 7")
    if manifest.get("contract") != "native-100-percent-refinement-2026-08-23":
        errors.append("surface manifest has the wrong governing contract")
    if manifest.get("dashboard_order") != [
        "study_calendar", "summary_metrics", "bible_verse"
    ]:
        errors.append("dashboard hierarchy is not canonical")

    manifest_ids = [item.get("id") for item in manifest.get("canonical_surfaces", [])]
    registry_ids = [item.get("id") for item in registry.get("surfaces", [])]
    if len(manifest_ids) < 38 or len(set(manifest_ids)) != len(manifest_ids):
        errors.append("canonical surfaces must contain at least 38 unique IDs")
    if registry_ids != manifest_ids or registry.get("exact_once") is not True:
        errors.append("surface registry does not exactly mirror the authority manifest")

    criteria = manifest.get("acceptance_criteria", [])
    if [item.get("id") for item in criteria] != list(range(1, 42)):
        errors.append("acceptance criteria must contain exact IDs 1 through 41")
    if any(not item.get("tags") or not str(item.get("requirement", "")).strip() for item in criteria):
        errors.append("every acceptance criterion needs tags and requirement text")

    axes = matrix.get("axes", {})
    try:
        expected = set(product(axes["theme"], axes["mode"], axes["view"]))
    except (KeyError, TypeError):
        expected = set()
        errors.append("primary visual matrix axes are incomplete")
    cases = matrix.get("cases", [])
    actual = {
        (case.get("theme"), case.get("mode"), case.get("view"))
        for case in cases if isinstance(case, dict)
    }
    case_ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if matrix.get("primary_case_count") != 16 or len(cases) != 16:
        errors.append("primary visual matrix must contain exactly 16 cases")
    if actual != expected or len(set(case_ids)) != 16:
        errors.append("primary visual matrix is not the exact theme/mode/view product")
    if any(case.get("text_scale") != 100 for case in cases):
        errors.append("every primary visual case must use 100 percent text scale")
    if matrix.get("deferred_scales_percent") != [125, 150]:
        errors.append("125 and 150 percent must remain explicitly deferred")

    if capture.get("primary_native_frames") != case_ids:
        errors.append("capture manifest primary frame order differs from the visual matrix")
    supplemental = capture.get("supplemental_frames", [])
    tags = {
        tag
        for case in list(cases) + list(supplemental)
        if isinstance(case, dict)
        for tag in case.get("tags", [])
    }
    missing_tags = sorted(set(capture.get("required_coverage_tags", [])) - tags)
    if missing_tags:
        errors.append("capture plan has uncovered tags: {}".format(", ".join(missing_tags)))
    references = capture.get("reference_inputs", [])
    if not references or any(
        item.get("may_count_as_acceptance_evidence") is not False
        or item.get("must_not_be_overwritten") is not True
        for item in references
    ):
        errors.append("reference inputs must be immutable calibration-only material")

    compact_source = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in ("renderer.py", "web/dashboard.js", "web/dashboard.css")
    ).casefold()
    for forbidden in (
        "hdo-selected-date-panel", "hdo-date-details", "hdo-due-deck",
        "hdo-insight-preview", "card-answer-preview", "expand preview",
        "transform: scale(", "zoom:",
    ):
        if forbidden in compact_source:
            errors.append("superseded or prohibited dashboard behavior remains: {}".format(forbidden))

    old_manifest = _read(root, "calendar_surface_manifest.json")
    old_matrix = _read(root, "visual_regression_matrix_1_8_0.json")
    if old_manifest.get("release") != "1.8.0" or old_matrix.get("release") != "1.8.0":
        errors.append("retained 1.8.0 contract history was modified")
    if not (root / "qa" / "release-evidence-1.8.0-2026-08-23").is_dir():
        errors.append("retained 1.8.0 release evidence is missing")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print("ERROR: {}".format(error))
        return 1
    print(
        "Revised UI contract: PASS "
        "(1.8.1 schema 7, 16 primary native cases, tagged supplemental evidence)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
