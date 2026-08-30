from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from home_dashboard_overhaul.themes import (
    DEFAULT_HEATMAP_PRESETS,
    HEATMAP_PRESETS,
    PRESETS,
    SETTINGS_COLOR_TOKENS,
)
from home_dashboard_overhaul.settings_model import history_range_choice


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
        cls.fullscreen_probe = (
            ROOT / "qa" / "runtime_probe_fullscreen_profile.py"
        ).read_text(encoding="utf-8")
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
                / "release-evidence-1.8.7-2026-08-30-4d0a4107-ui-readiness-100"
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

    def _verse_import_reader(self):
        tree = ast.parse(self.settings)
        selected_nodes = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name)
                and target.id == "MAX_VERSE_IMPORT_BYTES"
                for target in node.targets
            ):
                selected_nodes.append(node)
            elif (
                isinstance(node, ast.FunctionDef)
                and node.name == "_read_verse_import_text"
            ):
                selected_nodes.append(node)
        self.assertEqual(len(selected_nodes), 2)
        namespace = {"Path": lambda value: value}
        module = ast.Module(body=selected_nodes, type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, str(ROOT / "settings.py"), "exec"), namespace)
        return namespace["MAX_VERSE_IMPORT_BYTES"], namespace["_read_verse_import_text"]

    def test_oversized_verse_import_is_rejected_before_opening_the_file(self) -> None:
        maximum, read_import = self._verse_import_reader()

        class OversizedPath:
            opened = False

            @staticmethod
            def stat():
                return SimpleNamespace(st_size=maximum + 1)

            def open(self, _mode):
                self.opened = True
                raise AssertionError("oversized import must not be opened")

        selected = OversizedPath()
        with self.assertRaisesRegex(ValueError, "16 MB import limit"):
            read_import(selected)
        self.assertFalse(selected.opened)

    def test_verse_import_read_remains_bounded_if_file_grows_after_stat(self) -> None:
        maximum, read_import = self._verse_import_reader()

        class OversizedChunk:
            def __len__(self):
                return maximum + 1

        class GrowingPath:
            requested = None

            @staticmethod
            def stat():
                return SimpleNamespace(st_size=maximum)

            def open(self, mode):
                self.assert_mode = mode
                return self

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, requested):
                self.requested = requested
                return OversizedChunk()

        selected = GrowingPath()
        with self.assertRaisesRegex(ValueError, "16 MB import limit"):
            read_import(selected)
        self.assertEqual(selected.assert_mode, "rb")
        self.assertEqual(selected.requested, maximum + 1)

    def test_verse_import_ui_uses_bounded_reader_and_existing_error_surface(self) -> None:
        import_source = self.settings.split("    def _import_quotes(self) -> None:", 1)[1].split(
            "    def _export_quotes(self) -> None:", 1
        )[0]
        self.assertIn("text = _read_verse_import_text(path)", import_source)
        self.assertNotIn("read_text", import_source)
        self.assertIn(
            'QMessageBox.critical(self, "Import failed", str(exc)); return',
            import_source,
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
        self.assertIn("_settings_palette_source(bool(anki_dark))", theme_source)
        self.assertNotIn("resolve_theme", theme_source)

    def test_settings_use_one_canonical_native_shell(self) -> None:
        for marker in (
            "class SettingsDialog(QDialog):",
            "SETTINGS_SHELL_MAX_WIDTH = 1264",
            "SETTINGS_PAGE_MAX_WIDTH = 1080",
            "SETTINGS_ABOUT_MAX_WIDTH = 1080",
            "SETTINGS_COMPACT_BODY_WIDTH = 860",
            "SETTINGS_TWO_COLUMN_CONTENT_WIDTH = 760",
            "SETTINGS_SIDEBAR_WIDTH = 184",
            "SETTINGS_HEADER_HEIGHT = 72",
            "SETTINGS_FOOTER_MIN_HEIGHT = 56",
            "self.settings_shell.setMaximumWidth(SETTINGS_SHELL_MAX_WIDTH)",
            "self.settings_shell.setSizePolicy(",
            "self._update_settings_shell_margins()",
            "inset = max(0, (self.width() - SETTINGS_SHELL_MAX_WIDTH) // 2)",
            "self.sidebar_panel.setFixedWidth(SETTINGS_SIDEBAR_WIDTH)",
            "self.header_stack.setMinimumHeight(SETTINGS_HEADER_HEIGHT)",
            "outer.addWidget(self.sidebar_panel, 0, 0, 4, 1)",
            "outer.setRowStretch(1, 1)",
            "outer.addWidget(self.header_shell, 0, 1)",
            "outer.addWidget(self.body_shell, 1, 1)",
            "outer.addWidget(self.footer.error_panel, 2, 1)",
            "outer.addWidget(self.footer_shell, 3, 1)",
            "scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)",
            "page.setMaximumWidth(",
            "if page is getattr(self, \"about_page\", None)",
            "else SETTINGS_PAGE_MAX_WIDTH",
            "SETTINGS_ABOUT_MAX_WIDTH",
            'page_padding = SETTINGS_SPACING["compact_page"] if compact else SETTINGS_SPACING["page"]',
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
            "self.setMinimumSize(\n            min(SETTINGS_MINIMUM_SIZE[0], geometry[2])",
            "self._apply_initial_window_geometry(parent)",
            "SETTINGS_GEOMETRY_KEY = \"home_dashboard_overhaul/settings_dialog_geometry/v4\"",
            "SETTINGS_GEOMETRY_SCREEN_KEY = \"home_dashboard_overhaul/settings_dialog_geometry/v4_screen\"",
            "SETTINGS_GEOMETRY_AVAILABLE_KEY = \"home_dashboard_overhaul/settings_dialog_geometry/v4_available\"",
            "SETTINGS_GEOMETRY_DPR_KEY = \"home_dashboard_overhaul/settings_dialog_geometry/v4_dpr\"",
            "SETTINGS_PREVIOUS_GEOMETRY_KEY = \"home_dashboard_overhaul/settings_dialog_geometry/v3\"",
            "saved = self._rect_tuple(self._geometry_settings.value(SETTINGS_GEOMETRY_KEY))",
            "source_version = SETTINGS_GEOMETRY_VERSION",
            "source_version = SETTINGS_PREVIOUS_GEOMETRY_VERSION",
            "migrated = migrate_saved_window_geometry(",
            "saved_valid = migrated is not None",
            "geometry = clamp_window_geometry(",
            "self.setGeometry(QRect(*geometry))",
            "if self.isMaximized() or self.isFullScreen():",
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
            "active_dialog = self._active_settings_dialog",
            "self._route_active_settings_dialog(active_dialog, request)",
            "self._active_settings_dialog = dialog",
            "dialog.exec()",
            "if self._active_settings_dialog is dialog:",
            "self._active_settings_dialog = None",
        ):
            self.assertIn(marker, opener)
        for forbidden_opening_marker in (
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
            "setWindowModality",
            "setModal(",
            "setWindowFlags",
            "activateWindow()",
            "raise_()",
            "setFocusProxy(",
            "installEventFilter(self)",
            "AnkiWebView",
            "QWebEngine",
            "Qt.WindowType.Window",
            "Qt.WindowType.CustomizeWindowHint",
        ):
            self.assertNotIn(forbidden_marker, dialog_source)
        for guarded_frame_marker in (
            "def showEvent(self, event: Any) -> None:",
            "if not self._post_show_clamp_done:",
            "QTimer.singleShot(0, self._correct_decorated_frame_if_needed)",
            "def _correct_decorated_frame_if_needed(self) -> None:",
            "if available.contains(frame):",
            "if dx or dy:",
            "self.move(self.pos() + QPoint(dx, dy))",
        ):
            self.assertIn(guarded_frame_marker, dialog_source)
        self.assertEqual(dialog_source.count("self.move("), 1)
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
        self.assertEqual(self.settings_window_contract["minimum_size"], [860, 640])
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
        self.assertEqual(self.settings_window_contract["geometry_version"], 4)
        self.assertEqual(self.settings_window_contract["previous_geometry_version"], 3)
        self.assertEqual(
            self.settings_window_contract["active_dialog_reference"],
            "one temporary controller reference exists only during modal exec for re-entry routing and is cleared in finally",
        )
        self.assertEqual(
            self.settings_window_contract["initial_placement"],
            "migrate and restore a valid logical v3 or v4 QRect on its connected screen or center the preferred size on the active parent screen before first visibility",
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
            'DECORATED_SETTINGS_CAPTURE_METHOD_PREFIXES',
            '_complete_decorated_capture(record)',
        ):
            self.assertIn(marker, self.settings_review_assembler)
        self.assertTrue(self.settings_window_contract["pre_exec_geometry"])
        self.assertEqual(
            self.settings_window_contract["reposition_after_open"],
            "one decoration-only clamp when the decorated frame is outside the active screen; never move an already-contained frame",
        )
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
        self.assertIn("QStackedLayout.StackingMode.StackAll", self.settings)
        self.assertIn('QWidget#SettingsPromptPage {{ background: {overlay}; }}', self.settings)
        self.assertIn("prompt = SettingsPromptPage(\n            self._content_stack,", self.settings)
        self.assertIn("self._content_stack.setCurrentWidget(prompt)", self.settings)
        self.assertIn("self._content_stack.setCurrentWidget(self.settings_shell)", self.settings)
        self.assertIn('"Unsaved changes"', self.settings)
        self.assertIn('"Save your changes before closing?"', self.settings)
        self.assertIn('("Cancel", "secondary", lambda: None)', self.settings)
        self.assertIn('("Discard changes", "danger", self._close_dialog)', self.settings)
        self.assertIn('("Save and close", "primary", self._save_and_close)', self.settings)
        self.assertIn('"Settings changed elsewhere"', self.settings)
        self.assertIn("self._show_prompt(", self.settings)
        self.assertIn(
            'state.get("close_prompt_titles") == ["Unsaved changes"]',
            self.release_probe,
        )
        self.assertIn(
            'state.get("close_prompt_actions") == ["Cancel", "Discard changes", "Save and close"]',
            self.release_probe,
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
            "self._pending_close_after_save = True",
            "close_after_save = self._pending_close_after_save",
            "if close_after_save:",
            "self._pending_close_after_save = False",
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

    def test_fullscreen_probe_enters_in_place_without_space_switching_calls(self) -> None:
        fitter = self.fullscreen_probe.split("def _fit_fullscreen(", 1)[1].split(
            "def _capture_fullscreen", 1
        )[0]
        for marker in (
            "isolated Anki window must already be on the capture display before fullscreen",
            "if not mw.isFullScreen():",
            "mw.showFullScreen()",
        ):
            self.assertIn(marker, fitter)
        for forbidden in (
            "mw.showNormal()",
            "mw.move(",
            "mw.raise_()",
            "mw.activateWindow()",
        ):
            self.assertNotIn(forbidden, fitter)
        settings_preparation = self.fullscreen_probe.split(
            "def _prepare_settings_case(", 1
        )[1].split("def _capture_settings", 1)[0]
        self.assertLess(
            settings_preparation.index("dialog = _release_prepare_settings(case)"),
            settings_preparation.index("dialog.move("),
        )
        self.assertNotIn("dialog.show()", settings_preparation)
        self.assertNotIn("dialog.exec()", settings_preparation)

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
            "compact = self._screen_compact_fallback or shell_width <= SETTINGS_COMPACT_BODY_WIDTH",
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
        self.assertIn("progress = _progress_presentation(snapshot)", self.release_probe_base)
        self.assertIn("expected_progress = progress.label", self.release_probe_base)
        self.assertIn("[data-hdo-progress-label]", self.release_probe_base)
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
            "if settings_failures or structured_layout_failed",
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
            'report.get("schema_version") == 2',
            "validate_fullscreen_workflow(",
            'UNRUN BY USER DIRECTION',
            '"settings-fullscreen-acceptance.json"',
        ):
            self.assertIn(marker, self.settings_review_assembler)
        for marker in (
            "FULLSCREEN_WORKFLOW_STEP_IDS",
            '"all-four-pages"',
            '"events-tabs"',
            '"resize"',
            '"event-edit"',
            '"verse-edit"',
            '"save"',
            '"close-reopen"',
            '"controlled-restart"',
            'raw_step.get("remained_on_current_anki_space") is True',
            "_validate_native_settings_pages(report, key)",
            "physical_value - expected_physical",
            'key[2] == "dpr-1"',
        ):
            self.assertIn(marker, self.evidence_assembler)

    def test_structured_settings_layout_report_is_shared_and_adds_no_pngs(self) -> None:
        for marker in (
            "def validate_structured_settings_layout(",
            "CAPTURE_PLAN.structured_settings_layout()",
            'report.get("generated_png_count") == 0',
            '"structured Settings layout report did not pass"',
            'reports / "settings-structured-layout.json"',
            '"generated_png_count": 0',
        ):
            self.assertIn(marker, self.evidence_assembler)
        for marker in (
            "validate_structured_settings_layout(",
            "allow_failures=True",
            'reports / "settings-structured-layout.json"',
            '"review-failed"\n            if failures or structured_failures',
            '"structured_settings_layout_failure_count"',
            '"release_ready": False',
        ):
            self.assertIn(marker, self.settings_review_assembler)
        self.assertNotIn(
            "settings-structured-layout.png",
            self.evidence_assembler + self.settings_review_assembler,
        )

    def test_settings_review_sheets_resolve_canonical_plan_captions(self) -> None:
        source = self.settings_review_assembler.split("def _make_sheets(", 1)[1].split(
            "def assemble(", 1
        )[0]
        self.assertEqual(source.count('\n            "settings",\n'), 1)
        self.assertEqual(source.count('\n                "settings",\n'), 1)
        self.assertNotIn(
            'CAPTURE_PLAN.detail_groups("settings-100-review")',
            source,
        )

    def test_native_probe_produces_structured_layout_without_capture_calls(self) -> None:
        for marker in (
            "def _start_structured_settings_layout()",
            "def _inspect_structured_settings_case(",
            "def _structured_restoration_assertions(",
            "def _assert_scoped_settings_resets(",
            'if case.get("id") == "settings-font-100-dashboard":',
            "_assert_scoped_settings_resets(dialog)",
            "dialog._reset_card(scope, label)",
            '"Calendar event marker preserved"',
            '"pending manual verse restored"',
            "CAPTURE_PLAN.structured_settings_layout()",
            '"structured_work_area_logical"',
            '"structured_settings_application_font_percent"',
            '"generated_png_count": generated_png_count',
            "base._sha256(path)",
            "application.aboutToQuit.connect(_restore_application_font)",
            "_snapshot_geometry_preferences()",
            "_restore_geometry_snapshot(_structured_settings_geometry_snapshot)",
            'dialog.retention_target.setValue(81)',
            '"page_bottom_reachable"',
            '"clipped_wrapped_labels"',
            "width = max(1, label.width())",
            "required_height > label.height() + 1",
            'config["bible"]["rotation_mode"] = "manual"',
            "not text_elided",
            'or bool(target.get("elision_fallback_available"))',
        ):
            self.assertIn(marker, self.release_probe)

        tree = ast.parse(self.release_probe)
        structured_names = {
            "_start_structured_settings_layout",
            "_next_structured_settings_case",
            "_activate_structured_settings_case",
            "_inspect_structured_settings_case",
            "_finish_structured_settings_layout",
            "_assert_scoped_settings_resets",
        }
        for function in (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in structured_names
        ):
            calls = {
                node.func.id
                for node in ast.walk(function)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            self.assertNotIn("_capture_settings", calls, function.name)

        structured_next = self.release_probe.split(
            "def _next_structured_settings_case()", 1
        )[1].split("def _start_structured_settings_layout()", 1)[0]
        self.assertLess(
            structured_next.index("_close_settings_dialog()"),
            structured_next.index(
                "_restore_geometry_snapshot(_structured_settings_geometry_snapshot)"
            ),
        )

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

    def test_generated_current_contact_sheets_are_retained_with_current_evidence(self) -> None:
        current_directory = (
            "home_dashboard_overhaul/qa/"
            "release-evidence-1.8.7-2026-08-30-4d0a4107-ui-readiness-100/"
            "contact-sheets/"
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
        ):
            self.assertNotIn(forbidden, self.settings)
        for marker in (
            "class HeatmapPalettePreview(QWidget):",
            "class BibleAppearancePreview(QWidget):",
            "class SettingsEditorDialog(QDialog):",
            "self.setWindowModality(Qt.WindowModality.WindowModal)",
        ):
            self.assertIn(marker, self.settings)
        self.assertNotIn("self.setModal(True)", self.settings)

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
            '"ui_bg": "#0B1118"',
            '"ui_sidebar": "#090F15"',
            '"ui_surface": "#151D26"',
            '"ui_surface_raised": "#1B2631"',
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
            "Changes apply after you save.",
        ):
            self.assertIn(copy, self.settings)

    def test_sapphire_only_fields_are_hidden_without_discarding_values(self) -> None:
        source = self.settings.split("def _update_glass_controls", 1)[1].split(
            "def _select_heatmap_preset", 1
        )[0]
        self.assertIn('== "Sapphire Glass"', source)
        self.assertIn("self.opacity_field.setVisible(True)", source)
        self.assertIn("widget.setEnabled(enabled)", source)
        self.assertIn("self.blur_field_label.setVisible(True)", source)
        self.assertIn("self.blur_field.setVisible(True)", source)
        self.assertIn("self.blur_availability.setVisible(not enabled)", source)
        self.assertNotIn("setValue", source)

    def test_verse_rows_are_semantic_and_preview_fixtures_are_absent(self) -> None:
        verse_source = self.settings.split("class VerseLibraryDelegate", 1)[1].split(
            "class VerseLibraryView", 1
        )[0]
        for marker in (
            "semantic = bool(index.data(VERSE_CURRENT_ROLE) or index.data(VERSE_PENDING_ROLE))",
            'tokens["accent_soft"] if selected or semantic else tokens["base"]',
            "QRect(rect.left(), rect.top(), 3, rect.height())",
            "reference_font.setWeight(QFont.Weight.DemiBold)",
            "painter.drawEllipse(indicator)",
            "painter.drawEllipse(indicator.adjusted(4, 4, -4, -4))",
            "_two_line_excerpt(excerpt, excerpt_metrics, excerpt_rect.width())",
            "menu_rect = QRect(rect.right() - 39, rect.center().y() - 16, 32, 32)",
            "for offset in (-6, 0, 6):",
        ):
            self.assertIn(marker, verse_source)
        self.assertNotIn('("✓ " if semantic else "")', verse_source)
        self.assertNotIn("class VerseRowWidget", self.settings)

        self.assertIn("def _refresh_heatmap_preset_options", self.settings)
        self.assertIn("self.heatmap_preset = QComboBox()", self.settings)
        for retired in (
            "def _refresh_heatmap_preset_cards",
            "selected_indicator",
            "swatches.addWidget",
        ):
            self.assertNotIn(retired, self.settings)

    def test_theme_and_heatmap_palette_share_a_responsive_appearance_row(self) -> None:
        appearance_source = self.settings.split("def _create_appearance_card", 1)[1].split(
            "def _build_dashboard_page", 1
        )[0]
        calendar_source = self.settings.split("def _create_calendar_cards", 1)[1].split(
            "def _build_events_page", 1
        )[0]
        self.assertIn("self.heatmap_preset = QComboBox()", appearance_source)
        self.assertNotIn("self.heatmap_preset = QComboBox()", calendar_source)
        self.assertLess(
            appearance_source.index("self.dashboard_theme_field"),
            appearance_source.index("self.heatmap_palette_field"),
        )

        reflow_source = self.settings.split("def _reflow_compact_grids", 1)[1].split(
            "def _reflow_event_toolbar", 1
        )[0]
        for marker in (
            "if large_text or width < 680:",
            "for row, field in enumerate(self.appearance_fields):",
            "self.appearance_grid.addWidget(self.dashboard_theme_field, 0, 0)",
            "self.appearance_grid.addWidget(self.heatmap_palette_field, 0, 1)",
            "self.appearance_grid.addWidget(self.dashboard_mode_field, 1, 0, 1, 2)",
            "self.appearance_grid.addWidget(self.dashboard_scale_field, 2, 0, 1, 2)",
        ):
            self.assertIn(marker, reflow_source)

    def test_theme_and_heatmap_choices_use_targeted_staging(self) -> None:
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
        self.assertNotIn("self.mode.connect_changed(self._refresh_heatmap_preset_options)", appearance_source)

        theme_source = self.settings.split("def _dashboard_theme_changed", 1)[1].split(
            "def _update_glass_controls", 1
        )[0]
        self.assertIn("self._refresh_heatmap_preset_options()", theme_source)
        self.assertIn("self._stage_theme_palette_choices()", theme_source)

        stage_source = self.settings.split("def _stage_theme_palette_choices", 1)[1].split(
            "def _update_glass_controls", 1
        )[0]
        for marker in (
            'self.draft.values["appearance"]["preset"] = theme_name',
            'self.draft.values["heatmap"]["presets_by_theme"] = preferences',
            'self.staged["appearance"]["preset"] = theme_name',
            'self.staged["heatmap"]["presets_by_theme"] = deepcopy(preferences)',
            "self._update_color_swatch()",
            "self._update_dirty_state()",
        ):
            self.assertIn(marker, stage_source)
        for forbidden in (
            "_settings_changed",
            "_sync_draft",
            "_gather",
            "_minimal_excluded_deck_ids",
            "_apply_theme",
            "normalize_config",
        ):
            self.assertNotIn(forbidden, stage_source)

        handlers_source = self.settings.split("def _select_heatmap_preset", 1)[1].split(
            "def _update_color_swatch", 1
        )[0]
        self.assertGreaterEqual(
            handlers_source.count("self._queue_theme_palette_stage()"),
            2,
        )
        self.assertNotIn("self._settings_changed()", handlers_source)

        config_source = self.settings.split("def _apply_config_to_widgets", 1)[1].split(
            "def _walk_deck_items", 1
        )[0]
        self.assertIn("self._refresh_heatmap_preset_options()", config_source)

    def test_theme_palette_popup_signals_defer_layout_feedback_until_the_next_event_loop(self) -> None:
        init_source = self.settings.split("class SettingsDialog(QDialog):", 1)[1].split(
            "@staticmethod\n    def _active_screen", 1
        )[0]
        for marker in (
            "self._theme_palette_stage_timer = QTimer(self)",
            "self._theme_palette_stage_timer.setSingleShot(True)",
            "self._theme_palette_stage_timer.timeout.connect(",
        ):
            self.assertIn(marker, init_source)

        theme_source = self.settings.split("def _dashboard_theme_changed", 1)[1].split(
            "def _queue_theme_palette_stage", 1
        )[0]
        self.assertIn(
            "self._queue_theme_palette_stage(refresh_controls=True)",
            theme_source,
        )
        for forbidden in (
            "self._update_glass_controls()",
            "self._refresh_heatmap_preset_options()",
            "self._stage_theme_palette_choices()",
            "self._update_dirty_state()",
        ):
            self.assertNotIn(forbidden, theme_source)

        handlers_source = self.settings.split("def _select_heatmap_preset", 1)[1].split(
            "def _refresh_heatmap_preset_options", 1
        )[0]
        self.assertGreaterEqual(
            handlers_source.count("self._queue_theme_palette_stage()"),
            2,
        )
        self.assertNotIn("self._stage_theme_palette_choices()", handlers_source)

        flush_source = self.settings.split("def _flush_theme_palette_stage", 1)[1].split(
            "def _stage_theme_palette_choices", 1
        )[0]
        self.assertIn("self._update_glass_controls()", flush_source)
        self.assertIn("self._refresh_heatmap_preset_options()", flush_source)
        self.assertIn("self._stage_theme_palette_choices()", flush_source)

    def test_deferred_theme_palette_staging_accepts_repeated_same_session_changes(self) -> None:
        module = ast.parse(self.settings)
        dialog = next(
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "SettingsDialog"
        )
        method_names = {
            "_dashboard_theme_changed",
            "_queue_theme_palette_stage",
            "_flush_theme_palette_stage",
            "_stage_theme_palette_choices",
            "_heatmap_preset_changed",
        }
        functions = [
            node
            for node in dialog.body
            if isinstance(node, ast.FunctionDef) and node.name in method_names
        ]
        self.assertEqual({function.name for function in functions}, method_names)
        for function in functions:
            function.decorator_list = []
            function.returns = None
            arguments = list(function.args.args) + list(function.args.kwonlyargs)
            if function.args.vararg is not None:
                arguments.append(function.args.vararg)
            for argument in arguments:
                argument.annotation = None

        namespace: dict[str, object] = {
            "DEFAULT_HEATMAP_PRESETS": DEFAULT_HEATMAP_PRESETS,
            "HEATMAP_PRESETS": HEATMAP_PRESETS,
            "_combo_value": lambda combo, default: getattr(combo, "value", default),
            "deepcopy": deepcopy,
        }
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(body=functions, type_ignores=[])
                ),
                str(ROOT / "settings.py"),
                "exec",
            ),
            namespace,
        )

        class FakeTimer:
            def __init__(self) -> None:
                self.starts: list[int] = []

            def start(self, delay: int) -> None:
                self.starts.append(delay)

        class FakeDialog:
            def __init__(self) -> None:
                self._building = False
                self._theme_palette_refresh_pending = False
                self._theme_palette_stage_timer = FakeTimer()
                self.preset = SimpleNamespace(value="Sapphire Glass")
                self.heatmap_preset = SimpleNamespace(value="Sapphire")
                self._heatmap_preset_preferences = deepcopy(
                    self_config["heatmap"]["presets_by_theme"]
                )
                self.draft = SimpleNamespace(values=deepcopy(self_config))
                self.staged = deepcopy(self_config)
                self.glass_updates = 0
                self.option_refreshes = 0
                self.font_color_swatch = object()
                self.swatch_updates = 0
                self.dirty_updates = 0

            def _update_glass_controls(self) -> None:
                self.glass_updates += 1

            def _refresh_heatmap_preset_options(self) -> None:
                self.option_refreshes += 1
                theme_name = self.preset.value
                self.heatmap_preset.value = self._heatmap_preset_preferences.get(
                    theme_name,
                    DEFAULT_HEATMAP_PRESETS[theme_name],
                )

            def _update_dirty_state(self) -> None:
                self.dirty_updates += 1

            def _update_color_swatch(self) -> None:
                self.swatch_updates += 1

        for method_name in method_names:
            setattr(FakeDialog, method_name, namespace[method_name])

        self_config = deepcopy(self.config)
        fake = FakeDialog()

        fake.preset.value = "Graphite"
        fake._dashboard_theme_changed(1)
        self.assertEqual(fake.dirty_updates, 0)
        self.assertEqual(fake.glass_updates, 0)
        fake._flush_theme_palette_stage()
        self.assertEqual(fake.heatmap_preset.value, "Slate")

        fake.preset.value = "Emerald"
        fake._dashboard_theme_changed(2)
        fake._flush_theme_palette_stage()
        self.assertEqual(fake.heatmap_preset.value, "Emerald")

        for palette_name in ("Moss", "Lagoon"):
            before = fake.dirty_updates
            fake.heatmap_preset.value = palette_name
            fake._heatmap_preset_changed(3)
            self.assertEqual(fake.dirty_updates, before)
            fake._flush_theme_palette_stage()
            self.assertEqual(
                fake.draft.values["heatmap"]["presets_by_theme"]["Emerald"],
                palette_name,
            )

        fake.preset.value = "Graphite"
        fake._dashboard_theme_changed(4)
        fake._flush_theme_palette_stage()
        self.assertEqual(fake.heatmap_preset.value, "Slate")
        fake.heatmap_preset.value = "Mint"
        fake._heatmap_preset_changed(5)
        fake._flush_theme_palette_stage()

        fake.preset.value = "Emerald"
        fake._dashboard_theme_changed(6)
        fake._flush_theme_palette_stage()
        self.assertEqual(fake.heatmap_preset.value, "Lagoon")
        self.assertEqual(fake.dirty_updates, 7)
        self.assertEqual(fake.glass_updates, 4)
        self.assertEqual(fake.option_refreshes, 4)
        self.assertEqual(fake.swatch_updates, 7)
        self.assertEqual(fake._theme_palette_stage_timer.starts, [0] * 7)
        self.assertEqual(
            fake.draft.values["heatmap"]["presets_by_theme"]["Graphite"],
            "Mint",
        )
        self.assertEqual(
            fake.draft.values["heatmap"]["presets_by_theme"]["Emerald"],
            "Lagoon",
        )

    def test_targeted_theme_palette_staging_preserves_per_theme_choices(self) -> None:
        module = ast.parse(self.settings)
        dialog = next(
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "SettingsDialog"
        )
        function = next(
            node
            for node in dialog.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_stage_theme_palette_choices"
        )
        function.decorator_list = []
        function.returns = None
        for argument in function.args.args:
            argument.annotation = None

        namespace: dict[str, object] = {
            "DEFAULT_HEATMAP_PRESETS": DEFAULT_HEATMAP_PRESETS,
            "HEATMAP_PRESETS": HEATMAP_PRESETS,
            "_combo_value": lambda combo, default: getattr(combo, "value", default),
            "deepcopy": deepcopy,
        }
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
        stage_choices = namespace["_stage_theme_palette_choices"]

        class FakeDialog:
            def __init__(self) -> None:
                self._building = False
                self.preset = SimpleNamespace(value="Graphite")
                self.heatmap_preset = SimpleNamespace(value="Plum")
                self._heatmap_preset_preferences = deepcopy(
                    self_config["heatmap"]["presets_by_theme"]
                )
                self.draft = SimpleNamespace(values=deepcopy(self_config))
                self.staged = deepcopy(self_config)
                self.dirty_updates = 0

            def _update_dirty_state(self) -> None:
                self.dirty_updates += 1

        self_config = deepcopy(self.config)
        fake = FakeDialog()
        original_events = fake.draft.values["events"]

        graphite_palette = list(HEATMAP_PRESETS["Graphite"])[-1]
        emerald_palette = list(HEATMAP_PRESETS["Emerald"])[-1]
        fake.preset.value = "Graphite"
        fake.heatmap_preset.value = graphite_palette
        stage_choices(fake)
        fake.preset.value = "Emerald"
        fake.heatmap_preset.value = emerald_palette
        stage_choices(fake)
        fake.preset.value = "Graphite"
        fake.heatmap_preset.value = graphite_palette
        stage_choices(fake)

        self.assertEqual(fake.dirty_updates, 3)
        self.assertIs(fake.draft.values["events"], original_events)
        self.assertEqual(fake.draft.values["appearance"]["preset"], "Graphite")
        self.assertEqual(
            fake.draft.values["heatmap"]["presets_by_theme"]["Graphite"],
            graphite_palette,
        )
        self.assertEqual(
            fake.draft.values["heatmap"]["presets_by_theme"]["Emerald"],
            emerald_palette,
        )
        self.assertEqual(
            fake.draft.values["heatmap"]["presets_by_theme"],
            fake.staged["heatmap"]["presets_by_theme"],
        )

    def test_scoped_widget_hydration_repaints_each_reset_without_touching_context(self) -> None:
        module = ast.parse(self.settings)
        dialog = next(
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "SettingsDialog"
        )
        function = next(
            node
            for node in dialog.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_apply_config_to_widgets"
        )
        function.decorator_list = []
        function.returns = None
        for argument in list(function.args.args) + list(function.args.kwonlyargs):
            argument.annotation = None

        class FakeDate:
            def __init__(self, value: str, valid: bool) -> None:
                self.value = value
                self._valid = valid

            def isValid(self) -> bool:
                return self._valid

        class FakeQDate:
            @staticmethod
            def fromString(value: str, _format: str) -> FakeDate:
                return FakeDate(value, bool(value))

            @staticmethod
            def currentDate() -> FakeDate:
                return FakeDate("CURRENT_DATE", True)

        namespace: dict[str, object] = {
            "QDate": FakeQDate,
            "deepcopy": deepcopy,
            "history_range_choice": history_range_choice,
        }
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
        apply_config = namespace["_apply_config_to_widgets"]

        class FakeText:
            def __init__(self, value: str) -> None:
                self.value = value

            def text(self) -> str:
                return self.value

            def setText(self, value: object) -> None:
                self.value = str(value)

        class FakeValue:
            def __init__(self, value: object) -> None:
                self.current = value

            def setValue(self, value: object) -> None:
                self.current = value

        class FakeNumber(FakeValue):
            def __init__(self, value: int, text: str = "invalid") -> None:
                super().__init__(value)
                self.editor = FakeText(text)
                self.valid = False

            def setValue(self, value: object) -> None:
                super().setValue(int(value))
                self.editor.setText(value)
                self.valid = True

            def is_valid(self) -> bool:
                return self.valid

        class FakeCheck:
            def __init__(self, checked: bool) -> None:
                self.checked = checked

            def setChecked(self, checked: object) -> None:
                self.checked = bool(checked)

        class FakeDateEdit:
            def __init__(self) -> None:
                self.current = FakeDate("STALE_DATE", True)

            def setDate(self, value: FakeDate) -> None:
                self.current = value

        class FakeDialog:
            def __init__(self) -> None:
                self._building = False
                self.context = {
                    "page": "bible_verse",
                    "scroll": 317,
                    "event_search": "exam",
                    "deck_filter": "language",
                    "quote_search": "grace",
                    "selection": "keep-selection",
                    "disclosure": True,
                }
                self.preset = FakeValue("Not default")
                self.mode = FakeValue("dark")
                self.opacity = FakeValue(94)
                self.blur = FakeValue(0)
                self.text_scale = FakeValue(150)
                self.home_screen_position = FakeValue("bottom")
                self.visibility = {
                    key: FakeCheck(not bool(default))
                    for key, default in defaults["visibility"].items()
                }
                self.pace_unit = FakeValue("cards_per_minute")
                self.retention_target = FakeNumber(51)
                self.include_rescheduled = FakeCheck(False)
                self.calendar_view = FakeValue("month")
                self._legacy_week_start_value = "6"
                self._week_start_touched = True
                self.week_start = FakeValue("6")
                self.history_range = FakeValue("custom")
                self.forecast_days = FakeNumber(365)
                self.show_forecast = FakeCheck(False)
                self.ignore_before = FakeDateEdit()
                self.exclude_reschedules = FakeCheck(False)
                self.exclude_deleted = FakeCheck(True)
                self.deck_ids = [999]
                self.event_sort = FakeValue("descending")
                self.font_family_name = "Other"
                self.font_size = FakeNumber(9)
                self.font_color_value = "#BADBAD"
                self._font_color_invalid = True
                self.font_color = FakeText("not-a-color")
                self.theme_color = FakeValue("custom")
                self._font_family_touched = True
                self.rotation = FakeValue("manual")
                self.quotes = ["Unrelated verse"]
                self.pending_manual_quote = "Unrelated verse"
                self._pending_manual_quote_index = 0
                self._heatmap_preset_preferences = {"future": "keep"}
                self.event_refreshes = 0
                self.quote_refreshes = 0
                self.swatch_updates = 0

            def _set_combo_data(self, combo: FakeValue, value: object) -> None:
                combo.current = value

            def _update_glass_controls(self) -> None:
                pass

            def _refresh_heatmap_preset_options(self) -> None:
                pass

            def _update_forecast_range_visibility(self) -> None:
                pass

            def _update_history_range_visibility(self) -> None:
                pass

            def _apply_deck_exclusions(self, values: object) -> None:
                self.deck_ids = list(values) if isinstance(values, list) else []

            def _update_deck_exclusion_summary(self) -> None:
                pass

            def _select_saved_font_family(self, value: str) -> None:
                self.font_family_name = value

            def _update_rotation_help(self) -> None:
                pass

            def _update_quote_actions(self) -> None:
                if self.rotation.current != "manual":
                    self.pending_manual_quote = None
                    self._pending_manual_quote_index = None

            def _refresh_event_lists(self) -> None:
                self.event_refreshes += 1

            def _refresh_quote_list(self) -> None:
                self.quote_refreshes += 1

            def _update_color_swatch(self) -> None:
                self.swatch_updates += 1

        FakeDialog._apply_config_to_widgets = apply_config
        defaults = deepcopy(self.config)

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
                fake = FakeDialog()
                context_before = deepcopy(fake.context)
                fake._apply_config_to_widgets(defaults, scope=scope)
                self.assertEqual(fake.context, context_before)
                self.assertEqual(fake.event_refreshes, 0)
                self.assertEqual(fake.quote_refreshes, 0)
                if scope != "bible_rotation":
                    self.assertEqual(
                        fake.pending_manual_quote,
                        "Unrelated verse",
                    )
                if scope == "appearance":
                    self.assertEqual(fake.preset.current, defaults["appearance"]["preset"])
                    self.assertEqual(fake.opacity.current, defaults["appearance"]["opacity"])
                    self.assertFalse(fake.forecast_days.is_valid())
                elif scope == "dashboard_sections":
                    for key in ("heatmap", "remaining", "today", "heatmap_metrics", "bible"):
                        self.assertEqual(
                            fake.visibility[key].checked,
                            defaults["visibility"][key],
                        )
                    self.assertFalse(fake.visibility["events"].checked)
                elif scope == "study_metrics":
                    self.assertEqual(
                        fake.retention_target.current,
                        defaults["study"]["retention_target"],
                    )
                    self.assertTrue(fake.retention_target.is_valid())
                    self.assertFalse(fake.forecast_days.is_valid())
                elif scope == "calendar_display":
                    self.assertEqual(
                        fake.calendar_view.current,
                        defaults["heatmap"]["calendar_view"],
                    )
                    self.assertTrue(fake.visibility["events"].checked)
                    self.assertFalse(fake.retention_target.is_valid())
                elif scope == "calendar_range":
                    self.assertEqual(fake.history_range.current, "all")
                    self.assertTrue(fake.forecast_days.is_valid())
                    self.assertEqual(fake.ignore_before.current.value, "CURRENT_DATE")
                    self.assertFalse(fake.retention_target.is_valid())
                elif scope == "local_data":
                    self.assertEqual(fake.deck_ids, [])
                    self.assertEqual(
                        fake.exclude_reschedules.checked,
                        defaults["heatmap"]["exclude_manual_reschedules"],
                    )
                    self.assertFalse(fake.retention_target.is_valid())
                elif scope == "bible_appearance":
                    self.assertTrue(fake.font_size.is_valid())
                    self.assertFalse(fake._font_color_invalid)
                    self.assertEqual(
                        fake.font_color.text(),
                        defaults["bible"]["font_color"],
                    )
                elif scope == "bible_rotation":
                    self.assertEqual(
                        fake.rotation.current,
                        defaults["bible"]["rotation_mode"],
                    )
                    self.assertIsNone(fake.pending_manual_quote)
                    self.assertFalse(fake.font_size.is_valid())

    def test_reset_undo_and_commit_lifecycle_are_scoped(self) -> None:
        visibility_source = self.settings.split(
            "    def _update_reset_visibility",
            1,
        )[1].split("    def _request_revert_changes", 1)[0]
        self.assertIn("or self._scope_has_visual_error(scope)", visibility_source)
        self.assertIn("not self.retention_target.is_valid()", visibility_source)
        self.assertIn("not self.forecast_days.is_valid()", visibility_source)
        self.assertIn("not self.font_size.is_valid()", visibility_source)
        self.assertIn("self._font_color_invalid", visibility_source)

        reset_source = self.settings.split("    def _reset_card", 1)[1].split(
            "    def _week_start_changed", 1
        )[0]
        for marker in (
            "self.draft.scope_snapshot(scope)",
            '"kind": "reset"',
            '"scope": scope',
            "self._apply_config_to_widgets(self.staged, scope=scope)",
            "self.draft.restore_scope(scope, snapshot)",
            "self._capture_reset_visual_state(scope)",
            "self._restore_reset_visual_state(scope, visual_state)",
            "pending_manual_quote=self.pending_manual_quote",
        ):
            self.assertIn(marker, reset_source)
        self.assertNotIn("self.draft.replace_values(self._reset_undo_values)", reset_source)

        revert_source = self.settings.split("    def _revert_changes", 1)[1].split(
            "    def _reset_current_section", 1
        )[0]
        reload_source = self.settings.split("    def _reload_after_conflict", 1)[1].split(
            "    def _cancel_conflict", 1
        )[0]
        commit_source = self.settings.split("    def _commit_save", 1)[1].split(
            "    def _has_unsaved_changes", 1
        )[0]
        self.assertIn("self._clear_undo_state()", revert_source)
        self.assertIn("self._clear_event_feedback()", revert_source)
        self.assertIn("retain_quote_export_feedback", revert_source)
        self.assertIn("self.quote_current_feedback.setText(quote_feedback)", revert_source)
        self.assertIn("self._clear_undo_state()", reload_source)
        self.assertIn("self._clear_undo_state()", commit_source)
        failure_source = commit_source.split("except Exception as exc:", 1)[1].split(
            "self.pending_manual_quote = None", 1
        )[0]
        self.assertNotIn("self._clear_undo_state()", failure_source)

        for source in (reload_source, commit_source):
            self.assertIn(
                "self._saved_current_quote = self._read_current_quote(self.staged)",
                source,
            )
        read_source = self.settings.split("    def _read_current_quote", 1)[1].split(
            "    def _week_start_changed", 1
        )[0]
        self.assertIn('"current_quote"', read_source)

    def test_event_status_and_feedback_follow_net_staged_values(self) -> None:
        module = ast.parse(self.settings)
        dialog = next(
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "SettingsDialog"
        )
        names = {
            "_baseline_event",
            "_event_stage_status",
            "_event_items_differ_from_baseline",
            "_reconcile_event_feedback",
            "_set_event_feedback",
            "_clear_event_feedback",
        }
        functions = [
            node
            for node in dialog.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        self.assertEqual({function.name for function in functions}, names)
        for function in functions:
            function.decorator_list = []
            function.returns = None
            arguments = list(function.args.args) + list(function.args.kwonlyargs)
            for argument in arguments:
                argument.annotation = None
        namespace: dict[str, object] = {"Mapping": dict}
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(body=functions, type_ignores=[])
                ),
                str(ROOT / "settings.py"),
                "exec",
            ),
            namespace,
        )

        class FakeLabel:
            def __init__(self) -> None:
                self.value = ""
                self.accessible_name = ""
                self.accessible_description = ""

            def text(self) -> str:
                return self.value

            def setText(self, value: str) -> None:
                self.value = value

            def clear(self) -> None:
                self.value = ""

            def setAccessibleName(self, value: str) -> None:
                self.accessible_name = value

            def setAccessibleDescription(self, value: str) -> None:
                self.accessible_description = value

        class FakeDialog:
            def __init__(self) -> None:
                baseline_event = {
                    "id": "one",
                    "name": "Exam",
                    "date": "2026-08-27",
                    "archived": False,
                    "archived_at": "",
                }
                self.draft = SimpleNamespace(
                    baseline={"events": {"items": [deepcopy(baseline_event)]}}
                )
                self.staged = {"events": {"items": [deepcopy(baseline_event)]}}
                self.event_action_feedback = FakeLabel()

        for name in names:
            setattr(FakeDialog, name, namespace[name])
        fake = FakeDialog()
        event = fake.staged["events"]["items"][0]

        self.assertEqual(fake._event_stage_status(event), "")
        event["name"] = "Exam review"
        self.assertEqual(fake._event_stage_status(event), "Edited")
        fake._set_event_feedback("Updated. Save to keep this change.")
        self.assertIn("Save to keep", fake.event_action_feedback.text())
        event["name"] = "Exam"
        self.assertEqual(fake._event_stage_status(event), "")
        fake._set_event_feedback(
            "Updated. Save to keep this change.",
            change_active=False,
        )
        self.assertEqual(fake.event_action_feedback.text(), "")

        event["archived"] = True
        self.assertEqual(fake._event_stage_status(event), "Archived")
        event["archived"] = False
        self.assertEqual(fake._event_stage_status(event), "")
        fake.event_action_feedback.setText("Restored. Save to keep this change.")
        fake._reconcile_event_feedback()
        self.assertEqual(fake.event_action_feedback.text(), "")

        restored = deepcopy(fake.draft.baseline["events"]["items"][0])
        restored["archived"] = True
        fake.draft.baseline["events"]["items"][0] = restored
        self.assertEqual(fake._event_stage_status(event), "Restored")
        self.assertEqual(
            fake._event_stage_status(
                {
                    "id": "new",
                    "name": "New event",
                    "date": "2026-08-28",
                    "archived": False,
                }
            ),
            "New",
        )

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

    def test_event_manager_uses_two_line_rows_and_a_bounded_six_row_list(self) -> None:
        for marker in (
            "class EventRowWidget(QWidget)",
            'self.title.setObjectName("EventRowTitle")',
            'self.metadata.setObjectName("EventRowMeta")',
            'self.overflow.setIcon(_settings_vector_icon("ellipsis"))',
            'self.overflow.setFixedSize(32, 32)',
            'button.setToolTip("Event actions")',
            'self.event_tabs.addTab(self.active_events, "Active (0)")',
            'self.event_tabs.addTab(self.archived_events, "Archived (0)")',
            'self.event_toolbar_add = QPushButton("Add event")',
            "self.event_toolbar_add.setVisible(has_events)",
            '_stacked_field("Sort by", "", self.event_sort)',
            "self.event_search_clear = self.event_search.addAction(",
            'self.event_empty_add = QPushButton("Add event")',
            'self.event_empty_icon.setPixmap(_settings_vector_icon("calendar", 32).pixmap(32, 32))',
            'self.event_empty_clear = QPushButton("Clear search")',
            "self.event_empty_state.setMinimumHeight(180)",
            "self.event_empty_state.setMaximumHeight(200)",
            "self.event_empty_add.show()",
            "tree.setMinimumHeight(54 + 8)",
            "tree.setMaximumHeight((5 * 54) + 8)",
            "visible_rows = min(5, max(1, tree.topLevelItemCount()))",
            "target = (visible_rows * _event_row_target_height(tree, row_widget)) + 8",
            '("Name", "name")',
            'if sort_value == "name"',
            'str(item.get("name", "")).casefold()',
            "tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)",
            "self._edit_event()",
            "tree.clearSelection()",
            '"{} matching event{}".format',
            '"No events match “{}”.".format(query)',
            '"Delete permanently" if archived else "Delete"',
            'edit_action = None if archived else menu.addAction("Edit")',
            'button.setText("Restore")',
            'self.title.setWordWrap(True)',
        ):
            self.assertIn(marker, self.settings)
        event_source = self.settings.split("    def _build_events_page", 1)[1].split(
            "    def _build_bible_page", 1
        )[0]
        self.assertNotIn("setMaximumHeight(16777215)", event_source)
        self.assertNotIn('self.event_search_clear = QPushButton("Clear")', event_source)
        self.assertNotIn('QWidget#HomeDashboardSettings QWidget#EventRow[selected="true"]', self.settings)

    def test_page_header_keeps_actions_beside_title_and_help(self) -> None:
        page_source = self.settings.split("def _page(", 1)[1].split(
            "def _section_title", 1
        )[0]
        for marker in (
            "header_outer = QHBoxLayout(header)",
            "header_copy = QVBoxLayout()",
            "header_copy.addWidget(heading)",
            "header_copy.addWidget(help_label)",
            'header_actions_host.setObjectName("SettingsPageHeaderActions")',
            "Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter",
            "page._hdo_header_actions = header_actions",
        ):
            self.assertIn(marker, page_source)
        self.assertNotIn("header_outer.addWidget(help_label)", page_source)

    def test_bible_library_uses_reference_excerpt_and_a_bounded_complete_model(self) -> None:
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
            '"{} of {} verses".format(total, len(self.quotes))',
            "target = max(180, min(520, viewport_height - 300))",
            "self.quote_list.setMinimumHeight(target)",
            "self.quote_list.setMaximumHeight(target)",
            'SettingsCard(\n            "Rotation"',
            'SettingsCard(\n            "Verse library"',
            'self.quote_search_clear = _icon_button("clear", "Clear verse search")',
            "self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)",
            'save_button.setText("Add verse" if title.startswith("Add") else "Update verse")',
            "serialize_quote_reference(",
        ):
            self.assertIn(marker, self.settings)
        fit_source = self.settings.split("    def _fit_quote_list", 1)[1].split(
            "    def _open_quote_menu_for_model", 1
        )[0]
        self.assertNotIn("16777215", fit_source)
        for retired in (
            "VerseCardPreview",
            "class VerseRowWidget",
            "_quote_render_limit",
            "Load more",
            "Showing 100",
            "matches[:100]",
        ):
            self.assertNotIn(retired, self.settings)

    def test_about_is_bounded_and_export_feedback_never_dirties_the_draft(self) -> None:
        attribution = (
            "Scripture quotations are taken from the Holy Bible, New Living Translation, "
            "copyright ©1996, 2004, 2015 by Tyndale House Foundation. Used by permission "
            "of Tyndale House Publishers. All rights reserved."
        )
        for marker in (
            'SettingsCard("Version and support")',
            "page.setMaximumWidth(SETTINGS_ABOUT_MAX_WIDTH)",
            'definition_list.setObjectName("AboutDefinitionList")',
            'version_form.addRow("Version", QLabel(version))',
            'version_form.addRow("Compatibility", QLabel(compatibility))',
            "QSizePolicy.Policy.Maximum",
            'self.copy_diagnostics.setText("Copied")',
            'ExternalLinkButton("Documentation", PROJECT_URL)',
            'ExternalLinkButton("Report an issue", ISSUES_URL)',
            'SettingsCard("Privacy and legal")',
            'privacy_callout.setObjectName("InfoBanner")',
            "def add_about_disclosure(title: str, copy: str) -> None:",
            'SettingsCard("Backup and recovery")',
            '"Dashboard data stays on this device and is not sent to external services."',
            'recovery_export = QPushButton("Export verse library edits")',
            "self.recovery_export = recovery_export",
            'recovery_export.clicked.connect(self._export_quotes)',
            '"Verse library edits exported to {}.".format(path)',
            '"Could not export verse library edits. Your settings changes were not affected."',
            'self.export_copy_error = QPushButton("Copy error")',
            attribution,
        ):
            self.assertIn(marker, self.settings)
        recovery_source = self.settings.split('SettingsCard("Backup and recovery")', 1)[1].split(
            "layout.addStretch()", 1
        )[0]
        for forbidden in ("restore", "reset", "import"):
            self.assertNotIn(forbidden, recovery_source.casefold())
        export_source = self.settings.split("    def _export_quotes", 1)[1].split(
            "    def _copy_export_error", 1
        )[0]
        self.assertNotIn("_settings_changed", export_source)
        self.assertNotIn("_sync_draft", export_source)

    def test_footer_has_action_local_dirty_success_and_error_states(self) -> None:
        footer_index = self.settings.index("outer.addWidget(self.footer_shell, 3, 1)")
        body_index = self.settings.index("outer.addWidget(self.body_shell, 1, 1)")
        self.assertLess(body_index, footer_index)
        for marker in (
            'self.revert_button = QPushButton("Discard changes")',
            'self.close_button.setText("Close")',
            'self.save_button.setText("Save changes")',
            'self.error_label.setObjectName("InlineSaveError")',
            'self.details_button = QPushButton("View details")',
            'self.copy_error_button = QPushButton("Copy error")',
            'self.copy_error_button.setIcon(_settings_vector_icon("copy"))',
            "def _request_revert_changes(self)",
            "if not self._has_staged_destructive_deletions():",
            "def _revert_changes(self)",
            "baseline = deepcopy(self.draft.baseline)",
            'self._set_status("discarded", "Changes discarded")',
            'self._set_status("saving", "Saving changes…")',
            'self.save_button.setText("Save changes")',
            "self._set_mutation_controls_enabled(False)",
            "self.saved_status_timer.timeout.connect(self._clear_saved_status)",
            "self.saved_status_timer.setInterval(5000)",
            'self._set_status("saved", "Saved")',
            "self.save_button.setEnabled(False)",
            '"Could not save changes. Your draft is still available."',
            "self._last_save_error_detail = detail",
            "self.draft.baseline = deepcopy(dict(failure_baseline))",
            "self.draft.values = deepcopy(dict(failure_values))",
            'self.quotes = list(self.staged["bible"]["quotes"])',
            '"{} unsaved change{}".format',
            "class SettingsStatusIndicator(QWidget):",
            'if self._state == "saving":',
            "self.draft.replace_all(latest_saved)",
            "self._pending_close_after_save = False",
            "outer.addWidget(self.footer.error_panel, 2, 1)",
            "self.footer.setFixedHeight(SETTINGS_FOOTER_MIN_HEIGHT)",
            '"validation-error",',
            '"Fix {} error{} to save".format(',
            '"Enter a valid #RRGGBB color."',
            "self.error_panel.isHidden()",
        ):
            self.assertIn(marker, self.settings)
        self.assertNotIn(
            "bool(text) and not self.footer.error_panel.isVisible()",
            self.settings,
        )
        self.assertNotIn("simulated transactional write failure", self.settings)
        save_source = self.settings.split("    def _save(self) -> None:", 1)[1].split(
            "    def _has_unsaved_changes", 1
        )[0]
        self.assertNotIn('self.save_button.setText("Saving…")', save_source)
        self.assertNotIn('self._set_status("saved", "✓ Saved")', save_source)

    def test_save_lock_restores_nested_theme_and_palette_popup_controls(self) -> None:
        module = ast.parse(self.settings)
        dialog = next(
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "SettingsDialog"
        )
        function = next(
            node
            for node in dialog.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_set_mutation_controls_enabled"
        )
        function.decorator_list = []
        function.returns = None
        for argument in function.args.args:
            argument.annotation = None

        class FakeWidget:
            def __init__(
                self,
                parent: "FakeWidget | None" = None,
                enabled: bool = True,
            ) -> None:
                self.parent = parent
                self.explicitly_enabled = enabled
                self.children: list[FakeWidget] = []
                if parent is not None:
                    parent.children.append(self)

            def isEnabled(self) -> bool:
                return self.explicitly_enabled and (
                    self.parent is None or self.parent.isEnabled()
                )

            def setEnabled(self, enabled: bool) -> None:
                self.explicitly_enabled = enabled

            def findChildren(self, _kind: object) -> list["FakeWidget"]:
                found: list[FakeWidget] = []
                pending = list(self.children)
                while pending:
                    child = pending.pop(0)
                    found.append(child)
                    pending[0:0] = child.children
                return found

        class QWidget(FakeWidget):
            pass

        class QPushButton(QWidget):
            pass

        class QLineEdit(QWidget):
            pass

        class QComboBox(QWidget):
            pass

        class QDateEdit(QWidget):
            pass

        class QSlider(QWidget):
            pass

        class QCheckBox(QWidget):
            pass

        class QPlainTextEdit(QWidget):
            pass

        class QListView(QWidget):
            pass

        class QTreeWidget(QWidget):
            pass

        namespace: dict[str, object] = {
            "QWidget": QWidget,
            "QPushButton": QPushButton,
            "QLineEdit": QLineEdit,
            "QComboBox": QComboBox,
            "QDateEdit": QDateEdit,
            "QSlider": QSlider,
            "QCheckBox": QCheckBox,
            "QPlainTextEdit": QPlainTextEdit,
            "QListView": QListView,
            "QTreeWidget": QTreeWidget,
            "List": list,
        }
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
        set_mutation_controls_enabled = namespace[
            "_set_mutation_controls_enabled"
        ]

        class FakeDialog:
            def __init__(self) -> None:
                self.settings_shell = QWidget()
                self.preset = QComboBox(self.settings_shell)
                self.theme_popup = QListView(self.preset)
                self.heatmap_preset = QComboBox(self.settings_shell)
                self.palette_popup = QListView(self.heatmap_preset)
                self.disabled_dependency = QLineEdit(
                    self.settings_shell,
                    enabled=False,
                )
                self.nav = QWidget(self.settings_shell)
                self.active_events = QTreeWidget(self.settings_shell)
                self.archived_events = QTreeWidget(self.settings_shell)
                self.quote_list = QListView(self.settings_shell)
                self._mutation_enabled_states: dict[FakeWidget, bool] = {}

        fake = FakeDialog()
        for _cycle in range(2):
            set_mutation_controls_enabled(fake, False)
            self.assertFalse(fake.preset.isEnabled())
            self.assertFalse(fake.theme_popup.isEnabled())
            self.assertFalse(fake.heatmap_preset.isEnabled())
            self.assertFalse(fake.palette_popup.isEnabled())

            set_mutation_controls_enabled(fake, True)
            self.assertTrue(fake.preset.isEnabled())
            self.assertTrue(fake.theme_popup.isEnabled())
            self.assertTrue(fake.heatmap_preset.isEnabled())
            self.assertTrue(fake.palette_popup.isEnabled())
            self.assertFalse(fake.disabled_dependency.isEnabled())

    def test_controls_grow_with_application_font_without_an_alternate_layout(self) -> None:
        for marker in (
            "target = max(INTERACTION_TARGET_MIN_PX, widget.fontMetrics().lineSpacing() + 10)",
            "return max(INTERACTION_TARGET_MIN_PX, view.fontMetrics().lineSpacing() + 12)",
            "max(56, (2 * view.fontMetrics().lineSpacing()) + 20)",
            "self.setFixedSize(44, 34)",
            "class SuffixNumberField(QWidget):",
            "QIntValidator(self._minimum, self._maximum, self.editor)",
            'self.editor.setProperty("invalid", invalid)',
            "self.editor.editingFinished.connect(self._commit)",
            "spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)",
            "spin.setReadOnly(True)",
            "self.setMaximumWidth(380)",
            'button.setProperty("last", option_index == len(options) - 1)',
            "combo.setMaximumWidth(420)",
            "spin.setMaximumWidth(120)",
            "QFormLayout.RowWrapPolicy.WrapLongRows",
            "def _apply_role_fonts(root: QWidget) -> None:",
            '"PageTitle": role_font(20, QFont.Weight.DemiBold)',
            '"CardTitle": role_font(13, QFont.Weight.DemiBold)',
            '"PageHelp": role_font(12)',
            '"FieldHelp": role_font(11)',
            "large_text = self.fontMetrics().lineSpacing() >= 22",
        ):
            self.assertIn(marker, self.settings)
        self.assertNotIn("font-family:", self.settings)

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
