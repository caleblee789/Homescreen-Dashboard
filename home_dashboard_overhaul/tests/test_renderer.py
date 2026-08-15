from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import html
import json
import re
import time
import unittest

from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.models import BuriedStats, DayInsight, InsightItem, LongTermStats, QueueStats, TodayStats, VerseContent
from home_dashboard_overhaul.renderer import _eta, render_activation_required, render_dashboard, sample_snapshot


class RendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = normalize_config({})

    def _group(self, output: str, group_id: str) -> str:
        start = output.index('aria-labelledby="{}-title"'.format(group_id))
        return output[start:output.index("</section>", start)]

    def _progress_bar(self, output: str) -> str:
        match = re.search(r'<div class="hdo-progress-bar".*?</div>', output)
        self.assertIsNotNone(match)
        return match.group(0)

    def test_renderer_has_one_calendar_statistics_card_then_one_bible_card(self) -> None:
        output = render_dashboard(sample_snapshot(), self.config)
        cards = re.findall(r'<section class="hdo-card ([^"]+)"', output)
        self.assertEqual(cards, ["hdo-study-card", "hdo-bible-card"])
        self.assertGreater(output.index("hdo-bible-card"), output.index("hdo-study-card"))
        self.assertNotIn("hdo-event-list", output)
        self.assertNotIn("hdo-long-term", output)
        self.assertNotIn("hdo-panel", output)
        for group in ("Today", "Today’s Progress", "Buried Cards", "Consistency"):
            self.assertEqual(output.count(">{}</h3>".format(group)), 1)

    def test_all_hidden_dashboard_has_a_keyboard_recovery_action(self) -> None:
        config = normalize_config({"visibility": {
            "today": False,
            "remaining": False,
            "buried": False,
            "heatmap": False,
            "heatmap_metrics": False,
            "events": False,
            "bible": False,
        }})
        output = render_dashboard(sample_snapshot(), config)
        self.assertIn("Dashboard sections are hidden", output)
        self.assertIn('data-hdo-command="settings"', output)
        self.assertIn("Open Home screen settings", output)
        self.assertNotIn("hdo-study-card", output)
        self.assertNotIn("hdo-bible-card", output)

    def test_partial_errors_never_render_substitute_zeroes_or_raw_exceptions(self) -> None:
        snapshot = replace(
            sample_snapshot(),
            today=TodayStats(),
            buried=BuriedStats(),
            long_term=LongTermStats(),
            errors={
                "today": "SQL failed with token=private-value",
                "buried": "raw buried error",
                "heatmap": "raw history error",
                "forecast": "raw forecast error",
            },
        )
        output = render_dashboard(snapshot, self.config)
        for group_id in ("hdo-today", "hdo-buried", "hdo-consistency"):
            self.assertIn("<dd>—</dd>", self._group(output, group_id))
        self.assertNotIn("private-value", output)
        self.assertNotIn("raw history error", output)
        self.assertIn("Unavailable: buried-card counts, due forecast, study history, Today metrics.", output)
        payload = json.loads(re.search(r'<script type="application/json"[^>]*>(.*?)</script>', output).group(1))
        self.assertFalse(payload["availability"]["history"])
        self.assertFalse(payload["availability"]["forecast"])

    def test_renderer_exports_percent_complete_violet_without_recoloring_completed_segment(self) -> None:
        light = render_dashboard(sample_snapshot(), self.config)
        dark = render_dashboard(sample_snapshot(), self.config, anki_dark=True)
        self.assertIn("--hdo-progress-percent:#6D28D9", light)
        self.assertIn("--hdo-progress-percent:#C4B5FD", dark)

    def test_date_details_include_contextual_summary_without_duplicate_global_metrics(self) -> None:
        output = render_dashboard(sample_snapshot(), self.config)
        self.assertIn("Percent Complete", output)
        self.assertIn("Total remaining", output)
        self.assertEqual(output.count("Review cards due"), 1)
        self.assertIn("<dt>Completed Reviews</dt>", output)
        self.assertIn("<dt>Cards Due</dt>", output)
        self.assertIn("data-hdo-details-summary", output)
        self.assertIn("data-hdo-summary-completed", output)
        self.assertIn("data-hdo-summary-new", output)
        self.assertIn("data-hdo-summary-due", output)
        self.assertIn("data-hdo-details-announcement", output)
        self.assertIn('class="hdo-day-insight"', output)
        self.assertIn('data-hdo-insight-items', output)
        self.assertIn('role="status" aria-live="polite"', output)
        self.assertNotIn("<dt>Due Today</dt>", output)
        self.assertEqual(output.count("<dt>Pace</dt>"), 1)
        self.assertEqual(output.count("<dt>New Cards Studied</dt>"), 2)
        for label in ("Total Cards Studied", "Time studied", "ETA", "Percent Complete", "New remaining", "Learning remaining", "Reviews remaining", "Total remaining", "New", "Learning", "Reviews", "Avg cards / day", "Active days", "Longest streak", "Current streak"):
            self.assertEqual(output.count("<dt>{}</dt>".format(label)), 1, label)
        self.assertNotIn("New available", output)
        self.assertNotIn("Estimated time", output)

    def test_today_and_progress_rows_are_in_the_requested_order(self) -> None:
        output = render_dashboard(sample_snapshot(), self.config)
        today = self._group(output, "hdo-today")
        today_labels = ["Total Cards Studied", "New Cards Studied", "Time studied", "Pace", "ETA"]
        self.assertEqual(
            [match.group(1) for match in re.finditer(r"<dt>(.*?)</dt>", today)],
            today_labels,
        )
        self.assertIn("<dt>ETA</dt>", today)

        progress = self._group(output, "hdo-remaining")
        progress_labels = ["Percent Complete", "New remaining", "Learning remaining", "Reviews remaining", "Total remaining"]
        self.assertEqual(
            [html.unescape(match.group(1)) for match in re.finditer(r"<dt>(.*?)</dt>", progress)],
            progress_labels,
        )

    def test_one_day_streak_uses_singular_copy(self) -> None:
        snapshot = replace(
            sample_snapshot(),
            long_term=LongTermStats(10, 50, 1, 1),
        )
        consistency = self._group(render_dashboard(snapshot, self.config), "hdo-consistency")
        self.assertEqual(consistency.count(">1 day</dd>"), 2)
        self.assertNotIn("1 days", consistency)

    def test_eta_is_owned_only_by_today_and_can_be_hidden(self) -> None:
        output = render_dashboard(sample_snapshot(), self.config)
        self.assertIn("<dt>ETA</dt>", self._group(output, "hdo-today"))
        self.assertNotIn("<dt>ETA</dt>", self._group(output, "hdo-remaining"))
        hidden = render_dashboard(sample_snapshot(), normalize_config({"study": {"show_eta": False}}))
        self.assertNotIn("<dt>ETA</dt>", hidden)
        self.assertIn("hdo-remaining-title", hidden)

    def test_eta_is_absent_when_today_is_hidden_even_if_progress_is_visible(self) -> None:
        output = render_dashboard(
            sample_snapshot(),
            normalize_config({"visibility": {"today": False, "remaining": True}}),
        )
        self.assertNotIn("<dt>ETA</dt>", output)
        self.assertIn("hdo-remaining-title", output)

    def test_eta_uses_local_smart_clock_copy(self) -> None:
        central = timezone(timedelta(hours=-5))
        now = datetime(2026, 8, 13, 16, 42, tzinfo=central)
        self.assertEqual(_eta(None, now), "—")
        self.assertEqual(_eta(0, now), "Done")
        self.assertEqual(_eta(3600, now), "5:42 PM")
        self.assertEqual(_eta(8 * 3600, now), "Tomorrow, 12:42 AM")
        self.assertEqual(_eta(2 * 86400, now), "Aug 15, 4:42 PM")

    def test_renderer_shows_done_and_unknown_eta_states(self) -> None:
        done = replace(sample_snapshot(), queue=QueueStats(0, 0, 0, 0, 0))
        unknown = replace(sample_snapshot(), queue=QueueStats(1, 0, 0, 1, None))
        self.assertIn("<dt>ETA</dt><dd>Done</dd>", render_dashboard(done, self.config))
        self.assertIn("<dt>ETA</dt><dd>—</dd>", render_dashboard(unknown, self.config))

    def test_progress_percentage_segments_and_accessible_description(self) -> None:
        output = render_dashboard(sample_snapshot(), self.config)
        progress = self._group(output, "hdo-remaining")
        bar = self._progress_bar(progress)
        self.assertIn('role="progressbar"', bar)
        self.assertIn('aria-valuemin="0"', bar)
        self.assertIn('aria-valuemax="100"', bar)
        self.assertIn('aria-valuenow="62"', bar)
        self.assertIn("62% complete: 229 completed answers, 8 new remaining, 10 learning remaining, 124 reviews remaining, 142 total remaining.", html.unescape(bar))
        self.assertIn("<dt>Percent Complete</dt><dd>62%</dd>", progress)
        self.assertEqual(
            re.findall(r'data-hdo-segment="([^"]+)"', bar),
            ["completed", "new", "learning", "review"],
        )
        self.assertEqual(
            re.findall(r'data-hdo-count="([^"]+)"', bar),
            ["229", "8", "10", "124"],
        )
        self.assertEqual(re.sub(r"<[^>]+>", "", bar), "")
        self.assertNotIn("title=", bar)
        self.assertNotIn("tabindex=", bar)

    def test_progress_uses_half_up_whole_number_rounding_and_ignores_queue_total(self) -> None:
        snapshot = replace(
            sample_snapshot(),
            today=TodayStats(2, 0, 0, None),
            queue=QueueStats(1, 0, 0, 999, 30),
        )
        progress = self._group(render_dashboard(snapshot, self.config), "hdo-remaining")
        self.assertIn("<dt>Percent Complete</dt><dd>67%</dd>", progress)
        self.assertIn("<dt>Total remaining</dt><dd>1</dd>", progress)
        self.assertNotIn(">999</dd>", progress)

    def test_progress_complete_zero_and_neutral_states(self) -> None:
        complete = replace(sample_snapshot(), today=TodayStats(5), queue=QueueStats())
        complete_group = self._group(render_dashboard(complete, self.config), "hdo-remaining")
        self.assertIn('aria-valuenow="100"', self._progress_bar(complete_group))
        self.assertIn("<dt>Percent Complete</dt><dd>100%</dd>", complete_group)

        zero = replace(sample_snapshot(), today=TodayStats(), queue=QueueStats(0, 1, 0, 1, 60))
        zero_group = self._group(render_dashboard(zero, self.config), "hdo-remaining")
        self.assertIn('aria-valuenow="0"', self._progress_bar(zero_group))
        self.assertIn("<dt>Percent Complete</dt><dd>0%</dd>", zero_group)

        empty = replace(sample_snapshot(), today=TodayStats(), queue=QueueStats())
        empty_group = self._group(render_dashboard(empty, self.config), "hdo-remaining")
        empty_bar = self._progress_bar(empty_group)
        self.assertIn('data-hdo-progress-state="empty"', empty_bar)
        self.assertNotIn("aria-valuenow=", empty_bar)
        self.assertIn("No completed answers or actionable cards are available for the current day.", empty_bar)
        self.assertIn("<dt>Percent Complete</dt><dd>—</dd>", empty_group)

        unavailable = replace(sample_snapshot(), errors={"today": "unavailable"})
        unavailable_group = self._group(render_dashboard(unavailable, self.config), "hdo-remaining")
        unavailable_bar = self._progress_bar(unavailable_group)
        self.assertIn('data-hdo-progress-state="unavailable"', unavailable_bar)
        self.assertNotIn("aria-valuenow=", unavailable_bar)
        self.assertIn("<dt>Percent Complete</dt><dd>—</dd>", unavailable_group)

    def test_queue_unavailable_uses_neutral_numeric_rows_and_eta(self) -> None:
        snapshot = replace(sample_snapshot(), errors={"queue": "unavailable"})
        progress = self._group(render_dashboard(snapshot, self.config), "hdo-remaining")
        for label in ("New remaining", "Learning remaining", "Reviews remaining", "Total remaining"):
            self.assertIn("<dt>{}</dt><dd>—</dd>".format(label), progress)
        today = self._group(render_dashboard(snapshot, self.config), "hdo-today")
        self.assertIn("<dt>ETA</dt><dd>—</dd>", today)

    def test_buried_counts_cannot_affect_progress_markup(self) -> None:
        baseline = replace(sample_snapshot(), buried=BuriedStats(0, 0, 0))
        changed = replace(sample_snapshot(), buried=BuriedStats(999999, 888888, 777777))
        baseline_progress = self._group(render_dashboard(baseline, self.config), "hdo-remaining")
        changed_progress = self._group(render_dashboard(changed, self.config), "hdo-remaining")
        self.assertEqual(baseline_progress, changed_progress)
        self.assertNotIn("buried", baseline_progress.casefold())

    def test_tiny_and_zero_queue_segments_are_finite_and_keep_numeric_rows(self) -> None:
        snapshot = replace(
            sample_snapshot(),
            today=TodayStats(1),
            queue=QueueStats(0, 1, 0, 3000, 1),
        )
        progress = self._group(render_dashboard(snapshot, self.config), "hdo-remaining")
        bar = self._progress_bar(progress)
        self.assertEqual(re.findall(r'data-hdo-count="([^"]+)"', bar), ["1", "0", "1", "0"])
        self.assertIn("<dt>New remaining</dt><dd>0</dd>", progress)
        self.assertIn("<dt>Learning remaining</dt><dd>1</dd>", progress)
        self.assertIn("<dt>Reviews remaining</dt><dd>0</dd>", progress)
        self.assertNotRegex(bar.casefold(), r"nan|inf|-[0-9]")

    def test_remaining_visibility_key_still_hides_the_entire_progress_group(self) -> None:
        config = normalize_config({"visibility": {"remaining": False}})
        output = render_dashboard(sample_snapshot(), config)
        self.assertNotIn("hdo-remaining-title", output)
        self.assertNotIn("hdo-progress-bar", output)
        self.assertNotIn("Today’s Progress", output)
        self.assertIn("hdo-today-title", output)

    def test_renderer_uses_one_in_flow_details_structure_without_overlay_surfaces(self) -> None:
        output = render_dashboard(sample_snapshot(), self.config)
        self.assertEqual(output.count('<section class="hdo-date-details"'), 1)
        self.assertEqual(output.count('data-hdo-date-details'), 1)
        self.assertIn('role="region"', output)
        self.assertIn('data-hdo-details-close', output)
        self.assertIn('data-hdo-browse-date', output)
        self.assertIn('data-hdo-manage-events', output)
        self.assertIn('data-hdo-manage-events>Manage this date</button>', output)
        self.assertIn('data-hdo-details-summary', output)
        self.assertIn('data-hdo-summary-completed', output)
        self.assertIn('data-hdo-summary-new', output)
        self.assertIn('data-hdo-summary-due', output)
        self.assertIn('data-hdo-details-announcement', output)
        self.assertIn('aria-labelledby="hdo-insight-title"', output)
        self.assertEqual(output.count('data-hdo-insight-status'), 1)
        self.assertEqual(output.count('data-hdo-insight-items'), 1)
        self.assertEqual(output.count('data-hdo-day-preview hidden'), 1)
        self.assertEqual(output.count('role="tooltip"'), 1)
        self.assertNotIn("hdo-date-popover", output)
        self.assertNotIn("hdo-popover-action", output)
        self.assertNotIn("aria-modal", output)

    def test_calendar_secondary_owns_one_details_region_and_one_ordered_metric_set(self) -> None:
        output = render_dashboard(sample_snapshot(), self.config)
        secondary = output.index('<div class="hdo-calendar-secondary" data-hdo-has-stats="true">')
        details = output.index('<section class="hdo-date-details"', secondary)
        today = output.index('<section class="hdo-stat-group" aria-labelledby="hdo-today-title">', details)
        remaining = output.index('<section class="hdo-stat-group" aria-labelledby="hdo-remaining-title">', today)
        buried = output.index('<section class="hdo-stat-group" aria-labelledby="hdo-buried-title">', remaining)
        consistency = output.index('<section class="hdo-stat-group" aria-labelledby="hdo-consistency-title">', buried)
        self.assertLess(secondary, details)
        self.assertLess(details, today)
        self.assertLess(today, remaining)
        self.assertLess(remaining, buried)
        self.assertLess(buried, consistency)
        self.assertEqual(output.count('class="hdo-stat-groups"'), 1)
        self.assertNotIn("data-hdo-details-empty", output)

    def test_calendar_secondary_reports_when_all_metric_groups_are_disabled(self) -> None:
        config = normalize_config({"visibility": {
            "today": False,
            "remaining": False,
            "buried": False,
            "heatmap_metrics": False,
        }})
        output = render_dashboard(sample_snapshot(), config)
        self.assertIn('<div class="hdo-calendar-secondary" data-hdo-has-stats="false">', output)
        self.assertEqual(output.count('<section class="hdo-date-details"'), 1)
        self.assertNotIn('class="hdo-stat-groups"', output)
        self.assertNotIn('class="hdo-stats-divider"', output)

    def test_metric_visibility_combinations_keep_one_canonical_ordered_set(self) -> None:
        cases = (
            (
                {"heatmap_metrics": False},
                ("hdo-today-title", "hdo-remaining-title", "hdo-buried-title"),
            ),
            (
                {"today": False, "remaining": False, "buried": False},
                ("hdo-consistency-title",),
            ),
        )
        for visibility, expected_ids in cases:
            with self.subTest(expected_ids=expected_ids):
                output = render_dashboard(
                    sample_snapshot(),
                    normalize_config({"visibility": visibility}),
                )
                self.assertEqual(output.count('<section class="hdo-stat-group"'), len(expected_ids))
                positions = [output.index('aria-labelledby="{}"'.format(group_id)) for group_id in expected_ids]
                self.assertEqual(positions, sorted(positions))
                for group_id in expected_ids:
                    self.assertEqual(output.count('id="{}"'.format(group_id)), 1)

    def test_metrics_remain_once_when_calendar_is_hidden(self) -> None:
        config = normalize_config({"visibility": {"heatmap": False}})
        output = render_dashboard(sample_snapshot(), config)
        self.assertNotIn("hdo-calendar-secondary", output)
        self.assertNotIn("hdo-date-details", output)
        self.assertEqual(output.count('class="hdo-stat-groups"'), 1)

    def test_user_content_is_escaped_and_verse_markup_is_already_sanitized(self) -> None:
        snapshot = replace(sample_snapshot(), verse=VerseContent("&lt;script&gt;bad&lt;/script&gt;<strong>safe</strong>", "Romans 1:1 (NLT)"))
        config = normalize_config({"events": {"items": [{"id": "1", "name": '<img src=x onerror="bad">', "date": "2026-08-29"}]}})
        output = render_dashboard(snapshot, config)
        self.assertNotIn("<img src=x", output)
        self.assertIn("\\u003cimg", output)
        self.assertNotIn("<script>bad", output)
        self.assertIn("<strong>safe</strong>", output)

    def test_activity_payload_escapes_html_delimiters(self) -> None:
        output = render_dashboard(sample_snapshot(), self.config)
        scripts = re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', output)
        self.assertEqual(len(scripts), 1)
        self.assertNotIn("<", scripts[0])
        payload = json.loads(scripts[0])
        self.assertIsInstance(payload["activity"], list)
        self.assertIn("new_cards_studied", payload["activity"][0])
        self.assertEqual(payload["view"], "year")
        self.assertEqual(payload["week_start"], 0)
        self.assertEqual(payload["scheduling_date"], date.today().isoformat())
        self.assertIn("day_cutoff_iso", payload)
        self.assertEqual(payload["today_insight"]["kind"], "trouble_cards")
        self.assertEqual(len(payload["today_insight"]["items"]), 3)
        self.assertNotIn("browser_query", payload["today_insight"])
        self.assertNotIn("study_date", payload["today_insight"])

    def test_insight_payload_contains_sanitized_display_fields_but_no_controller_targets(self) -> None:
        snapshot = replace(
            sample_snapshot(),
            today_insight=DayInsight(
                date=date.today().isoformat(),
                study_date="2026-08-12",
                valid_answer_count=7,
                again_count=3,
                insight_kind="trouble_cards",
                items=[InsightItem("Visible prompt", "Parent::Child", 3, "Again ×3")],
                browse_action="trouble_cards",
                browser_query="cid:987654321",
            ),
        )
        output = render_dashboard(snapshot, self.config)
        payload = json.loads(re.search(r'<script type="application/json"[^>]*>(.*?)</script>', output).group(1))
        insight = payload["today_insight"]
        self.assertEqual(insight["valid_answer_count"], 7)
        self.assertEqual(insight["again_count"], 3)
        self.assertEqual(insight["items"][0]["primary_text"], "Visible prompt")
        self.assertNotIn("987654321", output)
        self.assertNotIn("browser_query", insight)

    def test_rollover_metadata_remains_in_payload_but_disclaimer_is_not_rendered(self) -> None:
        snapshot = replace(sample_snapshot(), scheduling_date="2026-08-14", day_cutoff_iso="2026-08-14T04:00-05:00")
        output = render_dashboard(snapshot, self.config)
        payload = json.loads(re.search(r'<script type="application/json"[^>]*>(.*?)</script>', output).group(1))
        self.assertEqual(payload["scheduling_date"], "2026-08-14")
        self.assertIn("Less", output)
        self.assertIn("More completed", output)
        self.assertIn("hdo-year-weekdays", output)
        self.assertNotIn("active study day", output.casefold())

    def test_calendar_payload_groups_multiple_active_events_and_excludes_archived(self) -> None:
        config = normalize_config({"events": {"items": [
            {"id": "a", "date": "2026-08-29", "name": "Alpha", "archived": False},
            {"id": "b", "date": "2026-08-29", "name": "Beta", "archived": False},
            {"id": "c", "date": "2026-08-29", "name": "Archived", "archived": True},
        ]}})
        output = render_dashboard(sample_snapshot(), config)
        script = re.search(r'<script type="application/json"[^>]*>(.*?)</script>', output).group(1)
        payload = json.loads(script)
        self.assertEqual([item["name"] for item in payload["events"]], ["Alpha", "Beta"])
        self.assertEqual({item["date"] for item in payload["events"]}, {"2026-08-29"})

    def test_activation_guard_names_enabled_legacy_addons(self) -> None:
        output = render_activation_required(["1771074083", "290511870"], self.config)
        self.assertIn("Review Heatmap", output)
        self.assertIn("Bible Verse Displayer", output)
        self.assertIn("paused", output)

    def test_large_preview_renders_quickly(self) -> None:
        started = time.perf_counter()
        output = render_dashboard(sample_snapshot(), self.config)
        self.assertLess(time.perf_counter() - started, 1.0)
        self.assertGreater(len(output), 10000)


if __name__ == "__main__":
    unittest.main()
