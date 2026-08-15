from __future__ import annotations

from datetime import date, datetime, timezone
import os
import sqlite3
import time
import unittest

from home_dashboard_overhaul.analytics import (
    _buried,
    _events,
    _history_query,
    _lifetime_paces,
    _queue,
    browser_search_for_day,
    calculate_long_term,
    collect_snapshot,
    pace_lower_bound,
    scheduling_today,
)
from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.models import VerseContent


class FakeDB:
    def __init__(
        self,
        history=None,
        forecast=None,
        today=(10, 100_000),
        today_new=2,
        lifetime=(100, 1_000_000, 20, 400_000),
        buried=(3, 2, 7),
    ) -> None:
        self.history = history if history is not None else [("2026-08-12", 5, 1), ("2026-08-13", 7, 2)]
        self.forecast = forecast if forecast is not None else [(500, 3), (501, 4)]
        self.today = today
        self.today_new = today_new
        self.lifetime = lifetime
        self.buried = buried
        self.history_queries = 0
        self.history_sql = ""
        self.lifetime_sql = ""
        self.today_new_sql = ""

    def first(self, sql, *args):
        if "FROM cards WHERE queue IN (-2, -3)" in sql:
            return self.buried
        if "sum(CASE" in sql and "r.ease = 1" not in sql:
            self.lifetime_sql = sql
            return self.lifetime
        if "count(DISTINCT CASE" in sql:
            self.today_new_sql = sql
            return (self.today_new,)
        if "FROM revlog" in sql and "id >= ?" in sql:
            return self.today
        return None

    def all(self, sql, *args):
        if "FROM revlog" in sql:
            self.history_queries += 1
            self.history_sql = sql
            return list(self.history)
        if "FROM cards" in sql:
            return list(self.forecast)
        return []


class DueTree:
    def __init__(self, new=8, learning=10, review=124) -> None:
        self.new_count = new
        self.learn_count = learning
        self.review_count = review


class Scheduler:
    today = 500
    day_cutoff = int(datetime(2026, 8, 14, tzinfo=timezone.utc).timestamp())

    def __init__(self, due_tree=None) -> None:
        self.due_tree = due_tree or DueTree()

    def deck_due_tree(self):
        return self.due_tree


class Decks:
    def children(self, _deck_id):
        return []


class FakeCollection:
    def __init__(self, history=None, forecast=None, due_tree=None, **db_values) -> None:
        self.db = FakeDB(history, forecast, **db_values)
        self.sched = Scheduler(due_tree)
        self.decks = Decks()


class SQLiteDB:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(
            "CREATE TABLE revlog (id INTEGER PRIMARY KEY, cid INTEGER, ease INTEGER, "
            "type INTEGER, lastIvl INTEGER, time INTEGER);"
            "CREATE TABLE cards (id INTEGER PRIMARY KEY, did INTEGER, queue INTEGER, due INTEGER, type INTEGER);"
        )

    def first(self, sql, *args):
        return self.connection.execute(sql, args).fetchone()

    def all(self, sql, *args):
        return self.connection.execute(sql, args).fetchall()


class SQLiteCollection:
    def __init__(self) -> None:
        self.db = SQLiteDB()
        self.sched = Scheduler()
        self.decks = Decks()


class LongTermTests(unittest.TestCase):
    def test_streak_gaps_and_yesterday_current_streak(self) -> None:
        stats = calculate_long_term([
            ("2026-08-08", 10),
            ("2026-08-09", 20),
            ("2026-08-11", 5),
            ("2026-08-12", 15),
        ], date(2026, 8, 13))
        self.assertEqual(stats.average_reviews_per_active_day, 12)
        self.assertEqual(stats.active_days_percent, 67)
        self.assertEqual(stats.longest_streak, 2)
        self.assertEqual(stats.current_streak, 2)

    def test_empty_history(self) -> None:
        self.assertEqual(calculate_long_term([], date(2026, 8, 13)).longest_streak, 0)


class SnapshotTests(unittest.TestCase):
    def test_daily_new_card_query_executes_and_honors_rescheduled_preference(self) -> None:
        col = SQLiteCollection()
        local_zone = datetime.now().astimezone().tzinfo

        def millis(day: int, hour: int, suffix: int) -> int:
            stamp = datetime(2026, 8, day, hour, 0, 0, suffix * 1000, tzinfo=local_zone)
            return int(stamp.timestamp() * 1000)

        col.sched.day_cutoff = int(datetime(2026, 8, 14, 4, 0, tzinfo=local_zone).timestamp())
        col.db.connection.executemany(
            "INSERT INTO cards (id, did, queue, due, type) VALUES (?, 1, 2, 500, 2)",
            [(1,), (2,), (3,)],
        )
        col.db.connection.executemany(
            "INSERT INTO revlog (id, cid, ease, type, lastIvl, time) VALUES (?, ?, 3, ?, ?, 1000)",
            [
                (millis(12, 12, 1), 1, 0, 0),
                (millis(13, 10, 1), 1, 1, 1),
                (millis(13, 11, 1), 2, 0, 0),
                (millis(10, 12, 1), 3, 0, 0),
                (millis(13, 13, 1), 3, 0, 0),
            ],
        )
        included = _history_query(col, normalize_config({}), date(2026, 8, 13), False)
        excluded = _history_query(
            col,
            normalize_config({"new_cards": {"include_rescheduled": False}}),
            date(2026, 8, 13),
            False,
        )
        self.assertEqual(next(row for row in included if row[0] == "2026-08-13"), ("2026-08-13", 3, 2))
        self.assertEqual(next(row for row in excluded if row[0] == "2026-08-13"), ("2026-08-13", 3, 1))

    def test_today_remaining_buried_and_calendar_fields_are_separate(self) -> None:
        col = FakeCollection()
        snapshot = collect_snapshot(col, normalize_config({}), VerseContent("Body", "Ref"))
        today = next(item for item in snapshot.activity if item.date == "2026-08-13")
        self.assertEqual(today.reviews_completed, 7)
        self.assertEqual(today.reviews_due, 3)
        self.assertEqual(today.new_cards_studied, 2)
        self.assertEqual(snapshot.today.new_cards_studied, 2)
        self.assertEqual(snapshot.queue.total, 142)
        self.assertEqual(snapshot.queue.estimated_duration_seconds, 1500)
        self.assertEqual(snapshot.today.pace_value, 10.0)
        self.assertEqual((snapshot.buried.new, snapshot.buried.learning, snapshot.buried.review), (3, 2, 7))
        self.assertEqual(col.db.history_queries, 1)
        self.assertEqual(snapshot.scheduling_date, "2026-08-13")
        self.assertEqual(snapshot.today_insight.date, "")
        self.assertNotIn("insight", snapshot.errors)
        self.assertTrue(snapshot.day_cutoff_iso)
        self.assertIn("r.type IN (0, 3) AND r.lastIvl = 0", col.db.history_sql)

    def test_today_new_card_count_is_independent_of_calendar_history_filters(self) -> None:
        col = FakeCollection(history=[], today_new=4)
        snapshot = collect_snapshot(col, normalize_config({"heatmap": {"history_days": 1}}), VerseContent())
        self.assertEqual(snapshot.today.new_cards_studied, 4)
        self.assertTrue(all(item.new_cards_studied == 0 for item in snapshot.activity))

    def test_eta_uses_lifetime_pace_for_zero_through_nine_answers(self) -> None:
        for today in ((0, 0), (9, 90_000)):
            with self.subTest(today=today):
                col = FakeCollection(today=today, lifetime=(100, 2_000_000, 10, 300_000))
                snapshot = collect_snapshot(col, normalize_config({}), VerseContent())
                self.assertEqual(snapshot.queue.estimated_duration_seconds, 2940)
        self.assertIsNone(collect_snapshot(
            FakeCollection(today=(0, 0)), normalize_config({}), VerseContent()
        ).today.pace_value)
        self.assertEqual(collect_snapshot(
            FakeCollection(today=(9, 90_000)), normalize_config({}), VerseContent()
        ).today.pace_value, 10.0)

    def test_eta_switches_to_today_average_at_answer_ten(self) -> None:
        col = FakeCollection(today=(10, 100_000), lifetime=(100, 2_000_000, 10, 300_000))
        snapshot = collect_snapshot(col, normalize_config({}), VerseContent())
        self.assertEqual(snapshot.queue.estimated_duration_seconds, 1620)

    def test_eta_uses_base_pace_when_no_new_card_history_exists(self) -> None:
        col = FakeCollection(today=(0, 0), lifetime=(100, 2_000_000, 0, 0))
        snapshot = collect_snapshot(col, normalize_config({}), VerseContent())
        self.assertEqual(snapshot.queue.estimated_duration_seconds, 2880)

    def test_eta_is_done_at_zero_remaining_and_unknown_without_history(self) -> None:
        done = collect_snapshot(
            FakeCollection(today=(0, 0), lifetime=(0, 0, 0, 0), due_tree=DueTree(0, 0, 0)),
            normalize_config({}),
            VerseContent(),
        )
        unknown = collect_snapshot(
            FakeCollection(today=(0, 0), lifetime=(0, 0, 0, 0)),
            normalize_config({}),
            VerseContent(),
        )
        self.assertEqual(done.queue.estimated_duration_seconds, 0)
        self.assertIsNone(unknown.queue.estimated_duration_seconds)

    def test_eta_rounds_up_to_a_whole_minute(self) -> None:
        queue = _queue(FakeCollection(due_tree=DueTree(1, 0, 0)), 10.0, 61.0)
        self.assertEqual(queue.estimated_duration_seconds, 120)

    def test_forecast_only_still_produces_activity(self) -> None:
        snapshot = collect_snapshot(FakeCollection(history=[]), normalize_config({}), VerseContent())
        self.assertEqual(
            [(item.reviews_completed, item.reviews_due, item.new_cards_studied) for item in snapshot.activity],
            [(0, 3, 0), (0, 4, 0)],
        )

    def test_calendar_new_card_history_excludes_reintroductions_when_configured(self) -> None:
        col = FakeCollection()
        collect_snapshot(
            col,
            normalize_config({"new_cards": {"include_rescheduled": False}}),
            VerseContent(),
        )
        self.assertIn("NOT EXISTS (SELECT 1 FROM revlog prior", col.db.history_sql)
        self.assertIn("NOT EXISTS (SELECT 1 FROM revlog prior", col.db.lifetime_sql)
        self.assertIn("NOT EXISTS (SELECT 1 FROM revlog prior", col.db.today_new_sql)

    def test_overdue_forecast_is_clamped_to_today(self) -> None:
        col = FakeCollection(history=[], forecast=[(490, 2), (500, 3), (501, 4)])
        snapshot = collect_snapshot(col, normalize_config({}), VerseContent())
        self.assertEqual(snapshot.activity[0].date, "2026-08-13")
        self.assertEqual(snapshot.activity[0].reviews_due, 5)

    def test_scheduling_today_uses_cutoff_not_wall_clock_now(self) -> None:
        cutoff = int(datetime(2026, 11, 2, tzinfo=timezone.utc).timestamp())
        self.assertEqual(scheduling_today(cutoff), date(2026, 11, 1))

    @unittest.skipUnless(hasattr(time, "tzset"), "requires Unix timezone support")
    def test_pace_window_preserves_wall_clock_cutoff_across_dst(self) -> None:
        previous = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "America/Chicago"
            time.tzset()
            cutoff = int(datetime(2026, 3, 8, 4, 0).timestamp())
            lower = pace_lower_bound(cutoff, 1)
            self.assertEqual(cutoff - lower, 23 * 3600)
        finally:
            if previous is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = previous
            time.tzset()

    def test_browser_search_uses_supported_signed_day_offsets(self) -> None:
        today = date(2026, 8, 13)
        self.assertEqual(browser_search_for_day(date(2026, 8, 12), today), "prop:rated=-1")
        self.assertEqual(browser_search_for_day(today, today), "(prop:rated=0 or prop:due=0)")
        self.assertEqual(browser_search_for_day(date(2026, 8, 14), today), "prop:due=1")

    def test_events_use_the_civil_calendar_not_anki_rollover(self) -> None:
        config = normalize_config({
            "events": {
                "items": [
                    {"id": "today", "name": "Today", "date": "2026-08-13", "archived": False},
                    {"id": "tomorrow", "name": "Tomorrow", "date": "2026-08-14", "archived": False},
                ]
            }
        })
        events = _events(config, date(2026, 8, 13))
        self.assertEqual([(item.name, item.days_remaining) for item in events], [("Today", 0), ("Tomorrow", 1)])


class HistoricalTimingAndBuriedTests(unittest.TestCase):
    def test_lifetime_and_empirical_new_card_paces_use_valid_answers(self) -> None:
        col = SQLiteCollection()
        col.db.connection.executemany(
            "INSERT INTO revlog (id, cid, ease, type, lastIvl, time) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, 1, 3, 0, 0, 5_000),
                (2, 2, 3, 0, 0, 15_000),
                (3, 3, 3, 1, 10, 20_000),
                (4, 4, 3, 1, 10, 10_000),
                (5, 4, 3, 0, 0, 50_000),
                (6, 5, 3, 4, 0, 100_000),
                (7, 6, 0, 0, 0, 100_000),
            ],
        )
        overall, included_new = _lifetime_paces(col, True)
        _, excluded_new = _lifetime_paces(col, False)
        self.assertAlmostEqual(overall, 20.0)
        self.assertAlmostEqual(included_new, 70.0 / 3.0)
        self.assertAlmostEqual(excluded_new, 10.0)

    def test_buried_counts_both_queue_kinds_and_classifies_relearning_as_learning(self) -> None:
        col = SQLiteCollection()
        rows = [
            (1, 1, -2, 0, 0),
            (2, 1, -3, 0, 0),
            (3, 1, -2, 0, 1),
            (4, 1, -3, 0, 3),
            (5, 1, -2, 0, 2),
            (6, 1, -1, 0, 0),
            (7, 1, 2, 0, 2),
        ]
        col.db.connection.executemany(
            "INSERT INTO cards (id, did, queue, due, type) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        stats = _buried(col)
        self.assertEqual((stats.new, stats.learning, stats.review), (2, 2, 1))


if __name__ == "__main__":
    unittest.main()
