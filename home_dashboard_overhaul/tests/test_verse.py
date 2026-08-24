from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest

from home_dashboard_overhaul.verse import MAX_VERSE_CHARS, QuoteRotator, sanitize_verse_html, split_quote_reference, verse_content, verse_within_limit


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


if __name__ == "__main__":
    unittest.main()
