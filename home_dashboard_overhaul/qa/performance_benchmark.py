#!/usr/bin/env python3
"""Deterministic large-collection benchmark for Dashboard analytics.

The fixture is deliberately synthetic and lives in a temporary directory.  It
exercises the production analytics entry point without importing Anki or
writing to a user's collection.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import tempfile
import time
from types import SimpleNamespace
from typing import Any, Iterable, Sequence


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PACKAGE_ROOT.parent

import sys

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from home_dashboard_overhaul.analytics import collect_dashboard_facts  # noqa: E402
from home_dashboard_overhaul.config_schema import normalize_config  # noqa: E402
from home_dashboard_overhaul.models import DashboardSnapshot, VerseContent  # noqa: E402
from home_dashboard_overhaul.renderer import dashboard_facts_payload  # noqa: E402


DEFAULT_REVIEWS = 500_000
DEFAULT_CARDS = 50_000
DEFAULT_WARMUPS = 2
DEFAULT_RUNS = 7
ABSOLUTE_MEDIAN_SECONDS = 0.500
RELATIVE_IMPROVEMENT = 0.40


class CountingDB:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.query_count = 0

    def reset_count(self) -> None:
        self.query_count = 0

    def first(self, sql: str, *args: object) -> Sequence[object] | None:
        self.query_count += 1
        return self.connection.execute(sql, args).fetchone()

    def all(self, sql: str, *args: object) -> list[Sequence[object]]:
        self.query_count += 1
        return self.connection.execute(sql, args).fetchall()


class Scheduler:
    def __init__(self, card_count: int, cutoff: int) -> None:
        self.today = 25_000
        self.day_cutoff = cutoff
        child = SimpleNamespace(
            deck_id=1,
            new_count=0,
            learn_count=0,
            review_count=card_count,
            children=(),
        )
        self._root = SimpleNamespace(deck_id=0, children=(child,))

    def deck_due_tree(self) -> object:
        return self._root


class Collection:
    def __init__(self, db: CountingDB, card_count: int, cutoff: int) -> None:
        self.db = db
        self.sched = Scheduler(card_count, cutoff)
        self.decks = SimpleNamespace(children=lambda _deck_id: ())
        self.mod = 1


def _batched(values: Iterable[tuple[int, ...]], size: int = 10_000) -> Iterable[list[tuple[int, ...]]]:
    batch: list[tuple[int, ...]] = []
    for value in values:
        batch.append(value)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _create_fixture(path: Path, reviews: int, cards: int, cutoff: int) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        PRAGMA temp_store=MEMORY;
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY,
            did INTEGER NOT NULL,
            odid INTEGER NOT NULL,
            type INTEGER NOT NULL,
            queue INTEGER NOT NULL,
            due INTEGER NOT NULL,
            odue INTEGER NOT NULL
        );
        CREATE TABLE revlog (
            id INTEGER PRIMARY KEY,
            cid INTEGER NOT NULL,
            ease INTEGER NOT NULL,
            type INTEGER NOT NULL,
            lastIvl INTEGER NOT NULL,
            factor INTEGER NOT NULL,
            time INTEGER NOT NULL
        );
        CREATE INDEX ix_revlog_cid ON revlog(cid);
        CREATE INDEX ix_cards_sched ON cards(queue, due, did);
        """
    )
    scheduler_today = 25_000
    card_rows = (
        (
            card_id,
            1,
            0,
            2,
            2,
            scheduler_today + (card_id % 121),
            0,
        )
        for card_id in range(1, cards + 1)
    )
    for batch in _batched(card_rows):
        connection.executemany(
            "INSERT INTO cards(id, did, odid, type, queue, due, odue) VALUES (?, ?, ?, ?, ?, ?, ?)",
            batch,
        )

    # Spread reviews over 2,000 scheduler days, while preserving monotonically
    # increasing millisecond IDs like Anki's revlog table.
    span_ms = 2_000 * 86_400_000
    start_ms = cutoff * 1000 - span_ms
    step_ms = max(1, span_ms // max(1, reviews))
    review_rows = (
        (
            start_ms + review_index * step_ms,
            review_index % cards + 1,
            1 if review_index % 9 == 0 else 3,
            1,
            10,
            2500,
            8_000 + review_index % 9_000,
        )
        for review_index in range(reviews)
    )
    for batch in _batched(review_rows):
        connection.executemany(
            "INSERT INTO revlog(id, cid, ease, type, lastIvl, factor, time) VALUES (?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
    connection.commit()
    connection.execute("ANALYZE")
    return connection


def _source_fingerprint() -> str:
    digest = hashlib.sha256()
    for filename in ("analytics.py", "controller.py", "models.py"):
        digest.update(filename.encode("utf-8"))
        digest.update((PACKAGE_ROOT / filename).read_bytes())
    return digest.hexdigest()


def _measure(col: Collection, config: dict[str, Any], warmups: int, runs: int) -> tuple[list[float], list[int], int]:
    for _ in range(warmups):
        collect_dashboard_facts(col, config)
    durations: list[float] = []
    query_counts: list[int] = []
    payload_bytes = 0
    for _ in range(runs):
        col.db.reset_count()
        started = time.perf_counter()
        facts = collect_dashboard_facts(col, config)
        durations.append(time.perf_counter() - started)
        query_counts.append(col.db.query_count)
        payload = dashboard_facts_payload(
            DashboardSnapshot(facts=facts, verse=VerseContent()),
            config,
            selected_date=facts.scheduling_date,
        )
        payload_bytes = len(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return durations, query_counts, payload_bytes


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    cutoff = int(datetime(2026, 8, 14, 4).timestamp())
    with tempfile.TemporaryDirectory(prefix="hdo-performance-") as temporary:
        connection = _create_fixture(
            Path(temporary) / "collection.anki2",
            args.reviews,
            args.cards,
            cutoff,
        )
        try:
            db = CountingDB(connection)
            col = Collection(db, args.cards, cutoff)
            config = normalize_config({})
            durations, query_counts, payload_bytes = _measure(
                col,
                config,
                args.warmups,
                args.runs,
            )
        finally:
            connection.close()
    median = statistics.median(durations)
    result: dict[str, Any] = {
        "schema_version": 1,
        "source_fingerprint": _source_fingerprint(),
        "fixture": {"revlog_rows": args.reviews, "card_rows": args.cards},
        "measurement": {
            "warmups": args.warmups,
            "runs": args.runs,
            "durations_seconds": [round(value, 6) for value in durations],
            "median_seconds": round(median, 6),
            "query_count_median": int(statistics.median(query_counts)),
            "payload_bytes": payload_bytes,
        },
        "acceptance": {
            "absolute_median_seconds": ABSOLUTE_MEDIAN_SECONDS,
            "relative_improvement_required": RELATIVE_IMPROVEMENT,
        },
    }
    if args.compare:
        baseline = json.loads(args.compare.read_text(encoding="utf-8"))
        if baseline.get("fixture") != result["fixture"]:
            raise ValueError("baseline fixture does not match the candidate fixture")
        baseline_median = float(baseline["measurement"]["median_seconds"])
        improvement = 1.0 - median / baseline_median if baseline_median > 0 else 0.0
        result["comparison"] = {
            "baseline_median_seconds": baseline_median,
            "improvement": round(improvement, 6),
            "absolute_pass": median < ABSOLUTE_MEDIAN_SECONDS,
            "relative_pass": improvement >= RELATIVE_IMPROVEMENT,
            "passed": median < ABSOLUTE_MEDIAN_SECONDS and improvement >= RELATIVE_IMPROVEMENT,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=int, default=DEFAULT_REVIEWS)
    parser.add_argument("--cards", type=int, default=DEFAULT_CARDS)
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.reviews <= 0 or args.cards <= 0 or args.warmups < 0 or args.runs <= 0:
        parser.error("fixture sizes and run count must be positive")
    result = run_benchmark(args)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    comparison = result.get("comparison")
    return 1 if isinstance(comparison, dict) and not comparison.get("passed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
