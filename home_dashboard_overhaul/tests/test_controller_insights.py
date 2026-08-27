from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from home_dashboard_overhaul.models import (
    BrowseTarget,
    BrowseTargetKind,
    DayInsight,
)
from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.tests.fixtures import sample_snapshot


class HookList(list):
    pass


class FakeAddonManager:
    def __init__(self) -> None:
        self.writes = []
        self.config = {}

    def addonFromModule(self, _name):
        return "home_dashboard_overhaul"

    def getConfig(self, _package):
        return deepcopy(self.config)

    def writeConfig(self, package, config):
        self.writes.append((package, deepcopy(config)))
        self.config = deepcopy(config)


class FakeSwitch:
    def __init__(self, table) -> None:
        self.table = table

    def setChecked(self, checked):
        if checked is False:
            self.table.notes_mode = False


class FakeTable:
    def __init__(self, notes_mode=False) -> None:
        self.notes_mode = notes_mode

    def is_notes_mode(self):
        return self.notes_mode


class FakeBrowser:
    def __init__(self, hooks, notes_mode=False) -> None:
        self.hooks = hooks
        self.searches = []
        self.contexts = []
        self.table = FakeTable(notes_mode)
        self._switch = FakeSwitch(self.table)

    def search_for(self, query):
        context = SimpleNamespace(
            browser=self,
            search=query,
            ids=None,
            order=True,
            reverse=True,
        )
        for hook in list(self.hooks.browser_will_search):
            hook(context)
        self.searches.append(query)
        self.contexts.append(context)


class FakeDialogs:
    def __init__(self, hooks) -> None:
        self.hooks = hooks
        self.opened = []
        self.next_notes_mode = False

    def open(self, name, _parent):
        browser = FakeBrowser(self.hooks, self.next_notes_mode)
        self.opened.append((name, browser))
        self.next_notes_mode = False
        return browser


class FakeWeb:
    def __init__(self) -> None:
        self.scripts = []

    def eval(self, script):
        self.scripts.append(script)


class FakeDeckBrowser:
    def __init__(self) -> None:
        self.web = FakeWeb()
        self.refresh_count = 0

    def refresh(self):
        self.refresh_count += 1


class FakeQueryOp:
    pending = []

    def __init__(self, parent, op, success) -> None:
        self.parent = parent
        self.op = op
        self.success = success
        self.failure_callback = None
        self.__class__.pending.append(self)

    def failure(self, callback):
        self.failure_callback = callback
        return self

    def run_in_background(self):
        return None

    def complete(self):
        self.success(self.op(self.parent.col))

    def fail(self, error=None):
        if self.failure_callback:
            self.failure_callback(error or RuntimeError("failure"))


class FakeQTimer:
    pending = []

    @classmethod
    def singleShot(cls, delay, callback) -> None:
        cls.pending.append((delay, callback))

    @classmethod
    def run_next(cls) -> None:
        index = min(range(len(cls.pending)), key=lambda item: (cls.pending[item][0], item))
        _delay, callback = cls.pending.pop(index)
        callback()


class FakeCentralLayout:
    def __init__(self, web) -> None:
        self.web = web

    def indexOf(self, widget) -> int:
        return 0 if widget is self.web else -1

    def insertWidget(self, *_args) -> None:
        return None


class FakeCentralWidget:
    def __init__(self, web) -> None:
        self._layout = FakeCentralLayout(web)

    def layout(self):
        return self._layout


class FakeRect:
    def __init__(self, x, y, width, height) -> None:
        self.x = x
        self.y = y
        self._width = width
        self._height = height

    def isValid(self):
        return self._width > 0 and self._height > 0

    def width(self):
        return self._width

    def height(self):
        return self._height

    def left(self):
        return self.x

    def top(self):
        return self.y

    def right(self):
        return self.x + self._width - 1

    def bottom(self):
        return self.y + self._height - 1


class FakeSize:
    def __init__(self, width, height) -> None:
        self._width = width
        self._height = height

    def width(self):
        return self._width

    def height(self):
        return self._height


class FakeScreen:
    def __init__(self, available_geometry) -> None:
        self.available_geometry = available_geometry

    def availableGeometry(self):
        return self.available_geometry


class FakeStatusBar:
    def __init__(self) -> None:
        self.messages = []

    def showMessage(self, message, duration) -> None:
        self.messages.append((message, duration))


class FakeSettingsDialog:
    instances = []
    exec_hook = None
    exec_error = None

    def __init__(self, *args) -> None:
        self.args = args
        self.exec_count = 0
        self.moves = []
        self.routes = []
        self.focus_count = 0
        self.visible = False
        self.__class__.instances.append(self)

    def size(self):
        return FakeSize(680, 620)

    def move(self, x, y) -> None:
        self.moves.append((x, y))

    def exec(self) -> None:
        self.exec_count += 1
        self.visible = True
        hook = type(self).exec_hook
        if hook is not None:
            hook(self)
        error = type(self).exec_error
        self.visible = False
        if error is not None:
            raise error

    def open_page(self, *args) -> None:
        self.routes.append(args)

    def isVisible(self) -> bool:
        return self.visible

    def setFocus(self) -> None:
        self.focus_count += 1


class ControllerCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        names = (
            "aqt", "aqt.deckbrowser", "aqt.operations", "aqt.qt", "aqt.theme",
            "home_dashboard_overhaul.controller",
        )
        cls.saved_modules = {name: sys.modules.get(name) for name in names}
        hooks = SimpleNamespace(
            browser_will_search=HookList(),
            deck_browser_will_render_content=HookList(),
            webview_will_set_content=HookList(),
            webview_did_receive_js_message=HookList(),
            profile_did_open=HookList(),
            profile_will_close=HookList(),
            reviewer_did_answer_card=HookList(),
            operation_did_execute=HookList(),
            state_did_change=HookList(),
        )
        aqt = ModuleType("aqt")
        aqt.__path__ = []
        aqt.gui_hooks = hooks
        aqt.dialogs = FakeDialogs(hooks)
        cutoff = int((datetime.now().astimezone() + timedelta(days=1)).timestamp())
        aqt.mw = SimpleNamespace(
            addonManager=FakeAddonManager(),
            col=SimpleNamespace(sched=SimpleNamespace(today=500, day_cutoff=cutoff), mod=1),
        )
        aqt.mw.web = object()
        aqt.mw.form = SimpleNamespace(centralwidget=FakeCentralWidget(aqt.mw.web))
        aqt.mw.centralWidget = lambda: aqt.mw.form.centralwidget
        aqt.mw.geometry = lambda: FakeRect(0, 66, 667, 570)
        aqt.mw.screen = lambda: FakeScreen(FakeRect(0, 0, 1710, 1112))
        cls.status_bar = FakeStatusBar()
        aqt.mw.statusBar = lambda: cls.status_bar
        deckbrowser = ModuleType("aqt.deckbrowser")
        deckbrowser.DeckBrowser = FakeDeckBrowser
        operations = ModuleType("aqt.operations")
        operations.QueryOp = FakeQueryOp
        qt = ModuleType("aqt.qt")
        qt.QTimer = FakeQTimer
        theme = ModuleType("aqt.theme")
        theme.theme_manager = SimpleNamespace(night_mode=False)
        sys.modules.update({
            "aqt": aqt,
            "aqt.deckbrowser": deckbrowser,
            "aqt.operations": operations,
            "aqt.qt": qt,
            "aqt.theme": theme,
        })
        cls.aqt = aqt
        sys.modules.pop("home_dashboard_overhaul.controller", None)
        cls.module = importlib.import_module("home_dashboard_overhaul.controller")

    @classmethod
    def tearDownClass(cls) -> None:
        for name, previous in cls.saved_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous

    def setUp(self) -> None:
        FakeQueryOp.pending.clear()
        FakeQTimer.pending.clear()
        self.status_bar.messages.clear()
        self.aqt.mw.addonManager.config = {}
        self.aqt.mw.addonManager.writes.clear()
        self.aqt.mw.state = "deckBrowser"
        self.aqt.mw.deckBrowser = FakeDeckBrowser()
        self.aqt.dialogs.opened.clear()
        self.aqt.gui_hooks.browser_will_search.clear()
        FakeSettingsDialog.instances.clear()
        FakeSettingsDialog.exec_hook = None
        FakeSettingsDialog.exec_error = None
        self.rotation_directory = tempfile.TemporaryDirectory()
        self.original_rotation = self.module.ROTATION_STATE_PATH
        self.module.ROTATION_STATE_PATH = Path(self.rotation_directory.name) / "rotation.json"
        self.controller = self.module.DashboardController()
        self.original_collector = self.module.collect_day_insight

    def tearDown(self) -> None:
        self.module.collect_day_insight = self.original_collector
        self.module.ROTATION_STATE_PATH = self.original_rotation
        self.rotation_directory.cleanup()

    @staticmethod
    def most_missed_insight() -> DayInsight:
        facts = sample_snapshot(date(2026, 8, 17)).facts.for_date("2026-08-17")
        return DayInsight(
            date=facts.date,
            browse_target=facts.most_missed_target,
            day_facts=facts,
        )

    def test_bridge_routes_calendar_settings_and_exact_event_editor(self) -> None:
        calls = []
        self.controller.open_settings = lambda *args: calls.append(args)
        context = FakeDeckBrowser()
        calendar = "hdo:" + json.dumps({"command": "settings", "payload": {"page": "calendar_data"}})
        event = "hdo:" + json.dumps({
            "command": "settings",
            "payload": {"page": "events", "date": "2026-08-28", "event_id": "exam-42"},
        })
        self.controller.on_bridge_message((False, None), calendar, context)
        self.assertEqual(calls, [])
        self.assertEqual(len(FakeQTimer.pending), 1)
        FakeQTimer.run_next()
        self.controller.on_bridge_message((False, None), event, context)
        self.assertEqual(calls, [("calendar_data", "", "")])
        self.assertEqual(len(FakeQTimer.pending), 1)
        FakeQTimer.run_next()
        self.assertEqual(calls, [
            ("calendar_data", "", ""),
            ("events", "2026-08-28", "exam-42"),
        ])

    def test_bridge_routes_loading_diagnostics_to_about_support(self) -> None:
        calls = []
        self.controller.open_settings = lambda *args: calls.append(args)
        context = FakeDeckBrowser()
        diagnostics = "hdo:" + json.dumps({"command": "diagnostics", "payload": {}})

        self.controller.on_bridge_message((False, None), diagnostics, context)
        self.assertEqual(calls, [])
        self.assertEqual(len(FakeQTimer.pending), 1)
        FakeQTimer.run_next()
        self.assertEqual(calls, [("about_support", "", "")])

    def test_bridge_settings_requests_are_deferred_and_coalesced(self) -> None:
        calls = []
        self.controller.open_settings = lambda *args: calls.append(args)

        self.controller.request_settings_open("dashboard")
        self.controller.request_settings_open("events", "2026-08-28", "exam-42")

        self.assertEqual(calls, [])
        self.assertEqual(len(FakeQTimer.pending), 1)
        FakeQTimer.run_next()
        self.assertEqual(calls, [("events", "2026-08-28", "exam-42")])
        self.assertFalse(self.controller._settings_open_pending)
        self.assertIsNone(self.controller._pending_settings_request)

    def test_settings_constructs_parented_dialog_and_executes_immediately(self) -> None:
        settings = ModuleType("home_dashboard_overhaul.settings")
        settings.SettingsDialog = FakeSettingsDialog

        with patch.dict(sys.modules, {"home_dashboard_overhaul.settings": settings}):
            self.controller.open_settings("calendar_data", "2026-08-28", "exam-42")
            dialog = FakeSettingsDialog.instances[-1]

            self.assertEqual(
                dialog.args,
                (
                    self.aqt.mw,
                    self.controller,
                    "calendar_data",
                    "2026-08-28",
                    "exam-42",
                ),
            )
            self.assertEqual(dialog.moves, [])
            self.assertEqual(dialog.exec_count, 1)
            self.assertEqual(FakeQTimer.pending, [])
            self.assertIsNone(self.controller._active_settings_dialog)

    def test_reentrant_menu_and_deferred_gear_route_the_live_dialog(self) -> None:
        settings = ModuleType("home_dashboard_overhaul.settings")
        settings.SettingsDialog = FakeSettingsDialog

        def reroute(_dialog) -> None:
            self.controller.open_settings("calendar_data")
            self.controller.request_settings_open(
                "events",
                "2026-08-28",
                "exam-42",
            )
            FakeQTimer.run_next()

        FakeSettingsDialog.exec_hook = reroute
        with patch.dict(sys.modules, {"home_dashboard_overhaul.settings": settings}):
            self.controller.open_settings("dashboard")

        self.assertEqual(len(FakeSettingsDialog.instances), 1)
        dialog = FakeSettingsDialog.instances[0]
        self.assertEqual(
            dialog.routes,
            [
                ("calendar_data", "", ""),
                ("events", "2026-08-28", "exam-42"),
            ],
        )
        self.assertEqual(dialog.focus_count, 2)
        self.assertEqual(dialog.moves, [])
        self.assertIsNone(self.controller._active_settings_dialog)

    def test_active_settings_reference_clears_when_modal_exec_raises(self) -> None:
        settings = ModuleType("home_dashboard_overhaul.settings")
        settings.SettingsDialog = FakeSettingsDialog
        FakeSettingsDialog.exec_error = RuntimeError("dialog failed")

        with patch.dict(sys.modules, {"home_dashboard_overhaul.settings": settings}):
            with self.assertRaisesRegex(RuntimeError, "dialog failed"):
                self.controller.open_settings()

        self.assertIsNone(self.controller._active_settings_dialog)

    def test_settings_open_does_not_query_or_move_against_the_parent_screen(self) -> None:
        FakeSettingsDialog.instances.clear()
        settings = ModuleType("home_dashboard_overhaul.settings")
        settings.SettingsDialog = FakeSettingsDialog
        original_screen = self.aqt.mw.screen
        self.aqt.mw.screen = lambda: (_ for _ in ()).throw(
            AssertionError("primary Settings must leave placement to Qt")
        )
        try:
            with patch.dict(sys.modules, {"home_dashboard_overhaul.settings": settings}):
                self.controller.open_settings()
        finally:
            self.aqt.mw.screen = original_screen

        dialog = FakeSettingsDialog.instances[-1]
        self.assertEqual(dialog.moves, [])
        self.assertEqual(dialog.exec_count, 1)
        self.assertEqual(self.status_bar.messages, [])

    def test_profile_close_cancels_pending_bridge_dialog(self) -> None:
        FakeSettingsDialog.instances.clear()
        settings = ModuleType("home_dashboard_overhaul.settings")
        settings.SettingsDialog = FakeSettingsDialog

        with patch.dict(sys.modules, {"home_dashboard_overhaul.settings": settings}):
            self.controller.request_settings_open("events")
            pending_token = self.controller._settings_request_token

            self.controller.on_profile_close()

            self.assertIsNone(self.controller._pending_settings_request)
            self.assertFalse(self.controller._settings_open_pending)
            self.assertGreater(self.controller._settings_request_token, pending_token)

            FakeQTimer.run_next()
            self.assertEqual(FakeSettingsDialog.instances, [])

    def test_year_scroll_position_survives_a_controller_rerender(self) -> None:
        message = "hdo:" + json.dumps({
            "command": "calendar_year_scroll",
            "payload": {"left": 137.5},
        })
        self.controller.on_bridge_message((False, None), message, FakeDeckBrowser())
        self.assertEqual(self.controller.year_scroll_left, 137.5)

        self.controller.snapshot = sample_snapshot(date(2026, 8, 17))
        self.controller.cache_key = self.controller._key()
        content = SimpleNamespace(stats="")
        self.controller.on_deck_browser_render(FakeDeckBrowser(), content)
        self.assertIn('"year_scroll_left":137.5', content.stats)

    def test_today_selection_requests_one_fresh_year_centering_pass(self) -> None:
        self.controller.year_scroll_left = 137.5
        current = self.controller._scheduler_date()
        self.assertIsNotNone(current)

        self.controller.set_calendar_selection(current.isoformat(), True)

        self.assertTrue(self.controller.selection_follows_today)
        self.assertIsNone(self.controller.year_scroll_left)

    def test_reviewed_and_due_actions_use_only_cached_exact_day_targets(self) -> None:
        snapshot = sample_snapshot(date(2026, 8, 17))
        self.controller.snapshot = snapshot
        self.controller.cache_key = self.controller._key()
        self.controller.open_day_in_browser("2026-08-17")
        browser = self.aqt.dialogs.opened[-1][1]
        self.assertEqual(browser.searches, [snapshot.facts.for_date("2026-08-17").browse_target.query])
        self.controller.open_day_in_browser("2026-08-18")
        due_browser = self.aqt.dialogs.opened[-1][1]
        self.assertEqual(due_browser.searches, [snapshot.facts.for_date("2026-08-18").browse_target.query])
        before = len(self.aqt.dialogs.opened)
        self.controller.open_day_in_browser("2026-08-16")
        # The fixture has review activity on the past date, so an exact Browser opens.
        self.assertEqual(len(self.aqt.dialogs.opened), before + 1)
        self.controller.open_day_in_browser("bad")
        self.assertEqual(len(self.aqt.dialogs.opened), before + 1)

    def test_most_missed_browser_retains_again_answer_id_rank(self) -> None:
        target = BrowseTarget(
            BrowseTargetKind.MOST_MISSED,
            "cid:42,7,11",
            True,
            (42, 7, 11),
        )
        self.aqt.dialogs.next_notes_mode = True
        self.controller._open_browser_target(target)
        browser = self.aqt.dialogs.opened[-1][1]
        self.assertFalse(browser.table.is_notes_mode())
        self.assertEqual(browser.contexts[-1].ids, (42, 7, 11))
        self.assertFalse(browser.contexts[-1].order)
        self.assertFalse(browser.contexts[-1].reverse)
        self.assertEqual(self.aqt.gui_hooks.browser_will_search, [])

    def test_ordinary_browser_target_does_not_override_user_sort(self) -> None:
        target = BrowseTarget(BrowseTargetKind.REVIEWED, "cid:5,6", True, (5, 6))
        self.controller._open_browser_target(target)
        context = self.aqt.dialogs.opened[-1][1].contexts[-1]
        self.assertIsNone(context.ids)
        self.assertTrue(context.order)

    def test_selected_day_capability_is_coalesced_cached_and_then_opens(self) -> None:
        selected = date(2026, 8, 17)
        self.controller.selected_date = selected.isoformat()
        insight = self.most_missed_insight()
        calls = []
        self.module.collect_day_insight = lambda *_args, **_kwargs: calls.append(selected) or insight
        context = FakeDeckBrowser()
        self.controller.open_most_missed_in_browser(context, selected.isoformat())
        self.controller.open_most_missed_in_browser(context, selected.isoformat())
        self.assertEqual(len(FakeQueryOp.pending), 1)
        self.assertEqual(len(self.controller.inflight_insights), 1)
        FakeQueryOp.pending[0].complete()
        self.assertEqual(calls, [selected])
        self.assertEqual(len(self.aqt.dialogs.opened), 1)
        opened = self.aqt.dialogs.opened[-1][1]
        self.assertEqual(opened.contexts[-1].ids, insight.browse_target.card_ids)

        self.controller.open_most_missed_in_browser(context, selected.isoformat())
        self.assertEqual(len(FakeQueryOp.pending), 1)
        self.assertEqual(len(self.aqt.dialogs.opened), 2)

    def test_most_missed_rejects_nonselected_date_and_query_failure(self) -> None:
        context = FakeDeckBrowser()
        self.controller.selected_date = "2026-08-17"
        self.controller.open_most_missed_in_browser(context, "2026-08-16")
        self.assertEqual(FakeQueryOp.pending, [])
        self.controller.open_most_missed_in_browser(context, "not-a-date")
        self.assertEqual(FakeQueryOp.pending, [])

        self.module.collect_day_insight = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
        self.controller.open_most_missed_in_browser(context, "2026-08-17")
        FakeQueryOp.pending[-1].fail()
        self.assertEqual(self.aqt.dialogs.opened, [])

    def test_day_capability_delivery_never_serializes_ids_or_card_content(self) -> None:
        context = FakeDeckBrowser()
        insight = self.most_missed_insight()
        self.controller._deliver_day_insight(context, 9, insight)
        script = context.web.scripts[-1]
        self.assertIn("receiveDayInsight", script)
        self.assertIn('"most_missed_available":true', script)
        for forbidden in ("100002", "card_ids", "browse_target", "primary_text", "answer_html"):
            self.assertNotIn(forbidden, script)

    def test_date_and_request_validation_fail_closed(self) -> None:
        self.assertIsNone(self.controller._parse_bridge_date("not-a-date"))
        self.assertIsNone(self.controller._parse_bridge_date((date.today() + timedelta(days=36501)).isoformat()))
        self.assertEqual(self.controller._parse_bridge_date(date.today().isoformat()), date.today())
        for invalid in (None, True, 0, -1, 2_147_483_648, "1"):
            self.assertFalse(self.controller._valid_request_id(invalid))
        self.assertTrue(self.controller._valid_request_id(1))

    def test_profile_open_retries_a_loading_render_after_collection_ready(self) -> None:
        calls = []
        self.controller._load_profile_config = lambda: calls.append("load")
        self.controller._schedule_refresh = lambda *args, **kwargs: calls.append(
            (args, kwargs)
        )

        self.controller.on_profile_open()

        self.assertEqual(calls[0], "load")
        self.assertEqual(
            calls[1],
            (("profile_open_ready",), {"delay_ms": 0, "invalidate_on_apply": False}),
        )

    def test_first_render_and_restart_use_the_stored_calendar_view(self) -> None:
        stored = normalize_config({
            "heatmap": {"calendar_view": "month"},
            "migration": {"completed": True},
        })
        self.aqt.mw.addonManager.config = stored
        controller = self.module.DashboardController()
        controller._load_profile_config()
        self.assertEqual(controller.config["heatmap"]["calendar_view"], "month")
        self.assertEqual(self.aqt.mw.addonManager.writes, [])

        content = SimpleNamespace(stats="")
        controller.on_deck_browser_render(FakeDeckBrowser(), content)
        self.assertIn('data-hdo-calendar-view="month"', content.stats)
        self.assertIn('data-hdo-calendar-view="month" aria-busy="true"', content.stats)

        before = len(self.aqt.mw.addonManager.writes)
        controller.set_calendar_view("year")
        self.assertEqual(len(self.aqt.mw.addonManager.writes), before + 1)
        self.assertEqual(self.aqt.mw.addonManager.config["heatmap"]["calendar_view"], "year")
        restarted = self.module.DashboardController()
        self.assertEqual(restarted.config["heatmap"]["calendar_view"], "year")

        writes = len(self.aqt.mw.addonManager.writes)
        restarted.set_calendar_view("invalid")
        restarted.set_calendar_view("year")
        self.assertEqual(len(self.aqt.mw.addonManager.writes), writes)

    def test_settings_save_commits_config_and_manual_verse_as_one_transaction(self) -> None:
        staged = deepcopy(self.controller.config)
        staged["appearance"]["mode"] = "dark"
        staged["bible"]["rotation_mode"] = "manual"
        preferred = staged["bible"]["quotes"][1]

        self.controller.save_config(staged, preferred_verse=preferred)

        self.assertEqual(self.aqt.mw.addonManager.config["appearance"]["mode"], "dark")
        self.assertEqual(self.controller.config["appearance"]["mode"], "dark")
        rotation = json.loads(self.module.ROTATION_STATE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(rotation["quote"], preferred)
        self.assertEqual(self.controller.rotator._memory_quote, preferred)

    def test_manual_verse_failure_rolls_back_config_and_previous_state_bytes(self) -> None:
        previous_config = deepcopy(self.controller.config)
        self.aqt.mw.addonManager.config = deepcopy(previous_config)
        previous_rotation = b'{"version":1,"quote":"previous"}\n'
        self.module.ROTATION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.module.ROTATION_STATE_PATH.write_bytes(previous_rotation)
        staged = deepcopy(previous_config)
        staged["appearance"]["mode"] = "dark"
        staged["bible"]["rotation_mode"] = "manual"
        preferred = staged["bible"]["quotes"][0]

        with patch.object(
            self.controller.rotator,
            "persist_prepared",
            side_effect=OSError("verse disk unavailable"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Could not save the current manual verse; previous settings were restored",
            ):
                self.controller.save_config(staged, preferred_verse=preferred)

        self.assertEqual(self.aqt.mw.addonManager.config, previous_config)
        self.assertEqual(self.module.ROTATION_STATE_PATH.read_bytes(), previous_rotation)
        self.assertEqual(self.controller.config, previous_config)
        self.assertEqual(len(self.aqt.mw.addonManager.writes), 2)

    def test_config_failure_never_mutates_manual_verse_state(self) -> None:
        previous_rotation = b'{"version":1,"quote":"previous"}\n'
        self.module.ROTATION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.module.ROTATION_STATE_PATH.write_bytes(previous_rotation)
        staged = deepcopy(self.controller.config)
        staged["bible"]["rotation_mode"] = "manual"
        preferred = staged["bible"]["quotes"][0]

        with patch.object(
            self.aqt.mw.addonManager,
            "writeConfig",
            side_effect=OSError("config disk unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Could not write add-on configuration"):
                self.controller.save_config(staged, preferred_verse=preferred)

        self.assertEqual(self.module.ROTATION_STATE_PATH.read_bytes(), previous_rotation)
        self.assertNotEqual(self.controller.config["bible"]["rotation_mode"], "manual")

    def test_refresh_failure_retains_previous_snapshot_and_exposes_retry_state(self) -> None:
        previous = sample_snapshot(date(2026, 8, 17))
        self.controller.snapshot = previous
        key = self.controller._key()
        self.controller._request_snapshot(key)
        self.assertEqual(len(FakeQueryOp.pending), 1)

        FakeQueryOp.pending[0].fail(RuntimeError("refresh failed"))

        self.assertIs(self.controller.snapshot, previous)
        self.assertTrue(self.controller.refresh_error)
        self.assertFalse(self.controller.initial_failure)
        scripts = self.aqt.mw.deckBrowser.web.scripts
        self.assertTrue(any("setRefreshFailed" in script for script in scripts))

    def test_initial_query_failure_has_no_fake_zero_snapshot(self) -> None:
        self.controller.snapshot = None
        key = self.controller._key()
        self.controller._request_snapshot(key)
        FakeQueryOp.pending[0].fail(RuntimeError("initial failed"))
        self.assertIsNone(self.controller.snapshot)
        self.assertTrue(self.controller.initial_failure)
        self.assertFalse(self.controller.refresh_error)


if __name__ == "__main__":
    unittest.main()
