from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "qa" / "calendar_surface_manifest.json"
VALIDATOR_PATH = ROOT / "qa" / "validate_calendar_report.py"
CALENDAR_PROBE_PATH = ROOT / "qa" / "acceptance_probe_calendar_polish.py"
SETTINGS_PROBE_PATH = ROOT / "qa" / "settings_acceptance_probe.py"
REJECTED_ROOT = ROOT / "qa" / "live-ui-acceptance-1.5.1-calendar-polish-2026-08-13"


def _validator_module():
    spec = importlib.util.spec_from_file_location("hdo_calendar_report_validator", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load calendar report validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_artifact(root: Path, release: str) -> tuple[Path, str]:
    artifact = root / "home-dashboard-overhaul-{}.ankiaddon".format(release)
    with ZipFile(artifact, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "package": "home_dashboard_overhaul",
                    "name": "Home Dashboard - Overhaul",
                    "human_version": release,
                }
            ),
        )
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    Path(str(artifact) + ".sha256").write_text(
        "{}  {}\n".format(digest, artifact.name),
        encoding="utf-8",
    )
    return artifact, digest


def _merge_expected_geometry(surface: dict[str, object]) -> dict[str, object]:
    geometry: dict[str, object] = {"width": 1, "height": 1}
    expected = deepcopy(surface.get("expected_geometry", {}))
    if isinstance(expected, dict):
        geometry.update(expected)
    return geometry


class CalendarQaManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.validator = _validator_module()

    def _valid_report(self, root: Path, digest: str) -> dict[str, object]:
        captures = []
        for surface in self.manifest["visual_surfaces"]:
            image = root / "{}.png".format(surface["id"])
            image.write_bytes(b"png")
            captures.append(
                {
                    "id": surface["id"],
                    "path": image.name,
                    "geometry": _merge_expected_geometry(surface),
                    "warnings": [],
                    "failures": [],
                    "render_ms": 1,
                    "horizontal_overflow": False,
                }
            )
        assertions = [
            {"matrix": matrix, "value": value, "passed": True}
            for matrix, values in self.manifest["assertion_matrices"].items()
            for value in values
        ]
        gates = self.manifest["acceptance"]
        initial = {
            gate: True for gate in gates["required_initial_identity_gates"]
        }
        restart_identity = {
            gate: True for gate in gates["required_restart_identity_gates"]
        }
        initial["all_gates"] = True
        restart_identity["all_gates"] = True
        return {
            "candidate_sha256": digest,
            "complete": True,
            "errors": [],
            "failures": [],
            "warnings": [],
            "surface_order": [surface["id"] for surface in self.manifest["visual_surfaces"]],
            "captures": captures,
            "assertion_results": assertions,
            "identity": {"initial": initial, "restart": restart_identity},
            "package_integrity": {
                "candidate_hash": digest,
                "candidate_hash_matches": True,
                "source_archive_parity": True,
                "installed_archive_parity": True,
                "byte_mismatches": [],
                "source_mismatches": [],
                "unexpected_files": [],
                "archive_file_count": 1,
                "passed": True,
            },
            "restart": {
                "requested": True,
                "completed": True,
                "month_view_persisted": True,
                "schema_3_persisted": True,
            },
            "accessibility": {
                "automated": "passed",
                "spoken_voiceover": "unavailable",
                "complete": False,
                "boundary": "A spoken VoiceOver pass remains human-required and incomplete.",
            },
        }

    def _write_report(self, root: Path, report: dict[str, object]) -> Path:
        report_path = root / "report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return report_path

    def test_surface_contract_is_unique_ordered_and_complete(self) -> None:
        surfaces = self.manifest["visual_surfaces"]
        identifiers = [surface["id"] for surface in surfaces]
        self.assertEqual(self.manifest["schema_version"], 2)
        self.assertEqual(self.manifest["release"], "1.5.3")
        self.assertTrue(self.manifest["acceptance"]["require_artifact_sidecar"])
        self.assertEqual(self.manifest["acceptance"]["expected_capture_count"], 28)
        self.assertEqual(len(identifiers), self.manifest["acceptance"]["expected_capture_count"])
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(identifiers, sorted(identifiers))
        self.assertEqual(
            identifiers[20:],
            [
                "21-all-hidden-recovery",
                "22-partial-data-unavailable",
                "23-loading-state",
                "24-legacy-activation-required",
                "25-calendar-settings-desktop",
                "26-calendar-settings-intermediate",
                "27-events-empty-and-contextual",
                "28-events-active-archived-feedback",
            ],
        )
        special_surfaces = {
            surface["id"]: surface["expected_geometry"]["special"]
            for surface in surfaces[20:24]
        }
        self.assertTrue(special_surfaces["21-all-hidden-recovery"]["hiddenHeading"])
        self.assertEqual(
            special_surfaces["22-partial-data-unavailable"]["unavailableValueCount"],
            17,
        )
        self.assertTrue(special_surfaces["23-loading-state"]["spinnerPresent"])
        self.assertTrue(
            special_surfaces["24-legacy-activation-required"]["legacyNameVisible"]
        )
        self.assertEqual(self.manifest["assertion_matrices"]["week_start"], list(range(7)))
        self.assertEqual(self.manifest["assertion_matrices"]["month_rows"], [4, 5, 6])
        self.assertIn("literal-html", self.manifest["assertion_matrices"]["events"])
        self.assertIn("restart-persistence", self.manifest["assertion_matrices"]["data_state"])
        self.assertIn("spoken-voiceover-grid-navigation", self.manifest["accessibility"]["human_required"])

    def test_validator_passes_with_an_independently_bound_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact, digest = _write_artifact(root, self.manifest["release"])
            report_path = self._write_report(root, self._valid_report(root, digest))
            self.assertEqual(
                self.validator.validate(MANIFEST_PATH, report_path, artifact),
                [],
            )

    def test_manifest_hash_pin_is_an_allowed_artifact_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _artifact, digest = _write_artifact(root, self.manifest["release"])
            manifest = deepcopy(self.manifest)
            manifest["candidate_sha256"] = digest
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            report_path = self._write_report(root, self._valid_report(root, digest))
            self.assertEqual(self.validator.validate(manifest_path, report_path), [])

    def test_validator_fails_closed_for_missing_or_duplicate_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact, digest = _write_artifact(root, self.manifest["release"])
            report = self._valid_report(root, digest)
            captures = report["captures"]
            report["captures"] = captures[:-1] + [deepcopy(captures[-2])]
            report_path = self._write_report(root, report)
            failures = self.validator.validate(MANIFEST_PATH, report_path, artifact)
            self.assertTrue(any("duplicate capture ids" in failure for failure in failures))
            self.assertTrue(any("capture order mismatch" in failure for failure in failures))

    def test_validator_rejects_unbound_and_inconsistent_candidate_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact, digest = _write_artifact(root, self.manifest["release"])
            report = self._valid_report(root, digest)
            report_path = self._write_report(root, report)
            failures = self.validator.validate(MANIFEST_PATH, report_path)
            self.assertTrue(any("candidate identity is unbound" in failure for failure in failures))

            report["candidate_sha256"] = "0" * 64
            report["package_integrity"]["candidate_hash"] = "1" * 64
            report_path = self._write_report(root, report)
            failures = self.validator.validate(MANIFEST_PATH, report_path, artifact)
            self.assertTrue(any("report candidate sha256" in failure for failure in failures))
            self.assertTrue(any("package-integrity candidate hash" in failure for failure in failures))

    def test_validator_rejects_bad_or_missing_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact, digest = _write_artifact(root, self.manifest["release"])
            report_path = self._write_report(root, self._valid_report(root, digest))
            sidecar = Path(str(artifact) + ".sha256")
            sidecar.write_text("{}  wrong.ankiaddon\n".format(digest), encoding="utf-8")
            failures = self.validator.validate(MANIFEST_PATH, report_path, artifact)
            self.assertTrue(any("names a different artifact" in failure for failure in failures))
            sidecar.unlink()
            failures = self.validator.validate(MANIFEST_PATH, report_path, artifact)
            self.assertTrue(any("sidecar is missing" in failure for failure in failures))

    def test_validator_rejects_report_failures_and_false_completion_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact, digest = _write_artifact(root, self.manifest["release"])
            report = self._valid_report(root, digest)
            report["warnings"] = ["visual review warning"]
            report["package_integrity"]["installed_archive_parity"] = False
            report["package_integrity"]["unexpected_files"] = ["unexpected.py"]
            report["restart"]["completed"] = False
            report_path = self._write_report(root, report)
            failures = self.validator.validate(MANIFEST_PATH, report_path, artifact)
            self.assertTrue(any("top-level warnings" in failure for failure in failures))
            self.assertTrue(any("installed_archive_parity" in failure for failure in failures))
            self.assertTrue(any("unexpected_files" in failure for failure in failures))
            self.assertTrue(any("restart field is not true: completed" in failure for failure in failures))

    def test_validator_does_not_falsely_claim_voiceover_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact, digest = _write_artifact(root, self.manifest["release"])
            report = self._valid_report(root, digest)
            report["accessibility"]["complete"] = True
            report["accessibility"]["spoken_voiceover"] = "passed"
            report_path = self._write_report(root, report)
            failures = self.validator.validate(MANIFEST_PATH, report_path, artifact)
            self.assertTrue(any("VoiceOver boundary" in failure for failure in failures))
            self.assertTrue(any("VoiceOver status" in failure for failure in failures))

    def test_validator_rejects_historical_breakpoint_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact, digest = _write_artifact(root, self.manifest["release"])
            report = self._valid_report(root, digest)
            captures = {item["id"]: item for item in report["captures"]}
            captures["11-month-rail-1150"]["geometry"]["qa"]["presentation"] = "inline"
            captures["15-month-event-chips-720"]["geometry"]["qa"]["chipCapacity"] = 0
            captures["19-date-details-today-combined"]["geometry"]["summaryVisible"] = 0
            report_path = self._write_report(root, report)
            failures = self.validator.validate(MANIFEST_PATH, report_path, artifact)
            self.assertTrue(any("11-month-rail-1150 geometry.qa.presentation" in failure for failure in failures))
            self.assertTrue(any("15-month-event-chips-720 geometry.qa.chipCapacity" in failure for failure in failures))
            self.assertTrue(any("19-date-details-today-combined geometry.summaryVisible" in failure for failure in failures))

    def test_validator_rejects_special_state_semantic_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact, digest = _write_artifact(root, self.manifest["release"])
            report = self._valid_report(root, digest)
            captures = {item["id"]: item for item in report["captures"]}
            captures["21-all-hidden-recovery"]["geometry"]["special"]["settingsActionCount"] = 0
            captures["22-partial-data-unavailable"]["geometry"]["special"]["rawErrorLeak"] = True
            captures["23-loading-state"]["geometry"]["special"]["spinnerPresent"] = False
            captures["24-legacy-activation-required"]["geometry"]["special"]["legacyNameVisible"] = False
            report_path = self._write_report(root, report)
            failures = self.validator.validate(MANIFEST_PATH, report_path, artifact)
            for surface_id in (
                "21-all-hidden-recovery",
                "22-partial-data-unavailable",
                "23-loading-state",
                "24-legacy-activation-required",
            ):
                self.assertTrue(
                    any(surface_id in failure for failure in failures),
                    failures,
                )

    def test_historically_rejected_report_cannot_pass_its_own_artifact(self) -> None:
        report_path = REJECTED_ROOT / "calendar-acceptance-report.json"
        artifact = REJECTED_ROOT / "home-dashboard-overhaul-1.5.1.ankiaddon"
        self.assertTrue(report_path.is_file())
        self.assertTrue(artifact.is_file())
        with tempfile.TemporaryDirectory() as temporary:
            manifest = deepcopy(self.manifest)
            manifest["release"] = "1.5.1"
            manifest_path = Path(temporary) / "calendar_surface_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            failures = self.validator.validate(manifest_path, report_path, artifact)
        self.assertTrue(any("11-month-rail-1150 geometry.qa.presentation" in failure for failure in failures))
        self.assertTrue(any("15-month-event-chips-720 geometry.qa.chipCapacity" in failure for failure in failures))

    def test_settings_probe_captures_editors_at_default_and_minimum_sizes(self) -> None:
        source = SETTINGS_PROBE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("event.resize(width, height)", source)
        self.assertNotIn("verse.resize(width, height)", source)
        self.assertIn('"desktop",\n            "default"', source)
        self.assertIn('"minimum",\n                "minimum"', source)
        self.assertIn("event.minimumSize().expandedTo(event.minimumSizeHint())", source)
        self.assertIn("verse.minimumSize().expandedTo(verse.minimumSizeHint())", source)
        self.assertIn("actions remain visible and inside the editor", source)
        self.assertIn("remains inside the available screen", source)
        self.assertIn("EXCLUDED_PID <= 0 or excluded_alive", source)

    def test_calendar_probe_derives_release_from_the_exact_artifact(self) -> None:
        source = CALENDAR_PROBE_PATH.read_text(encoding="utf-8")
        self.assertIn('EXPECTED_HUMAN_VERSION = str(', source)
        self.assertIn('manifest.get("human_version") == EXPECTED_HUMAN_VERSION', source)
        self.assertIn('IDENTITY.get("source_root") or IDENTITY["repository"]', source)
        self.assertNotIn('manifest.get("human_version") == "1.5.1"', source)

    def test_calendar_probe_uses_exact_package_renderers_for_transient_states(self) -> None:
        source = CALENDAR_PROBE_PATH.read_text(encoding="utf-8")
        special_source = source.split("def special_surfaces()", 1)[1].split(
            "def begin_special_surfaces()", 1
        )[0]
        self.assertIn("from dataclasses import replace", source)
        self.assertIn("from home_dashboard_overhaul.renderer import (", source)
        self.assertIn("render_dashboard(partial_snapshot, base_config, anki_dark)", source)
        self.assertIn("render_loading(base_config, anki_dark)", source)
        self.assertIn('render_activation_required(["1771074083"]', source)
        self.assertIn("HDO_QA_RAW_ANALYTICS_ERROR_MUST_NOT_RENDER", source)
        self.assertNotIn("save_config", special_source)
        self.assertIn("restore_dashboard_before_settings", source)
        self.assertIn('profile.get("syncMedia", False)', source)
        self.assertIn('values["excluded_pids"].values()', source)


if __name__ == "__main__":
    unittest.main()
