#!/usr/bin/env python3
"""Validate the machine-readable corrected 1.8.0 UI contract.

This validator intentionally checks source/contract structure only.  Spoken
VoiceOver behavior, native Windows high-DPI rendering, and visual judgment stay
as explicit human acceptance gates.
"""

from __future__ import annotations

from itertools import product
import json
from pathlib import Path
import sys
from typing import List


ROOT = Path(__file__).resolve().parents[1]


def validate(root: Path = ROOT) -> List[str]:
    errors: List[str] = []
    manifest = json.loads(
        (root / "qa" / "calendar_surface_manifest.json").read_text(encoding="utf-8")
    )
    matrix = json.loads(
        (root / "qa" / "visual_regression_matrix_1_8_0.json").read_text(encoding="utf-8")
    )
    registry = json.loads(
        (root / "qa" / "ui-surface-registry.json").read_text(encoding="utf-8")
    )

    if manifest.get("release") != "1.8.0":
        errors.append("manifest release must be 1.8.0")
    if manifest.get("contract") != "final-color-system-refinement-2026-08-23":
        errors.append("manifest does not describe the final-release dashboard overhaul")
    if manifest.get("dashboard_order") != [
        "study_calendar",
        "summary_metrics",
        "bible_verse",
    ]:
        errors.append("dashboard hierarchy is not canonical")

    manifest_ids = [item.get("id") for item in manifest.get("canonical_surfaces", [])]
    registry_ids = [item.get("id") for item in registry.get("surfaces", [])]
    if len(manifest_ids) != 25 or len(set(manifest_ids)) != 25:
        errors.append("canonical surface registry must contain 25 unique IDs")
    if registry_ids != manifest_ids:
        errors.append("surface registry does not exactly mirror the authority manifest")

    criteria = manifest.get("acceptance_criteria", [])
    if [item.get("id") for item in criteria] != list(range(1, 43)):
        errors.append("acceptance criteria must contain the exact IDs 1 through 42")

    axes = matrix.get("axes", {})
    axis_names = ("theme", "mode", "view", "layout", "text_scale")
    try:
        expected = set(product(*(axes[name] for name in axis_names)))
    except (KeyError, TypeError):
        expected = set()
        errors.append("visual matrix axes are incomplete")
    actual = {
        tuple(case.get(name) for name in axis_names)
        for case in matrix.get("cases", [])
    }
    case_ids = [case.get("id") for case in matrix.get("cases", [])]
    if matrix.get("case_count") != 96 or len(case_ids) != 96:
        errors.append("visual matrix must contain exactly 96 cases")
    if len(set(case_ids)) != 96:
        errors.append("visual matrix case IDs must be unique")
    if actual != expected:
        errors.append("visual matrix is not the exact Cartesian product")

    compact_source = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in ("renderer.py", "web/dashboard.js", "web/dashboard.css")
    ).casefold()
    for forbidden in (
        "hdo-selected-date-panel",
        "hdo-date-details",
        "hdo-due-deck",
        "hdo-insight-preview",
        "card-answer-preview",
        "expand preview",
    ):
        if forbidden in compact_source:
            errors.append("superseded dashboard surface remains: {}".format(forbidden))

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print("ERROR: {}".format(error))
        return 1
    print("Revised UI contract: PASS (25 surfaces, 42 finalization criteria, 96 visual cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
