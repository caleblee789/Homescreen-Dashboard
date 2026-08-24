from __future__ import annotations

from itertools import product
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NativeRefinementQaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        qa = ROOT / "qa"
        cls.manifest = json.loads(
            (qa / "calendar_surface_manifest_1_8_3.json").read_text(encoding="utf-8")
        )
        cls.matrix = json.loads(
            (qa / "visual_regression_matrix_1_8_3.json").read_text(encoding="utf-8")
        )
        cls.capture = json.loads(
            (qa / "capture_evidence_manifest_1_8_3.json").read_text(encoding="utf-8")
        )
        cls.registry = json.loads(
            (qa / "ui-surface-registry_1_8_3.json").read_text(encoding="utf-8")
        )

    def test_manifest_is_the_authoritative_1_8_3_native_contract(self) -> None:
        self.assertEqual(self.manifest["schema_version"], 8)
        self.assertEqual(self.manifest["release"], "1.8.3")
        self.assertEqual(
            self.manifest["contract"],
            "final-corrections-native-100-percent-2026-08-23",
        )
        self.assertEqual(
            self.manifest["dashboard_order"],
            ["study_calendar", "summary_metrics", "bible_verse"],
        )
        architecture = self.manifest["wide_architecture"]
        self.assertEqual(architecture["minimum_container_width"], 1040)
        self.assertEqual(architecture["dashboard_maximum_width"], 1240)
        self.assertEqual(architecture["minimum_page_side_margin"], 16)
        self.assertEqual(architecture["top_spacing"], 22)
        self.assertEqual(architecture["native_control_height"], 42)
        self.assertEqual(architecture["native_control_gap"], 24)
        self.assertEqual(architecture["bottom_safe_area"], 66)

    def test_current_surface_registry_is_exact_once_and_matches_authority(self) -> None:
        manifest_ids = [item["id"] for item in self.manifest["canonical_surfaces"]]
        registry_ids = [item["id"] for item in self.registry["surfaces"]]
        self.assertGreaterEqual(len(manifest_ids), 41)
        self.assertEqual(len(manifest_ids), len(set(manifest_ids)))
        self.assertEqual(registry_ids, manifest_ids)
        self.assertTrue(self.registry["exact_once"])
        self.assertEqual(
            self.registry["authority"],
            "qa/calendar_surface_manifest_1_8_3.json",
        )

    def test_primary_matrix_is_the_exact_sixteen_case_cartesian_product(self) -> None:
        axes = self.matrix["axes"]
        expected = set(product(axes["theme"], axes["mode"], axes["view"]))
        actual = {
            (case["theme"], case["mode"], case["view"])
            for case in self.matrix["cases"]
        }
        self.assertEqual(self.matrix["release"], "1.8.3")
        self.assertEqual(self.matrix["primary_case_count"], 16)
        self.assertEqual(len(self.matrix["cases"]), 16)
        self.assertEqual(len({case["id"] for case in self.matrix["cases"]}), 16)
        self.assertEqual(actual, expected)
        self.assertTrue(all(case["text_scale"] == 100 for case in self.matrix["cases"]))
        self.assertEqual(self.matrix["deferred_scales_percent"], [125, 150])
        self.assertEqual(
            self.matrix["required_container_width_assertions"],
            [1240, 1100, 1040, 1039, 620, 479, 419, 320, 319],
        )

    def test_capture_manifest_binds_every_primary_and_required_coverage_tag(self) -> None:
        primary_ids = [case["id"] for case in self.matrix["cases"]]
        self.assertEqual(self.capture["primary_native_frames"], primary_ids)
        tags = {
            tag
            for case in self.matrix["cases"] + self.capture["supplemental_frames"]
            for tag in case["tags"]
        }
        self.assertFalse(set(self.capture["required_coverage_tags"]) - tags)
        self.assertEqual(
            len({case["id"] for case in self.capture["supplemental_frames"]}),
            len(self.capture["supplemental_frames"]),
        )
        self.assertEqual(self.capture["native_frame_count"], {"initial": 55, "restart": 1, "total": 56})
        self.assertEqual(self.capture["contact_sheet_output"]["detail_sheet_count"], 15)
        restart = self.capture["supplemental_frames"][-1]
        self.assertEqual(restart["id"], "RUNTIME-RESTART-PERSISTENCE")
        self.assertIn("no_waiver", restart["tags"])
        self.assertNotIn("waived", json.dumps(self.capture).casefold())

    def test_1_8_3_capture_registry_probe_and_assembler_share_new_ids(self) -> None:
        required = {
            "HISTORICAL-ALL-CLEAR-SG-D-M",
            "RESP-SG-D-INTERMEDIATE-SCROLLED-BOTTOM",
            "RESP-HC-D-NARROW-SCROLLED-BOTTOM",
            "RESP-YEAR-NARROW-JANUARY",
            "RESP-YEAR-NARROW-CURRENT-MONTH",
            "RESP-YEAR-NARROW-DECEMBER",
            "BIBLE-LONG-NARROW",
            "STATE-NARROW-LONG-EVENT-PLUS-9",
            "STATE-NARROW-LONG-LOCALIZED-DATE",
        }
        planned = set(self.capture["primary_native_frames"]) | {
            item["id"] for item in self.capture["supplemental_frames"]
        }
        self.assertTrue(required <= planned)
        self.assertNotIn("FRESH-SG-D-M", planned)
        probe = (ROOT / "qa" / "runtime_probe_release_1_8_3.py").read_text(encoding="utf-8")
        assembler = (ROOT / "qa" / "assemble_release_evidence_1_8_3.py").read_text(encoding="utf-8")
        for capture_id in required:
            self.assertIn(capture_id, probe)
            self.assertIn(capture_id, assembler)

    def test_reference_inputs_are_calibration_only_and_history_stays_present(self) -> None:
        for reference in self.capture["reference_inputs"]:
            self.assertFalse(reference["may_count_as_acceptance_evidence"])
            self.assertTrue(reference["must_not_be_overwritten"])
        screenshot = self.capture["reference_inputs"][0]
        self.assertEqual(screenshot["physical_pixels"], [3420, 2214])
        self.assertEqual(
            screenshot["sha256"],
            "a53963d27305bfe531fdd56ebc675ccf25b8be58276636b4a8c4a7380e701c57",
        )
        old_manifest = json.loads(
            (ROOT / "qa" / "calendar_surface_manifest.json").read_text(encoding="utf-8")
        )
        old_matrix = json.loads(
            (ROOT / "qa" / "visual_regression_matrix_1_8_0.json").read_text(encoding="utf-8")
        )
        self.assertEqual(old_manifest["release"], "1.8.0")
        self.assertEqual(old_matrix["release"], "1.8.0")
        self.assertTrue((ROOT / "qa" / "release-evidence-1.8.0-2026-08-23").is_dir())
        retained_181 = json.loads(
            (ROOT / "qa" / "calendar_surface_manifest_1_8_1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(retained_181["release"], "1.8.1")
        self.assertTrue((ROOT / "qa" / "release-evidence-1.8.1-2026-08-23").is_dir())
        retained_182 = json.loads(
            (ROOT / "qa" / "calendar_surface_manifest_1_8_2.json").read_text(encoding="utf-8")
        )
        self.assertEqual(retained_182["release"], "1.8.2")
        self.assertTrue((ROOT / "qa" / "release-evidence-1.8.2-2026-08-23").is_dir())

    def test_acceptance_boundaries_are_machine_readable_and_separate(self) -> None:
        criteria = self.manifest["acceptance_criteria"]
        self.assertEqual([item["id"] for item in criteria], list(range(1, 42)))
        self.assertTrue(all(item["tags"] and item["requirement"].strip() for item in criteria))
        deferred = set(self.capture["deferred_unrun"])
        self.assertIn("voiceover_review", deferred)
        self.assertIn("windows_validation", deferred)
        self.assertIn("forced_colors_review", deferred)
        self.assertIn("non_100_percent_scaling", deferred)


if __name__ == "__main__":
    unittest.main()
