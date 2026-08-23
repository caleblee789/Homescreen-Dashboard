from __future__ import annotations

from itertools import product
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "qa" / "calendar_surface_manifest.json"
MATRIX_PATH = ROOT / "qa" / "visual_regression_matrix_1_7_0.json"
REGISTRY_PATH = ROOT / "qa" / "ui-surface-registry.json"


class RevisedUiQaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_manifest_is_the_authoritative_replacement_contract(self) -> None:
        self.assertEqual(self.manifest["schema_version"], 4)
        self.assertEqual(self.manifest["release"], "1.7.0")
        self.assertTrue(self.manifest["replaces_prior_selected_details_and_preview_contracts"])
        self.assertEqual(
            self.manifest["dashboard_order"],
            ["study_calendar", "summary_metrics", "bible_verse"],
        )
        self.assertEqual(len(self.manifest["removed_surfaces"]), 7)

    def test_current_surface_registry_is_exact_once_and_matches_authority(self) -> None:
        manifest_ids = [item["id"] for item in self.manifest["canonical_surfaces"]]
        registry_ids = [item["id"] for item in self.registry["surfaces"]]
        self.assertEqual(len(manifest_ids), 24)
        self.assertEqual(len(manifest_ids), len(set(manifest_ids)))
        self.assertEqual(registry_ids, manifest_ids)
        self.assertTrue(self.registry["exact_once"])
        self.assertEqual(
            self.registry["authority"],
            "qa/calendar_surface_manifest.json",
        )

    def test_removed_preview_fixtures_are_explicitly_prohibited(self) -> None:
        self.assertEqual(
            set(self.registry["prohibited_fixture_kinds"]),
            {
                "selected-date-details-panel",
                "due-deck-breakdown",
                "dashboard-most-missed-preview",
                "card-answer-preview",
            },
        )

    def test_all_twenty_eight_acceptance_criteria_are_bound(self) -> None:
        criteria = self.manifest["acceptance_criteria"]
        self.assertEqual([item["id"] for item in criteria], list(range(1, 29)))
        self.assertTrue(all(str(item["requirement"]).strip() for item in criteria))

    def test_visual_matrix_is_the_exact_96_case_cartesian_product(self) -> None:
        axes = self.matrix["axes"]
        expected = {
            (theme, mode, view, layout, scale)
            for theme, mode, view, layout, scale in product(
                axes["theme"],
                axes["mode"],
                axes["view"],
                axes["layout"],
                axes["text_scale"],
            )
        }
        actual = {
            (
                case["theme"],
                case["mode"],
                case["view"],
                case["layout"],
                case["text_scale"],
            )
            for case in self.matrix["cases"]
        }
        self.assertEqual(self.matrix["case_count"], 96)
        self.assertEqual(len(self.matrix["cases"]), 96)
        self.assertEqual(len({case["id"] for case in self.matrix["cases"]}), 96)
        self.assertEqual(actual, expected)
        self.assertEqual(
            axes,
            {
                "theme": ["Sapphire Glass", "Graphite", "Emerald", "High Contrast"],
                "mode": ["light", "dark"],
                "view": ["month", "year"],
                "layout": ["compact", "wide"],
                "text_scale": [100, 125, 150],
            },
        )

    def test_human_acceptance_remains_separate_from_automated_checks(self) -> None:
        automated = set(self.manifest["automated_accessibility"])
        human = set(self.manifest["human_required"])
        self.assertTrue(automated)
        self.assertEqual(automated & human, set())
        self.assertIn("spoken_voiceover_grid_navigation", human)
        self.assertIn("native_windows_high_dpi_visual_review", human)


if __name__ == "__main__":
    unittest.main()
