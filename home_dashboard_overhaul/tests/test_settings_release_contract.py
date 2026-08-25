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
        cls.release_probe_base = (ROOT / "qa" / "runtime_probe_release_1_8_4.py").read_text(
            encoding="utf-8"
        )
        cls.evidence_assembler = (
            ROOT / "qa" / "assemble_release_evidence_1_8_6.py"
        ).read_text(encoding="utf-8")
        cls.repository_ignore = (ROOT.parent / ".gitignore").read_text(encoding="utf-8")
        cls.release_evidence_manifest = json.loads(
            (
                ROOT
                / "qa"
                / "release-evidence-1.8.6-2026-08-24"
                / "capture-evidence-manifest.json"
            ).read_text(encoding="utf-8")
        )
        cls.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        cls.settings_window_contract = json.loads(
            (ROOT / "qa" / "settings_window_contract_1_8_7.json").read_text(
                encoding="utf-8"
            )
        )

    def test_release_metadata_and_schema_eight_are_current(self) -> None:
        self.assertEqual(self.manifest["human_version"], "1.8.7")
        self.assertEqual(self.settings_window_contract["release"], "1.8.7")
        self.assertEqual(self.settings_window_contract["schema_version"], 8)
        self.assertEqual(
            self.settings_window_contract["pages"],
            ["dashboard", "events", "bible_verse", "about_support"],
        )
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

    def test_settings_use_one_canonical_native_shell(self) -> None:
        for marker in (
            "self.setMinimumSize(680, 560)",
            "self.resize(680, 620)",
            "self.settings_shell.setMaximumWidth(1240)",
            "self.settings_shell.setSizePolicy(",
            "self._update_settings_shell_margins()",
            "inset = max(0, (self.width() - 1240) // 2)",
            "self.nav.setFixedWidth(152)",
            "outer.setRowStretch(1, 1)",
            "outer.addWidget(self.header_shell, 0, 0)",
            "outer.addWidget(self.body_shell, 1, 0)",
            "outer.addWidget(self.footer_shell, 2, 0)",
            'self._add_page("dashboard", page)',
            'self._add_page("events", page)',
            'self._add_page("bible_verse", page)',
            'self._add_page("about_support", page)',
        ):
            self.assertIn(marker, self.settings)
        for retired_geometry in (
            "self.setMinimumSize(min(1040, width), min(700, height))",
            "self.setMinimumSize(1040, 700)",
            "self.resize(1200, 800)",
        ):
            self.assertNotIn(retired_geometry, self.settings)
        self.assertNotIn("setFixedSize(width, height)", self.settings)
        self.assertNotIn("setFixedSize(1200, 800)", self.settings)
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

    def test_window_uses_parented_standard_dialog_exec_contract(self) -> None:
        for marker in (
            "parent: QWidget",
            "super().__init__(parent)",
            "self.setMinimumSize(680, 560)",
            "self.resize(680, 620)",
            "self._settle_initial_scroll_top()",
            "self.nav.setFocus(Qt.FocusReason.OtherFocusReason)",
        ):
            self.assertIn(marker, self.settings)
        opener = self.controller.split("    def open_settings(", 1)[1].split(
            "    def request_settings_open", 1
        )[0]
        self.assertIn("dialog = SettingsDialog(mw, self, page_name, date_value, event_value)", opener)
        self.assertIn("dialog.exec()", opener)
        for forbidden_opening_marker in (
            "settings_dialog",
            "setWindowModality",
            "WindowModal",
            "dialog.open()",
            "dialog.show()",
            "dialog.finished",
            "dialog.deleteLater()",
            "dialog.raise_()",
            "dialog.activateWindow()",
        ):
            self.assertNotIn(forbidden_opening_marker, opener)
        dialog_source = self.settings.split("class SettingsDialog(QDialog):", 1)[1].split(
            "def install_settings_menu", 1
        )[0]
        for forbidden_geometry in (
            "availableGeometry",
            "QApplication.primaryScreen",
            "clamp_window_size",
            "self.screen()",
            "self.move(",
            "settingsWindowSize",
            "def _settle_window_to_screen",
            "def showEvent",
        ):
            self.assertNotIn(forbidden_geometry, dialog_source)
        for retired_window_marker in (
            "Qt.WindowType.Tool",
            "Qt.WindowModality.NonModal",
            "setTransientParent",
            "_attach_transient_parent",
            "_attach_macos_settings_window",
            "_detach_macos_settings_window",
            "objc_msgSend",
            "self.winId()",
        ):
            self.assertNotIn(retired_window_marker, self.settings)
        self.assertNotIn("settingsWindowSize", json.dumps(self.config))
        self.assertEqual(self.settings_window_contract["minimum_size"], [680, 560])
        self.assertEqual(self.settings_window_contract["initial_size"], [680, 620])
        self.assertTrue(self.settings_window_contract["resizable_upward"])
        self.assertIn("scroll.setWidgetResizable(True)", dialog_source)
        self.assertIn(
            "scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)",
            dialog_source,
        )

    def test_bridge_settings_open_is_deferred_without_retaining_a_dialog(self) -> None:
        bridge_source = self.controller.split("    def request_settings_open(", 1)[1].split(
            "    def save_config", 1
        )[0]
        self.assertIn("QTimer.singleShot(0, self._open_pending_settings)", bridge_source)
        self.assertIn("self._pending_settings_request", bridge_source)
        self.assertIn("self._settings_open_pending", bridge_source)
        self.assertNotIn("SettingsDialog", bridge_source)
        self.assertNotIn("settings_dialog", bridge_source)

    def test_native_probe_window_overrides_remain_outside_product_code(self) -> None:
        self.assertNotIn("SETTINGS_SIZE_KEY", self.settings)
        self.assertNotIn("QSettings", self.settings)
        self.assertIn("def _center_decorated_settings_frame", self.release_probe)
        self.assertIn(
            "dialog.move(dialog.x() + delta_x, dialog.y() + delta_y)",
            self.release_probe,
        )
        self.assertIn('"decorated_frame": [frame.x(), frame.y(), frame.width(), frame.height()]', self.release_probe)

    def test_fixed_settings_rail_wraps_without_eliding_large_font_labels(self) -> None:
        for marker in (
            "self.setWordWrap(True)",
            "self.setTextElideMode(Qt.TextElideMode.ElideNone)",
            "def refresh_item_sizes(self) -> None:",
            "lines * metrics.lineSpacing() + self._ITEM_VERTICAL_INSET",
            "self.nav.refresh_item_sizes()",
        ):
            self.assertIn(marker, self.settings)
        for marker in (
            '"nav_word_wrap": dialog.nav.wordWrap()',
            '"nav_elision_disabled": dialog.nav.textElideMode() == Qt.TextElideMode.ElideNone',
            '"nav_about_visual_height": about_item_height',
            '"About & support did not receive a two-line row at 150 percent app font"',
        ):
            self.assertIn(marker, self.release_probe)

    def test_restart_smoke_separates_transient_queue_state_from_exact_fixture_limits(self) -> None:
        self.assertIn("RESTART_PRE_FIXTURE_EXPECTED_NEW = 10", self.release_probe_base)
        self.assertIn("base.RESTART_PRE_FIXTURE_EXPECTED_NEW = None", self.release_probe)
        self.assertIn("RESTART_MULTI_DECK_EXPECTED_TOTAL = 10", self.release_probe_base)
        self.assertIn("base.RESTART_MULTI_DECK_EXPECTED_TOTAL = 12", self.release_probe)
        self.assertIn(
            'pre_fixture_queue["new"] + pre_fixture_queue["learning"] + pre_fixture_queue["review"]',
            self.release_probe_base,
        )
        self.assertIn('expected_new=10', self.release_probe_base)
        self.assertIn('expected_total=(RESTART_MULTI_DECK_EXPECTED_TOTAL if STAGE == "restart" else 10)', self.release_probe_base)
        self.assertIn("expected_progress = _progress_presentation(snapshot).label", self.release_probe_base)
        self.assertIn('state.get("progressLabel") != expected_progress', self.release_probe_base)

    def test_report_sheet_distinguishes_new_limit_from_total_restart_workload(self) -> None:
        self.assertIn(
            "restart New = 10, Total = 12",
            self.evidence_assembler,
        )
        self.assertIn("resizable window policy", self.evidence_assembler)
        self.assertNotIn("fixed window policy", self.evidence_assembler)
        self.assertIn('"details": contact_sheets["detail_sheet_count"]', self.evidence_assembler)
        self.assertIn('"total": len(contact_sheets["sheets"])', self.evidence_assembler)

    def test_generated_1_8_6_contact_sheets_remain_local_only(self) -> None:
        ignored_directory = (
            "home_dashboard_overhaul/qa/"
            "release-evidence-1.8.6-2026-08-24/contact-sheets/"
        )
        self.assertIn(ignored_directory, self.repository_ignore)
        self.assertEqual(
            self.release_evidence_manifest["contact_sheets"]["repository_tracking"],
            "local-only",
        )
        self.assertIn('"repository_tracking": "local-only"', self.evidence_assembler)
        self.assertIn("retained as local-only release evidence", self.evidence_assembler)

    def test_settings_is_native_only_and_contains_no_preview_path(self) -> None:
        self.assertNotIn("preview", self.settings.casefold())
        for forbidden in (
            "AnkiWebView",
            "aqt.webview",
            "QWebEngine",
            "stdHtml",
            "focusChanged",
            "setWindowModality",
            "setModal(",
        ):
            self.assertNotIn(forbidden, self.settings)

    def test_page_changes_are_timer_free_and_controls_sync_immediately(self) -> None:
        section_source = self.settings.split("    def _show_section", 1)[1].split(
            "    def _schedule_dashboard_anchor", 1
        )[0]
        self.assertIn("self.stack.setCurrentIndex(self.page_indices[section_id])", section_source)
        self.assertNotIn("QTimer", section_source)
        self.assertNotIn("SettingsDialog", section_source)
        self.assertNotIn("_settings_changed", section_source)
        connect_source = self.settings.split("    def _connect_change_signals", 1)[1].split(
            "    @staticmethod", 1
        )[0]
        self.assertIn("connect(self._settings_changed)", connect_source)
        changed_source = self.settings.split("    def _settings_changed", 1)[1].split(
            "    def _gather", 1
        )[0]
        self.assertIn("self._sync_draft()", changed_source)
        self.assertNotIn("QTimer", changed_source)

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
            'self.selected_badge = QLabel("Selected")',
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
