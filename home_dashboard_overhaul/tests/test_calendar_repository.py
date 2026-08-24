from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import os
from pathlib import Path
import stat
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


RUNTIME_SUPPORTED = sys.version_info >= (3, 10)
if RUNTIME_SUPPORTED:
    from home_dashboard_overhaul.calendar_repository import (
        CalendarLimitError,
        CalendarRepository,
        CalendarRepositoryError,
        CalendarSourceError,
        FetchResponse,
        normalize_subscription_url,
        redacted_subscription_url,
    )


def calendar(*components: str, name: str = "Fixture calendar") -> bytes:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HDO Tests//EN", "X-WR-CALNAME:" + name]
    lines.extend(components)
    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def event(*lines: str) -> str:
    return "\r\n".join(("BEGIN:VEVENT",) + lines + ("END:VEVENT",))


@unittest.skipUnless(RUNTIME_SUPPORTED, "vendored iCalendar libraries require Python 3.10+")
class CalendarRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.user_files = self.root / "user_files"
        self.today = date(2026, 8, 13)
        self.config = {
            "events": {
                "sort": "ascending",
                "items": [],
            }
        }
        self.writes = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def repository(self, fetcher=None) -> "CalendarRepository":
        def write_config(value):
            self.writes += 1
            self.config = deepcopy(dict(value))

        return CalendarRepository(
            self.user_files,
            config_getter=lambda: self.config,
            config_writer=write_config,
            fetcher=fetcher,
            today_provider=lambda: self.today,
        )

    def write_ics(self, data: bytes, name: str = "fixture.ics") -> Path:
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_all_day_recurrence_exclusion_rdate_unicode_and_literal_markup(self) -> None:
        data = calendar(
            event(
                "UID:series-1",
                "DTSTART;VALUE=DATE:20260814",
                "DTEND;VALUE=DATE:20260815",
                "RRULE:FREQ=DAILY;COUNT=3",
                "RDATE;VALUE=DATE:20260820",
                "EXDATE;VALUE=DATE:20260815",
                "SUMMARY:Résumé <b>literal</b>",
            )
        )
        repo = self.repository()
        source = repo.import_file(self.write_ics(data))
        occurrences = repo.occurrences_between(date(2026, 8, 1), date(2026, 9, 1))
        self.assertEqual([item.start_date for item in occurrences], ["2026-08-14", "2026-08-16", "2026-08-20"])
        self.assertTrue(all(item.name == "Résumé <b>literal</b>" for item in occurrences))
        self.assertTrue(all(item.source_name == "Fixture calendar" for item in occurrences))
        self.assertEqual(source["event_count"], 1)
        self.assertNotIn("url", source)

    def test_floating_overnight_multiday_and_exclusive_midnight_projection(self) -> None:
        data = calendar(
            event(
                "UID:overnight",
                "DTSTART:20260814T233000",
                "DTEND:20260815T013000",
                "SUMMARY:Overnight",
            ),
            event(
                "UID:midnight",
                "DTSTART:20260816T120000",
                "DTEND:20260817T000000",
                "SUMMARY:Ends at midnight",
            ),
            event(
                "UID:multiday",
                "DTSTART;VALUE=DATE:20260818",
                "DTEND;VALUE=DATE:20260821",
                "SUMMARY:Conference",
            ),
        )
        repo = self.repository()
        repo.import_file(self.write_ics(data))
        rows = repo.day_events_between(date(2026, 8, 1), date(2026, 9, 1), active_only=False)
        grouped = {}
        for row in rows:
            grouped.setdefault(row.name, []).append(row.date)
        self.assertEqual(grouped["Overnight"], ["2026-08-14", "2026-08-15"])
        self.assertEqual(grouped["Ends at midnight"], ["2026-08-16"])
        self.assertEqual(grouped["Conference"], ["2026-08-18", "2026-08-19", "2026-08-20"])

    def test_vtimezone_dst_and_google_timezone_are_accepted(self) -> None:
        data = calendar(
            "X-WR-TIMEZONE:America/Chicago",
            event(
                "UID:dst",
                "DTSTART;TZID=America/Chicago:20260308T013000",
                "DTEND;TZID=America/Chicago:20260308T033000",
                "SUMMARY:DST boundary",
            ),
        )
        repo = self.repository()
        repo.import_file(self.write_ics(data))
        rows = repo.occurrences_between(date(2026, 3, 1), date(2026, 4, 1))
        self.assertEqual([(item.start_date, item.end_date_exclusive) for item in rows], [("2026-03-08", "2026-03-09")])

    def test_moved_instance_cancellation_and_duplicate_sequence(self) -> None:
        data = calendar(
            event(
                "UID:moves",
                "SEQUENCE:1",
                "DTSTART;VALUE=DATE:20260814",
                "RRULE:FREQ=DAILY;COUNT=3",
                "SUMMARY:Original",
            ),
            event(
                "UID:moves",
                "RECURRENCE-ID;VALUE=DATE:20260815",
                "SEQUENCE:2",
                "DTSTART;VALUE=DATE:20260820",
                "SUMMARY:Moved",
            ),
            event(
                "UID:moves",
                "RECURRENCE-ID;VALUE=DATE:20260816",
                "SEQUENCE:2",
                "DTSTART;VALUE=DATE:20260816",
                "STATUS:CANCELLED",
                "SUMMARY:Cancelled",
            ),
            event(
                "UID:duplicate",
                "SEQUENCE:1",
                "DTSTART;VALUE=DATE:20260822",
                "SUMMARY:Old title",
            ),
            event(
                "UID:duplicate",
                "SEQUENCE:2",
                "DTSTART;VALUE=DATE:20260822",
                "SUMMARY:New title",
            ),
        )
        repo = self.repository()
        repo.import_file(self.write_ics(data))
        rows = repo.occurrences_between(date(2026, 8, 1), date(2026, 9, 1))
        values = [(item.start_date, item.name) for item in rows]
        self.assertIn(("2026-08-14", "Original"), values)
        self.assertIn(("2026-08-20", "Moved"), values)
        self.assertNotIn(("2026-08-16", "Original"), values)
        self.assertNotIn(("2026-08-16", "Cancelled"), values)
        self.assertIn(("2026-08-22", "New title"), values)
        self.assertNotIn(("2026-08-22", "Old title"), values)

    def test_missing_uid_folded_line_control_cleanup_and_identity_stability(self) -> None:
        data = calendar(
            event(
                "DTSTART;VALUE=DATE:20260828",
                "SUMMARY:Folded café",
                " continuation\x01",
            )
        )
        path = self.write_ics(data)
        repo = self.repository()
        source = repo.import_file(path)
        first = repo.occurrences_between(date(2026, 8, 1), date(2026, 9, 1))[0]
        reopened = self.repository()
        second = reopened.occurrences_between(date(2026, 8, 1), date(2026, 9, 1))[0]
        self.assertEqual(first.occurrence_id, second.occurrence_id)
        self.assertTrue(first.series_id.startswith("missing-uid-"))
        self.assertNotIn("\x01", first.name)
        self.assertEqual(source["name"], "Fixture calendar")

    def test_same_uid_instances_on_one_date_collapse_for_dashboard_only(self) -> None:
        data = calendar(
            event("UID:repeat", "DTSTART:20260825T090000", "DTEND:20260825T100000", "SUMMARY:One"),
            event("UID:repeat", "RECURRENCE-ID:20260824T090000", "DTSTART:20260825T150000", "DTEND:20260825T160000", "SUMMARY:Moved same day"),
        )
        repo = self.repository()
        repo.import_file(self.write_ics(data))
        occurrences = repo.occurrences_between(date(2026, 8, 1), date(2026, 9, 1))
        dashboard = repo.day_events_between(date(2026, 8, 1), date(2026, 9, 1), active_only=False)
        self.assertEqual(len(occurrences), 2)
        self.assertEqual(len(dashboard), 1)

    def test_import_persists_digest_addressed_private_cache_and_remove_is_scoped(self) -> None:
        data = calendar(event("UID:a", "DTSTART;VALUE=DATE:20260830", "SUMMARY:A"))
        repo = self.repository()
        source = repo.import_file(self.write_ics(data))
        registry = json.loads((self.user_files / "calendar_sources.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["version"], 1)
        self.assertEqual(len(registry["sources"]), 1)
        source_root = repo._source_dir(source["id"])
        files = sorted(path.name for path in source_root.rglob("*") if path.is_file())
        self.assertEqual(files[0], "calendar.ics")
        self.assertEqual(len([value for value in files if value.startswith("occurrences-")]), 1)
        if os.name == "posix":
            for path in source_root.rglob("*"):
                if path.is_file():
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        sentinel = self.user_files / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        self.assertTrue(repo.remove_source(source["id"]))
        self.assertFalse(source_root.exists())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        self.assertEqual(repo.list_sources(), [])

    def test_hide_identity_survives_refresh_and_reset(self) -> None:
        first = calendar(event("UID:stable", "DTSTART;VALUE=DATE:20260830", "SUMMARY:First"))
        second = calendar(event("UID:stable", "DTSTART;VALUE=DATE:20260830", "SUMMARY:Renamed"))
        repo = self.repository()
        source = repo.import_file(self.write_ics(first, "first.ics"))
        occurrence = repo.occurrences_between(date(2026, 8, 1), date(2026, 9, 1))[0]
        self.assertTrue(repo.set_hidden(occurrence, True))
        self.assertEqual(repo.day_events_between(date(2026, 8, 1), date(2026, 9, 1)), [])
        result = repo.refresh_source(source["id"], replacement_file=self.write_ics(second, "second.ics"))
        self.assertTrue(result.success)
        hidden = repo.occurrences_between(date(2026, 8, 1), date(2026, 9, 1))[0]
        self.assertEqual(hidden.occurrence_id, occurrence.occurrence_id)
        self.assertTrue(hidden.hidden)
        self.assertEqual(repo.reset_hidden(source["id"]), 1)
        self.assertEqual(len(repo.day_events_between(date(2026, 8, 1), date(2026, 9, 1))), 1)

    def test_subscription_redaction_conditionals_304_and_last_good_fallback(self) -> None:
        data = calendar(event("UID:remote", "DTSTART;VALUE=DATE:20260831", "SUMMARY:Remote"))
        calls = []
        responses = [
            FetchResponse(200, data, {"ETag": '"v1"', "Last-Modified": "Thu, 13 Aug 2026 20:00:00 GMT"}, "https://calendar.example/final"),
            FetchResponse(304, b"", {}, "https://calendar.example/private/secret-token"),
            CalendarSourceError("failed https://calendar.example/private/secret-token"),
        ]

        def fetch(url, headers):
            calls.append((url, dict(headers)))
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        repo = self.repository(fetch)
        source = repo.subscribe_url("webcal://calendar.example/private/secret-token")
        self.assertEqual(source["display_location"], "https://calendar.example/…")
        self.assertNotIn("url", source)
        current = repo.refresh_source(source["id"])
        self.assertTrue(current.success)
        self.assertFalse(current.changed)
        self.assertEqual(calls[1][1], {
            "If-None-Match": '"v1"',
            "If-Modified-Since": "Thu, 13 Aug 2026 20:00:00 GMT",
        })
        failed = repo.refresh_source(source["id"])
        self.assertFalse(failed.success)
        self.assertNotIn("secret-token", failed.message)
        stored = repo.source(source["id"])
        self.assertNotIn("secret-token", stored["last_error"])
        self.assertEqual(len(repo.day_events_between(date(2026, 8, 1), date(2026, 9, 2))), 1)

    def test_failed_replacement_url_preserves_the_original_private_url(self) -> None:
        data = calendar(event("UID:a", "DTSTART;VALUE=DATE:20260820", "SUMMARY:A"))
        responses = [FetchResponse(200, data, {}, "https://old.example/final")]

        def fetch(url, _headers):
            if responses:
                return responses.pop(0)
            raise CalendarSourceError("Invalid replacement https://new.example/other-secret")

        repo = self.repository(fetch)
        source = repo.subscribe_url("https://old.example/original-secret")
        result = repo.refresh_source(source["id"], replacement_url="https://new.example/other-secret")
        self.assertFalse(result.success)
        registry = json.loads(repo.registry_path.read_text(encoding="utf-8"))
        self.assertEqual(registry["sources"][0]["url"], "https://old.example/original-secret")
        self.assertNotIn("other-secret", registry["sources"][0]["last_error"])

    def test_redirect_downgrade_is_rejected_even_for_an_injected_fetcher(self) -> None:
        data = calendar(event("UID:a", "DTSTART;VALUE=DATE:20260820", "SUMMARY:A"))
        repo = self.repository(
            lambda _url, _headers: FetchResponse(200, data, {}, "http://calendar.example/downgraded")
        )
        with self.assertRaises(CalendarSourceError):
            repo.subscribe_url("https://calendar.example/private")
        self.assertEqual(repo.list_sources(), [])

    def test_source_refresh_rebuilds_snapshot_cache_without_original_file(self) -> None:
        data = calendar(event("UID:a", "DTSTART;VALUE=DATE:20260820", "SUMMARY:A"))
        repo = self.repository()
        source = repo.import_file(self.write_ics(data))
        result = repo.refresh_source(source["id"])
        self.assertTrue(result.success)
        self.assertFalse(result.changed)
        self.assertEqual(len(repo.day_events_between(date(2026, 8, 1), date(2026, 9, 1))), 1)

    def test_out_of_range_query_keeps_the_broad_startup_cache(self) -> None:
        data = calendar(
            event("UID:a", "DTSTART;VALUE=DATE:20260820", "SUMMARY:Current"),
            event("UID:b", "DTSTART;VALUE=DATE:20300120", "SUMMARY:Later"),
        )
        repo = self.repository()
        source = repo.import_file(self.write_ics(data))
        later = repo.occurrences_between(date(2030, 1, 1), date(2030, 2, 1))
        self.assertEqual([item.name for item in later], ["Later"])
        reopened = self.repository()
        current = reopened.day_events_between(
            date(2026, 1, 1), date(2027, 1, 1), cached_only=True
        )
        self.assertEqual([item.name for item in current], ["Current"])
        generation = reopened._generation_dir(source["id"], source["content_sha256"])
        self.assertEqual(len(list(generation.glob("occurrences-*.json"))), 2)

    def test_url_validation_never_echoes_private_path(self) -> None:
        self.assertEqual(normalize_subscription_url("webcal://example.test/a/b"), "https://example.test/a/b")
        self.assertEqual(redacted_subscription_url("https://example.test/a/b?secret=1"), "https://example.test/…")
        for invalid in ("http://example.test/a", "ftp://example.test/a", "https://user:pass@example.test/a"):
            with self.subTest(invalid=invalid), self.assertRaises(CalendarSourceError):
                normalize_subscription_url(invalid)
        repo = self.repository(
            lambda _url, _headers: (_ for _ in ()).throw(
                CalendarSourceError("failed https://example.test/private-secret")
            )
        )
        with self.assertRaises(CalendarSourceError) as raised:
            repo.subscribe_url("https://example.test/private-secret")
        self.assertNotIn("private-secret", str(raised.exception))

    def test_local_actions_persist_immediately_and_reject_blank_names(self) -> None:
        repo = self.repository()
        event_id = repo.add_local("  Clerkship exam  ", "2026-09-01")
        self.assertEqual(self.writes, 1)
        self.assertEqual(self.config["events"]["items"][0]["name"], "Clerkship exam")
        self.assertTrue(repo.edit_local(event_id, "Final exam", "2026-09-02"))
        duplicate = repo.duplicate_local(event_id)
        self.assertIsNotNone(duplicate)
        self.assertEqual(repo.set_local_archived([event_id, "missing"], True), 1)
        self.assertEqual(repo.set_local_archived([event_id], False), 1)
        self.assertEqual(repo.delete_local([duplicate]), 1)
        with self.assertRaises(CalendarRepositoryError):
            repo.add_local("  ", "2026-09-03")
        self.assertEqual(self.writes, 6)

    def test_disable_and_rename_do_not_mutate_local_events(self) -> None:
        self.config["events"]["items"] = [{"id": "local", "name": "Local", "date": "2026-08-20", "archived": False}]
        data = calendar(event("UID:a", "DTSTART;VALUE=DATE:20260821", "SUMMARY:Remote"))
        repo = self.repository()
        source = repo.import_file(self.write_ics(data))
        self.assertTrue(repo.rename_source(source["id"], "Renamed source"))
        self.assertTrue(repo.set_source_enabled(source["id"], False))
        rows = repo.day_events_between(date(2026, 8, 1), date(2026, 9, 1))
        self.assertEqual([(row.name, row.source_name) for row in rows], [("Local", "Local")])
        self.assertEqual(self.config["events"]["items"][0]["name"], "Local")

    def test_day_events_name_sort_is_case_insensitive_then_date_and_stable_id(self) -> None:
        self.config["events"]["sort"] = "name"
        self.config["events"]["items"] = [
            {"id": "z", "name": "alpha", "date": "2026-08-16", "archived": False},
            {"id": "a", "name": "ALPHA", "date": "2026-08-15", "archived": False},
            {"id": "b", "name": "Beta", "date": "2026-08-14", "archived": False},
        ]
        repo = self.repository()

        rows = repo.day_events_between(date(2026, 8, 13), date(2026, 8, 20))

        self.assertEqual(
            [(row.name, row.date) for row in rows],
            [
                ("ALPHA", "2026-08-15"),
                ("alpha", "2026-08-16"),
                ("Beta", "2026-08-14"),
            ],
        )

    def test_malformed_feed_and_bounded_limits_are_visible_errors(self) -> None:
        repo = self.repository()
        with self.assertRaises(CalendarSourceError):
            repo.import_file(self.write_ics(b"not a calendar"))
        with self.assertRaises(CalendarLimitError):
            repo.occurrences_between(date(2000, 1, 1), date(2020, 1, 1))
        dense = calendar(
            event("UID:a", "DTSTART;VALUE=DATE:20260820", "SUMMARY:A"),
            event("UID:b", "DTSTART;VALUE=DATE:20260821", "SUMMARY:B"),
        )
        with patch("home_dashboard_overhaul.calendar_repository.MAX_COMPONENTS", 1):
            with self.assertRaises(CalendarLimitError):
                repo.import_file(self.write_ics(dense, "dense.ics"))


if __name__ == "__main__":
    unittest.main()
