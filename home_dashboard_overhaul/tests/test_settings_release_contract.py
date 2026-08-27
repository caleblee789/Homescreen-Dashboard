from __future__ import annotations

import ast
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
        cls.release_probe = (ROOT / "qa" / "runtime_probe_release_1_8_7.py").read_text(
            encoding="utf-8"
        )
        cls.release_probe_base = (ROOT / "qa" / "runtime_probe_release_1_8_4.py").read_text(
            encoding="utf-8"
        )
        cls.evidence_assembler = (
            ROOT / "qa" / "assemble_release_evidence_1_8_7.py"
        ).read_text(encoding="utf-8")
        cls.settings_review_assembler = (
            ROOT / "qa" / "assemble_settings_review_evidence_1_8_7.py"
        ).read_text(encoding="utf-8")
        cls.repository_ignore = (ROOT.parent / ".gitignore").read_text(encoding="utf-8")
        cls.release_evidence_manifest = json.loads(
            (
                ROOT
                / "qa"
                / "release-evidence-1.8.6-2026-08-25"
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
            self.settings_window_contract["settings_profile_acceptance_gate"],
            "a structured exact-package macOS report must pass both full-screen opening paths with no desktop or Space switch; the 41 PNGs cannot satisfy or waive this gate",
        )
        self.assertEqual(
            self.settings_window_contract["capture_surface_verification"],
            "every PNG must sample-match the live Settings client so a same-sized Dashboard background cannot pass; all 12 page captures must use the complete decorated native Settings frame",
        )
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
            "class SettingsDialog(QDialog):",
            "SETTINGS_SHELL_MAX_WIDTH = 1240",
            "SETTINGS_PAGE_MAX_WIDTH = 980",
            "SETTINGS_COMPACT_BODY_WIDTH = 820",
            "SETTINGS_SIDEBAR_WIDTH = 184",
            "SETTINGS_HEADER_HEIGHT = 72",
            "SETTINGS_FOOTER_MIN_HEIGHT = 60",
            "self.settings_shell.setMaximumWidth(SETTINGS_SHELL_MAX_WIDTH)",
            "self.settings_shell.setSizePolicy(",
            "self._update_settings_shell_margins()",
            "inset = max(0, (self.width() - SETTINGS_SHELL_MAX_WIDTH) // 2)",
            "self.sidebar_panel.setFixedWidth(SETTINGS_SIDEBAR_WIDTH)",
            "self.header_stack.setFixedHeight(SETTINGS_HEADER_HEIGHT)",
            "outer.addWidget(self.sidebar_panel, 0, 0, 3, 1)",
            "outer.setRowStretch(1, 1)",
            "outer.addWidget(self.header_shell, 0, 1)",
            "outer.addWidget(self.body_shell, 1, 1)",
            "outer.addWidget(self.footer_shell, 2, 1)",
            "scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)",
            "page.setMaximumWidth(SETTINGS_PAGE_MAX_WIDTH)",
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
            "self.resize(680, 620)",
            "setFixedSize(width, height)",
            "setFixedSize(1200, 800)",
        ):
            self.assertNotIn(retired_geometry, self.settings)
        shell_source = self.settings.split("dialog_layout = QHBoxLayout(self)", 1)[1].split(
            "outer = QGridLayout(self.settings_shell)", 1
        )[0]
        self.assertNotIn("addStretch", shell_source)
        self.assertNotIn("class SettingsWorkspace(QWidget):", self.settings)

    def test_window_uses_parented_standard_dialog_exec_contract(self) -> None:
        for marker in (
            "parent: QWidget",
            "super().__init__(parent)",
            'self.setWindowTitle("Home Screen Dashboard Settings")',
            "self.setMinimumSize(*SETTINGS_MINIMUM_SIZE)",
            "self._apply_initial_window_geometry(parent)",
            "SETTINGS_GEOMETRY_KEY = \"home_dashboard_overhaul/settings_dialog_geometry/v3\"",
            "SETTINGS_GEOMETRY_SCREEN_KEY = \"home_dashboard_overhaul/settings_dialog_geometry/v3_screen\"",
            "saved = self._rect_tuple(self._geometry_settings.value(SETTINGS_GEOMETRY_KEY))",
            "saved_valid = saved_window_geometry_is_valid(",
            "geometry = clamp_window_geometry(",
            "self.setGeometry(QRect(*geometry))",
            "or self.isMaximized()",
            "or self.isFullScreen()",
            "self._settle_initial_scroll_top()",
        ):
            self.assertIn(marker, self.settings)
        opener = self.controller.split("    def open_settings(", 1)[1].split(
            "    def request_settings_open", 1
        )[0]
        for marker in (
            "from .settings import SettingsDialog",
            "dialog = SettingsDialog(",
            "            mw,",
            "            self,",
            "dialog.exec()",
        ):
            self.assertIn(marker, opener)
        for forbidden_opening_marker in (
            "self.settings_dialog",
            "SettingsWorkspace",
            "centralwidget",
            "host_layout",
            "dialog.show()",
            "dialog.open()",
            "dialog.finished",
            "dialog.deleteLater()",
            "dialog.raise_()",
            "dialog.activateWindow()",
            "dialog.move(",
        ):
            self.assertNotIn(forbidden_opening_marker, opener)
        dialog_source = self.settings.split("class SettingsDialog(QDialog):", 1)[1].split(
            "def _object_name", 1
        )[0]
        for forbidden_marker in (
            "self.move(",
            "def showEvent",
            "setWindowModality",
            "setModal(",
            "setWindowFlags",
            "activateWindow()",
            "raise_()",
            "setFocus(",
            "setFocusProxy(",
            "installEventFilter(self)",
            "AnkiWebView",
            "QWebEngine",
            "Qt.WindowType.Window",
            "Qt.WindowType.CustomizeWindowHint",
        ):
            self.assertNotIn(forbidden_marker, dialog_source)
        for retired_placement_marker in (
            "def _clamped_settings_origin(",
            "def _place_settings_dialog(",
            "def _report_settings_placement_failure(",
            "dialog.move(",
            "parent.screen()",
            "screen.availableGeometry()",
        ):
            self.assertNotIn(retired_placement_marker, self.controller)
        self.assertNotIn("class SettingsWorkspace(QWidget):", self.settings)
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
        self.assertEqual(self.settings_window_contract["minimum_size"], [920, 640])
        self.assertEqual(self.settings_window_contract["default_size"], [1080, 760])
        self.assertEqual(
            self.settings_window_contract["screen_margins"],
            {"normal": 48, "small_screen_fallback": 24},
        )
        self.assertEqual(self.settings_window_contract["minimum_saved_visible_ratio"], .8)
        self.assertTrue(self.settings_window_contract["native_window"])
        self.assertTrue(self.settings_window_contract["logical_coordinates"])
        self.assertTrue(self.settings_window_contract["movable"])
        self.assertTrue(self.settings_window_contract["resizable"])
        self.assertEqual(
            self.settings_window_contract["initial_placement"],
            "restore a valid logical v3 QRect on its connected screen or center on the active parent screen before first visibility",
        )

    def test_native_capture_cannot_accept_the_dashboard_background(self) -> None:
        dialog_source = self.settings.split("class SettingsDialog(QDialog):", 1)[1].split(
            "def _object_name", 1
        )[0]
        for marker in (
            "settings_surface_match_ratio",
            "settings_surface_verified",
            "decorated_window_included",
            "native_frame_decoration",
            "active_dialog.exec()",
            "Settings page capture lacks native window decoration",
            "native Settings capture sampled the parent background instead of the Settings surface",
        ):
            self.assertIn(marker, self.release_probe)
        for marker in (
            'record.get("settings_surface_verified") is True',
            'record.get("capture_scope") == "complete-decorated-settings-window"',
            'str(record.get("capture_method", "")).startswith("QScreen.grabWindow")',
        ):
            self.assertIn(marker, self.settings_review_assembler)
        self.assertTrue(self.settings_window_contract["pre_exec_geometry"])
        self.assertFalse(self.settings_window_contract["reposition_after_open"])
        self.assertEqual(
            self.settings_window_contract["initial_grid_mount"],
            "parent every new field to its Settings card before showing or visibility filtering",
        )
        self.assertFalse(self.settings_window_contract["temporary_field_windows"])
        self.assertIn("scroll.setWidgetResizable(True)", dialog_source)
        self.assertIn(
            "scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)",
            dialog_source,
        )
        for shortcut_owner in (
            "self.escape_action",
            "self.save_shortcut",
            "self.close_shortcut",
            "self.escape_shortcut",
        ):
            shortcut_source = self.settings.split(shortcut_owner, 1)[1].split(
                "self.addAction", 1
            )[0]
            self.assertIn(
                "Qt.ShortcutContext.WidgetWithChildrenShortcut",
                shortcut_source,
            )

        navigation_source = self.settings.split("    def _nav_changed", 1)[1].split(
            "    def _schedule_dashboard_anchor", 1
        )[0]
        self.assertIn("self.stack.setCurrentIndex", navigation_source)
        for lifecycle_marker in (
            "attach(",
            "hide()",
            "show()",
            "setFocus(",
            "window()",
            "QTimer",
        ):
            self.assertNotIn(lifecycle_marker, navigation_source)

    def test_primary_save_and_close_prompts_are_embedded_children(self) -> None:
        self.assertIn("class SettingsPromptPage(QWidget):", self.settings)
        self.assertIn("self._content_stack.setCurrentWidget(prompt)", self.settings)
        self.assertIn("self._content_stack.setCurrentWidget(self.settings_shell)", self.settings)
        self.assertIn('"Discard unsaved changes?"', self.settings)
        self.assertIn('"Settings changed elsewhere"', self.settings)
        self.assertIn("self._show_prompt(", self.settings)
        self.assertIn(
            'expected_visible_scrollers = 0 if special == "close-confirmation" else 1',
            self.release_probe,
        )
        self.assertGreaterEqual(
            self.release_probe.count('if special != "close-confirmation":'),
            3,
        )
        primary_source = self.settings.split("    def _save(self) -> None:", 1)[1].split(
            "def _object_name", 1
        )[0]
        self.assertNotIn("message = QMessageBox(self)", primary_source)
        self.assertNotIn("message.exec()", primary_source)
        for marker in (
            "def reject(self) -> None:",
            "def closeEvent(self, event: Any) -> None:",
            "self.request_close()",
            "super().reject()",
            "event.ignore()",
        ):
            self.assertIn(marker, primary_source)

    def test_native_menu_is_direct_and_only_bridge_opening_is_deferred(self) -> None:
        bridge_source = self.controller.split("    def request_settings_open(", 1)[1].split(
            "    def save_config", 1
        )[0]
        self.assertIn("QTimer.singleShot(0, lambda: self._open_pending_settings(token))", bridge_source)
        self.assertIn("self._pending_settings_request", bridge_source)
        self.assertIn("self._settings_open_pending", bridge_source)
        self.assertIn("token != self._settings_request_token", bridge_source)
        self.assertNotIn("SettingsDialog", bridge_source)
        self.assertNotIn("settings_dialog", bridge_source)
        menu_source = self.settings.split("def install_settings_menu", 1)[1]
        self.assertIn("action.triggered.connect(controller.open_settings)", menu_source)
        for retired in (
            "_settings_workspace",
            "_settings_menu_waiting_for_hide",
            "request_settings_open_from_menu",
            "settings_menu_about_to_hide",
            "aboutToHide",
            "QTimer.singleShot(50",
            "_connect_settings_menu_handoff",
        ):
            self.assertNotIn(retired, self.controller + self.settings)

    def test_native_probe_window_overrides_remain_outside_product_code(self) -> None:
        self.assertIn("SETTINGS_GEOMETRY_KEY", self.settings)
        self.assertIn("QSettings", self.settings)
        self.assertIn("def _apply_initial_window_geometry", self.settings)
        self.assertIn("def _persist_window_geometry", self.settings)
        self.assertIn('"decorated_frame": [frame.x(), frame.y(), frame.width(), frame.height()]', self.release_probe)
        for forbidden in (
            "WindowStaysOnTopHint",
            "dialog.raise_()",
            "dialog.activateWindow()",
            "dialog.move(dialog.x()",
            "dialog.setFixedSize(",
        ):
            self.assertNotIn(forbidden, self.settings)
        self.assertNotIn("WindowStaysOnTopHint", self.release_probe)

    def test_fixed_settings_rail_wraps_without_eliding_large_font_labels(self) -> None:
        for marker in (
            "self.setWordWrap(False)",
            "self.setTextElideMode(Qt.TextElideMode.ElideNone)",
            "def refresh_item_sizes(self) -> None:",
            "max(36, metrics.lineSpacing() + self._ITEM_VERTICAL_INSET)",
            "def labels_fit(self) -> bool:",
            "metrics.horizontalAdvance(self.item(row).text()) <= available",
            "self.compact_nav = QTabBar(self.header_shell)",
            "self.compact_nav.setElideMode(Qt.TextElideMode.ElideNone)",
            "compact = self._screen_compact_fallback or shell_width < SETTINGS_COMPACT_BODY_WIDTH",
            "self.nav.refresh_item_sizes()",
        ):
            self.assertIn(marker, self.settings)
        for marker in (
            '"nav_word_wrap": dialog.nav.wordWrap()',
            '"nav_elision_disabled": dialog.nav.textElideMode() == Qt.TextElideMode.ElideNone',
            '"compact_nav_visible": dialog.compact_nav.isVisible()',
            '"compact_nav_elision_disabled": dialog.compact_nav.elideMode() == Qt.TextElideMode.ElideNone',
            '"Settings rail wraps labels"',
            "expected_single_line_height = max(",
            'int(state.get("nav_font_line_spacing", 0)) + 12',
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

    def test_statistics_probe_keeps_clock_relative_eta_out_of_exact_parity(self) -> None:
        self.assertIn(
            'CLOCK_RELATIVE_METRIC_KEYS = frozenset({"queue.eta"})',
            self.release_probe,
        )
        self.assertIn("stable_initial == stable_live", self.release_probe)
        self.assertIn("stable_live == canonical_stable", self.release_probe)
        self.assertIn(
            'initial.get("initial_progress") == state.get("progressLabel")',
            self.release_probe,
        )
        self.assertIn(
            '"parity_policy": "nonempty-clock-relative-presentation"',
            self.release_probe,
        )

    def test_settings_review_capture_retains_failures_and_still_builds_sheets(self) -> None:
        for marker in (
            'base.REPORT.setdefault("settings_case_failures", {})',
            'capture_state["layout_assertions"]',
            'base.REPORT["capture_completion_status"] = "complete"',
            '"review-failed" if settings_failures else "passed"',
        ):
            self.assertIn(marker, self.release_probe)
        for marker in (
            "complete 100%-font Settings review sheets",
            '"settings-100-review"',
            '"each_native_capture_in_details_exactly_once": True',
            'else "review-incomplete-nonrelease"',
            '"release_ready": False',
            "refusing to overwrite review evidence",
            "def _validate_fullscreen_report(",
            'parser.add_argument("--fullscreen-report", required=True',
            '"--allow-unrun-fullscreen"',
            'report.get("status") == "unrun"',
            '"unrun full-screen report lacks a reason"',
            'UNRUN BY USER DIRECTION',
            '"settings-fullscreen-acceptance.json"',
            'result.get("remained_on_anki_fullscreen_space") is True',
            'result.get("desktop_or_space_switch_observed") is False',
            'report.get("desktop_space_switch_regression") == "not-observed"',
            '"resize",',
        ):
            self.assertIn(marker, self.settings_review_assembler)
        self.assertNotIn('"move_resize"', self.settings_review_assembler)

    def test_report_sheet_distinguishes_new_limit_from_total_restart_workload(self) -> None:
        self.assertIn(
            "restart New = 10, Total = 12",
            self.evidence_assembler,
        )
        self.assertIn("resizable window policy", self.evidence_assembler)
        self.assertNotIn("fixed window policy", self.evidence_assembler)
        self.assertIn('"details": contact_sheets["detail_sheet_count"]', self.evidence_assembler)
        self.assertIn(
            '"capture_details": contact_sheets["capture_detail_sheet_count"]',
            self.evidence_assembler,
        )
        self.assertIn(
            '"reports": contact_sheets["report_sheet_count"]',
            self.evidence_assembler,
        )
        self.assertIn('"total": len(contact_sheets["sheets"])', self.evidence_assembler)

    def test_generated_1_8_6_contact_sheets_are_retained_with_current_evidence(self) -> None:
        current_directory = (
            "home_dashboard_overhaul/qa/"
            "release-evidence-1.8.6-2026-08-25/contact-sheets/"
        )
        self.assertNotIn(current_directory, self.repository_ignore)
        self.assertEqual(
            self.release_evidence_manifest["contact_sheets"]["repository_tracking"],
            "current-only",
        )
        self.assertIn('"repository_tracking": "current-only"', self.evidence_assembler)
        self.assertIn("retained with this current evidence set", self.evidence_assembler)

    def test_settings_is_native_only_and_rendered_previews_are_absent(self) -> None:
        for forbidden in (
            "class DashboardCardPreview",
            "class VerseCardPreview",
            "DashboardCardPreview()",
            "VerseCardPreview()",
            "HeatmapPresetCard",
            "heatmap_preset_cards",
            "preset_swatch",
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
        self.assertIn("page_index = self.page_indices[section_id]", section_source)
        self.assertIn("self.stack.setCurrentIndex(page_index)", section_source)
        self.assertIn("self.header_stack.setCurrentIndex(page_index)", section_source)
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
            "QListWidget#SettingsNav::item:selected {{ background: {accent_soft};",
            "QTabBar#EventTabsBar {{ background: {alternate};",
            "QTabBar#EventTabsBar::tab {{ background: {alternate};",
            "QTabBar#EventTabsBar::tab:selected {{ background: {accent_soft};",
            "class SettingsTabPanel(QWidget):",
            "painter.fillRect(rect, QColor(tokens[\"accent_soft\"] if selected or semantic else tokens[\"base\"]))",
            "painter.fillRect(QRect(rect.left(), rect.top(), 3, rect.height()), QColor(tokens[\"highlight\"]))",
            "QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred",
        ):
            self.assertIn(marker, self.settings)
        for token in (
            '"ui_bg": "#0D131A"',
            '"ui_sidebar": "#0A1016"',
            '"ui_surface": "#151D25"',
            '"ui_surface_raised": "#1A242E"',
            '"ui_accent_soft": "#263B4D"',
        ):
            self.assertIn(token, (ROOT / "themes.py").read_text(encoding="utf-8"))
        self.assertNotIn("WindowStaysOnTopHint", self.settings + self.release_probe)

    def test_dashboard_cards_are_in_the_canonical_order(self) -> None:
        dashboard_source = self.settings.split("    def _build_dashboard_page", 1)[1].split(
            "    def _build_events_page", 1
        )[0]
        card_markers = (
            "appearance_card = self._create_appearance_card()",
            'SettingsCard(\n            "Dashboard sections"',
            'SettingsCard("Study metrics", "", "Reset")',
            'self.calendar_display_disclosure = DisclosureHeader(\n            "Calendar display"',
            'self.local_data_disclosure = DisclosureHeader(\n            "Local data"',
        )
        positions = [dashboard_source.index(marker) for marker in card_markers]
        self.assertEqual(positions, sorted(positions))
        for copy in (
            "History, due load, and events.",
            "Cards remaining and completion.",
            "Cards studied, time, pace, and ETA.",
            "7-day and lifetime totals.",
            "Optional verse card.",
            "Changes how pace is displayed.",
            "Used to color retention status.",
            "Counts the first qualifying answer after a manual reschedule.",
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

    def test_verse_rows_are_semantic_and_preview_fixtures_are_absent(self) -> None:
        verse_source = self.settings.split("class VerseLibraryDelegate", 1)[1].split(
            "class VerseLibraryView", 1
        )[0]
        for marker in (
            "semantic = bool(index.data(VERSE_CURRENT_ROLE) or index.data(VERSE_PENDING_ROLE))",
            'tokens["accent_soft"] if selected or semantic else tokens["base"]',
            "QRect(rect.left(), rect.top(), 3, rect.height())",
            '("✓ " if semantic else "") + first_line',
            "_two_line_excerpt(excerpt, excerpt_metrics, excerpt_rect.width())",
        ):
            self.assertIn(marker, verse_source)
        self.assertNotIn("class VerseRowWidget", self.settings)

        self.assertIn("def _refresh_heatmap_preset_options", self.settings)
        self.assertIn("self.heatmap_preset = QComboBox()", self.settings)
        for retired in (
            "def _refresh_heatmap_preset_cards",
            "selected_indicator",
            "swatches.addWidget",
        ):
            self.assertNotIn(retired, self.settings)

    def test_heatmap_text_options_refresh_only_on_explicit_paths(self) -> None:
        apply_theme_source = self.settings.split("def _apply_theme", 1)[1].split(
            "def _update_forecast_range_visibility", 1
        )[0]
        self.assertNotIn("_refresh_heatmap_preset_options", apply_theme_source)
        self.assertIn("self._update_color_swatch()", apply_theme_source)

        appearance_source = self.settings.split("def _create_appearance_card", 1)[1].split(
            "def _build_dashboard_page", 1
        )[0]
        self.assertIn(
            "self.preset.currentIndexChanged.connect(self._dashboard_theme_changed)",
            appearance_source,
        )
        self.assertIn(
            "self.mode.connect_changed(self._refresh_heatmap_preset_options)",
            appearance_source,
        )

        theme_source = self.settings.split("def _dashboard_theme_changed", 1)[1].split(
            "def _update_glass_controls", 1
        )[0]
        self.assertIn("self._refresh_heatmap_preset_options()", theme_source)

        config_source = self.settings.split("def _apply_config_to_widgets", 1)[1].split(
            "def _walk_deck_items", 1
        )[0]
        self.assertIn("self._refresh_heatmap_preset_options()", config_source)

    def test_compact_grid_adopts_fields_before_visibility_filtering(self) -> None:
        module = ast.parse(self.settings)
        dialog = next(
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "SettingsDialog"
        )
        function = next(
            node
            for node in dialog.body
            if isinstance(node, ast.FunctionDef) and node.name == "_place_grid_widgets"
        )
        function.decorator_list = []
        function.returns = None
        for argument in function.args.args:
            argument.annotation = None
        namespace: dict[str, object] = {}
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(body=[function], type_ignores=[])
                ),
                str(ROOT / "settings.py"),
                "exec",
            ),
            namespace,
        )
        place_grid_widgets = namespace["_place_grid_widgets"]

        class Field:
            def __init__(self) -> None:
                self.parent: object | None = None
                self.hidden = True
                self.show_calls = 0
                self.was_shown_as_window = False

            def parentWidget(self) -> object | None:
                return self.parent

            def setParent(self, parent: object) -> None:
                self.parent = parent

            def show(self) -> None:
                self.show_calls += 1
                self.was_shown_as_window = self.parent is None
                self.hidden = False

            def hide(self) -> None:
                self.hidden = True

            def isHidden(self) -> bool:
                return self.hidden

        class Grid:
            def __init__(self, host: object) -> None:
                self.host = host
                self.widgets: list[Field] = []

            def parentWidget(self) -> object:
                return self.host

            def count(self) -> int:
                return len(self.widgets)

            def takeAt(self, index: int) -> Field:
                return self.widgets.pop(index)

            def addWidget(self, widget: Field, _row: int, _column: int) -> None:
                self.widgets.append(widget)

            def setColumnStretch(self, _column: int, _stretch: int) -> None:
                return

            def invalidate(self) -> None:
                return

        host = object()
        grid = Grid(host)
        fields = [Field() for _ in range(4)]

        place_grid_widgets(grid, fields, 2)

        self.assertEqual(grid.widgets, fields)
        for field in fields:
            self.assertIs(field.parentWidget(), host)
            self.assertEqual(field.show_calls, 1)
            self.assertFalse(field.was_shown_as_window)

        intentionally_hidden = fields[2]
        intentionally_hidden.hide()
        place_grid_widgets(grid, fields, 2)

        self.assertTrue(intentionally_hidden.isHidden())
        self.assertEqual(intentionally_hidden.show_calls, 1)
        self.assertNotIn(intentionally_hidden, grid.widgets)
        self.assertEqual(grid.widgets, [fields[0], fields[1], fields[3]])
        for field in fields:
            self.assertIs(field.parentWidget(), host)
            self.assertFalse(field.was_shown_as_window)

    def test_event_manager_uses_two_line_rows_name_sort_and_main_scroller(self) -> None:
        for marker in (
            "class EventRowWidget(QWidget)",
            'self.title.setObjectName("EventRowTitle")',
            'self.metadata.setObjectName("EventRowMeta")',
            'self.overflow.setFixedSize(32, 32)',
            'button.setToolTip("Event actions")',
            'self.event_tabs.addTab(self.active_events, "Active (0)")',
            'self.event_tabs.addTab(self.archived_events, "Archived (0)")',
            'self.event_add = QPushButton("Add event")',
            "page._hdo_header_actions.addWidget(self.event_add)",
            '_stacked_field("Sort by", "", self.event_sort)',
            'self.event_search_clear = QPushButton("Clear")',
            'self.event_empty_clear = QPushButton("Clear search")',
            'self.event_surface.setMinimumHeight(360)',
            'tree.setMinimumHeight(260)',
            'tree.setMaximumHeight(16777215)',
            'QSize(max(1, tree.viewport().width()), 54)',
            '("Name", "name")',
            'if sort_value == "name"',
            'str(item.get("name", "")).casefold()',
            "tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)",
            "self._edit_event()",
            "tree.clearSelection()",
            '"{} matching event{}".format',
            '"No events match “{}”.".format(query)',
        ):
            self.assertIn(marker, self.settings)
        self.assertNotIn('self.event_empty_add = QPushButton("Add event")', self.settings)
        self.assertNotIn('QWidget#HomeDashboardSettings QWidget#EventRow[selected="true"]', self.settings)

    def test_bible_library_uses_reference_excerpt_badges_and_incremental_rows(self) -> None:
        for marker in (
            "class VerseLibraryModel(QAbstractListModel):",
            "class VerseLibraryDelegate(QStyledItemDelegate):",
            "class VerseLibraryView(QListView):",
            "self.quote_model = VerseLibraryModel(self)",
            "self.quote_list = VerseLibraryView()",
            "self.quote_list.setModel(self.quote_model)",
            "self._rows = []",
            "self._rows.append((source_index, reference, excerpt))",
            "_two_line_excerpt(excerpt, excerpt_metrics, excerpt_rect.width())",
            'self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)',
            '"{} verses".format(len(self.quotes))',
            '"{} matching verse{}".format',
            'SettingsCard(\n            "Rotation"',
            'SettingsCard(\n            "Verse library"',
        ):
            self.assertIn(marker, self.settings)
        for retired in (
            "VerseCardPreview",
            "class VerseRowWidget",
            "_quote_render_limit",
            "Load more",
            "Showing 100",
            "matches[:100]",
        ):
            self.assertNotIn(retired, self.settings)

    def test_about_is_compact_and_exposes_only_existing_recovery_behavior(self) -> None:
        attribution = (
            "Scripture quotations are taken from the Holy Bible, New Living Translation, "
            "copyright ©1996, 2004, 2015 by Tyndale House Foundation. Used by permission "
            "of Tyndale House Publishers. All rights reserved."
        )
        for marker in (
            'SettingsCard("Version and support")',
            "QSizePolicy.Policy.Maximum",
            'self.copy_diagnostics.setText("Copied")',
            'ExternalLinkButton("Documentation", PROJECT_URL)',
            'ExternalLinkButton("Report an issue", ISSUES_URL)',
            'SettingsCard("Privacy and legal")',
            'SettingsCard("Backup and recovery")',
            '"Dashboard data stays on this device and is not sent to external services."',
            'recovery_export = QPushButton("Export verse edits")',
            'recovery_export.clicked.connect(self._export_quotes)',
            attribution,
        ):
            self.assertIn(marker, self.settings)
        recovery_source = self.settings.split('SettingsCard("Backup and recovery")', 1)[1].split(
            "layout.addStretch()", 1
        )[0]
        for forbidden in ("restore", "reset", "import"):
            self.assertNotIn(forbidden, recovery_source.casefold())

    def test_footer_has_action_local_dirty_success_and_error_states(self) -> None:
        footer_index = self.settings.index("outer.addWidget(self.footer_shell, 2, 1)")
        body_index = self.settings.index("outer.addWidget(self.body_shell, 1, 1)")
        self.assertLess(body_index, footer_index)
        for marker in (
            'self.revert_button = QPushButton("Discard changes")',
            'self.close_button.setText("Close")',
            'self.save_button.setText("Save changes")',
            'self.error_label.setObjectName("InlineSaveError")',
            'self.details_button = QPushButton("View details")',
            "def _revert_changes(self)",
            "baseline = deepcopy(self.draft.baseline)",
            'self._set_status("saving", "Saving…")',
            'self.save_button.setText("Saving…")',
            "self.saved_status_timer.timeout.connect(self._clear_saved_status)",
            "self.saved_status_timer.setInterval(2000)",
            'self._set_status("saved", "✓ Saved")',
            "self.save_button.setEnabled(False)",
            '"Save failed. Your changes are still available."',
            "self._last_save_error_detail = detail",
            "self.draft.baseline = deepcopy(dict(failure_baseline))",
            "self.draft.values = deepcopy(dict(failure_values))",
            'self.quotes = list(self.staged["bible"]["quotes"])',
            '"● {} unsaved change{}".format',
            "self.draft.replace_all(latest_saved)",
            "self._footer_clearance_timer = QTimer(self)",
            "self._footer_clearance_timer.timeout.connect(",
            "clearance = 36",
            'self._set_status("validation-error", "Fix 1 error to save")',
            '"Enter a valid #RRGGBB color."',
            "self._schedule_settings_footer_clearance()",
            "self.footer.error_panel.isHidden()",
        ):
            self.assertIn(marker, self.settings)
        self.assertNotIn(
            "bool(text) and not self.footer.error_panel.isVisible()",
            self.settings,
        )
        self.assertNotIn("simulated transactional write failure", self.settings)

    def test_controls_grow_with_application_font_without_an_alternate_layout(self) -> None:
        for marker in (
            "target = max(INTERACTION_TARGET_MIN_PX, widget.fontMetrics().lineSpacing() + 10)",
            "return max(INTERACTION_TARGET_MIN_PX, view.fontMetrics().lineSpacing() + 12)",
            "max(56, (2 * view.fontMetrics().lineSpacing()) + 20)",
            "self.setFixedSize(44, 36)",
            "combo.setMaximumWidth(420)",
            "spin.setMaximumWidth(120)",
            "QFormLayout.RowWrapPolicy.WrapLongRows",
            "def _apply_role_fonts(root: QWidget) -> None:",
            '"PageTitle": role_font(20, QFont.Weight.DemiBold)',
            '"CardTitle": role_font(14, QFont.Weight.DemiBold)',
            '"PageHelp": role_font(12)',
            '"FieldHelp": role_font(12)',
        ):
            self.assertIn(marker, self.settings)
        self.assertNotIn("font-size:", self.settings)

    def test_untitled_surfaces_and_label_resizes_survive_native_teardown(self) -> None:
        self.assertIn('title: str = ""', self.settings)
        self.assertIn("self._resync_timer = QTimer(self)", self.settings)
        self.assertIn(
            "self._resync_timer.timeout.connect(self._resync_minimum_height)",
            self.settings,
        )
        self.assertIn("self._resync_timer.start(0)", self.settings)
        self.assertNotIn(
            "lambda: self._sync_minimum_height(self.width())",
            self.settings,
        )

    def test_legacy_calendar_route_settles_to_the_dashboard_card(self) -> None:
        self.assertIn('"": ("dashboard", "")', self.model)
        self.assertIn('"calendar": ("dashboard", "calendar")', self.model)
        constructor_tail = self.settings.split("self.open_page(initial_page", 1)[1].split(
            "def resizeEvent", 1
        )[0]
        self.assertIn("if not self._requested_dashboard_anchor:", constructor_tail)
        self.assertIn("self._settle_initial_scroll_top()", constructor_tail)
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
