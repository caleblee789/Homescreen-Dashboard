(function (global) {
  "use strict";

  var DAY_MS = 86400000;

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
    return Math.max(1, Math.min(5, Math.ceil(scaled * 5)));
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
      root.setAttribute("aria-busy", "true");
      if (card) card.setAttribute("aria-busy", "true");
      if (heading) heading.textContent = "Loading your study dashboard…";
      if (message) message.textContent = "";
      if (skeleton) skeleton.hidden = false;
      if (failure) failure.hidden = true;
      delayedTimer = global.setTimeout(function () {
        if (message) message.textContent = "Still loading your study data…";
      }, 2500);
      failureTimer = global.setTimeout(function () {
        root.setAttribute("aria-busy", "false");
        if (card) card.setAttribute("aria-busy", "false");
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
      modelCache: new Map()
    };

    function adoptPayload(nextPayload, preserveAnchor, preserveCalendar) {
      state.payload = nextPayload;
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
    var dateState = root.querySelector("[data-hdo-date-state]");
    var contextDate = root.querySelector("[data-hdo-context-date]");
    var contextEvent = root.querySelector("[data-hdo-context-event]");
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
      var margin = 10;
      var offset = 9;
      var targetRect = target.getBoundingClientRect();
      var rect = tooltip.getBoundingClientRect();
      var left = targetRect.left + targetRect.width / 2 - rect.width / 2;
      var top = targetRect.top - rect.height - offset;
      left = Math.min(global.innerWidth - rect.width - margin, Math.max(margin, left));
      if (top < margin) top = targetRect.bottom + offset;
      top = Math.min(global.innerHeight - rect.height - margin, Math.max(margin, top));
      tooltip.style.left = Math.round(left) + "px";
      tooltip.style.top = Math.round(top) + "px";
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
      var upcoming = getNextUpcomingEvent(state.events, todayIso);
      if (contextEvent && contextEventMarker && eventLink && eventMeta && eventMore && eventEmpty && editEvent) {
        if (upcoming) {
          var countdown = eventCountdown(upcoming.event.date, todayIso, locale);
          var eventDate = formatEventDate(upcoming.event.date, todayIso, locale);
          var eventMetaText = eventDate + (countdown ? " · " + countdown : "");
          var eventDescription = "Next event: " + upcoming.event.name + (eventMetaText ? " · " + eventMetaText : "");
          contextEventMarker.hidden = false;
          eventLink.hidden = false;
          eventLink.textContent = upcoming.event.name;
          eventLink.title = eventDescription;
          eventLink.dataset.eventDate = upcoming.event.date;
          eventMeta.hidden = !eventMetaText;
          eventMeta.textContent = eventMetaText;
          eventMore.hidden = upcoming.additional <= 0;
          eventMore.textContent = upcoming.additional > 0
            ? "+" + formatNumber(upcoming.additional, locale) + " more"
            : "";
          eventEmpty.hidden = true;
          editEvent.hidden = false;
          editEvent.dataset.eventId = String(upcoming.event.id || "");
          editEvent.dataset.eventDate = upcoming.event.date;
          editEvent.setAttribute("aria-label", "Edit event: " + upcoming.event.name);
          editEvent.title = "Edit event";
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
          eventEmpty.hidden = false;
          editEvent.hidden = true;
          editEvent.dataset.eventId = "";
          editEvent.dataset.eventDate = "";
        }
      }
      var day = state.days[state.selected];
      var capabilities = getSelectedDateCapabilities(day, String(state.payload.scheduling_date || ""));
      if (primaryAction) {
        if (capabilities.primary === "reviewed") primaryAction.textContent = "View reviewed cards";
        if (capabilities.primary === "due") primaryAction.textContent = "View due cards";
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
      keepSelectedYearCellVisible();
      updateContext();
      send("calendar_selection_changed", { date: dayIso, follows_today: state.followsToday });
      if (liveStatus) liveStatus.textContent = "Selected " + formatLongDate(dayIso, locale);
    }

    function keepSelectedYearCellVisible() {
      if (state.view !== "year") return;
      var frame = shell.querySelector(".hdo-calendar-grid-frame");
      var selectedCell = calendar.querySelector(".hdo-calendar-day.is-selected");
      if (!frame || !selectedCell || frame.scrollWidth <= frame.clientWidth + 1) return;
      var target = selectedCell.offsetLeft + selectedCell.offsetWidth / 2 - frame.clientWidth / 2;
      frame.scrollLeft = Math.max(0, Math.min(frame.scrollWidth - frame.clientWidth, target));
    }

    var selectedVisibilityFrame = shell.querySelector(".hdo-calendar-grid-frame");
    if (selectedVisibilityFrame && typeof window.ResizeObserver === "function") {
      new window.ResizeObserver(function () {
        window.requestAnimationFrame(keepSelectedYearCellVisible);
      }).observe(selectedVisibilityFrame);
    } else {
      window.addEventListener("resize", keepSelectedYearCellVisible);
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
        for (var month = 0; month < 12; month += 1) {
          var monthStart = new Date(state.anchor.getFullYear(), month, 1);
          var labelColumn = Math.floor(dayDifference(monthStart, year.displayStart) / 7) + 1;
          var monthLabel = document.createElement("span");
          monthLabel.className = "hdo-year-month-label";
          monthLabel.textContent = new Intl.DateTimeFormat(locale || undefined, { month: "short" }).format(monthStart);
          monthLabel.style.setProperty("--hdo-month-start-week", String(labelColumn));
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
          cell.style.gridColumn = String(column);
          calendar.appendChild(cell);
        });
      }
      updateContext();
      if (typeof window.requestAnimationFrame === "function") {
        window.requestAnimationFrame(keepSelectedYearCellVisible);
      } else {
        keepSelectedYearCellVisible();
      }
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
      updateMetricValues(root, envelope.facts.statistics, locale, envelope.facts.retention_target);
      root.setAttribute("aria-busy", "false");
    };

    renderCalendar();
    updateMetricValues(root, payload.statistics, locale, payload.retention_target);
    global.addEventListener("resize", function () {
      updateProgressComposition(root, state.payload.statistics, locale);
    });
    var selectedDay = state.days[state.selected];
    if (selectedDay) requestMostMissedCapability(selectedDay);
    return state;
  }

  function setMetric(root, key, value) {
    var node = root.querySelector('[data-hdo-metric="' + key + '"]');
    if (!node) return;
    var row = node.closest(".hdo-metric-row");
    if (value === null || value === undefined || value === "") {
      if (row) row.hidden = true;
      else node.hidden = true;
      return;
    }
    if (row) row.hidden = false;
    else node.hidden = false;
    node.textContent = String(value);
  }

  function availableValue(state) {
    return state && state.status === "available" && state.reason === "" ? state.value : null;
  }

  function roundedProgressPercent(completed, workload) {
    if (workload <= 0) return 0;
    return Math.min(100, Math.max(0, Math.floor(100 * completed / workload + 0.5)));
  }

  function progressShare(count, workload) {
    if (workload <= 0) return "0";
    return (100 * count / workload).toFixed(1).replace(/\.0$/, "");
  }

  function updateProgressComposition(root, statistics, locale) {
    if (!statistics || typeof statistics !== "object") return;
    var today = availableValue(statistics.today);
    var queue = availableValue(statistics.queue);
    var track = root.querySelector("[data-hdo-progress-track]");
    var completeNode = root.querySelector('[data-hdo-metric="progress.percent"]');
    if (!today || !queue || !track || !completeNode) return;
    var counts = {
      completed: Math.max(0, Number(today.answers) || 0),
      new: Math.max(0, Number(queue.new) || 0),
      learning: Math.max(0, Number(queue.learning) || 0),
      review: Math.max(0, Number(queue.review) || 0)
    };
    var workload = counts.completed + counts.new + counts.learning + counts.review;
    var percent = roundedProgressPercent(counts.completed, workload);
    completeNode.textContent = percent + "% complete";
    completeNode.setAttribute("aria-label", percent + "% complete");
    track.setAttribute("aria-valuenow", String(percent));
    var labels = {
      completed: "Completed",
      new: "New remaining",
      learning: "Learning remaining",
      review: "Reviews remaining"
    };
    var descriptions = [];
    var hasPopulatedSegment = false;
    Object.keys(counts).forEach(function (key) {
      var segment = track.querySelector('[data-hdo-progress-segment="' + key + '"]');
      var description = labels[key] + ": " + formatNumber(counts[key], locale) +
        " (" + progressShare(counts[key], workload) + "%)";
      descriptions.push(description);
      if (!segment) return;
      segment.dataset.hdoProgressCount = String(counts[key]);
      segment.style.setProperty("--hdo-progress-count", String(counts[key]));
      segment.classList.toggle("is-populated", counts[key] > 0);
      segment.classList.toggle(
        "has-preceding-populated",
        counts[key] > 0 && hasPopulatedSegment
      );
      if (counts[key] > 0) hasPopulatedSegment = true;
      segment.title = description;
      var hiddenLabel = segment.querySelector(".hdo-visually-hidden");
      if (hiddenLabel) hiddenLabel.textContent = description;
    });
    track.setAttribute(
      "aria-valuetext",
      workload > 0
        ? percent + "% complete. " + descriptions.join("; ") + "."
        : "No workload today. 0% complete."
    );
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

  function updateMetricValues(root, statistics, locale, retentionTarget) {
    if (!statistics || typeof statistics !== "object") return;
    var today = availableValue(statistics.today);
    var queue = availableValue(statistics.queue);
    var buried = availableValue(statistics.buried);
    var recent = availableValue(statistics.last_seven_days);
    var longTerm = availableValue(statistics.long_term);
    if (today) {
      setMetric(root, "today.answers", formatNumber(today.answers, locale));
      setMetric(root, "today.new_cards_studied", formatNumber(today.new_cards_studied, locale));
    }
    if (queue) {
      setMetric(root, "queue.new", formatNumber(queue.new, locale));
      setMetric(root, "queue.learning", formatNumber(queue.learning, locale));
      setMetric(root, "queue.review", formatNumber(queue.review, locale));
      setMetric(root, "queue.total", formatNumber((queue.new || 0) + (queue.learning || 0) + (queue.review || 0), locale));
    }
    if (buried) setMetric(root, "buried.total", formatNumber((buried.new || 0) + (buried.learning || 0) + (buried.review || 0), locale));
    if (recent) {
      setMetric(root, "last_seven_days.cards_studied", formatNumber(recent.cards_studied, locale));
      setMetric(root, "last_seven_days.new_cards_studied", formatNumber(recent.new_cards_studied, locale));
      setMetric(root, "last_seven_days.retention", recent.retention && recent.retention.status === "available" ? recent.retention.percent + "%" : null);
      setMetric(root, "last_seven_days.again_rate", recent.again_rate && recent.again_rate.status === "available" ? recent.again_rate.percent + "%" : null);
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
    }
    if (longTerm) {
      setMetric(root, "long_term.average_reviews_per_active_day", formatNumber(longTerm.average_reviews_per_active_day, locale));
      setMetric(root, "long_term.current_streak", formatNumber(longTerm.current_streak, locale) + (longTerm.current_streak === 1 ? " day" : " days"));
      setMetric(root, "long_term.longest_streak", formatNumber(longTerm.longest_streak, locale) + (longTerm.longest_streak === 1 ? " day" : " days"));
      setMetric(root, "long_term.lifetime_cards_studied", formatNumber(longTerm.lifetime_cards_studied, locale));
      setMetric(root, "long_term.lifetime_retention", longTerm.lifetime_retention && longTerm.lifetime_retention.status === "available" ? longTerm.lifetime_retention.percent + "%" : null);
      updateMetricSemanticRole(root, "long_term.lifetime_retention", "");
    }
    updateProgressComposition(root, statistics, locale);
  }

  var activeState = null;

  function applyDocumentTheme(root) {
    if (!root || typeof document === "undefined") return;
    var styles = global.getComputedStyle(root);
    var canvas = styles.getPropertyValue("--ui-canvas").trim();
    var primary = styles.getPropertyValue("--ui-text-primary").trim();
    var track = styles.getPropertyValue("--ui-scrollbar-track").trim();
    var thumb = styles.getPropertyValue("--ui-scrollbar-thumb").trim();
    var mode = root.dataset.hdoColorMode === "dark" ? "dark" : "light";
    [document.documentElement, document.body].forEach(function (surface) {
      if (!surface) return;
      if (canvas) surface.style.background = canvas;
      if (primary) surface.style.color = primary;
      surface.style.colorScheme = mode;
      if (track && thumb) surface.style.scrollbarColor = thumb + " " + track;
    });
    document.documentElement.dataset.hdoColorMode = mode;
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
      if (root) root.setAttribute("aria-busy", updating ? "true" : "false");
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
    formatSelectedDate: formatSelectedDate,
    formatEventDate: formatEventDate,
    eventCountdown: eventCountdown,
    getSelectedDateCapabilities: getSelectedDateCapabilities,
    pluralLabel: pluralLabel,
    buildCalendarTooltipRows: buildCalendarTooltipRows,
    getDueLoadScale: getDueLoadScale,
    getDueLoadLevel: getDueLoadLevel,
    intensityThresholds: intensityThresholds,
    intensityLevel: intensityLevel,
    rateSemanticRole: rateSemanticRole,
    formatNumber: formatNumber,
    applyDocumentTheme: applyDocumentTheme,
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
