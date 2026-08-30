from __future__ import annotations

import ast
from copy import deepcopy
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import runpy
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.tests import test_controller_insights as controller_support
from home_dashboard_overhaul.tests.fixtures import sample_snapshot


ROOT = Path(__file__).resolve().parents[1]


class ControllerReleaseMatrixRegressionTests(unittest.TestCase):
    """Lifecycle and recovery cases that do not require a real Anki window."""

    @classmethod
    def setUpClass(cls) -> None:
        controller_support.ControllerCapabilityTests.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        controller_support.ControllerCapabilityTests.tearDownClass()

    def setUp(self) -> None:
        self.harness = controller_support.ControllerCapabilityTests(methodName="runTest")
        self.harness.setUp()
        self.aqt = self.harness.aqt
        self.module = self.harness.module
        self.controller = self.harness.controller
        self.aqt.mw.col.mod = 1
        self.aqt.mw.col.sched.today = 500
        self.aqt.mw.col.sched.day_cutoff = int(
            (datetime.now().astimezone() + timedelta(days=1)).timestamp()
        )
        self._clear_hooks()

    def tearDown(self) -> None:
        self._clear_hooks()
        self.harness.tearDown()

    def _clear_hooks(self) -> None:
        for name in (
            "browser_will_search",
            "deck_browser_will_render_content",
            "webview_will_set_content",
            "webview_did_receive_js_message",
            "profile_did_open",
            "profile_will_close",
            "reviewer_did_answer_card",
            "operation_did_execute",
            "state_did_change",
        ):
            getattr(self.aqt.gui_hooks, name).clear()

    def test_hook_installation_is_idempotent(self) -> None:
        self.controller._install_hooks()
        self.controller._install_hooks()

        expected = {
            "deck_browser_will_render_content": self.controller.on_deck_browser_render,
            "webview_will_set_content": self.controller.on_web_content,
            "webview_did_receive_js_message": self.controller.on_bridge_message,
            "profile_did_open": self.controller.on_profile_open,
            "profile_will_close": self.controller.on_profile_close,
            "reviewer_did_answer_card": self.controller.on_reviewer_answer,
            "operation_did_execute": self.controller.on_operation_did_execute,
            "state_did_change": self.controller.on_state_change,
        }
        for name, callback in expected.items():
            with self.subTest(hook=name):
                self.assertEqual(getattr(self.aqt.gui_hooks, name).count(callback), 1)

    def test_refresh_bursts_coalesce_and_repeated_cycles_leave_no_pending_state(self) -> None:
        initial_generation = self.controller.data_generation
        for index in range(25):
            self.controller._schedule_refresh("burst-{}".format(index))

        self.assertEqual(len(controller_support.FakeQTimer.pending), 1)
        self.assertEqual(len(self.controller._refresh_reasons), 25)
        controller_support.FakeQTimer.run_next()
        self.assertEqual(self.controller.data_generation, initial_generation + 1)
        self.assertEqual(self.aqt.mw.deckBrowser.refresh_count, 1)
        self.assertFalse(self.controller._refresh_pending)
        self.assertEqual(self.controller._refresh_reasons, set())

        for index in range(10):
            self.controller._schedule_refresh("cycle-{}-a".format(index))
            self.controller._schedule_refresh("cycle-{}-b".format(index))
            self.assertEqual(len(controller_support.FakeQTimer.pending), 1)
            controller_support.FakeQTimer.run_next()
            self.assertEqual(controller_support.FakeQTimer.pending, [])
            self.assertFalse(self.controller._refresh_pending)
        self.assertEqual(self.aqt.mw.deckBrowser.refresh_count, 11)

    def test_newer_snapshot_wins_when_queries_complete_out_of_order(self) -> None:
        older = sample_snapshot(date(2026, 8, 17))
        newer = deepcopy(older)
        old_key = self.controller._key()
        self.controller._request_snapshot(old_key)

        self.aqt.mw.col.mod = 2
        new_key = self.controller._key()
        self.controller._request_snapshot(new_key)
        self.assertEqual(len(controller_support.FakeQueryOp.pending), 2)

        controller_support.FakeQueryOp.pending[1].success(newer)
        self.assertIs(self.controller.snapshot, newer)
        self.assertEqual(self.controller.cache_key, new_key)
        revision = self.controller.facts_revision

        controller_support.FakeQueryOp.pending[0].success(older)
        self.assertIs(self.controller.snapshot, newer)
        self.assertEqual(self.controller.cache_key, new_key)
        self.assertEqual(self.controller.facts_revision, revision)
        self.assertFalse(self.controller.initial_failure)
        self.assertFalse(self.controller.refresh_error)

    def test_stale_query_failure_never_replaces_new_data_or_leaks_error_text(self) -> None:
        newer = sample_snapshot(date(2026, 8, 17))
        old_key = self.controller._key()
        self.controller._request_snapshot(old_key)
        self.aqt.mw.col.mod = 2
        new_key = self.controller._key()
        self.controller._request_snapshot(new_key)

        controller_support.FakeQueryOp.pending[1].success(newer)
        controller_support.FakeQueryOp.pending[0].fail(
            RuntimeError("secret collection path /Users/private/collection.anki2")
        )

        self.assertIs(self.controller.snapshot, newer)
        self.assertEqual(self.controller.cache_key, new_key)
        self.assertFalse(self.controller.initial_failure)
        self.assertFalse(self.controller.refresh_error)
        self.assertNotIn(
            "secret collection path",
            "\n".join(self.aqt.mw.deckBrowser.web.scripts),
        )

    def test_profile_close_cancels_pending_refresh_query_and_rollover_callbacks(self) -> None:
        reset_calls = []
        self.aqt.mw.col.sched.reset = lambda: reset_calls.append("reset")
        key = self.controller._key()
        self.controller._request_snapshot(key)
        query = controller_support.FakeQueryOp.pending[0]
        self.controller._schedule_refresh("pending-close")
        self.controller._schedule_rollover()
        self.assertGreaterEqual(len(controller_support.FakeQTimer.pending), 2)

        self.controller.on_profile_close()
        while controller_support.FakeQTimer.pending:
            controller_support.FakeQTimer.run_next()
        query.success(sample_snapshot(date(2026, 8, 17)))

        self.assertIsNone(self.controller.snapshot)
        self.assertIsNone(self.controller.cache_key)
        self.assertIsNone(self.controller.inflight_key)
        self.assertFalse(self.controller._refresh_pending)
        self.assertEqual(self.controller._refresh_reasons, set())
        self.assertEqual(reset_calls, [])
        self.assertEqual(self.aqt.mw.deckBrowser.refresh_count, 0)

    def test_bridge_rejects_oversized_malformed_unknown_and_unbounded_values(self) -> None:
        context = controller_support.FakeDeckBrowser()
        original = (False, "unhandled")
        self.assertEqual(
            self.controller.on_bridge_message(original, "other:{}", context),
            original,
        )
        for message in (
            "hdo:{",
            "hdo:[]",
            "hdo:" + json.dumps({"command": "unknown", "payload": {}}),
            "hdo:" + json.dumps({
                "command": "settings",
                "payload": {"page": "events", "event_id": "x" * 2_100},
            }),
        ):
            with self.subTest(message=message[:40]):
                self.assertEqual(
                    self.controller.on_bridge_message(original, message, context),
                    (True, None),
                )
        self.assertEqual(controller_support.FakeQTimer.pending, [])
        self.assertIsNone(self.controller._pending_settings_request)

        for left in (-1, 100_001, float("inf"), float("nan"), True, "10"):
            message = "hdo:" + json.dumps({
                "command": "calendar_year_scroll",
                "payload": {"left": left},
            })
            self.controller.on_bridge_message(original, message, context)
            self.assertIsNone(self.controller.year_scroll_left)

    def test_initial_failure_renders_only_generic_recovery_copy(self) -> None:
        key = self.controller._key()
        self.controller._request_snapshot(key)
        controller_support.FakeQueryOp.pending[0].fail(
            RuntimeError("database failed at /Users/private/collection.anki2")
        )
        content = type("Content", (), {"stats": ""})()
        self.controller.on_deck_browser_render(context := controller_support.FakeDeckBrowser(), content)

        self.assertIn("The dashboard data could not be loaded", content.stats)
        self.assertNotIn("/Users/private", content.stats)
        self.assertNotIn("database failed", content.stats)
        self.assertEqual(context.web.scripts, [])

    def test_repeated_modal_cycles_release_the_active_dialog_and_add_no_timers(self) -> None:
        settings = ModuleType("home_dashboard_overhaul.settings")
        settings.SettingsDialog = controller_support.FakeSettingsDialog

        with patch.dict(sys.modules, {"home_dashboard_overhaul.settings": settings}):
            for _index in range(40):
                self.controller.open_settings("dashboard")
                self.assertIsNone(self.controller._active_settings_dialog)

        self.assertEqual(len(controller_support.FakeSettingsDialog.instances), 40)
        self.assertTrue(all(dialog.exec_count == 1 for dialog in controller_support.FakeSettingsDialog.instances))
        self.assertEqual(controller_support.FakeQTimer.pending, [])


class PersistenceAndPrivacyReleaseMatrixTests(unittest.TestCase):
    def test_every_prior_schema_normalizes_to_eight_without_losing_unknown_values(self) -> None:
        for schema_version in range(1, 8):
            with self.subTest(schema=schema_version):
                raw = {
                    "schema_version": schema_version,
                    "appearance": {"density": "compact", "future": {"value": schema_version}},
                    "study": {"show_eta": False, "show_estimate": False, "future": "kept"},
                    "visibility": {"buried": False, "introduced": False},
                    "introduced": {"include_rescheduled": False, "week_start": 3},
                    "heatmap": {"calendar_mode": "nine_months", "future": "kept"},
                    "migration": {"completed": True},
                    "future_root": {"schema": schema_version},
                }
                normalized = normalize_config(raw)
                self.assertEqual(normalized["schema_version"], 8)
                self.assertEqual(normalized["appearance"]["future"], {"value": schema_version})
                self.assertEqual(normalized["study"]["future"], "kept")
                self.assertEqual(normalized["heatmap"]["future"], "kept")
                self.assertEqual(normalized["future_root"], {"schema": schema_version})
                self.assertFalse(normalized["new_cards"]["include_rescheduled"])
                self.assertEqual(normalized["heatmap"]["week_start"], 3)
                self.assertNotIn("density", normalized["appearance"])
                self.assertNotIn("show_eta", normalized["study"])
                self.assertNotIn("show_estimate", normalized["study"])
                self.assertNotIn("buried", normalized["visibility"])
                self.assertNotIn("introduced", normalized["visibility"])
                self.assertNotIn("introduced", normalized)
                self.assertNotIn("calendar_mode", normalized["heatmap"])
                self.assertEqual(normalize_config(normalized), normalized)

    def test_package_excludes_deferred_calendar_and_automatic_network_clients(self) -> None:
        builder = runpy.run_path(str(ROOT / "tools" / "build_ankiaddon.py"))
        members = tuple(builder["PACKAGE_FILES"])
        deferred = set(builder["DEFERRED_SOURCE_FILES"])
        self.assertEqual(len(members), 24)
        self.assertTrue(deferred.isdisjoint(members))
        self.assertFalse(any(name.startswith("_vendor/") for name in members))

        forbidden_import_roots = {"aiohttp", "http", "requests", "socket", "urllib"}
        for relative in members:
            if not relative.endswith(".py"):
                continue
            source = (ROOT / relative).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=relative)
            imported_roots = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_roots.add(node.module.split(".", 1)[0])
            with self.subTest(member=relative):
                self.assertTrue(forbidden_import_roots.isdisjoint(imported_roots))
                self.assertNotIn("calendar_repository", source)
                self.assertNotIn("calendar_manager_model", source)


if __name__ == "__main__":
    unittest.main()
