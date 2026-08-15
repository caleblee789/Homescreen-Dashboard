from __future__ import annotations

from datetime import date, datetime, timedelta
import importlib
import json
import sys
from types import ModuleType, SimpleNamespace
import unittest

# Load the package once while aqt is unavailable so its add-on entry point stays
# inert, then install the narrow fakes needed to exercise controller caching.
from home_dashboard_overhaul.models import DayInsight, InsightItem


class FakeAddonManager:
    def addonFromModule(self, _name):
        return "home_dashboard_overhaul"

    def getConfig(self, _package):
        return {}


class FakeBrowser:
    def __init__(self) -> None:
        self.searches = []

    def search_for(self, query):
        self.searches.append(query)


class FakeDialogs:
    def __init__(self) -> None:
        self.opened = []

    def open(self, name, _parent):
        browser = FakeBrowser()
        self.opened.append((name, browser))
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


class ControllerInsightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.saved_modules = {
            name: sys.modules.get(name)
            for name in (
                "aqt",
                "aqt.deckbrowser",
                "aqt.operations",
                "aqt.theme",
                "home_dashboard_overhaul.controller",
            )
        }
        aqt = ModuleType("aqt")
        aqt.__path__ = []
        aqt.gui_hooks = SimpleNamespace()
        aqt.dialogs = FakeDialogs()
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
        self.controller = self.module.DashboardController()
        self.original_collector = self.module.collect_day_insight

    def tearDown(self) -> None:
        self.module.collect_day_insight = self.original_collector

    @staticmethod
    def _insight(selected: date) -> DayInsight:
        return DayInsight(
            date=selected.isoformat(),
            study_date=selected.isoformat(),
            valid_answer_count=4,
            again_count=2,
            insight_kind="trouble_cards",
            items=[InsightItem("Prompt", "Deck", 2, "Again ×2")],
            browse_action="trouble_cards",
            browser_query="cid:123,456",
        )

    def test_malformed_dates_ranges_and_request_ids_are_rejected(self) -> None:
        parser = self.controller._parse_bridge_date
        self.assertIsNone(parser("not-a-date"))
        self.assertIsNone(parser((date.today() + timedelta(days=36501)).isoformat()))
        self.assertEqual(parser(date.today().isoformat()), date.today())
        for invalid in (None, True, 0, -1, 2_147_483_648, "1"):
            self.assertFalse(self.controller._valid_request_id(invalid))
        self.assertTrue(self.controller._valid_request_id(1))

        context = FakeDeckBrowser()
        message = "hdo:" + json.dumps({
            "command": "date_insight",
            "payload": {"date": "not-a-date", "request_id": 1},
        })
        self.controller.on_bridge_message((False, None), message, context)
        self.assertEqual(FakeQueryOp.pending, [])

    def test_one_background_query_serves_waiters_then_cache_and_browser(self) -> None:
        selected = date.today() - timedelta(days=1)
        expected = self._insight(selected)
        self.module.collect_day_insight = lambda *_args: expected
        first = FakeDeckBrowser()
        second = FakeDeckBrowser()
        self.controller.request_day_insight(first, selected, 1)
        self.controller.request_day_insight(second, selected, 2)
        self.assertEqual(len(FakeQueryOp.pending), 1)
        FakeQueryOp.pending[0].complete()
        self.assertEqual(len(first.web.scripts), 1)
        self.assertEqual(len(second.web.scripts), 1)
        self.assertNotIn("cid:123,456", first.web.scripts[0])
        self.assertNotIn("browser_query", first.web.scripts[0])

        cached = FakeDeckBrowser()
        self.controller.request_day_insight(cached, selected, 3)
        self.assertEqual(len(FakeQueryOp.pending), 1)
        self.assertEqual(len(cached.web.scripts), 1)
        self.controller.open_day_in_browser(selected.isoformat())
        self.assertEqual(self.aqt.dialogs.opened[-1][0], "Browser")
        self.assertEqual(self.aqt.dialogs.opened[-1][1].searches, ["cid:123,456"])

    def test_open_day_falls_back_to_date_scoped_search_without_cached_target(self) -> None:
        scheduling_date = self.module.scheduling_today(self.aqt.mw.col.sched.day_cutoff)
        self.controller.open_day_in_browser((scheduling_date - timedelta(days=1)).isoformat())
        targetless = DayInsight(
            date=scheduling_date.isoformat(),
            study_date=scheduling_date.isoformat(),
            insight_kind="trouble_cards",
            empty_reason="past_no_answers",
        )
        self.controller.insight_cache[(self.controller._key(), scheduling_date.isoformat())] = targetless
        self.controller.open_day_in_browser(scheduling_date.isoformat())
        self.assertEqual(
            [browser.searches for _name, browser in self.aqt.dialogs.opened],
            [["prop:rated=-1"], ["(prop:rated=0 or prop:due=0)"]],
        )

    def test_generation_change_discards_stale_response_and_profile_close_clears_cache(self) -> None:
        selected = date.today() - timedelta(days=1)
        expected = self._insight(selected)
        self.module.collect_day_insight = lambda *_args: expected
        context = FakeDeckBrowser()
        self.controller.request_day_insight(context, selected, 1)
        pending = FakeQueryOp.pending[0]
        self.controller.invalidate()
        pending.complete()
        self.assertEqual(context.web.scripts, [])
        self.assertEqual(self.controller.insight_cache, {})

        current_key = self.controller._key()
        self.controller.insight_cache[(current_key, selected.isoformat())] = expected
        self.controller.on_profile_close()
        self.assertEqual(self.controller.insight_cache, {})
        self.assertEqual(self.controller.inflight_insights, {})


if __name__ == "__main__":
    unittest.main()
