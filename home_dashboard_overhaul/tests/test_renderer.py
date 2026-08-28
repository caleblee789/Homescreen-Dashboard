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
    _duration,
    _duration_compact,
    _eta,
    calendar_range_payload,
    dashboard_facts_payload,
    day_insight_payload,
    render_activation_required,
    render_dashboard,
    render_failure,
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
        self.assertEqual(completion.count("data-level="), 6)
        self.assertEqual(due.count("data-due-level="), 3)
        self.assertIn("Due cards", due)
        self.assertIn("Completed reviews", html)
        self.assertIn('<span class="hdo-legend-endpoint">Low</span>', html)
        self.assertIn('<span class="hdo-legend-endpoint">High</span>', html)

        disabled = deepcopy(self.config)
        disabled["visibility"]["events"] = False
        disabled["heatmap"]["show_due_forecast"] = False
        disabled_html = render_dashboard(self.snapshot, disabled)
        self.assertNotIn("hdo-legend-due", disabled_html)
        self.assertNotIn("hdo-legend-event", disabled_html)
        self.assertNotIn("hdo-calendar-footer__event", disabled_html)
        self.assertIn("hdo-calendar-footer__date-context", disabled_html)

    def test_context_bar_has_selected_event_and_only_contextual_action_shells(self) -> None:
        html = render_dashboard(self.snapshot, self.config)
        context = html[html.index("hdo-calendar-context-bar"):html.index("hdo-calendar-tooltip")]
        self.assertIn("hdo-calendar-footer", html)
        self.assertIn("hdo-selected-date-line", context)
        self.assertIn("hdo-calendar-footer__date-context", context)
        self.assertIn("hdo-calendar-footer__event", context)
        self.assertIn("hdo-calendar-footer__actions", context)
        self.assertIn("hdo-date-state-chip", context)
        self.assertIn("data-hdo-date-state", context)
        self.assertIn("data-hdo-context-date", context)
        self.assertIn("data-hdo-event-rows", context)
        self.assertIn("data-hdo-context-event-label", context)
        self.assertIn("No upcoming event", context)
        self.assertIn("data-hdo-primary-action", context)
        self.assertIn("data-hdo-most-missed", context)
        self.assertNotIn("<strong>Selected date:</strong>", context)
        script = (Path(__file__).resolve().parents[1] / "web" / "dashboard.js").read_text()
        self.assertIn('primaryAction.textContent = "Reviewed cards"', script)
        self.assertIn('primaryAction.textContent = "Due cards"', script)
        self.assertIn("getContextEvent(state.events, state.selected, todayIso)", script)
        self.assertIn('relationship: "Next event"', script)
        self.assertIn('relationship: "Events on this date"', script)
        self.assertIn('edit.dataset.hdoEditEvent = ""', script)
        self.assertIn('items.slice(0, 2)', script)
        self.assertIn('" more"', script)

    def test_refresh_failure_uses_one_last_updated_banner(self) -> None:
        html = render_dashboard(
            self.snapshot,
            self.config,
            refresh_error=True,
            last_updated_at="2026-08-23T20:14:00-05:00",
        )
        self.assertEqual(html.count("hdo-refresh-warning"), 1)
        self.assertEqual(html.count("Refresh failed. Showing data last updated at"), 1)
        self.assertIn('data-hdo-last-updated-at="2026-08-23T20:14:00-05:00"', html)

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
        self.assertNotIn("data-hdo-progress-segment=", html)
        self.assertRegex(html, r'data-hdo-progress-state="in_progress"[^>]*aria-valuenow="77"')
        self.assertIn(">77%</span>", html)
        self.assertNotIn("data-hdo-progress-label", html)
        session = html[html.index("Today’s Session"):html.index("Last 7 Days")]
        for label in (
            "Cards studied", "New cards studied", "Cards buried",
            "Time spent", "Pace", "ETA",
        ):
            self.assertIn("<dt>{}</dt>".format(label), session)
        self.assertNotIn("<dt>Buried</dt>", html[html.index("Today’s Progress"):html.index("Today’s Session")])

    def test_progress_distinguishes_fresh_clear_complete_in_progress_and_unavailable(self) -> None:
        def rendered(
            today: TodayStats,
            queue: ValueState[QueueStats],
            *,
            history: bool = True,
        ) -> str:
            recent = self.snapshot.facts.last_seven_days
            lifetime = self.snapshot.facts.long_term
            if not history:
                recent = ValueState.available(LastSevenDaysStats())
                lifetime = ValueState.available(LongTermStats())
            facts = replace(
                self.snapshot.facts,
                today=ValueState.available(today),
                queue=queue,
                last_seven_days=recent,
                long_term=lifetime,
            )
            return render_dashboard(replace(self.snapshot, facts=facts), self.config)

        fresh = rendered(TodayStats(), ValueState.available(QueueStats()), history=False)
        self.assertIn('data-hdo-progress-state="no_cards_scheduled"', fresh)
        self.assertIn('>No cards scheduled</span>', fresh)
        self.assertIn('data-hdo-progress-track data-hdo-progress-state="no_cards_scheduled"', fresh)
        self.assertIn('aria-valuetext="No cards scheduled" hidden', fresh)

        clear = rendered(TodayStats(), ValueState.available(QueueStats()))
        self.assertIn('data-hdo-progress-state="all_clear"', clear)
        self.assertIn('>All clear</span>', clear)

        complete = rendered(TodayStats(7), ValueState.available(QueueStats()))
        self.assertIn('data-hdo-progress-state="complete"', complete)
        self.assertIn('aria-valuenow="100"', complete)
        self.assertIn('>100%</span>', complete)

        tiny = rendered(
            TodayStats(999),
            ValueState.available(QueueStats(new=1, learning=1, review=1, total=3)),
        )
        self.assertIn("<dt>Total remaining</dt><dd data-hdo-metric=\"queue.total\">3</dd>", tiny)
        self.assertNotIn("data-hdo-progress-segment", tiny)

        with self.assertRaisesRegex(ValueError, "queue total"):
            QueueStats(new=1, learning=1, review=1, total=999)

        unavailable = rendered(
            TodayStats(7),
            ValueState.unavailable(AvailabilityReason.QUERY_FAILED),
        )
        self.assertIn('data-hdo-progress-state="unavailable"', unavailable)
        self.assertIn('>Unavailable</span>', unavailable)
        self.assertNotIn('aria-valuetext="0% complete"', unavailable)

    def test_progress_example_uses_one_310_card_denominator(self) -> None:
        facts = replace(
            self.snapshot.facts,
            today=ValueState.available(TodayStats(186, 14, 8_520, 26.5)),
            queue=ValueState.available(QueueStats(32, 14, 78, 124, 10_800)),
        )
        html = render_dashboard(replace(self.snapshot, facts=facts), self.config)
        self.assertIn('aria-valuenow="60"', html)
        self.assertIn("60% complete", html)
        self.assertIn('aria-valuetext="60% complete"', html)
        self.assertIn('--hdo-progress-percent:60%', html)
        self.assertNotIn("data-hdo-progress-segment", html)

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
        lifetime = re.search(r'<div class="hdo-metric-row ([^"]*)"[^>]*><dt>Retention</dt>', all_time)
        self.assertIsNotNone(lifetime)
        self.assertEqual(lifetime.group(1), "")

    def test_native_retention_regression_renders_86_and_complementary_14(self) -> None:
        recent = LastSevenDaysStats(
            cards_studied=1_184,
            new_cards_studied=84,
            retention=RateMetric.from_counts(947, 1_100),
            again_rate=RateMetric.from_counts(153, 1_100),
        )
        facts = replace(
            self.snapshot.facts,
            last_seven_days=ValueState.available(recent),
        )
        html = render_dashboard(replace(self.snapshot, facts=facts), self.config)
        section = html[html.index("Last 7 Days"):html.index("All Time")]

        self.assertIn('<dt>Retention</dt><dd data-hdo-metric="last_seven_days.retention">86%</dd>', section)
        self.assertIn('<dt>Again rate</dt><dd data-hdo-metric="last_seven_days.again_rate">14%</dd>', section)
        self.assertNotIn(">80%</dd>", section)

    def test_theme_preserves_the_entire_host_canvas(self) -> None:
        html = render_dashboard(self.snapshot, self.config, anki_dark=False)
        self.assertNotIn('id="hdo-host-theme"', html)
        self.assertNotIn("html,body,#root", html)
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
        self.assertEqual(recent.count(">N/A</dd>"), 2)
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
        self.assertEqual(payload["presentation"]["progress"], {
            "status": "in_progress",
            "fill_percent": 77,
        })
        self.assertEqual(
            tuple(payload["presentation"]["today_session"]),
            (
                "cards_studied", "new_cards_studied", "cards_buried",
                "time_spent", "pace", "eta",
            ),
        )
        self.assertEqual(payload["presentation"]["today_session"]["cards_buried"], "12")
        self.assertEqual(payload["presentation"]["today_session"]["time_spent"], "4 hr 6 min")

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
        self.assertEqual(month_payload["statistics"], year_payload["statistics"])

        initial = payload_from(render_dashboard(self.snapshot, self.config, preview=False))
        preview = payload_from(render_dashboard(self.snapshot, self.config, preview=True))
        self.assertEqual(initial["statistics"], preview["statistics"])
        self.assertEqual(initial["presentation"], preview["presentation"])

    def test_selected_heatmap_tokens_and_safe_opacity_are_rendered(self) -> None:
        config = deepcopy(self.config)
        config["appearance"].update({"preset": "Graphite", "mode": "dark", "opacity": 94})
        config["heatmap"]["presets_by_theme"]["Graphite"] = "Plum"
        html = render_dashboard(self.snapshot, config, anki_dark=False)
        selected = HEATMAP_PRESETS["Graphite"]["Plum"]["dark"]
        self.assertIn("--heat-complete-5:{}".format(selected["heat_complete_5"]), html)
        self.assertIn("--heat-complete-text-5:{}".format(selected["heat_complete_text_5"]), html)
        self.assertRegex(html, r"--ui-card-background:#[0-9A-F]{6}")
        self.assertIn("data-hdo-high-contrast=\"false\"", html)

        high_contrast = deepcopy(self.config)
        high_contrast["appearance"].update({"preset": "High Contrast", "mode": "light", "opacity": 94})
        high_html = render_dashboard(self.snapshot, high_contrast, anki_dark=False)
        self.assertIn("--ui-card-background:#FFFFFF", high_html)
        self.assertIn("--hdo-card-backdrop-filter:none", high_html)

        sapphire = deepcopy(self.config)
        sapphire["appearance"].update({"preset": "Sapphire Glass", "mode": "light", "opacity": 96, "blur": 12})
        sapphire_html = render_dashboard(self.snapshot, sapphire, anki_dark=False)
        self.assertIn("rgba(255, 255, 255, 0.96)", sapphire_html)
        self.assertIn("--hdo-card-backdrop-filter:blur(12px) saturate(1.08)", sapphire_html)

    def test_bible_preference_renders_exact_size_and_hiding_removes_rail_slot(self) -> None:
        config = deepcopy(self.config)
        config["bible"]["font_size"] = "96px"
        html = render_dashboard(self.snapshot, config)
        self.assertIn("--hdo-verse-size:96.00px", html)
        self.assertIn('class="hdo-verse hdo-verse--medium"', html)

        short = render_dashboard(
            replace(self.snapshot, verse=VerseContent("Faith.", "Hebrews 11:1")),
            config,
        )
        self.assertIn('class="hdo-verse hdo-verse--short"', short)
        self.assertIn("--hdo-verse-size:96.00px", short)

        long = render_dashboard(
            replace(self.snapshot, verse=VerseContent("Grace " * 50, "Reference")),
            config,
        )
        self.assertIn('class="hdo-verse hdo-verse--long"', long)
        self.assertIn("--hdo-verse-size:96.00px", long)

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
        calendar_grid = loading.split('hdo-loading-calendar-grid">', 1)[1].split(
            "</div>", 1
        )[0]
        self.assertEqual(calendar_grid.count("<span></span>"), 53)
        self.assertEqual(loading.count("hdo-loading-metric-card"), 4)
        self.assertIn('data-hdo-loading-message', loading)
        self.assertIn('data-hdo-loading-failure hidden', loading)
        self.assertIn("Dashboard could not load", loading)
        self.assertIn(
            "The dashboard data could not be loaded. Retry or open diagnostics for details.",
            loading,
        )
        self.assertIn('data-hdo-command="retry"', loading)
        self.assertIn('data-hdo-command="diagnostics"', loading)
        failure = render_failure(self.config)
        self.assertIn('data-hdo-load-state="failure" aria-busy="false"', failure)
        self.assertIn('data-hdo-loading-skeleton aria-hidden="true" hidden', failure)
        self.assertNotIn('data-hdo-loading-failure hidden', failure)
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

    def test_time_formatting_uses_readable_and_compact_presentations(self) -> None:
        self.assertEqual(_duration(0), "0 min")
        self.assertEqual(_duration(42), "42 sec")
        self.assertEqual(_duration(4_920), "1 hr 22 min")
        self.assertEqual(_duration(313_020), "86 hr 57 min")
        self.assertEqual(_duration_compact(4_920), "1h 22m")
        self.assertEqual(_duration_compact(313_020), "86h 57m")


if __name__ == "__main__":
    unittest.main()
