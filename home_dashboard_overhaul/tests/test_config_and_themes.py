from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from home_dashboard_overhaul.config_schema import (
    SCHEMA_VERSION,
    analytics_config_fingerprint,
    default_config,
    normalize_config,
)
from home_dashboard_overhaul.themes import (
    COMPLETION_SCALES,
    DEFAULT_HEATMAP_PRESETS,
    HEATMAP_PRESETS,
    HEATMAP_COMPLETION_SCALES,
    PRESETS,
    PROJECTED_DUE_SCALES,
    REVIEWS_DUE_INDICATORS,
    SEMANTIC_PALETTES,
    SEMANTIC_THEME_OVERRIDES,
    contrast_ratio,
    resolve_theme,
)
from home_dashboard_overhaul.tools.build_ankiaddon import _perceptual_distance


EXPECTED_HEATMAPS = {
    "Sapphire Glass": ("Sapphire", "Amethyst", "Glacier", "Sea Glass"),
    "Graphite": ("Slate", "Steel", "Plum", "Mint"),
    "Emerald": ("Emerald", "Jade", "Moss", "Lagoon"),
    "High Contrast": ("Cyan", "Gold", "Magenta", "Monochrome"),
}


class ConfigTests(unittest.TestCase):
    def test_defaults_are_schema_eight_and_use_the_correct_hierarchy(self) -> None:
        config = normalize_config({})
        self.assertEqual(SCHEMA_VERSION, 8)
        self.assertEqual(config["schema_version"], 8)
        self.assertEqual(
            config["layout"]["order"],
            ["study_calendar", "summary_metrics", "bible_verse"],
        )
        self.assertEqual(config["appearance"]["text_scale"], 100)
        self.assertEqual(config["appearance"]["opacity"], 96)
        self.assertEqual(config["appearance"]["blur"], 12)
        self.assertEqual(config["study"]["retention_target"], 80)
        self.assertNotIn("buried", config["visibility"])
        self.assertEqual(config["heatmap"]["presets_by_theme"], dict(DEFAULT_HEATMAP_PRESETS))
        self.assertEqual(len(default_config()["bible"]["quotes"]), 483)

    def test_schema_eight_removes_known_retired_slots_and_is_idempotent(self) -> None:
        raw = {
            "schema_version": 5,
            "unknown_top": {"preserve": True},
            "visibility": {
                "selected_date": True,
                "most_missed": True,
                "due_decks": True,
                "buried": False,
            },
            "layout": {
                "order": [
                    "custom-before",
                    "selected_date_details",
                    "bible_verse",
                    "most_missed_preview",
                    "study_calendar",
                    "custom-after",
                    "summary_metrics",
                ],
                "selected_date_panel": "rail",
                "most_missed": {"visible": True},
                "due_deck_breakdown": True,
                "future_key": 7,
            },
            "study": {
                "show_eta": False,
                "show_estimate": True,
                "future_calculation": "preserved",
            },
        }
        once = normalize_config(raw)
        twice = normalize_config(deepcopy(once))
        self.assertEqual(once, twice)
        self.assertEqual(
            once["layout"]["order"],
            [
                "study_calendar", "summary_metrics", "bible_verse",
                "custom-before", "custom-after",
            ],
        )
        self.assertEqual(once["layout"]["future_key"], 7)
        self.assertEqual(once["unknown_top"], {"preserve": True})
        encoded = json.dumps(once)
        for removed in (
            "selected_date_panel", "selected_date_details", "most_missed_preview",
            "due_deck_breakdown",
        ):
            self.assertNotIn(removed, encoded)
        for removed in ("selected_date", "most_missed", "due_decks", "buried"):
            self.assertNotIn(removed, once["visibility"])
        self.assertNotIn("show_eta", once["study"])
        self.assertNotIn("show_estimate", once["study"])
        self.assertEqual(once["study"]["future_calculation"], "preserved")

    def test_heatmap_preferences_are_independent_and_unknown_values_reset_locally(self) -> None:
        config = normalize_config({
            "appearance": {"preset": "Graphite"},
            "heatmap": {
                "presets_by_theme": {
                    "Sapphire Glass": "Sea Glass",
                    "Graphite": "Plum",
                    "Emerald": "unknown",
                    "High Contrast": "Monochrome",
                }
            },
        })
        self.assertEqual(config["heatmap"]["presets_by_theme"], {
            "Sapphire Glass": "Sea Glass",
            "Graphite": "Plum",
            "Emerald": "Emerald",
            "High Contrast": "Monochrome",
        })
        self.assertEqual(
            normalize_config({"heatmap": {"preset": "Amethyst"}})["heatmap"]["presets_by_theme"],
            {
                "Sapphire Glass": "Amethyst",
                "Graphite": "Slate",
                "Emerald": "Emerald",
                "High Contrast": "Cyan",
            },
        )

    def test_bounds_and_invalid_values_normalize_without_losing_unknown_keys(self) -> None:
        normalized = normalize_config({
            "schema_version": 7,
            "appearance": {
                "text_scale": 999,
                "opacity": 1,
                "blur": 999,
                "future": "kept",
            },
            "visibility": {"buried": False},
            "study": {"retention_target": 2},
            "heatmap": {"forecast_days": 9000, "week_start": -8},
            "future_root": [1, 2, 3],
        })
        self.assertEqual(normalized["appearance"]["text_scale"], 150)
        self.assertEqual(normalized["schema_version"], 8)
        self.assertEqual(normalized["appearance"]["opacity"], 94)
        self.assertEqual(normalized["appearance"]["blur"], 16)
        self.assertNotIn("buried", normalized["visibility"])
        self.assertEqual(normalized["study"]["retention_target"], 50)
        self.assertEqual(normalized["heatmap"]["forecast_days"], 730)
        self.assertEqual(normalized["heatmap"]["week_start"], 0)
        self.assertEqual(normalized["appearance"]["future"], "kept")
        self.assertEqual(normalized["future_root"], [1, 2, 3])

    def test_render_only_preferences_do_not_invalidate_analytics(self) -> None:
        base = normalize_config({})
        changed = deepcopy(base)
        changed["appearance"]["preset"] = "Emerald"
        changed["appearance"]["text_scale"] = 150
        changed["heatmap"]["calendar_view"] = "month"
        changed["heatmap"]["presets_by_theme"]["Emerald"] = "Lagoon"
        changed["study"]["retention_target"] = 92
        self.assertEqual(analytics_config_fingerprint(base), analytics_config_fingerprint(changed))
        changed["heatmap"]["excluded_deck_ids"] = [123]
        self.assertNotEqual(analytics_config_fingerprint(base), analytics_config_fingerprint(changed))

    def test_event_name_is_the_only_new_sort_value(self) -> None:
        for value in ("ascending", "descending", "name"):
            with self.subTest(value=value):
                self.assertEqual(
                    normalize_config({"events": {"sort": value}})["events"]["sort"],
                    value,
                )
        for invalid in ("date", "NAME", "", None, 4):
            with self.subTest(invalid=invalid):
                self.assertEqual(
                    normalize_config({"events": {"sort": invalid}})["events"]["sort"],
                    "ascending",
                )

    def test_committed_default_json_is_normalized_and_idempotent(self) -> None:
        path = Path(__file__).resolve().parents[1] / "config.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        normalized = normalize_config(raw)
        self.assertEqual(len(normalized["bible"]["quotes"]), 483)
        self.assertEqual(normalized, normalize_config(normalized))


class ThemeTests(unittest.TestCase):
    def test_dashboard_and_heatmap_preset_sets_are_exact(self) -> None:
        self.assertEqual(tuple(PRESETS), tuple(EXPECTED_HEATMAPS))
        self.assertEqual(
            {name: tuple(presets) for name, presets in HEATMAP_PRESETS.items()},
            EXPECTED_HEATMAPS,
        )

    def test_saved_heatmap_ids_resolve_to_one_complete_contrast_safe_theme_scale(self) -> None:
        for theme_name, preset_names in EXPECTED_HEATMAPS.items():
            for preset_name in preset_names:
                palette = HEATMAP_PRESETS[theme_name][preset_name]
                for mode in ("light", "dark"):
                    tokens = palette[mode]
                    expected = {
                        *{"heat_complete_{}".format(level) for level in range(6)},
                        *{"heat_complete_text_{}".format(level) for level in range(6)},
                    }
                    self.assertEqual(set(tokens), expected)
                    self.assertEqual(
                        tuple(tokens["heat_complete_{}".format(level)] for level in range(6)),
                        HEATMAP_COMPLETION_SCALES[theme_name][preset_name][mode],
                    )
                    distances = [
                        _perceptual_distance(tokens["heat_complete_0"], tokens["heat_complete_{}".format(level)])
                        for level in range(1, 6)
                    ]
                    self.assertTrue(all(left < right for left, right in zip(distances, distances[1:])))
                    self.assertTrue(all(
                        _perceptual_distance(
                            tokens["heat_complete_{}".format(level)],
                            tokens["heat_complete_{}".format(level + 1)],
                        ) >= 1.5
                        for level in range(5)
                    ))
                    for level in range(6):
                        self.assertGreaterEqual(
                            contrast_ratio(tokens["heat_complete_{}".format(level)], tokens["heat_complete_text_{}".format(level)]),
                            4.5,
                        )
                    resolved = resolve_theme(theme_name, mode, mode == "dark", preset_name)
                    self.assertEqual(resolved["heatmap_preset"], preset_name)
                    for key, value in tokens.items():
                        self.assertEqual(resolved[key], value)
            for mode in ("light", "dark"):
                ladders = {
                    HEATMAP_COMPLETION_SCALES[theme_name][preset_name][mode]
                    for preset_name in preset_names
                }
                self.assertEqual(len(ladders), 4)

    def test_unknown_heatmap_value_uses_each_theme_default(self) -> None:
        for theme_name, default in DEFAULT_HEATMAP_PRESETS.items():
            with self.subTest(theme=theme_name):
                resolved = resolve_theme(theme_name, "light", False, "legacy")
                self.assertEqual(resolved["heatmap_preset"], default)

    def test_shared_semantic_roles_exist_without_component_hex(self) -> None:
        required = {
            "ui_canvas", "ui_surface_1", "ui_surface_2", "ui_surface_3",
            "ui_border_subtle", "ui_border_default", "ui_border_strong",
            "ui_text_primary", "ui_text_secondary", "ui_text_tertiary", "ui_text_disabled",
            "ui_eyebrow", "ui_accent", "ui_accent_hover", "ui_accent_pressed",
            "ui_accent_soft", "ui_accent_border", "ui_on_accent", "ui_focus",
            "ui_shadow_card", "ui_shadow_overlay",
            *{"status_{}_{}".format(role, suffix) for role in (
                "new", "learning", "review", "buried", "success", "warning", "danger", "event"
            ) for suffix in ("fill", "text")},
            *{"heat_complete_{}".format(level) for level in range(6)},
            *{"heat_due_bg_{}".format(level) for level in range(1, 4)},
            *{"heat_due_mark_{}".format(level) for level in range(1, 4)},
            "progress_complete", "calendar_empty_bg",
            "calendar_outside_bg", "calendar_outside_text", "calendar_future_bg",
            "calendar_future_text", "calendar_footer_bg", "calendar_today_ring",
            "calendar_selected_ring", "calendar_ring_halo", "calendar_event_halo",
        }
        for theme_name in PRESETS:
            for mode in ("light", "dark"):
                resolved = resolve_theme(theme_name, mode, mode == "dark")
                self.assertFalse(required.difference(resolved))
                expected_semantics = dict(SEMANTIC_PALETTES[mode])
                expected_semantics.update(
                    SEMANTIC_THEME_OVERRIDES.get(theme_name, {}).get(mode, {})
                )
                for key, value in expected_semantics.items():
                    self.assertEqual(resolved[key], value)

    def test_sapphire_dark_is_the_only_semantic_theme_override(self) -> None:
        self.assertEqual(
            SEMANTIC_THEME_OVERRIDES,
            {
                "Sapphire Glass": {
                    "dark": {
                        "status_learning_fill": "#F87171",
                        "status_learning_text": "#F87171",
                        "status_review_fill": "#22C55E",
                        "status_review_text": "#22C55E",
                    },
                },
            },
        )
        for theme_name in PRESETS:
            for mode in ("light", "dark"):
                if (theme_name, mode) == ("Sapphire Glass", "dark"):
                    continue
                resolved = resolve_theme(theme_name, mode, mode == "dark")
                for key, value in SEMANTIC_PALETTES[mode].items():
                    with self.subTest(theme=theme_name, mode=mode, role=key):
                        self.assertEqual(resolved[key], value)

    def test_core_surface_hierarchy_and_target_palettes_are_explicit(self) -> None:
        light = resolve_theme("Sapphire Glass", "light", False)
        dark = resolve_theme("Sapphire Glass", "dark", True)
        self.assertEqual(
            [light[key] for key in ("ui_canvas", "ui_surface_1", "ui_surface_2", "ui_surface_3")],
            ["#F4F7FB", "#FFFFFF", "#F8FAFD", "#EDF3F9"],
        )
        self.assertEqual(
            [dark[key] for key in ("ui_canvas", "ui_surface_1", "ui_surface_2", "ui_surface_3")],
            ["#0A131E", "#101D2B", "#142438", "#1B2A3D"],
        )
        self.assertEqual(
            [light[key] for key in ("status_new_fill", "status_learning_fill", "status_review_fill", "status_success_fill", "status_event_fill")],
            ["#2F7DD3", "#C76A00", "#7C3AED", "#147A42", "#E0BF55"],
        )
        self.assertEqual(
            [
                dark[key]
                for key in (
                    "status_learning_fill",
                    "status_learning_text",
                    "status_review_fill",
                    "status_review_text",
                )
            ],
            ["#F87171", "#F87171", "#22C55E", "#22C55E"],
        )
        self.assertEqual(
            [dark["heat_complete_{}".format(level)] for level in range(6)],
            list(COMPLETION_SCALES["Sapphire Glass"]["dark"]),
        )

    def test_sapphire_dark_remaining_semantics_pass_contrast_on_every_card_surface(self) -> None:
        dark = resolve_theme("Sapphire Glass", "dark", True)
        for semantic_role in ("status_learning_text", "status_review_text"):
            for surface_role in ("ui_surface_1", "ui_surface_2", "ui_surface_3"):
                with self.subTest(semantic=semantic_role, surface=surface_role):
                    self.assertGreaterEqual(
                        contrast_ratio(dark[semantic_role], dark[surface_role]),
                        4.5,
                    )

    def test_text_button_and_heat_tokens_pass_contrast_gates(self) -> None:
        for theme_name in PRESETS:
            for mode in ("light", "dark"):
                with self.subTest(theme=theme_name, mode=mode):
                    theme = resolve_theme(theme_name, mode, mode == "dark")
                    for text_role in ("ui_text_primary", "ui_text_secondary", "ui_text_tertiary"):
                        for surface_role in ("ui_surface_1", "ui_surface_2", "ui_surface_3"):
                            self.assertGreaterEqual(contrast_ratio(theme[text_role], theme[surface_role]), 4.5)
                    for background in ("ui_accent", "ui_accent_hover", "ui_accent_pressed"):
                        self.assertGreaterEqual(contrast_ratio(theme["ui_on_accent"], theme[background]), 4.5)
                    for level in range(1, 4):
                        self.assertGreaterEqual(
                            contrast_ratio(theme["heat_due_bg_{}".format(level)], theme["ui_text_primary"]),
                            4.5,
                        )
                        self.assertEqual(theme["heat_due_bg_{}".format(level)], PROJECTED_DUE_SCALES[mode][level])
                        self.assertEqual(theme["heat_due_mark_{}".format(level)], REVIEWS_DUE_INDICATORS[mode][level])
                    if theme_name == "High Contrast":
                        for surface_role in ("ui_surface_1", "ui_surface_2", "ui_surface_3"):
                            self.assertGreaterEqual(contrast_ratio(theme["ui_text_primary"], theme[surface_role]), 7)

    def test_theme_specific_finalization_keeps_structure_and_semantics_distinct(self) -> None:
        sapphire_dark = resolve_theme("Sapphire Glass", "dark", True)
        self.assertNotEqual(sapphire_dark["calendar_selected_ring"], sapphire_dark["heat_complete_5"])
        self.assertGreaterEqual(
            contrast_ratio(sapphire_dark["ui_text_secondary"], sapphire_dark["ui_surface_2"]),
            4.5,
        )

        emerald_dark = resolve_theme("Emerald", "dark", True)
        self.assertEqual(
            [emerald_dark[key] for key in ("ui_canvas", "ui_surface_1", "ui_surface_2", "ui_surface_3")],
            ["#0B1210", "#101B17", "#14231C", "#17251F"],
        )
        self.assertEqual(emerald_dark["ui_border_subtle"], "#294137")
        self.assertEqual(emerald_dark["ui_accent"], "#3CCF8E")
        self.assertNotEqual(emerald_dark["status_success_fill"], emerald_dark["ui_accent"])

        graphite_light = resolve_theme("Graphite", "light", False)
        self.assertEqual(graphite_light["ui_accent"], "#566B80")
        self.assertNotEqual(graphite_light["ui_accent"], graphite_light["status_new_fill"])

        graphite_dark = resolve_theme("Graphite", "dark", True)
        self.assertEqual(graphite_dark["progress_complete"], "#9BA6B1")
        self.assertEqual(graphite_dark["heat_complete_5"], "#8C9BAA")
        self.assertNotEqual(graphite_dark["calendar_selected_ring"], graphite_dark["ui_border_strong"])

        for mode in ("light", "dark"):
            high_contrast = resolve_theme("High Contrast", mode, mode == "dark")
            self.assertEqual(high_contrast["ui_shadow_card"], "none")

    def test_light_level_one_heat_colors_match_the_release_palette(self) -> None:
        self.assertEqual(resolve_theme("Sapphire Glass", "light", False)["heat_complete_1"], "#E7F0FA")
        self.assertEqual(resolve_theme("Graphite", "light", False)["heat_complete_1"], "#E6EAEE")
        self.assertEqual(resolve_theme("Emerald", "light", False)["heat_complete_1"], "#E5F3EB")


if __name__ == "__main__":
    unittest.main()
