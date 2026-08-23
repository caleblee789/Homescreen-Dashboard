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
    DEFAULT_HEATMAP_PRESETS,
    HEATMAP_PRESETS,
    PRESETS,
    _contrast,
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
    def test_defaults_are_schema_six_and_use_the_correct_hierarchy(self) -> None:
        config = normalize_config({})
        self.assertEqual(SCHEMA_VERSION, 6)
        self.assertEqual(config["schema_version"], 6)
        self.assertEqual(
            config["layout"]["order"],
            ["study_calendar", "summary_metrics", "bible_verse"],
        )
        self.assertEqual(config["appearance"]["text_scale"], 100)
        self.assertEqual(config["study"]["retention_target"], 80)
        self.assertEqual(config["heatmap"]["presets_by_theme"], dict(DEFAULT_HEATMAP_PRESETS))
        self.assertEqual(len(default_config()["bible"]["quotes"]), 483)

    def test_schema_six_removes_every_retired_slot_and_is_idempotent(self) -> None:
        raw = {
            "schema_version": 5,
            "unknown_top": {"preserve": True},
            "visibility": {
                "selected_date": True,
                "most_missed": True,
                "due_decks": True,
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
        for removed in ("selected_date", "most_missed", "due_decks"):
            self.assertNotIn(removed, once["visibility"])

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
            "appearance": {"text_scale": 999, "opacity": 1, "future": "kept"},
            "study": {"retention_target": 2},
            "heatmap": {"forecast_days": 9000, "week_start": -8},
            "future_root": [1, 2, 3],
        })
        self.assertEqual(normalized["appearance"]["text_scale"], 150)
        self.assertEqual(normalized["appearance"]["opacity"], 70)
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

    def test_all_sixteen_presets_are_independent_complete_and_contrast_safe(self) -> None:
        signatures = set()
        for theme_name, preset_names in EXPECTED_HEATMAPS.items():
            for preset_name in preset_names:
                palette = HEATMAP_PRESETS[theme_name][preset_name]
                signature = []
                for mode in ("light", "dark"):
                    tokens = palette[mode]
                    expected = {
                        "heatmap_empty", "on_heatmap_empty", "heatmap_out_of_month",
                        "on_heatmap_out_of_month",
                        *{"heatmap_{}".format(level) for level in range(1, 6)},
                        *{"on_heatmap_{}".format(level) for level in range(1, 6)},
                    }
                    self.assertEqual(set(tokens), expected)
                    distances = [
                        _perceptual_distance(tokens["heatmap_empty"], tokens["heatmap_{}".format(level)])
                        for level in range(1, 6)
                    ]
                    self.assertTrue(all(left < right for left, right in zip(distances, distances[1:])))
                    self.assertTrue(all(
                        _perceptual_distance(tokens["heatmap_{}".format(level)], tokens["heatmap_{}".format(level + 1)]) >= 6
                        for level in range(1, 5)
                    ))
                    for role in ("empty", "1", "2", "3", "4", "5", "out_of_month"):
                        self.assertGreaterEqual(
                            _contrast(tokens["heatmap_{}".format(role)], tokens["on_heatmap_{}".format(role)]),
                            4.5,
                        )
                    resolved = resolve_theme(theme_name, mode, mode == "dark", preset_name)
                    self.assertEqual(resolved["heatmap_preset"], preset_name)
                    for key, value in tokens.items():
                        self.assertEqual(resolved[key], value)
                    signature.extend(tokens[key] for key in sorted(tokens))
                self.assertNotIn(tuple(signature), signatures)
                signatures.add(tuple(signature))
        self.assertEqual(len(signatures), 16)

    def test_unknown_heatmap_value_uses_each_theme_default(self) -> None:
        for theme_name, default in DEFAULT_HEATMAP_PRESETS.items():
            with self.subTest(theme=theme_name):
                resolved = resolve_theme(theme_name, "light", False, "legacy")
                self.assertEqual(resolved["heatmap_preset"], default)

    def test_shared_semantic_roles_exist_without_component_hex(self) -> None:
        for theme_name in PRESETS:
            for mode in ("light", "dark"):
                resolved = resolve_theme(theme_name, mode, mode == "dark")
                for role in (
                    "surface", "panel_surface", "text", "muted", "border", "accent",
                    "completion", "review", "success", "event", "forecast", "focus",
                    "warning", "danger", "disabled", "due_stripe",
                ):
                    self.assertIn(role, resolved)


if __name__ == "__main__":
    unittest.main()
