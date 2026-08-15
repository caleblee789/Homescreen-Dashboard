from __future__ import annotations

from datetime import date
import unittest

from home_dashboard_overhaul.config_schema import analytics_config_fingerprint, archive_expired_events, normalize_config
from home_dashboard_overhaul.themes import PRESETS, composite_color, resolve_theme


class ConfigTests(unittest.TestCase):
    def test_defaults_include_supplied_verse_library(self) -> None:
        config = normalize_config({})
        self.assertEqual(config["schema_version"], 3)
        self.assertEqual(len(config["bible"]["quotes"]), 483)
        self.assertEqual(config["appearance"]["preset"], "Sapphire Glass")
        self.assertEqual(config["heatmap"]["calendar_view"], "year")

    def test_schema_one_calendar_modes_migrate_to_year_and_are_removed(self) -> None:
        for legacy_mode in ("year", "nine_months"):
            with self.subTest(legacy_mode=legacy_mode):
                config = normalize_config({"schema_version": 1, "heatmap": {"calendar_mode": legacy_mode}})
                self.assertEqual(config["schema_version"], 3)
                self.assertEqual(config["heatmap"]["calendar_view"], "year")
                self.assertNotIn("calendar_mode", config["heatmap"])

    def test_schema_two_statistics_settings_migrate_to_schema_three(self) -> None:
        config = normalize_config({
            "schema_version": 2,
            "visibility": {"introduced": False},
            "study": {
                "pace_lookback_days": 7,
                "new_card_weight": 2.5,
                "show_estimate": False,
            },
            "introduced": {
                "include_rescheduled": False,
                "period": "calendar_week",
                "week_start": 5,
                "custom_enabled": True,
                "custom_title": "Unused",
                "custom_query": "is:new",
            },
        })
        self.assertEqual(config["schema_version"], 3)
        self.assertFalse(config["visibility"]["buried"])
        self.assertNotIn("introduced", config["visibility"])
        self.assertFalse(config["study"]["show_eta"])
        self.assertEqual(set(config["study"]), {"pace_unit", "show_eta"})
        self.assertFalse(config["new_cards"]["include_rescheduled"])
        self.assertEqual(config["heatmap"]["week_start"], 5)
        self.assertNotIn("introduced", config)

    def test_calendar_view_validation_and_persistence(self) -> None:
        month = normalize_config({"heatmap": {"calendar_view": "month"}})
        self.assertEqual(month["heatmap"]["calendar_view"], "month")
        self.assertEqual(normalize_config(month)["heatmap"]["calendar_view"], "month")
        invalid = normalize_config({"heatmap": {"calendar_view": "nine_months"}})
        self.assertEqual(invalid["heatmap"]["calendar_view"], "year")

    def test_remaining_visibility_preference_is_preserved_without_a_schema_bump(self) -> None:
        config = normalize_config({"schema_version": 3, "visibility": {"remaining": False}})
        self.assertEqual(config["schema_version"], 3)
        self.assertFalse(config["visibility"]["remaining"])
        self.assertNotIn("progress", config["visibility"])

    def test_render_only_preferences_do_not_change_analytics_fingerprint(self) -> None:
        baseline = normalize_config({})
        visual = normalize_config({
            "appearance": {"preset": "High Contrast", "density": "compact"},
            "visibility": {"today": False},
            "heatmap": {"calendar_view": "month"},
            "events": {"items": [{"id": "e", "date": "2026-08-20", "name": "Exam"}]},
            "bible": {"font_size": "24px"},
        })
        self.assertEqual(analytics_config_fingerprint(baseline), analytics_config_fingerprint(visual))
        filtered = normalize_config({"heatmap": {"history_days": 30}})
        self.assertNotEqual(analytics_config_fingerprint(baseline), analytics_config_fingerprint(filtered))
        eta_hidden = normalize_config({"study": {"show_eta": False}})
        self.assertEqual(analytics_config_fingerprint(baseline), analytics_config_fingerprint(eta_hidden))
        cards_per_minute = normalize_config({"study": {"pace_unit": "cards_per_minute"}})
        self.assertNotEqual(analytics_config_fingerprint(baseline), analytics_config_fingerprint(cards_per_minute))

    def test_invalid_values_are_normalized_without_dropping_unknown_keys(self) -> None:
        config = normalize_config({
            "future_feature": {"kept": True},
            "appearance": {"preset": "not real", "opacity": 3, "text_scale": 999},
            "heatmap": {"ignore_before": "2026-02-30", "excluded_deck_ids": [3, "3", -2, "bad"]},
            "bible": {"quotes": ["  Verse <br>- John 1:1 (NLT)  ", 4], "font_family": "bad;family", "font_size": "200px"},
        })
        self.assertEqual(config["appearance"]["preset"], "Sapphire Glass")
        self.assertEqual(config["appearance"]["opacity"], 70)
        self.assertEqual(config["appearance"]["text_scale"], 125)
        self.assertEqual(config["heatmap"]["ignore_before"], "")
        self.assertEqual(config["heatmap"]["excluded_deck_ids"], [3])
        self.assertEqual(config["bible"]["font_family"], "Georgia, serif")
        self.assertEqual(config["bible"]["font_size"], "28px")
        self.assertTrue(config["future_feature"]["kept"])

    def test_expired_events_archive_instead_of_deleting(self) -> None:
        config = normalize_config({"events": {"items": [
            {"id": "past", "date": "2026-08-12", "name": "Past", "archived": False},
            {"id": "today", "date": "2026-08-13", "name": "Today", "archived": False},
        ]}})
        self.assertTrue(archive_expired_events(config, date(2026, 8, 13)))
        self.assertEqual(len(config["events"]["items"]), 2)
        self.assertTrue(config["events"]["items"][0]["archived"])
        self.assertFalse(config["events"]["items"][1]["archived"])
        self.assertFalse(archive_expired_events(config, date(2026, 8, 13)))


class ThemeTests(unittest.TestCase):
    @staticmethod
    def _contrast(left: str, right: str) -> float:
        def luminance(value: str) -> float:
            raw = value.lstrip("#")
            channels = [int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4)]
            linear = [item / 12.92 if item <= .04045 else ((item + .055) / 1.055) ** 2.4 for item in channels]
            return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]
        high, low = sorted((luminance(left), luminance(right)), reverse=True)
        return (high + .05) / (low + .05)

    @staticmethod
    def _composite(foreground: str, background: str, opacity: float) -> str:
        def channels(value: str) -> list[int]:
            raw = value.lstrip("#")
            return [int(raw[index:index + 2], 16) for index in (0, 2, 4)]
        values = [
            round(opacity * front + (1 - opacity) * back)
            for front, back in zip(channels(foreground), channels(background))
        ]
        return "#{:02x}{:02x}{:02x}".format(*values)

    def test_twelve_presets_have_complete_light_and_dark_tokens(self) -> None:
        self.assertEqual(len(PRESETS), 12)
        required = {"background", "surface", "border", "control_border", "text", "muted", "accent", "accent_soft", "forecast", "progress_percent", "shadow", "focus", "new", "success", "warning", "danger", "empty"}
        for name, variants in PRESETS.items():
            with self.subTest(name=name):
                self.assertEqual(set(variants), {"light", "dark"})
                self.assertTrue(required.issubset(variants["light"]))
                self.assertTrue(required.issubset(variants["dark"]))

    def test_auto_mode_follows_anki_theme(self) -> None:
        light = resolve_theme("Sapphire Glass", "auto", False)
        dark = resolve_theme("Sapphire Glass", "auto", True)
        self.assertNotEqual(light["background"], dark["background"])
        self.assertEqual(resolve_theme("missing", "light", True), resolve_theme("Sapphire Glass", "light", False))

    def test_card_composite_matches_the_renderer_opacity_model(self) -> None:
        self.assertEqual(composite_color("#ffffff", "#edf5ff", .70), "#fafcff")
        self.assertLess(self._contrast("#2176d2", "#fafcff"), 4.5)

    def test_normal_text_muted_text_and_accent_controls_meet_aa(self) -> None:
        for name in PRESETS:
            for mode, dark in (("light", False), ("dark", True)):
                with self.subTest(name=name, mode=mode):
                    theme = resolve_theme(name, mode, dark)
                    self.assertGreaterEqual(self._contrast(theme["text"], theme["surface"]), 4.5)
                    self.assertGreaterEqual(self._contrast(theme["muted"], theme["surface"]), 4.5)
                    self.assertGreaterEqual(self._contrast(theme["on_accent"], theme["accent"]), 4.5)
                    self.assertGreaterEqual(self._contrast(theme["control_border"], theme["surface"]), 3.0)
                    self.assertGreaterEqual(self._contrast(theme["focus"], theme["surface"]), 3.0)
                    self.assertGreaterEqual(self._contrast(theme["forecast"], theme["surface"]), 3.0)
                    self.assertGreaterEqual(self._contrast(theme["progress_percent"], theme["surface"]), 4.5)
                    self.assertGreaterEqual(self._contrast(theme["accent_text"], theme["surface"]), 4.5)
                    self.assertGreaterEqual(self._contrast(theme["new"], theme["surface"]), 4.5)
                    self.assertGreaterEqual(self._contrast(theme["success"], theme["surface"]), 4.5)
                    self.assertGreaterEqual(self._contrast(theme["warning"], theme["surface"]), 4.5)
                    self.assertGreaterEqual(self._contrast(theme["on_warning"], theme["warning"]), 4.5)
                    self.assertGreaterEqual(self._contrast(theme["disabled"], theme["surface"]), 4.5)
                    self.assertGreaterEqual(self._contrast(theme["danger"], theme["danger_soft"]), 4.5)
                    seventy_percent_card = self._composite(
                        theme["surface"], theme["background"], .70
                    )
                    for token in (
                        "text",
                        "muted",
                        "accent_text",
                        "new",
                        "success",
                        "warning",
                        "progress_percent",
                        "disabled",
                    ):
                        with self.subTest(token=token):
                            self.assertGreaterEqual(
                                self._contrast(theme[token], seventy_percent_card),
                                4.5,
                            )
                    warning_soft = self._composite(
                        theme["warning"], seventy_percent_card, .14
                    )
                    self.assertGreaterEqual(
                        self._contrast(theme["text"], warning_soft), 4.5
                    )

    def test_percent_complete_uses_mode_aware_violet_tokens(self) -> None:
        self.assertEqual(resolve_theme("Sapphire Glass", "light", False)["progress_percent"], "#6D28D9")
        self.assertEqual(resolve_theme("Sapphire Glass", "dark", True)["progress_percent"], "#C4B5FD")
        self.assertEqual(resolve_theme("High Contrast", "light", False)["progress_percent"], "#4C1D95")
        self.assertEqual(resolve_theme("High Contrast", "dark", True)["progress_percent"], "#DDD6FE")


if __name__ == "__main__":
    unittest.main()
