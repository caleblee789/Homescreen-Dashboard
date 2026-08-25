"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const model = require("../web/dashboard.js");

const available = (value) => ({ status: "available", value, reason: "" });
const unavailable = (reason) => ({ status: "unavailable", value: null, reason });

// Civil-date parsing and period geometry stay timezone-safe and exhaustive.
assert.strictEqual(model.isoDate(model.parseDate("2026-08-17")), "2026-08-17");
assert.strictEqual(model.parseDate("2026-02-29"), null);
assert.strictEqual(model.parseDate("2028-02-29") instanceof Date, true);
assert.strictEqual(model.parseDate("2026-2-9"), null);
assert.strictEqual(model.isoDate(model.addDays(model.parseDate("2026-12-31"), 1)), "2027-01-01");
assert.strictEqual(model.dayDifference(model.parseDate("2027-01-01"), model.parseDate("2026-12-31")), 1);

const fourWeek = model.monthRange(model.parseDate("2021-02-15"), 0);
const leapMonth = model.monthRange(model.parseDate("2028-02-15"), 0);
const sixWeek = model.monthRange(model.parseDate("2026-08-17"), 0);
assert.strictEqual(fourWeek.rows, 6);
assert.strictEqual(leapMonth.rows, 6);
assert.strictEqual(sixWeek.rows, 6);
for (let weekStart = 0; weekStart < 7; weekStart += 1) {
  const dates = model.calendarRangeDates("month", model.parseDate("2026-08-17"), weekStart);
  assert.strictEqual(dates.length, 42);
  assert.strictEqual(new Set(dates).size, dates.length);
}
assert.strictEqual(model.calendarRangeDates("year", model.parseDate("2026-08-17"), 0).length, 365);
assert.strictEqual(model.calendarRangeDates("year", model.parseDate("2028-08-17"), 0).length, 366);
assert.strictEqual(model.yearRange(model.parseDate("2026-08-17"), 0).weeks, 53);
const year2026 = model.calendarRangeDates("year", model.parseDate("2026-08-17"), 0);
assert.strictEqual(year2026[0], "2026-01-01");
assert.strictEqual(year2026[year2026.length - 1], "2026-12-31");
assert.strictEqual(model.isoDate(model.navigate(model.parseDate("2026-12-01"), "month", 1)), "2027-01-01");
assert.strictEqual(model.isoDate(model.navigate(model.parseDate("2026-08-01"), "year", -1)), "2025-08-01");

// Event grouping is inert, deterministic, and upcoming-event selection is
// relative to local Today—not the selected calendar date.
const events = [
  { id: "later", date: "2026-09-01", name: "Later event" },
  { id: "b", date: "2026-08-28", name: "Pediatric NBME" },
  { id: "a", date: "2026-08-28", name: "Alpha" },
  { id: "past", date: "2026-08-01", name: "Past" },
  { id: "invalid", date: "2026-02-30", name: "Invalid" },
  { id: "blank", date: "2026-08-19", name: "  " }
];
const grouped = model.groupEvents(events);
assert.deepStrictEqual(grouped["2026-08-28"].map((entry) => entry.name), ["Alpha", "Pediatric NBME"]);
assert.strictEqual(grouped["2026-02-30"], undefined);
const upcoming = model.getNextUpcomingEvent(events, "2026-08-17");
assert.strictEqual(upcoming.event.id, "a");
assert.strictEqual(upcoming.additional, 1);
assert.strictEqual(model.getNextUpcomingEvent(events, "2026-09-02"), null);
assert.deepStrictEqual(model.getContextEvent(events, "2026-08-28", "2026-08-17"), {
  event: { id: "a", date: "2026-08-28", name: "Alpha" },
  additional: 1,
  relationship: "On this date",
  kind: "selected"
});
assert.deepStrictEqual(model.getContextEvent(events, "2026-08-22", "2026-08-17"), {
  event: null,
  additional: 0,
  relationship: "No event on this date",
  kind: "empty_selected",
  upcoming: {
    event: { id: "a", date: "2026-08-28", name: "Alpha" },
    additional: 1
  }
});
assert.deepStrictEqual(model.getContextEvent(events, "2026-08-17", "2026-08-17"), {
  event: { id: "a", date: "2026-08-28", name: "Alpha" },
  additional: 1,
  relationship: "Next event",
  kind: "next"
});
assert.deepStrictEqual(model.getContextEvent([], "2026-08-17", "2026-08-17"), {
  event: null,
  additional: 0,
  relationship: "Next event",
  kind: "empty_today",
  upcoming: null
});
assert.strictEqual(model.formatSelectedDate("2026-08-22", "en-US"), "Sat, Aug 22, 2026");
assert.strictEqual(model.formatEventDate("2026-08-28", "2026-08-22", "en-US"), "Fri, Aug 28");
assert.strictEqual(model.formatCompactEventDate("2026-08-28", "2026-08-22", "en-US"), "Aug 28");
assert.strictEqual(model.eventCountdown("2026-08-28", "2026-08-22", "en-US"), "in 6 days");
assert.strictEqual(model.eventCountdownCompact("2026-08-28", "2026-08-22", "en-US"), "6d");
assert.strictEqual(model.dashboardDensity(1040), "wide");
assert.strictEqual(model.dashboardDensity(1039), "intermediate");
assert.strictEqual(model.dashboardDensity(420), "intermediate");
assert.strictEqual(model.dashboardDensity(419), "narrow");

// Exact selected-date action truth table.
function day(date, completed, due, again) {
  return {
    date,
    reviews_completed: completed,
    reviews_due: due,
    again_count: again,
    new_cards_studied: available(0),
    events: available([])
  };
}
const today = "2026-08-17";
assert.deepStrictEqual(
  model.getSelectedDateCapabilities(day("2026-08-07", available(5), unavailable("forecast_out_of_range"), available(1)), today),
  { primary: "reviewed", primaryEnabled: true, primaryReason: "", mostMissedCandidate: true }
);
assert.deepStrictEqual(
  model.getSelectedDateCapabilities(day("2026-08-07", available(0), unavailable("forecast_out_of_range"), available(0)), today),
  { primary: "reviewed", primaryEnabled: false, primaryReason: "No reviewed cards are available for this date.", mostMissedCandidate: false }
);
assert.deepStrictEqual(
  model.getSelectedDateCapabilities(day(today, available(5), available(12), available(0)), today),
  { primary: "reviewed", primaryEnabled: true, primaryReason: "", mostMissedCandidate: false }
);
assert.deepStrictEqual(
  model.getSelectedDateCapabilities(day(today, available(0), available(12), available(0)), today),
  { primary: "reviewed", primaryEnabled: false, primaryReason: "No reviewed cards are available for this date.", mostMissedCandidate: false }
);
assert.deepStrictEqual(
  model.getSelectedDateCapabilities(day("2026-08-18", unavailable("history_out_of_range"), available(12), unavailable("history_out_of_range")), today),
  { primary: "due", primaryEnabled: true, primaryReason: "", mostMissedCandidate: false }
);
assert.deepStrictEqual(
  model.getSelectedDateCapabilities(day("2026-08-18", unavailable("history_out_of_range"), available(0), unavailable("history_out_of_range")), today),
  { primary: "due", primaryEnabled: false, primaryReason: "No cards are due on this date.", mostMissedCandidate: false }
);
assert.deepStrictEqual(
  model.getSelectedDateCapabilities(day("2027-08-18", unavailable("history_out_of_range"), unavailable("forecast_out_of_range"), unavailable("history_out_of_range")), today),
  { primary: "due", primaryEnabled: false, primaryReason: "Due-card data is unavailable for this date.", mostMissedCandidate: false }
);

// Tooltip rows obey temporal applicability, omit unsupported data, and format
// singular/plural labels and locale numbers.
const pastTooltip = model.buildCalendarTooltipRows({
  date: "2026-08-07",
  reviews_completed: available(1),
  new_cards_studied: available(0),
  reviews_due: unavailable("forecast_out_of_range"),
  events: available([])
}, today, "en-US");
assert(pastTooltip.heading.includes("Aug"));
assert.deepStrictEqual(pastTooltip.rows.map((row) => row.label), ["Completed reviews", "New cards studied"]);
assert.deepStrictEqual(pastTooltip.rows.map((row) => row.value), ["1", "0"]);

const futureTooltip = model.buildCalendarTooltipRows({
  date: "2026-09-14",
  reviews_completed: unavailable("history_out_of_range"),
  new_cards_studied: unavailable("history_out_of_range"),
  reviews_due: available(1234),
  events: available([{ id: "exam", name: "Pediatric NBME", date: "2026-09-14" }])
}, today, "en-US");
assert.deepStrictEqual(futureTooltip.rows.map((row) => row.label), ["Reviews due", "Event"]);
assert.deepStrictEqual(futureTooltip.rows.map((row) => row.value), ["1,234", "Pediatric NBME"]);

const unsupportedTooltip = model.buildCalendarTooltipRows({
  date: "2027-09-14",
  reviews_completed: unavailable("history_out_of_range"),
  new_cards_studied: unavailable("history_out_of_range"),
  reviews_due: unavailable("forecast_out_of_range"),
  events: available([])
}, today, "en-US");
assert.deepStrictEqual(unsupportedTooltip.rows, []);
assert.strictEqual(model.pluralLabel(1, "en-US", "Card", "Cards"), "Card");
assert.strictEqual(model.pluralLabel(0, "en-US", "Card", "Cards"), "Cards");
assert.strictEqual(model.formatNumber(322120, "en-US"), "322,120");
assert.strictEqual(model.formatDurationCompact(42), "42s");
assert.strictEqual(model.formatDurationCompact(4920), "1h 22m");
assert.strictEqual(model.formatDurationCompact(313020), "86h 57m");

// Tooltip placement flips and clamps inside the visible calendar-card bounds.
assert.deepStrictEqual(
  model.tooltipPlacement(
    { left: 14, right: 26, top: 14, bottom: 26, width: 12, height: 12 },
    { width: 200, height: 90 },
    { left: 0, right: 500, top: 0, bottom: 300 },
    8,
    10
  ),
  { left: 8, top: 36, below: true, caretLeft: 14 }
);
assert.deepStrictEqual(
  model.tooltipPlacement(
    { left: 470, right: 482, top: 220, bottom: 232, width: 12, height: 12 },
    { width: 200, height: 90 },
    { left: 0, right: 500, top: 0, bottom: 300 },
    8,
    10
  ),
  { left: 292, top: 120, below: false, caretLeft: 184 }
);

// Robust due normalization ignores zeroes and caps outliers at p90.
assert.strictEqual(model.getDueLoadScale([0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10000]), 9);
assert.strictEqual(model.getDueLoadScale([0, 0, 0]), 0);
assert.strictEqual(model.getDueLoadScale([5, 5, 5]), 5);
assert.strictEqual(model.getDueLoadLevel(1, 100), 1);
assert.strictEqual(model.getDueLoadLevel(9, 100), 1);
assert.strictEqual(model.getDueLoadLevel(25, 100), 2);
assert.strictEqual(model.getDueLoadLevel(49, 100), 3);
assert.strictEqual(model.getDueLoadLevel(100, 100), 3);

// Target-aware rate colors remain neutral without a configured target and
// invert their success direction for Again rate.
assert.strictEqual(model.rateSemanticRole(92, 90, false), "success");
assert.strictEqual(model.rateSemanticRole(84, 90, false), "warning");
assert.strictEqual(model.rateSemanticRole(76, 90, false), "danger");
assert.strictEqual(model.rateSemanticRole(8, 10, true), "success");
assert.strictEqual(model.rateSemanticRole(14, 10, true), "warning");
assert.strictEqual(model.rateSemanticRole(24, 10, true), "danger");
assert.strictEqual(model.rateSemanticRole(92, null, false), "");

const thresholds = model.intensityThresholds([0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]);
assert.deepStrictEqual(thresholds, [2, 5, 13, 34, 89]);
assert.strictEqual(model.intensityLevel(0, thresholds), 0);
assert.strictEqual(model.intensityLevel(13, thresholds), 3);
assert.strictEqual(model.intensityLevel(1000, thresholds), 5);

// Source guards cover the shared interaction/performance architecture.
const js = fs.readFileSync(path.join(__dirname, "../web/dashboard.js"), "utf8");
const css = fs.readFileSync(path.join(__dirname, "../web/dashboard.css"), "utf8");
for (const forbidden of ["Outside due forecast", "Outside study history", "No events", "Select a date for details", "Expand preview"]) {
  assert(!js.includes(forbidden));
}
assert(js.includes('calendar.addEventListener("pointerover"'));
assert(js.includes('calendar.addEventListener("focusin"'));
assert(js.includes('calendar.addEventListener("keydown"'));
assert(!js.includes("cell.addEventListener"));
assert(js.includes("state.selected = isoDate(state.anchor)"));
assert(js.includes("modelCache: new Map()"));
assert(js.includes("state.mostMissed[day.date] = null"));
assert(css.includes("pointer-events: none"));
assert(css.includes("min-width: min(190px"));
assert(css.includes("max-width: min(220px"));
assert(css.includes("width: min(1120px, calc(100% - 40px))"));
assert(css.includes("grid-template-columns: minmax(0, 2.05fr) minmax(372px, .95fr)"));
assert(css.includes("@container hdo-dashboard (min-width: 420px)"));
assert(css.includes("@container hdo-dashboard (min-width: 1040px)"));
assert(css.includes("@container hdo-calendar (max-width: 419px)"));
assert(css.includes("@container hdo-dashboard (max-width: 479px)"));
assert(css.includes("28px repeat(var(--hdo-year-weeks, 53), minmax(0, 1fr))"));
assert(css.includes("18px repeat(var(--hdo-year-weeks, 53), minmax(0, 1fr))"));
assert(css.includes("min-width: 580px"));
assert(!css.includes("clamp(10px, 1cqi, 12px)"));
assert(js.includes('monthLabel.style.setProperty("--hdo-month-start-week"'));
assert(js.includes('primaryAction.textContent = "Reviewed cards"'));
assert(js.includes('primaryAction.textContent = "Due cards"'));
assert(js.includes('relationship: "On this date"'));
assert(js.includes("setButtonHidden(primaryAction, !capabilities.primaryEnabled)"));
assert(!js.includes("getDueOverlayHeight"));
assert(!js.includes("hdo-due-hatch"));
assert(css.includes('.hdo-calendar-day.is-future[data-due-level="1"]'));
assert(css.includes("background: var(--heat-due-mark-3)"));
assert(css.includes("block-size: 3px"));
assert(css.includes("block-size: 4px"));
assert(css.includes("block-size: 3px"));
assert(css.includes("block-size: 4px"));
assert(css.includes("background: var(--calendar-empty-bg)"));
assert(css.includes("outline: 2px solid var(--calendar-today-ring)"));
assert(js.includes('weekdayLabel.className = "hdo-year-weekday-label"'));
assert(js.includes("setYearScrollPosition"));
assert(js.includes("new Date(calendarToday.getFullYear(), calendarToday.getMonth(), 15)"));
assert(js.includes("state.yearScrollLeft = yearScrollFrame.scrollLeft"));
assert(js.includes("state.yearCenterRequested = true"));
assert(js.includes('send("calendar_year_scroll", { left: state.yearScrollLeft })'));
assert(!js.includes("keepSelectedYearCellVisible"));
assert(js.includes("document.scrollingElement"));
assert(js.includes("visibleBottomActionContainer"));
assert(js.includes("new global.ResizeObserver(update)"));
assert(js.includes("var footerHeight = candidate ? measured : 60"));
assert(js.includes("hdoFooterClearanceSource"));
assert(js.includes('relationship: "No event on this date"'));
assert(js.includes('editEvent.title = "Edit event"'));
assert(js.includes('editEvent.title = "Add event"'));
assert(js.includes("root.querySelector(\".hdo-refresh-warning\")"));
assert(js.includes("root.dataset.hdoLastUpdatedAt"));
assert(js.includes("global.ResizeObserver"));
assert(js.includes('state === "no_cards_scheduled"'));
assert(js.includes("presentation && presentation.progress"));
assert(js.includes("100 - Number(recent.retention.percent)"));
assert(js.includes("tooltipPlacement(targetRect, rect, bounds, margin, offset)"));

console.log("calendar model tests passed");
