from __future__ import annotations

import json
from pathlib import Path
import unittest

from home_dashboard_overhaul.themes import (
    DEFAULT_HEATMAP_PRESETS,
    HEATMAP_PRESETS,
    PRESETS,
    SETTINGS_COLOR_TOKENS,
)


ROOT = Path(__file__).resolve().parents[1]


class SettingsReleaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = (ROOT / "settings.py").read_text(encoding="utf-8")
        cls.controller = (ROOT / "controller.py").read_text(encoding="utf-8")
        cls.model = (ROOT / "settings_model.py").read_text(encoding="utf-8")
        cls.release_probe = (ROOT / "qa" / "runtime_probe_release_1_8_6.py").read_text(
            encoding="utf-8"
        )
        cls.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_release_metadata_and_schema_eight_are_current(self) -> None:
        self.assertEqual(self.manifest["human_version"], "1.8.6")
        self.assertEqual(self.config["schema_version"], 8)
        self.assertEqual(self.config["appearance"]["opacity"], 96)
        self.assertEqual(self.config["appearance"]["blur"], 12)
        self.assertNotIn("buried", self.config["visibility"])
        self.assertEqual(
            tuple(PRESETS),
            ("Sapphire Glass", "Graphite", "Emerald", "High Contrast"),
        )

    def test_saved_heatmap_ids_have_distinct_authored_light_and_dark_ladders(self) -> None:
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
            for variant in ("light", "dark"):
                ladders = []
                for name, variants in presets.items():
                    with self.subTest(theme=theme, preset=name, variant=variant):
                        tokens = variants[variant]
                        ladder = tuple(tokens["heat_complete_{}".format(level)] for level in range(6))
                        self.assertEqual(len(set(ladder)), 6)
                        ladders.append(ladder)
                        for level in range(6):
                            self.assertIn("heat_complete_text_{}".format(level), tokens)
                self.assertEqual(len(ladders), len(set(ladders)))
        self.assertEqual(
            tuple(
                HEATMAP_PRESETS["Graphite"]["Slate"]["dark"][
                    "heat_complete_{}".format(level)
                ]
                for level in range(6)
            ),
            ("#1B222A", "#303A45", "#424E5B", "#566474", "#6E7E90", "#8C9BAA"),
        )

    def test_settings_palette_is_owned_only_by_anki_appearance(self) -> None:
        self.assertEqual(set(SETTINGS_COLOR_TOKENS), {"light", "dark"})
        theme_source = self.settings.split("def _theme_tokens", 1)[1].split(
            "def _color_contrast", 1
        )[0]
        self.assertIn("del config", theme_source)
        self.assertIn('SETTINGS_COLOR_TOKENS["dark" if anki_dark else "light"]', theme_source)
        self.assertNotIn("resolve_theme", theme_source)

    def test_settings_use_one_canonical_shell_and_one_shared_preview_dock(self) -> None:
        for marker in (
            "self.setFixedSize(1200, 800)",
            "self.settings_shell.setMaximumWidth(1240)",
            "self.settings_shell.setSizePolicy(",
            "self._update_settings_shell_margins()",
            "inset = max(0, (self.width() - 1240) // 2)",
            "self.nav.setFixedWidth(152)",
            "outer.setRowStretch(1, 1)",
            "outer.addWidget(self.header_shell, 0, 0)",
            "outer.addWidget(self.body_shell, 1, 0)",
            "outer.addWidget(self.footer_shell, 2, 0)",
            'self.preview_wrap.setObjectName("PreviewDock")',
            "width < 1040",
            "1 if self._preview_overlay_mode else 2",
            'self._add_page("dashboard", page)',
            'self._add_page("events", page)',
            'self._add_page("bible_verse", page)',
            'self._add_page("about_support", page)',
        ):
            self.assertIn(marker, self.settings)
        self.assertEqual(self.settings.count('setObjectName("PreviewDock")'), 1)
        shell_source = self.settings.split("dialog_layout = QHBoxLayout(self)", 1)[1].split(
            "outer = QGridLayout(self.settings_shell)", 1
        )[0]
        self.assertNotIn("addStretch", shell_source)
        for retired in (
            "SettingsLayoutMetrics",
            "settings_content_mode",
            "section_selector",
            "section_tabs",
            "compact_toolbar",
            "CONTENT_MODE_NARROW",
            "CONTENT_MODE_INTERMEDIATE",
            "CONTENT_MODE_EXTRA_WIDE",
        ):
            self.assertNotIn(retired, self.settings)

    def test_window_matches_ankis_parented_addons_dialog_contract(self) -> None:
        for marker in (
            "super().__init__(mw)",
            "Qt.WindowModality.NonModal",
            "width, height = clamp_window_size(",
            "self.setFixedSize(width, height)",
            "available.center() - self.rect().center()",
            "QTimer.singleShot(0, self._settle_initial_scroll_top)",
        ):
            self.assertIn(marker, self.settings)
        self.assertIn("self.settings_dialog.show()", self.controller)
        self.assertNotIn("self.settings_dialog.open()", self.controller)
        reuse_source = self.controller.split(
            "if self.settings_dialog is not None and self.settings_dialog.isVisible():", 1
        )[1].split("return", 1)[0]
        self.assertLess(
            reuse_source.index("self.settings_dialog.activateWindow()"),
            reuse_source.index("self.settings_dialog.raise_()"),
        )
        self.assertNotIn("settingsWindowSize", self.settings)
        self.assertNotIn("def _settle_window_to_screen", self.settings)
        dialog_source = self.settings.split("class SettingsDialog(QDialog):", 1)[1]
        for retired_panel_marker in (
            "Qt.WindowType.Tool",
            "setTransientParent",
            "_attach_transient_parent",
        ):
            self.assertNotIn(retired_panel_marker, dialog_source)
        for native_attachment_marker in (
            "def _attach_macos_settings_window(",
            "def _detach_macos_settings_window(",
            'selector(b"addChildWindow:ordered:")',
            'selector(b"removeChildWindow:")',
            "actual_behavior & required == required",
            "actual_behavior & forbidden == 0",
            'if sys.platform == "darwin" and not self._macos_window_attached:',
            "if not _attach_macos_settings_window(self, self.parentWidget()):",
            'QMessageBox.critical(',
            "if self._macos_window_attached:",
        ):
            self.assertIn(native_attachment_marker, self.settings)
        show_source = dialog_source.split("def show(self) -> None:", 1)[1].split(
            "def showEvent", 1
        )[0]
        self.assertLess(
            show_source.index("_attach_macos_settings_window"),
            show_source.index("super().show()"),
        )
        self.assertIn("default: Tuple[int, int] = (1200, 800)", self.model)
        self.assertIn("minimum: Tuple[int, int] = (1040, 700)", self.model)
        self.assertNotIn("settingsWindowSize", json.dumps(self.config))

    def test_native_probe_window_overrides_remain_outside_product_code(self) -> None:
        self.assertNotIn("SETTINGS_SIZE_KEY", self.settings)
        self.assertNotIn("QSettings", self.settings)

    def test_preview_uses_the_production_renderer_and_approved_controls(self) -> None:
        for marker in (
            "render_dashboard(",
            "preview=True",
            '[("Section", "context"), ("Full dashboard", "full")]',
            '[("Fit", "fit"), ("100%", "actual")]',
            'self.preview_full_button = QPushButton("Open")',
            '"calendar": ".hdo-calendar-card"',
            '"bible_verse": ".hdo-bible-card"',
            "preview_snapshot_with_staged_events",
            "verse_content(self.quotes[selected_quote])",
            "root.style.transform = 'scale(' + scale + ')'",
            "document.documentElement.style.overflowY = 'auto'",
            "document.documentElement.style.overflowY = 'hidden'",
            "def _update_preview_canvas_height(self) -> None:",
            "rendered_height = max(0, self._preview_content_size.height())",
            "preferred = max(150, min(320, rendered_height + 8))",
            "self.preview_wrap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)",
        ):
            self.assertIn(marker, self.settings)
        self.assertNotIn("sample_snapshot", self.settings)

    def test_preview_visibility_is_session_only_and_about_omits_it(self) -> None:
        for marker in (
            "self._preview_visible = True",
            'if section_id != "about_support"',
            'self.current_section in {"dashboard", "events", "bible_verse"}',
            'if self.current_section == "about_support"',
        ):
            self.assertIn(marker, self.settings)
        self.assertNotIn("previewVisibility", self.settings)
        self.assertNotIn("preview_visible", json.dumps(self.config))

    def test_visual_polish_regressions_from_native_review_are_locked(self) -> None:
        for marker in (
            "QListWidget#SettingsNav::item:hover:!selected {{ color:",
            "card.setSizePolicy(\n                QSizePolicy.Policy.Expanding,\n                QSizePolicy.Policy.Preferred,",
            "dialog.setModal(True)",
            "Qt.WindowType.WindowStaysOnTopHint",
            'method = "QScreen.grabWindow-screen-client-crop"',
        ):
            source = self.release_probe if marker.startswith(("dialog.", "Qt.", "method")) else self.settings
            self.assertIn(marker, source)

    def test_dashboard_cards_are_in_the_canonical_order(self) -> None:
        card_markers = (
            '"Appearance"',
            '"Dashboard sections"',
            'SettingsCard("Study calculations")',
            'SettingsCard("Calendar display")',
            'SettingsCard("Calendar range")',
            'SettingsCard("Data and reset"',
        )
        positions = [self.settings.index(marker) for marker in card_markers]
        self.assertEqual(positions, sorted(positions))
        for copy in (
            "Study history, due load, and events.",
            "Cards remaining and completion.",
            "Display only. Study history is unchanged.",
            "Calendar totals update after saving.",
        ):
            self.assertIn(copy, self.settings)

    def test_sapphire_only_fields_are_hidden_without_discarding_values(self) -> None:
        source = self.settings.split("def _update_glass_controls", 1)[1].split(
            "def _select_heatmap_preset", 1
        )[0]
        self.assertIn('== "Sapphire Glass"', source)
        self.assertIn("self.opacity_field.setVisible(enabled)", source)
        self.assertIn("self.blur_field_label.setVisible(enabled)", source)
        self.assertIn("self.blur_field.setVisible(enabled)", source)
        self.assertNotIn("setValue", source)

    def test_event_manager_uses_two_line_rows_name_sort_and_main_scroller(self) -> None:
        for marker in (
            "class EventRowWidget(QWidget)",
            'self.title.setObjectName("EventRowTitle")',
            'self.metadata.setObjectName("EventRowMeta")',
            'self.overflow.setFixedSize(32, 32)',
            'self.event_tabs.addTab(self.active_events, "Active (0)")',
            'self.event_tabs.addTab(self.archived_events, "Archived (0)")',
            'self.event_empty_add = QPushButton("Add event")',
            '("Name", "name")',
            'if sort_value == "name"',
            'str(item.get("name", "")).casefold()',
            "tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)",
            "tree.setFixedHeight(max(2, tree.topLevelItemCount() * row_height + 8))",
        ):
            self.assertIn(marker, self.settings)

    def test_bible_library_uses_reference_excerpt_badges_and_incremental_rows(self) -> None:
        for marker in (
            "class VerseRowWidget(QWidget)",
            'self.current_badge = QLabel("Current")',
            'self.preview_badge = QLabel("Preview")',
            "split_quote_reference(quote)",
            "self._quote_render_limit = 100",
            "self._quote_render_limit += 100",
            "matches[:self._quote_render_limit]",
            "self.quote_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)",
            "self.quote_list.setFixedHeight(max(2, self.quote_list.count() * row_height + 8))",
            'SettingsCard(\n            "Rotation"',
            'SettingsCard(\n            "Verse library"',
        ):
            self.assertIn(marker, self.settings)

    def test_about_is_compact_and_exposes_only_existing_recovery_behavior(self) -> None:
        attribution = (
            "Scripture quotations are taken from the Holy Bible, New Living Translation, "
            "copyright ©1996, 2004, 2015 by Tyndale House Foundation. Used by permission "
            "of Tyndale House Publishers. All rights reserved."
        )
        for marker in (
            'SettingsCard("Version & compatibility")',
            'SettingsCard("Help")',
            "top_cards.addWidget(version_card, 0, 0)",
            "top_cards.addWidget(help_card, 0, 1)",
            'SettingsCard("Privacy & legal")',
            'SettingsCard("Backup and recovery")',
            'recovery_export.clicked.connect(self._export_quotes)',
            attribution,
        ):
            self.assertIn(marker, self.settings)
        recovery_source = self.settings.split('SettingsCard("Backup and recovery")', 1)[1].split(
            "layout.addStretch()", 1
        )[0]
        for forbidden in ("restore", "reset", "import"):
            self.assertNotIn(forbidden, recovery_source.casefold())

    def test_footer_has_stable_actions_revert_and_inline_error(self) -> None:
        footer_index = self.settings.index("outer.addWidget(self.footer_shell, 2, 0)")
        body_index = self.settings.index("outer.addWidget(self.body_shell, 1, 0)")
        self.assertLess(body_index, footer_index)
        for marker in (
            'self.revert_button = QPushButton("Revert changes")',
            'self.close_button.setText("Close")',
            'self.save_button.setText("Save changes")',
            'self.save_error.setObjectName("InlineSaveError")',
            "def _revert_changes(self)",
            "baseline = deepcopy(self.draft.baseline)",
            'self._set_status("saving", "Saving…")',
            "self.saved_status_timer.timeout.connect(self._clear_saved_status)",
            "self.saved_status_timer.start()",
            "self.save_button.setEnabled(False)",
            'self._last_save_error = "Could not save changes: {}".format(detail)',
            "self.draft.replace_all(latest_saved)",
        ):
            self.assertIn(marker, self.settings)
        self.assertNotIn('setText("Discard changes"', self.settings)

    def test_controls_grow_with_application_font_without_an_alternate_layout(self) -> None:
        for marker in (
            "widget.fontMetrics().lineSpacing() + 10",
            "view.fontMetrics().lineSpacing() + 12",
            "max(56, (2 * view.fontMetrics().lineSpacing()) + 20)",
            "self.setFixedSize(34, 20)",
            "combo.setMaximumWidth(260)",
            "spin.setMaximumWidth(92)",
            "QFormLayout.RowWrapPolicy.WrapLongRows",
        ):
            self.assertIn(marker, self.settings)

    def test_legacy_calendar_route_settles_to_the_dashboard_card(self) -> None:
        self.assertIn('"calendar": ("dashboard", "calendar")', self.model)
        source = self.settings.split("def _schedule_dashboard_anchor", 1)[1].split(
            "def _apply_canonical_layout", 1
        )[0]
        for marker in (
            "self._requested_dashboard_anchor = anchor",
            "QTimer.singleShot(0, lambda: self._settle_dashboard_anchor(anchor, -1, 0))",
            "target_y = target.mapTo(page, QPoint(0, 0)).y()",
            "value = max(0, target_y - 2)",
            "scroll.verticalScrollBar().setValue(value)",
        ):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
