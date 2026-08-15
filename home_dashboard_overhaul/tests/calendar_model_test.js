"use strict";

const assert = require("assert");
const model = require("../web/dashboard.js");

const year = model.yearRange(new Date(2026, 0, 1), 0);
assert.strictEqual(year.weeks, 53);
assert.strictEqual(model.isoDate(year.start), "2026-01-01");
assert.strictEqual(model.isoDate(year.end), "2026-12-31");

const february = model.monthRange(new Date(2026, 1, 1), 0);
const januaryLeap = model.monthRange(new Date(2028, 0, 1), 0);
const februaryLeap = model.monthRange(new Date(2028, 1, 1), 0);
assert.strictEqual(february.weeks, 5);
assert.strictEqual(januaryLeap.weeks, 6);
assert.strictEqual(model.isoDate(januaryLeap.end), "2028-01-31");
assert.strictEqual(model.isoDate(februaryLeap.end), "2028-02-29");

assert.strictEqual(model.isoDate(model.navigate(new Date(2026, 11, 1), "month", 1)), "2027-01-01");
assert.strictEqual(model.isoDate(model.navigate(new Date(2026, 7, 1), "year", -1)), "2025-08-01");
assert.deepStrictEqual(model.weekdayOrder(0), [1, 2, 3, 4, 5, 6, 0]);
assert.deepStrictEqual(model.weekdayOrder(6), [0, 1, 2, 3, 4, 5, 6]);
for (let weekStart = 0; weekStart < 7; weekStart += 1) {
  const order = model.weekdayOrder(weekStart);
  assert.strictEqual(order.length, 7);
  assert.strictEqual(new Set(order).size, 7);
  const range = model.monthRange(new Date(2026, 7, 1), weekStart);
  assert(range.weeks === 5 || range.weeks === 6);
  assert.strictEqual(model.dayDifference(range.displayEnd, range.displayStart) + 1, range.weeks * 7);
}

assert.strictEqual(model.intensityLevel(0, 100), 0);
assert.strictEqual(model.intensityLevel(100, 100), 5);
assert(model.intensityLevel(5, 100) >= 1);
const stableThresholds = model.intensityThresholds([1, 2, 3, 5, 8, 13, 21, 34, 55, 89]);
assert.deepStrictEqual(stableThresholds, [2, 5, 13, 34, 89]);
assert.strictEqual(model.intensityLevel(13, stableThresholds), 3);
assert.strictEqual(model.intensityLevel(13, stableThresholds), model.intensityLevel(13, stableThresholds));

const grouped = model.groupEvents([
  { id: "b", date: "2026-08-13", name: "Beta" },
  { id: "a", date: "2026-08-13", name: "Alpha" },
  { id: "c", date: "2026-08-13", name: "Gamma" },
  { id: "bad", date: "2026-02-30", name: "Invalid" }
]);
assert.deepStrictEqual(grouped["2026-08-13"].map((item) => item.name), ["Alpha", "Beta", "Gamma"]);
assert.strictEqual(grouped["2026-02-30"], undefined);
const noEvents = model.monthEventDisplay([]);
assert.deepStrictEqual(noEvents, { visible: [], overflow: 0 });
const oneEvent = model.monthEventDisplay(grouped["2026-08-13"].slice(0, 1));
assert.deepStrictEqual(oneEvent.visible.map((item) => item.name), ["Alpha"]);
assert.strictEqual(oneEvent.overflow, 0);
const twoEvents = model.monthEventDisplay(grouped["2026-08-13"].slice(0, 2));
assert.deepStrictEqual(twoEvents.visible.map((item) => item.name), ["Alpha", "Beta"]);
assert.strictEqual(twoEvents.overflow, 0);
const threeEvents = model.monthEventDisplay(grouped["2026-08-13"]);
assert.deepStrictEqual(threeEvents.visible.map((item) => item.name), ["Alpha", "Beta"]);
assert.strictEqual(threeEvents.overflow, 1);
const fourEvents = model.monthEventDisplay(grouped["2026-08-13"].concat([{ id: "d", date: "2026-08-13", name: "Delta" }]));
assert.strictEqual(fourEvents.visible.length, 2);
assert.strictEqual(fourEvents.overflow, 2);
assert.deepStrictEqual(model.monthEventDisplay(grouped["2026-08-13"], 0), { visible: [], overflow: 3 });
assert.deepStrictEqual(model.monthEventDisplay(grouped["2026-08-13"], 1).visible.map((item) => item.name), ["Alpha"]);

assert.strictEqual(
  model.isoDate(model.selectionForMonth(new Date(2026, 1, 1), new Date(2026, 0, 31), new Date(2026, 7, 13))),
  "2026-02-28"
);
assert.strictEqual(
  model.isoDate(model.selectionForMonth(new Date(2028, 1, 1), new Date(2028, 0, 31), new Date(2026, 7, 13))),
  "2028-02-29"
);
assert.strictEqual(
  model.isoDate(model.selectionForMonth(new Date(2026, 7, 1), null, new Date(2026, 7, 13))),
  "2026-08-13"
);
assert.strictEqual(
  model.isoDate(model.selectionForMonth(new Date(2026, 8, 1), null, new Date(2026, 7, 13))),
  "2026-09-01"
);
assert.strictEqual(model.detailsPresentation("month", 1150, 1054), "rail");
assert.strictEqual(model.detailsPresentation("month", 1149, 1054), "inline");
assert.strictEqual(model.detailsPresentation("month", 1150, 1053), "inline");
assert.strictEqual(model.detailsPresentation("month", 1180), "rail");
assert.strictEqual(model.detailsPresentation("year", 3420, 3420), "inline");
assert.strictEqual(model.sidebarCollapsed("rail", false, false), true);
assert.strictEqual(model.sidebarCollapsed("rail", true, false), false);
assert.strictEqual(model.sidebarCollapsed("rail", false, true), false);
assert.strictEqual(model.sidebarCollapsed("inline", false, false), false);
assert.strictEqual(model.arrowMove("month", "ArrowRight"), 1);
assert.strictEqual(model.arrowMove("month", "ArrowDown"), 7);
assert.strictEqual(model.arrowMove("year", "ArrowRight"), 7);
assert.strictEqual(model.arrowMove("year", "ArrowDown"), 1);
assert.strictEqual(model.arrowMove("year", "ArrowLeft"), -7);
assert.strictEqual(model.arrowMove("year", "ArrowUp"), -1);

const label = model.popoverLabel("2026-08-13", 12, 7, grouped["2026-08-13"], "en-US", 2, "2026-08-13");
assert(label.includes("12 completed reviews"));
assert(label.includes("7 cards due"));
assert(label.includes("3 events"));
const accessibleLabel = model.popoverLabel("2026-08-13", 12, 7, grouped["2026-08-13"], "en-US", 2, "2026-08-13");
assert(accessibleLabel.includes("2 new cards studied"));
const retrospectivePreview = model.dayPreview("2026-08-12", "2026-08-13", 12, 2, 7, "en-US");
assert(retrospectivePreview.date.includes("Aug 12, 2026"));
assert.strictEqual(retrospectivePreview.summary, "12 completed reviews · 2 new cards studied");
const currentPreview = model.dayPreview("2026-08-13", "2026-08-13", 1, 1, 9, "en-US");
assert.strictEqual(currentPreview.summary, "1 completed review · 1 new card studied · 9 cards due");
const prospectivePreview = model.dayPreview("2026-08-14", "2026-08-13", 0, 0, 7, "en-US");
assert.strictEqual(prospectivePreview.summary, "7 cards due");
const singularDuePreview = model.dayPreview("2026-08-14", "2026-08-13", 0, 0, 1, "en-US");
assert.strictEqual(singularDuePreview.summary, "1 card due");
assert.deepStrictEqual(model.dayPreview("bad", "2026-08-13", 0, 0, 0, "en-US"), { date: "Invalid date", summary: "" });
const pastDetails = model.dateDetailsViewModel("2026-08-12", "2026-08-13", 4, 2, 9, 0);
assert.strictEqual(pastDetails.relation, "past");
assert.strictEqual(pastDetails.showCompleted, true);
assert.strictEqual(pastDetails.showNew, true);
assert.strictEqual(pastDetails.showDue, false);
const todayDetails = model.dateDetailsViewModel("2026-08-13", "2026-08-13", 4, 2, 9, 3);
assert.deepStrictEqual(
  [todayDetails.showCompleted, todayDetails.showNew, todayDetails.showDue],
  [true, true, true]
);
assert(todayDetails.summaryParts.includes("3 events"));
const futureDetails = model.dateDetailsViewModel("2026-08-14", "2026-08-13", 4, 2, 9, 1);
assert.deepStrictEqual(
  [futureDetails.showCompleted, futureDetails.showNew, futureDetails.showDue],
  [false, false, true]
);
assert.strictEqual(model.dateDetailsViewModel("bad", "2026-08-13", 0, 0, 0, 0).valid, false);
const unavailableDetails = model.dateDetailsViewModel(
  "2026-08-13", "2026-08-13", 0, 0, 0, 0,
  { history: false, forecast: false, forecastEnabled: true }
);
assert.strictEqual(unavailableDetails.historyAvailable, false);
assert.strictEqual(unavailableDetails.forecastAvailable, false);
assert(unavailableDetails.summaryParts.includes("Study history unavailable"));
assert(unavailableDetails.summaryParts.includes("Due forecast unavailable"));
const forecastDisabledDetails = model.dateDetailsViewModel(
  "2026-08-14", "2026-08-13", 0, 0, 0, 0,
  { history: true, forecast: false, forecastEnabled: false }
);
assert.strictEqual(forecastDisabledDetails.showDue, false);
assert.strictEqual(model.isoDate(model.addDays(new Date(2026, 11, 31), 1)), "2027-01-01");

const troubleInsight = model.insightViewModel({
  kind: "trouble_cards",
  browse_action: "trouble_cards",
  items: [
    { primary_text: "One" },
    { primary_text: "Two" },
    { primary_text: "Three" },
    { primary_text: "Four" }
  ]
}, "2026-08-13", "2026-08-13");
assert.strictEqual(troubleInsight.title, "Cards most missed today");
assert.strictEqual(troubleInsight.buttonLabel, "Browse these cards");
assert.strictEqual(troubleInsight.items.length, 3);

const currentEmptyInsight = model.insightViewModel({
  kind: "trouble_cards",
  empty_reason: "today_no_answers",
  browse_action: "today",
  items: []
}, "2026-08-13", "2026-08-13");
assert.strictEqual(currentEmptyInsight.message, "No cards studied today yet.");
assert.strictEqual(currentEmptyInsight.supporting, "Start reviewing to see cards that you are missing repeatedly.");
assert.strictEqual(currentEmptyInsight.buttonLabel, "Browse today’s cards");

const pastEmptyInsight = model.insightViewModel({
  kind: "trouble_cards",
  empty_reason: "past_no_answers",
  browse_action: "none",
  items: []
}, "2026-08-12", "2026-08-13");
assert.strictEqual(pastEmptyInsight.message, "No cards were studied on this date.");
assert.strictEqual(pastEmptyInsight.buttonLabel, "Browse this day’s cards");

const noAgainInsight = model.insightViewModel({
  kind: "trouble_cards",
  empty_reason: "no_again",
  browse_action: "today",
  items: []
}, "2026-08-13", "2026-08-13");
assert.strictEqual(noAgainInsight.message, "No cards were missed today.");
assert.strictEqual(noAgainInsight.buttonLabel, "Browse today’s cards");

const deletedInsight = model.insightViewModel({
  kind: "trouble_cards",
  empty_reason: "deleted_misses",
  browse_action: "day",
  items: []
}, "2026-08-12", "2026-08-13");
assert.strictEqual(deletedInsight.message, "Cards missed on this date are no longer available.");
assert.strictEqual(deletedInsight.buttonLabel, "Browse this day’s cards");

const futureInsight = model.insightViewModel({
  kind: "future_due_decks",
  browse_action: "future_due",
  items: [{ primary_text: "Pediatrics", count_label: "8 cards due" }]
}, "2026-08-14", "2026-08-13");
assert.strictEqual(futureInsight.title, "Top due decks");
assert.strictEqual(futureInsight.buttonLabel, "Browse due cards");

const futureEmptyInsight = model.insightViewModel({
  kind: "future_due_decks",
  empty_reason: "no_due",
  browse_action: "none",
  items: []
}, "2026-08-14", "2026-08-13");
assert.strictEqual(futureEmptyInsight.message, "No review cards are due on this date.");
assert.strictEqual(futureEmptyInsight.buttonLabel, "Browse due cards");

const unavailableInsight = model.insightViewModel({
  kind: "unavailable",
  empty_reason: "unavailable",
  items: []
}, "2026-08-13", "2026-08-13");
assert.strictEqual(unavailableInsight.message, "Study insight unavailable.");
assert.strictEqual(unavailableInsight.buttonLabel, "Browse today’s cards");

const previewInsight = model.insightViewModel({
  kind: "unavailable",
  empty_reason: "preview_only",
  browse_action: "none",
  items: []
}, "2026-08-13", "2026-08-13");
assert.strictEqual(previewInsight.message, "Detailed study insight is available on the Deck Browser.");
assert.strictEqual(previewInsight.buttonLabel, "");

const reconciledInsight = model.insightViewModel({
  kind: "trouble_cards",
  empty_reason: "today_no_answers",
  browse_action: "today",
  items: []
}, "2026-08-13", "2026-08-13", 9);
assert.strictEqual(reconciledInsight.message, "No cards were missed today.");

const outOfRangeInsight = model.insightViewModel({
  kind: "future_due_decks",
  empty_reason: "forecast_out_of_range",
  browse_action: "future_due",
  items: []
}, "2028-02-15", "2026-08-13", 0);
assert.strictEqual(outOfRangeInsight.forecastUnavailable, true);
assert.strictEqual(outOfRangeInsight.supporting, "You can still browse that date directly.");

const bridgeTimers = [];
let bridgeReady = false;
let bridgeDispatches = 0;
let bridgeUnavailable = 0;
let bridgeDispatched = 0;
model.dispatchWhenReady(
  function () {
    if (!bridgeReady) return false;
    bridgeDispatches += 1;
    return true;
  },
  function () { return true; },
  function (callback, delay) { bridgeTimers.push({ callback, delay }); },
  function () { bridgeDispatched += 1; },
  function () { bridgeUnavailable += 1; },
  4,
  50
);
assert.strictEqual(bridgeDispatches, 0);
assert.strictEqual(bridgeDispatched, 0);
assert.strictEqual(bridgeUnavailable, 0);
assert.strictEqual(bridgeTimers.length, 1);
assert.strictEqual(bridgeTimers[0].delay, 50);
bridgeReady = true;
bridgeTimers.shift().callback();
assert.strictEqual(bridgeDispatches, 1);
assert.strictEqual(bridgeDispatched, 1);
assert.strictEqual(bridgeUnavailable, 0);
assert.strictEqual(bridgeTimers.length, 0);

const exhaustedTimers = [];
let exhaustedUnavailable = 0;
model.dispatchWhenReady(
  function () { return false; },
  function () { return true; },
  function (callback) { exhaustedTimers.push(callback); },
  function () { assert.fail("unavailable bridge must not report a dispatch"); },
  function () { exhaustedUnavailable += 1; },
  2,
  50
);
assert.strictEqual(exhaustedUnavailable, 0);
assert.strictEqual(exhaustedTimers.length, 1);
exhaustedTimers.shift()();
assert.strictEqual(exhaustedUnavailable, 1);
assert.strictEqual(exhaustedTimers.length, 0);

const cancelledTimers = [];
let requestCurrent = true;
let cancelledUnavailable = 0;
model.dispatchWhenReady(
  function () { return false; },
  function () { return requestCurrent; },
  function (callback) { cancelledTimers.push(callback); },
  function () { assert.fail("cancelled request must not dispatch"); },
  function () { cancelledUnavailable += 1; },
  2,
  50
);
requestCurrent = false;
cancelledTimers.shift()();
assert.strictEqual(cancelledUnavailable, 0);

console.log("calendar model tests passed");
