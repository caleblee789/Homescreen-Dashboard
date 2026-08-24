"""Shared production renderer for the dashboard and staged Settings preview."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timedelta
from enum import Enum
import html
import json
import re
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
from .themes import DEFAULT_HEATMAP_PRESETS, resolve_theme, rgba_color
from .ui_primitives import (
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


def _duration_compact(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if 0 < seconds < 60:
        return "{}s".format(round(seconds))
    minutes = max(0, round(seconds / 60.0))
    if minutes < 60:
        return "{}m".format(minutes)
    hours, remainder = divmod(minutes, 60)
    return "{}h {}m".format(hours, remainder) if remainder else "{}h".format(hours)


def _clock_time(value: datetime) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _last_updated_label(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return _clock_time(parsed.astimezone())


UNAVAILABLE_TEXT = "—"
N_A_TEXT = "N/A"


class _ProgressState(str, Enum):
    NO_CARDS_SCHEDULED = "no_cards_scheduled"
    ALL_CLEAR = "all_clear"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class _ProgressPresentation:
    state: _ProgressState
    fill_percent: int | None
    label: str


def _eta(
    duration_seconds: int | None,
    original_workload: int | None,
    now: datetime | None = None,
) -> str:
    """Format ETA without confusing an empty workload with completed work."""

    if duration_seconds is None or original_workload is None:
        return UNAVAILABLE_TEXT
    if duration_seconds <= 0:
        return "Done" if original_workload > 0 else UNAVAILABLE_TEXT
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


def _resolved_theme(config: Mapping[str, Any], anki_dark: bool) -> Mapping[str, str]:
    appearance = config["appearance"]
    theme_name = str(appearance.get("preset", "Sapphire Glass"))
    preset_map = config.get("heatmap", {}).get("presets_by_theme", {})
    heatmap_name = (
        preset_map.get(theme_name)
        if isinstance(preset_map, Mapping)
        else DEFAULT_HEATMAP_PRESETS.get(theme_name)
    )
    return resolve_theme(
        theme_name,
        appearance.get("mode"),
        anki_dark,
        heatmap_name,
    )


def _style(config: Mapping[str, Any], anki_dark: bool) -> str:
    appearance = config["appearance"]
    theme = _resolved_theme(config, anki_dark)

    glass = theme["theme_name"] == "Sapphire Glass"
    safe_opacity = max(94, min(100, int(appearance.get("opacity", 96)))) / 100
    blur = max(0, min(16, int(appearance.get("blur", 12)))) if glass else 0
    if glass:
        if "ui_card_gradient_start" in theme:
            card_background = "linear-gradient(180deg, {} 0%, {} 100%)".format(
                rgba_color(theme["ui_card_gradient_start"], safe_opacity),
                rgba_color(theme["ui_card_gradient_end"], safe_opacity),
            )
        else:
            card_background = rgba_color(theme["ui_surface_1"], safe_opacity)
    else:
        card_background = theme["ui_surface_1"]
    declarations = {
        "--ui-card-background": card_background,
        "--hdo-card-backdrop-filter": "blur({}px) saturate(1.08)".format(blur) if blur else "none",
        "--hdo-card-surface-opacity": "{:.2f}".format(safe_opacity if glass else 1.0),
        "--hdo-target-size": "{}px".format(INTERACTION_TARGET_MIN_PX),
        "--hdo-control-visual": "{}px".format(VISUAL_CHROME_PX),
        "--hdo-focus-ring": "{}px".format(FOCUS_RING_PX),
        "--hdo-focus-offset": "{}px".format(FOCUS_RING_OFFSET_PX),
        "--hdo-scale": str(int(appearance.get("text_scale", 100)) / 100),
    }
    declarations.update({
        "--{}".format(key.replace("_", "-")): value
        for key, value in theme.items()
        if key not in {"theme_name", "color_mode", "heatmap_preset"}
    })
    return ";".join("{}:{}".format(key, value) for key, value in declarations.items())


def _host_surface_style(config: Mapping[str, Any], anki_dark: bool) -> str:
    """Leave Anki's wallpaper, deck list, toolbar, footer, and canvas untouched."""

    del config, anki_dark
    return ""


def _format_count(value: object) -> str:
    try:
        return format(max(0, int(value)), ",")
    except (TypeError, ValueError, OverflowError):
        return "0"


def _metric(
    label: str,
    value: object,
    metric_key: str,
    modifier: str = "",
    *,
    semantic: str = "",
    semantic_value: int | float | None = None,
    unavailable: bool = False,
    compact_value: object | None = None,
) -> str:
    classes = [modifier] if modifier else []
    if semantic and not unavailable and semantic_value is not None and semantic_value > 0:
        classes.append("hdo-value--{}".format(semantic))
    if unavailable:
        classes.append("is-unavailable")
    semantic_attr = ' data-hdo-semantic="{}"'.format(_escape(semantic)) if semantic else ""
    rendered_value = _escape(value)
    compact_attr = ""
    if compact_value is not None:
        rendered_value = (
            '<span class="hdo-value-wide">{}</span>'
            '<span class="hdo-value-compact">{}</span>'
        ).format(_escape(value), _escape(compact_value))
        compact_attr = ' data-hdo-compact="true"'
    return (
        '<div class="hdo-metric-row {}" data-hdo-primitive="{}"{}>'
        '<dt>{}</dt><dd data-hdo-metric="{}"{}>{}</dd></div>'
    ).format(
        _escape(" ".join(classes)),
        _dashboard_primitive("metric-row"),
        semantic_attr,
        _escape(label),
        _escape(metric_key),
        compact_attr,
        rendered_value,
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
    card_class = {
        "hdo-progress": "hdo-progress-card",
        "hdo-session": "hdo-session-card",
        "hdo-last-seven": "hdo-recent-card",
        "hdo-all-time": "hdo-lifetime-card",
    }.get(group_id, "")
    return (
        '<section class="hdo-statistics-card {}" data-hdo-primitive="{}" '
        'aria-labelledby="{}-title"><header class="hdo-stat-card-header">'
        '<h3 id="{}-title">{}</h3>{}</header>{}<dl>{}</dl></section>'
    ).format(
        _escape(card_class),
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


def _progress_presentation(snapshot: DashboardSnapshot) -> _ProgressPresentation:
    today_state = _facts_state(snapshot, "today")
    queue_state = _facts_state(snapshot, "queue")
    if not today_state.is_available or not queue_state.is_available:
        return _ProgressPresentation(_ProgressState.UNAVAILABLE, None, "Unavailable")
    today: TodayStats = today_state.value
    queue: QueueStats = queue_state.value
    completed = max(0, int(today.answers))
    new_remaining = max(0, int(queue.new))
    learning_remaining = max(0, int(queue.learning))
    review_remaining = max(0, int(queue.review))
    remaining = new_remaining + learning_remaining + review_remaining
    workload = completed + remaining
    if workload == 0:
        long_term_state = _facts_state(snapshot, "long_term")
        recent_state = _facts_state(snapshot, "last_seven_days")
        has_history = (
            long_term_state.is_available
            and int(long_term_state.value.lifetime_cards_studied) > 0
        ) or (
            recent_state.is_available
            and int(recent_state.value.cards_studied) > 0
        )
        if has_history:
            state = _ProgressState.ALL_CLEAR
            label = "All clear"
        else:
            state = _ProgressState.NO_CARDS_SCHEDULED
            label = "No cards scheduled"
        percent = None
    elif remaining == 0:
        state = _ProgressState.COMPLETE
        percent = 100
        label = "100% complete"
    else:
        state = _ProgressState.IN_PROGRESS
        percent = _rounded_progress_percent(completed, workload)
        label = "{}% complete".format(percent)
    return _ProgressPresentation(state, percent, label)


def _progress_group(snapshot: DashboardSnapshot) -> str:
    queue_state = _facts_state(snapshot, "queue")
    presentation = _progress_presentation(snapshot)
    has_fill = presentation.fill_percent is not None
    percent = presentation.fill_percent if has_fill else 0
    heading_meta = (
        '<span class="hdo-progress-status-chip" data-hdo-progress-chip '
        'data-hdo-progress-state="{}"{}>{}</span>'
    ).format(
        _escape(presentation.state.value),
        " hidden" if has_fill else "",
        _escape(presentation.label),
    )
    lead = (
        '<div class="hdo-progress-track" data-hdo-progress-track '
        'data-hdo-progress-state="{}" role="progressbar" aria-valuemin="0" '
        'aria-valuemax="100" aria-valuenow="{}" aria-valuetext="{}"{} '
        'style="--hdo-progress-percent:{}%">'
        '<span class="hdo-progress-fill" data-hdo-progress-fill></span>'
        '<span class="hdo-progress-label hdo-progress-label--track" data-hdo-progress-label>{}</span>'
        '<span class="hdo-progress-label hdo-progress-label--fill" '
        'data-hdo-progress-label-fill aria-hidden="true">{}</span></div>'
    ).format(
        _escape(presentation.state.value),
        percent,
        _escape(presentation.label),
        "" if has_fill else " hidden",
        percent,
        _escape(presentation.label),
        _escape(presentation.label),
    )
    if queue_state.is_available:
        queue: QueueStats = queue_state.value
        new_remaining = max(0, int(queue.new))
        learning_remaining = max(0, int(queue.learning))
        review_remaining = max(0, int(queue.review))
        remaining = new_remaining + learning_remaining + review_remaining
        rows = [
            _metric("New remaining", _format_count(new_remaining), "queue.new", semantic="new", semantic_value=new_remaining),
            _metric("Learning remaining", _format_count(learning_remaining), "queue.learning", semantic="learning", semantic_value=learning_remaining),
            _metric("Reviews remaining", _format_count(review_remaining), "queue.review", semantic="review", semantic_value=review_remaining),
            _metric("Total remaining", _format_count(remaining), "queue.total"),
        ]
    else:
        rows = [
            _metric(label, UNAVAILABLE_TEXT, key, semantic=semantic, unavailable=True)
            for label, key, semantic in (
                ("New remaining", "queue.new", "new"),
                ("Learning remaining", "queue.learning", "learning"),
                ("Reviews remaining", "queue.review", "review"),
                ("Total remaining", "queue.total", ""),
            )
        ]
    return _stats_group("Today’s Progress", "hdo-progress", rows, lead, heading_meta)


def _today_session_presentation(snapshot: DashboardSnapshot) -> dict[str, str]:
    state = _facts_state(snapshot, "today")
    buried_state = _facts_state(snapshot, "buried")
    buried_total: int | None = None
    if buried_state.is_available:
        buried: BuriedStats = buried_state.value
        buried_total = sum(max(0, int(value)) for value in (buried.new, buried.learning, buried.review))
    if not state.is_available:
        return {
            "cards_studied": UNAVAILABLE_TEXT,
            "new_cards_studied": UNAVAILABLE_TEXT,
            "cards_buried": _format_count(buried_total) if buried_total is not None else UNAVAILABLE_TEXT,
            "time_spent": UNAVAILABLE_TEXT,
            "time_spent_compact": UNAVAILABLE_TEXT,
            "pace": UNAVAILABLE_TEXT,
            "eta": UNAVAILABLE_TEXT,
        }
    stats: TodayStats = state.value
    if stats.pace_value is not None:
        pace = (
            "{:.1f} cards/min".format(stats.pace_value)
            if stats.pace_unit == "cards_per_minute"
            else "{:.1f} sec/card".format(stats.pace_value)
        )
    else:
        pace = UNAVAILABLE_TEXT
    queue_state = _facts_state(snapshot, "queue")
    if queue_state.is_available:
        queue: QueueStats = queue_state.value
        workload = max(0, int(stats.answers)) + max(0, int(queue.new)) + max(0, int(queue.learning)) + max(0, int(queue.review))
        eta = _eta(queue.estimated_duration_seconds, workload)
    else:
        eta = UNAVAILABLE_TEXT
    return {
        "cards_studied": _format_count(stats.answers),
        "new_cards_studied": _format_count(stats.new_cards_studied),
        "cards_buried": _format_count(buried_total) if buried_total is not None else UNAVAILABLE_TEXT,
        "time_spent": _duration(stats.seconds),
        "time_spent_compact": _duration_compact(stats.seconds),
        "pace": pace,
        "eta": eta,
    }


def _today_session_group(snapshot: DashboardSnapshot) -> str:
    state = _facts_state(snapshot, "today")
    buried_state = _facts_state(snapshot, "buried")
    presentation = _today_session_presentation(snapshot)
    new_count = max(0, int(state.value.new_cards_studied)) if state.is_available else None
    buried_total = None
    if buried_state.is_available:
        buried_total = sum(
            max(0, int(value))
            for value in (
                buried_state.value.new,
                buried_state.value.learning,
                buried_state.value.review,
            )
        )
    unavailable = not state.is_available
    rows = [
        _metric("Cards studied", presentation["cards_studied"], "today.answers", unavailable=unavailable),
        _metric(
            "New cards studied",
            presentation["new_cards_studied"],
            "today.new_cards_studied",
            semantic="new",
            semantic_value=new_count,
            unavailable=unavailable,
        ),
        _metric(
            "Cards buried",
            presentation["cards_buried"],
            "today.cards_buried",
            semantic="buried",
            semantic_value=buried_total,
            unavailable=not buried_state.is_available,
        ),
        _metric(
            "Time spent",
            presentation["time_spent"],
            "today.time_spent",
            unavailable=unavailable,
            compact_value=presentation["time_spent_compact"],
        ),
        _metric("Pace", presentation["pace"], "today.pace", unavailable=presentation["pace"] == UNAVAILABLE_TEXT),
        _metric("ETA", presentation["eta"], "queue.eta", "hdo-value--estimate", unavailable=presentation["eta"] == UNAVAILABLE_TEXT),
    ]
    return _stats_group("Today’s Session", "hdo-session", rows)


def _rate_text(value: RateMetric) -> str:
    return "{}%".format(value.percent) if value.status == RateStatus.AVAILABLE and value.percent is not None else N_A_TEXT


def _retention_role(value: RateMetric, target: int | None) -> str:
    if value.status != RateStatus.AVAILABLE or value.percent is None or target is None:
        return ""
    if value.percent >= target:
        return "hdo-value--success"
    if value.percent >= max(0, target - 10):
        return "hdo-value--warning"
    return "hdo-value--danger"


def _again_role(value: RateMetric, retention_target: int | None) -> str:
    if value.status != RateStatus.AVAILABLE or value.percent is None or retention_target is None:
        return ""
    target = max(0, 100 - retention_target)
    if value.percent <= target:
        return "hdo-value--success"
    if value.percent <= min(100, target + 10):
        return "hdo-value--warning"
    return "hdo-value--danger"


def _last_seven_group(snapshot: DashboardSnapshot, target: int | None) -> str:
    state = _facts_state(snapshot, "last_seven_days")
    if not state.is_available:
        return _stats_group(
            "Last 7 Days",
            "hdo-last-seven",
            [
                _metric(label, UNAVAILABLE_TEXT, key, semantic=semantic, unavailable=True)
                for label, key, semantic in (
                    ("Cards studied", "last_seven_days.cards_studied", ""),
                    ("New cards studied", "last_seven_days.new_cards_studied", "new"),
                    ("Retention", "last_seven_days.retention", ""),
                    ("Again rate", "last_seven_days.again_rate", ""),
                )
            ],
        )
    stats: LastSevenDaysStats = state.value
    rows = [
        _metric("Cards studied", _format_count(stats.cards_studied), "last_seven_days.cards_studied"),
        _metric("New cards studied", _format_count(stats.new_cards_studied), "last_seven_days.new_cards_studied", semantic="new", semantic_value=stats.new_cards_studied),
    ]
    retention = _rate_text(stats.retention)
    rows.append(_metric(
        "Retention",
        retention,
        "last_seven_days.retention",
        _retention_role(stats.retention, target),
        unavailable=retention == UNAVAILABLE_TEXT,
    ))
    again = _rate_text(stats.again_rate)
    rows.append(_metric(
        "Again rate",
        again,
        "last_seven_days.again_rate",
        _again_role(stats.again_rate, target),
        unavailable=again == UNAVAILABLE_TEXT,
    ))
    return _stats_group("Last 7 Days", "hdo-last-seven", rows)


def _all_time_group(snapshot: DashboardSnapshot, _target: int | None) -> str:
    state = _facts_state(snapshot, "long_term")
    if not state.is_available:
        return _stats_group(
            "All Time",
            "hdo-all-time",
            [
                _metric(label, UNAVAILABLE_TEXT, key, unavailable=True)
                for label, key in (
                    ("Avg cards/day", "long_term.average_reviews_per_active_day"),
                    ("Current streak", "long_term.current_streak"),
                    ("Longest streak", "long_term.longest_streak"),
                    ("Retention", "long_term.lifetime_retention"),
                    ("Cards studied", "long_term.lifetime_cards_studied"),
                )
            ],
        )
    stats: LongTermStats = state.value
    day_text = lambda count: "{} day{}".format(_format_count(count), "" if count == 1 else "s")
    rows = [
        _metric("Avg cards/day", _format_count(stats.average_reviews_per_active_day), "long_term.average_reviews_per_active_day"),
        _metric("Current streak", day_text(stats.current_streak), "long_term.current_streak"),
        _metric("Longest streak", day_text(stats.longest_streak), "long_term.longest_streak"),
    ]
    retention = _rate_text(stats.lifetime_retention)
    rows.append(_metric(
        "Retention",
        retention,
        "long_term.lifetime_retention",
        unavailable=retention == UNAVAILABLE_TEXT,
    ))
    rows.append(_metric("Cards studied", _format_count(stats.lifetime_cards_studied), "long_term.lifetime_cards_studied"))
    return _stats_group("All Time", "hdo-all-time", rows)


def _metrics(snapshot: DashboardSnapshot, config: Mapping[str, Any]) -> str:
    visibility = config["visibility"]
    target_value = config.get("study", {}).get("retention_target")
    target = int(target_value) if isinstance(target_value, (int, float)) else None
    groups: list[str] = []
    if visibility.get("remaining", True):
        groups.append(_progress_group(snapshot))
    if visibility.get("today", True):
        groups.append(_today_session_group(snapshot))
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
        normalized = max(0, min(6, int(week_start)))
        start -= timedelta(days=(start.weekday() - normalized) % 7)
        # Month uses one stable six-week body at every anchor so switching
        # months never moves the legend, event summary, or following sections.
        end = start + timedelta(days=41)
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
    last_updated_at: str = "",
    year_scroll_left: float | None = None,
) -> dict[str, Any]:
    facts = snapshot.facts
    preview_date = _selected_iso(config.get("_preview_selected_date"))
    scheduling_date = _selected_iso(facts.scheduling_date)
    calendar_date = _selected_iso(facts.calendar_date) or scheduling_date
    selected = preview_date or _selected_iso(selected_date) or scheduling_date or calendar_date
    view = str(config.get("heatmap", {}).get("calendar_view", "year"))
    week_start = int(config.get("heatmap", {}).get("week_start", 0))
    retention_target_value = config.get("study", {}).get("retention_target")
    retention_target = (
        int(retention_target_value)
        if isinstance(retention_target_value, (int, float))
        else None
    )
    range_payload = calendar_range_payload(snapshot, selected or date.today().isoformat(), view, week_start)
    progress = _progress_presentation(snapshot)
    session = _today_session_presentation(snapshot)
    session.pop("time_spent_compact", None)
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
        "last_updated_at": str(last_updated_at or ""),
        "year_scroll_left": (
            max(0.0, float(year_scroll_left))
            if isinstance(year_scroll_left, (int, float)) and not isinstance(year_scroll_left, bool)
            else None
        ),
        "due_load_reference": max(0.0, float(facts.due_load_reference)),
        "statistics": {
            "today": _value_state_payload(facts.today),
            "queue": _value_state_payload(facts.queue),
            "buried": _value_state_payload(facts.buried),
            "last_seven_days": _value_state_payload(facts.last_seven_days),
            "long_term": _value_state_payload(facts.long_term),
        },
        "presentation": {
            "progress": {
                "status": progress.state.value,
                "fill_percent": progress.fill_percent,
            },
            "today_session": session,
        },
        "retention_target": retention_target,
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
        '<button type="button" data-hdo-calendar="today" title="Go to today">Today</button>'
        '<button type="button" data-hdo-calendar="next" aria-label="Next period" title="Next period">›</button></div>'
        '<button type="button" class="hdo-settings" data-hdo-command="calendar-settings" '
        'aria-label="Calendar settings" title="Calendar settings">'
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<path d="M9.7 2.8h4.6l.6 2.2c.5.2 1 .5 1.5.9l2.2-.6 2.3 4-1.6 1.6v2.2l1.6 1.6-2.3 4-2.2-.6c-.5.4-1 .7-1.5.9l-.6 2.2H9.7L9.1 19c-.5-.2-1-.5-1.5-.9l-2.2.6-2.3-4 1.6-1.6v-2.2L3.1 9.3l2.3-4 2.2.6c.5-.4 1-.7 1.5-.9l.6-2.2Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>'
        '<circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.7"/>'
        '</svg></button>'
        '</div>'
    ).format("true" if view == "month" else "false", "true" if view == "year" else "false")


def _calendar(
    snapshot: DashboardSnapshot,
    config: Mapping[str, Any],
    selected_date: str,
    facts_revision: int,
    last_updated_at: str,
    year_scroll_left: float | None,
) -> str:
    payload = dashboard_facts_payload(
        snapshot,
        config,
        selected_date,
        facts_revision,
        last_updated_at,
        year_scroll_left,
    )
    event_legend = (
        '<div class="hdo-legend-group hdo-legend-event">'
        '<i class="hdo-legend-event-marker" aria-hidden="true"></i><span>Event</span></div>'
        if config.get("visibility", {}).get("events", True)
        else ""
    )
    due_legend = (
        '<div class="hdo-legend-group hdo-legend-due">'
        '<span class="hdo-legend-title">Due cards</span>'
        '<span class="hdo-legend-scale hdo-due-legend" aria-hidden="true">'
        '<i data-due-level="1"></i><i data-due-level="2"></i><i data-due-level="3"></i>'
        '</span></div>'
        if config.get("heatmap", {}).get("show_due_forecast", True)
        else ""
    )
    event_summary = (
        '<div class="hdo-next-event-line hdo-calendar-footer__event" data-hdo-context-event>'
        '<span class="hdo-context-event-marker" data-hdo-event-marker aria-hidden="true" hidden></span>'
        '<span class="hdo-event-summary">'
        '<button type="button" class="hdo-event-title" data-hdo-open-events hidden></button>'
        '<span class="hdo-event-meta" data-hdo-event-meta hidden></span>'
        '<span class="hdo-event-more" data-hdo-event-more hidden></span>'
        '<span class="hdo-event-empty" data-hdo-event-empty>No upcoming events</span></span></div>'
        if config.get("visibility", {}).get("events", True)
        else ""
    )
    event_edit = (
        '<button type="button" class="hdo-edit-event-button hdo-icon-button" data-hdo-edit-event '
        'aria-label="Edit event" title="Edit event" hidden>'
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<path d="m4 16.8-.8 4 4-.8L18.6 8.6l-3.2-3.2L4 16.8Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>'
        '<path d="m13.8 7 3.2 3.2M3.8 20.2h16.4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'
        '</svg></button>'
        if config.get("visibility", {}).get("events", True)
        else ""
    )
    return (
        '<section class="hdo-card hdo-dashboard-panel hdo-calendar-card" data-hdo-primitive="{}" '
        'aria-labelledby="hdo-calendar-heading">'
        '<header class="hdo-dashboard-header" data-hdo-primitive="{}"><div>'
        '<p class="hdo-eyebrow">Study Calendar</p><div class="hdo-calendar-title-line">'
        '<h2 id="hdo-calendar-heading" data-hdo-calendar-title></h2>'
        '<span class="hdo-refresh-status" data-hdo-refresh-status role="status" hidden></span></div>'
        '</div>{}</header>'
        '<div class="hdo-calendar-shell" data-hdo-calendar-view="{}" aria-busy="false">'
        '<div class="hdo-calendar-body"><div class="hdo-month-weekdays" aria-hidden="true"></div>'
        '<div class="hdo-calendar-grid-frame"><div class="hdo-year-heatmap-content">'
        '<div class="hdo-calendar-grid" role="grid" aria-label="Study calendar"></div>'
        '</div></div></div></div>'
        '<footer class="hdo-calendar-footer" '
        'data-hdo-primitive="{}">'
        '<div class="hdo-calendar-legend" aria-label="Calendar legend">'
        '<div class="hdo-legend-group hdo-legend-completion">'
        '<span class="hdo-legend-title">Completed reviews</span>'
        '<span class="hdo-legend-endpoint">Low</span>'
        '<span class="hdo-legend-scale hdo-completion-legend" aria-hidden="true">'
        '<i data-level="1"></i><i data-level="2"></i><i data-level="3"></i><i data-level="4"></i><i data-level="5"></i>'
        '</span><span class="hdo-legend-endpoint">High</span></div>{}{}</div>'
        '<div class="hdo-calendar-context hdo-calendar-context-bar{}" aria-live="polite">'
        '<div class="hdo-selected-date-line hdo-calendar-footer__date-context">'
        '<span class="hdo-date-state-chip" data-hdo-date-state>Today</span>'
        '<time data-hdo-context-date></time></div>{}'
        '<div class="hdo-context-actions hdo-calendar-footer__actions">'
        '{}'
        '<button type="button" class="hdo-context-action hdo-calendar-card-action hdo-context-action--primary" data-hdo-primary-action hidden></button>'
        '<button type="button" class="hdo-context-action" data-hdo-most-missed hidden>Most missed</button>'
        '</div></div></footer>'
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
        _dashboard_primitive("calendar-context-bar"),
        due_legend,
        event_legend,
        " hdo-calendar-context--no-event" if not event_summary else "",
        event_summary,
        event_edit,
        _safe_json(payload),
    )


def _bible(snapshot: DashboardSnapshot, config: Mapping[str, Any]) -> str:
    bible = config["bible"]
    custom_color = "" if bible.get("theme_aware_color", True) else "color:{};".format(_escape(bible.get("font_color", "")))
    raw_size = str(bible.get("font_size", "28px"))
    try:
        configured_size = int(raw_size[:-2]) if raw_size.endswith("px") else 28
    except (TypeError, ValueError):
        configured_size = 28
    plain_verse = html.unescape(re.sub(r"<[^>]+>", " ", snapshot.verse.body_html))
    character_count = len(" ".join(plain_verse.split()))
    if character_count <= 90:
        verse_class = "hdo-verse hdo-verse--short"
    elif character_count <= 180:
        verse_class = "hdo-verse hdo-verse--medium"
    else:
        verse_class = "hdo-verse hdo-verse--long"
    reference = (
        '<footer class="hdo-verse-reference">{}</footer>'.format(snapshot.verse.reference_html)
        if snapshot.verse.reference_html
        else ""
    )
    return (
        '<section class="hdo-card hdo-dashboard-panel hdo-bible-card" data-hdo-primitive="{}" '
        'aria-labelledby="hdo-bible-title"><p class="hdo-eyebrow">Bible Verse</p>'
        '<h2 id="hdo-bible-title" class="hdo-visually-hidden">Bible Verse</h2>'
        '<blockquote class="{}" '
        'style="{}--hdo-verse-font:{};--hdo-verse-size:{:.2f}px">'
        '<div class="hdo-verse-body">{}</div></blockquote>{}</section>'
    ).format(
        _dashboard_primitive("bible-verse-card"),
        verse_class,
        custom_color,
        _escape(bible.get("font_family", "Georgia, serif")),
        configured_size,
        snapshot.verse.body_html,
        reference,
    )


def _data_warning(snapshot: DashboardSnapshot, config: Mapping[str, Any]) -> str:
    states = []
    visibility = config.get("visibility", {})
    if visibility.get("today", True):
        states.extend((snapshot.facts.today, snapshot.facts.buried))
    if visibility.get("remaining", True):
        states.append(snapshot.facts.queue)
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
    refresh_error: bool = False,
    last_updated_at: str = "",
    year_scroll_left: float | None = None,
) -> str:
    render_config = dict(config)
    if preview:
        render_config["_preview_context"] = True
    resolved_theme = _resolved_theme(render_config, anki_dark)
    visibility = render_config["visibility"]
    has_calendar = bool(visibility.get("heatmap", True))
    calendar = (
        _calendar(
            snapshot,
            render_config,
            selected_date,
            facts_revision,
            last_updated_at,
            year_scroll_left,
        )
        if has_calendar
        else ""
    )
    metrics = _metrics(snapshot, render_config)
    has_metrics = bool(metrics)
    bible = _bible(snapshot, render_config) if visibility.get("bible", True) else ""
    has_insights = bool(metrics or bible)
    sections: list[str] = []
    if calendar or has_insights:
        rail = (
            '<aside class="hdo-insight-rail" aria-label="Study insights" '
            'data-hdo-has-metrics="{}" data-hdo-has-bible="{}">{}{}</aside>'.format(
                "true" if has_metrics else "false",
                "true" if bible else "false",
                metrics,
                bible,
            )
            if has_insights
            else ""
        )
        sections.append(
            '<div class="hdo-dashboard-layout">{}{}</div>'.format(calendar, rail)
        )
    else:
        sections.append(
            '<section class="hdo-card hdo-recovery-card" data-hdo-primitive="{}" role="status">'
            '<p class="hdo-eyebrow">Home Screen Dashboard</p><h2>Dashboard sections are hidden</h2>'
            '<p>Turn on at least one Home screen section to show study information here.</p>'
            '<button type="button" data-hdo-command="settings">Open settings</button></section>'.format(
                _dashboard_primitive("recovery-card")
            )
        )
    payload = dashboard_facts_payload(
        snapshot,
        render_config,
        selected_date,
        facts_revision,
        last_updated_at,
        year_scroll_left,
    )
    if not visibility.get("heatmap", True):
        sections.append('<script type="application/json" class="hdo-dashboard-data">{}</script>'.format(_safe_json(payload)))
    last_updated_label = _last_updated_label(last_updated_at)
    refresh_copy = (
        "Refresh failed. Showing data last updated at {}.".format(last_updated_label)
        if last_updated_label
        else "Refresh failed. Showing previously loaded data."
    )
    return _host_surface_style(render_config, anki_dark) + (
        '<div id="hdo-dashboard" class="hdo-dashboard dashboard-host dashboard-scroll-surface{}" data-hdo-preview="{}" '
        'data-hdo-theme="{}" data-hdo-color-mode="{}" '
        'data-hdo-runtime-stack="{}" data-hdo-stack-position="{}" '
        'data-hdo-content-mode="{}" data-hdo-high-contrast="{}" '
        'data-hdo-calendar-view="{}" data-hdo-has-calendar="{}" data-hdo-has-metrics="{}" '
        'data-hdo-has-insights="{}" data-hdo-has-bible="{}" '
        'data-hdo-enlarged-text="{}" data-hdo-last-updated-at="{}" '
        'aria-busy="false" style="{}">'
        '<main class="hdo-stack">{}{}{}</main></div>'
    ).format(
        " hdo-dashboard--preview" if preview else "",
        "true" if preview else "false",
        _escape(resolved_theme["theme_name"]),
        _escape(resolved_theme["color_mode"]),
        "false" if preview else "true",
        _escape(render_config.get("home_screen", {}).get("position", "top")),
        CONTENT_MODE_INTERMEDIATE,
        "true" if render_config["appearance"].get("preset") == "High Contrast" else "false",
        _escape(render_config.get("heatmap", {}).get("calendar_view", "year")),
        "true" if has_calendar else "false",
        "true" if has_metrics else "false",
        "true" if has_insights else "false",
        "true" if bible else "false",
        "true" if int(render_config.get("appearance", {}).get("text_scale", 100)) >= 125 else "false",
        _escape(last_updated_at),
        _style(render_config, anki_dark),
        (
            '<div class="hdo-data-warning hdo-refresh-warning" role="alert">'
            '<span>{}</span>'
            '<button type="button" data-hdo-command="retry">Retry</button></div>'
            .format(_escape(refresh_copy)) if refresh_error else ""
        ),
        _data_warning(snapshot, render_config),
        "".join(sections),
    )


def _runtime_placeholder(
    config: Mapping[str, Any],
    anki_dark: bool,
    *,
    failed: bool,
) -> str:
    view = str(config.get("heatmap", {}).get("calendar_view", "year"))
    week_start = int(config.get("heatmap", {}).get("week_start", 0))
    loading_cell_count = (
        53
        if view == "year"
        else len(_calendar_payload_dates(date.today().isoformat(), "month", week_start))
    )
    bible_skeleton = (
        '<section class="hdo-card hdo-loading-region hdo-loading-region--bible">'
        '<span></span><span></span><span></span></section>'
        if config.get("visibility", {}).get("bible", True)
        else ""
    )
    metric_cards = "".join(
        '<section class="hdo-statistics-card hdo-loading-metric-card">{}</section>'.format(
            "".join("<span></span>" for _ in range(row_count))
        )
        for row_count in (6, 7, 5, 6)
    )
    resolved_theme = _resolved_theme(config, anki_dark)
    return _host_surface_style(config, anki_dark) + (
        '<div id="hdo-dashboard" class="hdo-dashboard dashboard-host dashboard-scroll-surface {}" '
        'data-hdo-theme="{}" data-hdo-color-mode="{}" '
        'data-hdo-runtime-stack="true" data-hdo-stack-position="{}" '
        'data-hdo-content-mode="{}" data-hdo-calendar-view="{}" data-hdo-load-state="{}" '
        'aria-busy="{}" style="{}"><main class="hdo-stack">'
        '<div class="hdo-loading-layout" data-hdo-loading-skeleton aria-hidden="true"{}>'
        '<section class="hdo-card hdo-loading-card hdo-loading-region--calendar" '
        'data-hdo-primitive="{}" data-hdo-calendar-view="{}" aria-busy="{}">'
        '<header><p class="hdo-eyebrow">Study Calendar</p>'
        '<h2>Loading your study dashboard…</h2>'
        '<p class="hdo-loading-message" data-hdo-loading-message role="status" aria-live="polite"></p></header>'
        '<div class="hdo-loading-calendar-grid">{}</div><div class="hdo-loading-calendar-footer"></div></section>'
        '<aside class="hdo-loading-rail"><div class="hdo-loading-region--metrics">{}</div>{}</aside></div>'
        '<section class="hdo-card hdo-loading-failure" data-hdo-loading-failure{} role="alert">'
        '<p class="hdo-eyebrow">Home Screen Dashboard</p><h2>Dashboard could not load</h2>'
        '<p>The dashboard data could not be loaded. Retry or open diagnostics for details.</p>'
        '<div class="hdo-loading-actions">'
        '<button type="button" class="hdo-context-action hdo-context-action--primary" '
        'data-hdo-command="retry">Retry</button>'
        '<button type="button" data-hdo-command="diagnostics">Open diagnostics</button>'
        '</div></section>'
        '</main></div>'
    ).format(
        "hdo-dashboard--failure" if failed else "hdo-dashboard--loading",
        _escape(resolved_theme["theme_name"]),
        _escape(resolved_theme["color_mode"]),
        _escape(config.get("home_screen", {}).get("position", "top")),
        CONTENT_MODE_INTERMEDIATE,
        _escape(view),
        "failure" if failed else "initial",
        "false" if failed else "true",
        _style(config, anki_dark),
        " hidden" if failed else "",
        _dashboard_primitive("loading-card"),
        _escape(view),
        "false" if failed else "true",
        "".join("<span></span>" for _ in range(loading_cell_count)),
        metric_cards,
        bible_skeleton,
        "" if failed else " hidden",
    )


def render_loading(config: Mapping[str, Any], anki_dark: bool = False) -> str:
    return _runtime_placeholder(config, anki_dark, failed=False)


def render_failure(config: Mapping[str, Any], anki_dark: bool = False) -> str:
    return _runtime_placeholder(config, anki_dark, failed=True)


def render_activation_required(
    enabled_ids: Sequence[str],
    config: Mapping[str, Any],
    anki_dark: bool = False,
) -> str:
    names = [LEGACY_NAMES.get(value, value) for value in enabled_ids]
    resolved_theme = _resolved_theme(config, anki_dark)
    return _host_surface_style(config, anki_dark) + (
        '<div id="hdo-dashboard" class="hdo-dashboard dashboard-host dashboard-scroll-surface" '
        'data-hdo-theme="{}" data-hdo-color-mode="{}" data-hdo-runtime-stack="true" '
        'data-hdo-stack-position="{}" data-hdo-content-mode="{}" style="{}">'
        '<main class="hdo-stack"><section class="hdo-card hdo-recovery-card" '
        'data-hdo-primitive="{}" role="status"><p class="hdo-eyebrow">Home Screen Dashboard</p>'
        '<h1>Ready to replace duplicate home-screen add-ons</h1>'
        '<p>The unified dashboard is paused while these legacy add-ons are enabled: <strong>{}</strong>.</p>'
        '<button type="button" data-hdo-command="settings">Open settings</button>'
        '</section></main></div>'
    ).format(
        _escape(resolved_theme["theme_name"]),
        _escape(resolved_theme["color_mode"]),
        _escape(config.get("home_screen", {}).get("position", "top")),
        CONTENT_MODE_INTERMEDIATE,
        _style(config, anki_dark),
        _dashboard_primitive("recovery-card"),
        _escape(", ".join(names)),
    )
