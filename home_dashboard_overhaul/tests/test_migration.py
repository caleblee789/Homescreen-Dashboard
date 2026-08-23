from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.migration import enabled_legacy_ids, prepare_migration
from home_dashboard_overhaul.verse import quote_fingerprint


class FakeManager:
    def __init__(self, root: Path, configs: dict) -> None:
        self.root = root
        self.configs = configs
        self.enabled = {key: True for key in configs}

    def addonsFolder(self):
        return str(self.root)

    def getConfig(self, addon_id):
        return self.configs.get(addon_id, {})

    def isEnabled(self, addon_id):
        return self.enabled.get(addon_id, False)


class FakeCollection:
    def __init__(self, synced):
        self.synced = synced

    def get_config(self, key):
        return self.synced if key == "heatmap" else None


class FakeProfileManager:
    profile = {"heatmap": {"display": {"deckbrowser": True}, "statsvis": True}}


class FakeMainWindow:
    def __init__(self, manager, synced):
        self.addonManager = manager
        self.col = FakeCollection(synced)
        self.pm = FakeProfileManager()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for addon_id in ("1771074083", "635082046", "1556734708", "1143540799", "290511870"):
            (self.root / addon_id / "user_files").mkdir(parents=True)
        database = self.root / "1143540799" / "user_files" / "events.db"
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE events(id INTEGER PRIMARY KEY, date TEXT, name TEXT)")
        connection.execute("INSERT INTO events VALUES(7, '2026-08-28', 'Pediatric NBME')")
        connection.commit(); connection.close()
        quotes = ["Grace.<br>- Romans 4:5 (NLT)", "Faith.<br>- Hebrews 11:1 (NLT)"]
        state = {"version": 1, "refresh_key": "daily:2026-08-13", "quote_fingerprint": quote_fingerprint(quotes), "quote": quotes[1]}
        (self.root / "290511870" / "user_files" / "rotation_state.json").write_text(json.dumps(state), encoding="utf-8")
        self.configs = {
            "635082046": {"Count rescheduled": True, "Week start": 5, "Custom search query": "is:new", "Custom search title": "New unsuspended"},
            "1556734708": {"CountTimesNew": 2, "DaysToConsider": 3, "ShowTimeLeft": True},
            "1143540799": {"sort": "ASC"},
            "290511870": {"quote": quotes, "font size": "28px", "font family": "Georgia, serif", "rotation mode": "daily", "use theme-aware color": True},
            "1771074083": {},
        }
        self.manager = FakeManager(self.root, self.configs)
        synced = {"colors": "ice", "mode": "year", "limhist": 0, "limfcst": 0, "limcdel": False, "limresched": True, "limdecks": []}
        self.mw = FakeMainWindow(self.manager, synced)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_migration_maps_effective_values_and_is_read_only(self) -> None:
        database = self.root / "1143540799" / "user_files" / "events.db"
        state_path = self.root / "290511870" / "user_files" / "rotation_state.json"
        before = (digest(database), digest(state_path))
        migrated, state = prepare_migration(self.mw, normalize_config({}))
        self.assertEqual(before, (digest(database), digest(state_path)))
        self.assertTrue(migrated["migration"]["completed"])
        self.assertEqual(migrated["appearance"]["preset"], "Sapphire Glass")
        self.assertEqual(migrated["heatmap"]["forecast_days"], 730)
        self.assertTrue(migrated["migration"]["warnings"])
        self.assertEqual(migrated["study"], {
            "pace_unit": "seconds_per_card",
            "show_eta": True,
            "retention_target": 80,
        })
        self.assertTrue(migrated["new_cards"]["include_rescheduled"])
        self.assertEqual(migrated["heatmap"]["week_start"], 5)
        self.assertNotIn("introduced", migrated)
        self.assertEqual(migrated["events"]["items"][0]["name"], "Pediatric NBME")
        self.assertEqual(migrated["bible"]["font_size"], "28px")
        self.assertEqual(state["quote"], self.configs["290511870"]["quote"][1])
        self.assertEqual(set(migrated["migration"]["sources"]), set(self.configs))

    def test_completed_migration_is_idempotent(self) -> None:
        migrated, _ = prepare_migration(self.mw, normalize_config({}))
        repeated, state = prepare_migration(self.mw, migrated)
        self.assertEqual(repeated, migrated)
        self.assertIsNone(state)

    def test_every_legacy_palette_alias_resets_to_sapphire(self) -> None:
        for palette in ("lime", "olive", "ice", "magenta", "flame", "unknown", "Emerald"):
            with self.subTest(palette=palette):
                self.mw.col.synced["colors"] = palette
                migrated, _state = prepare_migration(self.mw, {})
                self.assertEqual(migrated["schema_version"], 6)
                self.assertEqual(migrated["appearance"]["preset"], "Sapphire Glass")
                self.assertNotIn("density", migrated["appearance"])
                self.assertEqual(normalize_config(migrated), migrated)

    def test_legacy_guard_reports_only_enabled_ids(self) -> None:
        self.manager.enabled["1556734708"] = False
        enabled = enabled_legacy_ids(self.manager)
        self.assertIn("1771074083", enabled)
        self.assertNotIn("1556734708", enabled)

    def test_missing_addon_is_never_reported_enabled(self) -> None:
        missing = self.root / "1771074083"
        missing.rename(self.root / "1771074083-absent")
        self.assertNotIn("1771074083", enabled_legacy_ids(self.manager))


if __name__ == "__main__":
    unittest.main()
