from __future__ import annotations

import json
from pathlib import Path
import unittest

from home_dashboard_overhaul.themes import (
    DEFAULT_HEATMAP_PRESETS,
    HEATMAP_PRESETS,
    PRESETS,
)


ROOT = Path(__file__).resolve().parents[1]


class SettingsReleaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = (ROOT / "settings.py").read_text(encoding="utf-8")
        cls.runtime_probe = (ROOT / "qa" / "runtime_probe_settings_overhaul.py").read_text(
            encoding="utf-8"
        )
        cls.contact_sheet = (
            ROOT / "qa" / "generate_settings_overhaul_contact_sheets.py"
        ).read_text(encoding="utf-8")
        cls.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_release_metadata_and_schema_six_are_current(self) -> None:
        self.assertEqual(self.manifest["human_version"], "1.7.0")
        self.assertEqual(self.config["schema_version"], 6)
        self.assertEqual(
            tuple(PRESETS),
            ("Sapphire Glass", "Graphite", "Emerald", "High Contrast"),
        )

    def test_all_sixteen_heatmap_presets_are_theme_specific_cards(self) -> None:
        expected = {
            "Sapphire Glass": ("Sapphire", "Amethyst", "Glacier", "Sea Glass"),
            "Graphite": ("Slate", "Steel", "Plum", "Mint"),
            "Emerald": ("Emerald", "Jade", "Moss", "Lagoon"),
            "High Contrast": ("Cyan", "Gold", "Magenta", "Monochrome"),
        }
        self.assertEqual(
            {theme: tuple(presets) for theme, presets in HEATMAP_PRESETS.items()},
            expected,
        )
        self.assertEqual(set(DEFAULT_HEATMAP_PRESETS), set(expected))
        for theme, presets in HEATMAP_PRESETS.items():
            for name, variants in presets.items():
                with self.subTest(theme=theme, preset=name):
                    self.assertEqual(set(variants), {"light", "dark"})
                    for tokens in variants.values():
                        self.assertTrue(all(
                            key in tokens
                            for key in (
                                "heatmap_empty",
                                "heatmap_1",
                                "heatmap_2",
                                "heatmap_3",
                                "heatmap_4",
                                "heatmap_5",
                                "on_heatmap_1",
                                "on_heatmap_2",
                                "on_heatmap_3",
                                "on_heatmap_4",
                                "on_heatmap_5",
                                "heatmap_out_of_month",
                            )
                        ))
        self.assertIn('card = SettingsCard(\n            "Calendar & data"', self.settings)
        self.assertIn("self.heatmap_preset_grid", self.settings)
        self.assertIn('button.setObjectName("HeatmapPresetCard")', self.settings)
        self.assertNotIn('card_layout.addWidget(button)', self.settings)
        self.assertIn("presets_by_theme=deepcopy(self._heatmap_preset_preferences)", self.settings)

    def test_settings_use_four_page_responsive_shell(self) -> None:
        for marker in (
            "self.setMinimumSize(560, 560)",
            "self.setMaximumWidth(1320)",
            "outer = QGridLayout(self)",
            "outer.setRowStretch(1, 1)",
            "self.resize(1240, 860)",
            "settings_content_mode(self._settings_layout_metrics())",
            "self.nav.setVisible(extra_wide)",
            "self.section_tabs.setVisible(mode == CONTENT_MODE_INTERMEDIATE)",
            "self.section_selector_wrap.setVisible(narrow)",
            "self.compact_toolbar_layout.setDirection",
            'self.current_section in {"dashboard", "bible_verse"}',
            'self._add_page("dashboard", page)',
            'self._add_page("events", page)',
            'self._add_page("bible_verse", page)',
            'self._add_page("about_support", page)',
        ):
            self.assertIn(marker, self.settings)
        self.assertNotIn("Restore section defaults", self.settings)
        self.assertNotIn("PERSONALIZE", self.settings)

    def test_preview_is_contextual_content_sized_and_uses_bible_data(self) -> None:
        for marker in (
            "render_dashboard(",
            "preview=True",
            '[("Current section", "context"), ("Full dashboard", "full")]',
            '[("Fit", "fit"), ("Actual size", "actual")]',
            '"calendar": ".hdo-calendar-card"',
            '"study_calculations": ".hdo-summary-metrics-grid"',
            '"bible_verse": ".hdo-bible-card"',
            "var naturalWidth = focusOnly ? viewportWidth",
            "root.style.width = naturalWidth + 'px'",
            "child.style.display = child === target ? '' : 'none'",
            "document.documentElement.style.overflowY = 'auto'",
            "document.body.style.background = getComputedStyle(root).getPropertyValue('--hdo-bg')",
            "Open full preview",
            'QLabel("Sample data")',
            "representative_preview_snapshot",
            "verse_content(self.quotes[selected_quote])",
            "self.preview.setFixedHeight(max(160, min(520, height)))",
        ):
            self.assertIn(marker, self.settings)
        self.assertNotIn("Using sample data", self.settings)
        preview_source = self.settings.split("def _render_preview", 1)[1].split(
            "def _latest_stored_config", 1
        )[0]
        self.assertNotIn("scrollIntoView", preview_source)
        self.assertNotIn("Math.max(900", self.settings)
        self.assertNotIn("sample_snapshot", self.settings)

    def test_event_actions_are_owned_by_each_row(self) -> None:
        for marker in (
            "def _attach_event_menu",
            'button = QPushButton("•••")',
            "tree.setItemWidget(item, 2, button)",
            'menu.addAction("Edit")',
            'menu.addAction("Restore" if archived else "Archive")',
            'delete_action = menu.addAction("Delete")',
            '"Delete event?"',
            "self.undo_toast.show()",
        ):
            self.assertIn(marker, self.settings)
        self.assertNotIn("event_selection_state", self.settings)
        self.assertNotIn("item.setFirstColumnSpanned", self.settings)

    def test_non_narrow_forms_wrap_only_controls_that_cannot_fit(self) -> None:
        self.assertIn("QFormLayout.RowWrapPolicy.WrapLongRows", self.settings)

    def test_compound_labels_do_not_collapse_after_wrapping(self) -> None:
        self.assertIn("self._sync_minimum_height(220)", self.settings)
        self.assertIn("if self.minimumHeight() < target", self.settings)

    def test_wide_segmented_and_palette_fields_are_explicitly_stacked(self) -> None:
        self.assertIn("def _stacked_field", self.settings)
        for label in ("Appearance mode", "Heatmap palette", "Text color", "Rotation"):
            self.assertIn('                "{}",'.format(label), self.settings)

    def test_custom_bible_color_has_explicit_source_and_validation(self) -> None:
        for marker in (
            "self.font_color = QLineEdit",
            "self.font_color_swatch = QPushButton",
            '[("Theme color", "theme"), ("Custom color", "custom")]',
            're.fullmatch(r"#[0-9A-Fa-f]{6}"',
            "self.font_color.setEnabled(state[\"bible.font_color\"])",
            "self.font_color_swatch.setEnabled(state[\"bible.font_color\"])",
            "Qt.FocusPolicy.NoFocus",
            "self.font_color.setFocusPolicy(focus_policy)",
            "self.font_color_swatch.setFocusPolicy(focus_policy)",
            "self.custom_color_container.setVisible",
            "Enter a valid #RRGGBB color",
            "Low contrast",
        ):
            self.assertIn(marker, self.settings)

    def test_footer_is_a_normal_grid_row_with_dirty_save_states(self) -> None:
        footer_index = self.settings.index("outer.addWidget(self.footer_shell, 2, 0)")
        splitter_index = self.settings.index("outer.addWidget(self.splitter, 1, 0)")
        self.assertLess(splitter_index, footer_index)
        for marker in (
            'self.close_button.setText("Discard changes" if dirty else "Close")',
            'self._set_status("saving", "Saving…")',
            'self._set_status("saved", "✓ Saved")',
            'self._set_status("error", "Couldn’t save")',
            "QKeySequence.StandardKey.Save",
            "Save changes",
            "QTimer.singleShot(2000, clear_saved_status)",
        ):
            self.assertIn(marker, self.settings)
        clearance = self.settings.split("def _apply_settings_footer_clearance", 1)[1].split(
            "def _toggle_preview", 1
        )[0]
        self.assertIn("return 0", clearance)

    def test_control_system_has_vector_chevrons_contrast_and_distinct_focus(self) -> None:
        for marker in (
            "class SelectChevron(QWidget)",
            "painter.drawLine(3, 6, 8, 11)",
            "painter.drawLine(8, 11, 13, 6)",
            "QComboBox::down-arrow {{ image: none",
            '"highlight_text": _foreground_for(highlight)',
            "class SettingsSwitch(QPushButton)",
            "painter.drawRoundedRect(2, 4, 40, 24",
            "class SegmentButton(QPushButton)",
            "def move_selection",
            "QPushButton#SegmentButton:checked {{ background: {highlight}",
            "QPushButton#SegmentButton:focus {{ border: 2px solid {focus}",
        ):
            self.assertIn(marker, self.settings)

    def test_dashboard_has_exact_three_internal_areas_and_new_copy(self) -> None:
        for marker in (
            '"Appearance"',
            '"Content & study metrics"',
            '"Calendar & data"',
            '"Visible sections"',
            '"Study calculations"',
            '"Recent and lifetime statistics"',
            '"Count manually rescheduled cards as newly studied"',
            '"Retention status target"',
            '"Card background opacity"',
            '"Study totals and due dates recalculate after saving."',
        ):
            self.assertIn(marker, self.settings)

    def test_legacy_anchor_focus_cannot_override_the_settled_scroll_position(self) -> None:
        anchor_source = self.settings.split("def _scroll_dashboard_anchor", 1)[1].split(
            "def _settings_layout_metrics", 1
        )[0]
        focus_source = self.settings.split("def _ensure_settings_focus_visible", 1)[1].split(
            "def _update_preview_visibility", 1
        )[0]
        self.assertIn("self._dashboard_anchor_focus_active = True", anchor_source)
        self.assertIn("self._dashboard_anchor_focus_active = False", anchor_source)
        self.assertIn('getattr(self, "_dashboard_anchor_focus_active", False)', focus_source)
        responsive_source = self.settings.split("def _apply_responsive", 1)[1].split(
            "def _apply_settings_footer_clearance", 1
        )[0]
        self.assertIn("self._requested_dashboard_anchor", responsive_source)
        self.assertIn("self._settle_dashboard_anchor(anchor, -1, 0)", responsive_source)

    def test_capture_contract_includes_true_full_screen_month_and_year(self) -> None:
        for marker in (
            "isolated-main-window-initial-full-screen-month-rendered",
            "isolated-main-window-restart-full-screen-year-rendered",
            '"calendar_view": "month"',
            '"calendar_view": config["heatmap"]["calendar_view"]',
            "mw.isFullScreen()",
        ):
            self.assertIn(marker, self.runtime_probe)
        for marker in (
            "Rendered Anki home dashboard · Month and Year in true full-screen",
            "isolated-main-window-initial-full-screen-month-rendered.png",
            "isolated-main-window-restart-full-screen-year-rendered.png",
        ):
            self.assertIn(marker, self.contact_sheet)

    def test_two_column_labels_report_wrapped_height_to_qt(self) -> None:
        for marker in (
            "class WrappingFieldLabel(QWidget)",
            "def hasHeightForWidth(self) -> bool",
            "def heightForWidth(self, width: int) -> int",
            "return WrappingFieldLabel(title, description)",
        ):
            self.assertIn(marker, self.settings)

    def test_removed_dashboard_surfaces_have_no_settings_controls(self) -> None:
        lowered = self.settings.casefold()
        for forbidden in (
            "expand preview",
            "show most missed",
            "most missed preview",
            "selected-date panel position",
            "due-deck breakdown",
        ):
            self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
