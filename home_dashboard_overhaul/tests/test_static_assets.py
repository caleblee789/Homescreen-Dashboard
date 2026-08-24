from __future__ import annotations

from datetime import date
from pathlib import Path
import re
import unittest

from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.renderer import render_dashboard
from home_dashboard_overhaul.tests.fixtures import sample_snapshot


ROOT = Path(__file__).resolve().parents[1]


class CorrectedStaticAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.js = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "web" / "dashboard.css").read_text(encoding="utf-8")
        cls.renderer = (ROOT / "renderer.py").read_text(encoding="utf-8")
        cls.html = render_dashboard(
            sample_snapshot(date(2026, 8, 17)),
            normalize_config({}),
            anki_dark=True,
        )

    def test_dashboard_uses_one_shared_calendar_and_persistent_insight_rail(self) -> None:
        calendar = self.html.index("hdo-calendar-card")
        layout = self.html.index("hdo-dashboard-layout")
        rail = self.html.index("hdo-insight-rail")
        metrics = self.html.index("hdo-summary-metrics-grid")
        bible = self.html.index("hdo-bible-card")
        self.assertLess(layout, calendar)
        self.assertLess(calendar, metrics)
        self.assertLess(rail, metrics)
        self.assertLess(metrics, bible)
        self.assertEqual(self.html.count("hdo-dashboard-layout"), 1)
        self.assertEqual(self.html.count("hdo-insight-rail"), 1)

    def test_removed_dashboard_surfaces_leave_no_markup_or_reserved_slots(self) -> None:
        compact_sources = "\n".join((self.renderer, self.js, self.css, self.html)).casefold()
        for forbidden in (
            "hdo-selected-date-panel",
            "hdo-date-details",
            "hdo-due-deck",
            "hdo-insight-preview",
            "card-answer-preview",
            "expand preview",
            "browse these cards",
            "manage date",
        ):
            self.assertNotIn(forbidden, compact_sources)
        self.assertEqual(self.html.casefold().count("most missed"), 1)

    def test_context_bar_follows_legend_inside_the_calendar_card(self) -> None:
        calendar = self.html.split("hdo-calendar-card", 1)[1]
        self.assertLess(calendar.index("hdo-calendar-legend"), calendar.index("hdo-calendar-context-bar"))
        self.assertIn('class="hdo-calendar-footer"', calendar)
        self.assertIn('data-hdo-date-state', calendar)
        self.assertIn('data-hdo-context-date', calendar)
        self.assertIn('data-hdo-open-events', calendar)
        self.assertIn('data-hdo-event-meta', calendar)
        self.assertIn('data-hdo-event-empty', calendar)
        self.assertIn('data-hdo-edit-event', calendar)
        self.assertIn('data-hdo-primary-action', calendar)
        self.assertIn('data-hdo-most-missed hidden', calendar)
        self.assertRegex(
            self.css,
            r"\.hdo-next-event-line\s*\{[^}]*display:\s*flex;[^}]*flex-wrap:\s*nowrap;",
        )
        self.assertRegex(
            self.css,
            r"\.hdo-event-summary\s*\{[^}]*flex:\s*1 1 auto;",
        )
        self.assertIn("text-overflow: ellipsis", self.css)

    def test_compact_surfaces_omit_internal_boundary_copy_and_placeholders(self) -> None:
        sources = self.renderer + self.js
        for forbidden in (
            "Outside due forecast",
            "Outside study history",
            "No events",
            "Placeholder —",
        ):
            self.assertNotIn(forbidden, sources)

    def test_tooltip_is_conditional_locale_aware_focusable_and_collision_aware(self) -> None:
        for marker in (
            "buildCalendarTooltipRows",
            "tooltipPlacement",
            "Intl.NumberFormat",
            "Intl.PluralRules",
            'calendar.addEventListener("focusin"',
            "getBoundingClientRect()",
            "global.innerWidth",
            "global.innerHeight",
            "Math.max(0, cardBounds.left)",
            "Math.min(global.innerWidth, cardBounds.right)",
        ):
            self.assertIn(marker, self.js)
        self.assertIn("min-width: min(190px", self.css)
        self.assertIn("max-width: min(220px", self.css)
        self.assertIn("--hdo-tooltip-caret-left", self.css + self.js)
        tooltip_rule = self.css.split(".hdo-calendar-tooltip {", 1)[1].split("}", 1)[0]
        self.assertIn("pointer-events: none", tooltip_rule)

    def test_calendar_keyboard_and_roving_tabindex_contracts_are_present(self) -> None:
        for marker in (
            'role="grid"',
            "cell.tabIndex = dayIso === state.selected ? 0 : -1",
            'calendar.addEventListener("keydown"',
            'event.key === "Enter"',
            'event.key === " "',
            "var offsets = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }",
            'aria-rowindex',
            'aria-colindex',
        ):
            self.assertIn(marker, self.renderer + self.js)

    def test_due_load_uses_one_robust_reference_and_fixed_three_level_band(self) -> None:
        for marker in (
            "getDueLoadScale",
            "Math.ceil(positive.length * 0.9) - 1",
            "Math.sqrt(Math.min(count, robustReference) / robustReference)",
            "Math.ceil(scaled * 3)",
            "due_load_reference",
        ):
            self.assertIn(marker, self.js + self.renderer)
        self.assertIn("modelCache: new Map()", self.js)
        self.assertIn("getDueLoadLevel(due, state.dueReference)", self.js)
        self.assertNotIn("getDueOverlayHeight", self.js)
        self.assertNotIn("hdo-due-hatch", self.js + self.css)

    def test_calendar_state_hierarchy_has_distinct_visual_responsibilities(self) -> None:
        for marker in (
            ".hdo-calendar-day[data-level=",
            '.hdo-calendar-day.is-future[data-due-level="1"]',
            "var(--heat-due-mark-3)",
            ".hdo-event-marker",
            ".hdo-calendar-grid--month .hdo-calendar-day.is-today .hdo-date-number",
            ".hdo-calendar-grid--year .hdo-calendar-day.is-today::before",
            ".hdo-calendar-day.is-selected",
            ".hdo-calendar-day:focus-visible",
            ".hdo-calendar-day.is-out-of-month",
            ".hdo-calendar-day.is-out-of-month[data-due-level]",
        ):
            self.assertIn(marker, self.css)
        future_rule = self.css.split(".hdo-calendar-day.is-future {", 1)[1].split("}", 1)[0]
        self.assertIn("background: var(--calendar-empty-bg)", future_rule)
        self.assertNotIn("heat-due-bg", future_rule)
        self.assertIn("aspect-ratio: 1 / 1", self.css)
        selected_rule = self.css.split(".hdo-calendar-day.is-selected {", 1)[1].split("}", 1)[0]
        self.assertIn("outline: 2px solid var(--calendar-selected-ring)", selected_rule)
        self.assertIn("!important", selected_rule)
        self.assertNotIn("box-shadow", selected_rule)
        self.assertIn(".hdo-calendar-day.is-selected:focus-visible", self.css)
        for height in ("block-size: 2px", "block-size: 3px", "block-size: 4px"):
            self.assertIn(height, self.css)
        year_marker = self.css.split(".hdo-calendar-grid--year .hdo-event-marker {", 1)[1].split("}", 1)[0]
        self.assertIn("height: 4px", year_marker)
        self.assertIn("width: 4px", year_marker)

    def test_shared_shell_uses_release_container_breakpoints_and_geometry(self) -> None:
        self.assertIn("width: min(1320px, calc(100% - 32px))", self.css)
        self.assertIn("margin: 22px auto 0", self.css)
        self.assertIn("padding: 0 0 72px", self.css)
        self.assertIn("scroll-padding-bottom: 72px", self.css)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", self.css)
        self.assertIn("@container hdo-dashboard (min-width: 440px)", self.css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", self.css)
        self.assertIn("@container hdo-dashboard (min-width: 940px)", self.css)
        self.assertIn("grid-template-columns: minmax(0, 2.2fr) minmax(300px, 1fr);", self.css)
        self.assertIn("@container hdo-dashboard (max-width: 439px)", self.css)
        for retired in ("640px", "900px", "1220px"):
            self.assertNotIn("hdo-dashboard (min-width: {})".format(retired), self.css)
        self.assertNotIn('data-hdo-calendar-view="year"] .hdo-summary-metrics-grid', self.css)
        self.assertNotIn('data-hdo-calendar-view="month"] .hdo-summary-metrics-grid', self.css)
        self.assertNotRegex(self.css, r"grid-template-columns:\s*repeat\(3")
        self.assertIn("font-variant-numeric: tabular-nums", self.css)
        self.assertIn("grid-template-rows: repeat(4, auto)", self.css)
        stat_title_rule = self.css.split(".hdo-statistics-card h3 {", 1)[1].split("}", 1)[0]
        self.assertIn("font-size: calc(11px * var(--hdo-scale))", stat_title_rule)
        self.assertIn("white-space: nowrap", stat_title_rule)
        progress_title_rule = self.css.split(".hdo-progress-card h3 {", 1)[1].split("}", 1)[0]
        self.assertIn("letter-spacing: 0", progress_title_rule)
        progress_header_rule = self.css.split(
            ".hdo-progress-card .hdo-stat-card-header {", 1
        )[1].split("}", 1)[0]
        self.assertIn("flex-wrap: wrap", progress_header_rule)
        progress_chip_rule = self.css.split(
            ".hdo-progress-status-chip {", 1
        )[1].split("}", 1)[0]
        self.assertIn("max-width: 100%", progress_chip_rule)
        self.assertIn("overflow-wrap: anywhere", progress_chip_rule)
        self.assertIn("white-space: normal", progress_chip_rule)
        progress_rule = self.css.split(".hdo-progress-track {", 1)[1].split("}", 1)[0]
        self.assertIn("height: 14px", progress_rule)

    def test_live_canvas_is_transparent_while_cards_and_preview_remain_themed(self) -> None:
        root_rule = self.css.split("#hdo-dashboard {", 1)[1].split("}", 1)[0]
        preview_rule = self.css.split(
            "#hdo-dashboard.hdo-dashboard--preview {", 1
        )[1].split("}", 1)[0]
        apply_document_theme = self.js.split(
            "function applyDocumentTheme(root) {", 1
        )[1].split("function mount()", 1)[0]

        self.assertIn("background: transparent", root_rule)
        self.assertNotIn("\n#hdo-dashboard::before", self.css)
        self.assertIn("background: var(--ui-canvas)", preview_rule)
        self.assertIn("background: var(--ui-card-background)", self.css)
        self.assertNotIn("--ui-canvas", apply_document_theme)
        self.assertNotIn("style.background", apply_document_theme)
        self.assertNotIn("backgroundImage", apply_document_theme)
        self.assertIn('root.dataset.hdoHostPreserved = "true"', apply_document_theme)

    def test_year_grid_is_fluid_and_month_labels_use_week_columns(self) -> None:
        year = self.css.split(".hdo-calendar-grid--year {", 1)[1].split("}", 1)[0]
        dashboard_buttons = self.css.split("#hdo-dashboard button {", 1)[1].split("}", 1)[0]
        self.assertIn("22px repeat(var(--hdo-year-weeks, 53), minmax(0, 1fr))", year)
        self.assertIn("width: 100%", year)
        self.assertIn("min-width: 0", year)
        self.assertIn("margin: 0", dashboard_buttons)
        self.assertNotIn("repeat(var(--hdo-year-weeks, 53), max-content)", year)
        self.assertNotIn("transform: scale", self.css)
        self.assertIn("grid-column-start: var(--hdo-month-start-week)", self.css)
        self.assertIn('monthLabel.style.setProperty("--hdo-month-start-week"', self.js)
        self.assertIn("hdo-year-weekday-label", self.js + self.css)
        for label in ('label: "Mon"', 'label: "Wed"', 'label: "Fri"'):
            self.assertIn(label, self.js)
        self.assertEqual(self.css.count("overflow-x: auto"), 1)
        narrow_scroll = self.css.split("@container hdo-dashboard (max-width: 319px)", 1)[1]
        self.assertIn('data-hdo-calendar-view="year"] .hdo-calendar-grid-frame', narrow_scroll)
        self.assertIn("overflow-x: auto", narrow_scroll)

    def test_footer_is_compact_tonal_and_keeps_event_editing_adjacent(self) -> None:
        self.assertIn('grid-template-areas: "date event edit action"', self.css)
        compact = self.css.split("@container hdo-calendar (max-width: 699px)", 1)[1]
        self.assertIn('"date edit action"', compact)
        self.assertIn('"event event event"', compact)
        smallest = compact.split("@container hdo-calendar (max-width: 410px)", 1)[1].split(
            "@container hdo-calendar (max-width: 699px) and", 1
        )[0]
        self.assertIn('"date edit action"', smallest)
        self.assertIn('"event event event"', smallest)
        self.assertNotIn('"date date"', smallest)
        self.assertNotIn('"action action"', smallest)
        label_rule = self.css.split(".hdo-context-label {", 1)[1].split("}", 1)[0]
        self.assertIn("white-space: nowrap", label_rule)
        action_rule = self.css.split(".hdo-calendar-card-action {", 1)[1].split("}", 1)[0]
        self.assertIn("background: var(--ui-accent-soft)", action_rule)
        self.assertIn("border-color: var(--ui-accent-border)", action_rule)
        self.assertIn("height: 32px", action_rule)

    def test_no_component_specific_hex_colors_or_remote_dependencies(self) -> None:
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", self.css))
        self.assertNotIn("http://", self.css + self.js)
        self.assertNotIn("https://", self.css + self.js)
        self.assertTrue(all(
            selector.lstrip().startswith(("#hdo-dashboard", "@", "from", "to"))
            for selector in re.findall(r"(?:^|\n)([^{}]+)\{", self.css)
            if selector.strip()
        ))

    def test_loading_lifecycle_has_delayed_failure_retry_and_diagnostics_states(self) -> None:
        for marker in (
            "function mountLoadingState",
            'message.textContent = "Still loading your study data..."',
            "}, 2500)",
            "}, 12000)",
            'send("retry", {})',
            'send("diagnostics", {})',
            'root.setAttribute("aria-busy", "false")',
        ):
            self.assertIn(marker, self.js)
        for selector in (
            ".hdo-loading-layout",
            ".hdo-loading-region--calendar",
            ".hdo-loading-region--metrics",
            ".hdo-loading-failure",
            ".hdo-loading-actions",
        ):
            self.assertIn(selector, self.css)


if __name__ == "__main__":
    unittest.main()
