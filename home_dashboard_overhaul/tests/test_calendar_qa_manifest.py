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
        self.assertEqual(settings["default_window"], [940, 680])
        self.assertEqual(settings["minimum_normal_window"], [720, 520])
        self.assertEqual(settings["initial_available_geometry_caps"], {"width": .92, "height": .88})
        self.assertEqual(settings["maximum_inner_width"], 1120)
        self.assertEqual(settings["maximum_page_width"], 940)
        self.assertEqual(settings["rail_width"], 152)
        self.assertEqual(settings["compact_navigation_threshold"], 760)
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
        self.assertEqual(axes["window_width"], [720, 940, "full-screen"])
        self.assertEqual(axes["application_font_percent"], [100, 150])

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
        expected_unrun = {"voiceover_review", "forced_colors_review"}
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
        criteria = self.manifest["acceptance_criteria"]
        self.assertEqual(len({item["id"] for item in criteria}), len(criteria))
        self.assertTrue(all(item["tags"] and item["requirement"].strip() for item in criteria))


if __name__ == "__main__":
    unittest.main()
