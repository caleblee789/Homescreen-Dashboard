from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
QA_ROOT = ROOT / "qa"
sys.path.insert(0, str(QA_ROOT))
try:
    import assemble_release_evidence_1_8_7
    import capture_plan
    import prepare_capture_helper
finally:
    sys.path.pop(0)


class CapturePlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = capture_plan.load_capture_plan(QA_ROOT / "capture_plan.json")

    def test_plan_matches_all_current_release_authorities(self) -> None:
        summary = self.plan.validate_authorities(QA_ROOT)
        self.assertEqual(summary["status"], "passed")
        contract = json.loads(
            (QA_ROOT / "capture_evidence_manifest_1_8_7.json").read_text(encoding="utf-8")
        )
        derived = contract["derived_native_frame_count"]
        self.assertEqual(
            self.plan.counts("full"),
            {key: derived[key] for key in ("initial", "restart", "total")},
        )

    def test_authority_validation_detects_same_count_axis_drift(self) -> None:
        raw = deepcopy(self.plan.raw)
        pages = next(
            family for family in raw["families"] if family["id"] == "settings-pages"
        )["pages"]
        pages[0]["page"] = "future_dashboard"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "capture_plan.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            revised = capture_plan.load_capture_plan(path)
            with self.assertRaisesRegex(
                capture_plan.CapturePlanError,
                "Settings page axes differ",
            ):
                revised.validate_authorities(QA_ROOT)

    def test_profiles_are_semantic_subsets_with_derived_counts(self) -> None:
        full = self.plan.cases("full")
        wide = self.plan.cases("wide-100")
        settings = self.plan.cases("settings")
        self.assertEqual({case["component"] for case in settings}, {"settings"})
        self.assertTrue(set(self.plan.ids("wide-100")) < set(self.plan.ids("full")))
        self.assertTrue(all(
            case["layout"] == "wide"
            for case in wide
            if case["component"] == "production"
        ))
        self.assertTrue(all(
            case["font_percent"] == 100
            for case in wide
            if case["component"] == "settings"
        ))
        wide_page_cases = [case for case in wide if case["family"] == "settings-pages"]
        self.assertTrue(wide_page_cases)
        self.assertTrue(all(case["width"] == "full" for case in wide_page_cases))
        self.assertEqual(
            self.plan.counts("wide-100")["total"],
            len(wide),
        )
        self.assertEqual(len(full), len(self.plan.ids("full")))

    def test_settings_profile_is_the_exact_minimal_100_percent_contract(self) -> None:
        cases = self.plan.cases("settings")
        page_cases = [case for case in cases if case["family"] == "settings-pages"]
        self.assertEqual(self.plan.counts("settings"), {
            "initial": 40,
            "restart": 1,
            "total": 41,
        })
        self.assertEqual(len(page_cases), 12)
        self.assertEqual(
            {case["width"] for case in page_cases},
            {1080, 1280, "full"},
        )
        self.assertTrue(all(case["font_percent"] == 100 for case in cases))
        self.assertIn("SET-WINDOW-FRESH-OPEN", self.plan.ids("settings"))
        self.assertNotIn("SET-WINDOW-STANDARD", self.plan.ids("settings"))
        self.assertTrue(all("-720-" not in case["id"] for case in page_cases))
        self.assertTrue(all("-940-" not in case["id"] for case in page_cases))
        self.assertTrue(all(not case["id"].endswith("-150") for case in page_cases))
        self.assertLessEqual(2 + len(self.plan.detail_groups("settings")), 11)
        self.assertEqual(
            self.plan.profile("settings")["required_structured_manual_results"],
            ["macos-fullscreen-no-space-switch-menu-and-dashboard-gear"],
        )

    def test_each_profile_has_exactly_once_presentation_coverage(self) -> None:
        for profile_id in self.plan.profile_ids:
            with self.subTest(profile=profile_id):
                grouped = [
                    capture_id
                    for group in self.plan.detail_groups(profile_id)
                    for capture_id in group["capture_ids"]
                ]
                self.assertEqual(len(grouped), len(set(grouped)))
                self.assertEqual(set(grouped), set(self.plan.ids(profile_id)))

    def test_new_cases_flow_into_profiles_and_sheets_without_count_edits(self) -> None:
        raw = deepcopy(self.plan.raw)
        core = next(family for family in raw["families"] if family["id"] == "production-core")
        core["cases"].extend((
            {
                "id": "PROD-FUTURE-WIDE-STATE",
                "sheet_group": "production-legends-backgrounds-clearance",
                "layout": "wide",
                "special": "future-wide-state",
            },
            {
                "id": "PROD-FUTURE-NARROW-STATE",
                "sheet_group": "production-legends-backgrounds-clearance",
                "layout": "narrow",
                "special": "future-narrow-state",
            },
        ))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "capture_plan.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            revised = capture_plan.load_capture_plan(path)
        self.assertIn("PROD-FUTURE-WIDE-STATE", revised.ids("full"))
        self.assertIn("PROD-FUTURE-NARROW-STATE", revised.ids("full"))
        self.assertIn("PROD-FUTURE-WIDE-STATE", revised.ids("wide-100"))
        self.assertNotIn("PROD-FUTURE-NARROW-STATE", revised.ids("wide-100"))
        environment = next(
            group for group in revised.detail_groups("wide-100")
            if group["id"] == "production-legends-backgrounds-clearance"
        )
        self.assertIn("PROD-FUTURE-WIDE-STATE", environment["capture_ids"])

    def test_focused_helpers_keep_canonical_order_and_plan_identity(self) -> None:
        requested = ["SET-DIRTY", "PROD-MONTH-STABLE"]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "helper"
            prepare_capture_helper.prepare_helper(
                output,
                profile_id="full",
                include_ids=requested,
            )
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            request = json.loads((output / "_capture_profile.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["selected_capture_ids"],
                ["PROD-MONTH-STABLE", "SET-DIRTY"],
            )
            self.assertEqual(manifest["expected_capture_counts"], {
                "initial": 2,
                "restart": 0,
                "total": 2,
            })
            self.assertEqual(manifest["required_structured_manual_results"], [])
            self.assertEqual(request["plan_sha256"], self.plan.sha256)
            self.assertEqual(
                set(path.name for path in output.iterdir()),
                {
                    "__init__.py", "_release_probe.py", "_probe_base.py",
                    "_capture_plan.py", "_capture_plan.json",
                    "_capture_profile.json", "manifest.json",
                },
            )

    def test_bundled_profile_request_rejects_plan_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module = root / "__init__.py"
            module.write_text("", encoding="utf-8")
            (root / "_capture_profile.json").write_text(json.dumps({
                "schema_version": 1,
                "id": "full",
                "release": self.plan.release,
                "plan_sha256": "0" * 64,
            }), encoding="utf-8")
            with self.assertRaisesRegex(
                capture_plan.CapturePlanError,
                "profile hash differs",
            ):
                capture_plan.load_profile_request(module, plan=self.plan)

    def test_wide_helper_is_current_and_contains_no_retired_settings_ids(self) -> None:
        retired = {
            "SET-DOCK-SHOWN", "SET-DOCK-HIDDEN", "SET-PREVIEW-SECTION-FIT",
            "SET-PREVIEW-SECTION-100", "SET-PREVIEW-FULL-FIT",
            "SET-PREVIEW-FULL-100", "SET-WINDOW-FIXED", "SET-STATS-PREVIEW",
        }
        self.assertTrue(retired.isdisjoint(self.plan.ids("wide-100")))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "wide-helper"
            prepare_capture_helper.prepare_helper(output, profile_id="wide-100")
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["expected_capture_counts"], self.plan.counts("wide-100"))
            self.assertTrue((output / "_fullscreen_profile.py").is_file())

    def test_runtime_and_assembler_consume_the_plan_without_positional_slices(self) -> None:
        runtime = (QA_ROOT / "runtime_probe_release_1_8_7.py").read_text(encoding="utf-8")
        assembler = (QA_ROOT / "assemble_release_evidence_1_8_7.py").read_text(encoding="utf-8")
        self.assertIn("CAPTURE_PLAN.cases(", runtime)
        self.assertIn("CAPTURE_PLAN.ids(", runtime)
        self.assertIn("CAPTURE_PLAN.detail_groups(profile_id)", assembler)
        self.assertIn("allow_legacy_unversioned_reports", assembler)
        self.assertIn("CAPTURE_PLAN.validate_authorities", assembler)
        self.assertIn("validate_platform_bundles", assembler)
        for stale in (
            "EXPECTED_PRODUCTION_INITIAL = 48",
            "EXPECTED_SETTINGS_INITIAL = 26",
            "expected[:32]",
            "expected[48:72]",
            "contract[0:5]",
        ):
            self.assertNotIn(stale, runtime + assembler)

    def test_platform_bundle_gate_requires_one_exact_native_report_per_profile(self) -> None:
        candidate_hash = "a" * 64
        with self.assertRaisesRegex(RuntimeError, "every required native platform bundle"):
            assemble_release_evidence_1_8_7.validate_platform_bundles([], candidate_hash)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = []
            for index, entry in enumerate(self.plan.raw["native_platform_matrix"]):
                directory = root / "profile-{}".format(index)
                directory.mkdir()
                report = {
                    "status": "passed",
                    "release": self.plan.release,
                    "package_sha256": candidate_hash,
                    "capture_plan_sha256": self.plan.sha256,
                    "host_platform": entry["host_platform"],
                    "os_scale_percent": entry["os_scale_percent"],
                    "dpr_class": entry["dpr_class"],
                    "native_display_scaling": True,
                    "environment_scale_substitute": False,
                    "application_font_percents": [100],
                    "os": "fixture OS",
                    "anki_version": "26.8",
                    "qt_platform": "fixture",
                    "available_logical_geometry": [0, 0, 1440, 900],
                    "physical_geometry": [0, 0, 2880, 1800],
                    "logical_dpi": 96.0,
                    "physical_dpi": 192.0,
                    "device_pixel_ratio": 2.0,
                }
                if entry["host_platform"] == "macos":
                    report["fullscreen_space_switch"] = {
                        "status": "passed",
                        "opening_paths": ["menu", "dashboard-gear"],
                        "all_four_pages": True,
                        "events_tabs": True,
                        "move_resize": True,
                        "save_close_reopen": True,
                        "hard_restart": True,
                    }
                (directory / "platform-profile.json").write_text(
                    json.dumps(report), encoding="utf-8"
                )
                paths.append(directory)

            result = assemble_release_evidence_1_8_7.validate_platform_bundles(
                paths, candidate_hash
            )
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["required_profile_count"], 6)

            first_report = json.loads(
                (paths[0] / "platform-profile.json").read_text(encoding="utf-8")
            )
            first_report["package_sha256"] = "b" * 64
            (paths[0] / "platform-profile.json").write_text(
                json.dumps(first_report), encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "native platform package differs"):
                assemble_release_evidence_1_8_7.validate_platform_bundles(
                    paths, candidate_hash
                )


if __name__ == "__main__":
    unittest.main()
