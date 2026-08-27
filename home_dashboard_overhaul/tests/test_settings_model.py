from __future__ import annotations

from copy import deepcopy
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
    SettingsDraft,
    clamp_window_geometry,
    clamp_window_size,
    changed_paths,
    font_family_value,
    history_range_choice,
    history_range_values,
    import_quotes,
    migrate_saved_window_geometry,
    preview_snapshot_with_staged_events,
    resolve_section,
    resolve_section_target,
    saved_window_geometry_is_valid,
    settings_screen_uses_compact_fallback,
    three_way_merge,
    visible_geometry_ratio,
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

    def test_preview_name_sort_is_case_insensitive_then_date_then_stable_id(self) -> None:
        snapshot = sample_snapshot(date(2026, 8, 15))
        config = normalize_config(
            {
                "events": {
                    "sort": "name",
                    "items": [
                        {"id": "z", "date": "2026-08-18", "name": "alpha", "archived": False},
                        {"id": "b", "date": "2026-08-17", "name": "Beta", "archived": False},
                        {"id": "a", "date": "2026-08-16", "name": "ALPHA", "archived": False},
                        {"id": "c", "date": "2026-08-16", "name": "alpha", "archived": False},
                    ],
                }
            }
        )

        preview = preview_snapshot_with_staged_events(snapshot, config, "2026-08-15")

        self.assertEqual(
            [(item.name, item.date, item.event_id) for item in preview.facts.events.value or ()],
            [
                ("ALPHA", "2026-08-16", "a"),
                ("alpha", "2026-08-16", "c"),
                ("alpha", "2026-08-18", "z"),
                ("Beta", "2026-08-17", "b"),
            ],
        )

    def test_dirty_state_tracks_leaf_diffs_and_can_return_clean(self) -> None:
        baseline = normalize_config({"appearance": {"preset": "Graphite"}})
        draft = SettingsDraft(baseline)
        self.assertFalse(draft.dirty)
        edited = dict(draft.values)
        edited["appearance"] = dict(edited["appearance"], opacity=95)
        draft.replace_values(edited)
        self.assertTrue(draft.dirty)
        self.assertIn(("appearance", "opacity"), draft.changed_paths)
        draft.replace_values(baseline)
        self.assertFalse(draft.dirty)

    def test_dirty_counter_counts_exact_leaves_and_treats_lists_as_atomic(self) -> None:
        baseline = normalize_config(
            {
                "appearance": {"mode": "light", "opacity": 94},
                "bible": {"quotes": ["One"]},
            }
        )
        draft = SettingsDraft(baseline)
        edited = dict(draft.values)
        edited["appearance"] = dict(edited["appearance"], mode="dark", opacity=95)
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
                "appearance": {"opacity": 95},
                "heatmap": {
                    "presets_by_theme": {
                        "Sapphire Glass": "Rose",
                        "Graphite": "Plum",
                    }
                },
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
        defaults = normalize_config({})
        self.assertEqual(
            draft.values["heatmap"]["presets_by_theme"],
            defaults["heatmap"]["presets_by_theme"],
        )
        self.assertEqual(draft.values["events"]["items"], baseline["events"]["items"])
        self.assertEqual(draft.values["bible"]["quotes"], ["Keep this verse"])
        self.assertTrue(draft.values["future"]["feature"]["enabled"])
        self.assertTrue(draft.reset_section("bible verse"))
        self.assertEqual(draft.values["bible"]["quotes"], ["Keep this verse"])
        self.assertFalse(draft.reset_section("events"))

    def test_calendar_display_reset_preserves_appearance_owned_heatmap_palettes(self) -> None:
        baseline = normalize_config(
            {
                "heatmap": {
                    "calendar_view": "month",
                    "week_start": 6,
                    "presets_by_theme": {
                        "Sapphire Glass": "Rose",
                        "Graphite": "Plum",
                    },
                }
            }
        )
        draft = SettingsDraft(baseline)

        self.assertTrue(draft.reset_card("calendar_display"))
        self.assertEqual(
            draft.values["heatmap"]["presets_by_theme"],
            baseline["heatmap"]["presets_by_theme"],
        )

    def test_card_resets_preserve_unknown_nested_and_managed_values(self) -> None:
        baseline = normalize_config(
            {
                "appearance": {
                    "mode": "dark",
                    "future": {"appearance_option": "keep"},
                },
                "home_screen": {
                    "position": "bottom",
                    "future": {"placement_option": "keep"},
                },
                "visibility": {
                    "today": False,
                    "events": False,
                    "future_marker": True,
                },
                "study": {
                    "retention_target": 93,
                    "future": {"metric": "keep"},
                },
                "new_cards": {
                    "include_rescheduled": False,
                    "future": {"rule": "keep"},
                },
                "heatmap": {
                    "calendar_view": "month",
                    "future": {"calendar_option": "keep"},
                },
                "events": {
                    "items": [
                        {
                            "id": "managed-event",
                            "date": "2026-08-27",
                            "name": "Keep event",
                        }
                    ]
                },
                "bible": {
                    "quotes": ["Keep verse"],
                    "font_size": "40px",
                    "future": {"verse_option": "keep"},
                },
            }
        )
        draft = SettingsDraft(baseline)

        for scope in (
            "appearance",
            "dashboard_sections",
            "study_metrics",
            "calendar_display",
            "calendar_range",
            "local_data",
            "bible_appearance",
            "bible_rotation",
        ):
            with self.subTest(scope=scope):
                self.assertTrue(draft.reset_card(scope))

        self.assertTrue(draft.values["visibility"]["future_marker"])
        self.assertEqual(
            draft.values["appearance"]["future"]["appearance_option"],
            "keep",
        )
        self.assertEqual(
            draft.values["home_screen"]["future"]["placement_option"],
            "keep",
        )
        self.assertEqual(draft.values["study"]["future"]["metric"], "keep")
        self.assertEqual(draft.values["new_cards"]["future"]["rule"], "keep")
        self.assertEqual(
            draft.values["heatmap"]["future"]["calendar_option"],
            "keep",
        )
        self.assertEqual(draft.values["events"]["items"], baseline["events"]["items"])
        self.assertEqual(draft.values["bible"]["quotes"], ["Keep verse"])
        self.assertEqual(draft.values["bible"]["future"]["verse_option"], "keep")

    def test_dashboard_sections_reset_does_not_own_calendar_event_markers(self) -> None:
        draft = SettingsDraft(
            normalize_config(
                {
                    "visibility": {
                        "today": False,
                        "heatmap": False,
                        "events": False,
                    }
                }
            )
        )

        snapshot = draft.scope_snapshot("dashboard_sections")
        self.assertTrue(draft.reset_card("dashboard_sections"))

        self.assertTrue(draft.values["visibility"]["today"])
        self.assertTrue(draft.values["visibility"]["heatmap"])
        self.assertFalse(draft.values["visibility"]["events"])
        self.assertNotIn(("visibility", "events"), snapshot)

    def test_scoped_restore_preserves_later_edits_outside_reset_card(self) -> None:
        draft = SettingsDraft(
            normalize_config(
                {
                    "appearance": {"mode": "dark", "opacity": 95},
                    "study": {"retention_target": 91},
                }
            )
        )
        appearance_snapshot = draft.scope_snapshot("appearance")
        self.assertTrue(draft.reset_card("appearance"))
        later_values = deepcopy(draft.values)
        later_values["study"]["retention_target"] = 94
        draft.replace_values(later_values)

        self.assertTrue(
            draft.restore_scope("appearance", appearance_snapshot)
        )

        self.assertEqual(draft.values["appearance"]["mode"], "dark")
        self.assertEqual(draft.values["appearance"]["opacity"], 95)
        self.assertEqual(draft.values["study"]["retention_target"], 94)
        self.assertFalse(draft.restore_scope("unknown", appearance_snapshot))

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
                    "heatmap": {"show_due_forecast": False, "forecast_days": 180},
                    "bible": {"theme_aware_color": True, "font_color": "#123456"},
                }
            )
        )
        self.assertEqual(
            draft.dependency_state,
            {
                "visibility.events": False,
                "heatmap.forecast_days": False,
                "bible.font_color": False,
            },
        )
        self.assertTrue(draft.values["visibility"]["events"])
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
        baseline = normalize_config({"appearance": {"opacity": 94}, "future": {"left": 1}})
        draft = SettingsDraft(baseline)
        local = dict(draft.values)
        local["appearance"] = dict(local["appearance"], opacity=95)
        draft.replace_values(local)
        latest = normalize_config({"appearance": {"opacity": 94}, "future": {"left": 1, "right": 2}})
        conflicts = draft.rebase(latest)
        self.assertFalse(conflicts)
        self.assertEqual(draft.values["appearance"]["opacity"], 95)
        self.assertEqual(draft.values["future"]["right"], 2)

    def test_same_concurrent_value_is_not_a_conflict(self) -> None:
        baseline = normalize_config({"appearance": {"opacity": 94}})
        staged = normalize_config({"appearance": {"opacity": 95}})
        latest = normalize_config({"appearance": {"opacity": 95}})
        result = three_way_merge(baseline, staged, latest)
        self.assertFalse(result.conflicts)
        self.assertEqual(result.values["appearance"]["opacity"], 95)

    def test_managed_lists_are_atomic_during_merge(self) -> None:
        baseline = normalize_config({"bible": {"quotes": ["A"]}})
        staged = normalize_config({"bible": {"quotes": ["A", "Local"]}})
        latest = normalize_config({"bible": {"quotes": ["A", "External"]}})
        result = three_way_merge(baseline, staged, latest)
        self.assertEqual([item.path for item in result.conflicts], [("bible", "quotes")])
        self.assertEqual(result.values["bible"]["quotes"], ["A", "Local"])


class SettingsUtilityTests(unittest.TestCase):
    def test_default_settings_size_is_1080_by_760_logical_pixels(self) -> None:
        self.assertEqual(clamp_window_size(None, (1440, 900)), (1080, 760))

    def test_requested_settings_size_is_clamped_to_minimum_and_screen(self) -> None:
        self.assertEqual(clamp_window_size((700, 500), (1440, 900)), (820, 600))
        self.assertEqual(clamp_window_size((4000, 3000), (1440, 900)), (1344, 804))

    def test_physically_small_screen_uses_same_shell_inside_available_geometry(self) -> None:
        self.assertEqual(clamp_window_size((1200, 800), (800, 600)), (752, 600))
        self.assertEqual(clamp_window_size((1080, 760), (850, 620)), (820, 600))
        self.assertEqual(clamp_window_size((1080, 760), (820, 600)), (820, 600))
        self.assertEqual(
            clamp_window_geometry(None, (0, 0, 819, 599)),
            (24, 24, 771, 551),
        )
        self.assertTrue(settings_screen_uses_compact_fallback((800, 600)))
        self.assertFalse(settings_screen_uses_compact_fallback((1440, 900)))
        self.assertFalse(settings_screen_uses_compact_fallback((1440, 650)))

    def test_default_geometry_centers_on_parent_in_logical_coordinates(self) -> None:
        self.assertEqual(
            clamp_window_geometry(None, (100, 50, 1440, 900), parent=(200, 100, 1000, 700)),
            (160, 98, 1080, 760),
        )

    def test_valid_saved_geometry_keeps_position(self) -> None:
        self.assertEqual(
            clamp_window_geometry((150, 100, 1180, 800), (100, 50, 1600, 1000)),
            (150, 100, 1180, 800),
        )

    def test_offscreen_or_disconnected_monitor_geometry_recenters(self) -> None:
        expected = (160, 98, 1080, 760)
        self.assertEqual(
            clamp_window_geometry((5000, 4000, 1080, 760), (100, 50, 1440, 900), parent=(200, 100, 1000, 700)),
            expected,
        )
        self.assertEqual(
            clamp_window_geometry((-4000, -3000, 1080, 760), (100, 50, 1440, 900), parent=(200, 100, 1000, 700)),
            expected,
        )

    def test_oversized_normal_geometry_is_capped_and_fully_visible(self) -> None:
        self.assertEqual(
            clamp_window_geometry((-500, -500, 3000, 2000), (0, 0, 1440, 900)),
            (48, 48, 1344, 804),
        )

    def test_geometry_result_is_dpr_independent(self) -> None:
        logical = (60, 60, 1180, 800)
        self.assertEqual(clamp_window_geometry(logical, (0, 0, 1600, 1000)), logical)

    def test_saved_geometry_requires_minimum_size_screen_and_eighty_percent_visibility(self) -> None:
        primary = (0, 0, 1600, 1000)
        secondary = (1600, 0, 1920, 1080)
        self.assertFalse(saved_window_geometry_is_valid((100, 100, 720, 520), [primary]))
        self.assertFalse(saved_window_geometry_is_valid((100, 100, 819, 600), [primary]))
        self.assertFalse(saved_window_geometry_is_valid((100, 100, 820, 599), [primary]))
        self.assertTrue(saved_window_geometry_is_valid((100, 100, 820, 600), [primary]))
        self.assertTrue(saved_window_geometry_is_valid((100, 100, 940, 680), [primary]))
        self.assertTrue(saved_window_geometry_is_valid((100, 100, 1180, 800), [primary]))
        self.assertTrue(saved_window_geometry_is_valid((-236, 100, 1180, 800), [primary]))
        self.assertFalse(saved_window_geometry_is_valid((-237, 100, 1180, 800), [primary]))
        self.assertEqual(visible_geometry_ratio((-236, 100, 1180, 800), [primary]), .8)
        self.assertTrue(
            saved_window_geometry_is_valid(
                (1700, 100, 1180, 800),
                [primary, secondary],
                saved_screen_exists=True,
            )
        )
        self.assertFalse(
            saved_window_geometry_is_valid(
                (1700, 100, 1180, 800),
                [primary],
                saved_screen_exists=False,
            )
        )

    def test_geometry_v4_migrates_only_valid_v3_or_v4_logical_rectangles(self) -> None:
        primary = (0, 0, 1600, 1000)
        valid = (100, 120, 1080, 760)

        self.assertEqual(
            migrate_saved_window_geometry(
                valid,
                [primary],
                source_version=3,
            ),
            valid,
        )
        self.assertEqual(
            migrate_saved_window_geometry(
                valid,
                [primary],
                source_version=4,
            ),
            valid,
        )
        for unsupported in (None, True, 2, 5, "future"):
            self.assertIsNone(
                migrate_saved_window_geometry(
                    valid,
                    [primary],
                    source_version=unsupported,
                )
            )
        self.assertIsNone(
            migrate_saved_window_geometry(
                (100, 120, 819, 600),
                [primary],
                source_version=3,
            )
        )
        self.assertIsNone(
            migrate_saved_window_geometry(
                valid,
                [primary],
                source_version=3,
                saved_screen_exists=False,
            )
        )
    def test_reset_scope_visibility_and_split_calendar_scopes(self) -> None:
        baseline = normalize_config({
            "heatmap": {
                "calendar_view": "month",
                "show_due_forecast": False,
                "exclude_deleted_cards": True,
            }
        })
        draft = SettingsDraft(baseline)
        self.assertTrue(draft.scope_differs_from_defaults("calendar_display"))
        self.assertTrue(draft.scope_differs_from_defaults("calendar_range"))
        self.assertTrue(draft.scope_differs_from_defaults("local_data"))
        self.assertFalse(draft.scope_differs_from_defaults("study_metrics"))
        local_before = deepcopy(draft.values["heatmap"]["exclude_deleted_cards"])
        self.assertTrue(draft.reset_card("calendar_display"))
        self.assertFalse(draft.scope_differs_from_defaults("calendar_display"))
        self.assertEqual(draft.values["heatmap"]["exclude_deleted_cards"], local_before)
        self.assertTrue(draft.dirty)

    def test_routes_keep_old_aliases(self) -> None:
        self.assertEqual(resolve_section_target(""), ("dashboard", ""))
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
                "appearance": {"mode": "dark", "opacity": 95},
                "heatmap": {"history_days": 45, "excluded_deck_ids": [2, 8]},
                "events": {"sort": "descending"},
                "future": {"nested": {"value": [1, 2, 3]}},
            }
        )
        self.assertEqual(normalize_config(original), original)
        self.assertEqual(original["future"]["nested"]["value"], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
