from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime
import json
import re
import unittest

from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.models import (
    AvailabilityReason,
    BrowseTarget,
    BrowseTargetKind,
    DashboardSnapshot,
    DayInsight,
    LastSevenDaysStats,
    QueueStats,
    RateMetric,
    TodayStats,
    ValueState,
)
from home_dashboard_overhaul.renderer import (
    _eta,
    calendar_range_payload,
    dashboard_facts_payload,
    day_insight_payload,
    render_activation_required,
    render_dashboard,
    render_loading,
)
from home_dashboard_overhaul.tests.fixtures import sample_snapshot
from home_dashboard_overhaul.themes import HEATMAP_PRESETS


def payload_from(html: str) -> dict:
    match = re.search(
        r'<script type="application/json" class="(?:hdo-calendar-data|hdo-dashboard-data)">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("dashboard JSON payload missing")
    return json.loads(match.group(1))


class RendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = sample_snapshot(date(2026, 8, 17))
        self.config = normalize_config({})

    def test_dashboard_hierarchy_is_calendar_metrics_then_bible_everywhere(self) -> None:
        for view in ("month", "year"):
            for preview in (False, True):
                with self.subTest(view=view, preview=preview):
                    config = deepcopy(self.config)
                    config["heatmap"]["calendar_view"] = view
                    html = render_dashboard(self.snapshot, config, preview=preview)
                    calendar = html.index("hdo-calendar-card")
                    metrics = html.index("hdo-summary-metrics-grid")
                    bible = html.index("hdo-bible-card")
                    self.assertLess(calendar, metrics)
                    self.assertLess(metrics, bible)
                    self.assertEqual(html.count("hdo-calendar-context-bar"), 1)
                    self.assertEqual(html.count("hdo-summary-metrics-grid"), 1)
                    self.assertEqual(html.count("hdo-bible-card"), 1)

    def test_removed_dashboard_surfaces_and_copy_are_absent(self) -> None:
        html = render_dashboard(self.snapshot, self.config)
        for forbidden in (
            "selected-date-details", "Select a date for details", "due-deck",
            "MOST MISSED", "Expand preview", "Open in Browser", "Manage date",
            "Outside due forecast", "Outside study history", "No events", "&mdash;",
        ):
            self.assertNotIn(forbidden, html)
        self.assertNotIn("card_id", html)
        self.assertNotIn("card_ids", html)
        self.assertNotIn("browser_token", html)
        self.assertNotIn("browse_target", html)
        self.assertIn("data-hdo-most-missed", html)

    def test_calendar_contains_separate_completion_and_three_level_due_legends(self) -> None:
        html = render_dashboard(self.snapshot, self.config)
        completion = html[html.index("hdo-completion-legend"):html.index("hdo-due-legend")]
        due = html[html.index("hdo-due-legend"):html.index("hdo-calendar-context-bar")]
        self.assertEqual(completion.count("data-level="), 5)
        self.assertEqual(due.count("data-load="), 3)
        self.assertIn("Reviews due", due)

    def test_context_bar_has_selected_event_and_only_contextual_action_shells(self) -> None:
        html = render_dashboard(self.snapshot, self.config)
        context = html[html.index("hdo-calendar-context-bar"):html.index("hdo-calendar-tooltip")]
        self.assertIn("data-hdo-context-date", context)
        self.assertIn("data-hdo-open-events", context)
        self.assertIn("data-hdo-edit-event", context)
        self.assertIn("data-hdo-primary-action", context)
        self.assertIn("data-hdo-most-missed", context)
        self.assertIn("<strong>Selected date:</strong>", context)
        self.assertIn("aria-label=\"Edit event\"", context)

    def test_metric_group_order_rows_and_number_formatting(self) -> None:
        html = render_dashboard(self.snapshot, self.config)
        group_titles = [
            html.index("Today’s Progress"),
            html.index("Today’s Session"),
            html.index("Last 7 Days"),
            html.index("All Time"),
        ]
        self.assertEqual(group_titles, sorted(group_titles))
        recent = html[html.index("Last 7 Days"):html.index("All Time")]
        self.assertLess(recent.index("Cards studied"), recent.index("New cards studied"))
        self.assertLess(recent.index("New cards studied"), recent.index("Retention"))
        self.assertIn("1,754", recent)
        self.assertIn("312", recent)
        self.assertIn("322,120", html)
        self.assertIn("Avg cards/day", html)
        self.assertNotIn("Avg cards / day", html)
        self.assertNotIn("<dt>Active days</dt>", html)
        self.assertNotIn("<dt>Percent complete</dt>", html)
        self.assertIn("data-hdo-progress-track", html)
        self.assertEqual(html.count("data-hdo-progress-segment="), 4)
        self.assertIn("77% complete", html)

    def test_progress_uses_queue_counts_for_empty_complete_and_tiny_states(self) -> None:
        def rendered(today: TodayStats, queue: QueueStats) -> str:
            facts = replace(
                self.snapshot.facts,
                today=ValueState.available(today),
                queue=ValueState.available(queue),
            )
            return render_dashboard(replace(self.snapshot, facts=facts), self.config)

        empty = rendered(TodayStats(), QueueStats())
        self.assertIn("No workload today. 0% complete.", empty)

        complete = rendered(TodayStats(7), QueueStats())
        self.assertIn('aria-valuenow="100"', complete)

        tiny = rendered(TodayStats(999), QueueStats(new=1, learning=1, review=1, total=999))
        self.assertIn('data-hdo-progress-segment="learning" data-hdo-progress-count="1"', tiny)
        self.assertIn("<dt>Total remaining</dt><dd data-hdo-metric=\"queue.total\">3</dd>", tiny)

    def test_eta_is_neutral_and_retention_is_target_aware(self) -> None:
        html = render_dashboard(self.snapshot, self.config)
        eta_row = re.search(r'<div class="hdo-metric-row ([^"]*)"[^>]*><dt>ETA</dt>', html)
        self.assertIsNotNone(eta_row)
        self.assertIn("hdo-value--estimate", eta_row.group(1))
        self.assertNotIn("success", eta_row.group(1))
        recent = html[html.index("Last 7 Days"):html.index("All Time")]
        self.assertIn('<div class="hdo-metric-row hdo-value--warning"', recent)
        lower_target = deepcopy(self.config)
        lower_target["study"]["retention_target"] = 75
        lower_html = render_dashboard(self.snapshot, lower_target)
        lower_recent = lower_html[lower_html.index("Last 7 Days"):lower_html.index("All Time")]
        self.assertIn('<div class="hdo-metric-row hdo-value--success"', lower_recent)

    def test_unavailable_metrics_are_omitted_and_zero_values_remain(self) -> None:
        facts = replace(
            self.snapshot.facts,
            last_seven_days=ValueState.unavailable(AvailabilityReason.QUERY_FAILED),
        )
        html = render_dashboard(replace(self.snapshot, facts=facts), self.config)
        self.assertNotIn("Last 7 Days", html)
        self.assertIn("Some dashboard data is unavailable", html)
        self.assertNotIn("—", html)

        zero_recent = LastSevenDaysStats(
            cards_studied=0,
            new_cards_studied=0,
            retention=RateMetric(),
            again_rate=RateMetric(),
        )
        zero_html = render_dashboard(
            replace(self.snapshot, facts=replace(
                self.snapshot.facts,
                last_seven_days=ValueState.available(zero_recent),
            )),
            self.config,
        )
        recent = zero_html[zero_html.index("Last 7 Days"):zero_html.index("All Time")]
        self.assertEqual(recent.count(">0</dd>"), 2)
        self.assertNotIn("Retention", recent)
        self.assertNotIn("Again rate", recent)

    def test_payload_is_capability_only_and_escapes_script_delimiters(self) -> None:
        event = replace(
            self.snapshot.facts.events.value[0],
            name="</script><img src=x onerror=alert(1)>",
        )
        facts = replace(self.snapshot.facts, events=ValueState.available((event,)))
        html = render_dashboard(replace(self.snapshot, facts=facts), self.config)
        self.assertNotIn("</script><img", html)
        self.assertIn("\\u003c/script\\u003e", html)
        payload = payload_from(html)
        self.assertEqual(payload["events"]["value"][0]["name"], event.name)
        encoded = json.dumps(payload)
        for forbidden in ("card_ids", "browse_target", "browser_token", "primary_text", "secondary_text"):
            self.assertNotIn(forbidden, encoded)
        self.assertIsInstance(payload["due_load_reference"], float)

    def test_day_insight_callback_contains_no_native_ids_or_preview_content(self) -> None:
        facts = self.snapshot.facts.for_date("2026-08-17")
        insight = DayInsight(
            date=facts.date,
            browse_target=facts.most_missed_target,
            day_facts=facts,
        )
        payload = day_insight_payload(insight)
        self.assertEqual(payload, {
            "date": "2026-08-17",
            "state": "trouble",
            "most_missed_available": True,
        })
        self.assertNotIn("100002", json.dumps(payload))

    def test_calendar_range_month_and_year_share_one_due_reference(self) -> None:
        month = calendar_range_payload(self.snapshot, "2026-08-17", "month", 0)
        year = calendar_range_payload(self.snapshot, "2026-08-17", "year", 0)
        self.assertEqual(len(month["activity"]), 42)
        self.assertEqual(len(year["activity"]), 365)
        month_payload = dashboard_facts_payload(
            self.snapshot,
            {**self.config, "heatmap": {**self.config["heatmap"], "calendar_view": "month"}},
        )
        year_payload = dashboard_facts_payload(self.snapshot, self.config)
        self.assertEqual(month_payload["due_load_reference"], year_payload["due_load_reference"])
        self.assertEqual(month_payload["due_load_reference"], self.snapshot.facts.due_load_reference)

    def test_selected_heatmap_tokens_and_safe_opacity_are_rendered(self) -> None:
        config = deepcopy(self.config)
        config["appearance"].update({"preset": "Graphite", "mode": "dark", "opacity": 70})
        config["heatmap"]["presets_by_theme"]["Graphite"] = "Plum"
        html = render_dashboard(self.snapshot, config, anki_dark=False)
        selected = HEATMAP_PRESETS["Graphite"]["Plum"]["dark"]
        self.assertIn("--hdo-heatmap-5:{}".format(selected["heatmap_5"]), html)
        self.assertIn("--hdo-on-heatmap-5:{}".format(selected["on_heatmap_5"]), html)
        self.assertRegex(html, r"--hdo-panel-background:rgba\([^;]+,0\.91\)")
        self.assertIn("data-hdo-high-contrast=\"false\"", html)

    def test_preview_reuses_the_production_components(self) -> None:
        normal = render_dashboard(self.snapshot, self.config)
        preview = render_dashboard(self.snapshot, self.config, preview=True)
        for marker in (
            "hdo-calendar-card", "hdo-calendar-context-bar", "hdo-summary-metrics-grid",
            "hdo-bible-card", "data-hdo-calendar-data",
        ):
            if marker == "data-hdo-calendar-data":
                continue
            self.assertEqual(normal.count(marker), preview.count(marker))
        self.assertIn("hdo-dashboard--preview", preview)
        self.assertIn('data-hdo-preview="true"', preview)
        self.assertIn('data-hdo-runtime-stack="false"', preview)

    def test_recovery_loading_and_activation_surfaces_remain_safe(self) -> None:
        hidden = deepcopy(self.config)
        hidden["visibility"].update({
            "heatmap": False,
            "remaining": False,
            "today": False,
            "heatmap_metrics": False,
            "bible": False,
        })
        self.assertIn("Dashboard sections are hidden", render_dashboard(self.snapshot, hidden))
        self.assertIn("Open settings", render_dashboard(self.snapshot, hidden))
        loading = render_loading(self.config)
        self.assertIn("Loading your study dashboard", loading)
        self.assertIn('aria-busy="true"', loading)
        calendar_region = loading.split('hdo-loading-region--calendar">', 1)[1].split(
            "</div>", 1
        )[0]
        metrics_region = loading.split('hdo-loading-region--metrics">', 1)[1].split(
            "</div>", 1
        )[0]
        self.assertEqual(calendar_region.count("<span></span>"), 28)
        self.assertEqual(metrics_region.count("<span></span>"), 4)
        self.assertIn('data-hdo-loading-message', loading)
        self.assertIn('data-hdo-loading-failure hidden', loading)
        self.assertIn("The dashboard could not finish loading.", loading)
        self.assertIn('data-hdo-command="retry"', loading)
        self.assertIn('data-hdo-command="diagnostics"', loading)
        activation = render_activation_required(["1771074083"], self.config)
        self.assertIn("Review Heatmap", activation)
        self.assertNotIn("1771074083", activation)

    def test_eta_formatter_handles_done_same_day_and_rollover(self) -> None:
        now = datetime(2026, 8, 17, 22, 30).astimezone()
        self.assertEqual(_eta(None, now), "")
        self.assertEqual(_eta(0, now), "Done")
        self.assertIn("PM", _eta(60, now))
        self.assertTrue(_eta(7200, now).startswith("Tomorrow,"))


if __name__ == "__main__":
    unittest.main()
