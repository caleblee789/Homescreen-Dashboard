from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
import unittest

from home_dashboard_overhaul.insights import (
    collect_day_insight,
    enrich_day_facts,
    project_day_insight,
    unavailable_day_insight,
)
from home_dashboard_overhaul.models import (
    BrowseTargetKind,
    DayDomainState,
    DayFacts,
    DayRelation,
    FilterScope,
    ValueState,
)


class FakeDB:
    def __init__(self, rows=(), error: Exception | None = None) -> None:
        self.rows = list(rows)
        self.error = error
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def all(self, sql: str, *args: object):
        self.calls.append((sql, args))
        if self.error:
            raise self.error
        return list(self.rows)


class FakeCollection:
    def __init__(self, rows=(), error: Exception | None = None) -> None:
        self.db = FakeDB(rows, error)
        self.sched = SimpleNamespace(
            day_cutoff=int(datetime(2026, 8, 18, 4).timestamp()),
            today=600,
        )


def historical_facts(again: int = 4) -> DayFacts:
    return DayFacts(
        date="2026-08-17",
        scheduling_date="2026-08-17",
        relation=DayRelation.CURRENT,
        reviews_completed=ValueState.available(12),
        new_cards_studied=ValueState.available(2),
        reviews_due=ValueState.available(7),
        again_count=ValueState.available(again),
        filter_scope=FilterScope(exclude_manual_reschedules=True),
        domain_state=DayDomainState.TROUBLE if again else DayDomainState.NO_AGAIN,
    )


class MostMissedCapabilityTests(unittest.TestCase):
    def test_query_is_lazy_exact_and_uses_required_deterministic_rank(self) -> None:
        col = FakeCollection(rows=[
            (42, 5, 8),
            (7, 5, 7),
            (11, 3, 9),
        ])
        enriched = enrich_day_facts(col, {}, historical_facts())
        self.assertEqual(len(col.db.calls), 1)
        sql, _args = col.db.calls[0]
        self.assertIn("sum(CASE WHEN r.ease = 1", sql)
        self.assertIn("count(*) AS total_answers", sql)
        self.assertIn("GROUP BY r.cid", sql)
        self.assertIn("HAVING again_count > 0", sql)
        self.assertIn("ORDER BY again_count DESC, total_answers DESC, r.cid ASC", sql)
        self.assertNotIn("flds", sql)
        self.assertNotIn("notes", sql)
        self.assertNotIn("question", sql.casefold())
        target = enriched.most_missed_target
        self.assertEqual(target.kind, BrowseTargetKind.MOST_MISSED)
        self.assertTrue(target.exact)
        self.assertEqual(target.card_ids, (42, 7, 11))
        self.assertEqual(target.query, "cid:42,7,11")

    def test_invalid_duplicate_and_deleted_ids_fail_closed(self) -> None:
        col = FakeCollection(rows=[
            (9, 4, 4), (9, 3, 3), (0, 2, 2), (-1, 1, 1), ("bad", 1, 1),
        ])
        enriched = enrich_day_facts(col, {}, historical_facts())
        self.assertEqual(enriched.most_missed_target.card_ids, (9,))

        deleted = enrich_day_facts(FakeCollection(rows=[]), {}, historical_facts())
        self.assertEqual(deleted.most_missed_target.kind, BrowseTargetKind.NONE)
        self.assertEqual(deleted.domain_state, DayDomainState.DELETED_MISSES)

    def test_ineligible_dates_never_execute_the_ranking_query(self) -> None:
        future = historical_facts()
        future = DayFacts(
            **{
                **future.__dict__,
                "date": "2026-08-18",
                "relation": DayRelation.FUTURE,
            }
        )
        no_again = historical_facts(0)
        for facts in (future, no_again):
            with self.subTest(relation=facts.relation, again=facts.again_count.value):
                col = FakeCollection(rows=[(1, 1, 1)])
                enriched = enrich_day_facts(col, {}, facts)
                self.assertEqual(col.db.calls, [])
                self.assertEqual(enriched.most_missed_target.kind, BrowseTargetKind.NONE)

    def test_projection_and_callback_are_capability_only(self) -> None:
        enriched = enrich_day_facts(FakeCollection(rows=[(5, 2, 4)]), {}, historical_facts())
        insight = project_day_insight(enriched)
        self.assertEqual(insight.date, "2026-08-17")
        self.assertEqual(insight.browse_target.card_ids, (5,))
        self.assertIs(insight.day_facts, enriched)
        self.assertFalse(hasattr(insight, "items"))
        self.assertFalse(hasattr(insight, "empty_reason"))
        self.assertFalse(hasattr(enriched, "insight_items"))

    def test_collection_failure_returns_typed_unavailable_without_leaking_error(self) -> None:
        insight = collect_day_insight(
            FakeCollection(error=RuntimeError("secret database path")),
            {},
            date(2026, 8, 17),
            date(2026, 8, 17),
            date(2026, 8, 17),
            day_facts=historical_facts(),
        )
        self.assertEqual(insight.day_facts.domain_state, DayDomainState.UNAVAILABLE)
        self.assertEqual(insight.browse_target.kind, BrowseTargetKind.NONE)
        self.assertNotIn("secret", repr(insight))

    def test_unavailable_factory_preserves_date_relation(self) -> None:
        for selected, expected in (
            (date(2026, 8, 16), DayRelation.PAST),
            (date(2026, 8, 17), DayRelation.CURRENT),
            (date(2026, 8, 18), DayRelation.FUTURE),
        ):
            with self.subTest(selected=selected):
                result = unavailable_day_insight(selected, date(2026, 8, 17))
                self.assertEqual(result.day_facts.relation, expected)
                self.assertEqual(result.day_facts.domain_state, DayDomainState.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
