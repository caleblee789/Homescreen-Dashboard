from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest

from home_dashboard_overhaul.verse import (
    MAX_VERSE_CHARS,
    QuoteRotator,
    sanitize_verse_html,
    serialize_quote_reference,
    split_quote_reference,
    verse_content,
    verse_within_limit,
)


class VerseSafetyTests(unittest.TestCase):
    def test_only_attribute_free_formatting_tags_survive(self) -> None:
        value = '<b>safe</b><br><i title="x">unsafe tag</i><script>alert(1)</script>'
        output = sanitize_verse_html(value)
        self.assertIn("<b>safe</b><br>", output)
        self.assertIn("&lt;i title=", output)
        self.assertIn("&lt;script&gt;", output)
        self.assertNotIn("<script>", output)

    def test_reference_is_rendered_separately(self) -> None:
        body, reference = split_quote_reference("Faith and grace.<br>- Romans 4:5 (NLT)")
        self.assertEqual(body, "Faith and grace.")
        self.assertEqual(reference, "Romans 4:5 (NLT)")
        content = verse_content("<strong>Faith</strong>.<br>- Romans 4:5 (NLT)")
        self.assertEqual(content.body_html, "<strong>Faith</strong>.")
        self.assertEqual(content.reference_html, "Romans 4:5 (NLT)")

    def test_explicit_final_line_accepts_long_free_form_reference(self) -> None:
        long_reference = (
            "A much longer attribution that intentionally exceeds the legacy "
            "citation limit and does not contain a chapter or verse number"
        )

        body, reference = split_quote_reference("Faith and grace.\n- " + long_reference)

        self.assertEqual(body, "Faith and grace.")
        self.assertEqual(reference, long_reference)

    def test_explicit_final_line_accepts_unicode_dash_markers(self) -> None:
        for marker in ("\u2013", "\u2014"):
            with self.subTest(marker=marker):
                self.assertEqual(
                    split_quote_reference("Be still.<br>{} A free-form source".format(marker)),
                    ("Be still.", "A free-form source"),
                )

    def test_ordinary_multiline_body_is_not_treated_as_a_reference(self) -> None:
        for value in (
            "First body line.\nSecond body line without a reference marker.",
            "First body line.<br>Second body line without a reference marker.",
        ):
            with self.subTest(value=value):
                self.assertEqual(split_quote_reference(value), (value, ""))

    def test_legacy_unmarked_bible_citation_still_splits(self) -> None:
        self.assertEqual(
            split_quote_reference("Faith and grace.\nRomans 4:5 (NLT)"),
            ("Faith and grace.", "Romans 4:5 (NLT)"),
        )

    def test_quote_reference_serialization_round_trips(self) -> None:
        body = "First line.<br>Second line with <strong>emphasis</strong>."
        reference = "A long free-form reference without a numeric citation"

        serialized = serialize_quote_reference(body, reference)

        self.assertEqual(serialized, body + "<br>- " + reference)
        self.assertEqual(split_quote_reference(serialized), (body, reference))

    def test_explicit_free_form_reference_is_still_sanitized_for_rendering(self) -> None:
        content = verse_content("Safe body.<br>- <script>unsafe source</script>")

        self.assertEqual(content.body_html, "Safe body.")
        self.assertIn("&lt;script&gt;", content.reference_html)
        self.assertNotIn("<script>", content.reference_html)

    def test_quote_reference_serializer_handles_blank_values(self) -> None:
        self.assertEqual(serialize_quote_reference("  Body only.  ", "  "), "Body only.")
        self.assertEqual(serialize_quote_reference("", "Reference"), "<br>- Reference")
        self.assertEqual(serialize_quote_reference(None, None), "")
        self.assertEqual(split_quote_reference("<br>- Reference"), ("<br>- Reference", ""))

    def test_oversized_existing_text_is_bounded_for_rendering(self) -> None:
        oversized = "A" * (MAX_VERSE_CHARS + 500)
        self.assertFalse(verse_within_limit(oversized))
        content = verse_content(oversized)
        self.assertLessEqual(len(content.body_html), MAX_VERSE_CHARS + 1)
        self.assertTrue(content.body_html.endswith("…"))


class RotationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / "user_files" / "rotation_state.json"
        self.quotes = ["A", "B"]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_daily_rotation_survives_restart_and_changes_next_day(self) -> None:
        first = QuoteRotator(self.state, now=lambda: datetime(2026, 8, 13, 10), choose=lambda values: values[0])
        self.assertEqual(first.get_quote(self.quotes, "daily"), "A")
        restarted = QuoteRotator(self.state, now=lambda: datetime(2026, 8, 13, 23), choose=lambda values: values[1])
        self.assertEqual(restarted.get_quote(self.quotes, "daily"), "A")
        next_day = QuoteRotator(self.state, now=lambda: datetime(2026, 8, 14, 1), choose=lambda values: values[1])
        self.assertEqual(next_day.get_quote(self.quotes, "daily"), "B")

    def test_manual_is_restart_safe_and_every_render_does_not_persist(self) -> None:
        manual = QuoteRotator(self.state, choose=lambda values: values[1])
        self.assertEqual(manual.get_quote(self.quotes, "manual"), "B")
        self.assertEqual(json.loads(self.state.read_text())["refresh_key"], "manual")
        choices = iter(["A", "B"])
        each = QuoteRotator(self.state, choose=lambda _values: next(choices))
        self.assertEqual(each.get_quote(self.quotes, "every render"), "A")
        self.assertEqual(each.get_quote(self.quotes, "every render"), "B")
        self.assertEqual(json.loads(self.state.read_text())["quote"], "B")

    def test_quote_changes_invalidate_persisted_state(self) -> None:
        first = QuoteRotator(self.state, choose=lambda values: values[0])
        first.get_quote(self.quotes, "manual")
        changed = QuoteRotator(self.state, choose=lambda values: values[-1])
        self.assertEqual(changed.get_quote(["A", "C"], "manual"), "C")

    def test_explicit_manual_choice_is_persisted_and_validated(self) -> None:
        rotator = QuoteRotator(self.state, choose=lambda values: values[0])
        self.assertTrue(rotator.set_quote(self.quotes, "manual", "B"))
        self.assertEqual(rotator.get_quote(self.quotes, "manual"), "B")
        restarted = QuoteRotator(self.state, choose=lambda values: values[0])
        self.assertEqual(restarted.get_quote(self.quotes, "manual"), "B")
        self.assertFalse(rotator.set_quote(self.quotes, "manual", "missing"))
        self.assertFalse(rotator.set_quote(self.quotes, "every render", "A"))

    def test_manual_choice_can_be_prepared_without_mutating_disk_or_memory(self) -> None:
        rotator = QuoteRotator(self.state, choose=lambda values: values[0])

        prepared = rotator.prepare_quote(self.quotes, "manual", "B")

        self.assertIsNotNone(prepared)
        self.assertFalse(self.state.exists())
        self.assertEqual(rotator._memory_quote, "")
        rotator.persist_prepared(prepared or {})
        self.assertEqual(json.loads(self.state.read_text(encoding="utf-8"))["quote"], "B")
        self.assertEqual(rotator._memory_quote, "")
        rotator.adopt_prepared(prepared or {})
        self.assertEqual(rotator._memory_quote, "B")

    def test_current_quote_reads_valid_memory_or_disk_without_selecting(self) -> None:
        persisted = QuoteRotator(self.state, choose=lambda values: values[1])
        self.assertEqual(persisted.get_quote(self.quotes, "manual"), "B")
        before = self.state.read_text(encoding="utf-8")
        restarted = QuoteRotator(
            self.state,
            choose=lambda _values: self.fail("current_quote must not choose"),
        )

        self.assertEqual(restarted.current_quote(self.quotes, "manual"), "B")
        self.assertEqual(restarted._memory_quote, "")
        self.assertEqual(self.state.read_text(encoding="utf-8"), before)

        restarted.adopt_prepared(
            restarted.prepare_quote(self.quotes, "manual", "A") or {}
        )
        self.assertEqual(restarted.current_quote(self.quotes, "manual"), "A")

    def test_current_quote_has_no_marker_for_unstable_or_stale_state(self) -> None:
        rotator = QuoteRotator(
            self.state,
            now=lambda: datetime(2026, 8, 27, 10),
            choose=lambda values: values[0],
        )
        self.assertEqual(rotator.get_quote(self.quotes, "daily"), "A")
        before = self.state.read_text(encoding="utf-8")

        self.assertEqual(rotator.current_quote(self.quotes, "every render"), "")
        self.assertEqual(rotator.current_quote(["A", "C"], "daily"), "")
        next_day = QuoteRotator(
            self.state,
            now=lambda: datetime(2026, 8, 28, 10),
            choose=lambda _values: self.fail("current_quote must not choose"),
        )
        self.assertEqual(next_day.current_quote(self.quotes, "daily"), "")
        self.assertEqual(self.state.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
