from __future__ import annotations

from datetime import date
import unittest

from home_dashboard_overhaul.calendar_manager_model import (
    CalendarManagerRangeError,
    eligible_for_action,
    filter_occurrences,
    manager_date_range,
)
from home_dashboard_overhaul.calendar_models import CalendarOccurrence


class CalendarManagerModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.today = date(2026, 8, 13)
        self.local = CalendarOccurrence(
            "local-1", "Local exam", "2026-08-20", "2026-08-21",
            "local", "Local", "local-1", True,
        )
        self.archived = CalendarOccurrence(
            "local-2", "Past local", "2026-08-01", "2026-08-02",
            "local", "Local", "local-2", True, True,
        )
        self.external = CalendarOccurrence(
            "remote-1", "Rounds", "2026-08-21", "2026-08-22",
            "source-a", "Clerkship", "uid-a", False,
        )
        self.hidden = CalendarOccurrence(
            "remote-2", "Hidden rounds", "2026-08-22", "2026-08-23",
            "source-a", "Clerkship", "uid-b", False, False, True,
        )

    def test_default_and_named_ranges_are_bounded_and_end_exclusive(self) -> None:
        self.assertEqual(
            manager_date_range("upcoming", self.today),
            (date(2026, 8, 13), date(2027, 8, 13)),
        )
        self.assertEqual(
            manager_date_range("month", self.today),
            (date(2026, 8, 1), date(2026, 9, 1)),
        )
        self.assertEqual(
            manager_date_range("year", self.today),
            (date(2026, 1, 1), date(2027, 1, 1)),
        )
        self.assertEqual(
            manager_date_range("past", self.today),
            (date(2025, 8, 13), date(2026, 8, 13)),
        )
        self.assertEqual(
            manager_date_range("custom", self.today, date(2026, 8, 20), date(2026, 8, 20)),
            (date(2026, 8, 20), date(2026, 8, 21)),
        )
        with self.assertRaises(CalendarManagerRangeError):
            manager_date_range("custom", self.today, date(2000, 1, 1), date(2020, 1, 1))

    def test_upcoming_past_hidden_search_and_source_filters(self) -> None:
        values = [self.local, self.archived, self.external, self.hidden]
        upcoming = filter_occurrences(values, view="upcoming", today=self.today)
        self.assertEqual([value.occurrence_id for value in upcoming], ["local-1", "remote-1"])
        past = filter_occurrences(values, view="past", today=self.today)
        self.assertEqual([value.occurrence_id for value in past], ["local-2"])
        hidden = filter_occurrences(values, view="hidden", today=self.today)
        self.assertEqual([value.occurrence_id for value in hidden], ["remote-2"])
        searched = filter_occurrences(
            values, view="upcoming", today=self.today, source_id="source-a", search="clerkship"
        )
        self.assertEqual([value.occurrence_id for value in searched], ["remote-1"])

    def test_local_and_external_actions_never_cross_ownership(self) -> None:
        values = [self.local, self.external, self.hidden]
        for action in ("duplicate", "archive", "restore", "delete"):
            eligible, skipped = eligible_for_action(values, action)
            self.assertEqual(eligible, [self.local])
            self.assertEqual(skipped, 2)
        for action in ("hide", "unhide", "refresh"):
            eligible, skipped = eligible_for_action(values, action)
            self.assertEqual(eligible, [self.external, self.hidden])
            self.assertEqual(skipped, 1)
        self.assertEqual(eligible_for_action([self.local], "edit"), ([self.local], 0))
        self.assertEqual(eligible_for_action([self.external], "edit"), ([], 1))
        self.assertEqual(eligible_for_action([self.external], "manage"), ([self.external], 0))
        self.assertEqual(eligible_for_action([self.external, self.hidden], "manage"), ([], 2))


if __name__ == "__main__":
    unittest.main()
