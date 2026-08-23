from __future__ import annotations

from dataclasses import replace
from datetime import date
import unittest

from home_dashboard_overhaul.analytics import unavailable_snapshot
from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.models import (
    AvailabilityReason,
    BrowseTarget,
    BrowseTargetKind,
    DayDomainState,
    ValueState,
    ValueStatus,
)
from home_dashboard_overhaul.settings_model import (
    SECTION_GROUPS,
    SECTION_IDS,
    SECTION_LABELS,
    SETTINGS_CONTENT_MODES,
    SettingsLayoutMetrics,
    SettingsDraft,
    changed_paths,
    font_family_value,
    history_range_choice,
    history_range_values,
    import_quotes,
    preview_snapshot_with_staged_events,
    resolve_section,
    resolve_section_target,
    settings_content_mode,
    three_way_merge,
)
from home_dashboard_overhaul.tests.fixtures import sample_snapshot


class SettingsDraftTests(unittest.TestCase):
    def test_history_range_choices_round_trip_to_existing_schema_fields(self) -> None:
        self.assertEqual(history_range_choice(0, ""), "all")
        self.assertEqual(history_range_choice(90, ""), "90")
        self.assertEqual(history_range_choice(180, ""), "180")
        self.assertEqual(history_range_choice(365, ""), "365")
        self.assertEqual(history_range_choice(45, ""), "all")
        self.assertEqual(history_range_choice(90, "2026-01-02"), "custom")
        self.assertEqual(history_range_values("all", "2026-01-02"), (0, ""))
        self.assertEqual(history_range_values("90", "2026-01-02"), (90, ""))
        self.assertEqual(history_range_values("custom", "2026-01-02"), (0, "2026-01-02"))
        self.assertEqual(history_range_values("custom", "invalid"), (0, ""))

    def test_preview_event_overlay_preserves_canonical_future_action(self) -> None:
        snapshot = sample_snapshot(date(2026, 8, 15))
        selected_iso = "2026-08-16"
        selected = replace(
            snapshot.facts.days[selected_iso],
            reviews_due=ValueState.available(12),
            domain_state=DayDomainState.FUTURE_DUE,
            browse_target=BrowseTarget(
                BrowseTargetKind.DUE,
                "cid:1201,1202",
                True,
                (1201, 1202),
            ),
        )
        snapshot = replace(
            snapshot,
            facts=replace(
                snapshot.facts,
                days={**snapshot.facts.days, selected_iso: selected},
            ),
        )
        config = normalize_config({
            "events": {
                "items": [{
                    "id": "future-event",
                    "date": selected_iso,
                    "name": "Pediatrics review",
                    "archived": False,
                }],
            },
        })

        preview = preview_snapshot_with_staged_events(snapshot, config, "2026-08-15")
        preview_selected = preview.facts.days[selected_iso]

        self.assertEqual(preview_selected.reviews_due.value, 12)
        self.assertEqual(preview_selected.domain_state, DayDomainState.FUTURE_DUE)
        self.assertEqual(preview_selected.browse_target.kind, BrowseTargetKind.DUE)
        self.assertEqual(preview_selected.browse_target.card_ids, (1201, 1202))
        self.assertEqual(
            [item.name for item in preview_selected.events.value or ()],
            ["Pediatrics review"],
        )

    def test_preview_overlays_staged_events_without_substituting_study_zeros(self) -> None:
        snapshot = unavailable_snapshot(
            scheduling_date="2026-08-15",
        )
        config = normalize_config(
            {
                "events": {
                    "items": [
                        {
                            "id": "staged",
                            "date": "2026-08-16",
                            "name": "Full staged event name",
                            "archived": False,
                        },
                        {
                            "id": "archived",
                            "date": "2026-08-16",
                            "name": "Archived event",
                            "archived": True,
                        },
                    ]
                }
            }
        )

        preview = preview_snapshot_with_staged_events(snapshot, config, "2026-08-15")

        self.assertEqual(
            [item.event_id for item in preview.facts.events.value or ()],
            ["staged"],
        )
        selected = preview.facts.for_date("2026-08-16")
        self.assertEqual(
            [item.name for item in selected.events.value or ()],
            ["Full staged event name"],
        )
        self.assertEqual(selected.reviews_completed.status, ValueStatus.UNAVAILABLE)
        self.assertEqual(
            selected.reviews_completed.reason,
            AvailabilityReason.QUERY_FAILED,
        )
        self.assertIsNone(selected.reviews_completed.value)
        self.assertEqual(selected.reviews_due.status, ValueStatus.UNAVAILABLE)
        self.assertEqual(selected.reviews_due.reason, AvailabilityReason.QUERY_FAILED)
        self.assertIsNone(selected.reviews_due.value)
        self.assertEqual(preview.facts.today.status, ValueStatus.UNAVAILABLE)
        self.assertEqual(preview.facts.today.reason, AvailabilityReason.QUERY_FAILED)
        self.assertIsNone(preview.facts.today.value)
        self.assertEqual(snapshot.facts.events.status, ValueStatus.UNAVAILABLE)

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

    def test_dirty_counter_counts_exact_leaves_and_treats_lists_as_atomic(self) -> None:
        baseline = normalize_config(
            {
                "appearance": {"mode": "light", "opacity": 88},
                "bible": {"quotes": ["One"]},
            }
        )
        draft = SettingsDraft(baseline)
        edited = dict(draft.values)
        edited["appearance"] = dict(edited["appearance"], mode="dark", opacity=91)
        edited["bible"] = dict(edited["bible"], quotes=["One", "Two", "Three"])
        draft.replace_values(edited)
        self.assertEqual(draft.changed_leaf_count, 3)
        self.assertEqual(
            draft.changed_paths,
            {
                ("appearance", "mode"),
                ("appearance", "opacity"),
                ("bible", "quotes"),
            },
        )

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

    def test_home_screen_reset_restores_top_position(self) -> None:
        draft = SettingsDraft(
            normalize_config(
                {
                    "home_screen": {"position": "bottom"},
                    "visibility": {"today": False},
                }
            )
        )
        self.assertTrue(draft.reset_section("home screen"))
        self.assertEqual(draft.values["home_screen"]["position"], "top")
        self.assertTrue(draft.values["visibility"]["today"])

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
    def test_settings_modes_follow_measured_region_fit(self) -> None:
        common = {
            "font_height": 16,
            "sidebar_width": 208,
            "editor_width": 520,
            "preview_width": 360,
            "footer_width": 620,
            "spacing": 10,
        }
        self.assertEqual(
            settings_content_mode(SettingsLayoutMetrics(available_width=1240, **common)),
            "extra-wide",
        )
        self.assertEqual(
            settings_content_mode(SettingsLayoutMetrics(available_width=900, **common)),
            "intermediate",
        )
        self.assertEqual(
            settings_content_mode(SettingsLayoutMetrics(available_width=600, **common)),
            "narrow",
        )
        self.assertEqual(
            SETTINGS_CONTENT_MODES,
            ("extra-wide", "intermediate", "narrow"),
        )

    def test_navigation_breakpoints_remain_stable_with_scaled_fonts(self) -> None:
        normal = SettingsLayoutMetrics(
            available_width=900,
            font_height=16,
            sidebar_width=208,
            editor_width=500,
            preview_width=360,
            footer_width=620,
            spacing=10,
        )
        scaled = SettingsLayoutMetrics(
            available_width=900,
            font_height=32,
            sidebar_width=310,
            editor_width=720,
            preview_width=520,
            footer_width=980,
            spacing=10,
        )
        self.assertEqual(settings_content_mode(normal), "intermediate")
        self.assertEqual(settings_content_mode(scaled), "intermediate")

    def test_settings_mode_rejects_invalid_measurements(self) -> None:
        with self.assertRaises(ValueError):
            settings_content_mode(
                SettingsLayoutMetrics(
                    available_width=-1,
                    font_height=16,
                    sidebar_width=200,
                    editor_width=480,
                    preview_width=360,
                    footer_width=600,
                )
            )

    def test_routes_keep_old_aliases(self) -> None:
        self.assertEqual(resolve_section("appearance"), "dashboard")
        self.assertEqual(resolve_section("dashboard"), "dashboard")
        self.assertEqual(resolve_section("activity"), "dashboard")
        self.assertEqual(resolve_section("calendar"), "dashboard")
        self.assertEqual(resolve_section("events"), "events")
        self.assertEqual(resolve_section("Bible Verse"), "bible_verse")
        self.assertEqual(resolve_section("About & Credits"), "about_support")
        self.assertEqual(resolve_section_target("theme_layout"), ("dashboard", "appearance"))
        self.assertEqual(resolve_section_target("home_screen"), ("dashboard", "dashboard_sections"))
        self.assertEqual(resolve_section_target("calendar_data"), ("dashboard", "calendar"))

    def test_section_ids_labels_and_groups_match_the_navigation_contract(self) -> None:
        self.assertEqual(
            SECTION_IDS,
            (
                "dashboard",
                "events",
                "bible_verse",
                "about_support",
            ),
        )
        self.assertEqual(
            [SECTION_LABELS[value] for value in SECTION_IDS],
            ["Dashboard", "Events", "Bible verse", "About & support"],
        )
        self.assertEqual(
            [SECTION_GROUPS[value] for value in SECTION_IDS],
            ["", "", "", ""],
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
