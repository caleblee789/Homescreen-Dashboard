from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime
import json
from pathlib import Path
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
    LongTermStats,
    QueueStats,
    RateMetric,
    TodayStats,
    ValueState,
    VerseContent,
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

    def test_dashboard_hierarchy_is_one_shared_shell_and_persistent_rail_everywhere(self) -> None:
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
                    self.assertEqual(html.count("hdo-dashboard-layout"), 1)
                    self.assertEqual(html.count("hdo-insight-rail"), 1)
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
        due = html[html.index("hdo-legend-due"):html.index("hdo-calendar-context-bar")]
        self.assertEqual(completion.count("data-level="), 5)
        self.assertEqual(due.count("data-due-level="), 3)
        self.assertIn("Reviews due", due)
        self.assertIn("Completed reviews", html)
        self.assertIn('<span class="hdo-legend-endpoint">Low</span>', html)
        self.assertIn('<span class="hdo-legend-endpoint">High</span>', html)

    def test_context_bar_has_selected_event_and_only_contextual_action_shells(self) -> None:
        html = render_dashboard(self.snapshot, self.config)
        context = html[html.index("hdo-calendar-context-bar"):html.index("hdo-calendar-tooltip")]
        self.assertIn("hdo-calendar-footer", html)
        self.assertIn("hdo-selected-date-line", context)
        self.assertIn("hdo-date-state-chip", context)
        self.assertIn("data-hdo-date-state", context)
        self.assertIn("data-hdo-context-date", context)
        self.assertIn("data-hdo-open-events", context)
        self.assertIn("data-hdo-event-meta", context)
        self.assertIn("No upcoming event", context)
        self.assertIn("data-hdo-edit-event", context)
        self.assertIn("data-hdo-primary-action", context)
        self.assertIn("data-hdo-most-missed", context)
        self.assertNotIn("<strong>Selected date:</strong>", context)
        self.assertIn("aria-label=\"Edit event\"", context)
        self.assertIn("<svg", context)
        script = (Path(__file__).resolve().parents[1] / "web" / "dashboard.js").read_text()
        self.assertIn('primaryAction.textContent = "Reviewed cards"', script)
        self.assertIn('primaryAction.textContent = "Due cards"', script)
        self.assertIn("getContextEvent(state.events, state.selected, todayIso)", script)
        self.assertIn('eventContext ? eventContext.relationship : "Next event"', script)

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
        self.assertRegex(html, r'data-hdo-progress-state="in_progress"[^>]*>77%</span>')
        session = html[html.index("Today’s Session"):html.index("Last 7 Days")]
        for label in ("Cards studied", "New cards studied", "Time", "Pace", "ETA"):
            self.assertIn("<dt>{}</dt>".format(label), session)

    def test_progress_uses_queue_counts_for_empty_complete_and_tiny_states(self) -> None:
        def rendered(today: TodayStats, queue: QueueStats) -> str:
            facts = replace(
                self.snapshot.facts,
                today=ValueState.available(today),
                queue=ValueState.available(queue),
            )
            return render_dashboard(replace(self.snapshot, facts=facts), self.config)

        empty = rendered(TodayStats(), QueueStats())
        self.assertIn('data-hdo-progress-state="no_cards_due"', empty)
        self.assertIn('aria-label="No cards are due today.">No cards due</span>', empty)

        complete = rendered(TodayStats(7), QueueStats())
        self.assertIn('aria-valuenow="100"', complete)

        tiny = rendered(TodayStats(999), QueueStats(new=1, learning=1, review=1, total=999))
        self.assertIn('data-hdo-progress-segment="learning" data-hdo-progress-count="1"', tiny)
        self.assertIn("<dt>Total remaining</dt><dd data-hdo-metric=\"queue.total\">3</dd>", tiny)
        self.assertNotIn("is-visually-tiny", tiny)

    def test_progress_example_uses_one_310_card_denominator(self) -> None:
        facts = replace(
            self.snapshot.facts,
            today=ValueState.available(TodayStats(186, 14, 8_520, 26.5)),
            queue=ValueState.available(QueueStats(32, 14, 78, 124, 10_800)),
        )
        html = render_dashboard(replace(self.snapshot, facts=facts), self.config)
        self.assertIn('aria-valuenow="60"', html)
        self.assertIn("60% complete", html)
        self.assertRegex(html, r'aria-label="60% complete\.[^"]+">60%</span>')
        for key, count in (("completed", 186), ("new", 32), ("learning", 14), ("review", 78)):
            self.assertIn(
                'data-hdo-progress-segment="{}" data-hdo-progress-count="{}"'.format(key, count),
                html,
            )
        self.assertIn("Completed: 186 (60%)", html)

    def test_release_stress_values_and_long_verse_render_without_truncation(self) -> None:
        facts = replace(
            self.snapshot.facts,
            today=ValueState.available(TodayStats(12_486, 1_048, 12_486 * 125.4, 125.4)),
            queue=ValueState.available(QueueStats(32, 14, 78, 124, 10_800)),
            last_seven_days=ValueState.available(LastSevenDaysStats(
                cards_studied=12_486,
                new_cards_studied=1_048,
                retention=RateMetric.from_counts(11_237, 12_486),
                again_rate=RateMetric.from_counts(1_249, 12_486),
            )),
            long_term=ValueState.available(LongTermStats(
                average_reviews_per_active_day=12_486,
                current_streak=1_024,
                longest_streak=1_517,
                lifetime_retention=RateMetric.from_counts(974_376, 1_082_640),
                lifetime_cards_studied=1_082_640,
            )),
        )
        verse = VerseContent(
            "The steadfast love of the Lord never ceases; his mercies never come to an end; "
            "they are new every morning; great is your faithfulness, and your loving care "
            "continues through every season of patient study and service.",
            "Lamentations 3:22–23",
        )
        html = render_dashboard(replace(self.snapshot, facts=facts, verse=verse), self.config)
        for expected in (
            "12,486",
            "1,048",
            "125.4 sec/card",
            "1,024 days",
            "1,517 days",
            "1,082,640",
            "continues through every season of patient study and service.",
            "Lamentations 3:22–23",
        ):
            self.assertIn(expected, html)
        self.assertNotIn("text-overflow:ellipsis", html.replace(" ", ""))

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
        all_time = html[html.index("All Time"):]
        lifetime = re.search(r'<div class="hdo-metric-row ([^"]*)"[^>]*><dt>Lifetime retention</dt>', all_time)
        self.assertIsNotNone(lifetime)
        self.assertEqual(lifetime.group(1), "")

    def test_theme_styles_the_host_without_painting_its_background(self) -> None:
        html = render_dashboard(self.snapshot, self.config, anki_dark=False)
        self.assertLess(html.index('id="hdo-host-theme"'), html.index('id="hdo-dashboard"'))
        self.assertIn("html,body,#root,.dashboard-host,.dashboard-scroll-surface", html)
        host_style = html.split('<style id="hdo-host-theme">', 1)[1].split("</style>", 1)[0]
        host_rule = host_style.split("{", 1)[1].split("}", 1)[0]
        self.assertNotIn("background", host_rule)
        self.assertIn("color-scheme:light", html)
        self.assertIn('data-hdo-theme="Sapphire Glass"', html)
        self.assertIn('data-hdo-color-mode="light"', html)

    def test_unavailable_metrics_keep_stable_rows_and_zero_values_remain_neutral(self) -> None:
        facts = replace(
            self.snapshot.facts,
            last_seven_days=ValueState.unavailable(AvailabilityReason.QUERY_FAILED),
        )
        html = render_dashboard(replace(self.snapshot, facts=facts), self.config)
        self.assertIn("Last 7 Days", html)
        self.assertIn("Some dashboard data is unavailable", html)
        recent = html[html.index("Last 7 Days"):html.index("All Time")]
        for label in ("Cards studied", "New cards studied", "Retention", "Again rate"):
            self.assertIn("<dt>{}</dt>".format(label), recent)
        self.assertEqual(recent.count(">—</dd>"), 4)

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
        self.assertIn("<dt>Retention</dt>", recent)
        self.assertIn("<dt>Again rate</dt>", recent)
        self.assertEqual(recent.count(">—</dd>"), 2)
        self.assertNotIn("hdo-value--new", recent)

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
        self.assertEqual(payload["presentation"]["progress"]["state"], "in_progress")
        self.assertEqual(
            tuple(payload["presentation"]["today_session"]),
            ("cards_studied", "new_cards_studied", "time", "pace", "eta"),
        )

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
        self.assertIn("--heat-complete-5:{}".format(selected["heat_complete_5"]), html)
        self.assertIn("--heat-complete-text-5:{}".format(selected["heat_complete_text_5"]), html)
        self.assertRegex(html, r"--ui-card-background:#[0-9A-F]{6}")
        self.assertIn("data-hdo-high-contrast=\"false\"", html)

        high_contrast = deepcopy(self.config)
        high_contrast["appearance"].update({"preset": "High Contrast", "mode": "light", "opacity": 70})
        high_html = render_dashboard(self.snapshot, high_contrast, anki_dark=False)
        self.assertIn("--ui-card-background:#FFFFFF", high_html)

    def test_bible_preference_maps_to_safe_clamp_and_hiding_removes_rail_slot(self) -> None:
        config = deepcopy(self.config)
        config["bible"]["font_size"] = "96px"
        html = render_dashboard(self.snapshot, config)
        self.assertIn("--hdo-verse-size:19.00px", html)
        self.assertIn("--hdo-verse-long-size:17.10px", html)

        config["visibility"]["bible"] = False
        hidden = render_dashboard(self.snapshot, config)
        self.assertNotIn("hdo-bible-card", hidden)
        self.assertIn('data-hdo-has-metrics="true" data-hdo-has-bible="false"', hidden)

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
        self.assertEqual(_eta(None, None, now), "—")
        self.assertEqual(_eta(0, 0, now), "—")
        self.assertEqual(_eta(0, 7, now), "Done")
        self.assertIn("PM", _eta(60, 7, now))
        self.assertTrue(_eta(7200, 7, now).startswith("Tomorrow,"))


if __name__ == "__main__":
    unittest.main()
