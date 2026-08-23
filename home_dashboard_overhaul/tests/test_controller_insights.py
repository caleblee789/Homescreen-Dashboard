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

from home_dashboard_overhaul.models import (
    BrowseTarget,
    BrowseTargetKind,
    DayInsight,
)
from home_dashboard_overhaul.tests.fixtures import sample_snapshot


class HookList(list):
    pass


class FakeAddonManager:
    def __init__(self) -> None:
        self.writes = []

    def addonFromModule(self, _name):
        return "home_dashboard_overhaul"

    def getConfig(self, _package):
        return {}

    def writeConfig(self, package, config):
        self.writes.append((package, deepcopy(config)))


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


class ControllerCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        names = (
            "aqt", "aqt.deckbrowser", "aqt.operations", "aqt.theme",
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
        deckbrowser = ModuleType("aqt.deckbrowser")
        deckbrowser.DeckBrowser = FakeDeckBrowser
        operations = ModuleType("aqt.operations")
        operations.QueryOp = FakeQueryOp
        theme = ModuleType("aqt.theme")
        theme.theme_manager = SimpleNamespace(night_mode=False)
        sys.modules.update({
            "aqt": aqt,
            "aqt.deckbrowser": deckbrowser,
            "aqt.operations": operations,
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
        self.aqt.dialogs.opened.clear()
        self.aqt.gui_hooks.browser_will_search.clear()
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
        self.controller.on_bridge_message((False, None), event, context)
        self.assertEqual(calls, [
            ("calendar_data",),
            ("events", "2026-08-28", "exam-42"),
        ])

    def test_bridge_routes_loading_diagnostics_to_about_support(self) -> None:
        calls = []
        self.controller.open_settings = lambda *args: calls.append(args)
        context = FakeDeckBrowser()
        diagnostics = "hdo:" + json.dumps({"command": "diagnostics", "payload": {}})

        self.controller.on_bridge_message((False, None), diagnostics, context)

        self.assertEqual(calls, [("about_support",)])

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


if __name__ == "__main__":
    unittest.main()
