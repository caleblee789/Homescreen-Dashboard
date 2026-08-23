"""Shared production renderer for the dashboard and staged Settings preview."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta
from enum import Enum
import html
import json
from typing import Any, Mapping, Sequence

from .models import (
    BuriedStats,
    DashboardFacts,
    DashboardSnapshot,
    DayFacts,
    DayInsight,
    EventItem,
    LastSevenDaysStats,
    LongTermStats,
    QueueStats,
    RateMetric,
    RateStatus,
    TodayStats,
    ValueState,
)
from .themes import DEFAULT_HEATMAP_PRESETS, resolve_theme
from .ui_primitives import (
    COMPLETION_TOKEN_ROLE,
    CONTENT_MODE_INTERMEDIATE,
    DASHBOARD_PRIMITIVES,
    FOCUS_RING_OFFSET_PX,
    FOCUS_RING_PX,
    INTERACTION_TARGET_MIN_PX,
    VISUAL_CHROME_PX,
)


LEGACY_NAMES = {
    "1771074083": "Review Heatmap",
    "635082046": "New Cards Counter",
    "1556734708": "More Decks Stats and Time Left",
    "1143540799": "Events",
    "290511870": "Bible Verse Displayer",
}

_DASHBOARD_PRIMITIVES = frozenset(DASHBOARD_PRIMITIVES)


def _dashboard_primitive(name: str) -> str:
    if name not in _DASHBOARD_PRIMITIVES:
        raise ValueError("unknown dashboard primitive: {}".format(name))
    return name


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _duration(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if 0 < seconds < 60:
        return "{} sec".format(round(seconds))
    minutes = seconds / 60.0
    if minutes < 60:
        return "{} min".format("{:.1f}".format(minutes).rstrip("0").rstrip("."))
    hours = int(minutes // 60)
    remainder = round(minutes % 60)
    return "{} hr {} min".format(hours, remainder) if remainder else "{} hr".format(hours)


def _clock_time(value: datetime) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _eta(duration_seconds: int | None, now: datetime | None = None) -> str:
    """Format an available ETA; unavailable estimates are omitted by callers."""

    if duration_seconds is None:
        return ""
    if duration_seconds <= 0:
        return "Done"
    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.astimezone()
    completion = current + timedelta(seconds=duration_seconds)
    if completion.date() == current.date():
        return _clock_time(completion)
    if completion.date() == current.date() + timedelta(days=1):
        return "Tomorrow, {}".format(_clock_time(completion))
    label = "{} {}".format(completion.strftime("%b"), completion.day)
    if completion.year != current.year:
        label += ", {}".format(completion.year)
    return "{}, {}".format(label, _clock_time(completion))


def _rgba(hex_color: str, percent: int) -> str:
    raw = str(hex_color).lstrip("#")
    try:
        red, green, blue = (int(raw[index:index + 2], 16) for index in (0, 2, 4))
    except (TypeError, ValueError):
        red, green, blue = 255, 255, 255
    return "rgba({},{},{},{:.2f})".format(
        red, green, blue, min(100, max(0, int(percent))) / 100.0
    )


def _style(config: Mapping[str, Any], anki_dark: bool) -> str:
    appearance = config["appearance"]
    theme_name = str(appearance.get("preset", "Sapphire Glass"))
    preset_map = config.get("heatmap", {}).get("presets_by_theme", {})
    heatmap_name = (
        preset_map.get(theme_name)
        if isinstance(preset_map, Mapping)
        else DEFAULT_HEATMAP_PRESETS.get(theme_name)
    )
    theme = resolve_theme(
        theme_name,
        appearance.get("mode"),
        anki_dark,
        heatmap_name,
    )
    # The panel layer owns a readability floor even when the user asks for a
    # more transparent decorative background.
    safe_opacity = max(91, int(appearance.get("opacity", 88)))
    declarations = {
        "--hdo-bg": theme["background"],
        "--hdo-page-scrim-start": _rgba(theme["background"], 72),
        "--hdo-page-scrim-end": _rgba(theme["background"], 82),
        "--hdo-panel-background": _rgba(theme["panel_surface"], safe_opacity),
        "--hdo-panel-scrim": _rgba(theme["panel_surface"], 97),
        "--hdo-surface-solid": theme["surface"],
        "--hdo-border": theme["border"],
        "--hdo-control-border": theme["control_border"],
        "--hdo-text": theme["text"],
        "--hdo-muted": theme["muted"],
        "--hdo-disabled": theme["disabled"],
        "--hdo-accent": theme["accent"],
        "--hdo-selection": theme["selection"],
        "--hdo-accent-text": theme["accent_text"],
        "--hdo-on-accent": theme["on_accent"],
        "--hdo-on-selection": theme["on_selection"],
        "--hdo-accent-soft": theme["accent_soft"],
        "--hdo-forecast": theme["forecast"],
        "--hdo-due-stripe": theme["due_stripe"],
        "--hdo-review": theme["review"],
        "--hdo-event": theme["event"],
        "--hdo-on-event": theme["on_event"],
        "--hdo-shadow": theme["shadow"],
        "--hdo-focus": theme["focus"],
        "--hdo-new": theme["new"],
        "--hdo-success": theme["success"],
        "--hdo-{}".format(COMPLETION_TOKEN_ROLE): theme["completion"],
        "--hdo-warning": theme["warning"],
        "--hdo-danger": theme["danger"],
        "--hdo-danger-soft": theme["danger_soft"],
        "--hdo-heatmap-empty": theme["heatmap_empty"],
        "--hdo-on-heatmap-empty": theme["on_heatmap_empty"],
        "--hdo-heatmap-out-of-month": theme["heatmap_out_of_month"],
        "--hdo-on-heatmap-out-of-month": theme["on_heatmap_out_of_month"],
        "--hdo-heatmap-1": theme["heatmap_1"],
        "--hdo-heatmap-2": theme["heatmap_2"],
        "--hdo-heatmap-3": theme["heatmap_3"],
        "--hdo-heatmap-4": theme["heatmap_4"],
        "--hdo-heatmap-5": theme["heatmap_5"],
        "--hdo-on-heatmap-1": theme["on_heatmap_1"],
        "--hdo-on-heatmap-2": theme["on_heatmap_2"],
        "--hdo-on-heatmap-3": theme["on_heatmap_3"],
        "--hdo-on-heatmap-4": theme["on_heatmap_4"],
        "--hdo-on-heatmap-5": theme["on_heatmap_5"],
        "--hdo-target-size": "{}px".format(INTERACTION_TARGET_MIN_PX),
        "--hdo-control-visual": "{}px".format(VISUAL_CHROME_PX),
        "--hdo-focus-ring": "{}px".format(FOCUS_RING_PX),
        "--hdo-focus-offset": "{}px".format(FOCUS_RING_OFFSET_PX),
        "--hdo-scale": str(int(appearance.get("text_scale", 100)) / 100),
    }
    return ";".join("{}:{}".format(key, value) for key, value in declarations.items())


def _format_count(value: object) -> str:
    try:
        return format(max(0, int(value)), ",")
    except (TypeError, ValueError, OverflowError):
        return "0"


def _metric(label: str, value: object, metric_key: str, modifier: str = "") -> str:
    return (
        '<div class="hdo-metric-row {}" data-hdo-primitive="{}">'
        '<dt>{}</dt><dd data-hdo-metric="{}">{}</dd></div>'
    ).format(
        _escape(modifier),
        _dashboard_primitive("metric-row"),
        _escape(label),
        _escape(metric_key),
        _escape(value),
    )


def _stats_group(
    title: str,
    group_id: str,
    rows: Sequence[str],
    lead: str = "",
    heading_meta: str = "",
) -> str:
    if not rows and not lead:
        return ""
    return (
        '<section class="hdo-statistics-card" data-hdo-primitive="{}" '
        'aria-labelledby="{}-title"><header class="hdo-stat-card-header">'
        '<h3 id="{}-title">{}</h3>{}</header>{}<dl>{}</dl></section>'
    ).format(
        _dashboard_primitive("statistics-card"),
        _escape(group_id),
        _escape(group_id),
        _escape(title),
        heading_meta,
        lead,
        "".join(rows),
    )


def _facts_state(snapshot: DashboardSnapshot, name: str) -> ValueState[Any]:
    return getattr(snapshot.facts, name)


def _rounded_progress_percent(completed: int, workload: int) -> int:
    """Return an integer percentage rounded half-up from exact counts."""

    if workload <= 0:
        return 0
    return min(100, max(0, (200 * max(0, completed) + workload) // (2 * workload)))


def _progress_share(count: int, workload: int) -> str:
    if workload <= 0:
        return "0"
    return "{:.1f}".format(100 * max(0, count) / workload).rstrip("0").rstrip(".")


def _progress_segment(label: str, key: str, count: int, workload: int) -> str:
    safe_count = max(0, int(count))
    share = _progress_share(safe_count, workload)
    description = "{}: {} ({}%)".format(label, _format_count(safe_count), share)
    return (
        '<span class="hdo-progress-segment hdo-progress-segment--{}" '
        'data-hdo-progress-segment="{}" data-hdo-progress-count="{}" '
        'style="--hdo-progress-count:{}" title="{}">'
        '<span class="hdo-visually-hidden">{}</span></span>'
    ).format(
        _escape(key),
        _escape(key),
        safe_count,
        safe_count,
        _escape(description),
        _escape(description),
    )


def _progress_group(snapshot: DashboardSnapshot) -> str:
    today_state = _facts_state(snapshot, "today")
    queue_state = _facts_state(snapshot, "queue")
    buried_state = _facts_state(snapshot, "buried")
    rows: list[str] = []
    lead = ""
    heading_meta = ""
    if queue_state.is_available:
        queue: QueueStats = queue_state.value
        new_remaining = max(0, int(queue.new))
        learning_remaining = max(0, int(queue.learning))
        review_remaining = max(0, int(queue.review))
        remaining = new_remaining + learning_remaining + review_remaining
        if today_state.is_available:
            today: TodayStats = today_state.value
            completed = max(0, int(today.answers))
            workload = completed + remaining
            percent = _rounded_progress_percent(completed, workload)
            composition = (
                "{}% complete. Completed: {} ({}%); New remaining: {} ({}%); "
                "Learning remaining: {} ({}%); Reviews remaining: {} ({}%)."
            ).format(
                percent,
                _format_count(completed),
                _progress_share(completed, workload),
                _format_count(new_remaining),
                _progress_share(new_remaining, workload),
                _format_count(learning_remaining),
                _progress_share(learning_remaining, workload),
                _format_count(review_remaining),
                _progress_share(review_remaining, workload),
            )
            if workload == 0:
                composition = "No workload today. 0% complete."
            heading_meta = (
                '<span class="hdo-progress-complete" data-hdo-metric="progress.percent">'
                '{}% complete</span>'
            ).format(percent)
            lead = (
                '<div class="hdo-progress-track" data-hdo-progress-track role="progressbar" '
                'aria-label="Today’s workload composition" aria-valuemin="0" '
                'aria-valuemax="100" aria-valuenow="{}" aria-valuetext="{}">{}</div>'
            ).format(
                percent,
                _escape(composition),
                "".join((
                    _progress_segment("Completed", "completed", completed, workload),
                    _progress_segment("New remaining", "new", new_remaining, workload),
                    _progress_segment("Learning remaining", "learning", learning_remaining, workload),
                    _progress_segment("Reviews remaining", "review", review_remaining, workload),
                )),
            )
        rows.extend((
            _metric("New remaining", _format_count(new_remaining), "queue.new", "hdo-value--new"),
            _metric("Learning remaining", _format_count(learning_remaining), "queue.learning", "hdo-value--warning"),
            _metric("Reviews remaining", _format_count(review_remaining), "queue.review", "hdo-value--review"),
            _metric("Total remaining", _format_count(remaining), "queue.total"),
        ))
    if buried_state.is_available:
        buried: BuriedStats = buried_state.value
        buried_total = max(0, int(buried.new)) + max(0, int(buried.learning)) + max(0, int(buried.review))
        rows.append(_metric("Buried", _format_count(buried_total), "buried.total"))
    return _stats_group("Today’s Progress", "hdo-progress", rows, lead, heading_meta)


def _today_session_group(snapshot: DashboardSnapshot, show_eta: bool) -> str:
    state = _facts_state(snapshot, "today")
    if not state.is_available:
        return ""
    stats: TodayStats = state.value
    rows = [
        _metric("Cards studied", _format_count(stats.answers), "today.answers"),
        _metric("New cards studied", _format_count(stats.new_cards_studied), "today.new_cards_studied", "hdo-value--new"),
        _metric("Time", _duration(stats.seconds), "today.seconds"),
    ]
    if stats.pace_value is not None:
        pace = (
            "{:.1f} cards/min".format(stats.pace_value)
            if stats.pace_unit == "cards_per_minute"
            else "{:.1f} sec/card".format(stats.pace_value)
        )
        rows.append(_metric("Pace", pace, "today.pace"))
    queue_state = _facts_state(snapshot, "queue")
    if show_eta and queue_state.is_available:
        queue: QueueStats = queue_state.value
        eta = _eta(queue.estimated_duration_seconds)
        if eta:
            rows.append(_metric("ETA", eta, "queue.eta", "hdo-value--estimate"))
    return _stats_group("Today’s Session", "hdo-session", rows)


def _rate_text(value: RateMetric) -> str:
    return "{}%".format(value.percent) if value.status == RateStatus.AVAILABLE and value.percent is not None else ""


def _retention_role(value: RateMetric, target: int) -> str:
    if value.status != RateStatus.AVAILABLE or value.percent is None:
        return ""
    if value.percent >= target:
        return "hdo-value--success"
    if value.percent >= max(0, target - 10):
        return "hdo-value--warning"
    return "hdo-value--danger"


def _again_role(value: RateMetric, retention_target: int) -> str:
    if value.status != RateStatus.AVAILABLE or value.percent is None:
        return ""
    target = max(0, 100 - retention_target)
    if value.percent <= target:
        return "hdo-value--success"
    if value.percent <= min(100, target + 10):
        return "hdo-value--warning"
    return "hdo-value--danger"


def _last_seven_group(snapshot: DashboardSnapshot, target: int) -> str:
    state = _facts_state(snapshot, "last_seven_days")
    if not state.is_available:
        return ""
    stats: LastSevenDaysStats = state.value
    rows = [
        _metric("Cards studied", _format_count(stats.cards_studied), "last_seven_days.cards_studied"),
        _metric("New cards studied", _format_count(stats.new_cards_studied), "last_seven_days.new_cards_studied", "hdo-value--new"),
    ]
    retention = _rate_text(stats.retention)
    if retention:
        rows.append(_metric("Retention", retention, "last_seven_days.retention", _retention_role(stats.retention, target)))
    again = _rate_text(stats.again_rate)
    if again:
        rows.append(_metric("Again rate", again, "last_seven_days.again_rate", _again_role(stats.again_rate, target)))
    return _stats_group("Last 7 Days", "hdo-last-seven", rows)


def _all_time_group(snapshot: DashboardSnapshot, target: int) -> str:
    state = _facts_state(snapshot, "long_term")
    if not state.is_available:
        return ""
    stats: LongTermStats = state.value
    day_text = lambda count: "{} day{}".format(_format_count(count), "" if count == 1 else "s")
    rows = [
        _metric("Avg cards/day", _format_count(stats.average_reviews_per_active_day), "long_term.average_reviews_per_active_day"),
        _metric("Current streak", day_text(stats.current_streak), "long_term.current_streak"),
        _metric("Longest streak", day_text(stats.longest_streak), "long_term.longest_streak"),
    ]
    retention = _rate_text(stats.lifetime_retention)
    if retention:
        rows.append(_metric("Lifetime retention", retention, "long_term.lifetime_retention", _retention_role(stats.lifetime_retention, target)))
    rows.append(_metric("Lifetime cards studied", _format_count(stats.lifetime_cards_studied), "long_term.lifetime_cards_studied"))
    return _stats_group("All Time", "hdo-all-time", rows)


def _metrics(snapshot: DashboardSnapshot, config: Mapping[str, Any]) -> str:
    visibility = config["visibility"]
    target = int(config.get("study", {}).get("retention_target", 80))
    groups: list[str] = []
    if visibility.get("remaining", True):
        groups.append(_progress_group(snapshot))
    if visibility.get("today", True):
        groups.append(_today_session_group(snapshot, bool(config.get("study", {}).get("show_eta", True))))
    if visibility.get("heatmap_metrics", True):
        groups.extend((_last_seven_group(snapshot, target), _all_time_group(snapshot, target)))
    groups = [group for group in groups if group]
    if not groups:
        return ""
    return (
        '<section class="hdo-summary-metrics-grid" data-hdo-primitive="{}" '
        'aria-label="Study summary">{}</section>'
    ).format(_dashboard_primitive("summary-metrics-grid"), "".join(groups))


def _safe_json(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        payload.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _selected_iso(value: object) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat() if value else ""
    except (TypeError, ValueError):
        return ""


def _json_value(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _value_state_payload(value: ValueState[Any]) -> dict[str, Any]:
    return {
        "status": _json_value(value.status),
        "value": _json_value(value.value),
        "reason": _json_value(value.reason),
    }


def _event_rows(items: Sequence[EventItem]) -> list[dict[str, Any]]:
    return [
        {"id": item.event_id, "name": item.name, "date": item.date}
        for item in items
        if not item.archived
    ]


def _event_state_payload(value: ValueState[Sequence[EventItem]]) -> dict[str, Any]:
    payload = _value_state_payload(value)
    if value.is_available:
        payload["value"] = _event_rows(value.value)
    return payload


def _day_facts_payload(day: DayFacts) -> dict[str, Any]:
    return {
        "date": day.date,
        "relation": _json_value(day.relation),
        "reviews_completed": _value_state_payload(day.reviews_completed),
        "reviews_due": _value_state_payload(day.reviews_due),
        "new_cards_studied": _value_state_payload(day.new_cards_studied),
        "again_count": _value_state_payload(day.again_count),
        "events": _event_state_payload(day.events),
        "domain_state": _json_value(day.domain_state),
        "most_missed_available": bool(
            day.most_missed_target.exact and day.most_missed_target.card_ids
        ),
    }


def day_insight_payload(insight: DayInsight) -> dict[str, object]:
    """Return capability-only fields; no card content or native IDs cross the bridge."""

    facts = insight.day_facts
    target = facts.most_missed_target if facts is not None else insight.browse_target
    return {
        "date": insight.date,
        "state": _json_value(facts.domain_state) if facts is not None else "unavailable",
        "most_missed_available": bool(target.exact and target.card_ids),
    }


def _calendar_payload_dates(anchor_iso: str, view: str, week_start: int) -> list[str]:
    anchor = date.fromisoformat(anchor_iso)
    if view == "year":
        start, end = date(anchor.year, 1, 1), date(anchor.year, 12, 31)
    else:
        start = date(anchor.year, anchor.month, 1)
        next_month = date(anchor.year + 1, 1, 1) if anchor.month == 12 else date(anchor.year, anchor.month + 1, 1)
        end = next_month - timedelta(days=1)
        normalized = max(0, min(6, int(week_start)))
        start -= timedelta(days=(start.weekday() - normalized) % 7)
        end += timedelta(days=(normalized + 6 - end.weekday()) % 7)
    return [
        (start + timedelta(days=offset)).isoformat()
        for offset in range((end - start).days + 1)
    ]


def calendar_range_payload(
    snapshot: DashboardSnapshot,
    anchor: str,
    view: str,
    week_start: int = 0,
) -> dict[str, Any]:
    anchor_iso = _selected_iso(anchor)
    if not anchor_iso or view not in {"month", "year"}:
        raise ValueError("calendar range requires a valid anchor and view")
    week_start = max(0, min(6, int(week_start)))
    facts = snapshot.facts
    return {
        "anchor": anchor_iso,
        "view": view,
        "week_start": week_start,
        "source_revision": facts.revision,
        "activity": [
            _day_facts_payload(facts.for_date(iso_date))
            for iso_date in _calendar_payload_dates(anchor_iso, view, week_start)
        ],
    }


def dashboard_facts_payload(
    snapshot: DashboardSnapshot,
    config: Mapping[str, Any],
    selected_date: str = "",
    facts_revision: int = 0,
) -> dict[str, Any]:
    facts = snapshot.facts
    preview_date = _selected_iso(config.get("_preview_selected_date"))
    scheduling_date = _selected_iso(facts.scheduling_date)
    calendar_date = _selected_iso(facts.calendar_date) or scheduling_date
    selected = preview_date or _selected_iso(selected_date) or scheduling_date or calendar_date
    view = str(config.get("heatmap", {}).get("calendar_view", "year"))
    week_start = int(config.get("heatmap", {}).get("week_start", 0))
    range_payload = calendar_range_payload(snapshot, selected or date.today().isoformat(), view, week_start)
    return {
        "activity": range_payload["activity"],
        "events": _event_state_payload(facts.events),
        "events_enabled": bool(config.get("visibility", {}).get("events", True)),
        "today": scheduling_date,
        "calendar_date": calendar_date,
        "anchor": selected or calendar_date,
        "selected_date": selected,
        "scheduling_date": scheduling_date,
        "day_cutoff_iso": facts.next_rollover,
        "source_revision": facts.revision,
        "revision": max(0, int(facts_revision)),
        "due_load_reference": max(0.0, float(facts.due_load_reference)),
        "statistics": {
            "today": _value_state_payload(facts.today),
            "queue": _value_state_payload(facts.queue),
            "buried": _value_state_payload(facts.buried),
            "last_seven_days": _value_state_payload(facts.last_seven_days),
            "long_term": _value_state_payload(facts.long_term),
        },
        "retention_target": int(config.get("study", {}).get("retention_target", 80)),
        "view": view,
        "week_start": week_start,
    }


def _calendar_controls(config: Mapping[str, Any]) -> str:
    view = str(config.get("heatmap", {}).get("calendar_view", "year"))
    return (
        '<div class="hdo-header-controls">'
        '<div class="hdo-view-switch" role="group" aria-label="Calendar view">'
        '<button type="button" data-hdo-view="month" aria-pressed="{}">Month</button>'
        '<button type="button" data-hdo-view="year" aria-pressed="{}">Year</button></div>'
        '<div class="hdo-period-controls" aria-label="Calendar period">'
        '<button type="button" data-hdo-calendar="previous" aria-label="Previous period" title="Previous period">‹</button>'
        '<button type="button" data-hdo-calendar="today">Today</button>'
        '<button type="button" data-hdo-calendar="next" aria-label="Next period" title="Next period">›</button></div>'
        '<button type="button" class="hdo-settings" data-hdo-command="calendar-settings" '
        'aria-label="Calendar settings" title="Calendar settings">⚙</button>'
        '</div>'
    ).format("true" if view == "month" else "false", "true" if view == "year" else "false")


def _calendar(snapshot: DashboardSnapshot, config: Mapping[str, Any], selected_date: str, facts_revision: int) -> str:
    payload = dashboard_facts_payload(snapshot, config, selected_date, facts_revision)
    event_legend = (
        '<span class="hdo-legend-key"><i class="hdo-legend-event" aria-hidden="true"></i>Event</span>'
        if config.get("visibility", {}).get("events", True)
        else ""
    )
    return (
        '<section class="hdo-card hdo-dashboard-panel hdo-calendar-card" data-hdo-primitive="{}" '
        'aria-labelledby="hdo-calendar-heading">'
        '<header class="hdo-dashboard-header" data-hdo-primitive="{}"><div>'
        '<p class="hdo-eyebrow">Study Calendar</p><h2 id="hdo-calendar-heading" data-hdo-calendar-title></h2>'
        '</div>{}</header>'
        '<div class="hdo-calendar-shell" data-hdo-calendar-view="{}" aria-busy="false">'
        '<div class="hdo-month-weekdays" aria-hidden="true"></div>'
        '<div class="hdo-calendar-grid" role="grid" aria-label="Study calendar"></div>'
        '</div>'
        '<div class="hdo-calendar-legend" aria-label="Calendar legend">'
        '<span class="hdo-completion-legend"><span>Less completed</span>'
        '<i data-level="1"></i><i data-level="2"></i><i data-level="3"></i><i data-level="4"></i><i data-level="5"></i>'
        '<span>More</span></span>'
        '<span class="hdo-due-legend"><span>Reviews due</span>'
        '<i data-load="low"></i><i data-load="medium"></i><i data-load="high"></i></span>{}</div>'
        '<div class="hdo-calendar-context-bar" data-hdo-primitive="{}" aria-live="polite">'
        '<div class="hdo-context-copy">'
        '<div class="hdo-context-selected"><strong>Selected date:</strong> <span data-hdo-context-date></span></div>'
        '<div class="hdo-context-event" data-hdo-context-event hidden>'
        '<span class="hdo-context-event-marker" aria-hidden="true"></span>'
        '<button type="button" class="hdo-context-event-link" data-hdo-open-events></button>'
        '<span data-hdo-event-more></span>'
        '<button type="button" class="hdo-icon-button" data-hdo-edit-event '
        'aria-label="Edit event" title="Edit event">✎</button></div></div>'
        '<div class="hdo-context-actions">'
        '<button type="button" class="hdo-context-action hdo-context-action--primary" data-hdo-primary-action hidden></button>'
        '<button type="button" class="hdo-context-action" data-hdo-most-missed hidden>Most missed</button>'
        '</div></div>'
        '<div id="hdo-calendar-tooltip" class="hdo-calendar-tooltip" role="tooltip" hidden>'
        '<h3 data-hdo-tooltip-heading></h3><dl data-hdo-tooltip-rows></dl></div>'
        '<p class="hdo-visually-hidden" role="status" aria-live="polite" data-hdo-calendar-status></p>'
        '<script type="application/json" class="hdo-calendar-data">{}</script>'
        '</section>'
    ).format(
        _dashboard_primitive("dashboard-panel"),
        _dashboard_primitive("dashboard-header"),
        _calendar_controls(config),
        _escape(config.get("heatmap", {}).get("calendar_view", "year")),
        event_legend,
        _dashboard_primitive("calendar-context-bar"),
        _safe_json(payload),
    )


def _bible(snapshot: DashboardSnapshot, config: Mapping[str, Any]) -> str:
    bible = config["bible"]
    custom_color = "" if bible.get("theme_aware_color", True) else "color:{};".format(_escape(bible.get("font_color", "#1E90FF")))
    reference = (
        '<div class="hdo-verse-reference">{}</div>'.format(snapshot.verse.reference_html)
        if snapshot.verse.reference_html
        else ""
    )
    return (
        '<section class="hdo-card hdo-dashboard-panel hdo-bible-card" data-hdo-primitive="{}" '
        'aria-labelledby="hdo-bible-title"><p class="hdo-eyebrow">Bible Verse</p>'
        '<h2 id="hdo-bible-title" class="hdo-visually-hidden">Bible Verse</h2>'
        '<div class="hdo-verse-scrim"><blockquote class="hdo-verse" '
        'style="{}--hdo-verse-font:{};--hdo-verse-size:{}">'
        '<div class="hdo-verse-body">{}</div>{}</blockquote></div></section>'
    ).format(
        _dashboard_primitive("bible-verse-card"),
        custom_color,
        _escape(bible.get("font_family", "Georgia, serif")),
        _escape(bible.get("font_size", "28px")),
        snapshot.verse.body_html,
        reference,
    )


def _data_warning(snapshot: DashboardSnapshot, config: Mapping[str, Any]) -> str:
    states = []
    visibility = config.get("visibility", {})
    if visibility.get("today", True):
        states.append(snapshot.facts.today)
    if visibility.get("remaining", True):
        states.extend((snapshot.facts.queue, snapshot.facts.buried))
    if visibility.get("heatmap_metrics", True):
        states.extend((snapshot.facts.last_seven_days, snapshot.facts.long_term))
    unavailable = any(_json_value(state.status) == "unavailable" for state in states)
    if not unavailable:
        return ""
    return (
        '<div class="hdo-data-warning" data-hdo-primitive="{}" role="alert">'
        '<span>Some dashboard data is unavailable.</span>'
        '<button type="button" data-hdo-command="retry">Retry</button></div>'
    ).format(_dashboard_primitive("alert-banner"))


def render_dashboard(
    snapshot: DashboardSnapshot,
    config: Mapping[str, Any],
    anki_dark: bool = False,
    preview: bool = False,
    selected_date: str = "",
    facts_revision: int = 0,
) -> str:
    render_config = dict(config)
    if preview:
        render_config["_preview_context"] = True
    visibility = render_config["visibility"]
    sections: list[str] = []
    has_calendar = bool(visibility.get("heatmap", True))
    if has_calendar:
        sections.append(_calendar(snapshot, render_config, selected_date, facts_revision))
    metrics = _metrics(snapshot, render_config)
    has_metrics = bool(metrics)
    if metrics:
        sections.append(metrics)
    if visibility.get("bible", True):
        sections.append(_bible(snapshot, render_config))
    if not sections:
        sections.append(
            '<section class="hdo-card hdo-recovery-card" data-hdo-primitive="{}" role="status">'
            '<p class="hdo-eyebrow">Home Screen Dashboard</p><h2>Dashboard sections are hidden</h2>'
            '<p>Turn on at least one Home screen section to show study information here.</p>'
            '<button type="button" data-hdo-command="settings">Open settings</button></section>'.format(
                _dashboard_primitive("recovery-card")
            )
        )
    payload = dashboard_facts_payload(snapshot, render_config, selected_date, facts_revision)
    if not visibility.get("heatmap", True):
        sections.append('<script type="application/json" class="hdo-dashboard-data">{}</script>'.format(_safe_json(payload)))
    return (
        '<div id="hdo-dashboard" class="hdo-dashboard{}" data-hdo-preview="{}" '
        'data-hdo-runtime-stack="{}" data-hdo-stack-position="{}" '
        'data-hdo-content-mode="{}" data-hdo-high-contrast="{}" '
        'data-hdo-calendar-view="{}" data-hdo-has-calendar="{}" data-hdo-has-metrics="{}" '
        'data-hdo-enlarged-text="{}" aria-busy="false" style="{}">'
        '<main class="hdo-stack">{}{}</main></div>'
    ).format(
        " hdo-dashboard--preview" if preview else "",
        "true" if preview else "false",
        "false" if preview else "true",
        _escape(render_config.get("home_screen", {}).get("position", "top")),
        CONTENT_MODE_INTERMEDIATE,
        "true" if render_config["appearance"].get("preset") == "High Contrast" else "false",
        _escape(render_config.get("heatmap", {}).get("calendar_view", "year")),
        "true" if has_calendar else "false",
        "true" if has_metrics else "false",
        "true" if int(render_config.get("appearance", {}).get("text_scale", 100)) >= 125 else "false",
        _style(render_config, anki_dark),
        _data_warning(snapshot, render_config),
        "".join(sections),
    )


def render_loading(config: Mapping[str, Any], anki_dark: bool = False) -> str:
    bible_skeleton = (
        '<div class="hdo-loading-region hdo-loading-region--bible"><span></span></div>'
        if config.get("visibility", {}).get("bible", True)
        else ""
    )
    return (
        '<div id="hdo-dashboard" class="hdo-dashboard hdo-dashboard--loading" '
        'data-hdo-runtime-stack="true" data-hdo-stack-position="{}" '
        'data-hdo-content-mode="{}" aria-busy="true" style="{}"><main class="hdo-stack">'
        '<section class="hdo-card hdo-loading-card" data-hdo-primitive="{}" aria-busy="true">'
        '<p class="hdo-eyebrow">Study Calendar</p><h2>Loading your study dashboard…</h2>'
        '<p class="hdo-loading-message" data-hdo-loading-message role="status" aria-live="polite"></p>'
        '<div class="hdo-loading-layout" data-hdo-loading-skeleton aria-hidden="true">'
        '<div class="hdo-loading-region hdo-loading-region--calendar">{}</div>'
        '<div class="hdo-loading-region hdo-loading-region--metrics">{}</div>{}</div>'
        '<div class="hdo-loading-failure" data-hdo-loading-failure hidden>'
        '<p>The dashboard could not finish loading.</p><div class="hdo-loading-actions">'
        '<button type="button" data-hdo-command="retry">Retry</button>'
        '<button type="button" data-hdo-command="diagnostics">Open diagnostics</button>'
        '</div></div></section>'
        '</main></div>'
    ).format(
        _escape(config.get("home_screen", {}).get("position", "top")),
        CONTENT_MODE_INTERMEDIATE,
        _style(config, anki_dark),
        _dashboard_primitive("loading-card"),
        "".join("<span></span>" for _ in range(28)),
        "".join("<span></span>" for _ in range(4)),
        bible_skeleton,
    )


def render_activation_required(
    enabled_ids: Sequence[str],
    config: Mapping[str, Any],
    anki_dark: bool = False,
) -> str:
    names = [LEGACY_NAMES.get(value, value) for value in enabled_ids]
    return (
        '<div id="hdo-dashboard" class="hdo-dashboard" data-hdo-runtime-stack="true" '
        'data-hdo-stack-position="{}" data-hdo-content-mode="{}" style="{}">'
        '<main class="hdo-stack"><section class="hdo-card hdo-recovery-card" '
        'data-hdo-primitive="{}" role="status"><p class="hdo-eyebrow">Home Screen Dashboard</p>'
        '<h1>Ready to replace duplicate home-screen add-ons</h1>'
        '<p>The unified dashboard is paused while these legacy add-ons are enabled: <strong>{}</strong>.</p>'
        '<button type="button" data-hdo-command="settings">Open settings</button>'
        '</section></main></div>'
    ).format(
        _escape(config.get("home_screen", {}).get("position", "top")),
        CONTENT_MODE_INTERMEDIATE,
        _style(config, anki_dark),
        _dashboard_primitive("recovery-card"),
        _escape(", ".join(names)),
    )
