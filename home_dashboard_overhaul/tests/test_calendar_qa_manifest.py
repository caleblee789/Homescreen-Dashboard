from __future__ import annotations

from itertools import product
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CanonicalUiReleaseQaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        qa = ROOT / "qa"
        cls.manifest = json.loads(
            (qa / "calendar_surface_manifest_1_8_5.json").read_text(encoding="utf-8")
        )
        cls.matrix = json.loads(
            (qa / "visual_regression_matrix_1_8_5.json").read_text(encoding="utf-8")
        )
        cls.capture = json.loads(
            (qa / "capture_evidence_manifest_1_8_5.json").read_text(encoding="utf-8")
        )
        cls.registry = json.loads(
            (qa / "ui-surface-registry_1_8_5.json").read_text(encoding="utf-8")
        )

    def test_manifest_is_the_authoritative_1_8_5_schema_eight_contract(self) -> None:
        self.assertEqual(self.manifest["schema_version"], 8)
        self.assertEqual(self.manifest["release"], "1.8.5")
        self.assertEqual(
            self.manifest["contract"],
            "canonical-settings-and-production-dashboard-final-ui-2026-08-24",
        )
        self.assertEqual(
            self.manifest["dashboard_order"],
            ["study_calendar", "summary_metrics", "bible_verse"],
        )
        settings = self.manifest["settings_architecture"]
        self.assertEqual(settings["default_window"], [1200, 800])
        self.assertEqual(settings["minimum_normal_window"], [1040, 700])
        self.assertEqual(settings["maximum_inner_width"], 1240)
        self.assertEqual(settings["rail_width"], 152)
        self.assertFalse(settings["preview_persisted"])
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
            "qa/calendar_surface_manifest_1_8_5.json",
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
        self.assertEqual(len(expected), 32)
        self.assertEqual(actual, expected)
        self.assertEqual(len({case["id"] for case in self.matrix["palette_cases"]}), 32)
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
        self.assertEqual(expected_count, 24)
        self.assertEqual(self.matrix["settings_page_case_count"], expected_count)
        self.assertEqual(axes["window_width"], [1040, 1200, "full-screen"])
        self.assertEqual(axes["application_font_percent"], [100, 150])

    def test_capture_count_is_derived_from_contract_families(self) -> None:
        families = self.capture["capture_families"]
        derived = self.capture["derived_native_frame_count"]
        self.assertEqual(sum(family["count"] for family in families), derived["total"])
        self.assertEqual(derived, {
            "initial": 95,
            "restart": 2,
            "total": 97,
            "derivation": "sum(capture_families.count)",
        })
        self.assertEqual(
            {family["id"]: family["count"] for family in families},
            {
                "production-palettes": 32,
                "production-core": 16,
                "settings-pages": 24,
                "settings-contract": 23,
                "restart": 2,
            },
        )
        all_explicit = [
            capture_id
            for family in families
            for capture_id in family.get("capture_ids", [])
        ]
        self.assertEqual(len(all_explicit), len(set(all_explicit)))
        self.assertEqual(
            families[-1]["capture_ids"],
            ["PROD-RESTART-PERSISTENCE", "SET-RESTART-PERSISTENCE"],
        )
        self.assertIn("no-waiver", families[-1]["requirements"])

    def test_settings_contract_includes_every_required_interaction_state(self) -> None:
        family = next(
            item for item in self.capture["capture_families"]
            if item["id"] == "settings-contract"
        )
        required = {
            "SET-DOCK-SHOWN", "SET-DOCK-HIDDEN",
            "SET-PREVIEW-SECTION-FIT", "SET-PREVIEW-SECTION-100",
            "SET-PREVIEW-FULL-FIT", "SET-PREVIEW-FULL-100",
            "SET-OVERLAY-SUBMIN",
            "SET-EVENTS-EMPTY", "SET-EVENTS-POPULATED", "SET-EVENTS-SELECTED",
            "SET-EVENTS-SEARCHED", "SET-EVENTS-ARCHIVED",
            "SET-BIBLE-SHORT", "SET-BIBLE-LONG", "SET-BIBLE-CUSTOM",
            "SET-ABOUT-BOTTOM", "SET-DIRTY", "SET-REVERT",
            "SET-SAVE-SUCCESS", "SET-SAVE-ERROR", "SET-LEGACY-ROUTE",
            "SET-WINDOW-RESTORE", "SET-WINDOW-CLAMP",
        }
        self.assertEqual(set(family["capture_ids"]), required)

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
        self.assertEqual(set(family["capture_ids"]), required)

    def test_references_are_immutable_and_user_owned_evidence_is_never_staged(self) -> None:
        references = self.capture["reference_inputs"]
        self.assertTrue(all(not item["may_count_as_acceptance_evidence"] for item in references))
        self.assertTrue(all(item["must_not_be_overwritten"] for item in references))
        user_owned = next(item for item in references if item["id"].startswith("USER-OWNED"))
        self.assertEqual(
            user_owned["path"],
            "qa/settings-menu-contact-sheets-1.8.3-2026-08-23-2222",
        )
        self.assertTrue(user_owned["must_not_be_staged"])
        for version in ("1.8.0", "1.8.1", "1.8.2", "1.8.3", "1.8.4"):
            self.assertTrue(any(version in item["id"] for item in references))

    def test_acceptance_boundaries_and_isolation_are_explicit(self) -> None:
        expected_unrun = {
            "voiceover_review", "windows_validation", "linux_validation",
            "forced_colors_review", "device_pixel_ratio_1", "os_display_scaling",
        }
        self.assertEqual(set(self.capture["deferred_unrun"]), expected_unrun)
        self.assertEqual(set(self.matrix["deferred_unrun"]), expected_unrun)
        self.assertEqual(len(self.capture["isolation_gates"]), 4)
        self.assertIn("controlled-restart", self.capture["required_automated_gates"])
        criteria = self.manifest["acceptance_criteria"]
        self.assertEqual(len({item["id"] for item in criteria}), len(criteria))
        self.assertTrue(all(item["tags"] and item["requirement"].strip() for item in criteria))


if __name__ == "__main__":
    unittest.main()
