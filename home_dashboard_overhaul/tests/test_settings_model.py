from __future__ import annotations

import unittest

from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.settings_model import (
    SECTION_GROUPS,
    SECTION_IDS,
    SECTION_LABELS,
    SettingsDraft,
    changed_paths,
    font_family_value,
    import_quotes,
    resolve_section,
    three_way_merge,
)


class SettingsDraftTests(unittest.TestCase):
    def test_dirty_state_tracks_leaf_diffs_and_can_return_clean(self) -> None:
        baseline = normalize_config({"appearance": {"preset": "Graphite"}})
        draft = SettingsDraft(baseline)
        self.assertFalse(draft.dirty)
        edited = dict(draft.values)
        edited["appearance"] = dict(edited["appearance"], opacity=91)
        draft.replace_values(edited)
        self.assertTrue(draft.dirty)
        self.assertIn(("appearance", "opacity"), draft.changed_paths)
        draft.replace_values(baseline)
        self.assertFalse(draft.dirty)

    def test_section_reset_preserves_events_verse_library_and_unknown_keys(self) -> None:
        baseline = normalize_config(
            {
                "appearance": {"opacity": 71},
                "events": {
                    "items": [
                        {
                            "id": "keep",
                            "date": "2026-08-20",
                            "name": "Keep me",
                        }
                    ]
                },
                "bible": {"quotes": ["Keep this verse"], "font_size": "47px"},
                "future": {"feature": {"enabled": True}},
            }
        )
        draft = SettingsDraft(baseline)
        self.assertTrue(draft.reset_section("appearance"))
        self.assertEqual(draft.values["events"]["items"], baseline["events"]["items"])
        self.assertEqual(draft.values["bible"]["quotes"], ["Keep this verse"])
        self.assertTrue(draft.values["future"]["feature"]["enabled"])
        self.assertTrue(draft.reset_section("bible verse"))
        self.assertEqual(draft.values["bible"]["quotes"], ["Keep this verse"])
        self.assertFalse(draft.reset_section("events"))

    def test_dependency_rules_disable_without_erasing_preferences(self) -> None:
        draft = SettingsDraft(
            normalize_config(
                {
                    "visibility": {"today": False, "heatmap": False, "events": True},
                    "study": {"show_eta": True},
                    "heatmap": {"show_due_forecast": False, "forecast_days": 180},
                    "bible": {"theme_aware_color": True, "font_color": "#123456"},
                }
            )
        )
        self.assertEqual(
            draft.dependency_state,
            {
                "study.show_eta": False,
                "visibility.events": False,
                "heatmap.forecast_days": False,
                "bible.font_color": False,
            },
        )
        self.assertTrue(draft.values["visibility"]["events"])
        self.assertTrue(draft.values["study"]["show_eta"])
        self.assertEqual(draft.values["heatmap"]["forecast_days"], 180)

    def test_three_way_merge_takes_untouched_external_and_reports_conflict(self) -> None:
        baseline = {"appearance": {"opacity": 88, "blur": 18}, "future": {"value": 1}}
        staged = {"appearance": {"opacity": 92, "blur": 18}, "future": {"value": 1}}
        latest = {"appearance": {"opacity": 80, "blur": 24}, "future": {"value": 2}}
        result = three_way_merge(baseline, staged, latest)
        self.assertEqual(result.values["appearance"]["opacity"], 92)
        self.assertEqual(result.values["appearance"]["blur"], 24)
        self.assertEqual(result.values["future"]["value"], 2)
        self.assertEqual([conflict.path for conflict in result.conflicts], [("appearance", "opacity")])

    def test_rebase_keeps_unknown_external_keys_and_local_edits(self) -> None:
        baseline = normalize_config({"appearance": {"opacity": 88}, "future": {"left": 1}})
        draft = SettingsDraft(baseline)
        local = dict(draft.values)
        local["appearance"] = dict(local["appearance"], opacity=93)
        draft.replace_values(local)
        latest = normalize_config({"appearance": {"opacity": 88}, "future": {"left": 1, "right": 2}})
        conflicts = draft.rebase(latest)
        self.assertFalse(conflicts)
        self.assertEqual(draft.values["appearance"]["opacity"], 93)
        self.assertEqual(draft.values["future"]["right"], 2)

    def test_same_concurrent_value_is_not_a_conflict(self) -> None:
        baseline = normalize_config({"appearance": {"opacity": 88}})
        staged = normalize_config({"appearance": {"opacity": 94}})
        latest = normalize_config({"appearance": {"opacity": 94}})
        result = three_way_merge(baseline, staged, latest)
        self.assertFalse(result.conflicts)
        self.assertEqual(result.values["appearance"]["opacity"], 94)

    def test_managed_lists_are_atomic_during_merge(self) -> None:
        baseline = normalize_config({"bible": {"quotes": ["A"]}})
        staged = normalize_config({"bible": {"quotes": ["A", "Local"]}})
        latest = normalize_config({"bible": {"quotes": ["A", "External"]}})
        result = three_way_merge(baseline, staged, latest)
        self.assertEqual([item.path for item in result.conflicts], [("bible", "quotes")])
        self.assertEqual(result.values["bible"]["quotes"], ["A", "Local"])


class SettingsUtilityTests(unittest.TestCase):
    def test_routes_keep_old_aliases(self) -> None:
        self.assertEqual(resolve_section("appearance"), "theme_layout")
        self.assertEqual(resolve_section("dashboard"), "home_screen")
        self.assertEqual(resolve_section("activity"), "calendar_data")
        self.assertEqual(resolve_section("calendar"), "calendar_data")
        self.assertEqual(resolve_section("events"), "events")
        self.assertEqual(resolve_section("Bible Verse"), "bible_verse")
        self.assertEqual(resolve_section("About & Credits"), "about")

    def test_section_ids_labels_and_groups_match_the_navigation_contract(self) -> None:
        self.assertEqual(
            SECTION_IDS,
            (
                "theme_layout",
                "home_screen",
                "calendar_data",
                "events",
                "bible_verse",
                "about",
            ),
        )
        self.assertEqual(
            [SECTION_LABELS[value] for value in SECTION_IDS],
            ["Theme & layout", "Home screen", "Calendar & data", "Events", "Bible verse", "About"],
        )
        self.assertEqual(
            [SECTION_GROUPS[value] for value in SECTION_IDS],
            ["Personalize", "Personalize", "Personalize", "Content", "Content", "Support"],
        )

    def test_unknown_key_diff_is_visible(self) -> None:
        self.assertEqual(changed_paths({"future": {"a": 1}}, {"future": {"a": 2}}), {("future", "a")})

    def test_verse_import_trims_skips_duplicates_and_reports_limit(self) -> None:
        values, summary = import_quotes(
            ["Existing"],
            ["  New one  ", "Existing", "", "New two", "Beyond"],
            limit=3,
        )
        self.assertEqual(values, ["Existing", "New one", "New two"])
        self.assertEqual(summary.imported, 2)
        self.assertEqual(summary.duplicates, 1)
        self.assertEqual(summary.empty, 1)
        self.assertEqual(summary.limited, 1)
        self.assertEqual(summary.oversized, 0)

    def test_verse_import_skips_oversized_entries(self) -> None:
        values, summary = import_quotes([], ["A" * 4001, "Safe"])
        self.assertEqual(values, ["Safe"])
        self.assertEqual(summary.oversized, 1)
        self.assertEqual(summary.imported, 1)

    def test_missing_font_family_is_preserved_until_explicitly_changed(self) -> None:
        self.assertEqual(
            font_family_value("Unavailable Medical Serif, serif", "Arial", False),
            "Unavailable Medical Serif, serif",
        )
        self.assertEqual(
            font_family_value("Unavailable Medical Serif, serif", "Arial", True),
            "Arial",
        )

    def test_normalized_round_trip_preserves_future_nested_values(self) -> None:
        original = normalize_config(
            {
                "appearance": {"mode": "dark", "opacity": 91},
                "heatmap": {"history_days": 45, "excluded_deck_ids": [2, 8]},
                "events": {"sort": "descending"},
                "future": {"nested": {"value": [1, 2, 3]}},
            }
        )
        self.assertEqual(normalize_config(original), original)
        self.assertEqual(original["future"]["nested"]["value"], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
