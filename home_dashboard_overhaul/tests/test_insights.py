from __future__ import annotations

from datetime import date, datetime
import os
import sqlite3
import time
import unittest

from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.insights import MAX_PROMPT_CHARACTERS, collect_day_insight


class SQLiteDB:
    def __init__(self, connection=None) -> None:
        self.connection = connection or sqlite3.connect(":memory:")
        if connection is None:
            self.connection.executescript(
                "CREATE TABLE revlog (id INTEGER PRIMARY KEY, cid INTEGER, ease INTEGER, "
                "type INTEGER, lastIvl INTEGER, time INTEGER);"
                "CREATE TABLE cards (id INTEGER PRIMARY KEY, did INTEGER, queue INTEGER, "
                "due INTEGER, type INTEGER);"
            )

    def first(self, sql, *args):
        return self.connection.execute(sql, args).fetchone()

    def all(self, sql, *args):
        return self.connection.execute(sql, args).fetchall()


class BrokenDB:
    def first(self, _sql, *_args):
        raise RuntimeError("query failed")

    def all(self, _sql, *_args):
        raise RuntimeError("query failed")


class Scheduler:
    def __init__(self, day_cutoff: int, today: int = 500) -> None:
        self.day_cutoff = day_cutoff
        self.today = today


class Note:
    def __init__(self, fields) -> None:
        self.fields = list(fields)


class Card:
    def __init__(self, card_id: int, deck_id: int, question: str, fields=()) -> None:
        self.id = card_id
        self.did = deck_id
        self._question = question
        self._note = Note(fields)

    def question(self):
        return self._question

    def note(self):
        return self._note

    def current_deck_id(self):
        return self.did


class Decks:
    def __init__(self, names=None, children=None) -> None:
        self.names = dict(names or {})
        self.child_map = dict(children or {})

    def children(self, deck_id):
        return [(self.names.get(child, ""), child) for child in self.child_map.get(deck_id, [])]

    def name_if_exists(self, deck_id):
        return self.names.get(deck_id)

    def get(self, deck_id):
        name = self.names.get(deck_id)
        return {"name": name} if name else None


class Collection:
    def __init__(self, db=None, cards=None, decks=None, day_cutoff=None, scheduler_today=500) -> None:
        self.db = db or SQLiteDB()
        self.cards = dict(cards or {})
        self.decks = decks or Decks()
        cutoff = day_cutoff if day_cutoff is not None else local_seconds(2026, 8, 14, 4)
        self.sched = Scheduler(cutoff, scheduler_today)

    def get_card(self, card_id):
        return self.cards[card_id]


def local_seconds(year: int, month: int, day: int, hour: int, minute: int = 0) -> int:
    local_zone = datetime.now().astimezone().tzinfo
    return int(datetime(year, month, day, hour, minute, tzinfo=local_zone).timestamp())


def revlog_id(day: int, hour: int, minute: int = 0, suffix: int = 0, month: int = 8, year: int = 2026) -> int:
    return local_seconds(year, month, day, hour, minute) * 1000 + suffix


def add_card(col: Collection, card: Card, queue=2, due=500, card_type=2) -> None:
    col.cards[card.id] = card
    col.db.connection.execute(
        "INSERT INTO cards (id, did, queue, due, type) VALUES (?, ?, ?, ?, ?)",
        (card.id, card.did, queue, due, card_type),
    )


def add_answer(col: Collection, answer_id: int, card_id: int, ease: int, answer_type: int = 1) -> None:
    col.db.connection.execute(
        "INSERT INTO revlog (id, cid, ease, type, lastIvl, time) VALUES (?, ?, ?, ?, 1, 1000)",
        (answer_id, card_id, ease, answer_type),
    )


class HistoricalInsightTests(unittest.TestCase):
    scheduling_date = date(2026, 8, 13)
    calendar_today = date(2026, 8, 13)

    def test_full_day_ranking_filters_again_and_sanitizes_prompts(self) -> None:
        decks = Decks({1: "Medicine::Alpha", 2: "Medicine::Beta", 3: "Medicine::Gamma"})
        col = Collection(decks=decks)
        add_card(col, Card(10, 1, '<img src="x">', ["<b>Field fallback</b>"]))
        add_card(col, Card(20, 2, "<div>Question <b>twenty</b> [sound:x.mp3] [anki:play:q:0]</div>"))
        add_card(col, Card(30, 3, "[sound:q.mp3]", ["<img src=x>"]))
        add_card(col, Card(40, 1, "Hard is not a miss"))
        for raw in (
            (revlog_id(13, 9, suffix=1), 10, 1),
            (revlog_id(13, 11, suffix=2), 10, 1),
            (revlog_id(13, 10, suffix=3), 20, 1),
            (revlog_id(13, 12, suffix=4), 20, 1),
            (revlog_id(13, 13, suffix=5), 30, 1),
            (revlog_id(13, 14, suffix=6), 40, 2),
        ):
            add_answer(col, *raw)

        insight = collect_day_insight(
            col,
            normalize_config({}),
            self.calendar_today,
            self.scheduling_date,
            self.calendar_today,
        )

        self.assertEqual(insight.valid_answer_count, 6)
        self.assertEqual(insight.again_count, 5)
        self.assertEqual([item.count for item in insight.items], [2, 2, 1])
        self.assertEqual(
            [item.primary_text for item in insight.items],
            ["Question twenty", "Field fallback", "Media-only card 30"],
        )
        self.assertEqual(
            [item.secondary_text for item in insight.items],
            ["Medicine::Beta", "Medicine::Alpha", "Medicine::Gamma"],
        )
        self.assertEqual([item.count_label for item in insight.items], ["Again ×2", "Again ×2", "Again ×1"])
        self.assertEqual(insight.browser_query, "cid:20,10,30")
        self.assertNotIn("40", insight.browser_query)

    def test_prompt_payload_is_capped_at_160_characters(self) -> None:
        col = Collection(decks=Decks({1: "Deck"}))
        add_card(col, Card(1, 1, "x" * 300))
        add_answer(col, revlog_id(13, 9), 1, 1)
        insight = collect_day_insight(
            col, normalize_config({}), self.calendar_today, self.scheduling_date, self.calendar_today
        )
        self.assertEqual(len(insight.items[0].primary_text), MAX_PROMPT_CHARACTERS)
        self.assertTrue(insight.items[0].primary_text.endswith("…"))

    def test_multiple_sessions_and_fresh_collection_wrapper_share_full_day_revlog(self) -> None:
        first = Collection(decks=Decks({1: "Deck"}))
        add_card(first, Card(1, 1, "Persistent prompt"))
        add_answer(first, revlog_id(13, 7), 1, 1)
        add_answer(first, revlog_id(13, 19), 1, 1)
        first_result = collect_day_insight(
            first, normalize_config({}), self.calendar_today, self.scheduling_date, self.calendar_today
        )
        restarted = Collection(
            db=SQLiteDB(first.db.connection),
            cards=first.cards,
            decks=first.decks,
            day_cutoff=first.sched.day_cutoff,
        )
        restarted_result = collect_day_insight(
            restarted, normalize_config({}), self.calendar_today, self.scheduling_date, self.calendar_today
        )
        self.assertEqual(first_result.items[0].count_label, "Again ×2")
        self.assertEqual(restarted_result, first_result)

    def test_empty_and_deleted_states_are_distinct(self) -> None:
        empty = Collection()
        current = collect_day_insight(
            empty, normalize_config({}), self.calendar_today, self.scheduling_date, self.calendar_today
        )
        past = collect_day_insight(
            empty, normalize_config({}), date(2026, 8, 12), self.scheduling_date, self.calendar_today
        )
        self.assertEqual((current.empty_reason, current.browse_action), ("today_no_answers", "today"))
        self.assertEqual(current.browser_query, "(prop:rated=0 or prop:due=0)")
        self.assertEqual((past.empty_reason, past.browse_action, past.browser_query), ("past_no_answers", "none", ""))

        studied = Collection(decks=Decks({1: "Deck"}))
        add_card(studied, Card(1, 1, "Known"))
        add_answer(studied, revlog_id(13, 9), 1, 3)
        no_misses = collect_day_insight(
            studied, normalize_config({}), self.calendar_today, self.scheduling_date, self.calendar_today
        )
        self.assertEqual((no_misses.valid_answer_count, no_misses.again_count), (1, 0))
        self.assertEqual((no_misses.empty_reason, no_misses.browse_action), ("no_again", "today"))

        deleted = Collection()
        add_answer(deleted, revlog_id(13, 9), 999, 1)
        deleted_result = collect_day_insight(
            deleted, normalize_config({}), self.calendar_today, self.scheduling_date, self.calendar_today
        )
        self.assertEqual((deleted_result.valid_answer_count, deleted_result.again_count), (1, 1))
        self.assertEqual(deleted_result.empty_reason, "deleted_misses")
        self.assertEqual(deleted_result.items, [])

    def test_exclusions_manual_reschedules_and_deleted_preference_are_honored(self) -> None:
        decks = Decks(
            {1: "Included", 2: "Excluded", 3: "Excluded::Child"},
            {2: [3]},
        )
        col = Collection(decks=decks)
        for card_id, deck_id in ((1, 1), (2, 2), (3, 3)):
            add_card(col, Card(card_id, deck_id, "Card {}".format(card_id)))
        add_answer(col, revlog_id(13, 8, suffix=1), 1, 1)
        add_answer(col, revlog_id(13, 9, suffix=2), 2, 1)
        add_answer(col, revlog_id(13, 10, suffix=3), 3, 1)
        add_answer(col, revlog_id(13, 11, suffix=4), 1, 1, 4)
        config = normalize_config({"heatmap": {"excluded_deck_ids": [2]}})
        insight = collect_day_insight(
            col, config, self.calendar_today, self.scheduling_date, self.calendar_today
        )
        self.assertEqual((insight.valid_answer_count, insight.again_count), (1, 1))
        self.assertEqual(insight.browser_query, "cid:1")

        included_manual = collect_day_insight(
            col,
            normalize_config({"heatmap": {
                "excluded_deck_ids": [2],
                "exclude_manual_reschedules": False,
            }}),
            self.calendar_today,
            self.scheduling_date,
            self.calendar_today,
        )
        self.assertEqual((included_manual.valid_answer_count, included_manual.again_count), (2, 2))

        deleted = Collection()
        add_answer(deleted, revlog_id(13, 12), 99, 1)
        hidden = collect_day_insight(
            deleted,
            normalize_config({"heatmap": {"exclude_deleted_cards": True}}),
            self.calendar_today,
            self.scheduling_date,
            self.calendar_today,
        )
        self.assertEqual(hidden.empty_reason, "today_no_answers")

    def test_history_limit_and_query_failure_return_non_ambiguous_states(self) -> None:
        outside = collect_day_insight(
            Collection(),
            normalize_config({"heatmap": {"history_days": 2}}),
            date(2026, 8, 10),
            self.scheduling_date,
            self.calendar_today,
        )
        self.assertEqual(outside.empty_reason, "history_out_of_range")
        failed = Collection()
        failed.db = BrokenDB()
        unavailable = collect_day_insight(
            failed, normalize_config({}), self.calendar_today, self.scheduling_date, self.calendar_today
        )
        self.assertEqual((unavailable.insight_kind, unavailable.empty_reason), ("unavailable", "unavailable"))

    def test_rollover_assigns_answers_to_the_complete_anki_day(self) -> None:
        col = Collection(decks=Decks({1: "Deck"}))
        add_card(col, Card(1, 1, "Boundary"))
        add_answer(col, revlog_id(13, 3, 59, 1), 1, 1)
        add_answer(col, revlog_id(13, 4, 0, 2), 1, 1)
        prior = collect_day_insight(
            col, normalize_config({}), date(2026, 8, 12), self.scheduling_date, self.calendar_today
        )
        current = collect_day_insight(
            col, normalize_config({}), self.calendar_today, self.scheduling_date, self.calendar_today
        )
        self.assertEqual(prior.items[0].count, 1)
        self.assertEqual(current.items[0].count, 1)

    @unittest.skipUnless(hasattr(time, "tzset"), "requires Unix timezone support")
    def test_rollover_remains_correct_across_dst(self) -> None:
        previous = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "America/Chicago"
            time.tzset()
            cutoff = local_seconds(2026, 3, 9, 4)
            col = Collection(decks=Decks({1: "Deck"}), day_cutoff=cutoff)
            add_card(col, Card(1, 1, "DST"))
            add_answer(col, revlog_id(8, 3, 30, 1, month=3), 1, 1)
            add_answer(col, revlog_id(8, 4, 30, 2, month=3), 1, 1)
            march_seven = collect_day_insight(
                col, normalize_config({}), date(2026, 3, 7), date(2026, 3, 8), date(2026, 3, 9)
            )
            march_eight = collect_day_insight(
                col, normalize_config({}), date(2026, 3, 8), date(2026, 3, 8), date(2026, 3, 9)
            )
            self.assertEqual(march_seven.items[0].count, 1)
            self.assertEqual(march_eight.items[0].count, 1)
        finally:
            if previous is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = previous
            time.tzset()


class FutureInsightTests(unittest.TestCase):
    def test_future_due_decks_are_grouped_ranked_and_excluded(self) -> None:
        decks = Decks({1: "Alpha", 2: "Beta::Child", 3: "Excluded"})
        col = Collection(decks=decks, scheduler_today=500)
        card_id = 1
        for deck_id, count in ((1, 2), (2, 4), (3, 5)):
            for _ in range(count):
                add_card(col, Card(card_id, deck_id, "Card"), due=502)
                card_id += 1
        add_card(col, Card(card_id, 1, "New"), queue=0, due=502, card_type=0)
        insight = collect_day_insight(
            col,
            normalize_config({"heatmap": {"excluded_deck_ids": [3]}}),
            date(2026, 8, 15),
            date(2026, 8, 13),
            date(2026, 8, 13),
        )
        self.assertEqual(insight.insight_kind, "future_due_decks")
        self.assertEqual([item.primary_text for item in insight.items], ["Beta::Child", "Alpha"])
        self.assertEqual([item.count_label for item in insight.items], ["4 cards due", "2 cards due"])
        self.assertEqual(insight.browse_action, "future_due")
        self.assertEqual(insight.browser_query, "prop:due=2 -did:3")

    def test_future_empty_disabled_and_out_of_range_states(self) -> None:
        selected = date(2026, 8, 15)
        scheduling = date(2026, 8, 13)
        calendar_today = date(2026, 8, 13)
        empty = collect_day_insight(
            Collection(), normalize_config({}), selected, scheduling, calendar_today
        )
        self.assertEqual((empty.empty_reason, empty.browse_action), ("no_due", "none"))
        disabled = collect_day_insight(
            Collection(),
            normalize_config({"heatmap": {"show_due_forecast": False}}),
            selected,
            scheduling,
            calendar_today,
        )
        self.assertEqual(disabled.empty_reason, "forecast_disabled")
        out_of_range = collect_day_insight(
            Collection(),
            normalize_config({"heatmap": {"forecast_days": 2}}),
            selected,
            scheduling,
            calendar_today,
        )
        self.assertEqual(out_of_range.empty_reason, "forecast_out_of_range")


if __name__ == "__main__":
    unittest.main()
