from __future__ import annotations

from datetime import date, datetime
import os
import sqlite3
import time
from types import SimpleNamespace
import unittest

from home_dashboard_overhaul.analytics import (
    _buried,
    _events,
    _history_query,
    _lifetime_paces,
    _queue,
    browse_target_for_day,
    calculate_last_seven_days,
    calculate_long_term,
    collect_dashboard_facts,
    collect_snapshot,
    pace_lower_bound,
    scheduling_today,
    unavailable_snapshot,
)
from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.models import (
    AvailabilityReason,
    BrowseTargetKind,
    DashboardFacts,
    DayDomainState,
    FilterScope,
    RateMetric,
    RateStatus,
    ValueState,
    ValueStatus,
    VerseContent,
)


class FakeDB:
    def __init__(
        self,
        history=None,
        forecast=None,
        today=(10, 100_000),
        today_new=2,
        lifetime=(100, 1_000_000, 20, 400_000),
        buried=(3, 2, 7),
        remaining=(8, 10, 3),
        intraday_relearning=(0, None),
    ) -> None:
        self.history = history if history is not None else [
            ("2026-08-12", 5, 1, 1, None),
            ("2026-08-13", 7, 2, 2, None),
        ]
        self.forecast = forecast if forecast is not None else [(500, 3), (501, 4)]
        self.today = today
        self.today_new = today_new
        self.lifetime = lifetime
        self.buried = buried
        self.remaining = remaining
        self.intraday_relearning = intraday_relearning
        self.history_queries = 0
        self.history_sql = ""
        self.lifetime_sql = ""
        self.today_new_sql = ""
        self.remaining_sql = ""

    def first(self, sql, *args):
        if "queue = 1" in sql and "type = 3" in sql and "group_concat(id)" in sql:
            return self.intraday_relearning
        if "queue = 0 AND type = 0" in sql:
            return self.remaining
        if "FROM cards WHERE queue IN (-2, -3)" in sql:
            return self.buried
        if "sum(CASE" in sql and "r.ease = 1" not in sql:
            self.lifetime_sql = sql
            return self.lifetime
        if "count(DISTINCT CASE" in sql and "r.ease != 1" in sql:
            answers = sum(max(0, int(row[1] or 0)) for row in self.history)
            new_cards = sum(max(0, int(row[2] or 0)) for row in self.history if len(row) > 2)
            again = sum(max(0, int(row[3] or 0)) for row in self.history if len(row) > 3)
            passed = sum(
                max(0, int(row[4] or 0)) if len(row) >= 7 else max(0, int(row[1] or 0) - (int(row[3] or 0) if len(row) > 3 else 0))
                for row in self.history
            )
            failed = sum(
                max(0, int(row[5] or 0)) if len(row) >= 7 else (max(0, int(row[3] or 0)) if len(row) > 3 else 0)
                for row in self.history
            )
            return answers, new_cards, again, passed, failed
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
            cutoff = int(args[0]) if args else Scheduler.day_cutoff
            current_day = scheduling_today(cutoff)
            if "count(DISTINCT CASE" not in sql:
                return [
                    ((date.fromisoformat(str(row[0])) - current_day).days, row[1])
                    for row in self.history
                ]
            output = []
            for row in self.history:
                day_index = (date.fromisoformat(str(row[0])) - current_day).days
                count = max(0, int(row[1] or 0)) if len(row) > 1 else 0
                new_cards = max(0, int(row[2] or 0)) if len(row) > 2 else 0
                again = max(0, int(row[3] or 0)) if len(row) > 3 else 0
                if len(row) >= 7:
                    passed = max(0, int(row[4] or 0))
                    failed = max(0, int(row[5] or 0))
                    card_ids = row[6]
                else:
                    passed = max(0, count - again)
                    failed = min(count, again)
                    card_ids = row[4] if len(row) > 4 else None
                output.append((day_index, count, new_cards, again, passed, failed, card_ids))
            return output
        if "GROUP BY did" in sql and "queue = 0" in sql:
            self.remaining_sql = sql
            if self.remaining and isinstance(self.remaining[0], (tuple, list)):
                return list(self.remaining)
            return [(1, self.remaining[0], self.remaining[1], self.remaining[2])]
        if "SELECT id, type, queue, due, odue, odid FROM cards" in sql:
            output = []
            card_id = 10_000
            for due, count, *_rest in self.forecast:
                for _ in range(max(0, int(count or 0))):
                    output.append((card_id, 2, 2, int(due), 0, 0))
                    card_id += 1
            return output
        if "FROM cards" in sql:
            return list(self.forecast)
        return []


class DueTree:
    def __init__(self, new=8, learning=10, review=124, deck_id=1, children=()) -> None:
        self.deck_id = deck_id
        self.new_count = new
        self.learn_count = learning
        self.review_count = review
        self.children = tuple(children)


def due_tree_root(*children):
    return SimpleNamespace(deck_id=0, new_count=0, children=tuple(children))


class Scheduler:
    today = 500
    day_cutoff = int(datetime(2026, 8, 14, 4).timestamp())

    def __init__(self, due_tree=None) -> None:
        if due_tree is None:
            self.due_tree = due_tree_root(
                DueTree(new=10_000, deck_id=1),
                DueTree(new=10_000, deck_id=2),
                DueTree(new=10_000, deck_id=99),
            )
        elif getattr(due_tree, "deck_id", None) == 0:
            self.due_tree = due_tree
        else:
            self.due_tree = due_tree_root(due_tree)

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
            "type INTEGER, lastIvl INTEGER, time INTEGER, factor INTEGER NOT NULL DEFAULT 2500);"
            "CREATE TABLE cards (id INTEGER PRIMARY KEY, did INTEGER, queue INTEGER, "
            "due INTEGER, type INTEGER, odid INTEGER NOT NULL DEFAULT 0, "
            "odue INTEGER NOT NULL DEFAULT 0);"
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
        self.assertEqual(stats.average_reviews_per_active_day, 13)
        self.assertEqual(stats.active_days_percent, 67)
        self.assertEqual(stats.longest_streak, 2)
        self.assertEqual(stats.current_streak, 2)
        self.assertEqual(stats.lifetime_cards_studied, 50)
        self.assertEqual(stats.lifetime_retention.status, RateStatus.NO_ACTIVITY)

    def test_lifetime_and_last_seven_rates_distinguish_zero_from_no_activity(self) -> None:
        rows = [
            ("2026-08-06", 10, 1),
            ("2026-08-05", 4, 4),
            ("2026-08-12", 3, 0),
            ("2026-08-13", 5, 2),
        ]
        long_term = calculate_long_term(rows, date(2026, 8, 13))
        recent = calculate_last_seven_days(rows, date(2026, 8, 13))

        self.assertEqual(long_term.lifetime_cards_studied, 22)
        self.assertEqual(
            (
                long_term.lifetime_retention.status,
                long_term.lifetime_retention.numerator,
                long_term.lifetime_retention.denominator,
                long_term.lifetime_retention.percent,
            ),
            (RateStatus.AVAILABLE, 15, 22, 68),
        )
        self.assertEqual(recent.cards_studied, 8)
        self.assertEqual(recent.retention.percent, 75)
        self.assertEqual(recent.again_rate.percent, 25)

        empty = calculate_last_seven_days([], date(2026, 8, 13))
        self.assertEqual(empty.cards_studied, 0)
        self.assertEqual(empty.retention.status, RateStatus.NO_ACTIVITY)
        self.assertIsNone(empty.retention.percent)
        self.assertEqual(empty.again_rate.status, RateStatus.NO_ACTIVITY)
        all_again = calculate_last_seven_days(
            [("2026-08-13", 4, 4)],
            date(2026, 8, 13),
        )
        self.assertEqual(all_again.retention.status, RateStatus.AVAILABLE)
        self.assertEqual(all_again.retention.percent, 0)
        self.assertEqual(all_again.again_rate.percent, 100)

    def test_empty_history(self) -> None:
        stats = calculate_long_term([], date(2026, 8, 13))
        self.assertEqual(stats.longest_streak, 0)
        self.assertEqual(stats.lifetime_cards_studied, 0)
        self.assertEqual(stats.lifetime_retention.status, RateStatus.NO_ACTIVITY)

    def test_current_streak_truth_table(self) -> None:
        today = date(2026, 8, 13)
        cases = (
            ("yesterday complete, no card today", [("2026-08-11", 1), ("2026-08-12", 1)], 2),
            ("first card today extends yesterday", [("2026-08-11", 1), ("2026-08-12", 1), ("2026-08-13", 1)], 3),
            ("yesterday broken, no card today", [("2026-08-11", 1)], 0),
            ("first card after break", [("2026-08-11", 1), ("2026-08-13", 1)], 1),
        )
        for label, rows, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(calculate_long_term(rows, today).current_streak, expected)


class NativeRetentionTests(unittest.TestCase):
    @staticmethod
    def _collection() -> SQLiteCollection:
        col = SQLiteCollection()
        col.sched.day_cutoff = int(datetime(2026, 8, 14, 4).timestamp())
        col.sched.today = 500
        return col

    @staticmethod
    def _insert_reviews(col: SQLiteCollection, rows) -> None:
        col.db.connection.executemany(
            "INSERT INTO revlog (id, cid, ease, type, lastIvl, time, factor) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

    def test_native_eligible_retention_replaces_all_answer_success(self) -> None:
        col = self._collection()
        cutoff_ms = col.sched.day_cutoff * 1000
        start = cutoff_ms - 60_000
        rows = []
        for index in range(947):
            rows.append((start + index, index + 1, 3, 1, 1, 1000, 2500))
        for index in range(153):
            rows.append((start + 947 + index, 10_000 + index, 1, 1, 1, 1000, 2500))
        # Learning Again answers with no prior one-day interval affect the
        # all-answer success rate, but are ineligible for native Retention.
        for index in range(84):
            rows.append((start + 1100 + index, 20_000 + index, 1, 0, 0, 1000, 2500))
        self._insert_reviews(col, rows)

        facts = collect_dashboard_facts(col, normalize_config({}), date(2026, 8, 13))
        recent = facts.last_seven_days.value
        lifetime = facts.long_term.value

        self.assertEqual(RateMetric.from_counts(947, 1184).percent, 80)
        self.assertEqual(recent.cards_studied, 1184)
        self.assertEqual(
            (
                recent.retention.numerator,
                recent.retention.denominator,
                recent.retention.percent,
                recent.again_rate.numerator,
                recent.again_rate.percent,
            ),
            (947, 1100, 86, 153, 14),
        )
        self.assertEqual(
            (
                lifetime.lifetime_retention.numerator,
                lifetime.lifetime_retention.denominator,
                lifetime.lifetime_retention.percent,
            ),
            (947, 1100, 86),
        )

    def test_retention_eligibility_matches_anki_review_kinds_and_cram_rule(self) -> None:
        col = self._collection()
        base = col.sched.day_cutoff * 1000 - 30_000
        self._insert_reviews(col, [
            (base + 1, 1, 3, 1, 0, 1000, 2500),       # Review: pass, always eligible.
            (base + 2, 2, 3, 0, 1, 1000, 2500),       # Learning after >=1 day: pass.
            (base + 3, 3, 1, 2, -86400, 1000, 2500),  # Relearning after >=1 day: fail.
            (base + 4, 4, 4, 3, 1, 1000, 2500),       # Filtered, rescheduling: pass.
            (base + 5, 5, 1, 3, 1, 1000, 0),          # Filtered cram: ineligible.
            (base + 6, 6, 1, 0, 0, 1000, 2500),       # First learning step: ineligible.
            (base + 7, 6, 1, 0, 0, 1000, 2500),       # Repeated same-day attempt.
            (base + 8, 8, 3, 4, 1, 1000, 2500),       # Manual: excluded by scope.
            (base + 9, 9, 3, 5, 1, 1000, 2500),       # Rescheduled: excluded by scope.
        ])

        recent = collect_dashboard_facts(
            col,
            normalize_config({}),
            date(2026, 8, 13),
        ).last_seven_days.value

        self.assertEqual((recent.cards_studied, recent.new_cards_studied), (7, 1))
        self.assertEqual(
            (
                recent.retention.numerator,
                recent.retention.denominator,
                recent.retention.percent,
                recent.again_rate.numerator,
                recent.again_rate.percent,
            ),
            (3, 4, 75, 1, 25),
        )

    def test_exact_seven_period_cutoffs_are_start_inclusive_and_end_exclusive(self) -> None:
        col = self._collection()
        cutoff_ms = col.sched.day_cutoff * 1000
        lower = cutoff_ms - 7 * 86_400 * 1000
        self._insert_reviews(col, [
            (lower - 1, 1, 1, 1, 1, 1000, 2500),
            (lower, 2, 3, 1, 1, 1000, 2500),
            (cutoff_ms - 1, 3, 3, 1, 1, 1000, 2500),
            (cutoff_ms, 4, 1, 1, 1, 1000, 2500),
        ])

        facts = collect_dashboard_facts(col, normalize_config({}), date(2026, 8, 13))

        self.assertEqual(facts.last_seven_days.value.cards_studied, 2)
        self.assertEqual(facts.last_seven_days.value.retention.percent, 100)
        self.assertEqual(facts.today.value.answers, 1)
        self.assertEqual(facts.long_term.value.lifetime_cards_studied, 3)

    def test_calendar_day_index_keeps_exact_active_period_lower_bound_today(self) -> None:
        col = self._collection()
        cutoff_ms = col.sched.day_cutoff * 1000
        lower = cutoff_ms - 86_400 * 1000
        self._insert_reviews(col, [
            (lower - 1, 1, 3, 1, 1, 1000, 2500),
            (lower, 2, 3, 1, 1, 1000, 2500),
            (cutoff_ms - 1, 3, 3, 1, 1, 1000, 2500),
            (cutoff_ms, 4, 3, 1, 1, 1000, 2500),
        ])

        facts = collect_dashboard_facts(col, normalize_config({}), date(2026, 8, 13))

        self.assertEqual(facts.for_date("2026-08-12").reviews_completed.value, 1)
        self.assertEqual(facts.for_date("2026-08-13").reviews_completed.value, 2)
        self.assertEqual(facts.today.value.answers, 2)

    def test_new_introductions_are_distinct_and_resets_follow_scope_policy(self) -> None:
        col = self._collection()
        cutoff_ms = col.sched.day_cutoff * 1000
        older = cutoff_ms - 8 * 86_400 * 1000
        current = cutoff_ms - 10_000
        self._insert_reviews(col, [
            (older, 1, 3, 0, 0, 1000, 2500),
            (current + 1, 1, 0, 4, 0, 0, 2500),
            (current + 2, 1, 3, 0, 0, 1000, 2500),
            (current + 3, 2, 1, 0, 0, 1000, 2500),
            (current + 4, 2, 3, 0, 0, 1000, 2500),
            (current + 5, 3, 3, 3, 0, 1000, 0),
        ])

        included = collect_dashboard_facts(col, normalize_config({}), date(2026, 8, 13))
        excluded = collect_dashboard_facts(
            col,
            normalize_config({"new_cards": {"include_rescheduled": False}}),
            date(2026, 8, 13),
        )

        self.assertEqual(
            (
                included.today.value.new_cards_studied,
                included.last_seven_days.value.new_cards_studied,
            ),
            (2, 2),
        )
        self.assertEqual(
            (
                excluded.today.value.new_cards_studied,
                excluded.last_seven_days.value.new_cards_studied,
            ),
            (1, 1),
        )


class SnapshotTests(unittest.TestCase):
    def test_due_load_reference_uses_positive_full_horizon_p90(self) -> None:
        col = FakeCollection(forecast=[
            (500, 0),
            *[(500 + value, value) for value in range(1, 10)],
            (510, 10_000),
        ])
        facts = collect_dashboard_facts(col, normalize_config({}), date(2026, 8, 13))
        self.assertEqual(facts.due_load_reference, 9.0)

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

    def test_today_uses_exact_native_period_while_calendar_keeps_day_index_facts(self) -> None:
        col = FakeCollection()
        snapshot = collect_snapshot(col, normalize_config({}), VerseContent("Body", "Ref"))
        facts = snapshot.facts
        today = facts.for_date("2026-08-13")
        self.assertEqual(today.reviews_completed.value, 7)
        self.assertEqual(today.reviews_due.value, 3)
        self.assertEqual(today.new_cards_studied.value, 2)
        self.assertEqual(facts.today.value.answers, 10)
        self.assertEqual(facts.today.value.new_cards_studied, 2)
        self.assertEqual(
            (facts.queue.value.new, facts.queue.value.learning, facts.queue.value.review),
            (8, 10, 3),
        )
        self.assertEqual(facts.queue.value.total, 21)
        self.assertEqual(facts.queue.value.estimated_duration_seconds, 300)
        self.assertAlmostEqual(facts.today.value.pace_value, 10.0)
        self.assertEqual(
            (facts.buried.value.new, facts.buried.value.learning, facts.buried.value.review),
            (3, 2, 7),
        )
        self.assertEqual(facts.last_seven_days.value.cards_studied, 12)
        self.assertEqual(facts.last_seven_days.value.retention.percent, 75)
        self.assertEqual(facts.last_seven_days.value.again_rate.percent, 25)
        self.assertEqual(facts.long_term.value.lifetime_cards_studied, 12)
        self.assertEqual(facts.long_term.value.lifetime_retention.percent, 75)
        self.assertEqual(col.db.history_queries, 1)
        self.assertEqual(facts.scheduling_date, "2026-08-13")
        self.assertTrue(facts.next_rollover)
        self.assertEqual(set(snapshot.__dataclass_fields__), {"facts", "verse"})
        self.assertIn("r.type IN (0, 3) AND r.lastIvl = 0", col.db.history_sql)

    def test_today_new_card_count_uses_the_exact_active_scheduler_period(self) -> None:
        col = FakeCollection(history=[], today_new=4)
        snapshot = collect_snapshot(col, normalize_config({"heatmap": {"history_days": 1}}), VerseContent())
        self.assertEqual(snapshot.facts.today.value.new_cards_studied, 4)
        self.assertEqual(snapshot.facts.for_date("2026-08-13").new_cards_studied.value, 0)

    def test_collect_snapshot_preserves_partial_unavailability_without_numeric_projection(self) -> None:
        class HistoryFailureDB(FakeDB):
            def all(self, sql, *args):
                if "FROM revlog" in sql:
                    raise RuntimeError("history unavailable")
                return super().all(sql, *args)

        col = FakeCollection()
        col.db = HistoryFailureDB()
        snapshot = collect_snapshot(col, normalize_config({}), VerseContent())

        self.assertEqual(snapshot.facts.history_coverage.status, ValueStatus.UNAVAILABLE)
        self.assertEqual(snapshot.facts.last_seven_days.status, ValueStatus.UNAVAILABLE)
        self.assertEqual(snapshot.facts.long_term.status, ValueStatus.UNAVAILABLE)
        self.assertEqual(snapshot.facts.today.status, ValueStatus.UNAVAILABLE)
        self.assertEqual(snapshot.facts.queue.status, ValueStatus.AVAILABLE)
        self.assertEqual(snapshot.facts.queue.value.review, 3)
        current = snapshot.facts.for_date(snapshot.facts.scheduling_date)
        self.assertEqual(current.reviews_completed.status, ValueStatus.UNAVAILABLE)
        self.assertIsNone(current.reviews_completed.value)
        self.assertFalse(any(
            hasattr(snapshot, name)
            for name in ("today", "queue", "buried", "events", "activity", "long_term", "errors")
        ))

    def test_eta_uses_lifetime_pace_for_zero_through_nine_answers(self) -> None:
        for today, history in (((0, 0), []), ((9, 90_000), [("2026-08-13", 9, 2)])):
            with self.subTest(today=today):
                col = FakeCollection(
                    history=history,
                    today=today,
                    lifetime=(100, 2_000_000, 10, 300_000),
                )
                snapshot = collect_snapshot(col, normalize_config({}), VerseContent())
                self.assertEqual(snapshot.facts.queue.value.estimated_duration_seconds, 540)
        self.assertIsNone(collect_snapshot(
            FakeCollection(history=[], today=(0, 0)), normalize_config({}), VerseContent()
        ).facts.today.value.pace_value)
        self.assertEqual(collect_snapshot(
            FakeCollection(history=[("2026-08-13", 9, 2)], today=(9, 90_000)),
            normalize_config({}),
            VerseContent(),
        ).facts.today.value.pace_value, 10.0)

    def test_eta_switches_to_today_average_at_answer_ten(self) -> None:
        col = FakeCollection(
            history=[("2026-08-13", 10, 2)],
            today=(10, 100_000),
            lifetime=(100, 2_000_000, 10, 300_000),
        )
        snapshot = collect_snapshot(col, normalize_config({}), VerseContent())
        self.assertEqual(snapshot.facts.queue.value.estimated_duration_seconds, 420)

    def test_eta_uses_base_pace_when_no_new_card_history_exists(self) -> None:
        col = FakeCollection(history=[], today=(0, 0), lifetime=(100, 2_000_000, 0, 0))
        snapshot = collect_snapshot(col, normalize_config({}), VerseContent())
        self.assertEqual(snapshot.facts.queue.value.estimated_duration_seconds, 420)

    def test_eta_is_done_at_zero_remaining_and_unknown_without_history(self) -> None:
        done = collect_snapshot(
            FakeCollection(
                history=[],
                forecast=[],
                today=(0, 0),
                lifetime=(0, 0, 0, 0),
                due_tree=DueTree(0, 0, 0),
                remaining=(0, 0, 0),
            ),
            normalize_config({}),
            VerseContent(),
        )
        unknown = collect_snapshot(
            FakeCollection(today=(0, 0), lifetime=(0, 0, 0, 0)),
            normalize_config({}),
            VerseContent(),
        )
        self.assertEqual(done.facts.queue.value.estimated_duration_seconds, 0)
        self.assertIsNone(unknown.facts.queue.value.estimated_duration_seconds)

    def test_eta_rounds_up_to_a_whole_minute(self) -> None:
        queue = _queue(FakeCollection(remaining=(1, 0, 0)), 10.0, 61.0)
        self.assertEqual(queue.estimated_duration_seconds, 120)

    def test_new_remaining_obeys_ankis_scheduler_daily_limit(self) -> None:
        class MultiDeckScheduler:
            today = Scheduler.today
            day_cutoff = Scheduler.day_cutoff

            def get_queued_cards(self, *, fetch_limit):
                raise AssertionError("the active-deck queue must not cap the dashboard")

            def deck_due_tree(self):
                return due_tree_root(
                    DueTree(new=3, deck_id=1),
                    DueTree(new=7, deck_id=2),
                )

        col = FakeCollection(remaining=[(1, 40, 1, 3), (2, 40, 1, 2)])
        col.sched = MultiDeckScheduler()

        queue = _queue(col, 10.0, 20.0)

        self.assertEqual((queue.new, queue.learning, queue.review), (10, 2, 5))
        self.assertEqual(queue.total, 17)
        self.assertEqual(queue.estimated_duration_seconds, 300)

    def test_new_remaining_applies_parent_child_limits_and_exclusions_once(self) -> None:
        head_a = DueTree(
            new=8,
            deck_id=1,
            children=(
                DueTree(new=3, deck_id=11),
                DueTree(new=5, deck_id=12),
            ),
        )
        head_b = DueTree(new=6, deck_id=2)
        col = FakeCollection(remaining=[
            (1, 2, 0, 0),
            (11, 8, 0, 0),
            (12, 8, 0, 0),
            (2, 10, 0, 0),
        ])
        col.sched = Scheduler(due_tree_root(head_a, head_b))

        all_decks = _queue(col, 10.0, 10.0)
        without_child = _queue(
            col,
            10.0,
            10.0,
            FilterScope(excluded_deck_ids=(11,)),
        )

        self.assertEqual(all_decks.new, 14)
        self.assertEqual(without_child.new, 13)

    def test_new_remaining_honors_consumed_and_zero_daily_limits(self) -> None:
        col = FakeCollection(remaining=[(1, 20, 0, 0), (2, 20, 0, 0)])
        col.sched = Scheduler(due_tree_root(
            DueTree(new=2, deck_id=1),
            DueTree(new=0, deck_id=2),
        ))

        queue = _queue(col, 10.0, 10.0)

        self.assertEqual((queue.new, queue.total), (2, 2))

    def test_remaining_is_collection_wide_and_selection_invariant(self) -> None:
        class QueueAwareScheduler:
            today = Scheduler.today
            day_cutoff = Scheduler.day_cutoff

            def __init__(self) -> None:
                self.due_tree = due_tree_root(
                    DueTree(new=7, learning=5, review=9, deck_id=1),
                    DueTree(new=2, learning=1, review=3, deck_id=2),
                )

            def deck_due_tree(self):
                return self.due_tree

            def get_queued_cards(self, *, fetch_limit):
                raise AssertionError("selected-deck queue must not alter collection totals")

        col = FakeCollection(remaining=[
            (1, 7, 5, 9),
            (2, 2, 1, 3),
        ])
        col.sched = QueueAwareScheduler()
        selected = {"deck_id": 1}
        col.decks = SimpleNamespace(get_current_id=lambda: selected["deck_id"])

        first_selection = _queue(col, 10.0, 10.0)
        selected["deck_id"] = 2
        second_selection = _queue(col, 10.0, 10.0)
        without_second_deck = _queue(
            col,
            10.0,
            10.0,
            FilterScope(excluded_deck_ids=(2,)),
        )

        self.assertEqual(
            (
                first_selection.new,
                first_selection.learning,
                first_selection.review,
                first_selection.total,
            ),
            (9, 6, 12, 27),
        )
        self.assertEqual(second_selection, first_selection)
        self.assertEqual(
            (
                without_second_deck.new,
                without_second_deck.learning,
                without_second_deck.review,
                without_second_deck.total,
            ),
            (7, 5, 9, 21),
        )

    def test_due_tree_failure_makes_progress_unavailable_without_raw_fallback(self) -> None:
        class BrokenDueTreeScheduler:
            today = Scheduler.today
            day_cutoff = Scheduler.day_cutoff

            def deck_due_tree(self):
                raise RuntimeError("due tree failed")

        col = FakeCollection(remaining=[(1, 40, 0, 0)])
        col.sched = BrokenDueTreeScheduler()

        facts = collect_dashboard_facts(col, normalize_config({}), date(2026, 8, 13))

        self.assertEqual(
            (facts.queue.status, facts.queue.reason, facts.queue.value),
            (ValueStatus.UNAVAILABLE, AvailabilityReason.QUERY_FAILED, None),
        )

    def test_forecast_only_is_preserved_in_canonical_day_facts(self) -> None:
        snapshot = collect_snapshot(FakeCollection(history=[]), normalize_config({}), VerseContent())
        self.assertEqual(
            [
                (day.date, day.reviews_due.value)
                for day in snapshot.facts.days.values()
                if day.reviews_due.is_available and day.reviews_due.value
            ],
            [("2026-08-13", 3), ("2026-08-14", 4)],
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
        current = snapshot.facts.for_date("2026-08-13")
        self.assertEqual(current.date, "2026-08-13")
        self.assertEqual(current.reviews_due.value, 5)

    def test_scheduling_today_uses_cutoff_not_wall_clock_now(self) -> None:
        cutoff = int(datetime(2026, 11, 2, 4).timestamp())
        self.assertEqual(scheduling_today(cutoff), date(2026, 11, 1))

    @unittest.skipUnless(hasattr(time, "tzset"), "requires Unix timezone support")
    def test_pace_window_uses_ankis_fixed_scheduler_period_across_dst(self) -> None:
        previous = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "America/Chicago"
            time.tzset()
            cutoff = int(datetime(2026, 3, 8, 4, 0).timestamp())
            lower = pace_lower_bound(cutoff, 1)
            self.assertEqual(cutoff - lower, 24 * 3600)
        finally:
            if previous is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = previous
            time.tzset()

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

    def test_events_can_sort_case_insensitively_by_name_then_date_and_id(self) -> None:
        config = normalize_config({
            "events": {
                "sort": "name",
                "items": [
                    {"id": "z", "name": "alpha", "date": "2026-08-16", "archived": False},
                    {"id": "a", "name": "ALPHA", "date": "2026-08-15", "archived": False},
                    {"id": "b", "name": "alpha", "date": "2026-08-15", "archived": False},
                    {"id": "c", "name": "Beta", "date": "2026-08-14", "archived": False},
                ],
            }
        })

        events = _events(config, date(2026, 8, 13))

        self.assertEqual(
            [(item.name, item.date, item.event_id) for item in events],
            [
                ("ALPHA", "2026-08-15", "a"),
                ("alpha", "2026-08-15", "b"),
                ("alpha", "2026-08-16", "z"),
                ("Beta", "2026-08-14", "c"),
            ],
        )

    def test_dashboard_keeps_scheduler_today_and_civil_event_today_distinct(self) -> None:
        config = normalize_config({
            "events": {
                "items": [{
                    "id": "civil-today",
                    "name": "Civil today",
                    "date": "2026-08-14",
                    "archived": False,
                }]
            }
        })
        facts = collect_dashboard_facts(
            FakeCollection(),
            config,
            date(2026, 8, 14),
        )

        self.assertEqual(facts.scheduling_date, "2026-08-13")
        self.assertEqual(facts.calendar_date, "2026-08-14")
        self.assertEqual(facts.events.value[0].days_remaining, 0)
        self.assertEqual(facts.for_date("2026-08-13").events.value, ())
        civil_day = facts.for_date("2026-08-14")
        self.assertEqual(civil_day.relation.value, "future")
        self.assertEqual([event.name for event in civil_day.events.value], ["Civil today"])


class CanonicalFactsTests(unittest.TestCase):
    @staticmethod
    def _local_millis(year: int, month: int, day: int, hour: int, suffix: int = 0) -> int:
        return int(datetime(year, month, day, hour).timestamp() * 1000) + suffix

    @staticmethod
    def _sqlite_collection() -> SQLiteCollection:
        col = SQLiteCollection()
        col.sched.day_cutoff = int(datetime(2026, 8, 14, 4).timestamp())
        col.sched.today = 500
        return col

    def test_missing_dates_are_schema_failures_and_covered_zeroes_are_explicit(self) -> None:
        empty_target = browse_target_for_day(
            date(2026, 8, 13),
            date(2026, 8, 13),
            FilterScope(),
            (),
        )
        self.assertEqual((empty_target.kind, empty_target.query), (BrowseTargetKind.NONE, ""))

        facts = collect_dashboard_facts(
            FakeCollection(history=[], forecast=[]),
            normalize_config({
                "heatmap": {"history_days": 2, "forecast_days": 2},
                "events": {"items": [{
                    "id": "outside",
                    "name": "Outside forecast",
                    "date": "2026-08-15",
                    "archived": False,
                }]},
            }),
            date(2026, 8, 13),
        )
        self.assertTrue(facts.revision)
        self.assertTrue(facts.next_rollover)
        self.assertIn("2026-08-12", facts.days)
        historical_zero = facts.for_date("2026-08-12")
        self.assertNotIn("study_date", historical_zero.__dataclass_fields__)
        self.assertEqual(historical_zero.reviews_completed.status, ValueStatus.AVAILABLE)
        self.assertEqual(historical_zero.reviews_completed.value, 0)
        self.assertEqual(
            historical_zero.domain_state,
            DayDomainState.NO_HISTORICAL_ACTIVITY,
        )
        self.assertEqual(historical_zero.reviews_completed.reason, AvailabilityReason.NONE)
        self.assertEqual(historical_zero.browse_target.kind, BrowseTargetKind.NONE)
        self.assertEqual(historical_zero.browse_target.query, "")
        future_zero = facts.for_date("2026-08-14")
        self.assertEqual((future_zero.reviews_due.status, future_zero.reviews_due.value), (ValueStatus.AVAILABLE, 0))
        self.assertEqual(future_zero.reviews_due.reason, AvailabilityReason.NONE)
        self.assertEqual(future_zero.domain_state, DayDomainState.NO_DUE)
        self.assertEqual(future_zero.browse_target.kind, BrowseTargetKind.NONE)

        event_outside_coverage = facts.for_date("2026-08-15")
        self.assertIn("2026-08-15", facts.days)
        self.assertEqual(
            event_outside_coverage.reviews_due.reason,
            AvailabilityReason.FORECAST_OUT_OF_RANGE,
        )
        self.assertEqual(event_outside_coverage.events.value[0].name, "Outside forecast")

        missing = facts.for_date("2026-08-11")
        self.assertNotIn("2026-08-11", facts.days)
        self.assertEqual(missing.domain_state, DayDomainState.UNAVAILABLE)
        for state in (
            missing.reviews_completed,
            missing.new_cards_studied,
            missing.reviews_due,
            missing.again_count,
            missing.events,
        ):
            self.assertEqual(
                (state.status, state.reason),
                (ValueStatus.UNAVAILABLE, AvailabilityReason.QUERY_FAILED),
            )
        self.assertNotEqual(ValueState.available(0), ValueState.unavailable(AvailabilityReason.QUERY_FAILED))

    def test_unlimited_history_has_finite_coverage_and_materializes_gap_zeroes(self) -> None:
        populated = collect_dashboard_facts(
            FakeCollection(
                history=[
                    ("2026-08-11", 2, 1),
                    ("2026-08-13", 1, 0),
                ],
                forecast=[],
            ),
            normalize_config({"heatmap": {"forecast_days": 1}}),
            date(2026, 8, 13),
        )
        self.assertEqual(
            (
                populated.history_coverage.value.start,
                populated.history_coverage.value.end,
            ),
            ("2026-08-11", "2026-08-13"),
        )
        self.assertEqual(
            set(populated.days),
            {"2026-08-11", "2026-08-12", "2026-08-13"},
        )
        gap = populated.days["2026-08-12"]
        self.assertEqual(
            (gap.reviews_completed.status, gap.reviews_completed.value),
            (ValueStatus.AVAILABLE, 0),
        )
        self.assertEqual(gap.domain_state, DayDomainState.NO_HISTORICAL_ACTIVITY)

        empty = collect_dashboard_facts(
            FakeCollection(history=[], forecast=[]),
            normalize_config({"heatmap": {"forecast_days": 1}}),
            date(2026, 8, 13),
        )
        self.assertEqual(
            (
                empty.history_coverage.value.start,
                empty.history_coverage.value.end,
            ),
            ("2026-08-13", "2026-08-13"),
        )
        self.assertEqual(empty.days["2026-08-13"].reviews_completed.value, 0)

    def test_value_state_reasons_are_only_unavailability_reasons(self) -> None:
        self.assertEqual(
            {reason.value for reason in AvailabilityReason if reason != AvailabilityReason.NONE},
            {
                "query_failed",
                "history_out_of_range",
                "forecast_disabled",
                "forecast_out_of_range",
            },
        )
        with self.assertRaises(ValueError):
            ValueState(ValueStatus.AVAILABLE, 0, AvailabilityReason.QUERY_FAILED)

        sparse = DashboardFacts(scheduling_date="2026-08-13", calendar_date="2026-08-13")
        missing_day = sparse.for_date("2026-08-13")
        self.assertEqual(missing_day.domain_state, DayDomainState.UNAVAILABLE)
        self.assertEqual(missing_day.reviews_completed.reason, AvailabilityReason.QUERY_FAILED)
        self.assertEqual(missing_day.reviews_due.reason, AvailabilityReason.QUERY_FAILED)
        self.assertEqual(missing_day.events.reason, AvailabilityReason.QUERY_FAILED)

    def test_early_morning_boundary_uses_active_scheduler_day_and_future_cutoff(self) -> None:
        col = self._sqlite_collection()
        col.sched.day_cutoff = int(datetime(2026, 8, 15, 4).timestamp())
        before = collect_dashboard_facts(col, normalize_config({}), date(2026, 8, 15))
        self.assertEqual(before.scheduling_date, "2026-08-14")
        simulated_now = datetime(2026, 8, 15, 3, 30).astimezone()
        self.assertGreater(datetime.fromisoformat(before.next_rollover), simulated_now)

        col.sched.day_cutoff = int(datetime(2026, 8, 16, 4).timestamp())
        col.sched.today += 1
        after = collect_dashboard_facts(col, normalize_config({}), date(2026, 8, 15))
        self.assertEqual(after.scheduling_date, "2026-08-15")
        self.assertNotEqual(after.revision, before.revision)

    def test_unavailable_snapshot_has_no_legacy_error_or_false_available_section(self) -> None:
        snapshot = unavailable_snapshot(
            VerseContent("Body", "Ref"),
            scheduling_date="2026-08-13",
            day_cutoff_iso="2026-08-14T04:00-05:00",
            revision="failed-1",
        )
        self.assertEqual(set(snapshot.__dataclass_fields__), {"facts", "verse"})
        self.assertEqual(snapshot.facts.revision, "failed-1")
        self.assertEqual(snapshot.facts.next_rollover, "2026-08-14T04:00-05:00")
        for state in (
            snapshot.facts.today,
            snapshot.facts.queue,
            snapshot.facts.buried,
            snapshot.facts.events,
            snapshot.facts.long_term,
            snapshot.facts.history_coverage,
            snapshot.facts.forecast_coverage,
        ):
            self.assertEqual((state.status, state.reason), (ValueStatus.UNAVAILABLE, AvailabilityReason.QUERY_FAILED))
        day = snapshot.facts.for_date("2026-08-13")
        self.assertEqual(day.domain_state, DayDomainState.UNAVAILABLE)
        self.assertEqual(day.reviews_completed.reason, AvailabilityReason.QUERY_FAILED)

    def test_one_scope_filters_today_consistency_calendar_and_browse(self) -> None:
        col = self._sqlite_collection()
        col.db.connection.executemany(
            "INSERT INTO cards (id, did, queue, due, type) VALUES (?, ?, ?, ?, ?)",
            [(1, 1, 2, 500, 2), (2, 2, 2, 500, 2), (3, 1, 2, 500, 2)],
        )
        col.db.connection.executemany(
            "INSERT INTO revlog (id, cid, ease, type, lastIvl, time) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (self._local_millis(2026, 8, 13, 9, 1), 1, 3, 0, 0, 1_000),
                (self._local_millis(2026, 8, 13, 10, 2), 2, 3, 0, 0, 7_000),
                (self._local_millis(2026, 8, 13, 11, 3), 1, 3, 4, 0, 9_000),
                (self._local_millis(2026, 8, 13, 12, 4), 999, 1, 1, 1, 11_000),
                (self._local_millis(2026, 8, 12, 9, 5), 2, 3, 1, 1, 13_000),
                (self._local_millis(2026, 8, 12, 10, 6), 1, 3, 1, 1, 17_000),
            ],
        )
        config = normalize_config({"heatmap": {
            "excluded_deck_ids": [2],
            "exclude_deleted_cards": True,
            "exclude_manual_reschedules": True,
            "ignore_before": "2026-08-13",
        }})
        facts = collect_dashboard_facts(col, config, date(2026, 8, 13))
        current = facts.for_date("2026-08-13")
        self.assertEqual(facts.filter_scope.excluded_deck_ids, (2,))
        self.assertEqual(facts.filter_scope.ignore_before, "2026-08-13")
        self.assertEqual((current.reviews_completed.value, current.new_cards_studied.value), (1, 1))
        self.assertEqual((facts.today.value.answers, facts.today.value.new_cards_studied), (1, 1))
        self.assertEqual(facts.today.value.seconds, 1.0)
        self.assertEqual(facts.long_term.value.current_streak, 1)
        self.assertEqual(current.browse_target.card_ids, (1,))
        self.assertEqual(current.browse_target.query, "cid:1")
        self.assertTrue(current.browse_target.exact)

    def test_progress_uses_native_learning_and_review_queue_categories(self) -> None:
        col = self._sqlite_collection()
        col.sched.due_tree = due_tree_root(
            DueTree(new=2, learning=4, review=1)
        )
        col.db.connection.executemany(
            "INSERT INTO cards (id, did, queue, due, type) VALUES (?, ?, ?, ?, ?)",
            [
                (1, 1, 2, 490, 2),
                (2, 1, 3, 500, 3),
                (3, 1, -2, 500, 2),
                (4, 1, -1, 500, 2),
                (5, 2, 2, 500, 2),
                (6, 1, 2, 501, 2),
                (7, 1, 3, 500, 1),
                (8, 1, 3, 501, 1),
                (9, 1, 0, 100, 0),
                (10, 1, 1, col.sched.day_cutoff - 1, 1),
                (11, 1, 1, col.sched.day_cutoff - 1, 3),
                (12, 2, 1, col.sched.day_cutoff - 1, 3),
            ],
        )
        facts = collect_dashboard_facts(
            col,
            normalize_config({"heatmap": {"excluded_deck_ids": [2]}}),
            date(2026, 8, 13),
        )
        current = facts.for_date("2026-08-13")
        tomorrow = facts.for_date("2026-08-14")
        self.assertEqual(current.reviews_due.value, 5)
        self.assertEqual(current.browse_target.kind, BrowseTargetKind.DUE)
        self.assertEqual(current.browse_target.card_ids, (1, 2, 7, 10, 11))
        self.assertTrue(current.browse_target.exact)
        self.assertEqual((tomorrow.reviews_due.value, tomorrow.browse_target.card_ids), (2, (6, 8)))
        self.assertEqual((facts.queue.value.new, facts.queue.value.learning), (1, 4))
        self.assertEqual(facts.queue.value.review, 1)
        self.assertEqual(facts.queue.value.total, 6)
        self.assertEqual(tomorrow.browse_target.query, "cid:6,8")
        self.assertEqual(tomorrow.browse_target.kind, BrowseTargetKind.FUTURE_DUE)
        self.assertTrue(tomorrow.browse_target.exact)

        disabled = collect_dashboard_facts(
            col,
            normalize_config({"heatmap": {
                "excluded_deck_ids": [2],
                "show_due_forecast": False,
            }}),
            date(2026, 8, 13),
        )
        self.assertEqual(disabled.for_date("2026-08-13").reviews_due.value, 5)
        self.assertEqual(disabled.queue.value.review, 1)
        self.assertEqual(
            disabled.for_date("2026-08-14").reviews_due.reason,
            AvailabilityReason.QUERY_FAILED,
        )

    def test_forecast_failure_does_not_hide_scheduler_progress(self) -> None:
        class ForecastFailureDB(FakeDB):
            def all(self, sql, *args):
                if "SELECT id, type, queue, due, odue, odid FROM cards" in sql:
                    raise RuntimeError("scheduled demand unavailable")
                return super().all(sql, *args)

        col = FakeCollection(due_tree=DueTree(3, 2, 1))
        col.db = ForecastFailureDB()
        facts = collect_dashboard_facts(col, normalize_config({}), date(2026, 8, 13))

        self.assertEqual(
            (facts.forecast_coverage.status, facts.forecast_coverage.reason),
            (ValueStatus.UNAVAILABLE, AvailabilityReason.QUERY_FAILED),
        )
        self.assertEqual(
            facts.for_date(facts.scheduling_date).reviews_due.status,
            ValueStatus.UNAVAILABLE,
        )
        self.assertEqual(
            (
                facts.queue.status,
                facts.queue.value.new,
                facts.queue.value.learning,
                facts.queue.value.review,
                facts.queue.value.total,
            ),
            (ValueStatus.AVAILABLE, 3, 2, 1, 6),
        )

    def test_incomplete_scheduler_tree_makes_remaining_counts_unavailable(self) -> None:
        incomplete_tree = SimpleNamespace(
            deck_id=1,
            new_count=2,
            learn_count=1,
            children=(),
        )
        col = FakeCollection(due_tree=incomplete_tree)
        facts = collect_dashboard_facts(col, normalize_config({}), date(2026, 8, 13))

        self.assertEqual(
            (facts.queue.status, facts.queue.reason),
            (ValueStatus.UNAVAILABLE, AvailabilityReason.QUERY_FAILED),
        )
        self.assertEqual(facts.for_date(facts.scheduling_date).reviews_due.value, 3)

    def test_deck_exclusions_scope_every_collection_backed_consumer(self) -> None:
        col = self._sqlite_collection()
        col.db.connection.executemany(
            "INSERT INTO cards (id, did, queue, due, type) VALUES (?, ?, ?, ?, ?)",
            [
                (1, 1, 0, 100, 0),
                (2, 1, 1, 0, 1),
                (3, 1, 3, 500, 1),
                (4, 1, 2, 499, 2),
                (5, 1, 3, 500, 3),
                (6, 1, 2, 501, 2),
                (7, 1, -2, 0, 0),
                (8, 1, -3, 0, 3),
                (9, 1, -2, 0, 2),
                (10, 1, -1, 500, 2),
                (11, 2, 0, 100, 0),
                (12, 2, 1, 0, 1),
                (13, 2, 3, 500, 1),
                (14, 2, 2, 499, 2),
                (15, 2, 3, 500, 3),
                (16, 2, 2, 501, 2),
                (17, 2, -2, 0, 0),
                (18, 2, -3, 0, 3),
                (19, 2, -2, 0, 2),
            ],
        )
        col.db.connection.executemany(
            "INSERT INTO revlog (id, cid, ease, type, lastIvl, time) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (self._local_millis(2026, 8, 13, 9, 1), 1, 3, 0, 0, 1_000),
                (self._local_millis(2026, 8, 13, 10, 2), 4, 1, 1, 1, 2_000),
                (self._local_millis(2026, 8, 13, 11, 3), 11, 3, 0, 0, 4_000),
                (self._local_millis(2026, 8, 13, 12, 4), 14, 1, 1, 1, 8_000),
            ],
        )
        config = normalize_config({"heatmap": {"excluded_deck_ids": [2]}})

        def filtered_facts():
            return collect_dashboard_facts(col, config, date(2026, 8, 13))

        facts = filtered_facts()
        current = facts.for_date("2026-08-13")
        future = facts.for_date("2026-08-14")
        self.assertEqual(facts.filter_scope.excluded_deck_ids, (2,))
        self.assertEqual(
            (current.reviews_completed.value, current.new_cards_studied.value, current.again_count.value),
            (2, 1, 1),
        )
        self.assertEqual(
            (facts.today.value.answers, facts.today.value.new_cards_studied, facts.today.value.seconds),
            (2, 1, 3.0),
        )
        self.assertEqual(facts.long_term.value.current_streak, 1)
        self.assertEqual(current.browse_target.card_ids, (1, 4))
        self.assertFalse({11, 14}.intersection(current.browse_target.card_ids))
        self.assertEqual(current.reviews_due.value, 4)
        self.assertEqual((future.reviews_due.value, future.browse_target.card_ids), (1, (6,)))
        self.assertNotIn(3, current.browse_target.card_ids)
        self.assertFalse({13, 16}.intersection(future.browse_target.card_ids))
        self.assertEqual(
            (
                facts.queue.value.new,
                facts.queue.value.learning,
                facts.queue.value.review,
                facts.queue.value.total,
            ),
            (1, 3, 1, 5),
        )
        self.assertEqual(
            (facts.buried.value.new, facts.buried.value.learning, facts.buried.value.review),
            (1, 1, 1),
        )

        unfiltered = collect_dashboard_facts(col, normalize_config({}), date(2026, 8, 13))
        self.assertNotEqual(
            unfiltered.for_date("2026-08-13").reviews_completed,
            current.reviews_completed,
        )
        self.assertNotEqual(unfiltered.today, facts.today)
        self.assertNotEqual(unfiltered.queue, facts.queue)
        self.assertNotEqual(unfiltered.buried, facts.buried)
        self.assertNotEqual(unfiltered.long_term, facts.long_term)

        settings_snapshot = collect_snapshot(col, config, VerseContent())
        self.assertEqual(settings_snapshot.facts.filter_scope, facts.filter_scope)
        self.assertEqual(settings_snapshot.facts.today.value, facts.today.value)
        self.assertEqual(settings_snapshot.facts.queue.value, facts.queue.value)
        self.assertEqual(settings_snapshot.facts.buried.value, facts.buried.value)
        self.assertEqual(
            settings_snapshot.facts.for_date("2026-08-14").browse_target.card_ids,
            (6,),
        )

        mutation_expectations = (
            ("bury", -2, 3, 0, 2),
            ("unbury", 2, 4, 1, 1),
            ("suspend", -1, 3, 0, 1),
            ("unsuspend", 2, 4, 1, 1),
        )
        for label, queue, due_count, queue_review, buried_review in mutation_expectations:
            with self.subTest(mutation=label):
                col.db.connection.execute("UPDATE cards SET queue = ? WHERE id = 4", (queue,))
                updated = filtered_facts()
                self.assertEqual(updated.for_date("2026-08-13").reviews_due.value, due_count)
                self.assertEqual(updated.queue.value.review, queue_review)
                self.assertEqual(updated.buried.value.review, buried_review)

        col.db.connection.execute("UPDATE cards SET queue = -2 WHERE id = 6")
        future_buried = filtered_facts()
        self.assertEqual(future_buried.for_date("2026-08-14").reviews_due.value, 1)
        self.assertEqual(future_buried.for_date("2026-08-14").browse_target.card_ids, (6,))
        col.db.connection.execute("UPDATE cards SET queue = 2 WHERE id = 6")
        future_unburied = filtered_facts()
        self.assertEqual(future_unburied.for_date("2026-08-14").reviews_due.value, 1)
        self.assertEqual(future_unburied.for_date("2026-08-14").browse_target.card_ids, (6,))

    def test_filtered_deck_original_ids_and_preview_queue_obey_the_same_scope(self) -> None:
        col = self._sqlite_collection()
        col.db.connection.executemany(
            "INSERT INTO cards (id, did, queue, due, type, odid, odue) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, 99, 0, 100, 0, 2, 100),
                (2, 99, 1, col.sched.day_cutoff - 1, 1, 2, col.sched.day_cutoff - 1),
                (3, 99, 2, 500, 2, 2, 500),
                (4, 99, -2, 500, 3, 2, 500),
                (5, 99, 0, 100, 0, 1, 100),
                (6, 99, 1, col.sched.day_cutoff - 1, 1, 1, col.sched.day_cutoff - 1),
                (7, 99, 2, 500, 0, 1, 500),
                (8, 99, -2, 500, 3, 1, 500),
                (9, 99, 4, col.sched.day_cutoff - 1, 1, 1, col.sched.day_cutoff - 1),
                (10, 99, 4, col.sched.day_cutoff - 1, 3, 1, col.sched.day_cutoff - 1),
                (11, 2, 0, 100, 0, 1, 100),
                (12, 99, 2, 501, 2, 2, 501),
                (13, 99, 2, 501, 2, 1, 501),
                (14, 99, 1, col.sched.day_cutoff - 1, 3, 2, col.sched.day_cutoff - 1),
                (15, 99, 1, col.sched.day_cutoff - 1, 3, 1, col.sched.day_cutoff - 1),
            ],
        )
        col.db.connection.executemany(
            "INSERT INTO revlog (id, cid, ease, type, lastIvl, time) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (self._local_millis(2026, 8, 13, 9, 1), 3, 3, 1, 1, 2_000),
                (self._local_millis(2026, 8, 13, 10, 2), 7, 3, 1, 1, 3_000),
            ],
        )

        facts = collect_dashboard_facts(
            col,
            normalize_config({"heatmap": {"excluded_deck_ids": [2]}}),
            date(2026, 8, 13),
        )
        current = facts.for_date(facts.scheduling_date)
        future = facts.for_date("2026-08-14")

        self.assertEqual(current.reviews_completed.value, 1)
        self.assertEqual(current.browse_target.card_ids, (7,))
        self.assertEqual(facts.today.value.answers, 1)
        self.assertEqual(facts.today.value.seconds, 3.0)
        self.assertEqual(current.reviews_due.value, 4)
        self.assertEqual(future.reviews_due.value, 1)
        self.assertEqual(future.browse_target.card_ids, (13,))
        self.assertNotIn(12, future.browse_target.card_ids)
        self.assertEqual(
            (
                facts.queue.value.new,
                facts.queue.value.learning,
                facts.queue.value.review,
                facts.queue.value.total,
            ),
            (1, 4, 1, 6),
        )
        self.assertEqual(
            facts.queue.value.total,
            facts.queue.value.new
            + facts.queue.value.learning
            + facts.queue.value.review,
        )
        self.assertEqual(
            (facts.buried.value.new, facts.buried.value.learning, facts.buried.value.review),
            (0, 1, 0),
        )

    def test_live_mutation_recompute_table(self) -> None:
        col = self._sqlite_collection()
        col.sched.due_tree = due_tree_root(DueTree(0, 0, 1))
        col.db.connection.execute(
            "INSERT INTO cards (id, did, queue, due, type) VALUES (1, 1, 2, 500, 2)"
        )
        config = normalize_config({})

        def current_facts():
            dashboard = collect_dashboard_facts(col, config, date(2026, 8, 13))
            return dashboard, dashboard.for_date(dashboard.scheduling_date)

        dashboard, current = current_facts()
        self.assertEqual((current.reviews_due.value, dashboard.queue.value.review), (1, 1))
        queue_mutations = (
            ("bury", -2, 0),
            ("unbury", 2, 1),
            ("suspend", -1, 0),
            ("unsuspend", 2, 1),
        )
        for label, queue, expected in queue_mutations:
            with self.subTest(mutation=label):
                col.db.connection.execute("UPDATE cards SET queue = ? WHERE id = 1", (queue,))
                col.sched.due_tree.review_count = expected
                dashboard, current = current_facts()
                self.assertEqual((current.reviews_due.value, dashboard.queue.value.review), (expected, expected))

        col.db.connection.execute(
            "INSERT INTO revlog (id, cid, ease, type, lastIvl, time) VALUES (?, 1, 3, 0, 0, 1000)",
            (self._local_millis(2026, 8, 13, 9, 1),),
        )
        dashboard, current = current_facts()
        self.assertEqual((current.reviews_completed.value, current.new_cards_studied.value), (1, 1))
        self.assertEqual(current.domain_state, DayDomainState.NO_AGAIN)
        self.assertEqual(dashboard.long_term.value.current_streak, 1)

        col.db.connection.execute(
            "INSERT INTO revlog (id, cid, ease, type, lastIvl, time) VALUES (?, 1, 1, 1, 1, 1000)",
            (self._local_millis(2026, 8, 13, 10, 2),),
        )
        dashboard, current = current_facts()
        self.assertEqual((current.reviews_completed.value, current.again_count.value), (2, 1))
        self.assertEqual(current.domain_state, DayDomainState.TROUBLE)

        col.sched.day_cutoff = int(datetime(2026, 8, 15, 4).timestamp())
        col.sched.today = 501
        dashboard, current = current_facts()
        self.assertEqual(dashboard.scheduling_date, "2026-08-14")
        self.assertEqual(current.reviews_completed.value, 0)
        self.assertEqual(dashboard.for_date("2026-08-13").reviews_completed.value, 2)
        self.assertEqual(dashboard.long_term.value.current_streak, 1)

        col.db.connection.execute(
            "INSERT INTO revlog (id, cid, ease, type, lastIvl, time) VALUES (?, 1, 3, 1, 1, 1000)",
            (self._local_millis(2026, 8, 14, 9, 3),),
        )
        dashboard, current = current_facts()
        self.assertEqual(current.reviews_completed.value, 1)
        self.assertEqual(dashboard.long_term.value.current_streak, 2)


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

    def test_buried_counts_only_new_or_due_cards_in_both_explicit_queue_kinds(self) -> None:
        col = SQLiteCollection()
        rows = [
            (1, 1, -2, 0, 0),
            (2, 1, -3, 0, 0),
            (3, 1, -2, col.sched.today, 1),
            (4, 1, -3, col.sched.day_cutoff - 1, 3),
            (5, 1, -2, col.sched.today, 2),
            (6, 1, -1, 0, 0),
            (7, 1, 2, 0, 2),
            (8, 1, -2, col.sched.today + 1, 1),
            (9, 1, -3, col.sched.day_cutoff + 1, 3),
            (10, 1, -2, col.sched.today + 1, 2),
        ]
        col.db.connection.executemany(
            "INSERT INTO cards (id, did, queue, due, type) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        stats = _buried(col)
        self.assertEqual((stats.new, stats.learning, stats.review), (2, 2, 1))

    def test_buried_does_not_infer_transient_queue_hidden_cards(self) -> None:
        class QueueAwareScheduler:
            today = 500
            day_cutoff = int(datetime(2026, 8, 14, 4).timestamp())

            def deck_due_tree(self, deck_id):
                raise AssertionError("buried totals must not inspect the due tree")

            def get_queued_cards(self, *, fetch_limit):
                raise AssertionError("buried totals must not inspect the built queue")

        col = SQLiteCollection()
        col.sched = QueueAwareScheduler()
        col.decks = SimpleNamespace(get_current_id=lambda: 1)
        col.db.connection.executemany(
            "INSERT INTO cards (id, did, queue, due, type) VALUES (?, ?, ?, ?, ?)",
            [
                (1, 1, -2, 0, 0),
                (2, 1, -3, col.sched.day_cutoff - 1, 1),
                (3, 1, -2, col.sched.today, 2),
            ],
        )

        stats = _buried(col)

        self.assertEqual((stats.new, stats.learning, stats.review), (1, 1, 1))

    def test_buried_uses_sql_only_when_dashboard_deck_exclusions_are_active(self) -> None:
        class QueueAwareScheduler:
            today = 500
            day_cutoff = int(datetime(2026, 8, 14, 4).timestamp())

            def deck_due_tree(self, _deck_id):
                raise AssertionError("unscoped scheduler counts must not be used")

            def get_queued_cards(self, *, fetch_limit):
                raise AssertionError("unscoped scheduler counts must not be used")

        col = SQLiteCollection()
        col.sched = QueueAwareScheduler()
        col.decks = SimpleNamespace(get_current_id=lambda: 1)
        col.db.connection.execute(
            "INSERT INTO cards (id, did, queue, due, type) VALUES (1, 1, -2, 0, 0)"
        )

        stats = _buried(col, FilterScope(excluded_deck_ids=(2,)))

        self.assertEqual((stats.new, stats.learning, stats.review), (1, 0, 0))


if __name__ == "__main__":
    unittest.main()
