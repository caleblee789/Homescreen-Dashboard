"""Compact, namespaced Deck Browser renderer shared by runtime and preview."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timedelta
import html
import json
from typing import Any, Mapping, Optional, Sequence

from .models import (
    BuriedStats,
    CalendarDayEvent,
    DailyActivity,
    DashboardSnapshot,
    EventItem,
    LongTermStats,
    QueueStats,
    TodayStats,
    VerseContent,
)
from .themes import resolve_theme


LEGACY_NAMES = {
    "1771074083": "Review Heatmap",
    "635082046": "New Cards Counter",
    "1556734708": "More Decks Stats and Time Left",
    "1143540799": "Events",
    "290511870": "Bible Verse Displayer",
}


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _duration(seconds: float) -> str:
    minutes = max(0.0, seconds) / 60.0
    if minutes < 1 and seconds > 0:
        return "{} sec".format(round(seconds))
    if minutes < 60:
        value = "{:.1f}".format(minutes).rstrip("0").rstrip(".")
        return "{} min".format(value)
    hours = int(minutes // 60)
    remainder = round(minutes % 60)
    return "{} hr {} min".format(hours, remainder) if remainder else "{} hr".format(hours)


def _clock_time(value: datetime) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _eta(duration_seconds: int | None, now: datetime | None = None) -> str:
    if duration_seconds is None:
        return "—"
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
    calendar_date = "{} {}".format(completion.strftime("%b"), completion.day)
    if completion.year != current.year:
        calendar_date += ", {}".format(completion.year)
    return "{}, {}".format(calendar_date, _clock_time(completion))


def _rgba(hex_color: str, percent: int) -> str:
    candidate = hex_color.lstrip("#")
    try:
        red, green, blue = (int(candidate[index:index + 2], 16) for index in (0, 2, 4))
    except (ValueError, TypeError):
        red, green, blue = 255, 255, 255
    return "rgba({},{},{},{:.2f})".format(red, green, blue, min(100, max(0, percent)) / 100.0)


def _style(config: Mapping[str, Any], anki_dark: bool) -> str:
    appearance = config["appearance"]
    theme = resolve_theme(appearance.get("preset"), appearance.get("mode"), anki_dark)
    density = {"compact": "8px", "comfortable": "11px", "spacious": "15px"}.get(
        str(appearance.get("density")), "11px"
    )
    declarations = {
        "--hdo-bg": theme["background"],
        "--hdo-surface": _rgba(theme["surface"], int(appearance.get("opacity", 88))),
        "--hdo-surface-solid": theme["surface"],
        "--hdo-border": theme["border"],
        "--hdo-control-border": theme["control_border"],
        "--hdo-text": theme["text"],
        "--hdo-muted": theme["muted"],
        "--hdo-accent": theme["accent"],
        "--hdo-on-accent": theme["on_accent"],
        "--hdo-accent-soft": theme["accent_soft"],
        "--hdo-forecast": theme["forecast"],
        "--hdo-shadow": theme["shadow"],
        "--hdo-focus": theme["focus"],
        "--hdo-success": theme["success"],
        "--hdo-progress-percent": theme["progress_percent"],
        "--hdo-warning": theme["warning"],
        "--hdo-danger": theme["danger"],
        "--hdo-empty": theme["empty"],
        "--hdo-gap": density,
        "--hdo-blur": "{}px".format(int(appearance.get("blur", 18))),
        "--hdo-scale": "{}".format(int(appearance.get("text_scale", 100)) / 100),
    }
    return ";".join("{}:{}".format(key, value) for key, value in declarations.items())


def _metric(label: str, value: object, modifier: str = "") -> str:
    return (
        '<div class="hdo-stat {}"><dt>{}</dt><dd>{}</dd></div>'
    ).format(_escape(modifier), _escape(label), _escape(value))


def _stats_group(
    title: str,
    group_id: str,
    metrics: Sequence[tuple[str, object, str]],
    seen: set[str],
    lead_markup: str = "",
) -> str:
    rows = []
    for label, value, modifier in metrics:
        normalized_label = str(label).strip().casefold()
        metric_key = "{}::{}".format(group_id, normalized_label)
        if metric_key in seen:
            continue
        seen.add(metric_key)
        rows.append(_metric(str(label), value, modifier))
    return (
        '<section class="hdo-stat-group" aria-labelledby="{}-title">'
        '<h3 id="{}-title">{}</h3>{}<dl>{}</dl></section>'
    ).format(
        _escape(group_id),
        _escape(group_id),
        _escape(title),
        lead_markup,
        "".join(rows),
    )


def _today_group(snapshot: DashboardSnapshot, seen: set[str], show_eta: bool) -> str:
    stats = snapshot.today
    pace = "—"
    if stats.pace_value is not None:
        pace = (
            "{:.1f} cards/min".format(stats.pace_value)
            if stats.pace_unit == "cards_per_minute"
            else "{:.1f} sec/card".format(stats.pace_value)
        )
    metrics = [
        ("Total Cards Studied", stats.answers, "hdo-stat--primary"),
        ("New Cards Studied", stats.new_cards_studied, "hdo-stat--new"),
        ("Time studied", _duration(stats.seconds), ""),
        ("Pace", pace, ""),
    ]
    if show_eta:
        eta_available = not any(
            key in snapshot.errors for key in ("today", "queue", "dashboard")
        )
        eta = _eta(snapshot.queue.estimated_duration_seconds) if eta_available else "—"
        metrics.append(("ETA", eta, "hdo-stat--estimate"))
    return _stats_group(
        "Today",
        "hdo-today",
        metrics,
        seen,
    )


def _nonnegative_count(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _progress_group(snapshot: DashboardSnapshot, seen: set[str]) -> str:
    today_available = not any(key in snapshot.errors for key in ("today", "dashboard"))
    queue_available = not any(key in snapshot.errors for key in ("queue", "dashboard"))

    completed = _nonnegative_count(snapshot.today.answers)
    queue = snapshot.queue
    new = _nonnegative_count(queue.new)
    learning = _nonnegative_count(queue.learning)
    review = _nonnegative_count(queue.review)
    remaining = new + learning + review

    percent: int | None = None
    if today_available and queue_available:
        workload = completed + remaining
        if workload > 0:
            percent = min(100, max(0, (completed * 100 + workload // 2) // workload))

    if percent is None:
        if not today_available or not queue_available:
            state = "unavailable"
            description = "Today’s progress is unavailable because Today or queue data could not be loaded."
        else:
            state = "empty"
            description = "No completed answers or actionable cards are available for the current day."
        aria_now = ""
        segment_counts = (0, 0, 0, 0)
    else:
        state = "available"
        description = (
            "{}% complete: {} completed answers, {} new remaining, "
            "{} learning remaining, {} reviews remaining, {} total remaining."
        ).format(percent, completed, new, learning, review, remaining)
        aria_now = ' aria-valuenow="{}"'.format(percent)
        segment_counts = (completed, new, learning, review)

    segments = "".join(
        (
            '<span class="hdo-progress-segment hdo-progress-segment--{}" '
            'data-hdo-segment="{}" data-hdo-count="{}" '
            'style="--hdo-progress-value:{}" aria-hidden="true"></span>'
        ).format(name, name, count, count)
        for name, count in zip(("completed", "new", "learning", "review"), segment_counts)
    )
    progress = (
        '<div class="hdo-progress-bar" data-hdo-progress-state="{}" role="progressbar" '
        'aria-labelledby="hdo-remaining-title" aria-valuemin="0" aria-valuemax="100"{} '
        'aria-valuetext="{}">{}</div>'
    ).format(state, aria_now, _escape(description), segments)

    queue_value = lambda value: value if queue_available else "—"
    metrics = [
        ("Percent Complete", "{}%".format(percent) if percent is not None else "—", "hdo-stat--progress hdo-stat--completed"),
        ("New remaining", queue_value(new), "hdo-stat--progress hdo-stat--new"),
        ("Learning remaining", queue_value(learning), "hdo-stat--progress hdo-stat--learning"),
        ("Reviews remaining", queue_value(review), "hdo-stat--progress hdo-stat--review"),
        ("Total remaining", queue_value(remaining), ""),
    ]
    return _stats_group("Today’s Progress", "hdo-remaining", metrics, seen, progress)


def _buried_group(snapshot: DashboardSnapshot, seen: set[str]) -> str:
    stats = snapshot.buried
    return _stats_group(
        "Buried Cards",
        "hdo-buried",
        (
            ("New", stats.new, "hdo-stat--new"),
            ("Learning", stats.learning, "hdo-stat--learning"),
            ("Reviews", stats.review, "hdo-stat--primary"),
        ),
        seen,
    )


def _consistency_group(snapshot: DashboardSnapshot, seen: set[str]) -> str:
    stats = snapshot.long_term
    return _stats_group(
        "Consistency",
        "hdo-consistency",
        (
            ("Avg cards / day", stats.average_reviews_per_active_day, ""),
            ("Active days", "{}%".format(stats.active_days_percent), ""),
            ("Longest streak", "{} days".format(stats.longest_streak), ""),
            ("Current streak", "{} days".format(stats.current_streak), ""),
        ),
        seen,
    )


def _safe_json(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        payload.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _active_event_payload(
    config: Mapping[str, Any],
    enabled: bool,
    calendar_events: Optional[Sequence[CalendarDayEvent]] = None,
) -> list[dict[str, object]]:
    if not enabled:
        return []
    if calendar_events is not None:
        return [
            {
                "id": item.event_id,
                "occurrence_id": item.occurrence_id,
                "date": item.date,
                "name": item.name,
                "source_id": item.source_id,
                "source_name": item.source_name,
                "editable": item.editable,
            }
            for item in calendar_events
        ]
    rows = []
    for item in config.get("events", {}).get("items", []):
        if not isinstance(item, Mapping) or item.get("archived"):
            continue
        event_date = item.get("date")
        event_name = item.get("name")
        if isinstance(event_date, str) and isinstance(event_name, str):
            rows.append(
                {
                    "id": str(item.get("id", "")),
                    "occurrence_id": str(item.get("id", "")),
                    "date": event_date,
                    "name": event_name,
                    "source_id": "local",
                    "source_name": "Local",
                    "editable": True,
                }
            )
    reverse = config.get("events", {}).get("sort") == "descending"
    return sorted(rows, key=lambda item: (item["date"], item["name"].casefold()), reverse=reverse)


def _calendar_controls(config: Mapping[str, Any]) -> str:
    view = str(config["heatmap"].get("calendar_view", "year"))
    segmented = (
        '<div class="hdo-view-switch" role="group" aria-label="Calendar view">'
        '<button type="button" data-hdo-view="month" aria-pressed="{}">Month</button>'
        '<button type="button" data-hdo-view="year" aria-pressed="{}">Year</button></div>'
    ).format("true" if view == "month" else "false", "true" if view == "year" else "false")
    controls = (
        '<div class="hdo-period-controls" aria-label="Calendar period">'
        '<button type="button" data-hdo-calendar="previous" title="Previous period" aria-label="Previous period">&#8249;</button>'
        '<button type="button" data-hdo-calendar="today">Today</button>'
        '<button type="button" data-hdo-calendar="next" title="Next period" aria-label="Next period">&#8250;</button>'
        '</div>'
    )
    return (
        '<div class="hdo-header-controls">{}{}'
        '<button type="button" class="hdo-settings" data-hdo-command="settings" '
        'aria-label="Open Home Dashboard settings" title="Dashboard settings">&#9881;</button></div>'
    ).format(segmented, controls)


def _calendar(
    snapshot: DashboardSnapshot,
    config: Mapping[str, Any],
    stats_markup: str = "",
    calendar_events: Optional[Sequence[CalendarDayEvent]] = None,
    calendar_generation: int = 0,
    calendar_range: Optional[tuple[str, str]] = None,
    calendar_sources: Optional[Sequence[Mapping[str, Any]]] = None,
) -> str:
    visibility = config["visibility"]
    view = str(config["heatmap"].get("calendar_view", "year"))
    events_enabled = bool(visibility.get("events", True))
    source_errors = [
        {"name": str(source.get("name", "Calendar")), "error": str(source.get("last_error", ""))}
        for source in (calendar_sources or [])
        if source.get("last_error")
    ]
    loaded_start, loaded_end = calendar_range or ("", "")
    payload = {
        "activity": [asdict(day) for day in snapshot.activity],
        "events": _active_event_payload(config, events_enabled, calendar_events),
        "today": date.today().isoformat(),
        "scheduling_date": snapshot.scheduling_date or date.today().isoformat(),
        "day_cutoff_iso": snapshot.day_cutoff_iso,
        "view": view,
        "week_start": int(config["heatmap"].get("week_start", 0)),
        "calendar_generation": int(calendar_generation),
        "loaded_start": loaded_start,
        "loaded_end": loaded_end,
        "source_errors": source_errors,
    }
    manage_action = (
        '<button type="button" class="hdo-details-action" data-hdo-manage-events>Manage this date</button>'
        if events_enabled
        else ""
    )
    event_legend = '<span><i class="hdo-legend-event"></i>Event</span>' if events_enabled else ""
    stale_notice = (
        '<button type="button" class="hdo-calendar-source-warning" data-hdo-manage-calendars '
        'aria-label="One or more calendars are using cached data. Manage calendars for details.">'
        '{} calendar{} using cached data</button>'.format(
            len(source_errors), " is" if len(source_errors) == 1 else "s are"
        )
        if source_errors
        else ""
    )
    return (
        '<div class="hdo-calendar-region" data-hdo-calendar-view="{}" data-hdo-events-enabled="{}">'
        '<div class="hdo-calendar-workspace">'
        '<div class="hdo-calendar-primary">'
        '<div class="hdo-calendar-subheader"><strong class="hdo-calendar-title" aria-live="polite"></strong>'
        '<span class="hdo-calendar-load-status" data-hdo-calendar-load-status role="status" aria-live="polite"></span>{}</div>'
        '<div class="hdo-calendar-frame"><div class="hdo-calendar-layout">'
        '<div class="hdo-year-weekdays" aria-hidden="true"></div>'
        '<div class="hdo-calendar-content">'
        '<div class="hdo-year-months" aria-hidden="true"></div>'
        '<div class="hdo-month-weekdays" aria-hidden="true"></div>'
        '<div class="hdo-calendar" role="grid" aria-label="Study calendar"></div>'
        '</div></div></div>'
        '<div class="hdo-calendar-footer"><div class="hdo-calendar-legend" aria-label="Calendar legend">'
        '<span class="hdo-intensity-legend"><span>Less</span><i data-level="1"></i><i data-level="2"></i><i data-level="3"></i><i data-level="4"></i><i data-level="5"></i><span>More completed</span></span>'
        '<span><i class="hdo-legend-due"></i>Due Today</span>'
        '{}</div>'
        '<span class="hdo-calendar-help">Select a date for details</span></div>'
        '</div>'
        '<div class="hdo-calendar-secondary" data-hdo-has-stats="{}">'
        '<section class="hdo-date-details" role="region" aria-labelledby="hdo-date-title" data-hdo-date-details hidden>'
        '<button type="button" class="hdo-details-close" data-hdo-details-close aria-label="Close date details">&#215;</button>'
        '<div class="hdo-details-content" data-hdo-details-content hidden>'
        '<h3 id="hdo-date-title" data-hdo-detail-date></h3>'
        '<dl class="hdo-date-summary"><div><dt>Completed reviews</dt><dd data-hdo-detail-completed></dd></div>'
        '<div><dt>Due Today</dt><dd data-hdo-detail-due></dd></div></dl>'
        '<div class="hdo-date-events"><h4>Events</h4><ul data-hdo-detail-events></ul>'
        '<p class="hdo-date-events-empty" data-hdo-detail-events-empty>No events scheduled.</p></div>'
        '<div class="hdo-details-actions"><button type="button" class="hdo-details-action hdo-details-action--primary" data-hdo-browse-date>Browse cards</button>'
        '{}'
        '</div></div></section>'
        '{}'
        '</div>'
        '</div>'
        '<div id="hdo-day-preview" class="hdo-day-preview" role="tooltip" data-hdo-day-preview hidden>'
        '<strong data-hdo-day-preview-date></strong><span data-hdo-day-preview-summary></span></div>'
        '<script type="application/json" class="hdo-calendar-data">{}</script>'
        '</div>'
    ).format(
        _escape(view),
        "true" if events_enabled else "false",
        stale_notice,
        event_legend,
        "true" if stats_markup else "false",
        manage_action,
        stats_markup,
        _safe_json(payload),
    )


def _errors(snapshot: DashboardSnapshot) -> str:
    if not snapshot.errors:
        return ""
    details = "; ".join("{}: {}".format(key, value) for key, value in sorted(snapshot.errors.items()))
    return (
        '<div class="hdo-data-warning" role="alert"><strong>Some dashboard data is unavailable.</strong>'
        '<span>{}</span></div>'
    ).format(_escape(details))


def _study_card(
    snapshot: DashboardSnapshot,
    config: Mapping[str, Any],
    calendar_events: Optional[Sequence[CalendarDayEvent]] = None,
    calendar_generation: int = 0,
    calendar_range: Optional[tuple[str, str]] = None,
    calendar_sources: Optional[Sequence[Mapping[str, Any]]] = None,
) -> str:
    visibility = config["visibility"]
    groups = []
    seen_metrics: set[str] = set()
    if visibility.get("today"):
        groups.append(
            _today_group(
                snapshot,
                seen_metrics,
                bool(config["study"].get("show_eta", True)),
            )
        )
    if visibility.get("remaining"):
        groups.append(_progress_group(snapshot, seen_metrics))
    if visibility.get("buried"):
        groups.append(_buried_group(snapshot, seen_metrics))
    if visibility.get("heatmap_metrics", True):
        groups.append(_consistency_group(snapshot, seen_metrics))
    controls = _calendar_controls(config) if visibility.get("heatmap", True) else (
        '<button type="button" class="hdo-settings" data-hdo-command="settings" '
        'aria-label="Open Home Dashboard settings" title="Dashboard settings">&#9881;</button>'
    )
    stats = (
        '<div class="hdo-stats-divider" role="separator"></div>'
        '<div class="hdo-stat-groups">{}</div>'.format("".join(groups))
        if groups
        else ""
    )
    body = (
        _calendar(
            snapshot,
            config,
            stats,
            calendar_events,
            calendar_generation,
            calendar_range,
            calendar_sources,
        )
        if visibility.get("heatmap", True)
        else stats
    )
    return (
        '<section class="hdo-card hdo-study-card" aria-labelledby="hdo-study-title">'
        '<header class="hdo-card-header"><div><p class="hdo-eyebrow">Study calendar</p>'
        '<h2 id="hdo-study-title">Your study at a glance</h2></div>{}</header>'
        '{}{}'
        '</section>'
    ).format(controls, _errors(snapshot), body)


def _bible(snapshot: DashboardSnapshot, config: Mapping[str, Any]) -> str:
    bible = config["bible"]
    color_style = "" if bible.get("theme_aware_color", True) else "color:{};".format(
        _escape(bible.get("font_color", "#1E90FF"))
    )
    reference = (
        '<div class="hdo-verse-reference">{}</div>'.format(snapshot.verse.reference_html)
        if snapshot.verse.reference_html
        else ""
    )
    return (
        '<section class="hdo-card hdo-bible-card" aria-labelledby="hdo-bible-title">'
        '<h2 id="hdo-bible-title">Bible verse</h2>'
        '<blockquote class="hdo-verse" style="{}font-family:{};font-size:{}">'
        '<div class="hdo-verse-body">{}</div>{}</blockquote></section>'
    ).format(
        color_style,
        _escape(bible.get("font_family", "Georgia, serif")),
        _escape(bible.get("font_size", "28px")),
        snapshot.verse.body_html,
        reference,
    )


def render_dashboard(
    snapshot: DashboardSnapshot,
    config: Mapping[str, Any],
    anki_dark: bool = False,
    preview: bool = False,
    calendar_events: Optional[Sequence[CalendarDayEvent]] = None,
    calendar_generation: int = 0,
    calendar_range: Optional[tuple[str, str]] = None,
    calendar_sources: Optional[Sequence[Mapping[str, Any]]] = None,
) -> str:
    visibility = config["visibility"]
    primary_visible = any(
        visibility.get(key, True)
        for key in ("today", "remaining", "buried", "heatmap", "heatmap_metrics")
    ) or bool(snapshot.errors)
    cards = []
    if primary_visible:
        cards.append(
            _study_card(
                snapshot,
                config,
                calendar_events,
                calendar_generation,
                calendar_range,
                calendar_sources,
            )
        )
    if visibility.get("bible"):
        cards.append(_bible(snapshot, config))
    return (
        '<div id="hdo-dashboard" class="hdo-dashboard{}" data-hdo-preview="{}" data-hdo-high-contrast="{}" style="{}">'
        '<main class="hdo-stack">{}</main></div>'
    ).format(
        " hdo-dashboard--preview" if preview else "",
        "true" if preview else "false",
        "true" if config["appearance"].get("preset") == "High Contrast" else "false",
        _style(config, anki_dark),
        "".join(cards),
    )


def render_loading(config: Mapping[str, Any], anki_dark: bool = False) -> str:
    return (
        '<div id="hdo-dashboard" class="hdo-dashboard hdo-dashboard--loading" style="{}">'
        '<div class="hdo-loading-card" role="status"><span class="hdo-spinner" aria-hidden="true"></span>'
        '<span>Loading your study dashboard…</span></div></div>'
    ).format(_style(config, anki_dark))


def render_activation_required(
    enabled_ids: Sequence[str], config: Mapping[str, Any], anki_dark: bool = False
) -> str:
    names = [LEGACY_NAMES.get(value, value) for value in enabled_ids]
    return (
        '<div id="hdo-dashboard" class="hdo-dashboard" style="{}">'
        '<section class="hdo-card hdo-activation" role="status"><p class="hdo-eyebrow">Home Dashboard - Overhaul</p>'
        '<h1>Ready to replace duplicate home-screen add-ons</h1>'
        '<p>The unified dashboard is paused while these legacy add-ons are enabled: <strong>{}</strong>.</p>'
        '<p>Open settings to review the migrated layout, then disable the legacy add-ons and restart Anki.</p>'
        '<button type="button" class="hdo-primary-button" data-hdo-command="settings">Open dashboard settings</button>'
        '</section></div>'
    ).format(_style(config, anki_dark), _escape(", ".join(names)))


def sample_snapshot() -> DashboardSnapshot:
    today = date.today()
    activity = []
    for offset in range(-364, 91):
        completed = 0 if offset > 0 or offset % 5 == 0 else ((offset * offset) % 43) + 4
        due = 0 if offset < 0 else ((offset * 17) % 29) + 3
        new_cards_studied = 0 if offset > 0 or completed == 0 else (abs(offset * 3) % 8) + 1
        activity.append(
            DailyActivity(
                (today + timedelta(days=offset)).isoformat(),
                completed,
                due,
                new_cards_studied,
            )
        )
    return DashboardSnapshot(
        today=TodayStats(229, 17, 3684.6, 16.1, "seconds_per_card"),
        queue=QueueStats(8, 10, 124, 142, 2400),
        buried=BuriedStats(3, 2, 7),
        events=[EventItem("preview", "Pediatric NBME", (today + timedelta(days=16)).isoformat(), 16)],
        activity=activity,
        long_term=LongTermStats(228, 62, 751, 751),
        verse=VerseContent(
            "But people are counted as righteous, not because of their work, but because of their faith in God who forgives sinners.",
            "Romans 4:5 (NLT)",
        ),
        generated_at=datetime_now_iso(),
        scheduling_date=today.isoformat(),
        day_cutoff_iso="",
    )


def datetime_now_iso() -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat(timespec="seconds")
