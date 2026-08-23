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

    def test_dashboard_order_is_calendar_metrics_then_bible(self) -> None:
        calendar = self.html.index("hdo-calendar-card")
        metrics = self.html.index("hdo-summary-metrics-grid")
        bible = self.html.index("hdo-bible-card")
        self.assertLess(calendar, metrics)
        self.assertLess(metrics, bible)

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
        self.assertIn('data-hdo-context-date', calendar)
        self.assertIn('data-hdo-open-events', calendar)
        self.assertIn('data-hdo-edit-event', calendar)
        self.assertIn('data-hdo-primary-action', calendar)
        self.assertIn('data-hdo-most-missed hidden', calendar)

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
            "Intl.NumberFormat",
            "Intl.PluralRules",
            'calendar.addEventListener("focusin"',
            "getBoundingClientRect()",
            "global.innerWidth",
            "global.innerHeight",
        ):
            self.assertIn(marker, self.js)
        self.assertIn("min-width: min(232px", self.css)
        self.assertIn("max-width: min(260px", self.css)
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

    def test_due_load_uses_one_robust_reference_and_view_specific_quiet_band(self) -> None:
        for marker in (
            "getDueLoadScale",
            "Math.ceil(positive.length * 0.9) - 1",
            "Math.sqrt(Math.min(count, robustReference) / robustReference)",
            'return view === "year" ? 100 : 6',
            'return "low"',
            'return "medium"',
            'return "high"',
            "due_load_reference",
        ):
            self.assertIn(marker, self.js + self.renderer)
        self.assertIn("modelCache: new Map()", self.js)
        self.assertIn("getDueOverlayHeight(due, state.dueReference, view)", self.js)
        self.assertIn("getDueLoadLevel(due, state.dueReference)", self.js)

    def test_calendar_state_hierarchy_has_distinct_visual_responsibilities(self) -> None:
        for marker in (
            ".hdo-calendar-day[data-level=",
            ".hdo-due-hatch",
            ".hdo-event-marker",
            ".is-today .hdo-date-number",
            ".hdo-calendar-day.is-selected",
            ".hdo-calendar-day:focus-visible",
            ".hdo-calendar-day.is-out-of-month",
        ):
            self.assertIn(marker, self.css)
        self.assertIn("height: 10px", self.css)
        self.assertIn("aspect-ratio: 1 / 1", self.css)
        year_marker = self.css.split(".hdo-calendar-grid--year .hdo-event-marker {", 1)[1].split("}", 1)[0]
        self.assertIn("height: 7px", year_marker)
        self.assertIn("width: 7px", year_marker)

    def test_metrics_use_only_four_two_or_one_columns(self) -> None:
        self.assertIn("grid-template-columns: minmax(0, 1fr);", self.css)
        self.assertIn("@container hdo-dashboard (min-width: 600px)", self.css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", self.css)
        self.assertIn("@container hdo-dashboard (min-width: 1100px)", self.css)
        self.assertIn("grid-template-columns: repeat(4, minmax(0, 1fr));", self.css)
        self.assertIn("@container hdo-dashboard (min-width: 1320px)", self.css)
        self.assertIn("grid-template-columns: minmax(760px, 1fr) minmax(500px, .46fr);", self.css)
        self.assertNotRegex(self.css, r"grid-template-columns:\s*repeat\(3")
        self.assertIn("font-variant-numeric: tabular-nums", self.css)

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
            'message.textContent = "Still loading your study data…"',
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
