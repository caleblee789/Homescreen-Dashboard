from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UiSurfaceRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(
            (ROOT / "qa" / "ui-surface-registry.json").read_text(encoding="utf-8")
        )
        cls.manifest = json.loads(
            (ROOT / "qa" / "calendar_surface_manifest.json").read_text(encoding="utf-8")
        )

    def test_registry_has_one_current_entry_per_authoritative_surface(self) -> None:
        expected = [item["id"] for item in self.manifest["canonical_surfaces"]]
        actual = [item["id"] for item in self.registry["surfaces"]]
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(self.registry["schema_version"], 20)
        self.assertEqual(self.registry["release"], "1.8.0")

    def test_entries_are_machine_checkable_and_fixture_scoped(self) -> None:
        for surface in self.registry["surfaces"]:
            with self.subTest(surface=surface["id"]):
                self.assertEqual(set(surface), {"id", "owner", "fixture"})
                self.assertTrue(all(str(value).strip() for value in surface.values()))

    def test_superseded_large_panel_fixtures_are_not_registered(self) -> None:
        text = json.dumps(self.registry).casefold()
        for forbidden in (
            "selected-date-details-panel",
            "due-deck-breakdown",
            "dashboard-most-missed-preview",
            "card-answer-preview",
        ):
            self.assertIn(forbidden, self.registry["prohibited_fixture_kinds"])
            self.assertNotIn(forbidden, json.dumps(self.registry["surfaces"]).casefold())


if __name__ == "__main__":
    unittest.main()
