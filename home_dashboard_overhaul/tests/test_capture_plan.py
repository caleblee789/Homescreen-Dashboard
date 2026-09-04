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
    import assemble_settings_review_evidence_1_8_7
    import capture_plan
    import prepare_capture_helper
finally:
    sys.path.pop(0)


class CapturePlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = capture_plan.load_capture_plan(QA_ROOT / "capture_plan.json")

    def _structured_layout_report(self) -> dict[str, object]:
        spec = self.plan.raw["structured_settings_layout"]
        assertions = {
            "horizontal_scroll_zero": True,
            "visible_controls_contained": True,
            "labels_unclipped_or_approved": True,
            "segmented_selection_matches_model": True,
            "body_footer_disjoint": True,
            "footer_actions_visible": True,
            "page_bottom_reachable": True,
            "target_fully_visible": True,
        }
        reports = []
        for percent in spec["application_font_percents"]:
            reports.append({
                "id": "settings-font-{}".format(percent),
                "kind": "application-font-layout",
                "status": "passed",
                "application_font_percent": percent,
                "fixture_kind": "logical-work-area-equivalence",
                "work_area_logical": list(spec["work_area_logical"]),
                "resolved_window_geometry_logical": [143, 48, 1080, 672],
                "pages": [
                    {
                        "id": page,
                        "status": "passed",
                        "assertions": dict(assertions),
                    }
                    for page in spec["pages"]
                ],
            })
        reports.append({
            "id": spec["restore_scenarios"][0]["id"],
            "kind": "geometry-restoration",
            "status": "passed",
            "application_font_percent": 100,
            "assertions": {
                "saved_screen_not_connected": True,
                "saved_record_rejected": True,
                "centered_on_parent_screen_before_visibility": True,
                "logical_geometry_not_dpr_multiplied": True,
                "decorated_frame_inside_available": True,
            },
        })
        return {
            "schema_version": 1,
            "release": self.plan.release,
            "stage": "initial",
            "status": "passed",
            "package_sha256": "a" * 64,
            "capture_plan_sha256": self.plan.sha256,
            "adds_png_frames": False,
            "generated_png_count": 0,
            "reports": reports,
        }

    def _native_settings_page_layout(self) -> dict[str, object]:
        assertions = {
            name: True
            for name in assemble_release_evidence_1_8_7.NATIVE_SETTINGS_LAYOUT_ASSERTIONS
        }
        return {
            "status": "passed",
            "application_font_percent": 100,
            "pages": [
                {"id": page, "status": "passed", "assertions": dict(assertions)}
                for page in self.plan.structured_settings_layout()["pages"]
            ],
        }

    def _fullscreen_workflow(self, status: str = "passed") -> dict[str, object]:
        passed = status == "passed"
        steps = {
            step_id: {
                "status": status,
                "completed": passed,
                "remained_on_current_anki_space": True if passed else None,
                "desktop_or_space_switch_observed": False if passed else None,
            }
            for step_id in assemble_release_evidence_1_8_7.FULLSCREEN_WORKFLOW_STEP_IDS
        }
        return {
            "schema_version": 2,
            "status": status,
            "native_fullscreen": passed,
            "desktop_space_switch_regression": "not-observed" if passed else "unrun",
            **({"reason": "Manual native full-screen workflow was not run."} if not passed else {}),
            "opening_paths": {
                path_id: {
                    "status": status,
                    "settings_opened": passed,
                    "remained_on_anki_fullscreen_space": True if passed else None,
                    "desktop_or_space_switch_observed": False if passed else None,
                    "workflow_steps": deepcopy(steps),
                }
                for path_id in ("menu", "dashboard-gear")
            },
        }

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
            "initial": 62,
            "restart": 1,
            "total": 63,
        })
        self.assertEqual(len(page_cases), 21)
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
        self.assertLessEqual(2 + len(self.plan.detail_groups("settings")), 14)
        self.assertEqual(
            self.plan.profile("settings")["required_structured_manual_results"],
            ["macos-fullscreen-no-space-switch-menu-and-dashboard-gear"],
        )
        self.assertTrue(all(case.get("caption") for case in cases))
        self.assertTrue(all(case.get("visible_target") for case in cases))
        future_on = next(
            case for case in cases
            if case["id"] == "SET-DASHBOARD-FUTURE-ON"
        )
        self.assertEqual(
            future_on["visible_target"],
            {"kind": "widget", "attribute": "forecast_days"},
        )
        self.assertEqual(
            future_on["compare_with"],
            "SET-DASHBOARD-FUTURE-OFF",
        )
        fresh = next(
            case for case in cases
            if case["id"] == "SET-WINDOW-FRESH-OPEN"
        )
        self.assertIn("complete decorated", fresh["caption"])
        verse_editor = next(
            case for case in cases if case["id"] == "SET-BIBLE-LONG"
        )
        self.assertEqual(
            verse_editor["visible_target"],
            {"kind": "editor", "attribute": "_qa_verse_editor"},
        )
        self.assertIn("single-title editor", verse_editor["caption"])

    def test_structured_settings_layout_validator_is_strict_and_non_png(self) -> None:
        report = self._structured_layout_report()
        validated, failures = (
            assemble_release_evidence_1_8_7.validate_structured_settings_layout(
                report,
                "a" * 64,
                "full",
            )
        )
        self.assertEqual(validated["status"], "passed")
        self.assertEqual(validated["generated_png_count"], 0)
        self.assertEqual(failures, {})
        self.assertEqual(
            [entry["id"] for entry in validated["reports"]],
            [
                "settings-font-100",
                "disconnected-monitor-v4",
            ],
        )
        with self.assertRaisesRegex(RuntimeError, "lacks structured_settings_layout"):
            assemble_release_evidence_1_8_7.validate_structured_settings_layout(
                None,
                "a" * 64,
                "full",
            )
        generated_png = deepcopy(report)
        generated_png["generated_png_count"] = 1
        with self.assertRaisesRegex(RuntimeError, "added PNG frames"):
            assemble_release_evidence_1_8_7.validate_structured_settings_layout(
                generated_png,
                "a" * 64,
                "full",
            )

    def test_structured_settings_failures_are_retained_only_for_focused_review(self) -> None:
        report = self._structured_layout_report()
        page = report["reports"][0]["pages"][0]
        page["assertions"]["horizontal_scroll_zero"] = False
        page["status"] = "failed"
        report["reports"][0]["status"] = "failed"
        report["status"] = "failed"
        with self.assertRaisesRegex(RuntimeError, "did not pass"):
            assemble_release_evidence_1_8_7.validate_structured_settings_layout(
                report,
                "a" * 64,
                "full",
            )
        validated, failures = (
            assemble_release_evidence_1_8_7.validate_structured_settings_layout(
                report,
                "a" * 64,
                "settings",
                allow_failures=True,
            )
        )
        self.assertEqual(validated["status"], "failed")
        self.assertEqual(
            set(failures),
            {"settings-font-100/dashboard/horizontal_scroll_zero"},
        )
        inconsistent = deepcopy(report)
        inconsistent["reports"][0]["pages"][0]["status"] = "passed"
        with self.assertRaisesRegex(RuntimeError, "status disagrees"):
            assemble_release_evidence_1_8_7.validate_structured_settings_layout(
                inconsistent,
                "a" * 64,
                "settings",
                allow_failures=True,
            )

    def test_structured_settings_layout_is_non_png_and_does_not_change_capture_plan(self) -> None:
        capture_ids = {
            profile_id: self.plan.ids(profile_id)
            for profile_id in self.plan.profile_ids
        }
        capture_counts = {
            profile_id: self.plan.counts(profile_id)
            for profile_id in self.plan.profile_ids
        }
        detail_groups = {
            profile_id: [
                (group["id"], tuple(group["capture_ids"]))
                for group in self.plan.detail_groups(profile_id)
            ]
            for profile_id in self.plan.profile_ids
        }
        self.assertEqual(capture_counts, {
            "full": {"initial": 114, "restart": 2, "total": 116},
            "settings": {"initial": 62, "restart": 1, "total": 63},
            "wide-100": {"initial": 96, "restart": 2, "total": 98},
        })
        self.assertEqual(
            [group_id for group_id, _capture_ids in detail_groups["settings"]],
            [
                "settings-dashboard-widths",
                "settings-appearance-widths",
                "settings-calendar-widths",
                "settings-events-widths",
                "settings-bible-widths",
                "settings-bible-display-widths",
                "settings-about-widths",
                "settings-events-states",
                "settings-bible-states",
                "settings-save-workflow",
                "settings-window-route",
                "restart-persistence",
            ],
        )

        layout = self.plan.structured_settings_layout()
        self.assertEqual(layout, {
            "schema_version": 1,
            "stage": "initial",
            "required_profiles": ["full", "settings"],
            "adds_png_frames": False,
            "work_area_logical": [0, 0, 1366, 768],
            "application_font_percents": [100],
            "pages": ["dashboard", "appearance", "calendar", "events", "bible_verse", "bible_display", "about_support"],
            "restore_scenarios": [{
                "id": "disconnected-monitor-v4",
                "saved_geometry_logical": [1700, 100, 1180, 800],
                "saved_screen_name": "Disconnected Display",
                "saved_available_logical": [1600, 0, 1920, 1080],
                "saved_device_pixel_ratio": 2.0,
            }],
        })
        layout["pages"].append("mutated-copy")
        self.assertEqual(
            self.plan.structured_settings_layout()["pages"],
            ["dashboard", "appearance", "calendar", "events", "bible_verse", "bible_display", "about_support"],
        )
        self.assertEqual(
            {profile_id: self.plan.ids(profile_id) for profile_id in self.plan.profile_ids},
            capture_ids,
        )
        self.assertEqual(
            {profile_id: self.plan.counts(profile_id) for profile_id in self.plan.profile_ids},
            capture_counts,
        )
        self.assertEqual(
            {
                profile_id: [
                    (group["id"], tuple(group["capture_ids"]))
                    for group in self.plan.detail_groups(profile_id)
                ]
                for profile_id in self.plan.profile_ids
            },
            detail_groups,
        )

    def test_structured_settings_layout_schema_rejects_contract_drift(self) -> None:
        mutations = (
            (
                "unknown field",
                lambda layout: layout.__setitem__("unexpected", True),
                "fields differ from the non-PNG contract",
            ),
            (
                "PNG output",
                lambda layout: layout.__setitem__("adds_png_frames", True),
                "must not add PNG frames",
            ),
            (
                "work area",
                lambda layout: layout.__setitem__("work_area_logical", [0, 0, 1365, 768]),
                "work area differs",
            ),
            (
                "font matrix",
                lambda layout: layout.__setitem__("application_font_percents", [100, 150]),
                "font percentages differ",
            ),
            (
                "page matrix",
                lambda layout: layout.__setitem__("pages", ["dashboard", "events"]),
                "pages differ",
            ),
            (
                "restore fields",
                lambda layout: layout["restore_scenarios"][0].pop("saved_screen_name"),
                "restore scenario fields differ",
            ),
            (
                "restore visibility",
                lambda layout: (
                    layout["restore_scenarios"][0].__setitem__(
                        "saved_geometry_logical", [100, 100, 1180, 800]
                    ),
                    layout["restore_scenarios"][0].__setitem__(
                        "saved_available_logical", [0, 0, 1366, 768]
                    ),
                ),
                "still valid on the work area",
            ),
        )
        for label, mutate, message in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                raw = deepcopy(self.plan.raw)
                mutate(raw["structured_settings_layout"])
                path = Path(temporary) / "capture_plan.json"
                path.write_text(json.dumps(raw), encoding="utf-8")
                with self.assertRaisesRegex(capture_plan.CapturePlanError, message):
                    capture_plan.load_capture_plan(path)

    def test_settings_metadata_is_required_and_comparison_pairs_are_atomic(self) -> None:
        raw = deepcopy(self.plan.raw)
        contract = next(
            family for family in raw["families"]
            if family["id"] == "settings-contract"
        )
        contract["cases"][0].pop("visible_target")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "capture_plan.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(
                capture_plan.CapturePlanError,
                "has no declarative visible target",
            ):
                capture_plan.load_capture_plan(path)
        with self.assertRaisesRegex(
            capture_plan.CapturePlanError,
            "omits comparison baseline",
        ):
            self.plan.cases(
                "settings",
                include_ids=["SET-DASHBOARD-FUTURE-ON"],
            )

        raw = deepcopy(self.plan.raw)
        contract = next(
            family for family in raw["families"]
            if family["id"] == "settings-contract"
        )
        future_on = next(
            case for case in contract["cases"]
            if case["id"] == "SET-DASHBOARD-FUTURE-ON"
        )
        future_on["width"] = 820
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "capture_plan.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(
                capture_plan.CapturePlanError,
                "comparison baseline changes width",
            ):
                capture_plan.load_capture_plan(path)

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
                    "__init__.py", "_release_probe.py", "_probe_base.py", "_workflow_probe.py",
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
        for marker in (
            "_position_visible_target",
            "visible_target_fully_visible",
            "_settings_image_difference_ratio",
            "paired_image_comparison",
            '"same_physical_size": same_physical_size',
            '"event_active_scroll_maximum"',
            '"the final Event row is not reachable through the bounded list"',
            "dialog._continue_save()",
            "current != expected",
            "complete-decorated-settings-window",
            'active_prompt = getattr(dialog, "_active_prompt", None)',
        ):
            self.assertIn(marker, runtime)
        validation = runtime.split("def _validate_settings_state", 1)[1].split(
            "def _settings_client_capture", 1
        )[0]
        self.assertLess(
            validation.index('visible_target = state.get("visible_target", {})'),
            validation.index('if bool(visible_target.get("allow_elision"))'),
        )
        self.assertIn('case.get("caption")', assembler)
        self.assertIn('record.get("visible_target")', assembler)
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
        self.assertEqual(
            self.plan.raw["native_platform_matrix"],
            [{"host_platform": "macos", "os_scale_percent": 100, "dpr_class": "retina"}],
        )
        with self.assertRaisesRegex(RuntimeError, "every required native platform bundle"):
            assemble_release_evidence_1_8_7.validate_platform_bundles([], candidate_hash)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = []
            for index, entry in enumerate(self.plan.raw["native_platform_matrix"]):
                directory = root / "profile-{}".format(index)
                directory.mkdir()
                if entry["dpr_class"] == "dpr-1":
                    dpr = 1.0
                elif entry["dpr_class"] == "native":
                    dpr = entry["os_scale_percent"] / 100.0
                else:
                    dpr = 2.0
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
                    "physical_geometry": [0, 0, 1440 * dpr, 900 * dpr],
                    "logical_dpi": 96.0,
                    "physical_dpi": 96.0 * dpr,
                    "device_pixel_ratio": dpr,
                    "settings_page_layout": self._native_settings_page_layout(),
                }
                if entry["host_platform"] == "macos":
                    report["fullscreen_space_switch"] = self._fullscreen_workflow()
                (directory / "platform-profile.json").write_text(
                    json.dumps(report), encoding="utf-8"
                )
                paths.append(directory)

            result = assemble_release_evidence_1_8_7.validate_platform_bundles(
                paths, candidate_hash
            )
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["required_profile_count"], 1)

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

    def test_platform_bundle_geometry_layout_and_fullscreen_steps_fail_closed(self) -> None:
        candidate_hash = "a" * 64
        workflow = self._fullscreen_workflow()
        del workflow["opening_paths"]["menu"]["workflow_steps"]["event-edit"]
        with self.assertRaisesRegex(RuntimeError, "workflow steps or order"):
            assemble_release_evidence_1_8_7.validate_fullscreen_workflow(workflow)

        workflow = self._fullscreen_workflow()
        workflow["opening_paths"]["dashboard-gear"]["workflow_steps"]["verse-edit"][
            "remained_on_current_anki_space"
        ] = False
        with self.assertRaisesRegex(RuntimeError, "current-Space retention"):
            assemble_release_evidence_1_8_7.validate_fullscreen_workflow(workflow)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = []
            for index, entry in enumerate(self.plan.raw["native_platform_matrix"]):
                directory = root / "profile-{}".format(index)
                directory.mkdir()
                dpr = (
                    1.0
                    if entry["dpr_class"] == "dpr-1"
                    else (
                        entry["os_scale_percent"] / 100.0
                        if entry["dpr_class"] == "native"
                        else 2.0
                    )
                )
                report = {
                    "status": "passed",
                    "release": self.plan.release,
                    "package_sha256": candidate_hash,
                    "capture_plan_sha256": self.plan.sha256,
                    **entry,
                    "native_display_scaling": True,
                    "environment_scale_substitute": False,
                    "application_font_percents": [100],
                    "os": "fixture OS",
                    "anki_version": "26.8",
                    "qt_platform": "fixture",
                    "available_logical_geometry": [0, 0, 1440, 900],
                    "physical_geometry": [0, 0, 1440 * dpr, 900 * dpr],
                    "logical_dpi": 96.0,
                    "physical_dpi": 96.0 * dpr,
                    "device_pixel_ratio": dpr,
                    "settings_page_layout": self._native_settings_page_layout(),
                }
                if entry["host_platform"] == "macos":
                    report["fullscreen_space_switch"] = self._fullscreen_workflow()
                (directory / "platform-profile.json").write_text(
                    json.dumps(report), encoding="utf-8"
                )
                paths.append(directory)

            first_path = paths[0] / "platform-profile.json"
            first = json.loads(first_path.read_text(encoding="utf-8"))
            first["physical_geometry"][2] += 300
            first_path.write_text(json.dumps(first), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "does not match logical geometry and DPR"):
                assemble_release_evidence_1_8_7.validate_platform_bundles(paths, candidate_hash)

            first["physical_geometry"] = [0, 0, 1440, 900]
            first["device_pixel_ratio"] = 2.0
            first_path.write_text(json.dumps(first), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "does not match logical geometry and DPR|Retina"):
                assemble_release_evidence_1_8_7.validate_platform_bundles(paths, candidate_hash)

            first["device_pixel_ratio"] = 2.0
            first["physical_geometry"] = [0, 0, 2880, 1800]
            first["settings_page_layout"]["pages"][0]["assertions"][
                "horizontal_scroll_zero"
            ] = False
            first_path.write_text(json.dumps(first), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "failed layout assertion"):
                assemble_release_evidence_1_8_7.validate_platform_bundles(paths, candidate_hash)

    def test_focused_fullscreen_report_uses_schema_two_per_route_steps(self) -> None:
        candidate_hash = "a" * 64
        report = {
            "schema_version": 2,
            "id": "macos-fullscreen-no-space-switch-menu-and-dashboard-gear",
            "release": self.plan.release,
            "host_platform": "macos",
            "candidate_sha256": candidate_hash,
            "capture_plan_sha256": self.plan.sha256,
            **self._fullscreen_workflow("unrun"),
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings-fullscreen-acceptance.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            validated = assemble_settings_review_evidence_1_8_7._validate_fullscreen_report(
                path,
                candidate_hash=candidate_hash,
                allow_unrun=True,
            )
            self.assertEqual(validated["status"], "unrun")

            report["schema_version"] = 1
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "schema mismatch"):
                assemble_settings_review_evidence_1_8_7._validate_fullscreen_report(
                    path,
                    candidate_hash=candidate_hash,
                    allow_unrun=True,
                )

    def test_fullscreen_unrun_template_is_complete_and_claims_no_observations(self) -> None:
        template = json.loads(
            (
                QA_ROOT / "settings_fullscreen_acceptance_template_1_8_7.json"
            ).read_text(encoding="utf-8")
        )
        validated = assemble_release_evidence_1_8_7.validate_fullscreen_workflow(
            template,
            allow_unrun=True,
        )
        self.assertEqual(validated["status"], "unrun")
        self.assertFalse(validated["native_fullscreen"])


if __name__ == "__main__":
    unittest.main()
