from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from home_dashboard_overhaul.analytics import collect_dashboard_facts
from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.qa.performance_benchmark import (
    ABSOLUTE_MEDIAN_SECONDS,
    DEFAULT_CARDS,
    DEFAULT_REVIEWS,
    RELATIVE_IMPROVEMENT,
    Collection,
    CountingDB,
    _create_fixture,
)


class PerformanceContractTests(unittest.TestCase):
    def test_large_collection_contract_and_bounded_refresh_queries(self) -> None:
        self.assertEqual((DEFAULT_REVIEWS, DEFAULT_CARDS), (500_000, 50_000))
        self.assertEqual((ABSOLUTE_MEDIAN_SECONDS, RELATIVE_IMPROVEMENT), (0.5, 0.4))

        cutoff = int(datetime(2026, 8, 14, 4).timestamp())
        with tempfile.TemporaryDirectory(prefix="hdo-performance-test-") as temporary:
            connection = _create_fixture(
                Path(temporary) / "collection.anki2",
                reviews=5_000,
                cards=1_000,
                cutoff=cutoff,
            )
            try:
                db = CountingDB(connection)
                facts = collect_dashboard_facts(
                    Collection(db, 1_000, cutoff),
                    normalize_config({}),
                )
            finally:
                connection.close()

        self.assertLessEqual(db.query_count, 7)
        self.assertTrue(facts.long_term.is_available)
        self.assertTrue(all(not day.browse_target.card_ids for day in facts.days.values()))


if __name__ == "__main__":
    unittest.main()
