"""One-pass collection analytics with explicitly defined metric semantics."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
import math
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set, Tuple

from .models import (
    BuriedStats,
    DailyActivity,
    DashboardSnapshot,
    EventItem,
    LongTermStats,
    QueueStats,
    TodayStats,
    VerseContent,
)


REVLOG_MANUAL_RESCHEDULE = 4


def scheduling_today(day_cutoff: int) -> date:
    return datetime.fromtimestamp(max(0, int(day_cutoff) - 1)).astimezone().date()


def pace_lower_bound(day_cutoff: int, days: int) -> int:
    """Return a wall-clock scheduling cutoff that remains correct across DST."""
    local_cutoff = datetime.fromtimestamp(int(day_cutoff))
    local_start = local_cutoff - timedelta(days=max(1, int(days)))
    return int(local_start.timestamp())


def browser_search_for_day(selected: date, today: date) -> str:
    offset = (selected - today).days
    if offset < 0:
        return "prop:rated={}".format(offset)
    if offset > 0:
        return "prop:due={}".format(offset)
    return "(prop:rated=0 or prop:due=0)"


def history_start_date(config: Mapping[str, Any], today: date, visible: bool) -> date | None:
    heatmap = config["heatmap"]
    candidates: List[date] = []
    ignore_before = heatmap.get("ignore_before")
    if isinstance(ignore_before, str) and ignore_before:
        try:
            candidates.append(date.fromisoformat(ignore_before))
        except ValueError:
            pass
    if visible and int(heatmap.get("history_days", 0)) > 0:
        candidates.append(today - timedelta(days=int(heatmap["history_days"]) - 1))
    return max(candidates) if candidates else None


def calculate_long_term(rows: Iterable[Tuple[str, int]], today: date) -> LongTermStats:
    counts: Dict[date, int] = {}
    for iso_date, raw_count in rows:
        try:
            parsed = date.fromisoformat(iso_date)
        except (TypeError, ValueError):
            continue
        count = max(0, int(raw_count or 0))
        if count:
            counts[parsed] = counts.get(parsed, 0) + count
    if not counts:
        return LongTermStats()
    active_dates = sorted(counts)
    longest = 1
    run = 1
    for previous, current in zip(active_dates, active_dates[1:]):
        if current == previous + timedelta(days=1):
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    latest = active_dates[-1]
    current_streak = 0
    if latest in {today, today - timedelta(days=1)}:
        current_streak = 1
        cursor = latest
        while cursor - timedelta(days=1) in counts:
            current_streak += 1
            cursor -= timedelta(days=1)
    span = max(1, (today - active_dates[0]).days + 1)
    return LongTermStats(
        average_reviews_per_active_day=round(sum(counts.values()) / len(counts)),
        active_days_percent=round(100 * len(counts) / span),
        longest_streak=longest,
        current_streak=current_streak,
    )


def _safe_first(db: Any, sql: str, *args: object) -> Tuple[Any, ...]:
    row = db.first(sql, *args)
    return tuple(row or ())


def _safe_all(db: Any, sql: str, *args: object) -> List[Tuple[Any, ...]]:
    return [tuple(row) for row in (db.all(sql, *args) or [])]


def _rollover_seconds(day_cutoff: int) -> int:
    cutoff = datetime.fromtimestamp(int(day_cutoff)).astimezone()
    return cutoff.hour * 3600 + cutoff.minute * 60 + cutoff.second


def _excluded_deck_ids(col: Any, configured: Sequence[int]) -> Set[int]:
    result = {int(deck_id) for deck_id in configured if int(deck_id) > 0}
    children = getattr(getattr(col, "decks", None), "children", None)
    if not callable(children):
        return result
    for parent in list(result):
        try:
            descendants = children(parent)
        except Exception:
            continue
        for child in descendants or []:
            candidate = child[1] if isinstance(child, (tuple, list)) and len(child) > 1 else getattr(child, "id", 0)
            try:
                result.add(int(candidate))
            except (TypeError, ValueError, OverflowError):
                pass
    return result


def _new_card_condition(alias: str, include_rescheduled: bool) -> str:
    condition = "{0}.type IN (0, 3) AND {0}.lastIvl = 0".format(alias)
    if not include_rescheduled:
        condition += (
            " AND NOT EXISTS (SELECT 1 FROM revlog prior "
            "WHERE prior.cid = {alias}.cid AND prior.id < {alias}.id "
            "AND prior.ease > 0 AND prior.type != 4)"
        ).format(alias=alias)
    return condition


def _history_query(
    col: Any,
    config: Mapping[str, Any],
    today: date,
    visible: bool,
) -> List[Tuple[str, int, int]]:
    heatmap = config["heatmap"]
    excluded = _excluded_deck_ids(col, heatmap.get("excluded_deck_ids", []))
    join_cards = bool(excluded or heatmap.get("exclude_deleted_cards"))
    conditions: List[str] = []
    args: List[object] = []
    if heatmap.get("exclude_manual_reschedules", True):
        conditions.extend(["r.ease > 0", "r.type != ?"])
        args.append(REVLOG_MANUAL_RESCHEDULE)
    start = history_start_date(config, today, visible)
    if start:
        start_dt = datetime.combine(start, datetime.min.time()).astimezone()
        conditions.append("r.id >= ?")
        args.append(int(start_dt.timestamp() * 1000))
    if excluded:
        placeholders = ",".join("?" for _ in excluded)
        conditions.append("c.did NOT IN ({})".format(placeholders))
        args.extend(sorted(excluded))
    rollover = _rollover_seconds(int(col.sched.day_cutoff))
    day_expr = "date(r.id / 1000, 'unixepoch', 'localtime', '-{} seconds')".format(rollover)
    new_card_condition = _new_card_condition(
        "r",
        bool(config["new_cards"].get("include_rescheduled", True)),
    )
    sql = (
        "SELECT {day}, count(*), "
        "count(DISTINCT CASE WHEN {new_cards} THEN r.cid END) "
        "FROM revlog r {join} {where} GROUP BY {day} ORDER BY {day}"
    ).format(
        day=day_expr,
        new_cards=new_card_condition,
        join="JOIN cards c ON c.id = r.cid" if join_cards else "",
        where="WHERE " + " AND ".join(conditions) if conditions else "",
    )
    return [
        (str(day), int(count or 0), int(new_cards or 0))
        for day, count, new_cards in _safe_all(col.db, sql, *args)
        if day
    ]


def _forecast_query(col: Any, config: Mapping[str, Any], today: date) -> Dict[str, int]:
    heatmap = config["heatmap"]
    if not heatmap.get("show_due_forecast", True) or int(heatmap.get("forecast_days", 0)) <= 0:
        return {}
    scheduler_today = int(getattr(col.sched, "today", 0))
    last_due = scheduler_today + int(heatmap["forecast_days"]) - 1
    excluded = _excluded_deck_ids(col, heatmap.get("excluded_deck_ids", []))
    conditions = ["queue IN (2, 3)", "due <= ?"]
    args: List[object] = [last_due]
    if excluded:
        placeholders = ",".join("?" for _ in excluded)
        conditions.append("did NOT IN ({})".format(placeholders))
        args.extend(sorted(excluded))
    rows = _safe_all(
        col.db,
        "SELECT due, count(*) FROM cards WHERE {} GROUP BY due ORDER BY due".format(" AND ".join(conditions)),
        *args,
    )
    output: Dict[str, int] = {}
    for raw_due, raw_count in rows:
        try:
            due = max(scheduler_today, int(raw_due))
            offset = due - scheduler_today
        except (TypeError, ValueError, OverflowError):
            continue
        if offset >= int(heatmap["forecast_days"]):
            continue
        day = (today + timedelta(days=offset)).isoformat()
        output[day] = output.get(day, 0) + int(raw_count or 0)
    return output


def _pace(col: Any, days: int) -> Tuple[int, float, float | None]:
    cutoff = int(col.sched.day_cutoff)
    lower = pace_lower_bound(cutoff, days) * 1000
    row = _safe_first(
        col.db,
        "SELECT count(*), coalesce(sum(time), 0) FROM revlog WHERE id >= ? AND ease > 0 AND type != ?",
        lower,
        REVLOG_MANUAL_RESCHEDULE,
    )
    answers = int(row[0] or 0) if row else 0
    seconds = float(row[1] or 0) / 1000.0 if len(row) > 1 else 0.0
    cards_per_minute = answers * 60.0 / seconds if answers and seconds > 0 else None
    return answers, seconds, cards_per_minute


def _lifetime_paces(col: Any, include_rescheduled: bool) -> Tuple[float | None, float | None]:
    valid = "r.ease > 0 AND r.type != ?"
    new_condition = _new_card_condition("r", include_rescheduled)
    row = _safe_first(
        col.db,
        "SELECT count(*), coalesce(sum(time), 0), "
        "sum(CASE WHEN {new} THEN 1 ELSE 0 END), "
        "coalesce(sum(CASE WHEN {new} THEN time ELSE 0 END), 0) "
        "FROM revlog r WHERE {valid}".format(new=new_condition, valid=valid),
        REVLOG_MANUAL_RESCHEDULE,
    )
    answers = int(row[0] or 0) if row else 0
    seconds = float(row[1] or 0) / 1000.0 if len(row) > 1 else 0.0
    new_answers = int(row[2] or 0) if len(row) > 2 else 0
    new_seconds = float(row[3] or 0) / 1000.0 if len(row) > 3 else 0.0
    overall_seconds_per_card = seconds / answers if answers and seconds > 0 else None
    new_seconds_per_card = new_seconds / new_answers if new_answers and new_seconds > 0 else None
    return overall_seconds_per_card, new_seconds_per_card


def _today_new_cards_studied(col: Any, include_rescheduled: bool) -> int:
    cutoff = int(col.sched.day_cutoff)
    lower = pace_lower_bound(cutoff, 1) * 1000
    condition = _new_card_condition("r", include_rescheduled)
    row = _safe_first(
        col.db,
        "SELECT count(DISTINCT CASE WHEN {new} THEN r.cid END) "
        "FROM revlog r WHERE r.id >= ? AND r.ease > 0 AND r.type != ?".format(new=condition),
        lower,
        REVLOG_MANUAL_RESCHEDULE,
    )
    return max(0, int(row[0] or 0)) if row else 0


def _today(col: Any, config: Mapping[str, Any]) -> Tuple[TodayStats, float | None, float | None]:
    study = config["study"]
    today_answers, today_seconds, _ = _pace(col, 1)
    include_rescheduled = bool(config["new_cards"].get("include_rescheduled", True))
    today_new_cards = _today_new_cards_studied(col, include_rescheduled)
    lifetime_pace, new_pace = _lifetime_paces(
        col,
        include_rescheduled,
    )
    today_pace = today_seconds / today_answers if today_answers and today_seconds > 0 else None
    estimate_pace = today_pace if today_answers >= 10 and today_pace else lifetime_pace
    if study.get("pace_unit") == "cards_per_minute":
        pace = today_answers * 60.0 / today_seconds if today_answers and today_seconds > 0 else None
    else:
        pace = today_pace
    return (
        TodayStats(today_answers, today_new_cards, today_seconds, pace, str(study.get("pace_unit"))),
        estimate_pace,
        new_pace,
    )


def _queue(
    col: Any,
    estimate_pace: float | None,
    new_pace: float | None,
) -> QueueStats:
    root = col.sched.deck_due_tree()
    new = max(0, int(getattr(root, "new_count", 0) or 0))
    learning = max(0, int(getattr(root, "learn_count", 0) or 0))
    review = max(0, int(getattr(root, "review_count", 0) or 0))
    total = new + learning + review
    estimate: int | None = None
    if total == 0:
        estimate = 0
    elif estimate_pace and estimate_pace > 0:
        effective_new_pace = new_pace if new_pace and new_pace > 0 else estimate_pace
        raw_seconds = new * effective_new_pace + (learning + review) * estimate_pace
        estimate = max(60, math.ceil(raw_seconds / 60.0) * 60)
    return QueueStats(new, learning, review, total, estimate)


def _buried(col: Any) -> BuriedStats:
    row = _safe_first(
        col.db,
        "SELECT "
        "coalesce(sum(CASE WHEN type = 0 THEN 1 ELSE 0 END), 0), "
        "coalesce(sum(CASE WHEN type IN (1, 3) THEN 1 ELSE 0 END), 0), "
        "coalesce(sum(CASE WHEN type = 2 THEN 1 ELSE 0 END), 0) "
        "FROM cards WHERE queue IN (-2, -3)",
    )
    return BuriedStats(
        max(0, int(row[0] or 0)) if row else 0,
        max(0, int(row[1] or 0)) if len(row) > 1 else 0,
        max(0, int(row[2] or 0)) if len(row) > 2 else 0,
    )


def _events(config: Mapping[str, Any], today: date) -> List[EventItem]:
    items: List[EventItem] = []
    for item in config["events"].get("items", []):
        if item.get("archived"):
            continue
        try:
            event_date = date.fromisoformat(str(item["date"]))
        except (KeyError, ValueError):
            continue
        items.append(EventItem(str(item["id"]), str(item["name"]), event_date.isoformat(), (event_date - today).days))
    reverse = config["events"].get("sort") == "descending"
    return sorted(items, key=lambda item: (item.date, item.name.casefold()), reverse=reverse)


def collect_snapshot(col: Any, config: Mapping[str, Any], verse: VerseContent) -> DashboardSnapshot:
    cutoff = int(col.sched.day_cutoff)
    today_date = scheduling_today(cutoff)
    calendar_today = date.today()
    errors: Dict[str, str] = {}
    try:
        today_stats, estimate_pace, new_pace = _today(col, config)
    except Exception as exc:
        today_stats = TodayStats(pace_unit=str(config["study"].get("pace_unit")))
        estimate_pace = new_pace = None
        errors["today"] = str(exc)
    try:
        queue = _queue(col, estimate_pace, new_pace)
    except Exception as exc:
        queue = QueueStats()
        errors["queue"] = str(exc)
    try:
        buried = _buried(col)
    except Exception as exc:
        buried = BuriedStats()
        errors["buried"] = str(exc)
    try:
        history_rows = _history_query(col, config, today_date, False)
        metric_history = [(day, count) for day, count, _new_cards in history_rows]
        visible_start = history_start_date(config, today_date, True)
        visible_history = [
            (day, count, new_cards_studied)
            for day, count, new_cards_studied in history_rows
            if visible_start is None or day >= visible_start.isoformat()
        ]
    except Exception as exc:
        visible_history, metric_history = [], []
        errors["heatmap"] = str(exc)
    try:
        forecast = _forecast_query(col, config, today_date)
    except Exception as exc:
        forecast = {}
        errors["forecast"] = str(exc)
    activity: Dict[str, DailyActivity] = {
        day: DailyActivity(day, count, 0, new_cards_studied)
        for day, count, new_cards_studied in visible_history
    }
    for day, due in forecast.items():
        previous = activity.get(day, DailyActivity(day))
        activity[day] = replace(previous, reviews_due=due)
    return DashboardSnapshot(
        today=today_stats,
        queue=queue,
        buried=buried,
        # Events follow the user's civil calendar.  Anki's scheduling day can
        # roll over after midnight, which is correct for reviews but would make
        # a calendar event dated today appear as already past.
        events=_events(config, calendar_today),
        activity=[activity[key] for key in sorted(activity)],
        long_term=calculate_long_term(metric_history, today_date),
        verse=verse,
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        scheduling_date=today_date.isoformat(),
        day_cutoff_iso=datetime.fromtimestamp(cutoff).astimezone().isoformat(timespec="minutes"),
        errors=errors,
    )
