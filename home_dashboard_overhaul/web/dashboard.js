(function (global) {
  "use strict";

  var DAY_MS = 86400000;
  var UNAVAILABLE_TEXT = "—";
  var N_A_TEXT = "N/A";

  function parseDate(value) {
    var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
    if (!match) return null;
    var result = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    if (
      Number.isNaN(result.getTime()) ||
      result.getFullYear() !== Number(match[1]) ||
      result.getMonth() !== Number(match[2]) - 1 ||
      result.getDate() !== Number(match[3])
    ) return null;
    return result;
  }

  function dateValue(value) {
    if (value instanceof Date && !Number.isNaN(value.getTime())) {
      return new Date(value.getFullYear(), value.getMonth(), value.getDate());
    }
    return parseDate(value);
  }

  function isoDate(value) {
    return [
      String(value.getFullYear()).padStart(4, "0"),
      String(value.getMonth() + 1).padStart(2, "0"),
      String(value.getDate()).padStart(2, "0")
    ].join("-");
  }

  function addDays(value, amount) {
    var result = new Date(value.getFullYear(), value.getMonth(), value.getDate());
    result.setDate(result.getDate() + Number(amount || 0));
    return result;
  }

  function dayDifference(left, right) {
    var leftUtc = Date.UTC(left.getFullYear(), left.getMonth(), left.getDate());
    var rightUtc = Date.UTC(right.getFullYear(), right.getMonth(), right.getDate());
    return Math.round((leftUtc - rightUtc) / DAY_MS);
  }

  function jsWeekStart(weekStart) {
    return (Math.max(0, Math.min(6, Number(weekStart) || 0)) + 1) % 7;
  }

  function startOfWeek(value, weekStart) {
    return addDays(value, -((value.getDay() - jsWeekStart(weekStart) + 7) % 7));
  }

  function endOfWeek(value, weekStart) {
    return addDays(startOfWeek(value, weekStart), 6);
  }

  function monthRange(anchor, weekStart) {
    var start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    var end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
    var displayStart = startOfWeek(start, weekStart);
    var displayEnd = endOfWeek(end, weekStart);
    return {
      start: start,
      end: end,
      displayStart: displayStart,
      displayEnd: displayEnd,
      rows: Math.ceil((dayDifference(displayEnd, displayStart) + 1) / 7)
    };
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
      weeks: Math.ceil((dayDifference(displayEnd, displayStart) + 1) / 7)
    };
  }

  function viewRange(view, anchor, weekStart) {
    return view === "month" ? monthRange(anchor, weekStart) : yearRange(anchor, weekStart);
  }

  function calendarRangeDates(view, anchorValue, weekStart) {
    var anchor = dateValue(anchorValue);
    if (!anchor || (view !== "month" && view !== "year")) return [];
    var range = viewRange(view, anchor, weekStart);
    var start = view === "month" ? range.displayStart : range.start;
    var end = view === "month" ? range.displayEnd : range.end;
    var rows = [];
    for (var cursor = start; cursor <= end; cursor = addDays(cursor, 1)) rows.push(isoDate(cursor));
    return rows;
  }

  function navigate(anchor, view, direction) {
    var amount = direction < 0 ? -1 : 1;
    return view === "month"
      ? new Date(anchor.getFullYear(), anchor.getMonth() + amount, 1)
      : new Date(anchor.getFullYear() + amount, anchor.getMonth(), 1);
  }

  function stateNumber(value) {
    if (
      !value || value.status !== "available" || value.reason !== "" ||
      typeof value.value !== "number" || !Number.isFinite(value.value) || value.value < 0
    ) return null;
    return value.value;
  }

  function stateItems(value) {
    return value && value.status === "available" && value.reason === "" && Array.isArray(value.value)
      ? value.value.slice()
      : null;
  }

  function formatNumber(value, locale) {
    return new Intl.NumberFormat(locale || undefined).format(Math.max(0, Number(value) || 0));
  }

  function formatDurationCompact(seconds) {
    var rawSeconds = Math.max(0, Number(seconds) || 0);
    if (rawSeconds > 0 && rawSeconds < 60) return Math.round(rawSeconds) + "s";
    var minutes = Math.max(0, Math.round(rawSeconds / 60));
    if (minutes < 60) return minutes + "m";
    var hours = Math.floor(minutes / 60);
    var remainder = minutes % 60;
    return remainder ? hours + "h " + remainder + "m" : hours + "h";
  }

  function formatLongDate(value, locale) {
    var parsed = dateValue(value);
    return parsed
      ? new Intl.DateTimeFormat(locale || undefined, {
        weekday: "short", year: "numeric", month: "short", day: "numeric"
      }).format(parsed)
      : "";
  }

  function formatSelectedDate(value, locale) {
    var parsed = dateValue(value);
    if (!parsed) return "";
    return formatLongDate(parsed, locale);
  }

  function formatEventDate(value, referenceValue, locale) {
    var parsed = dateValue(value);
    var reference = dateValue(referenceValue);
    if (!parsed) return "";
    return new Intl.DateTimeFormat(locale || undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: reference && reference.getFullYear() === parsed.getFullYear() ? undefined : "numeric"
    }).format(parsed);
  }

  function formatCompactEventDate(value, referenceValue, locale) {
    var parsed = dateValue(value);
    var reference = dateValue(referenceValue);
    if (!parsed) return "";
    return new Intl.DateTimeFormat(locale || undefined, {
      month: "short",
      day: "numeric",
      year: reference && reference.getFullYear() === parsed.getFullYear() ? undefined : "numeric"
    }).format(parsed);
  }

  function groupEvents(rows) {
    var grouped = Object.create(null);
    (Array.isArray(rows) ? rows : []).forEach(function (event) {
      if (!event || !parseDate(event.date) || typeof event.name !== "string" || !event.name.trim()) return;
      if (!grouped[event.date]) grouped[event.date] = [];
      grouped[event.date].push({
        id: String(event.id || ""),
        date: event.date,
        name: event.name.trim()
      });
    });
    Object.keys(grouped).forEach(function (key) {
      grouped[key].sort(function (left, right) {
        return left.name.localeCompare(right.name) || left.id.localeCompare(right.id);
      });
    });
    return grouped;
  }

  function getNextUpcomingEvent(events, todayValue) {
    var today = dateValue(todayValue);
    if (!today) return null;
    var todayIso = isoDate(today);
    var upcoming = (Array.isArray(events) ? events : []).filter(function (event) {
      return event && event.archived !== true && parseDate(event.date) && event.date >= todayIso &&
        typeof event.name === "string" && event.name.trim();
    }).sort(function (left, right) {
      return left.date.localeCompare(right.date) ||
        left.name.localeCompare(right.name) || String(left.id || "").localeCompare(String(right.id || ""));
    });
    if (!upcoming.length) return null;
    var firstDate = upcoming[0].date;
    return {
      event: upcoming[0],
      additional: upcoming.filter(function (event) { return event.date === firstDate; }).length - 1
    };
  }

  function getContextEvent(events, selectedIso, todayIso) {
    var grouped = groupEvents(events);
    var selected = grouped[selectedIso] || [];
    if (selectedIso === todayIso) {
      var next = getNextUpcomingEvent(events, todayIso);
      return next ? {
        event: next.event,
        additional: next.additional,
        relationship: "Next event",
        kind: "next"
      } : {
        event: null,
        additional: 0,
        relationship: "Next event",
        kind: "empty_today",
        upcoming: null
      };
    }
    if (selected.length) {
      return {
        event: selected[0],
        additional: selected.length - 1,
        relationship: "On this date",
        kind: "selected"
      };
    }
    var upcoming = getNextUpcomingEvent(events, todayIso);
    return {
      event: null,
      additional: 0,
      relationship: "No event on this date",
      kind: "empty_selected",
      upcoming: upcoming
    };
  }

  function eventCountdown(eventDate, todayValue, locale) {
    var eventDay = dateValue(eventDate);
    var today = dateValue(todayValue);
    if (!eventDay || !today) return "";
    var days = dayDifference(eventDay, today);
    if (days === 0) return "today";
    if (days === 1) return "tomorrow";
    if (typeof Intl.RelativeTimeFormat === "function") {
      return new Intl.RelativeTimeFormat(locale || undefined, { numeric: "always" }).format(days, "day");
    }
    return "in " + formatNumber(days, locale) + " days";
  }

  function eventCountdownCompact(eventDate, todayValue, locale) {
    var eventDay = dateValue(eventDate);
    var today = dateValue(todayValue);
    if (!eventDay || !today) return "";
    var days = dayDifference(eventDay, today);
    if (days === 0) return "today";
    if (days === 1) return "tomorrow";
    if (days === -1) return "yesterday";
    return (days < 0 ? "−" : "") + formatNumber(Math.abs(days), locale) + "d";
  }

  function formatLastUpdatedTime(value, locale) {
    var parsed = new Date(String(value || ""));
    if (Number.isNaN(parsed.getTime())) return "";
    return new Intl.DateTimeFormat(locale || undefined, {
      hour: "numeric",
      minute: "2-digit"
    }).format(parsed);
  }

  function dashboardDensity(width) {
    var resolved = Math.max(0, Number(width) || 0);
    if (resolved >= 1040) return "wide";
    if (resolved >= 420) return "intermediate";
    return "narrow";
  }

  function getSelectedDateCapabilities(day, schedulingDate) {
    var result = {
      primary: "",
      primaryEnabled: false,
      primaryReason: "",
      mostMissedCandidate: false
    };
    if (!day || !parseDate(day.date) || !parseDate(schedulingDate)) return result;
    var relation = day.date < schedulingDate ? "past" : day.date > schedulingDate ? "future" : "current";
    var completed = stateNumber(day.reviews_completed);
    var due = stateNumber(day.reviews_due);
    var again = stateNumber(day.again_count);
    if (relation === "past" || relation === "current") {
      result.primary = "reviewed";
      result.primaryEnabled = completed !== null && completed > 0;
      result.primaryReason = completed === 0
        ? "No reviewed cards are available for this date."
        : completed === null ? "Reviewed-card data is unavailable for this date." : "";
      result.mostMissedCandidate = result.primaryEnabled && again !== null && again > 0;
    } else {
      result.primary = "due";
      result.primaryEnabled = due !== null && due > 0;
      result.primaryReason = due === 0
        ? "No cards are due on this date."
        : due === null ? "Due-card data is unavailable for this date." : "";
    }
    return result;
  }

  function pluralLabel(value, locale, singular, plural) {
    var count = Math.abs(Number(value) || 0);
    if (typeof Intl.PluralRules === "function") {
      return new Intl.PluralRules(locale || undefined).select(count) === "one" ? singular : plural;
    }
    return count === 1 ? singular : plural;
  }

  function buildCalendarTooltipRows(day, schedulingDate, locale) {
    if (!day || !parseDate(day.date)) return { heading: "", rows: [] };
    var relation = day.date < schedulingDate ? "past" : day.date > schedulingDate ? "future" : "current";
    var rows = [];
    var completed = stateNumber(day.reviews_completed);
    var newCards = stateNumber(day.new_cards_studied);
    var due = stateNumber(day.reviews_due);
    var newDue = stateNumber(day.new_cards_due);
    if (relation !== "future") {
      if (completed !== null) rows.push({ label: "Completed reviews", value: formatNumber(completed, locale), kind: "metric" });
      if (newCards !== null) rows.push({ label: "New cards studied", value: formatNumber(newCards, locale), kind: "metric" });
    }
    if (relation !== "past" && due !== null) {
      rows.push({ label: "Reviews due", value: formatNumber(due, locale), kind: "metric" });
    }
    if (relation === "future" && newDue !== null) {
      rows.push({ label: "New cards due", value: formatNumber(newDue, locale), kind: "metric" });
    }
    var events = stateItems(day.events);
    if (events && events.length) {
      events.forEach(function (event) {
        if (event && typeof event.name === "string" && event.name.trim()) {
          rows.push({ label: "Event", value: event.name.trim(), kind: "event" });
        }
      });
    }
    return { heading: formatLongDate(day.date, locale), rows: rows };
  }

  function tooltipPlacement(targetRect, tooltipRect, bounds, marginValue, offsetValue) {
    var margin = Number.isFinite(Number(marginValue)) ? Math.max(0, Number(marginValue)) : 8;
    var offset = Number.isFinite(Number(offsetValue)) ? Math.max(0, Number(offsetValue)) : 10;
    var width = Math.max(0, Number(tooltipRect && tooltipRect.width) || 0);
    var height = Math.max(0, Number(tooltipRect && tooltipRect.height) || 0);
    var leftBound = Number(bounds && bounds.left) || 0;
    var rightBound = Number(bounds && bounds.right) || 0;
    var topBound = Number(bounds && bounds.top) || 0;
    var bottomBound = Number(bounds && bounds.bottom) || 0;
    var targetLeft = Number(targetRect && targetRect.left) || 0;
    var targetTop = Number(targetRect && targetRect.top) || 0;
    var targetWidth = Math.max(0, Number(targetRect && targetRect.width) || 0);
    var targetHeight = Math.max(0, Number(targetRect && targetRect.height) || 0);
    var targetRight = Number.isFinite(Number(targetRect && targetRect.right))
      ? Number(targetRect.right)
      : targetLeft + targetWidth;
    var targetBottom = Number.isFinite(Number(targetRect && targetRect.bottom))
      ? Number(targetRect.bottom)
      : targetTop + targetHeight;
    var center = targetLeft + targetWidth / 2;
    var spaceAbove = targetTop - (topBound + margin);
    var spaceBelow = (bottomBound - margin) - targetBottom;
    var placeBelow = spaceAbove < height + offset && spaceBelow >= spaceAbove;
    var preferredTop = placeBelow ? targetBottom + offset : targetTop - height - offset;
    var maximumLeft = Math.max(leftBound + margin, rightBound - width - margin);
    var maximumTop = Math.max(topBound + margin, bottomBound - height - margin);
    var left = Math.min(maximumLeft, Math.max(leftBound + margin, center - width / 2));
    var top = Math.min(maximumTop, Math.max(topBound + margin, preferredTop));
    return {
      left: Math.round(left),
      top: Math.round(top),
      below: placeBelow,
      caretLeft: Math.round(Math.max(14, Math.min(Math.max(14, width - 14), center - left)))
    };
  }

  function getDueLoadScale(forecast) {
    var positive = (Array.isArray(forecast) ? forecast : []).map(function (entry) {
      if (entry && typeof entry === "object" && Object.prototype.hasOwnProperty.call(entry, "reviews_due")) {
        return stateNumber(entry.reviews_due);
      }
      return Math.max(0, Number(entry) || 0);
    }).filter(function (value) { return value !== null && value > 0; })
      .sort(function (left, right) { return left - right; });
    if (!positive.length) return 0;
    return positive[Math.max(0, Math.min(positive.length - 1, Math.ceil(positive.length * 0.9) - 1))];
  }

  function getDueLoadLevel(dueCount, reference) {
    var count = Math.max(0, Number(dueCount) || 0);
    var robustReference = Math.max(0, Number(reference) || 0);
    if (!count || !robustReference) return 0;
    var scaled = Math.sqrt(Math.min(count, robustReference) / robustReference);
    return Math.max(1, Math.min(3, Math.ceil(scaled * 3)));
  }

  function intensityThresholds(values) {
    var positive = (Array.isArray(values) ? values : []).map(function (value) {
      return Math.max(0, Number(value) || 0);
    }).filter(function (value) { return value > 0; }).sort(function (left, right) { return left - right; });
    if (!positive.length) return [];
    return [0.2, 0.4, 0.6, 0.8, 1].map(function (percentile) {
      return positive[Math.max(0, Math.min(positive.length - 1, Math.ceil(positive.length * percentile) - 1))];
    });
  }

  function intensityLevel(completed, thresholds) {
    var value = Math.max(0, Number(completed) || 0);
    if (!value || !Array.isArray(thresholds) || !thresholds.length) return 0;
    for (var index = 0; index < thresholds.length; index += 1) {
      if (value <= thresholds[index]) return index + 1;
    }
    return 5;
  }

  function send(command, payload) {
    if (typeof global.pycmd !== "function") return;
    global.pycmd("hdo:" + JSON.stringify({ command: command, payload: payload || {} }));
  }

  function parsePayload(root) {
    var node = root.querySelector(".hdo-calendar-data, .hdo-dashboard-data");
    if (!node) return null;
    try {
      var parsed = JSON.parse(node.textContent || "{}");
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_error) {
      return null;
    }
  }

  function setButtonHidden(button, hidden) {
    if (!button) return;
    button.hidden = Boolean(hidden);
    button.tabIndex = hidden ? -1 : 0;
  }

  function calendarPayloadFingerprint(payload) {
    if (!payload || typeof payload !== "object") return "";
    return JSON.stringify({
      activity: payload.activity || [],
      events: payload.events || null,
      events_enabled: payload.events_enabled !== false,
      calendar_date: payload.calendar_date || "",
      scheduling_date: payload.scheduling_date || "",
      due_load_reference: Number(payload.due_load_reference) || 0,
      view: payload.view || "",
      week_start: Number(payload.week_start) || 0
    });
  }

  function mountLoadingState(root) {
    if (!root || !root.classList.contains("hdo-dashboard--loading")) return null;
    var card = root.querySelector(".hdo-loading-card");
    var heading = card && card.querySelector("h2");
    var message = root.querySelector("[data-hdo-loading-message]");
    var skeleton = root.querySelector("[data-hdo-loading-skeleton]");
    var failure = root.querySelector("[data-hdo-loading-failure]");
    var delayedTimer = 0;
    var failureTimer = 0;

    function clearTimers() {
      if (delayedTimer) global.clearTimeout(delayedTimer);
      if (failureTimer) global.clearTimeout(failureTimer);
      delayedTimer = 0;
      failureTimer = 0;
    }

    function start() {
      clearTimers();
      root.dataset.hdoLoadState = "initial";
      root.setAttribute("aria-busy", "true");
      if (card) card.setAttribute("aria-busy", "true");
      if (heading) heading.textContent = "Loading your study dashboard…";
      if (message) message.textContent = "";
      if (skeleton) skeleton.hidden = false;
      if (failure) failure.hidden = true;
      delayedTimer = global.setTimeout(function () {
        root.dataset.hdoLoadState = "delayed";
        if (message) message.textContent = "Still loading your study data...";
      }, 2500);
      failureTimer = global.setTimeout(function () {
        root.dataset.hdoLoadState = "failure";
        root.setAttribute("aria-busy", "false");
        if (card) card.setAttribute("aria-busy", "false");
        if (heading) heading.textContent = "Dashboard could not load";
        if (message) message.textContent = "";
        if (skeleton) skeleton.hidden = true;
        if (failure) failure.hidden = false;
      }, 12000);
    }

    start();
    return { retry: start, clear: clearTimers };
  }

  function mountDashboard(root) {
    if (!root || root.dataset.hdoMounted === "true") return null;
    root.dataset.hdoMounted = "true";
    var payload = parsePayload(root);
    var calendar = root.querySelector(".hdo-calendar-grid");
    var locale = document.documentElement.lang || undefined;
    var loadingState = mountLoadingState(root);
    var scrollOwner = applyDocumentScrollClearance(root);

    function updateDensity() {
      root.dataset.hdoContentMode = dashboardDensity(root.getBoundingClientRect().width);
    }

    updateDensity();
    if (typeof global.ResizeObserver === "function") {
      new global.ResizeObserver(updateDensity).observe(root);
    } else {
      global.addEventListener("resize", updateDensity);
    }

    root.querySelectorAll("[data-hdo-command]").forEach(function (button) {
      button.addEventListener("click", function () {
        var command = button.dataset.hdoCommand;
        if (command === "retry") {
          if (loadingState) loadingState.retry();
          send("retry", {});
        }
        else if (command === "diagnostics") send("diagnostics", {});
        else if (command === "calendar-settings") send("settings", { page: "calendar_data" });
        else send("settings", {});
      });
    });
    if (!payload) return null;
    var hasStoredYearScroll = payload.year_scroll_left !== null && payload.year_scroll_left !== undefined &&
      Number.isFinite(Number(payload.year_scroll_left));

    var state = {
      payload: payload,
      view: payload.view === "month" ? "month" : "year",
      weekStart: Math.max(0, Math.min(6, Number(payload.week_start) || 0)),
      anchor: dateValue(payload.anchor) || dateValue(payload.calendar_date) || new Date(),
      selected: String(payload.selected_date || payload.scheduling_date || payload.calendar_date || ""),
      followsToday: String(payload.selected_date || "") === String(payload.scheduling_date || ""),
      days: Object.create(null),
      events: [],
      eventsByDate: Object.create(null),
      dueReference: Math.max(0, Number(payload.due_load_reference) || 0),
      thresholds: [],
      requestId: 0,
      latestRangeRequest: 0,
      latestInsightRequest: Object.create(null),
      mostMissed: Object.create(null),
      modelCache: new Map(),
      yearScrollLeft: hasStoredYearScroll ? Math.max(0, Number(payload.year_scroll_left)) : null,
      yearInitialCentered: hasStoredYearScroll,
      yearCenterRequested: !hasStoredYearScroll,
      scrollOwner: scrollOwner
    };

    function adoptPayload(nextPayload, preserveAnchor, preserveCalendar) {
      state.payload = nextPayload;
      if (nextPayload.last_updated_at) root.dataset.hdoLastUpdatedAt = String(nextPayload.last_updated_at);
      state.view = nextPayload.view === "month" ? "month" : "year";
      state.weekStart = Math.max(0, Math.min(6, Number(nextPayload.week_start) || 0));
      if (!preserveAnchor) state.anchor = dateValue(nextPayload.anchor) || state.anchor;
      state.selected = String(nextPayload.selected_date || state.selected || nextPayload.scheduling_date || "");
      state.dueReference = Math.max(0, Number(nextPayload.due_load_reference) || 0);
      if (preserveCalendar) return;
      state.days = Object.create(null);
      (Array.isArray(nextPayload.activity) ? nextPayload.activity : []).forEach(function (day) {
        if (day && parseDate(day.date)) {
          state.days[day.date] = day;
          if (day.most_missed_available === true) state.mostMissed[day.date] = true;
        }
      });
      state.events = nextPayload.events_enabled === false ? [] : (stateItems(nextPayload.events) || []);
      state.eventsByDate = groupEvents(state.events);
      state.thresholds = intensityThresholds(Object.keys(state.days).map(function (key) {
        return stateNumber(state.days[key].reviews_completed) || 0;
      }));
      if (!state.dueReference) state.dueReference = getDueLoadScale(Object.keys(state.days).map(function (key) { return state.days[key]; }));
      state.modelCache.clear();
    }

    adoptPayload(payload, false, false);
    if (!calendar) return state;

    var shell = root.querySelector(".hdo-calendar-shell");
    var weekdays = root.querySelector(".hdo-month-weekdays");
    var title = root.querySelector("[data-hdo-calendar-title]");
    var tooltip = root.querySelector(".hdo-calendar-tooltip");
    var tooltipHeading = root.querySelector("[data-hdo-tooltip-heading]");
    var tooltipRows = root.querySelector("[data-hdo-tooltip-rows]");
    // Keep the fixed tooltip outside the glass card: backdrop-filter makes the
    // card a containing block and would otherwise offset viewport coordinates.
    if (tooltip && tooltip.parentElement !== root) root.appendChild(tooltip);
    var dateState = root.querySelector("[data-hdo-date-state]");
    var contextDate = root.querySelector("[data-hdo-context-date]");
    var contextEvent = root.querySelector("[data-hdo-context-event]");
    var contextEventLabel = root.querySelector("[data-hdo-context-event-label]");
    var contextEventMarker = root.querySelector("[data-hdo-event-marker]");
    var eventLink = root.querySelector("[data-hdo-open-events]");
    var eventMeta = root.querySelector("[data-hdo-event-meta]");
    var eventMore = root.querySelector("[data-hdo-event-more]");
    var eventEmpty = root.querySelector("[data-hdo-event-empty]");
    var editEvent = root.querySelector("[data-hdo-edit-event]");
    var primaryAction = root.querySelector("[data-hdo-primary-action]");
    var mostMissed = root.querySelector("[data-hdo-most-missed]");
    var liveStatus = root.querySelector("[data-hdo-calendar-status]");

    function cachedDayModel(day, view) {
      if (!day) return null;
      var completed = stateNumber(day.reviews_completed);
      var due = stateNumber(day.reviews_due);
      var events = state.eventsByDate[day.date] || stateItems(day.events) || [];
      var relation = day.date < String(state.payload.scheduling_date || "")
        ? "past"
        : day.date > String(state.payload.scheduling_date || "") ? "future" : "current";
      var cacheKey = [day.date, view, completed, due, events.length, state.dueReference, state.thresholds.join(",")].join("|");
      if (state.modelCache.has(cacheKey)) return state.modelCache.get(cacheKey);
      var model = {
        day: day,
        completed: completed,
        due: due,
        events: events,
        relation: relation,
        intensity: intensityLevel(completed, state.thresholds),
        dueLoad: relation === "past" ? 0 : getDueLoadLevel(due, state.dueReference)
      };
      state.modelCache.set(cacheKey, model);
      return model;
    }

    function hideTooltip() {
      if (tooltip) tooltip.hidden = true;
    }

    function positionTooltip(target, _pointer) {
      if (!tooltip || tooltip.hidden) return;
      var margin = 8;
      var offset = 10;
      var targetRect = target.getBoundingClientRect();
      var rect = tooltip.getBoundingClientRect();
      var card = target.closest(".hdo-calendar-card");
      var cardBounds = card ? card.getBoundingClientRect() : {
        left: 0, right: global.innerWidth, top: 0, bottom: global.innerHeight
      };
      var bounds = {
        left: Math.max(0, cardBounds.left),
        right: Math.min(global.innerWidth, cardBounds.right),
        top: Math.max(0, cardBounds.top),
        bottom: Math.min(global.innerHeight, cardBounds.bottom)
      };
      var placement = tooltipPlacement(targetRect, rect, bounds, margin, offset);
      tooltip.classList.toggle("is-below", placement.below);
      tooltip.style.setProperty(
        "--hdo-tooltip-caret-left",
        placement.caretLeft + "px"
      );
      tooltip.style.left = placement.left + "px";
      tooltip.style.top = placement.top + "px";
    }

    function showTooltip(target, day, pointer) {
      if (!tooltip || !tooltipHeading || !tooltipRows) return;
      var model = buildCalendarTooltipRows(day, String(state.payload.scheduling_date || ""), locale);
      if (!model.heading || !model.rows.length) {
        hideTooltip();
        return;
      }
      tooltipHeading.textContent = model.heading;
      tooltipRows.replaceChildren();
      model.rows.forEach(function (row) {
        var wrapper = document.createElement("div");
        wrapper.className = row.kind === "event" ? "hdo-tooltip-event" : "hdo-tooltip-metric";
        if (row.label) {
          var term = document.createElement("dt");
          term.textContent = row.label;
          wrapper.appendChild(term);
        }
        var value = document.createElement("dd");
        value.textContent = row.value;
        wrapper.appendChild(value);
        tooltipRows.appendChild(wrapper);
      });
      tooltip.hidden = false;
      target.setAttribute("aria-describedby", "hdo-calendar-tooltip");
      positionTooltip(target, pointer);
    }

    function requestMostMissedCapability(day) {
      var capabilities = getSelectedDateCapabilities(day, String(state.payload.scheduling_date || ""));
      if (!capabilities.mostMissedCandidate || Object.prototype.hasOwnProperty.call(state.mostMissed, day.date)) return;
      state.mostMissed[day.date] = null;
      state.requestId += 1;
      state.latestInsightRequest[day.date] = state.requestId;
      send("date_insight", { date: day.date, request_id: state.requestId });
    }

    function updateContext() {
      var todayIso = String(state.payload.calendar_date || state.payload.scheduling_date || "");
      if (contextDate) {
        contextDate.textContent = formatSelectedDate(state.selected, locale);
        contextDate.dateTime = state.selected;
      }
      if (dateState) {
        var selectedIsToday = state.selected === todayIso;
        dateState.textContent = selectedIsToday ? "Today" : "Selected";
        dateState.classList.toggle("is-today", selectedIsToday);
        dateState.classList.toggle("is-selected", !selectedIsToday);
      }
      var eventContext = getContextEvent(state.events, state.selected, todayIso);
      if (contextEvent && contextEventMarker && eventLink && eventMeta && eventMore && eventEmpty && editEvent) {
        var calendarCard = root.querySelector(".hdo-calendar-card");
        var compactFooter = (calendarCard ? calendarCard.clientWidth : root.clientWidth) < 760;
        var selectedEvent = eventContext && eventContext.event;
        var secondaryUpcoming = eventContext && eventContext.kind === "empty_selected" && !compactFooter
          ? eventContext.upcoming
          : null;
        var displayedEvent = selectedEvent || (secondaryUpcoming && secondaryUpcoming.event) || null;
        var additionalEvents = selectedEvent
          ? eventContext.additional
          : secondaryUpcoming ? secondaryUpcoming.additional : 0;
        if (contextEventLabel) contextEventLabel.textContent = eventContext.relationship;
        if (displayedEvent) {
          var countdown = compactFooter
            ? eventCountdownCompact(displayedEvent.date, todayIso, locale)
            : eventCountdown(displayedEvent.date, todayIso, locale);
          var eventDate = compactFooter
            ? formatCompactEventDate(displayedEvent.date, todayIso, locale)
            : formatEventDate(displayedEvent.date, todayIso, locale);
          var eventMetaText = eventDate + (countdown ? " · " + countdown : "");
          var eventTitle = secondaryUpcoming
            ? "Next upcoming: " + displayedEvent.name
            : displayedEvent.name;
          var eventDescription = eventContext.relationship + ": " + eventTitle + (eventMetaText ? " · " + eventMetaText : "");
          contextEventMarker.hidden = false;
          eventLink.hidden = false;
          eventLink.textContent = eventTitle;
          eventLink.title = eventDescription;
          eventLink.dataset.eventDate = displayedEvent.date;
          eventMeta.hidden = !eventMetaText;
          eventMeta.textContent = eventMetaText;
          eventMore.hidden = additionalEvents <= 0;
          eventMore.textContent = additionalEvents > 0
            ? "+" + formatNumber(additionalEvents, locale)
            : "";
          eventEmpty.hidden = true;
        } else {
          contextEventMarker.hidden = true;
          eventLink.hidden = true;
          eventLink.textContent = "";
          eventLink.removeAttribute("title");
          eventLink.dataset.eventDate = "";
          eventMeta.hidden = true;
          eventMeta.textContent = "";
          eventMore.hidden = true;
          eventMore.textContent = "";
          eventEmpty.textContent = eventContext.kind === "empty_today" ? "No upcoming event" : "";
          eventEmpty.hidden = !eventEmpty.textContent;
        }
        var canEditEvents = state.payload.events_enabled !== false;
        editEvent.hidden = !canEditEvents;
        editEvent.dataset.eventId = selectedEvent ? String(selectedEvent.id || "") : "";
        editEvent.dataset.eventDate = selectedEvent ? selectedEvent.date : state.selected;
        if (selectedEvent) {
          editEvent.setAttribute("aria-label", "Edit event: " + selectedEvent.name);
          editEvent.title = "Edit event";
        } else {
          editEvent.setAttribute("aria-label", "Add event on " + formatSelectedDate(state.selected, locale));
          editEvent.title = "Add event";
        }
      }
      var day = state.days[state.selected];
      var capabilities = getSelectedDateCapabilities(day, String(state.payload.scheduling_date || ""));
      if (primaryAction) {
        if (capabilities.primary === "reviewed") primaryAction.textContent = "Reviewed cards";
        if (capabilities.primary === "due") primaryAction.textContent = "Due cards";
        primaryAction.dataset.action = capabilities.primary;
        setButtonHidden(primaryAction, !capabilities.primaryEnabled);
        primaryAction.disabled = false;
        primaryAction.title = capabilities.primaryEnabled
          ? "Open " + primaryAction.textContent.toLowerCase()
          : "";
      }
      if (mostMissed) {
        var available = capabilities.mostMissedCandidate && state.mostMissed[state.selected] === true;
        setButtonHidden(mostMissed, !available);
      }
      if (day) requestMostMissedCapability(day);
    }

    function selectDate(dayIso, focusCell) {
      if (!parseDate(dayIso)) return;
      var previous = calendar.querySelector(".hdo-calendar-day.is-selected");
      state.selected = dayIso;
      state.followsToday = dayIso === String(state.payload.scheduling_date || "");
      if (previous) {
        previous.classList.remove("is-selected");
        previous.setAttribute("aria-selected", "false");
        previous.tabIndex = -1;
      }
      var next = Array.prototype.find.call(calendar.querySelectorAll(".hdo-calendar-day"), function (cell) {
        return cell.dataset.date === dayIso;
      });
      if (next) {
        next.classList.add("is-selected");
        next.setAttribute("aria-selected", "true");
        next.tabIndex = 0;
        if (focusCell) next.focus();
      }
      updateContext();
      send("calendar_selection_changed", { date: dayIso, follows_today: state.followsToday });
      if (liveStatus) liveStatus.textContent = "Selected " + formatLongDate(dayIso, locale);
    }

    function updateYearScrollEdges(frame) {
      if (!frame) return;
      var maximum = Math.max(0, frame.scrollWidth - frame.clientWidth);
      frame.classList.toggle("has-overflow-left", maximum > 1 && frame.scrollLeft > 1);
      frame.classList.toggle("has-overflow-right", maximum > 1 && frame.scrollLeft < maximum - 1);
    }

    function setYearScrollPosition(forceCenter) {
      if (state.view !== "year") return;
      var frame = shell.querySelector(".hdo-calendar-grid-frame");
      if (!frame) return;
      var maximum = Math.max(0, frame.scrollWidth - frame.clientWidth);
      if (maximum <= 1) {
        frame.scrollLeft = 0;
        updateYearScrollEdges(frame);
        return;
      }
      var shouldCenter = Boolean(forceCenter || state.yearCenterRequested || state.yearScrollLeft === null);
      if (shouldCenter) {
        var calendarToday = dateValue(state.payload.calendar_date);
        var targetIso = calendarToday && calendarToday.getFullYear() === state.anchor.getFullYear()
          ? isoDate(new Date(calendarToday.getFullYear(), calendarToday.getMonth(), 15))
          : isoDate(state.anchor);
        var targetCell = calendar.querySelector('.hdo-calendar-day[data-date="' + targetIso + '"]');
        var target = targetCell
          ? targetCell.offsetLeft + targetCell.offsetWidth / 2 - frame.clientWidth / 2
          : maximum / 2;
        frame.scrollLeft = Math.max(0, Math.min(maximum, target));
        state.yearInitialCentered = true;
        state.yearCenterRequested = false;
      } else {
        frame.scrollLeft = Math.max(0, Math.min(maximum, Number(state.yearScrollLeft) || 0));
      }
      state.yearScrollLeft = frame.scrollLeft;
      updateYearScrollEdges(frame);
    }

    function scheduleYearScroll(forceCenter) {
      var apply = function () { setYearScrollPosition(forceCenter); };
      if (typeof global.requestAnimationFrame === "function") global.requestAnimationFrame(apply);
      else apply();
    }

    var yearScrollFrame = shell.querySelector(".hdo-calendar-grid-frame");
    var yearScrollSendTimer = 0;
    if (yearScrollFrame) {
      yearScrollFrame.addEventListener("scroll", function () {
        if (state.view !== "year") return;
        state.yearScrollLeft = yearScrollFrame.scrollLeft;
        updateYearScrollEdges(yearScrollFrame);
        if (yearScrollSendTimer) global.clearTimeout(yearScrollSendTimer);
        yearScrollSendTimer = global.setTimeout(function () {
          send("calendar_year_scroll", { left: state.yearScrollLeft });
        }, 80);
      }, { passive: true });
      if (typeof global.ResizeObserver === "function") {
        new global.ResizeObserver(function () {
          scheduleYearScroll(false);
        }).observe(yearScrollFrame);
      } else {
        global.addEventListener("resize", function () { scheduleYearScroll(false); });
      }
    }

    function createDayCell(dayIso, outOfMonth, view, rowIndex, columnIndex) {
      var day = state.days[dayIso] || {
        date: dayIso,
        reviews_completed: null,
        reviews_due: null,
        new_cards_studied: null,
        again_count: null,
        events: null
      };
      var dateObject = parseDate(dayIso);
      var model = cachedDayModel(day, view);
      var cell = document.createElement("button");
      cell.type = "button";
      cell.className = "hdo-calendar-day";
      cell.dataset.date = dayIso;
      cell.dataset.level = String(model ? model.intensity : 0);
      cell.dataset.dueLevel = String(model ? model.dueLoad : 0);
      cell.dataset.heatKind = model && model.relation === "future" && model.dueLoad > 0
        ? "due"
        : "completion";
      cell.setAttribute("role", "gridcell");
      var cellLabel = formatLongDate(dayIso, locale);
      if (model && model.events.length) {
        cellLabel += ". " + model.events.map(function (event) {
          return "Event: " + event.name;
        }).join(". ");
      }
      cell.setAttribute("aria-label", cellLabel);
      cell.setAttribute("aria-selected", dayIso === state.selected ? "true" : "false");
      cell.tabIndex = dayIso === state.selected ? 0 : -1;
      if (rowIndex) cell.setAttribute("aria-rowindex", String(rowIndex));
      if (columnIndex) cell.setAttribute("aria-colindex", String(columnIndex));
      if (outOfMonth) cell.classList.add("is-out-of-month");
      if (model && model.relation === "future") cell.classList.add("is-future");
      if (dayIso === state.selected) cell.classList.add("is-selected");
      if (dayIso === String(state.payload.calendar_date || "")) cell.classList.add("is-today");
      if (dateObject && dateObject.getDate() === 1) cell.classList.add("is-month-start");

      var number = document.createElement("span");
      number.className = "hdo-date-number";
      number.textContent = String(dateObject ? dateObject.getDate() : "");
      cell.appendChild(number);

      if (model && model.events.length) {
        var marker = document.createElement("span");
        marker.className = "hdo-event-marker";
        marker.setAttribute("aria-hidden", "true");
        if (view === "month" && model.events.length > 1) {
          var count = document.createElement("span");
          count.textContent = String(model.events.length);
          marker.appendChild(count);
        }
        cell.appendChild(marker);
      }

      return cell;
    }

    function delegatedCell(target) {
      var cell = target && typeof target.closest === "function"
        ? target.closest(".hdo-calendar-day")
        : null;
      return cell && calendar.contains(cell) ? cell : null;
    }

    function delegatedDay(cell) {
      return cell ? state.days[cell.dataset.date] || {
        date: cell.dataset.date,
        reviews_completed: null,
        reviews_due: null,
        new_cards_studied: null,
        again_count: null,
        events: null
      } : null;
    }

    calendar.addEventListener("click", function (event) {
      var cell = delegatedCell(event.target);
      if (cell) selectDate(cell.dataset.date, false);
    });
    calendar.addEventListener("pointerover", function (event) {
      var cell = delegatedCell(event.target);
      if (!cell || delegatedCell(event.relatedTarget) === cell) return;
      showTooltip(cell, delegatedDay(cell), event);
    });
    calendar.addEventListener("pointermove", function (event) {
      var cell = delegatedCell(event.target);
      if (cell) positionTooltip(cell, event);
    });
    calendar.addEventListener("pointerout", function (event) {
      var cell = delegatedCell(event.target);
      if (!cell || delegatedCell(event.relatedTarget) === cell) return;
      if (document.activeElement !== cell) {
        cell.removeAttribute("aria-describedby");
        hideTooltip();
      }
    });
    calendar.addEventListener("focusin", function (event) {
      var cell = delegatedCell(event.target);
      if (cell) showTooltip(cell, delegatedDay(cell), null);
    });
    calendar.addEventListener("focusout", function (event) {
      var cell = delegatedCell(event.target);
      if (!cell || delegatedCell(event.relatedTarget) === cell) return;
      cell.removeAttribute("aria-describedby");
      hideTooltip();
    });
    calendar.addEventListener("keydown", function (event) {
      var cell = delegatedCell(event.target);
      if (!cell) return;
      var offsets = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectDate(cell.dataset.date, false);
        return;
      }
      if (!Object.prototype.hasOwnProperty.call(offsets, event.key)) return;
      var selectedDate = parseDate(cell.dataset.date);
      if (!selectedDate) return;
      event.preventDefault();
      var targetIso = isoDate(addDays(selectedDate, offsets[event.key]));
      var target = Array.prototype.find.call(calendar.querySelectorAll(".hdo-calendar-day"), function (candidate) {
        return candidate.dataset.date === targetIso;
      });
      if (target) selectDate(targetIso, true);
    });

    function renderWeekdays() {
      if (!weekdays) return;
      weekdays.replaceChildren();
      var start = jsWeekStart(state.weekStart);
      for (var index = 0; index < 7; index += 1) {
        var reference = new Date(2026, 7, 2 + ((start + index) % 7));
        var label = document.createElement("span");
        label.textContent = new Intl.DateTimeFormat(locale || undefined, { weekday: "short" }).format(reference);
        weekdays.appendChild(label);
      }
    }

    function renderCalendar() {
      if (state.view === "year" && yearScrollFrame && state.yearInitialCentered) {
        state.yearScrollLeft = yearScrollFrame.scrollLeft;
      }
      calendar.replaceChildren();
      shell.dataset.hdoCalendarView = state.view;
      root.dataset.hdoCalendarView = state.view;
      root.querySelectorAll("[data-hdo-view]").forEach(function (button) {
        button.setAttribute("aria-pressed", button.dataset.hdoView === state.view ? "true" : "false");
      });
      if (state.view === "month") {
        var range = monthRange(state.anchor, state.weekStart);
        if (title) title.textContent = new Intl.DateTimeFormat(locale || undefined, { month: "long", year: "numeric" }).format(state.anchor);
        renderWeekdays();
        calendar.className = "hdo-calendar-grid hdo-calendar-grid--month";
        calendar.style.setProperty("--hdo-month-rows", String(range.rows));
        var monthDates = calendarRangeDates("month", state.anchor, state.weekStart);
        monthDates.forEach(function (dayIso, index) {
          var dayDate = parseDate(dayIso);
          calendar.appendChild(createDayCell(
            dayIso,
            dayDate.getMonth() !== state.anchor.getMonth(),
            "month",
            Math.floor(index / 7) + 1,
            (index % 7) + 1
          ));
        });
      } else {
        var year = yearRange(state.anchor, state.weekStart);
        if (title) title.textContent = String(state.anchor.getFullYear());
        if (weekdays) weekdays.replaceChildren();
        calendar.className = "hdo-calendar-grid hdo-calendar-grid--year";
        calendar.style.setProperty("--hdo-year-weeks", String(year.weeks));
        [
          { day: 1, label: "Mon" },
          { day: 3, label: "Wed" },
          { day: 5, label: "Fri" }
        ].forEach(function (weekday) {
          var weekdayLabel = document.createElement("span");
          var weekdayRow = ((weekday.day - jsWeekStart(state.weekStart) + 7) % 7) + 2;
          weekdayLabel.className = "hdo-year-weekday-label";
          weekdayLabel.textContent = weekday.label;
          weekdayLabel.style.gridRow = String(weekdayRow);
          weekdayLabel.setAttribute("aria-hidden", "true");
          calendar.appendChild(weekdayLabel);
        });
        for (var month = 0; month < 12; month += 1) {
          var monthStart = new Date(state.anchor.getFullYear(), month, 1);
          var labelColumn = Math.floor(dayDifference(monthStart, year.displayStart) / 7) + 1;
          var monthLabel = document.createElement("span");
          monthLabel.className = "hdo-year-month-label";
          monthLabel.textContent = new Intl.DateTimeFormat(locale || undefined, { month: "short" }).format(monthStart);
          monthLabel.style.setProperty("--hdo-month-start-week", String(labelColumn + 1));
          monthLabel.setAttribute("aria-hidden", "true");
          calendar.appendChild(monthLabel);
        }
        calendarRangeDates("year", state.anchor, state.weekStart).forEach(function (dayIso) {
          var parsed = parseDate(dayIso);
          var offset = dayDifference(parsed, year.displayStart);
          var row = ((parsed.getDay() - jsWeekStart(state.weekStart) + 7) % 7) + 1;
          var column = Math.floor(offset / 7) + 1;
          var cell = createDayCell(dayIso, false, "year", row, column);
          cell.style.gridRow = String(row + 1);
          cell.style.gridColumn = String(column + 1);
          calendar.appendChild(cell);
        });
      }
      updateContext();
      scheduleYearScroll(false);
    }

    function requestRange() {
      state.requestId += 1;
      state.latestRangeRequest = state.requestId;
      send("calendar_range", {
        anchor: isoDate(state.anchor),
        view: state.view,
        request_id: state.requestId,
        revision: Number(state.payload.revision) || 0,
        source_revision: String(state.payload.source_revision || "")
      });
    }

    root.querySelectorAll("[data-hdo-view]").forEach(function (button) {
      button.addEventListener("click", function () {
        var next = button.dataset.hdoView;
        if (next !== "month" && next !== "year" || next === state.view) return;
        state.view = next;
        state.anchor = dateValue(state.selected) || state.anchor;
        renderCalendar();
        send("calendar_view_changed", { view: state.view });
        requestRange();
      });
    });

    root.querySelectorAll("[data-hdo-calendar]").forEach(function (button) {
      button.addEventListener("click", function () {
        if (button.dataset.hdoCalendar === "today") {
          state.anchor = dateValue(state.payload.calendar_date) || new Date();
          state.yearCenterRequested = true;
          if (state.payload.scheduling_date) selectDate(String(state.payload.scheduling_date), false);
        } else {
          state.anchor = navigate(state.anchor, state.view, button.dataset.hdoCalendar === "previous" ? -1 : 1);
          state.selected = isoDate(state.anchor);
          state.followsToday = state.selected === String(state.payload.scheduling_date || "");
          send("calendar_selection_changed", { date: state.selected, follows_today: state.followsToday });
        }
        renderCalendar();
        requestRange();
      });
    });

    if (eventLink) eventLink.addEventListener("click", function () {
      send("settings", { page: "events" });
    });
    if (editEvent) editEvent.addEventListener("click", function () {
      send("settings", {
        page: "events",
        date: editEvent.dataset.eventDate || "",
        event_id: editEvent.dataset.eventId || ""
      });
    });
    if (primaryAction) primaryAction.addEventListener("click", function () {
      if (!primaryAction.hidden && !primaryAction.disabled) send("open_day", { date: state.selected });
    });
    if (mostMissed) mostMissed.addEventListener("click", function () {
      if (!mostMissed.hidden) send("open_most_missed", { date: state.selected });
    });

    state.receiveCalendarRange = function (envelope) {
      if (
        !envelope || Number(envelope.request_id) !== state.latestRangeRequest ||
        envelope.view !== state.view || String(envelope.source_revision || "") !== String(state.payload.source_revision || "")
      ) return;
      (Array.isArray(envelope.activity) ? envelope.activity : []).forEach(function (day) {
        if (day && parseDate(day.date)) state.days[day.date] = day;
      });
      state.thresholds = intensityThresholds(Object.keys(state.days).map(function (key) {
        return stateNumber(state.days[key].reviews_completed) || 0;
      }));
      state.modelCache.clear();
      renderCalendar();
    };

    state.receiveDayInsight = function (envelope) {
      if (!envelope || !parseDate(envelope.date)) return;
      if (Number(envelope.request_id) !== Number(state.latestInsightRequest[envelope.date])) return;
      state.mostMissed[envelope.date] = Boolean(envelope.insight && envelope.insight.most_missed_available === true);
      if (envelope.date === state.selected) updateContext();
    };

    state.receiveDashboardFacts = function (envelope) {
      if (!envelope || !envelope.facts || Number(envelope.revision) < Number(state.payload.revision || 0)) return;
      var priorSelected = state.selected;
      var calendarChanged = calendarPayloadFingerprint(state.payload) !== calendarPayloadFingerprint(envelope.facts);
      adoptPayload(envelope.facts, true, !calendarChanged);
      state.selected = state.followsToday ? String(envelope.facts.scheduling_date || priorSelected) : priorSelected;
      if (calendarChanged) renderCalendar();
      else updateContext();
      updateMetricValues(
        root,
        envelope.facts.statistics,
        envelope.facts.presentation,
        locale,
        envelope.facts.retention_target
      );
      setDashboardUpdating(root, false);
      var refreshWarning = root.querySelector(".hdo-refresh-warning");
      if (refreshWarning) refreshWarning.remove();
    };

    renderCalendar();
    updateMetricValues(root, payload.statistics, payload.presentation, locale, payload.retention_target);
    global.addEventListener("resize", function () {
      updateProgressComposition(root, state.payload.statistics, state.payload.presentation, locale);
    });
    var selectedDay = state.days[state.selected];
    if (selectedDay) requestMostMissedCapability(selectedDay);
    return state;
  }

  function setMetric(root, key, value, rawValue, compactValue) {
    var node = root.querySelector('[data-hdo-metric="' + key + '"]');
    if (!node) return;
    var row = node.closest(".hdo-metric-row");
    var unavailable = value === null || value === undefined || value === "" || value === UNAVAILABLE_TEXT;
    if (row) {
      row.hidden = false;
      row.classList.toggle("is-unavailable", unavailable);
      var semantic = row.dataset.hdoSemantic || "";
      if (semantic) {
        row.classList.toggle(
          "hdo-value--" + semantic,
          !unavailable && Number.isFinite(Number(rawValue)) && Number(rawValue) > 0
        );
      }
    }
    node.hidden = false;
    var resolved = unavailable ? UNAVAILABLE_TEXT : String(value);
    var wide = node.querySelector(".hdo-value-wide");
    var compact = node.querySelector(".hdo-value-compact");
    if (wide && compact) {
      wide.textContent = resolved;
      compact.textContent = unavailable ? UNAVAILABLE_TEXT : String(compactValue || value);
    } else {
      node.textContent = resolved;
    }
  }

  function availableValue(state) {
    return state && state.status === "available" && state.reason === "" ? state.value : null;
  }

  function updateProgressComposition(root, _statistics, presentation, _locale) {
    var track = root.querySelector("[data-hdo-progress-track]");
    var fill = root.querySelector("[data-hdo-progress-fill]");
    var label = root.querySelector("[data-hdo-progress-label]");
    var fillLabel = root.querySelector("[data-hdo-progress-label-fill]");
    var chip = root.querySelector("[data-hdo-progress-chip]");
    if (!track || !fill || !label || !chip) return;
    var progress = presentation && presentation.progress && typeof presentation.progress === "object"
      ? presentation.progress
      : { status: "unavailable", fill_percent: null };
    var state = typeof progress.status === "string" ? progress.status : "unavailable";
    var hasFill = (state === "in_progress" || state === "complete") &&
      progress.fill_percent !== null && progress.fill_percent !== undefined;
    var percent = hasFill ? Math.min(100, Math.max(0, Number(progress.fill_percent) || 0)) : 0;
    var statusLabel = state === "no_cards_scheduled"
      ? "No cards scheduled"
      : state === "all_clear"
        ? "All clear"
        : state === "complete"
          ? "100% complete"
          : state === "in_progress"
            ? Math.round(percent) + "% complete"
            : "Unavailable";
    chip.hidden = hasFill;
    chip.textContent = statusLabel;
    chip.dataset.hdoProgressState = state;
    track.hidden = !hasFill;
    track.dataset.hdoProgressState = state;
    track.setAttribute("aria-valuenow", String(percent));
    track.setAttribute("aria-valuetext", statusLabel);
    track.style.setProperty("--hdo-progress-percent", percent + "%");
    label.textContent = statusLabel;
    if (fillLabel) fillLabel.textContent = statusLabel;
  }

  function updateMetricSemanticRole(root, key, role) {
    var value = root.querySelector('[data-hdo-metric="' + key + '"]');
    var row = value && value.closest(".hdo-metric-row");
    if (!row) return;
    ["success", "warning", "danger"].forEach(function (name) {
      row.classList.remove("hdo-value--" + name);
    });
    if (role) row.classList.add("hdo-value--" + role);
  }

  function rateSemanticRole(percent, target, lowerIsBetter) {
    if (target === null || target === undefined || target === "") return "";
    var value = Number(percent);
    var threshold = Number(target);
    if (!Number.isFinite(value) || !Number.isFinite(threshold)) return "";
    if (lowerIsBetter) {
      if (value <= threshold) return "success";
      if (value <= threshold + 10) return "warning";
      return "danger";
    }
    if (value >= threshold) return "success";
    if (value >= threshold - 10) return "warning";
    return "danger";
  }

  function updateMetricValues(root, statistics, presentation, locale, retentionTarget) {
    if (!statistics || typeof statistics !== "object") return;
    var today = availableValue(statistics.today);
    var queue = availableValue(statistics.queue);
    var buried = availableValue(statistics.buried);
    var recent = availableValue(statistics.last_seven_days);
    var longTerm = availableValue(statistics.long_term);
    var todayPresentation = presentation && presentation.today_session || {};
    if (today) {
      setMetric(root, "today.answers", todayPresentation.cards_studied || formatNumber(today.answers, locale), today.answers);
      setMetric(root, "today.new_cards_studied", todayPresentation.new_cards_studied || formatNumber(today.new_cards_studied, locale), today.new_cards_studied);
      setMetric(
        root,
        "today.time_spent",
        todayPresentation.time_spent || UNAVAILABLE_TEXT,
        today.seconds,
        formatDurationCompact(today.seconds)
      );
      setMetric(root, "today.pace", todayPresentation.pace || UNAVAILABLE_TEXT, today.pace_value);
      setMetric(root, "queue.eta", todayPresentation.eta || UNAVAILABLE_TEXT, queue && queue.estimated_duration_seconds);
    } else {
      ["today.answers", "today.new_cards_studied", "today.time_spent", "today.pace", "queue.eta"].forEach(function (key) {
        setMetric(root, key, UNAVAILABLE_TEXT, null);
      });
    }
    if (queue) {
      setMetric(root, "queue.new", formatNumber(queue.new, locale), queue.new);
      setMetric(root, "queue.learning", formatNumber(queue.learning, locale), queue.learning);
      setMetric(root, "queue.review", formatNumber(queue.review, locale), queue.review);
      setMetric(root, "queue.total", formatNumber((queue.new || 0) + (queue.learning || 0) + (queue.review || 0), locale), (queue.new || 0) + (queue.learning || 0) + (queue.review || 0));
    } else {
      ["queue.new", "queue.learning", "queue.review", "queue.total"].forEach(function (key) {
        setMetric(root, key, UNAVAILABLE_TEXT, null);
      });
    }
    if (buried) {
      var buriedTotal = (buried.new || 0) + (buried.learning || 0) + (buried.review || 0);
      setMetric(root, "today.cards_buried", todayPresentation.cards_buried || formatNumber(buriedTotal, locale), buriedTotal);
    } else setMetric(root, "today.cards_buried", UNAVAILABLE_TEXT, null);
    if (recent) {
      setMetric(root, "last_seven_days.cards_studied", formatNumber(recent.cards_studied, locale), recent.cards_studied);
      setMetric(root, "last_seven_days.new_cards_studied", formatNumber(recent.new_cards_studied, locale), recent.new_cards_studied);
      setMetric(root, "last_seven_days.retention", recent.retention && recent.retention.status === "available" ? recent.retention.percent + "%" : N_A_TEXT, recent.retention && recent.retention.percent);
      setMetric(root, "last_seven_days.again_rate", recent.again_rate && recent.again_rate.status === "available" ? recent.again_rate.percent + "%" : N_A_TEXT, recent.again_rate && recent.again_rate.percent);
      updateMetricSemanticRole(
        root,
        "last_seven_days.retention",
        recent.retention && recent.retention.status === "available"
          ? rateSemanticRole(recent.retention.percent, retentionTarget, false)
          : ""
      );
      updateMetricSemanticRole(
        root,
        "last_seven_days.again_rate",
        recent.again_rate && recent.again_rate.status === "available"
          ? rateSemanticRole(
              recent.again_rate.percent,
              retentionTarget === null || retentionTarget === undefined || retentionTarget === ""
                ? null
                : 100 - Number(retentionTarget),
              true
            )
          : ""
      );
    } else {
      ["last_seven_days.cards_studied", "last_seven_days.new_cards_studied", "last_seven_days.retention", "last_seven_days.again_rate"].forEach(function (key) {
        setMetric(root, key, UNAVAILABLE_TEXT, null);
      });
      updateMetricSemanticRole(root, "last_seven_days.retention", "");
      updateMetricSemanticRole(root, "last_seven_days.again_rate", "");
    }
    if (longTerm) {
      setMetric(root, "long_term.average_reviews_per_active_day", formatNumber(longTerm.average_reviews_per_active_day, locale), longTerm.average_reviews_per_active_day);
      setMetric(root, "long_term.current_streak", formatNumber(longTerm.current_streak, locale) + (longTerm.current_streak === 1 ? " day" : " days"), longTerm.current_streak);
      setMetric(root, "long_term.longest_streak", formatNumber(longTerm.longest_streak, locale) + (longTerm.longest_streak === 1 ? " day" : " days"), longTerm.longest_streak);
      setMetric(root, "long_term.lifetime_cards_studied", formatNumber(longTerm.lifetime_cards_studied, locale), longTerm.lifetime_cards_studied);
      setMetric(root, "long_term.lifetime_retention", longTerm.lifetime_retention && longTerm.lifetime_retention.status === "available" ? longTerm.lifetime_retention.percent + "%" : N_A_TEXT, longTerm.lifetime_retention && longTerm.lifetime_retention.percent);
      updateMetricSemanticRole(root, "long_term.lifetime_retention", "");
    } else {
      ["long_term.average_reviews_per_active_day", "long_term.current_streak", "long_term.longest_streak", "long_term.lifetime_retention", "long_term.lifetime_cards_studied"].forEach(function (key) {
        setMetric(root, key, UNAVAILABLE_TEXT, null);
      });
    }
    updateProgressComposition(root, statistics, presentation, locale);
  }

  var activeState = null;

  function setDashboardUpdating(root, updating) {
    if (!root) return;
    root.setAttribute("aria-busy", updating ? "true" : "false");
    var status = root.querySelector("[data-hdo-refresh-status]");
    if (status) {
      status.hidden = !updating;
      status.textContent = updating ? "Refreshing…" : "";
      status.classList.remove("is-error");
    }
  }

  function setDashboardRefreshFailed(root) {
    if (!root) return;
    root.setAttribute("aria-busy", "false");
    var status = root.querySelector("[data-hdo-refresh-status]");
    if (status) {
      status.hidden = true;
      status.textContent = "";
      status.classList.remove("is-error");
    }
    if (root.querySelector(".hdo-refresh-warning")) return;
    var stack = root.querySelector(".hdo-stack");
    if (!stack) return;
    var warning = document.createElement("div");
    warning.className = "hdo-data-warning hdo-refresh-warning";
    warning.setAttribute("role", "alert");
    var copy = document.createElement("span");
    var updated = formatLastUpdatedTime(root.dataset.hdoLastUpdatedAt, document.documentElement.lang || undefined);
    copy.textContent = updated
      ? "Refresh failed. Showing data last updated at " + updated + "."
      : "Refresh failed. Showing previously loaded data.";
    var retry = document.createElement("button");
    retry.type = "button";
    retry.textContent = "Retry";
    retry.addEventListener("click", function () {
      warning.remove();
      setDashboardUpdating(root, true);
      send("retry", {});
    });
    warning.append(copy, retry);
    stack.prepend(warning);
  }

  function applyDocumentTheme(root) {
    if (!root) return;
    root.dataset.hdoHostPreserved = "true";
  }

  function applyDocumentScrollClearance(root) {
    if (!root || root.dataset.hdoPreview === "true" || typeof document === "undefined") return null;
    var scrollOwner = document.scrollingElement;
    if (!scrollOwner || !scrollOwner.style) return null;
    scrollOwner.style.setProperty("scroll-padding-block-end", "66px");
    root.dataset.hdoScrollOwner = scrollOwner === document.documentElement ? "documentElement" : "body";
    return scrollOwner;
  }

  function mount() {
    var root = document.getElementById("hdo-dashboard");
    if (root) {
      applyDocumentTheme(root);
      activeState = mountDashboard(root);
    }
  }

  global.HDOHomeDashboard = {
    receiveCalendarRange: function (envelope) {
      if (activeState && typeof activeState.receiveCalendarRange === "function") activeState.receiveCalendarRange(envelope);
    },
    receiveDayInsight: function (envelope) {
      if (activeState && typeof activeState.receiveDayInsight === "function") activeState.receiveDayInsight(envelope);
    },
    receiveDashboardFacts: function (envelope) {
      if (activeState && typeof activeState.receiveDashboardFacts === "function") activeState.receiveDashboardFacts(envelope);
    },
    setUpdating: function (updating) {
      var root = document.getElementById("hdo-dashboard");
      setDashboardUpdating(root, Boolean(updating));
    },
    setRefreshFailed: function () {
      setDashboardRefreshFailed(document.getElementById("hdo-dashboard"));
    }
  };

  var exported = {
    parseDate: parseDate,
    isoDate: isoDate,
    addDays: addDays,
    dayDifference: dayDifference,
    monthRange: monthRange,
    yearRange: yearRange,
    calendarRangeDates: calendarRangeDates,
    navigate: navigate,
    groupEvents: groupEvents,
    getNextUpcomingEvent: getNextUpcomingEvent,
    getContextEvent: getContextEvent,
    formatSelectedDate: formatSelectedDate,
    formatEventDate: formatEventDate,
    formatCompactEventDate: formatCompactEventDate,
    eventCountdown: eventCountdown,
    eventCountdownCompact: eventCountdownCompact,
    formatLastUpdatedTime: formatLastUpdatedTime,
    dashboardDensity: dashboardDensity,
    getSelectedDateCapabilities: getSelectedDateCapabilities,
    pluralLabel: pluralLabel,
    buildCalendarTooltipRows: buildCalendarTooltipRows,
    tooltipPlacement: tooltipPlacement,
    getDueLoadScale: getDueLoadScale,
    getDueLoadLevel: getDueLoadLevel,
    intensityThresholds: intensityThresholds,
    intensityLevel: intensityLevel,
    rateSemanticRole: rateSemanticRole,
    formatNumber: formatNumber,
    formatDurationCompact: formatDurationCompact,
    applyDocumentTheme: applyDocumentTheme,
    applyDocumentScrollClearance: applyDocumentScrollClearance,
    setDashboardUpdating: setDashboardUpdating,
    setDashboardRefreshFailed: setDashboardRefreshFailed,
    mountLoadingState: mountLoadingState,
    mountDashboard: mountDashboard
  };
  global.HDOCalendarModel = exported;
  if (typeof module !== "undefined" && module.exports) module.exports = exported;

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount, { once: true });
    else mount();
  }
})(typeof window !== "undefined" ? window : globalThis);
