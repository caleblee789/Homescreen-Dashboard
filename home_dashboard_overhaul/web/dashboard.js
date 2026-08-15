(function (global) {
  "use strict";

  function parseDate(value) {
    var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
    if (!match) return null;
    var parsed = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    if (
      Number.isNaN(parsed.getTime()) ||
      parsed.getFullYear() !== Number(match[1]) ||
      parsed.getMonth() !== Number(match[2]) - 1 ||
      parsed.getDate() !== Number(match[3])
    ) return null;
    return parsed;
  }

  function dateValue(value) {
    if (value instanceof Date && !Number.isNaN(value.getTime())) {
      return new Date(value.getFullYear(), value.getMonth(), value.getDate());
    }
    return parseDate(value);
  }

  function isoDate(value) {
    var year = value.getFullYear();
    var month = String(value.getMonth() + 1).padStart(2, "0");
    var day = String(value.getDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
  }

  function addDays(value, amount) {
    var result = new Date(value.getFullYear(), value.getMonth(), value.getDate());
    result.setDate(result.getDate() + amount);
    return result;
  }

  function dayDifference(left, right) {
    var leftUtc = Date.UTC(left.getFullYear(), left.getMonth(), left.getDate());
    var rightUtc = Date.UTC(right.getFullYear(), right.getMonth(), right.getDate());
    return Math.round((leftUtc - rightUtc) / 86400000);
  }

  function jsWeekStart(weekStart) {
    var pythonDay = Math.max(0, Math.min(6, Number(weekStart) || 0));
    return (pythonDay + 1) % 7;
  }

  function startOfWeek(value, weekStart) {
    var offset = (value.getDay() - jsWeekStart(weekStart) + 7) % 7;
    return addDays(value, -offset);
  }

  function endOfWeek(value, weekStart) {
    return addDays(startOfWeek(value, weekStart), 6);
  }

  function yearRange(anchor, weekStart) {
    var start = new Date(anchor.getFullYear(), 0, 1);
    var end = new Date(anchor.getFullYear(), 11, 31);
    var displayStart = startOfWeek(start, weekStart);
    var displayEnd = endOfWeek(end, weekStart);
    return {
      start: start,
      end: end,
      displayStart: displayStart,
      displayEnd: displayEnd,
      weeks: Math.ceil((dayDifference(displayEnd, displayStart) + 1) / 7),
      rows: 7
    };
  }

  function monthRange(anchor, weekStart) {
    var start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    var end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
    var displayStart = startOfWeek(start, weekStart);
    var displayEnd = endOfWeek(end, weekStart);
    var rows = Math.ceil((dayDifference(displayEnd, displayStart) + 1) / 7);
    return {
      start: start,
      end: end,
      displayStart: displayStart,
      displayEnd: displayEnd,
      weeks: rows,
      rows: rows
    };
  }

  function viewRange(view, anchor, weekStart) {
    return view === "month" ? monthRange(anchor, weekStart) : yearRange(anchor, weekStart);
  }

  function navigate(anchor, view, direction) {
    var amount = direction < 0 ? -1 : 1;
    if (view === "month") return new Date(anchor.getFullYear(), anchor.getMonth() + amount, 1);
    return new Date(anchor.getFullYear() + amount, anchor.getMonth(), 1);
  }

  function weekdayOrder(weekStart) {
    var first = jsWeekStart(weekStart);
    var result = [];
    for (var index = 0; index < 7; index += 1) result.push((first + index) % 7);
    return result;
  }

  function intensityThresholds(values) {
    var positive = (Array.isArray(values) ? values : [])
      .map(function (value) { return Math.max(0, Number(value) || 0); })
      .filter(function (value) { return value > 0; })
      .sort(function (a, b) { return a - b; });
    if (!positive.length) return [1, 2, 3, 4, 5];
    return [0.2, 0.4, 0.6, 0.8, 1].map(function (percentile) {
      return positive[Math.min(positive.length - 1, Math.ceil(positive.length * percentile) - 1)];
    });
  }

  function intensityLevel(completed, thresholds) {
    var value = Math.max(0, Number(completed) || 0);
    if (!value) return 0;
    if (!Array.isArray(thresholds)) {
      var maximum = Math.max(0, Number(thresholds) || 0);
      return maximum ? Math.max(1, Math.min(5, Math.ceil(5 * Math.sqrt(value / maximum)))) : 0;
    }
    for (var index = 0; index < thresholds.length; index += 1) {
      if (value <= thresholds[index]) return index + 1;
    }
    return 5;
  }

  function groupEvents(rows) {
    var grouped = Object.create(null);
    (Array.isArray(rows) ? rows : []).forEach(function (item) {
      if (!item || !parseDate(item.date) || typeof item.name !== "string") return;
      if (!grouped[item.date]) grouped[item.date] = [];
      grouped[item.date].push({ id: String(item.id || ""), date: item.date, name: item.name });
    });
    Object.keys(grouped).forEach(function (key) {
      grouped[key].sort(function (a, b) { return a.name.localeCompare(b.name); });
    });
    return grouped;
  }

  function monthEventDisplay(events, capacity) {
    var values = Array.isArray(events) ? events : [];
    var limit = capacity === undefined ? 2 : Math.max(0, Math.floor(Number(capacity) || 0));
    return { visible: values.slice(0, limit), overflow: Math.max(0, values.length - limit) };
  }

  function selectionForMonth(anchorValue, preferredValue, todayValue) {
    var anchor = dateValue(anchorValue);
    if (!anchor) return null;
    var preferred = dateValue(preferredValue);
    var today = dateValue(todayValue);
    var day = 1;
    if (preferred) day = preferred.getDate();
    else if (today && today.getFullYear() === anchor.getFullYear() && today.getMonth() === anchor.getMonth()) {
      day = today.getDate();
    }
    var lastDay = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0).getDate();
    return new Date(anchor.getFullYear(), anchor.getMonth(), Math.max(1, Math.min(lastDay, day)));
  }

  var WIDE_DASHBOARD_MIN = 1150;
  var WIDE_REGION_MIN = 1054;

  function detailsPresentation(view, dashboardWidthValue, regionWidthValue) {
    var dashboard = Math.max(0, Number(dashboardWidthValue) || 0);
    var region = regionWidthValue === undefined
      ? dashboard
      : Math.max(0, Number(regionWidthValue) || 0);
    return view === "month" && dashboard >= WIDE_DASHBOARD_MIN && region >= WIDE_REGION_MIN
      ? "rail"
      : "inline";
  }

  function sidebarCollapsed(presentation, hasContent, hasStats) {
    return presentation === "rail" && !hasContent && !hasStats;
  }

  function arrowMove(view, key) {
    var month = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
    var year = { ArrowLeft: -7, ArrowRight: 7, ArrowUp: -1, ArrowDown: 1 };
    return (view === "year" ? year : month)[key];
  }

  function countLabel(value, singular, plural) {
    var count = Math.max(0, Number(value) || 0);
    return count + " " + (count === 1 ? singular : plural);
  }

  function dateDetailsViewModel(dateString, todayString, completed, newCardsStudied, due, eventCount, availabilityValue) {
    var parsed = parseDate(dateString);
    var today = parseDate(todayString);
    if (!parsed || !today) {
      return {
        valid: false,
        relation: "invalid",
        showCompleted: false,
        showNew: false,
        showDue: false,
        completed: 0,
        newCardsStudied: 0,
        due: 0,
        eventCount: 0,
        summaryParts: []
      };
    }
    var availability = availabilityValue && typeof availabilityValue === "object"
      ? availabilityValue
      : {};
    var historyAvailable = availability.history !== false;
    var forecastEnabled = availability.forecastEnabled !== false;
    var forecastAvailable = forecastEnabled && availability.forecast !== false;
    var difference = dayDifference(parsed, today);
    var completedCount = Math.max(0, Number(completed) || 0);
    var newCount = Math.max(0, Number(newCardsStudied) || 0);
    var dueCount = Math.max(0, Number(due) || 0);
    var eventsCount = Math.max(0, Number(eventCount) || 0);
    var showHistory = difference <= 0;
    var showDue = difference >= 0 && forecastEnabled;
    var parts = [];
    if (showHistory) {
      if (historyAvailable) {
        parts.push(countLabel(completedCount, "completed review", "completed reviews"));
        parts.push(countLabel(newCount, "new card studied", "new cards studied"));
      } else {
        parts.push("Study history unavailable");
      }
    }
    if (showDue) {
      parts.push(
        forecastAvailable
          ? countLabel(dueCount, "card due", "cards due")
          : "Due forecast unavailable"
      );
    }
    if (eventsCount) parts.push(countLabel(eventsCount, "event", "events"));
    return {
      valid: true,
      relation: difference < 0 ? "past" : (difference > 0 ? "future" : "today"),
      showCompleted: showHistory,
      showNew: showHistory,
      showDue: showDue,
      historyAvailable: historyAvailable,
      forecastAvailable: forecastAvailable,
      forecastEnabled: forecastEnabled,
      completed: completedCount,
      newCardsStudied: newCount,
      due: dueCount,
      eventCount: eventsCount,
      summaryParts: parts
    };
  }

  function dayPreview(dateString, todayString, completed, newCardsStudied, due, locale, eventCount, availability) {
    var parsed = parseDate(dateString);
    var details = dateDetailsViewModel(
      dateString,
      todayString,
      completed,
      newCardsStudied,
      due,
      eventCount,
      availability
    );
    if (!parsed || !details.valid) return { date: "Invalid date", summary: "" };
    var full = parsed.toLocaleDateString(locale || undefined, {
      weekday: "short", year: "numeric", month: "short", day: "numeric"
    });
    return { date: full, summary: details.summaryParts.join(" · ") };
  }

  function popoverLabel(dateString, completed, due, events, locale, newCardsStudied, todayString, availability) {
    var parsed = parseDate(dateString);
    if (!parsed) return "Invalid date";
    var full = parsed.toLocaleDateString(locale || undefined, {
      weekday: "long", year: "numeric", month: "long", day: "numeric"
    });
    var details = dateDetailsViewModel(
      dateString,
      todayString || isoDate(new Date()),
      completed,
      newCardsStudied,
      due,
      events && events.length,
      availability
    );
    return full + ": " + details.summaryParts.join(", ");
  }

  function insightViewModel(insight, dateString, todayString, completedValue) {
    var value = insight && typeof insight === "object" ? insight : {};
    var items = Array.isArray(value.items) ? value.items.slice(0, 3) : [];
    var selectedDate = parseDate(dateString);
    var currentDate = parseDate(todayString);
    var relation = selectedDate && currentDate ? dayDifference(selectedDate, currentDate) : null;
    var isToday = relation === 0;
    var emptyReason = String(value.empty_reason || "");
    if (
      Math.max(0, Number(completedValue) || 0) > 0
      && (emptyReason === "today_no_answers" || emptyReason === "past_no_answers")
    ) {
      emptyReason = "no_again";
    }
    var result = {
      title: value.kind === "future_due_decks" ? "Top due decks" : "Study insight",
      message: "",
      supporting: "",
      buttonLabel: "",
      items: items,
      forecastUnavailable: relation !== null && relation >= 0 && (
        emptyReason === "forecast_out_of_range" || emptyReason === "unavailable"
      )
    };
    if (items.length) {
      result.title = value.kind === "future_due_decks"
        ? "Top due decks"
        : (isToday ? "Cards most missed today" : "Cards most missed on this date");
    } else {
      var copy = {
        today_no_answers: "No cards studied today yet.",
        past_no_answers: "No cards were studied on this date.",
        no_again: isToday ? "No cards were missed today." : "No cards were missed on this date.",
        deleted_misses: isToday ? "Cards missed today are no longer available." : "Cards missed on this date are no longer available.",
        no_due: "No review cards are due on this date.",
        history_out_of_range: "This date is outside the configured study history.",
        forecast_disabled: "Due forecasts are turned off in Calendar settings.",
        forecast_out_of_range: "This date is outside the configured due forecast.",
        unavailable: "Study insight unavailable.",
        preview_only: "Detailed study insight is available on the Deck Browser."
      };
      result.message = copy[emptyReason] || copy.unavailable;
      if (emptyReason === "today_no_answers") {
        result.supporting = "Start reviewing to see cards that you are missing repeatedly.";
      } else if (emptyReason === "forecast_out_of_range") {
        result.supporting = "You can still browse that date directly.";
      }
    }
    var actions = {
      trouble_cards: "Browse these cards",
      today: "Browse today’s cards",
      day: "Browse this day’s cards",
      future_due: "Browse due cards"
    };
    result.buttonLabel = actions[value.browse_action] || "";
    if (!result.buttonLabel && emptyReason !== "preview_only") {
      var selectedDate = parseDate(dateString);
      var currentDate = parseDate(todayString);
      if (selectedDate && currentDate) {
        var relation = dayDifference(selectedDate, currentDate);
        result.buttonLabel = relation < 0
          ? "Browse this day’s cards"
          : (relation > 0 ? "Browse due cards" : "Browse today’s cards");
      }
    }
    return result;
  }

  function dispatchWhenReady(dispatch, isCurrent, schedule, onDispatched, onUnavailable, attempts, delay) {
    var attemptsRemaining = Math.max(1, Number(attempts) || 1);

    function attempt() {
      if (!isCurrent()) return;
      if (dispatch()) {
        onDispatched();
        return;
      }
      attemptsRemaining -= 1;
      if (attemptsRemaining <= 0) {
        onUnavailable();
        return;
      }
      schedule(attempt, delay);
    }

    attempt();
  }

  var Model = {
    parseDate: parseDate,
    isoDate: isoDate,
    addDays: addDays,
    dayDifference: dayDifference,
    startOfWeek: startOfWeek,
    yearRange: yearRange,
    monthRange: monthRange,
    viewRange: viewRange,
    navigate: navigate,
    weekdayOrder: weekdayOrder,
    intensityThresholds: intensityThresholds,
    intensityLevel: intensityLevel,
    groupEvents: groupEvents,
    monthEventDisplay: monthEventDisplay,
    selectionForMonth: selectionForMonth,
    detailsPresentation: detailsPresentation,
    sidebarCollapsed: sidebarCollapsed,
    arrowMove: arrowMove,
    dateDetailsViewModel: dateDetailsViewModel,
    dayPreview: dayPreview,
    popoverLabel: popoverLabel,
    insightViewModel: insightViewModel,
    dispatchWhenReady: dispatchWhenReady
  };

  global.HDOCalendarModel = Model;
  if (typeof module !== "undefined" && module.exports) module.exports = Model;
  if (typeof document === "undefined") return;

  function command(name, payload) {
    if (typeof pycmd !== "function") return false;
    pycmd("hdo:" + JSON.stringify({ command: name, payload: payload || {} }));
    return true;
  }

  function initCalendar(root) {
    var region = root.querySelector(".hdo-calendar-region");
    var dataElement = root.querySelector(".hdo-calendar-data");
    if (!region || !dataElement) return;

    var previewMode = root.dataset.hdoPreview === "true";
    var payload = {};
    try { payload = JSON.parse(dataElement.textContent || "{}"); } catch (_) { payload = {}; }
    var activity = new Map();
    (Array.isArray(payload.activity) ? payload.activity : []).forEach(function (item) {
      if (item && parseDate(item.date)) activity.set(item.date, item);
    });
    var events = groupEvents(payload.events);
    var today = parseDate(payload.today) || new Date();
    var todayIso = isoDate(today);
    var initialAnchor = parseDate(payload.anchor) || today;
    var availability = payload.availability && typeof payload.availability === "object"
      ? {
          history: payload.availability.history !== false,
          forecast: payload.availability.forecast !== false,
          forecastEnabled: payload.availability.forecast_enabled !== false
        }
      : { history: true, forecast: true, forecastEnabled: true };
    region.dataset.hdoHistoryAvailable = availability.history ? "true" : "false";
    region.dataset.hdoForecastAvailable = availability.forecast ? "true" : "false";
    var insightCache = new Map();
    if (payload.today_insight && parseDate(payload.today_insight.date)) {
      insightCache.set(payload.today_insight.date, payload.today_insight);
    }
    var thresholds = intensityThresholds(Array.from(activity.values()).map(function (item) {
      return item.reviews_completed;
    }));
    var state = {
      view: payload.view === "month" ? "month" : "year",
      weekStart: Math.max(0, Math.min(6, Number(payload.week_start) || 0)),
      anchor: new Date(initialAnchor.getFullYear(), initialAnchor.getMonth(), initialAnchor.getDate()),
      focusDate: isoDate(initialAnchor),
      selectedDate: "",
      detailsFullDate: "",
      triggerDate: "",
      presentation: "inline",
      railDismissed: false,
      pendingMonthSelection: "",
      chipCapacity: -1,
      requestSequence: 0,
      activeRequestId: 0,
      pendingInsightDate: ""
    };

    var grid = region.querySelector(".hdo-calendar");
    var title = region.querySelector(".hdo-calendar-title");
    var monthLabels = region.querySelector(".hdo-year-months");
    var yearWeekdays = region.querySelector(".hdo-year-weekdays");
    var weekdayRow = region.querySelector(".hdo-month-weekdays");
    var primary = region.querySelector(".hdo-calendar-primary");
    var secondary = region.querySelector(".hdo-calendar-secondary");
    var details = region.querySelector("[data-hdo-date-details]");
    var detailsContent = region.querySelector("[data-hdo-details-content]");
    var closeButton = region.querySelector("[data-hdo-details-close]");
    var browseButton = region.querySelector("[data-hdo-browse-date]");
    var manageButton = region.querySelector("[data-hdo-manage-events]");
    var dayInsight = region.querySelector("[data-hdo-day-insight]");
    var insightTitle = region.querySelector("[data-hdo-insight-title]");
    var insightStatus = region.querySelector("[data-hdo-insight-status]");
    var insightItems = region.querySelector("[data-hdo-insight-items]");
    var summaryCompleted = region.querySelector("[data-hdo-summary-completed]");
    var summaryNew = region.querySelector("[data-hdo-summary-new]");
    var summaryDue = region.querySelector("[data-hdo-summary-due]");
    var detailCompleted = region.querySelector("[data-hdo-detail-completed]");
    var detailNew = region.querySelector("[data-hdo-detail-new]");
    var detailDue = region.querySelector("[data-hdo-detail-due]");
    var detailsAnnouncement = region.querySelector("[data-hdo-details-announcement]");
    var eventsHeading = region.querySelector("[data-hdo-detail-events-heading]");
    var dayPreviewElement = region.querySelector("[data-hdo-day-preview]");
    var dayPreviewDate = region.querySelector("[data-hdo-day-preview-date]");
    var dayPreviewSummary = region.querySelector("[data-hdo-day-preview-summary]");
    var hasStats = Boolean(secondary && secondary.dataset.hdoHasStats === "true");

    function dashboardWidth() {
      var rectangle = root.getBoundingClientRect ? root.getBoundingClientRect() : null;
      return rectangle && rectangle.width ? rectangle.width : (root.clientWidth || global.innerWidth || 0);
    }

    function calendarWidth() {
      var rectangle = primary && primary.getBoundingClientRect ? primary.getBoundingClientRect() : null;
      return rectangle && rectangle.width ? rectangle.width : dashboardWidth();
    }

    function calendarRegionWidth() {
      var rectangle = region.getBoundingClientRect ? region.getBoundingClientRect() : null;
      return rectangle && rectangle.width ? rectangle.width : (region.clientWidth || dashboardWidth());
    }

    function desiredPresentation() {
      return detailsPresentation(state.view, dashboardWidth(), calendarRegionWidth());
    }

    function desiredChipCapacity() {
      return state.view === "month" && Math.round(calendarWidth()) >= 720 ? 2 : 0;
    }

    function activityFor(iso) {
      return activity.get(iso) || {
        reviews_completed: 0,
        reviews_due: 0,
        new_cards_studied: 0
      };
    }

    function hideDayPreview() {
      if (!dayPreviewElement) return;
      var described = grid.querySelector('[aria-describedby="hdo-day-preview"]');
      if (described) described.removeAttribute("aria-describedby");
      dayPreviewElement.hidden = true;
      dayPreviewElement.style.left = "";
      dayPreviewElement.style.top = "";
    }

    function showDayPreview(cell) {
      if (!cell || !dayPreviewElement || !dayPreviewDate || !dayPreviewSummary) return;
      var iso = cell.dataset.date;
      var item = activityFor(iso);
      var preview = dayPreview(
        iso,
        todayIso,
        item.reviews_completed,
        item.new_cards_studied,
        item.reviews_due,
        undefined,
        (events[iso] || []).length,
        availability
      );
      dayPreviewDate.textContent = preview.date;
      dayPreviewSummary.textContent = preview.summary;
      grid.querySelectorAll('[aria-describedby="hdo-day-preview"]').forEach(function (described) {
        described.removeAttribute("aria-describedby");
      });
      cell.setAttribute("aria-describedby", "hdo-day-preview");
      dayPreviewElement.hidden = false;
      var regionRectangle = region.getBoundingClientRect();
      var cellRectangle = cell.getBoundingClientRect();
      var previewRectangle = dayPreviewElement.getBoundingClientRect();
      var left = cellRectangle.left - regionRectangle.left + (cellRectangle.width - previewRectangle.width) / 2;
      var maximumLeft = Math.max(4, regionRectangle.width - previewRectangle.width - 4);
      left = Math.max(4, Math.min(maximumLeft, left));
      var top = cellRectangle.top - regionRectangle.top - previewRectangle.height - 6;
      if (top < 4) top = cellRectangle.bottom - regionRectangle.top + 6;
      var maximumTop = Math.max(4, regionRectangle.height - previewRectangle.height - 4);
      top = Math.max(4, Math.min(maximumTop, top));
      dayPreviewElement.style.left = Math.round(left) + "px";
      dayPreviewElement.style.top = Math.round(top) + "px";
    }

    function setDetailsVisibility(hasContent) {
      details.hidden = !hasContent;
      detailsContent.hidden = !hasContent;
      region.dataset.hdoSidebarCollapsed = sidebarCollapsed(
        state.presentation,
        hasContent,
        hasStats
      ) ? "true" : "false";
    }

    function clearSelectedCell() {
      grid.querySelectorAll('[aria-selected="true"]').forEach(function (cell) {
        cell.setAttribute("aria-selected", "false");
      });
    }

    function restoreTriggerFocus() {
      var trigger = state.triggerDate && grid.querySelector('[data-date="' + state.triggerDate + '"]');
      if (trigger) trigger.focus();
    }

    function closeDetails(restoreFocus) {
      clearSelectedCell();
      state.selectedDate = "";
      state.detailsFullDate = "";
      state.pendingInsightDate = "";
      if (state.presentation === "rail") state.railDismissed = true;
      setDetailsVisibility(false);
      if (restoreFocus !== false) restoreTriggerFocus();
    }

    function setBrowseButton(viewModel, iso) {
      if (previewMode) {
        browseButton.textContent = "Browse cards on the Deck Browser";
        browseButton.hidden = true;
        browseButton.dataset.date = "";
        return;
      }
      browseButton.textContent = viewModel.buttonLabel || "";
      browseButton.hidden = !viewModel.buttonLabel;
      browseButton.dataset.date = viewModel.buttonLabel ? iso : "";
    }

    function renderDetailsSummary(viewModel, fullDate) {
      summaryCompleted.hidden = !viewModel.showCompleted;
      summaryNew.hidden = !viewModel.showNew;
      summaryDue.hidden = !viewModel.showDue;
      detailCompleted.textContent = viewModel.historyAvailable ? String(viewModel.completed) : "—";
      detailNew.textContent = viewModel.historyAvailable ? String(viewModel.newCardsStudied) : "—";
      detailDue.textContent = viewModel.forecastAvailable ? String(viewModel.due) : "—";
      detailsAnnouncement.textContent = fullDate + ". " + viewModel.summaryParts.join(". ") + ".";
    }

    function renderInsight(insight, iso) {
      var completed = activityFor(iso).reviews_completed;
      var viewModel = insightViewModel(insight, iso, todayIso, completed);
      dayInsight.setAttribute("aria-busy", "false");
      insightTitle.textContent = viewModel.title;
      insightStatus.replaceChildren();
      if (viewModel.message) {
        var message = document.createElement("p");
        message.textContent = viewModel.message;
        insightStatus.appendChild(message);
      }
      if (viewModel.supporting) {
        var supporting = document.createElement("p");
        supporting.className = "hdo-insight-supporting";
        supporting.textContent = viewModel.supporting;
        insightStatus.appendChild(supporting);
      }
      insightStatus.hidden = !viewModel.message && !viewModel.supporting;
      insightItems.replaceChildren();
      viewModel.items.forEach(function (item) {
        var row = document.createElement("li");
        var copy = document.createElement("div");
        copy.className = "hdo-insight-copy";
        var primary = document.createElement("span");
        primary.className = "hdo-insight-primary";
        primary.textContent = String(item.primary_text || "");
        copy.appendChild(primary);
        if (item.secondary_text) {
          var secondaryText = document.createElement("span");
          secondaryText.className = "hdo-insight-secondary";
          secondaryText.textContent = String(item.secondary_text);
          copy.appendChild(secondaryText);
        }
        var count = document.createElement("span");
        count.className = "hdo-insight-count";
        count.textContent = String(item.count_label || item.count || "");
        row.appendChild(copy);
        row.appendChild(count);
        insightItems.appendChild(row);
      });
      insightItems.hidden = viewModel.items.length === 0;
      setBrowseButton(viewModel, iso);
      if (viewModel.forecastUnavailable && state.detailsFullDate) {
        var selectedActivity = activityFor(iso);
        var selectedEvents = events[iso] || [];
        renderDetailsSummary(dateDetailsViewModel(
          iso,
          todayIso,
          selectedActivity.reviews_completed,
          selectedActivity.new_cards_studied,
          selectedActivity.reviews_due,
          selectedEvents.length,
          {
            history: availability.history,
            forecast: false,
            forecastEnabled: true
          }
        ), state.detailsFullDate);
      }
    }

    function requestInsight(iso) {
      if (state.pendingInsightDate === iso) return;
      if (previewMode) {
        renderInsight({
          date: iso,
          kind: "unavailable",
          empty_reason: "preview_only",
          browse_action: "none",
          items: []
        }, iso);
        return;
      }
      state.requestSequence += 1;
      state.activeRequestId = state.requestSequence;
      state.pendingInsightDate = iso;
      dayInsight.setAttribute("aria-busy", "true");
      insightTitle.textContent = parseDate(iso) > today ? "Top due decks" : "Study insight";
      insightItems.replaceChildren();
      insightItems.hidden = true;
      insightStatus.replaceChildren();
      var loading = document.createElement("p");
      loading.textContent = "Loading study insight…";
      insightStatus.appendChild(loading);
      insightStatus.hidden = false;
      setBrowseButton(insightViewModel({}, iso, todayIso), iso);
      var requestedId = state.activeRequestId;
      function requestIsCurrent() {
        return state.selectedDate === iso
          && state.pendingInsightDate === iso
          && state.activeRequestId === requestedId;
      }
      function renderUnavailableIfCurrent() {
        if (!requestIsCurrent()) return;
        state.pendingInsightDate = "";
        renderInsight({
          date: iso,
          kind: "unavailable",
          empty_reason: "unavailable",
          browse_action: "none",
          items: []
        }, iso);
      }
      dispatchWhenReady(
        function () {
          return command("date_insight", { date: iso, request_id: requestedId });
        },
        requestIsCurrent,
        function (callback, delay) { global.setTimeout(callback, delay); },
        function () { global.setTimeout(renderUnavailableIfCurrent, 8000); },
        renderUnavailableIfCurrent,
        100,
        50
      );
    }

    function showDetails(cell) {
      if (!cell) return;
      var iso = cell.dataset.date;
      var dateEvents = events[iso] || [];
      var parsed = parseDate(iso);
      if (!parsed) return;
      var fullDate = parsed.toLocaleDateString(undefined, {
        weekday: "long", year: "numeric", month: "long", day: "numeric"
      });
      region.querySelector("[data-hdo-detail-date]").textContent = fullDate;
      var activityItem = activityFor(iso);
      renderDetailsSummary(dateDetailsViewModel(
        iso,
        todayIso,
        activityItem.reviews_completed,
        activityItem.new_cards_studied,
        activityItem.reviews_due,
        dateEvents.length,
        availability
      ), fullDate);
      var eventList = region.querySelector("[data-hdo-detail-events]");
      var empty = region.querySelector("[data-hdo-detail-events-empty]");
      eventList.replaceChildren();
      dateEvents.forEach(function (eventItem) {
        var row = document.createElement("li");
        row.textContent = eventItem.name;
        eventList.appendChild(row);
      });
      empty.hidden = dateEvents.length > 0;
      eventList.hidden = dateEvents.length === 0;
      if (eventsHeading) eventsHeading.textContent = "Events (" + dateEvents.length + ")";
      if (manageButton) {
        manageButton.dataset.date = iso;
        manageButton.setAttribute("aria-label", "Manage events for " + fullDate);
      }
      state.selectedDate = iso;
      state.detailsFullDate = fullDate;
      state.triggerDate = iso;
      state.railDismissed = false;
      clearSelectedCell();
      cell.setAttribute("aria-selected", "true");
      setDetailsVisibility(true);
      if (insightCache.has(iso)) renderInsight(insightCache.get(iso), iso);
      else requestInsight(iso);
    }

    function dayLabel(dateValue, item, dateEvents) {
      return popoverLabel(
        isoDate(dateValue),
        item.reviews_completed,
        item.reviews_due,
        dateEvents,
        undefined,
        item.new_cards_studied,
        todayIso,
        availability
      ) + ". Select for date details.";
    }

    function moveFocus(currentDate, amount) {
      var target = addDays(currentDate, amount);
      state.anchor = new Date(target.getFullYear(), target.getMonth(), target.getDate());
      state.focusDate = isoDate(target);
      render(true);
    }

    function createDay(dateValue, outside, view, rowIndex, columnIndex, monthBoundary) {
      var iso = isoDate(dateValue);
      var item = activityFor(iso);
      var dateEvents = events[iso] || [];
      var completed = Number(item.reviews_completed) || 0;
      var due = Number(item.reviews_due) || 0;
      var button = document.createElement("button");
      button.type = "button";
      button.className = "hdo-day" + (outside ? " hdo-day--outside" : "");
      button.dataset.date = iso;
      button.dataset.level = String(intensityLevel(completed, thresholds));
      button.dataset.due = due > 0 ? "true" : "false";
      button.dataset.events = String(dateEvents.length);
      if (monthBoundary) button.dataset.monthBoundary = "true";
      button.setAttribute("role", "gridcell");
      button.setAttribute("aria-selected", "false");
      button.setAttribute("aria-rowindex", String(rowIndex));
      button.setAttribute("aria-colindex", String(columnIndex));
      button.setAttribute("aria-label", dayLabel(dateValue, item, dateEvents));
      button.tabIndex = iso === state.focusDate ? 0 : -1;
      if (iso === todayIso) {
        button.dataset.today = "true";
        button.setAttribute("aria-current", "date");
      }

      if (view === "month") {
        var numberRow = document.createElement("span");
        numberRow.className = "hdo-date-number-row";
        var number = document.createElement("span");
        number.className = "hdo-date-number";
        number.textContent = String(dateValue.getDate());
        numberRow.appendChild(number);
        button.appendChild(numberRow);
      }
      if (dateEvents.length) {
        var marker = document.createElement("span");
        marker.className = "hdo-event-marker";
        marker.setAttribute("aria-hidden", "true");
        if ((view === "year" && dateEvents.length > 1) || (view === "month" && state.chipCapacity === 0)) {
          marker.textContent = String(dateEvents.length);
        }
        button.appendChild(marker);
      }
      if (view === "month" && dateEvents.length && state.chipCapacity > 0) {
        var eventWrap = document.createElement("span");
        eventWrap.className = "hdo-month-events";
        eventWrap.setAttribute("aria-hidden", "true");
        var display = monthEventDisplay(dateEvents, state.chipCapacity);
        display.visible.forEach(function (eventItem) {
          var chip = document.createElement("span");
          chip.className = "hdo-event-chip";
          chip.textContent = eventItem.name;
          chip.title = eventItem.name;
          eventWrap.appendChild(chip);
        });
        if (display.overflow) {
          var overflow = document.createElement("span");
          overflow.className = "hdo-event-overflow";
          overflow.textContent = "+" + display.overflow;
          eventWrap.appendChild(overflow);
        }
        button.appendChild(eventWrap);
      }
      button.addEventListener("mouseenter", function () { showDayPreview(button); });
      button.addEventListener("mouseleave", function () {
        if (document.activeElement !== button) hideDayPreview();
      });
      button.addEventListener("focus", function () { showDayPreview(button); });
      button.addEventListener("blur", function () {
        if (!button.matches(":hover")) hideDayPreview();
      });
      button.addEventListener("click", function () {
        hideDayPreview();
        showDetails(button);
      });
      button.addEventListener("keydown", function (event) {
        var amount = arrowMove(state.view, event.key);
        if (event.key === "Home" || event.key === "End") {
          var start = startOfWeek(dateValue, state.weekStart);
          amount = dayDifference(event.key === "Home" ? start : addDays(start, 6), dateValue);
        }
        if (event.key === "PageUp" || event.key === "PageDown") {
          event.preventDefault();
          navigatePeriod(event.key === "PageDown" ? 1 : -1, true);
          return;
        }
        if (amount === undefined) return;
        event.preventDefault();
        moveFocus(dateValue, amount);
      });
      return button;
    }

    function renderYearLabels(range) {
      monthLabels.replaceChildren();
      monthLabels.style.setProperty("--hdo-columns", String(range.weeks));
      for (var month = 0; month < 12; month += 1) {
        var first = new Date(state.anchor.getFullYear(), month, 1);
        var column = Math.floor(dayDifference(first, range.displayStart) / 7) + 1;
        var label = document.createElement("span");
        label.textContent = first.toLocaleDateString(undefined, { month: "short" });
        label.style.gridColumn = String(Math.max(1, Math.min(range.weeks, column)));
        monthLabels.appendChild(label);
      }
    }

    function renderWeekdays() {
      weekdayRow.replaceChildren();
      weekdayOrder(state.weekStart).forEach(function (dayIndex) {
        var reference = new Date(2026, 7, 2 + dayIndex);
        var label = document.createElement("span");
        label.textContent = reference.toLocaleDateString(undefined, { weekday: "short" });
        weekdayRow.appendChild(label);
      });
    }

    function renderYearWeekdays() {
      yearWeekdays.replaceChildren();
      weekdayOrder(state.weekStart).forEach(function (dayIndex) {
        var reference = new Date(2026, 7, 2 + dayIndex);
        var label = document.createElement("span");
        label.textContent = reference.toLocaleDateString(undefined, { weekday: "narrow" });
        yearWeekdays.appendChild(label);
      });
    }

    function autoMonthSelection() {
      var preferred = state.pendingMonthSelection ? parseDate(state.pendingMonthSelection) : null;
      var selected = selectionForMonth(state.anchor, preferred, today);
      state.pendingMonthSelection = "";
      return selected ? isoDate(selected) : "";
    }

    function render(focusAfter) {
      var renderStarted = global.performance && typeof global.performance.now === "function"
        ? global.performance.now()
        : Date.now();
      var selectedBefore = state.selectedDate;
      hideDayPreview();
      state.presentation = desiredPresentation();
      region.dataset.hdoCalendarView = state.view;
      region.dataset.hdoDetailsPresentation = state.presentation;
      root.querySelectorAll("[data-hdo-view]").forEach(function (button) {
        button.setAttribute("aria-pressed", button.dataset.hdoView === state.view ? "true" : "false");
      });
      var periodName = state.view === "month" ? "month" : "year";
      var previousButton = root.querySelector('[data-hdo-calendar="previous"]');
      var todayButton = root.querySelector('[data-hdo-calendar="today"]');
      var nextButton = root.querySelector('[data-hdo-calendar="next"]');
      previousButton.setAttribute("aria-label", "Previous " + periodName);
      previousButton.title = "Previous " + periodName;
      nextButton.setAttribute("aria-label", "Next " + periodName);
      nextButton.title = "Next " + periodName;
      var isCurrentPeriod = state.view === "year"
        ? state.anchor.getFullYear() === today.getFullYear()
        : state.anchor.getFullYear() === today.getFullYear() && state.anchor.getMonth() === today.getMonth();
      todayButton.dataset.hdoCurrentPeriod = isCurrentPeriod ? "true" : "false";
      grid.replaceChildren();
      grid.className = "hdo-calendar hdo-calendar--" + state.view;
      var range = viewRange(state.view, state.anchor, state.weekStart);
      grid.style.setProperty("--hdo-columns", String(range.weeks));
      grid.style.setProperty("--hdo-month-rows", String(range.rows));
      grid.setAttribute("aria-rowcount", String(state.view === "year" ? 7 : range.rows));
      grid.setAttribute("aria-colcount", String(state.view === "year" ? range.weeks : 7));
      if (state.view === "year") {
        title.textContent = String(state.anchor.getFullYear());
        weekdayRow.hidden = true;
        yearWeekdays.hidden = false;
        monthLabels.hidden = false;
        renderYearLabels(range);
        renderYearWeekdays();
      } else {
        title.textContent = range.start.toLocaleDateString(undefined, { month: "long", year: "numeric" });
        monthLabels.hidden = true;
        yearWeekdays.hidden = true;
        weekdayRow.hidden = false;
        renderWeekdays();
      }

      state.chipCapacity = desiredChipCapacity();
      var fragment = document.createDocumentFragment();
      var rowCount = state.view === "year" ? 7 : range.rows;
      var rows = [];
      for (var row = 0; row < rowCount; row += 1) {
        var rowElement = document.createElement("div");
        rowElement.className = "hdo-calendar-row";
        rowElement.setAttribute("role", "row");
        rowElement.setAttribute("aria-rowindex", String(row + 1));
        rows.push(rowElement);
        fragment.appendChild(rowElement);
      }
      var position = 0;
      var monthBoundaryColumns = {};
      if (state.view === "year") {
        for (var boundaryMonth = 1; boundaryMonth < 12; boundaryMonth += 1) {
          var boundaryDate = new Date(state.anchor.getFullYear(), boundaryMonth, 1);
          monthBoundaryColumns[Math.floor(dayDifference(boundaryDate, range.displayStart) / 7) + 1] = true;
        }
      }
      for (var cursor = range.displayStart; cursor <= range.displayEnd; cursor = addDays(cursor, 1)) {
        var outside = cursor < range.start || cursor > range.end;
        var yearColumn = Math.floor(position / 7) + 1;
        var monthBoundary = state.view === "year" && Boolean(monthBoundaryColumns[yearColumn]);
        if (state.view === "year" && outside) {
          var placeholder = document.createElement("span");
          placeholder.className = "hdo-day-placeholder";
          placeholder.setAttribute("aria-hidden", "true");
          if (monthBoundary) placeholder.dataset.monthBoundary = "true";
          rows[position % 7].appendChild(placeholder);
        } else {
          var rowIndex = state.view === "year" ? (position % 7) + 1 : Math.floor(position / 7) + 1;
          var columnIndex = state.view === "year" ? Math.floor(position / 7) + 1 : (position % 7) + 1;
          rows[rowIndex - 1].appendChild(createDay(cursor, outside, state.view, rowIndex, columnIndex, monthBoundary));
        }
        position += 1;
      }
      grid.appendChild(fragment);

      var focused = grid.querySelector('[data-date="' + state.focusDate + '"]');
      if (!focused) {
        focused = grid.querySelector(".hdo-day:not(.hdo-day--outside)") || grid.querySelector(".hdo-day");
        if (focused) state.focusDate = focused.dataset.date;
      }
      grid.querySelectorAll(".hdo-day").forEach(function (cell) {
        cell.tabIndex = cell === focused ? 0 : -1;
      });

      var selectedCell = selectedBefore && grid.querySelector('[data-date="' + selectedBefore + '"]');
      if (selectedCell) {
        showDetails(selectedCell);
      } else if (state.presentation === "rail" && state.view === "month" && !state.railDismissed) {
        var automaticIso = autoMonthSelection();
        var automatic = automaticIso && grid.querySelector('[data-date="' + automaticIso + '"]');
        if (automatic) showDetails(automatic);
        else setDetailsVisibility(false);
      } else {
        state.selectedDate = "";
        setDetailsVisibility(false);
      }
      if (focusAfter && focused) focused.focus();
      var renderFinished = global.performance && typeof global.performance.now === "function"
        ? global.performance.now()
        : Date.now();
      region.dataset.hdoLastRenderMs = Math.max(0, renderFinished - renderStarted).toFixed(2);
    }

    function navigatePeriod(direction, focusAfter) {
      var preferred = parseDate(state.selectedDate || state.focusDate) || state.anchor;
      var retainSelection = Boolean(state.selectedDate);
      state.anchor = navigate(state.anchor, state.view, direction);
      state.selectedDate = "";
      state.railDismissed = false;
      if (state.view === "month") {
        var retained = selectionForMonth(state.anchor, preferred, today);
        state.focusDate = isoDate(retained);
        state.pendingMonthSelection = state.focusDate;
        if (retainSelection) state.selectedDate = state.focusDate;
      } else {
        state.focusDate = isoDate(new Date(state.anchor.getFullYear(), 0, 1));
      }
      render(focusAfter);
    }

    root.querySelectorAll("[data-hdo-view]").forEach(function (button) {
      button.addEventListener("click", function () {
        var next = button.dataset.hdoView;
        if (next !== "month" && next !== "year" || next === state.view) return;
        state.view = next;
        state.selectedDate = "";
        state.railDismissed = false;
        state.focusDate = isoDate(state.anchor);
        if (next === "month") state.pendingMonthSelection = state.focusDate;
        render(true);
        if (!previewMode) command("calendar_view_changed", { view: next });
      });
    });

    root.querySelectorAll("[data-hdo-calendar]").forEach(function (button) {
      button.addEventListener("click", function () {
        var action = button.dataset.hdoCalendar;
        if (action === "today") {
          state.anchor = new Date(today.getFullYear(), today.getMonth(), today.getDate());
          state.focusDate = todayIso;
          state.selectedDate = "";
          state.railDismissed = false;
          state.pendingMonthSelection = todayIso;
          render(true);
        } else {
          navigatePeriod(action === "next" ? 1 : -1, true);
        }
      });
    });

    closeButton.addEventListener("click", function () { closeDetails(true); });
    browseButton.addEventListener("click", function () {
      if (previewMode) return;
      if (browseButton.dataset.date) command("open_day", { date: browseButton.dataset.date });
    });
    if (manageButton) manageButton.addEventListener("click", function () {
      if (previewMode) return;
      if (manageButton.dataset.date) command("settings", { page: "events", date: manageButton.dataset.date });
    });
    if (previewMode && manageButton) {
      manageButton.disabled = true;
      manageButton.setAttribute("aria-disabled", "true");
      manageButton.title = "Available on the Deck Browser";
    }

    var namespace = global.HDOHomeDashboard = global.HDOHomeDashboard || {};
    namespace.qaSnapshot = function () {
      var gridRectangle = grid.getBoundingClientRect();
      var footer = region.querySelector(".hdo-calendar-footer");
      var footerRectangle = footer ? footer.getBoundingClientRect() : null;
      return {
        contractVersion: 1,
        view: state.view,
        anchor: isoDate(state.anchor),
        focusDate: state.focusDate,
        selectedDate: state.selectedDate,
        presentation: state.presentation,
        chipCapacity: state.chipCapacity,
        dayCount: grid.querySelectorAll(".hdo-day").length,
        rowCount: Number(grid.getAttribute("aria-rowcount")) || 0,
        columnCount: Number(grid.getAttribute("aria-colcount")) || 0,
        renderMs: Number(region.dataset.hdoLastRenderMs) || 0,
        grid: {
          left: Math.round(gridRectangle.left),
          top: Math.round(gridRectangle.top),
          width: Math.round(gridRectangle.width),
          height: Math.round(gridRectangle.height)
        },
        footerBottom: footerRectangle ? Math.round(footerRectangle.bottom) : 0,
        horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        calendarOverflow: grid.scrollWidth > grid.clientWidth + 1,
        visibleDetails: !details.hidden,
        duplicateDates: grid.querySelectorAll(".hdo-day").length !== new Set(
          Array.from(grid.querySelectorAll(".hdo-day")).map(function (cell) { return cell.dataset.date; })
        ).size
      };
    };
    namespace.qaSetCalendarState = function (value) {
      if (!global.__HDO_QA_ACTIVE__ || !value || typeof value !== "object") return null;
      var nextAnchor = parseDate(value.anchor);
      if (nextAnchor) state.anchor = nextAnchor;
      if (value.view === "month" || value.view === "year") state.view = value.view;
      if (Number.isInteger(value.weekStart) && value.weekStart >= 0 && value.weekStart <= 6) {
        state.weekStart = value.weekStart;
      }
      state.selectedDate = "";
      state.railDismissed = false;
      state.focusDate = isoDate(state.anchor);
      state.pendingMonthSelection = state.view === "month" ? state.focusDate : "";
      render(false);
      return namespace.qaSnapshot();
    };
    namespace.receiveDayInsight = function (response) {
      if (!response || response.date !== state.selectedDate) return;
      if (Number(response.request_id) !== state.activeRequestId) return;
      if (!response.insight || response.insight.date !== response.date) return;
      state.pendingInsightDate = "";
      insightCache.set(response.date, response.insight);
      renderInsight(response.insight, response.date);
    };
    if (namespace.escapeHandler) document.removeEventListener("keydown", namespace.escapeHandler);
    namespace.escapeHandler = function (event) {
      if (event.key === "Escape" && state.selectedDate) {
        event.preventDefault();
        closeDetails(true);
      }
    };
    document.addEventListener("keydown", namespace.escapeHandler);
    if (namespace.resizeObserver) namespace.resizeObserver.disconnect();
    var resizeQueued = false;
    function handleResize() {
      if (resizeQueued) return;
      resizeQueued = true;
      hideDayPreview();
      global.requestAnimationFrame(function () {
        resizeQueued = false;
        var nextPresentation = desiredPresentation();
        var nextCapacity = desiredChipCapacity();
        if (nextPresentation !== state.presentation || nextCapacity !== state.chipCapacity) render(false);
      });
    }
    if (typeof ResizeObserver !== "undefined") {
      namespace.resizeObserver = new ResizeObserver(handleResize);
      namespace.resizeObserver.observe(root);
    } else {
      if (namespace.resizeHandler) global.removeEventListener("resize", namespace.resizeHandler);
      namespace.resizeHandler = handleResize;
      global.addEventListener("resize", namespace.resizeHandler);
    }
    render(false);
  }

  function init() {
    var root = document.getElementById("hdo-dashboard");
    if (!root || root.dataset.hdoInitialized === "true") return;
    root.dataset.hdoInitialized = "true";
    var previewMode = root.dataset.hdoPreview === "true";
    root.querySelectorAll("[data-hdo-command]").forEach(function (button) {
      if (previewMode) {
        button.disabled = true;
        button.setAttribute("aria-disabled", "true");
        button.title = button.dataset.hdoCommand === "settings"
          ? "Already in Home Dashboard settings"
          : "Available on the Deck Browser";
        return;
      }
      button.addEventListener("click", function () { command(button.dataset.hdoCommand, {}); });
    });
    initCalendar(root);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
  var namespace = global.HDOHomeDashboard = global.HDOHomeDashboard || {};
  if (namespace.observer) namespace.observer.disconnect();
  namespace.observer = new MutationObserver(function () {
    if (!document.getElementById("hdo-dashboard")) return;
    init();
  });
  namespace.observer.observe(document.documentElement, { childList: true, subtree: true });
})(typeof globalThis !== "undefined" ? globalThis : this);
