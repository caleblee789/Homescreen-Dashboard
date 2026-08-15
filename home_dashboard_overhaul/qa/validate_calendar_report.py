#!/usr/bin/env python3
"""Fail-closed validator for the calendar release-acceptance report.

The report is self-authored by a disposable Anki probe, so booleans in the
report are evidence to cross-check, not an artifact identity boundary.  This
validator therefore requires either an explicit release artifact or a
candidate hash pinned in the manifest and independently binds every reported
hash to that value.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Optional
from zipfile import BadZipFile, ZipFile


SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")


def _read(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("{} must contain a JSON object".format(path))
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _empty_list(value: Any) -> bool:
    return isinstance(value, list) and not value


def _manifest_candidate_sha256(manifest: Mapping[str, Any]) -> str:
    """Return an optional immutable hash pin from a manifest."""

    acceptance = manifest.get("acceptance", {})
    values = (
        manifest.get("candidate_sha256"),
        acceptance.get("candidate_sha256") if isinstance(acceptance, dict) else None,
    )
    for value in values:
        candidate = str(value or "").strip().lower()
        if SHA256_RE.fullmatch(candidate):
            return candidate
    return ""


def _expected_subset_failures(
    actual: Any,
    expected: Any,
    label: str,
) -> list[str]:
    """Compare a manifest-owned subset without constraining extra probe data."""

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return ["{} must be an object".format(label)]
        failures: list[str] = []
        for key, value in expected.items():
            child = "{}.{}".format(label, key)
            if key not in actual:
                failures.append("{} is missing".format(child))
            else:
                failures.extend(_expected_subset_failures(actual[key], value, child))
        return failures
    if actual != expected:
        return ["{} expected {!r}, found {!r}".format(label, expected, actual)]
    return []


def _artifact_binding(
    manifest: Mapping[str, Any],
    artifact_path: Optional[Path],
) -> tuple[str, list[str]]:
    failures: list[str] = []
    pinned_hash = _manifest_candidate_sha256(manifest)
    if artifact_path is None:
        if not pinned_hash:
            return "", [
                "candidate identity is unbound; pass --artifact or pin candidate_sha256 in the manifest"
            ]
        return pinned_hash, failures

    artifact_path = artifact_path.resolve()
    if not artifact_path.is_file():
        return "", ["candidate artifact is missing: {}".format(artifact_path)]
    actual_hash = _sha256(artifact_path)
    if pinned_hash and pinned_hash != actual_hash:
        failures.append("artifact sha256 does not match manifest candidate_sha256")

    acceptance = manifest.get("acceptance", {})
    if not isinstance(acceptance, dict):
        acceptance = {}
    if acceptance.get("require_artifact_sidecar") is True:
        sidecar = Path(str(artifact_path) + ".sha256")
        if not sidecar.is_file():
            failures.append("candidate sha256 sidecar is missing: {}".format(sidecar))
        else:
            tokens = sidecar.read_text(encoding="utf-8").strip().split()
            recorded = tokens[0].lower() if tokens else ""
            if not SHA256_RE.fullmatch(recorded):
                failures.append("candidate sha256 sidecar is malformed")
            elif recorded != actual_hash:
                failures.append("candidate sha256 sidecar does not match artifact bytes")
            if len(tokens) > 1 and Path(tokens[-1].lstrip("*")).name != artifact_path.name:
                failures.append("candidate sha256 sidecar names a different artifact")

    try:
        with ZipFile(artifact_path) as archive:
            packaged_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        if not isinstance(packaged_manifest, dict):
            failures.append("packaged manifest is not an object")
        else:
            expected_release = str(manifest.get("release", "")).strip()
            expected_package = str(manifest.get("package", "")).strip()
            if expected_release and packaged_manifest.get("human_version") != expected_release:
                failures.append(
                    "packaged release mismatch; expected {}, found {}".format(
                        expected_release,
                        packaged_manifest.get("human_version"),
                    )
                )
            if expected_package and packaged_manifest.get("package") != expected_package:
                failures.append(
                    "packaged add-on mismatch; expected {}, found {}".format(
                        expected_package,
                        packaged_manifest.get("package"),
                    )
                )
    except (BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        failures.append("candidate archive manifest could not be verified: {}".format(exc))

    return actual_hash, failures


def validate(
    manifest_path: Path,
    report_path: Path,
    artifact_path: Optional[Path] = None,
) -> list[str]:
    manifest = _read(manifest_path)
    report = _read(report_path)
    failures: list[str] = []

    bound_hash, binding_failures = _artifact_binding(manifest, artifact_path)
    failures.extend(binding_failures)

    if report.get("complete") is not True:
        failures.append("report is not complete")
    for field in ("errors", "failures", "warnings"):
        if not _empty_list(report.get(field)):
            failures.append("top-level {} must be present and empty".format(field))

    surfaces = manifest.get("visual_surfaces", [])
    if not isinstance(surfaces, list):
        surfaces = []
        failures.append("manifest visual_surfaces must be a list")
    expected = [str(item.get("id", "")) for item in surfaces if isinstance(item, dict)]
    captures = report.get("captures", [])
    if not isinstance(captures, list):
        captures = []
        failures.append("captures must be a list")
    actual = [str(item.get("id", "")) for item in captures if isinstance(item, dict)]
    if len(actual) != len(set(actual)):
        failures.append("duplicate capture ids")
    if actual != expected:
        missing = [value for value in expected if value not in actual]
        unexpected = [value for value in actual if value not in expected]
        failures.append(
            "capture order mismatch; missing={}; unexpected={}".format(missing, unexpected)
        )
    if report.get("surface_order") != expected:
        failures.append("reported surface_order does not match the manifest")
    acceptance = manifest.get("acceptance", {})
    if not isinstance(acceptance, dict):
        acceptance = {}
        failures.append("manifest acceptance must be an object")
    expected_count = int(acceptance.get("expected_capture_count", -1))
    if len(actual) != expected_count:
        failures.append("expected {} captures, found {}".format(expected_count, len(actual)))

    surface_by_id = {
        str(item.get("id", "")): item
        for item in surfaces
        if isinstance(item, dict)
    }
    for capture in captures:
        if not isinstance(capture, dict):
            failures.append("capture entry is not an object")
            continue
        capture_id = str(capture.get("id", ""))
        raw_path = str(capture.get("path", ""))
        path = Path(raw_path)
        if not path.is_absolute():
            path = report_path.parent / path
        if not raw_path or not path.is_file():
            failures.append("missing capture file for {}".format(capture_id))
        geometry = capture.get("geometry")
        if not isinstance(geometry, dict) or not geometry:
            failures.append("missing geometry for {}".format(capture_id))
        expected_geometry = surface_by_id.get(capture_id, {}).get("expected_geometry")
        if isinstance(expected_geometry, dict):
            failures.extend(
                _expected_subset_failures(
                    geometry,
                    expected_geometry,
                    "{} geometry".format(capture_id),
                )
            )
        for field in ("warnings", "failures"):
            if not _empty_list(capture.get(field)):
                failures.append(
                    "surface {} for {} must be present and empty".format(field, capture_id)
                )
        render_ms = capture.get("render_ms")
        if render_ms is None:
            failures.append("render time missing for {}".format(capture_id))
        else:
            try:
                if float(render_ms) > float(acceptance["maximum_representative_render_ms"]):
                    failures.append("render budget exceeded for {}".format(capture_id))
            except (KeyError, TypeError, ValueError):
                failures.append("invalid render time for {}".format(capture_id))
        if capture.get("horizontal_overflow") is not False:
            failures.append("horizontal overflow was not explicitly cleared for {}".format(capture_id))

    assertion_results = report.get("assertion_results", [])
    if not isinstance(assertion_results, list):
        assertion_results = []
        failures.append("assertion_results must be a list")
    assertion_pairs: list[tuple[str, str]] = []
    for item in assertion_results:
        if not isinstance(item, dict):
            failures.append("assertion result is not an object")
            continue
        pair = (str(item.get("matrix")), str(item.get("value")))
        assertion_pairs.append(pair)
        if item.get("passed") is not True:
            failures.append("assertion did not pass {}={}".format(*pair))
    if len(assertion_pairs) != len(set(assertion_pairs)):
        failures.append("duplicate assertion results")
    expected_assertions = {
        (str(matrix), str(value))
        for matrix, values in manifest.get("assertion_matrices", {}).items()
        for value in values
    }
    actual_assertions = set(assertion_pairs)
    for pair in sorted(expected_assertions - actual_assertions):
        failures.append("missing passing assertion {}={}".format(*pair))
    for pair in sorted(actual_assertions - expected_assertions):
        failures.append("unexpected assertion {}={}".format(*pair))

    identity = report.get("identity", {})
    if not isinstance(identity, dict):
        identity = {}
        failures.append("identity must be an object")
    for phase in ("initial", "restart"):
        phase_value = identity.get(phase, {})
        if not isinstance(phase_value, dict):
            phase_value = {}
        gates = acceptance.get("required_{}_identity_gates".format(phase), [])
        for gate in gates:
            if phase_value.get(gate) is not True:
                failures.append("{} identity gate failed: {}".format(phase, gate))
        if phase_value.get("all_gates") is not True:
            failures.append("{} aggregate identity gate failed".format(phase))

    report_hash = str(report.get("candidate_sha256", "")).lower()
    if not SHA256_RE.fullmatch(report_hash):
        failures.append("candidate sha256 is missing or malformed")
    elif bound_hash and report_hash != bound_hash:
        failures.append("report candidate sha256 does not match bound artifact")

    integrity = report.get("package_integrity", {})
    if not isinstance(integrity, dict):
        integrity = {}
        failures.append("package_integrity must be an object")
    integrity_hash = str(integrity.get("candidate_hash", "")).lower()
    if not SHA256_RE.fullmatch(integrity_hash):
        failures.append("package-integrity candidate hash is missing or malformed")
    elif bound_hash and integrity_hash != bound_hash:
        failures.append("package-integrity candidate hash does not match bound artifact")
    for field in acceptance.get("required_package_integrity_true", []):
        if integrity.get(field) is not True:
            failures.append("package integrity field is not true: {}".format(field))
    for field in acceptance.get("required_package_integrity_empty", []):
        if not _empty_list(integrity.get(field)):
            failures.append("package integrity field must be present and empty: {}".format(field))
    archive_file_count = integrity.get("archive_file_count")
    if not isinstance(archive_file_count, int) or isinstance(archive_file_count, bool) or archive_file_count <= 0:
        failures.append("package archive_file_count must be a positive integer")

    restart = report.get("restart", {})
    if not isinstance(restart, dict):
        restart = {}
        failures.append("restart must be an object")
    for field in acceptance.get("required_restart_true", []):
        if restart.get(field) is not True:
            failures.append("restart field is not true: {}".format(field))

    accessibility = report.get("accessibility", {})
    if not isinstance(accessibility, dict):
        accessibility = {}
        failures.append("accessibility must be an object")
    if accessibility.get("automated") != "passed":
        failures.append("automated accessibility checks did not pass")
    if manifest.get("accessibility", {}).get("human_required"):
        if accessibility.get("complete") is not False:
            failures.append("human VoiceOver boundary must remain explicitly incomplete")
        if accessibility.get("spoken_voiceover") not in {
            "human-required",
            "incomplete",
            "not-run",
            "unavailable",
        }:
            failures.append("spoken VoiceOver status is not recorded as human-required")
        if not str(accessibility.get("boundary", "")).strip():
            failures.append("human VoiceOver boundary is missing")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("calendar_surface_manifest.json"),
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        help="release .ankiaddon to hash and bind to the report",
    )
    args = parser.parse_args()
    try:
        failures = validate(args.manifest, args.report, args.artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failures = ["validator input error: {}".format(exc)]
    if failures:
        for failure in failures:
            print("FAIL: {}".format(failure))
        return 1
    print(
        "calendar automated surface report passed; "
        "spoken VoiceOver remains human-required and incomplete"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
