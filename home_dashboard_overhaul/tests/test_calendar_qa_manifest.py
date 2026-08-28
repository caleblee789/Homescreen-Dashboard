from __future__ import annotations

from itertools import product
import json
from pathlib import Path
import runpy
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CanonicalUiReleaseQaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        qa = ROOT / "qa"
        cls.manifest = json.loads(
            (qa / "calendar_surface_manifest_1_8_7.json").read_text(encoding="utf-8")
        )
        cls.matrix = json.loads(
            (qa / "visual_regression_matrix_1_8_7.json").read_text(encoding="utf-8")
        )
        cls.capture = json.loads(
            (qa / "capture_evidence_manifest_1_8_7.json").read_text(encoding="utf-8")
        )
        cls.registry = json.loads(
            (qa / "ui-surface-registry_1_8_7.json").read_text(encoding="utf-8")
        )
        plan_namespace = runpy.run_path(str(qa / "capture_plan.py"))
        cls.plan = plan_namespace["load_capture_plan"](qa / "capture_plan.json")

    def test_manifest_is_the_authoritative_1_8_7_schema_eight_contract(self) -> None:
        self.assertEqual(self.manifest["schema_version"], 8)
        self.assertEqual(self.manifest["release"], "1.8.7")
        self.assertEqual(
            self.manifest["contract"],
            "corrected-native-settings-and-production-dashboard-release-ui-2026-08-26",
        )
        self.assertEqual(
            self.manifest["dashboard_order"],
            ["study_calendar", "summary_metrics", "bible_verse"],
        )
        settings = self.manifest["settings_architecture"]
        self.assertEqual(settings["default_window"], [1080, 760])
        self.assertEqual(settings["minimum_normal_window"], [820, 600])
        self.assertEqual(settings["screen_margins"], {"normal": 48, "small_screen_fallback": 24})
        self.assertEqual(settings["minimum_saved_visible_ratio"], .8)
        self.assertEqual(settings["maximum_inner_width"], 1120)
        self.assertEqual(settings["maximum_page_width"], 920)
        self.assertEqual(settings["maximum_about_width"], 840)
        self.assertEqual(settings["rail_width"], 184)
        self.assertEqual(settings["fixed_header_height"], 72)
        self.assertEqual(settings["fixed_footer_height"], 56)
        self.assertEqual(settings["compact_navigation_threshold"], 864)
        self.assertEqual(settings["embedded_web_content"], "none")
        self.assertEqual(settings["window_lifecycle"], "parented-standard-dialog-exec")
        self.assertEqual(settings["page_switching"], "native-stacked-widget-only-no-render-timer")
        dashboard = self.manifest["dashboard_architecture"]
        self.assertEqual(dashboard["maximum_width"], 1120)
        self.assertEqual(dashboard["month_cells"], 42)
        self.assertEqual(dashboard["month_rows"], 6)
        self.assertEqual(dashboard["year_weeks"], 53)
        self.assertEqual(dashboard["year_weekday_column"], 28)
        self.assertEqual(dashboard["year_cell_range"], [10, 12])
        self.assertEqual(dashboard["year_gap"], 3)

    def test_surface_registry_matches_the_authority_exactly_once(self) -> None:
        manifest_surfaces = self.manifest["canonical_surfaces"]
        registry_surfaces = self.registry["surfaces"]
        ids = [surface["id"] for surface in manifest_surfaces]
        self.assertGreaterEqual(len(ids), 30)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(registry_surfaces, manifest_surfaces)
        self.assertTrue(self.registry["exact_once"])
        self.assertEqual(
            self.registry["authority"],
            "qa/calendar_surface_manifest_1_8_7.json",
        )

    def test_palette_matrix_covers_every_theme_id_in_both_modes(self) -> None:
        expected = {
            (theme, palette, mode)
            for theme, palettes in self.matrix["palette_ids_by_theme"].items()
            for palette, mode in product(palettes, self.matrix["modes"])
        }
        actual = {
            (case["theme"], case["palette"], case["mode"])
            for case in self.matrix["palette_cases"]
        }
        self.assertGreater(len(expected), 0)
        self.assertEqual(actual, expected)
        self.assertEqual(
            len({case["id"] for case in self.matrix["palette_cases"]}),
            len(expected),
        )
        self.assertTrue(all(case["view"] == "month" for case in self.matrix["palette_cases"]))
        self.assertEqual(
            [case["id"] for case in self.matrix["view_cases"]],
            ["PROD-MONTH-STABLE", "PROD-YEAR-STABLE"],
        )

    def test_settings_page_matrix_is_derived_from_all_required_axes(self) -> None:
        axes = self.matrix["settings_page_axes"]
        expected_count = len(axes["page"]) * len(axes["window_width"]) * len(
            axes["application_font_percent"]
        )
        self.assertGreater(expected_count, 0)
        self.assertEqual(self.matrix["settings_page_case_count"], expected_count)
        self.assertEqual(axes["window_width"], [1080, 1280, "full-screen"])
        self.assertEqual(axes["application_font_percent"], [100])
        self.assertEqual(self.plan.counts("settings"), {"initial": 40, "restart": 1, "total": 41})
        self.assertLessEqual(2 + len(self.plan.detail_groups("settings")), 11)

    def test_capture_count_is_derived_from_contract_families(self) -> None:
        families = self.capture["capture_families"]
        derived = self.capture["derived_native_frame_count"]
        self.assertEqual(sum(family["count"] for family in families), derived["total"])
        planned_counts = self.plan.counts("full")
        self.assertEqual(
            {key: derived[key] for key in ("initial", "restart", "total")},
            planned_counts,
        )
        self.assertEqual(derived["derivation"], "sum(capture_families.count)")
        self.assertEqual(
            {family["id"]: family["count"] for family in families},
            {
                family["id"]: len(self.plan.family_ids(family["id"]))
                for family in self.plan.raw["families"]
            },
        )
        all_explicit = [
            capture_id
            for family in families
            for capture_id in family.get("capture_ids", [])
        ]
        self.assertEqual(len(all_explicit), len(set(all_explicit)))
        restart = next(family for family in families if family["id"] == "restart")
        self.assertEqual(
            tuple(restart["capture_ids"]),
            self.plan.family_ids("restart"),
        )
        self.assertIn("no-waiver", restart["requirements"])

    def test_settings_contract_includes_every_required_interaction_state(self) -> None:
        family = next(
            item for item in self.capture["capture_families"]
            if item["id"] == "settings-contract"
        )
        self.assertEqual(
            tuple(family["capture_ids"]),
            self.plan.family_ids("settings-contract"),
        )
        required = {
            "SET-EVENT-EDITOR-OPEN", "SET-EVENTS-NO-RESULTS", "SET-EVENT-LONG-TITLE",
            "SET-BIBLE-CUSTOM-VALID", "SET-BIBLE-CUSTOM-INVALID", "SET-BIBLE-LONG-ROW",
            "SET-DASHBOARD-FUTURE-OFF", "SET-DASHBOARD-FUTURE-ON", "SET-DASHBOARD-ADVANCED",
            "SET-CLOSE-CONFIRM", "SET-SAVE-IN-PROGRESS", "SET-WINDOW-OFFSCREEN-RESTORE",
            "SET-THEME-LIGHT", "SET-THEME-DARK",
        }
        self.assertTrue(required <= set(family["capture_ids"]))
        self.assertNotIn("SET-EVENTS-SELECTED", family["capture_ids"])

    def test_statistics_accuracy_family_covers_every_value_shell(self) -> None:
        family = next(
            item for item in self.capture["capture_families"]
            if item["id"] == "statistics-accuracy"
        )
        expected = {
            "PROD-STATS-WIDE-MONTH",
            "PROD-STATS-WIDE-YEAR",
            "PROD-STATS-INTERMEDIATE",
            "PROD-STATS-NARROW",
        }
        self.assertTrue(expected <= set(family["capture_ids"]))
        self.assertTrue(
            expected
            <= {case["id"] for case in self.matrix["statistics_accuracy_cases"]}
        )

    def test_production_core_includes_geometry_semantics_backgrounds_and_clearance(self) -> None:
        family = next(
            item for item in self.capture["capture_families"]
            if item["id"] == "production-core"
        )
        required = {
            "PROD-MONTH-STABLE", "PROD-YEAR-STABLE",
            "PROD-MARKERS-COMBINED", "PROD-MARKERS-COMPLETION",
            "PROD-MARKERS-DUE", "PROD-MARKERS-TODAY", "PROD-MARKERS-EVENT",
            "PROD-LEGEND-NO-DUE", "PROD-LEGEND-NO-EVENT",
            "PROD-BG-WHITE", "PROD-BG-BLACK", "PROD-BG-PURPLE", "PROD-BG-IMAGE",
            "PROD-SECTIONS-BELOW", "PROD-BOTTOM-CLEARANCE", "PROD-VERSE-EXACT",
        }
        self.assertTrue(required <= set(family["capture_ids"]))

    def test_geometry_reference_is_immutable_and_old_captures_are_not_required(self) -> None:
        references = self.capture["reference_inputs"]
        self.assertEqual(
            [item["id"] for item in references],
            ["USER-NATIVE-WIDE-2026-08-23-1710X1107"],
        )
        self.assertTrue(all(not item["may_count_as_acceptance_evidence"] for item in references))
        self.assertTrue(all(item["must_not_be_overwritten"] for item in references))
        self.assertTrue(all("path" not in item for item in references))

    def test_acceptance_boundaries_and_isolation_are_explicit(self) -> None:
        expected_unrun = {
            "windows-native-settings-validation",
            "linux-native-settings-validation",
            "alternate-os-scaling-settings-validation",
            "alternate-application-font-settings-validation",
            "voiceover_review",
            "forced_colors_review",
        }
        self.assertEqual(set(self.capture["deferred_unrun"]), expected_unrun)
        self.assertEqual(set(self.matrix["deferred_unrun"]), expected_unrun)
        self.assertEqual(
            self.capture["required_native_platform_profiles"],
            self.plan.raw["native_platform_matrix"],
        )
        self.assertEqual(
            self.matrix["required_native_platform_profiles"],
            self.plan.raw["native_platform_matrix"],
        )
        self.assertEqual(len(self.capture["isolation_gates"]), 4)
        self.assertIn("controlled-restart", self.capture["required_automated_gates"])
        self.assertIn("native-statistics-parity", self.capture["required_automated_gates"])
        self.assertIn(
            "macos-fullscreen-space-switch-acceptance",
            self.capture["required_automated_gates"],
        )
        gate = self.capture["settings_profile_structured_manual_gate"]
        self.assertEqual(gate, {
            "id": "macos-fullscreen-no-space-switch-menu-and-dashboard-gear",
            "report_schema_version": 2,
            "required_for_acceptance": True,
            "adds_png_frames": False,
            "opening_paths": ["menu", "dashboard-gear"],
            "workflow_steps_per_path": [
                "all-four-pages",
                "events-tabs",
                "resize",
                "event-edit",
                "verse-edit",
                "save",
                "close-reopen",
                "controlled-restart",
            ],
            "required_result": "every workflow step through both paths remains on the current native Anki full-screen Space with no desktop switch",
        })
        self.assertEqual(
            self.plan.profile("settings")["required_structured_manual_results"],
            [gate["id"]],
        )
        platform_contract = self.capture["native_platform_profile_contract"]
        self.assertEqual(platform_contract["macos_fullscreen_schema_version"], 2)
        self.assertEqual(
            platform_contract["settings_pages"],
            ["dashboard", "events", "bible_verse", "about_support"],
        )
        self.assertIn("horizontal_scroll_zero", platform_contract["settings_page_assertions"])
        self.assertIn("target_fully_visible", platform_contract["settings_page_assertions"])
        self.assertIn(
            "macos-fullscreen-menu-and-dashboard-gear-open-without-desktop-space-switch",
            self.matrix["settings_quality_assertions"],
        )
        self.assertIn(
            "every-png-sample-matches-live-settings-surface",
            self.matrix["settings_quality_assertions"],
        )
        for family_id in ("settings-pages", "settings-contract"):
            family = next(
                item for item in self.capture["capture_families"]
                if item["id"] == family_id
            )
            self.assertIn("live-settings-surface-sample-match", family["requirements"])
        criteria = self.manifest["acceptance_criteria"]
        self.assertEqual(len({item["id"] for item in criteria}), len(criteria))
        self.assertTrue(all(item["tags"] and item["requirement"].strip() for item in criteria))
        workflow = next(item for item in criteria if item["id"] == "SET-WORKFLOW")
        self.assertIn("both menu and Dashboard gear", workflow["requirement"])
        self.assertIn("without a desktop or Space switch", workflow["requirement"])


if __name__ == "__main__":
    unittest.main()
