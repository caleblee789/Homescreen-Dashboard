"""One-pass collection analytics with explicitly defined metric semantics."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .models import (
    AvailabilityReason,
    BrowseTarget,
    BrowseTargetKind,
    BuriedStats,
    DashboardFacts,
    DashboardSnapshot,
    DateCoverage,
    DayDomainState,
    DayFacts,
    DayRelation,
    EventItem,
    FilterScope,
    LastSevenDaysStats,
    LongTermStats,
    QueueStats,
    RateMetric,
    TodayStats,
    ValueState,
    ValueStatus,
    VerseContent,
)


REVLOG_MANUAL_RESCHEDULE = 4


def scheduling_today(day_cutoff: int) -> date:
    """Return the civil label of the active Anki scheduling day.

    ``day_cutoff`` is the end of the active scheduler day.  Its local calendar
    date therefore labels the next day, regardless of the configured rollover
    clock time.
    """
    cutoff_date = datetime.fromtimestamp(max(0, int(day_cutoff))).astimezone().date()
    return cutoff_date - timedelta(days=1)


def pace_lower_bound(day_cutoff: int, days: int) -> int:
    """Return a wall-clock scheduling cutoff that remains correct across DST."""
    local_cutoff = datetime.fromtimestamp(int(day_cutoff))
    local_start = local_cutoff - timedelta(days=max(1, int(days)))
    return int(local_start.timestamp())


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


def calculate_long_term(rows: Iterable[Sequence[object]], today: date) -> LongTermStats:
    counts: Dict[date, int] = {}
    total_answers = 0
    total_again = 0
    rate_data_available = False
    for row in rows:
        if len(row) < 2:
            continue
        iso_date, raw_count = row[0], row[1]
        try:
            parsed = date.fromisoformat(str(iso_date))
        except (TypeError, ValueError):
            continue
        count = max(0, int(raw_count or 0))
        if count:
            counts[parsed] = counts.get(parsed, 0) + count
            total_answers += count
        if len(row) >= 3:
            rate_data_available = True
            again = max(0, int(row[2] or 0))
            total_again += min(count, again)
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
        lifetime_retention=(
            RateMetric.from_counts(total_answers - total_again, total_answers)
            if rate_data_available
            else RateMetric()
        ),
        lifetime_cards_studied=total_answers,
    )


def calculate_last_seven_days(
    rows: Iterable[Sequence[object]],
    scheduling_date: date,
) -> LastSevenDaysStats:
    """Aggregate the active scheduler day and its six preceding days."""

    start = scheduling_date - timedelta(days=6)
    answers = 0
    new_cards = 0
    again = 0
    for row in rows:
        if len(row) < 3:
            continue
        try:
            study_date = date.fromisoformat(str(row[0]))
            count = max(0, int(row[1] or 0))
            missed = max(0, int(row[2] or 0))
        except (TypeError, ValueError, OverflowError):
            continue
        if not start <= study_date <= scheduling_date:
            continue
        answers += count
        again += min(count, missed)
        if len(row) >= 4:
            try:
                new_cards += max(0, int(row[3] or 0))
            except (TypeError, ValueError, OverflowError):
                pass
    return LastSevenDaysStats(
        cards_studied=answers,
        new_cards_studied=new_cards,
        retention=RateMetric.from_counts(answers - again, answers),
        again_rate=RateMetric.from_counts(again, answers),
    )


def _safe_first(db: Any, sql: str, *args: object) -> Tuple[Any, ...]:
    row = db.first(sql, *args)
    if not row:
        # Every caller issues an aggregate query, which must return one row
        # even when its count is zero. A missing row is therefore unavailable
        # data, not evidence of a numeric zero.
        raise RuntimeError("aggregate query returned no row")
    return tuple(row)


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


def resolve_filter_scope(col: Any, config: Mapping[str, Any]) -> FilterScope:
    """Resolve the one dashboard filter scope, including excluded descendants."""
    heatmap = config["heatmap"]
    return FilterScope(
        excluded_deck_ids=tuple(sorted(_excluded_deck_ids(col, heatmap.get("excluded_deck_ids", [])))),
        exclude_manual_reschedules=bool(heatmap.get("exclude_manual_reschedules", True)),
        exclude_deleted_cards=bool(heatmap.get("exclude_deleted_cards", False)),
        include_rescheduled_new_cards=bool(config["new_cards"].get("include_rescheduled", True)),
        ignore_before=str(heatmap.get("ignore_before") or ""),
    )


def _deck_scope_condition(
    scope: FilterScope,
    alias: str = "",
) -> Tuple[Optional[str], List[object]]:
    """Return a deck exclusion condition for normal and filtered-deck cards."""
    if not scope.excluded_deck_ids:
        return None, []
    prefix = "{}.".format(alias) if alias else ""
    placeholders = ",".join("?" for _ in scope.excluded_deck_ids)
    return (
        "{prefix}did NOT IN ({ids}) AND "
        "({prefix}odid = 0 OR {prefix}odid NOT IN ({ids}))".format(
            prefix=prefix,
            ids=placeholders,
        ),
        list(scope.excluded_deck_ids) + list(scope.excluded_deck_ids),
    )


def _consistency_history_query(
    col: Any,
    scope: Optional[FilterScope] = None,
) -> List[Tuple[str, int]]:
    """Count scoped valid answers by scheduler date for Consistency."""
    resolved = scope or FilterScope()
    rollover = _rollover_seconds(int(col.sched.day_cutoff))
    day_expr = "date(r.id / 1000, 'unixepoch', 'localtime', '-{} seconds')".format(
        rollover
    )
    conditions, args = _history_filter_conditions(resolved)
    lower = _scope_history_lower_bound(col, resolved)
    if lower is not None:
        conditions.append("r.id >= ?")
        args.append(lower)
    rows = _safe_all(
        col.db,
        "SELECT {day}, count(*) FROM revlog r {join} "
        "WHERE {where} GROUP BY {day} ORDER BY {day}".format(
            day=day_expr,
            join="JOIN cards c ON c.id = r.cid" if _history_join(resolved) else "",
            where=" AND ".join(conditions),
        ),
        *args,
    )
    return [
        (str(row[0]), max(0, int(row[1] or 0)))
        for row in rows
        if len(row) >= 2 and row[0]
    ]


def browse_target_for_day(
    selected: date,
    scheduling_date: date,
    scope: FilterScope,
    card_ids: Sequence[int] = (),
    available: bool = True,
) -> BrowseTarget:
    """Return an exact, backend-owned card set for a covered scheduler date."""
    if not available:
        return BrowseTarget()
    del scope  # Scope was already applied by the query that produced card_ids.
    kind = BrowseTargetKind.REVIEWED if selected <= scheduling_date else BrowseTargetKind.DUE
    resolved = tuple(sorted({int(card_id) for card_id in card_ids if int(card_id) > 0}))
    if not resolved:
        return BrowseTarget()
    query = "cid:{}".format(",".join(str(card_id) for card_id in resolved))
    return BrowseTarget(kind=kind, query=query, exact=True, card_ids=resolved)


def _browse_target_for_ids(kind: BrowseTargetKind, card_ids: Sequence[int]) -> BrowseTarget:
    """Build an exact target from IDs already counted by the canonical query."""

    resolved = tuple(sorted({int(card_id) for card_id in card_ids if int(card_id) > 0}))
    if not resolved:
        return BrowseTarget()
    return BrowseTarget(
        kind=kind,
        query="cid:{}".format(",".join(str(card_id) for card_id in resolved)),
        exact=True,
        card_ids=resolved,
    )


def _history_join(scope: FilterScope) -> bool:
    return bool(scope.excluded_deck_ids or scope.exclude_deleted_cards)


def _history_filter_conditions(
    scope: FilterScope,
    alias: str = "r",
) -> Tuple[List[str], List[object]]:
    conditions = ["{}.ease > 0".format(alias)]
    args: List[object] = []
    if scope.exclude_manual_reschedules:
        conditions.append("{}.type != ?".format(alias))
        args.append(REVLOG_MANUAL_RESCHEDULE)
    deck_condition, deck_args = _deck_scope_condition(scope, "c")
    if deck_condition:
        conditions.append(deck_condition)
        args.extend(deck_args)
    return conditions, args


def _scope_history_lower_bound(col: Any, scope: FilterScope) -> Optional[int]:
    if not scope.ignore_before:
        return None
    try:
        start = date.fromisoformat(scope.ignore_before)
    except ValueError:
        return None
    rollover_time = datetime.fromtimestamp(int(col.sched.day_cutoff)).astimezone().timetz()
    return int(datetime.combine(start, rollover_time).timestamp() * 1000)


def _history_conditions_for_day(
    col: Any,
    scope: FilterScope,
    study_date: date,
) -> Tuple[List[str], List[object]]:
    rollover = _rollover_seconds(int(col.sched.day_cutoff))
    day_expression = "date(r.id / 1000, 'unixepoch', 'localtime', '-{} seconds')".format(rollover)
    conditions = ["{} = ?".format(day_expression)]
    args: List[object] = [study_date.isoformat()]
    filtered, filter_args = _history_filter_conditions(scope)
    conditions.extend(filtered)
    args.extend(filter_args)
    return conditions, args


def _new_card_condition(alias: str, include_rescheduled: bool) -> str:
    condition = "{0}.type IN (0, 3) AND {0}.lastIvl = 0".format(alias)
    if not include_rescheduled:
        condition += (
            " AND NOT EXISTS (SELECT 1 FROM revlog prior "
            "WHERE prior.cid = {alias}.cid AND prior.id < {alias}.id "
            "AND prior.ease > 0 AND prior.type != 4)"
        ).format(alias=alias)
    return condition


def _history_facts_query(
    col: Any,
    config: Mapping[str, Any],
    today: date,
    visible: bool,
    scope: Optional[FilterScope] = None,
) -> List[Tuple[str, int, int, int, Tuple[int, ...]]]:
    resolved = scope or resolve_filter_scope(col, config)
    conditions, args = _history_filter_conditions(resolved)
    start = history_start_date(config, today, visible)
    if start:
        rollover_time = datetime.fromtimestamp(int(col.sched.day_cutoff)).astimezone().timetz()
        start_dt = datetime.combine(start, rollover_time)
        conditions.append("r.id >= ?")
        args.append(int(start_dt.timestamp() * 1000))
    rollover = _rollover_seconds(int(col.sched.day_cutoff))
    day_expr = "date(r.id / 1000, 'unixepoch', 'localtime', '-{} seconds')".format(rollover)
    new_card_condition = _new_card_condition(
        "r",
        resolved.include_rescheduled_new_cards,
    )
    sql = (
        "SELECT {day}, count(*), "
        "count(DISTINCT CASE WHEN {new_cards} THEN r.cid END), "
        "coalesce(sum(CASE WHEN r.ease = 1 THEN 1 ELSE 0 END), 0), "
        "group_concat(DISTINCT CASE WHEN EXISTS "
        "(SELECT 1 FROM cards existing WHERE existing.id = r.cid) THEN r.cid END) "
        "FROM revlog r {join} {where} GROUP BY {day} ORDER BY {day}"
    ).format(
        day=day_expr,
        new_cards=new_card_condition,
        join="JOIN cards c ON c.id = r.cid" if _history_join(resolved) else "",
        where="WHERE " + " AND ".join(conditions) if conditions else "",
    )
    output: List[Tuple[str, int, int, int, Tuple[int, ...]]] = []
    for row in _safe_all(col.db, sql, *args):
        if not row or not row[0]:
            continue
        raw_ids = str(row[4] or "").split(",") if len(row) > 4 else []
        card_ids = tuple(sorted({int(value) for value in raw_ids if value.isdigit() and int(value) > 0}))
        output.append((
            str(row[0]),
            max(0, int(row[1] or 0)) if len(row) > 1 else 0,
            max(0, int(row[2] or 0)) if len(row) > 2 else 0,
            max(0, int(row[3] or 0)) if len(row) > 3 else 0,
            card_ids,
        ))
    return output


def _history_query(
    col: Any,
    config: Mapping[str, Any],
    today: date,
    visible: bool,
) -> List[Tuple[str, int, int]]:
    """Backward-compatible projection of the canonical history query."""
    return [
        (iso_date, completed, new_cards)
        for iso_date, completed, new_cards, _again_count, _card_ids in _history_facts_query(
            col,
            config,
            today,
            visible,
        )
    ]


def _history_day_counts(
    col: Any,
    scope: FilterScope,
    study_date: date,
) -> Tuple[int, int, int, Tuple[int, ...]]:
    conditions, args = _history_conditions_for_day(col, scope, study_date)
    new_card_condition = _new_card_condition("r", scope.include_rescheduled_new_cards)
    row = _safe_first(
        col.db,
        "SELECT count(*), "
        "count(DISTINCT CASE WHEN {new_cards} THEN r.cid END), "
        "coalesce(sum(CASE WHEN r.ease = 1 THEN 1 ELSE 0 END), 0), "
        "group_concat(DISTINCT CASE WHEN EXISTS "
        "(SELECT 1 FROM cards existing WHERE existing.id = r.cid) THEN r.cid END) "
        "FROM revlog r {join} WHERE {where}".format(
            new_cards=new_card_condition,
            join="JOIN cards c ON c.id = r.cid" if _history_join(scope) else "",
            where=" AND ".join(conditions),
        ),
        *args,
    )
    raw_ids = str(row[3] or "").split(",") if len(row) > 3 else []
    card_ids = tuple(sorted({int(value) for value in raw_ids if value.isdigit() and int(value) > 0}))
    return (
        max(0, int(row[0] or 0)) if row else 0,
        max(0, int(row[1] or 0)) if len(row) > 1 else 0,
        max(0, int(row[2] or 0)) if len(row) > 2 else 0,
        card_ids,
    )


def _due_conditions(
    scope: FilterScope,
    due_operator: str,
) -> Tuple[List[str], List[object]]:
    if due_operator not in {"=", "<="}:
        raise ValueError("unsupported due operator")
    conditions = [
        "queue IN (2, 3)",
        "type IN (2, 3)",
        "due {} ?".format(due_operator),
    ]
    args: List[object] = []
    deck_condition, deck_args = _deck_scope_condition(scope)
    if deck_condition:
        conditions.append(deck_condition)
        args.extend(deck_args)
    return conditions, args


def _intraday_relearning_due_details(
    col: Any,
    scope: FilterScope,
) -> Tuple[int, Tuple[int, ...]]:
    """Return active intraday relearning work belonging to the current day."""
    conditions = ["queue = 1", "type = 3", "due < ?"]
    args: List[object] = [int(col.sched.day_cutoff)]
    deck_condition, deck_args = _deck_scope_condition(scope)
    if deck_condition:
        conditions.append(deck_condition)
        args.extend(deck_args)
    row = _safe_first(
        col.db,
        "SELECT count(*), group_concat(id) FROM cards WHERE {}".format(
            " AND ".join(conditions)
        ),
        *args,
    )
    raw_ids = str(row[1] or "").split(",") if len(row) > 1 else []
    card_ids = tuple(
        sorted({int(value) for value in raw_ids if value.isdigit() and int(value) > 0})
    )
    return max(0, int(row[0] or 0)), card_ids


def _scheduled_due_details_for_day(
    col: Any,
    scope: FilterScope,
    offset: int,
) -> Tuple[int, Tuple[int, ...]]:
    scheduler_today = int(getattr(col.sched, "today", 0))
    operator = "<=" if offset == 0 else "="
    conditions, args = _due_conditions(scope, operator)
    args.insert(0, scheduler_today + max(0, int(offset)))
    row = _safe_first(
        col.db,
        "SELECT count(*), group_concat(id) FROM cards WHERE {}".format(" AND ".join(conditions)),
        *args,
    )
    raw_ids = str(row[1] or "").split(",") if len(row) > 1 else []
    card_ids = tuple(sorted({int(value) for value in raw_ids if value.isdigit() and int(value) > 0}))
    count = max(0, int(row[0] or 0))
    if offset == 0:
        intraday_count, intraday_ids = _intraday_relearning_due_details(col, scope)
        count += intraday_count
        card_ids = tuple(sorted(set(card_ids).union(intraday_ids)))
    return count, card_ids


def _scheduled_due_for_day(col: Any, scope: FilterScope, offset: int) -> int:
    """Backward-compatible count projection."""
    return _scheduled_due_details_for_day(col, scope, offset)[0]


def _forecast_facts_query(
    col: Any,
    config: Mapping[str, Any],
    today: date,
    scope: Optional[FilterScope] = None,
) -> Dict[str, Tuple[int, Tuple[int, ...]]]:
    heatmap = config["heatmap"]
    if not heatmap.get("show_due_forecast", True) or int(heatmap.get("forecast_days", 0)) <= 0:
        return {}
    scheduler_today = int(getattr(col.sched, "today", 0))
    last_due = scheduler_today + int(heatmap["forecast_days"]) - 1
    resolved = scope or resolve_filter_scope(col, config)
    conditions, args = _due_conditions(resolved, "<=")
    args.insert(0, last_due)
    rows = _safe_all(
        col.db,
        "SELECT due, count(*), group_concat(id) FROM cards WHERE {} GROUP BY due ORDER BY due".format(
            " AND ".join(conditions)
        ),
        *args,
    )
    output: Dict[str, Tuple[int, Tuple[int, ...]]] = {}
    for row in rows:
        if len(row) < 2:
            continue
        raw_due, raw_count = row[0], row[1]
        try:
            due = max(scheduler_today, int(raw_due))
            offset = due - scheduler_today
        except (TypeError, ValueError, OverflowError):
            continue
        if offset >= int(heatmap["forecast_days"]):
            continue
        day = (today + timedelta(days=offset)).isoformat()
        previous_count, previous_ids = output.get(day, (0, ()))
        raw_ids = str(row[2] or "").split(",") if len(row) > 2 else []
        card_ids = tuple(int(value) for value in raw_ids if value.isdigit() and int(value) > 0)
        output[day] = (
            previous_count + max(0, int(raw_count or 0)),
            tuple(sorted(set(previous_ids).union(card_ids))),
        )
    intraday_count, intraday_ids = _intraday_relearning_due_details(col, resolved)
    if intraday_count:
        current = today.isoformat()
        previous_count, previous_ids = output.get(current, (0, ()))
        output[current] = (
            previous_count + intraday_count,
            tuple(sorted(set(previous_ids).union(intraday_ids))),
        )
    return output


def _forecast_query(col: Any, config: Mapping[str, Any], today: date) -> Dict[str, int]:
    """Backward-compatible count projection of canonical scheduled demand."""
    return {
        iso_date: count
        for iso_date, (count, _card_ids) in _forecast_facts_query(col, config, today).items()
    }


def _pace(
    col: Any,
    days: int,
    scope: Optional[FilterScope] = None,
) -> Tuple[int, float, float | None]:
    cutoff = int(col.sched.day_cutoff)
    lower = pace_lower_bound(cutoff, days) * 1000
    resolved = scope or FilterScope()
    scoped_lower = _scope_history_lower_bound(col, resolved)
    if scoped_lower is not None:
        lower = max(lower, scoped_lower)
    conditions, args = _history_filter_conditions(resolved)
    conditions.append("r.id >= ?")
    args.append(lower)
    row = _safe_first(
        col.db,
        "SELECT count(*), coalesce(sum(r.time), 0) FROM revlog r {join} WHERE {where}".format(
            join="JOIN cards c ON c.id = r.cid" if _history_join(resolved) else "",
            where=" AND ".join(conditions),
        ),
        *args,
    )
    answers = int(row[0] or 0) if row else 0
    seconds = float(row[1] or 0) / 1000.0 if len(row) > 1 else 0.0
    cards_per_minute = answers * 60.0 / seconds if answers and seconds > 0 else None
    return answers, seconds, cards_per_minute


def _lifetime_paces(
    col: Any,
    include_rescheduled: bool,
    scope: Optional[FilterScope] = None,
) -> Tuple[float | None, float | None]:
    resolved = scope or FilterScope(include_rescheduled_new_cards=include_rescheduled)
    conditions, args = _history_filter_conditions(resolved)
    scoped_lower = _scope_history_lower_bound(col, resolved)
    if scoped_lower is not None:
        conditions.append("r.id >= ?")
        args.append(scoped_lower)
    new_condition = _new_card_condition("r", include_rescheduled)
    row = _safe_first(
        col.db,
        "SELECT count(*), coalesce(sum(time), 0), "
        "sum(CASE WHEN {new} THEN 1 ELSE 0 END), "
        "coalesce(sum(CASE WHEN {new} THEN time ELSE 0 END), 0) "
        "FROM revlog r {join} WHERE {valid}".format(
            new=new_condition,
            join="JOIN cards c ON c.id = r.cid" if _history_join(resolved) else "",
            valid=" AND ".join(conditions),
        ),
        *args,
    )
    answers = int(row[0] or 0) if row else 0
    seconds = float(row[1] or 0) / 1000.0 if len(row) > 1 else 0.0
    new_answers = int(row[2] or 0) if len(row) > 2 else 0
    new_seconds = float(row[3] or 0) / 1000.0 if len(row) > 3 else 0.0
    overall_seconds_per_card = seconds / answers if answers and seconds > 0 else None
    new_seconds_per_card = new_seconds / new_answers if new_answers and new_seconds > 0 else None
    return overall_seconds_per_card, new_seconds_per_card


def _today_new_cards_studied(
    col: Any,
    include_rescheduled: bool,
    scope: Optional[FilterScope] = None,
) -> int:
    cutoff = int(col.sched.day_cutoff)
    lower = pace_lower_bound(cutoff, 1) * 1000
    resolved = scope or FilterScope(include_rescheduled_new_cards=include_rescheduled)
    scoped_lower = _scope_history_lower_bound(col, resolved)
    if scoped_lower is not None:
        lower = max(lower, scoped_lower)
    condition = _new_card_condition("r", include_rescheduled)
    conditions, args = _history_filter_conditions(resolved)
    conditions.append("r.id >= ?")
    args.append(lower)
    row = _safe_first(
        col.db,
        "SELECT count(DISTINCT CASE WHEN {new} THEN r.cid END) "
        "FROM revlog r {join} WHERE {where}".format(
            new=condition,
            join="JOIN cards c ON c.id = r.cid" if _history_join(resolved) else "",
            where=" AND ".join(conditions),
        ),
        *args,
    )
    return max(0, int(row[0] or 0)) if row else 0


def _today(
    col: Any,
    config: Mapping[str, Any],
    day_facts: Optional[DayFacts] = None,
    scope: Optional[FilterScope] = None,
) -> Tuple[TodayStats, float | None, float | None]:
    """Collect scoped completed work and pace for the active scheduler day."""
    study = config["study"]
    resolved = scope or resolve_filter_scope(col, config)
    queried_answers, today_seconds, _ = _pace(col, 1, resolved)
    include_rescheduled = resolved.include_rescheduled_new_cards
    if day_facts is None:
        today_answers = queried_answers
        today_new_cards = _today_new_cards_studied(
            col,
            include_rescheduled,
            resolved,
        )
    else:
        if not day_facts.reviews_completed.is_available:
            raise RuntimeError("current-day completed answers are unavailable")
        if not day_facts.new_cards_studied.is_available:
            raise RuntimeError("current-day new-card count is unavailable")
        # Calendar, Today, Progress and Settings all consume these canonical
        # current-day counts.  The pace query contributes elapsed time only.
        today_answers = int(day_facts.reviews_completed.value)
        today_new_cards = int(day_facts.new_cards_studied.value)
    try:
        lifetime_pace, new_pace = _lifetime_paces(
            col,
            include_rescheduled,
            resolved,
        )
    except Exception:
        # Pace history is optional.  Its failure makes ETA unknown, not Today's
        # successfully collected answer counts falsely unavailable or zero.
        lifetime_pace = new_pace = None
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
    scheduled_review: Optional[int] = None,
    scope: Optional[FilterScope] = None,
) -> QueueStats:
    """Return one scoped, raw workload for Today’s Progress.

    New is active new-card inventory. Learning is active original learning work
    due before the next rollover, including interday learning due by the current
    scheduler day. Relearning is deliberately excluded from Learning because it
    belongs to the canonical review/relearning value supplied by ``DayFacts``.
    Preview/repeat cards in queue 4 are excluded from every category. None of
    these values is reduced by deck daily limits.
    """
    if scheduled_review is None:
        raise RuntimeError("scheduled review demand is unavailable")
    try:
        review = int(scheduled_review)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError("scheduled review demand is unavailable") from exc
    if review < 0:
        raise RuntimeError("scheduled review demand is unavailable")

    resolved = scope or FilterScope()
    conditions = [
        "((queue = 0 AND type = 0) OR "
        "(type = 1 AND ((queue = 1 AND due < ?) OR (queue = 3 AND due <= ?))))"
    ]
    args: List[object] = [
        int(col.sched.day_cutoff),
        int(getattr(col.sched, "today", 0)),
    ]
    deck_condition, deck_args = _deck_scope_condition(resolved)
    if deck_condition:
        conditions.append(deck_condition)
        args.extend(deck_args)
    row = _safe_first(
        col.db,
        "SELECT "
        "coalesce(sum(CASE WHEN queue = 0 AND type = 0 THEN 1 ELSE 0 END), 0), "
        "coalesce(sum(CASE WHEN type = 1 AND "
        "((queue = 1 AND due < ?) OR (queue = 3 AND due <= ?)) "
        "THEN 1 ELSE 0 END), 0) "
        "FROM cards WHERE {}".format(" AND ".join(conditions)),
        int(col.sched.day_cutoff),
        int(getattr(col.sched, "today", 0)),
        *args,
    )
    new = max(0, int(row[0] or 0))
    learning = max(0, int(row[1] or 0))
    total = new + learning + review
    estimate: int | None = None
    if total == 0:
        estimate = 0
    elif estimate_pace and estimate_pace > 0:
        effective_new_pace = new_pace if new_pace and new_pace > 0 else estimate_pace
        raw_seconds = new * effective_new_pace + (learning + review) * estimate_pace
        estimate = max(60, math.ceil(raw_seconds / 60.0) * 60)
    return QueueStats(new, learning, review, total, estimate)


def _deck_tree_node(node: Any, deck_id: int) -> Any | None:
    """Return one deck node from an Anki due tree without assuming its root."""

    try:
        if int(getattr(node, "deck_id", 0) or 0) == deck_id:
            return node
    except (TypeError, ValueError, OverflowError):
        pass
    for child in getattr(node, "children", ()) or ():
        match = _deck_tree_node(child, deck_id)
        if match is not None:
            return match
    return None


def _scheduler_hidden_buried(
    col: Any,
    scope: FilterScope,
) -> BuriedStats:
    """Return due siblings omitted from Anki's authoritative reviewer queue.

    Anki's due tree is populated before the queue builder applies sibling
    burying, while ``QueuedCards`` is the source of the native reviewer
    counter.  Progressbar reconciles those two snapshots and adds each positive
    category difference to cards already in queues -2/-3.  Deck exclusions are
    a dashboard-only filter that Anki's queue builder cannot express, so the
    reconciliation deliberately falls back to SQL-only counts when exclusions
    are active.
    """

    if scope.excluded_deck_ids:
        return BuriedStats()

    sched = getattr(col, "sched", None)
    decks = getattr(col, "decks", None)
    get_queued_cards = getattr(sched, "get_queued_cards", None)
    deck_due_tree = getattr(sched, "deck_due_tree", None)
    if not callable(get_queued_cards) or not callable(deck_due_tree):
        return BuriedStats()

    get_current_id = getattr(decks, "get_current_id", None)
    if not callable(get_current_id):
        get_current_id = getattr(decks, "selected", None)
    if not callable(get_current_id):
        return BuriedStats()

    try:
        deck_id = int(get_current_id())
        try:
            node = deck_due_tree(deck_id)
        except TypeError:
            node = _deck_tree_node(deck_due_tree(), deck_id)
        if node is None:
            return BuriedStats()
        try:
            queued = get_queued_cards(fetch_limit=0)
        except TypeError:
            queued = get_queued_cards()
        tree_new = max(0, int(getattr(node, "new_count", 0) or 0))
        tree_learning = max(0, int(getattr(node, "learn_count", 0) or 0))
        tree_review = max(0, int(getattr(node, "review_count", 0) or 0))
        queue_new = max(0, int(getattr(queued, "new_count", 0) or 0))
        queue_learning = max(0, int(getattr(queued, "learning_count", 0) or 0))
        queue_review = max(0, int(getattr(queued, "review_count", 0) or 0))
    except Exception:
        # The scheduler reconciliation is an optional precision layer.  A
        # backend or compatibility failure must not hide the authoritative SQL
        # count of cards already in queues -2/-3.
        return BuriedStats()

    return BuriedStats(
        max(0, tree_new - queue_new),
        max(0, tree_learning - queue_learning),
        max(0, tree_review - queue_review),
    )


def _buried(col: Any, scope: Optional[FilterScope] = None) -> BuriedStats:
    """Return Progressbar-equivalent buried and scheduler-hidden due counts."""
    resolved = scope or FilterScope()
    conditions = ["queue IN (-2, -3)"]
    args: List[object] = []
    deck_condition, deck_args = _deck_scope_condition(resolved)
    if deck_condition:
        conditions.append(deck_condition)
        args.extend(deck_args)
    row = _safe_first(
        col.db,
        "SELECT "
        "coalesce(sum(CASE WHEN type = 0 THEN 1 ELSE 0 END), 0), "
        "coalesce(sum(CASE WHEN type IN (1, 3) AND due <= "
        "CASE WHEN due < 1000000000 THEN ? ELSE ? END THEN 1 ELSE 0 END), 0), "
        "coalesce(sum(CASE WHEN type = 2 AND due <= ? THEN 1 ELSE 0 END), 0) "
        "FROM cards WHERE {}".format(" AND ".join(conditions)),
        int(getattr(col.sched, "today", 0)),
        int(col.sched.day_cutoff),
        int(getattr(col.sched, "today", 0)),
        *args,
    )
    already_buried = BuriedStats(
        max(0, int(row[0] or 0)) if row else 0,
        max(0, int(row[1] or 0)) if len(row) > 1 else 0,
        max(0, int(row[2] or 0)) if len(row) > 2 else 0,
    )
    scheduler_hidden = _scheduler_hidden_buried(col, resolved)
    return BuriedStats(
        already_buried.new + scheduler_hidden.new,
        already_buried.learning + scheduler_hidden.learning,
        already_buried.review + scheduler_hidden.review,
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


def _relation(selected: date, scheduling_date: date) -> DayRelation:
    if selected < scheduling_date:
        return DayRelation.PAST
    if selected > scheduling_date:
        return DayRelation.FUTURE
    return DayRelation.CURRENT


def _unavailable_int(reason: AvailabilityReason) -> ValueState[int]:
    return ValueState.unavailable(reason)


def _materialize_day_facts(
    selected: date,
    scheduling_date: date,
    scope: FilterScope,
    history_coverage: ValueState[DateCoverage],
    forecast_coverage: ValueState[DateCoverage],
    history_record: Optional[Tuple[int, int, int, Tuple[int, ...]]],
    forecast_record: Optional[Tuple[int, Tuple[int, ...]]],
    events_state: ValueState[Tuple[EventItem, ...]],
) -> DayFacts:
    iso_date = selected.isoformat()
    relation = _relation(selected, scheduling_date)
    if relation == DayRelation.FUTURE:
        completed = new_cards = again = _unavailable_int(
            AvailabilityReason.HISTORY_OUT_OF_RANGE
        )
        history_ids: Tuple[int, ...] = ()
    elif history_coverage.status == ValueStatus.LOADING:
        completed = new_cards = again = ValueState.loading()
        history_ids = ()
    elif not history_coverage.is_available:
        completed = new_cards = again = _unavailable_int(history_coverage.reason)
        history_ids = ()
    elif not history_coverage.value.contains(iso_date):
        completed = new_cards = again = _unavailable_int(AvailabilityReason.HISTORY_OUT_OF_RANGE)
        history_ids = ()
    else:
        answer_count, new_count, again_count, history_ids = history_record or (0, 0, 0, ())
        completed = ValueState.available(answer_count)
        new_cards = ValueState.available(new_count)
        again = ValueState.available(again_count)

    if relation == DayRelation.PAST:
        due = _unavailable_int(AvailabilityReason.FORECAST_OUT_OF_RANGE)
        due_ids: Tuple[int, ...] = ()
    elif forecast_record is not None:
        due_count, due_ids = forecast_record
        due = ValueState.available(due_count)
    elif forecast_coverage.status == ValueStatus.LOADING:
        due = ValueState.loading()
        due_ids = ()
    elif not forecast_coverage.is_available:
        due = _unavailable_int(forecast_coverage.reason)
        due_ids = ()
    elif not forecast_coverage.value.contains(iso_date):
        due = _unavailable_int(AvailabilityReason.FORECAST_OUT_OF_RANGE)
        due_ids = ()
    else:
        due = ValueState.available(0)
        due_ids = ()

    if events_state.status == ValueStatus.LOADING:
        day_events: ValueState[Tuple[EventItem, ...]] = ValueState.loading()
    elif not events_state.is_available:
        day_events = ValueState.unavailable(events_state.reason)
    else:
        day_events = ValueState.available(tuple(item for item in events_state.value if item.date == iso_date))

    if relation == DayRelation.FUTURE:
        if due.status == ValueStatus.LOADING:
            domain_state = DayDomainState.LOADING
        elif not due.is_available:
            domain_state = DayDomainState.UNAVAILABLE
        elif int(due.value) > 0:
            domain_state = DayDomainState.FUTURE_DUE
        else:
            domain_state = DayDomainState.NO_DUE
        browse_available = due.is_available and int(due.value) > 0 and bool(due_ids)
        browse_ids = due_ids
        browse_kind = BrowseTargetKind.DUE
    else:
        if completed.status == ValueStatus.LOADING:
            domain_state = DayDomainState.LOADING
        elif not completed.is_available:
            domain_state = DayDomainState.UNAVAILABLE
        elif int(completed.value) == 0:
            domain_state = DayDomainState.NO_HISTORICAL_ACTIVITY
        elif int(again.value) == 0:
            domain_state = DayDomainState.NO_AGAIN
        else:
            domain_state = DayDomainState.TROUBLE
        if (
            relation == DayRelation.CURRENT
            and completed.is_available
            and int(completed.value) == 0
            and due.is_available
            and int(due.value) > 0
        ):
            browse_ids = due_ids
            browse_available = bool(due_ids)
            browse_kind = BrowseTargetKind.DUE
        else:
            browse_ids = history_ids
            browse_available = (
                completed.is_available
                and int(completed.value) > 0
                and bool(browse_ids)
            )
            browse_kind = BrowseTargetKind.REVIEWED

    return DayFacts(
        date=iso_date,
        scheduling_date=scheduling_date.isoformat(),
        relation=relation,
        reviews_completed=completed,
        new_cards_studied=new_cards,
        reviews_due=due,
        again_count=again,
        events=day_events,
        browse_target=(
            _browse_target_for_ids(browse_kind, browse_ids)
            if browse_available
            else BrowseTarget()
        ),
        filter_scope=scope,
        domain_state=domain_state,
    )


def _inclusive_iso_dates(start: date, end: date) -> Iterable[str]:
    """Yield a bounded inclusive date range without sparse-value inference."""
    if start > end:
        return
    for ordinal in range(start.toordinal(), end.toordinal() + 1):
        yield date.fromordinal(ordinal).isoformat()


def _revision(col: Any, scope: FilterScope, cutoff: int) -> str:
    raw_mod = getattr(col, "mod", 0)
    try:
        collection_mod = raw_mod() if callable(raw_mod) else raw_mod
    except Exception:
        collection_mod = 0
    return "{}:{}:{}:{}:{}:{}:{}:{}".format(
        collection_mod or 0,
        int(getattr(col.sched, "today", 0)),
        cutoff,
        ",".join(str(deck_id) for deck_id in scope.excluded_deck_ids),
        int(scope.exclude_manual_reschedules),
        int(scope.exclude_deleted_cards),
        int(scope.include_rescheduled_new_cards),
        scope.ignore_before,
    )


def collect_dashboard_facts(
    col: Any,
    config: Mapping[str, Any],
    calendar_today: Optional[date] = None,
) -> DashboardFacts:
    """Collect every dashboard consumer through one resolved filter scope."""
    cutoff = int(col.sched.day_cutoff)
    scheduling_date = scheduling_today(cutoff)
    civil_today = calendar_today or date.today()
    scope = resolve_filter_scope(col, config)

    try:
        history_rows = _history_facts_query(col, config, scheduling_date, False, scope)
        rate_rows = [
            (day, count, again, new_cards)
            for day, count, new_cards, again, _ids in history_rows
        ]
        last_seven_days: ValueState[LastSevenDaysStats] = ValueState.available(
            calculate_last_seven_days(rate_rows, scheduling_date)
        )
        long_term: ValueState[LongTermStats] = ValueState.available(
            calculate_long_term(
                rate_rows,
                scheduling_date,
            )
        )
        visible_start = history_start_date(config, scheduling_date, True)
        if visible_start is None:
            covered_history_dates: List[date] = []
            for day, _count, _new_cards, _again_count, _card_ids in history_rows:
                try:
                    parsed = date.fromisoformat(day)
                except (TypeError, ValueError):
                    continue
                if parsed <= scheduling_date:
                    covered_history_dates.append(parsed)
            coverage_start = min(covered_history_dates, default=scheduling_date)
        else:
            coverage_start = visible_start
        coverage = DateCoverage(
            coverage_start.isoformat(),
            scheduling_date.isoformat(),
        )
        visible_history = {
            day: (count, new_cards, again_count, card_ids)
            for day, count, new_cards, again_count, card_ids in history_rows
            if coverage.contains(day)
        }
        history_coverage: ValueState[DateCoverage] = ValueState.available(coverage)
    except Exception:
        visible_history = {}
        last_seven_days = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)
        long_term = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)
        history_coverage = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)

    heatmap = config["heatmap"]
    forecast_days = max(0, int(heatmap.get("forecast_days", 0)))
    forecast_enabled = bool(heatmap.get("show_due_forecast", True)) and forecast_days > 0
    try:
        if forecast_enabled:
            forecast = _forecast_facts_query(col, config, scheduling_date, scope)
            forecast_coverage: ValueState[DateCoverage] = ValueState.available(DateCoverage(
                scheduling_date.isoformat(),
                (scheduling_date + timedelta(days=forecast_days - 1)).isoformat(),
            ))
        else:
            current_due = _scheduled_due_details_for_day(col, scope, 0)
            forecast = {scheduling_date.isoformat(): current_due}
            forecast_coverage = ValueState.unavailable(AvailabilityReason.FORECAST_DISABLED)
    except Exception:
        forecast = {}
        forecast_coverage = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)

    # Normalize against positive workload only.  Zero days must not pull the
    # robust percentile toward zero when the loaded horizon is sparse.
    forecast_counts = sorted(
        count
        for record in forecast.values()
        for count in (max(0, int(record[0])),)
        if count > 0
    )
    if forecast_counts:
        rank = max(0, min(len(forecast_counts) - 1, math.ceil(len(forecast_counts) * .90) - 1))
        due_load_reference = float(max(1, forecast_counts[rank]))
    else:
        due_load_reference = 0.0

    try:
        event_items = tuple(_events(config, civil_today))
        events: ValueState[Tuple[EventItem, ...]] = ValueState.available(event_items)
    except Exception:
        events = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)

    provisional = DashboardFacts(
        scheduling_date=scheduling_date.isoformat(),
        calendar_date=civil_today.isoformat(),
        revision=_revision(col, scope, cutoff),
        next_rollover=datetime.fromtimestamp(cutoff).astimezone().isoformat(timespec="minutes"),
        filter_scope=scope,
        events=events,
        last_seven_days=last_seven_days,
        long_term=long_term,
        history_coverage=history_coverage,
        forecast_coverage=forecast_coverage,
        due_load_reference=due_load_reference,
    )

    keys = set(visible_history).union(forecast)
    if history_coverage.is_available:
        try:
            keys.update(_inclusive_iso_dates(
                date.fromisoformat(history_coverage.value.start),
                date.fromisoformat(history_coverage.value.end),
            ))
        except ValueError:
            pass
    if forecast_coverage.is_available:
        try:
            keys.update(_inclusive_iso_dates(
                date.fromisoformat(forecast_coverage.value.start),
                date.fromisoformat(forecast_coverage.value.end),
            ))
        except ValueError:
            pass
    if events.is_available:
        keys.update(item.date for item in events.value)
    keys.add(scheduling_date.isoformat())
    days = {
        iso_date: _materialize_day_facts(
            date.fromisoformat(iso_date),
            scheduling_date,
            scope,
            history_coverage,
            forecast_coverage,
            visible_history.get(iso_date),
            forecast.get(iso_date),
            events,
        )
        for iso_date in sorted(keys)
    }
    try:
        current_day = days[scheduling_date.isoformat()]
        today_stats, estimate_pace, new_pace = _today(
            col,
            config,
            current_day,
            scope,
        )
        today: ValueState[TodayStats] = ValueState.available(today_stats)
    except Exception:
        today = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)
        estimate_pace = new_pace = None

    try:
        current_due = days[scheduling_date.isoformat()].reviews_due
        if not current_due.is_available:
            raise RuntimeError("current scheduled review demand is unavailable")
        queue: ValueState[QueueStats] = ValueState.available(
            _queue(
                col,
                estimate_pace,
                new_pace,
                int(current_due.value),
                scope,
            )
        )
    except Exception:
        queue = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)

    try:
        buried: ValueState[BuriedStats] = ValueState.available(_buried(col, scope))
    except Exception:
        buried = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)

    return replace(provisional, today=today, queue=queue, buried=buried, days=days)


def collect_day_facts(
    col: Any,
    config: Mapping[str, Any],
    selected_date: date,
    scheduling_date: date,
    calendar_today: date,
) -> DayFacts:
    """Collect one date through the same filters and meanings as the dashboard."""
    scope = resolve_filter_scope(col, config)
    visible_start = history_start_date(config, scheduling_date, True)
    history_coverage: ValueState[DateCoverage] = ValueState.available(DateCoverage(
        visible_start.isoformat() if visible_start else "",
        scheduling_date.isoformat(),
    ))
    history_record: Optional[Tuple[int, int, int, Tuple[int, ...]]] = None
    if selected_date <= scheduling_date and history_coverage.value.contains(selected_date.isoformat()):
        try:
            history_record = _history_day_counts(col, scope, selected_date)
        except Exception:
            history_coverage = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)

    heatmap = config["heatmap"]
    forecast_days = max(0, int(heatmap.get("forecast_days", 0)))
    forecast_enabled = bool(heatmap.get("show_due_forecast", True)) and forecast_days > 0
    forecast_record: Optional[Tuple[int, Tuple[int, ...]]] = None
    if forecast_enabled:
        forecast_coverage: ValueState[DateCoverage] = ValueState.available(DateCoverage(
            scheduling_date.isoformat(),
            (scheduling_date + timedelta(days=forecast_days - 1)).isoformat(),
        ))
    else:
        forecast_coverage = ValueState.unavailable(AvailabilityReason.FORECAST_DISABLED)
    offset = (selected_date - scheduling_date).days
    if offset == 0 or (offset > 0 and forecast_enabled and offset < forecast_days):
        try:
            forecast_record = _scheduled_due_details_for_day(col, scope, offset)
        except Exception:
            forecast_coverage = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)

    try:
        events: ValueState[Tuple[EventItem, ...]] = ValueState.available(tuple(_events(config, calendar_today)))
    except Exception:
        events = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)
    return _materialize_day_facts(
        selected_date,
        scheduling_date,
        scope,
        history_coverage,
        forecast_coverage,
        history_record,
        forecast_record,
        events,
    )


def unavailable_snapshot(
    verse: Optional[VerseContent] = None,
    scheduling_date: str = "",
    day_cutoff_iso: str = "",
    revision: str = "",
) -> DashboardSnapshot:
    """Build a typed full-query failure without zero/error projections."""
    facts = DashboardFacts.unavailable(
        scheduling_date=scheduling_date,
        calendar_date=date.today().isoformat(),
        revision=revision,
        next_rollover=day_cutoff_iso,
    )
    return DashboardSnapshot(
        facts=facts,
        verse=verse or VerseContent(),
    )


def representative_preview_snapshot(reference_date: str = "") -> DashboardSnapshot:
    """Return deterministic, clearly labelled sample facts for Settings only."""

    try:
        scheduling_day = date.fromisoformat(reference_date) if reference_date else date.today()
    except (TypeError, ValueError):
        scheduling_day = date.today()
    event_day = scheduling_day + timedelta(days=11)
    event = EventItem(
        "settings-preview-event",
        "Pediatrics review",
        event_day.isoformat(),
        11,
    )
    days: Dict[str, DayFacts] = {}
    for offset in range(-28, 91):
        current = scheduling_day + timedelta(days=offset)
        relation = (
            DayRelation.PAST
            if offset < 0
            else DayRelation.FUTURE
            if offset > 0
            else DayRelation.CURRENT
        )
        completed = max(0, 186 - abs(offset) * 7) if offset <= 0 else 0
        due = 0 if offset < 0 else 26 + (offset * 19) % 118
        history_unavailable = ValueState.unavailable(
            AvailabilityReason.HISTORY_OUT_OF_RANGE
        )
        forecast_unavailable = ValueState.unavailable(
            AvailabilityReason.FORECAST_OUT_OF_RANGE
        )
        days[current.isoformat()] = DayFacts(
            date=current.isoformat(),
            scheduling_date=scheduling_day.isoformat(),
            relation=relation,
            reviews_completed=(
                ValueState.available(completed)
                if offset <= 0
                else history_unavailable
            ),
            new_cards_studied=(
                ValueState.available(max(0, 14 - abs(offset) // 3))
                if offset <= 0
                else history_unavailable
            ),
            reviews_due=(
                ValueState.available(due)
                if offset >= 0
                else forecast_unavailable
            ),
            again_count=(
                ValueState.available(max(0, 9 - abs(offset) // 2))
                if offset <= 0
                else history_unavailable
            ),
            events=ValueState.available((event,) if current == event_day else ()),
            domain_state=(
                DayDomainState.TROUBLE
                if offset <= 0 and completed
                else DayDomainState.FUTURE_DUE
                if due
                else DayDomainState.NO_DUE
            ),
        )
    facts = DashboardFacts(
        scheduling_date=scheduling_day.isoformat(),
        calendar_date=scheduling_day.isoformat(),
        revision="settings-preview-sample-v1",
        next_rollover="{}T04:00:00".format(
            (scheduling_day + timedelta(days=1)).isoformat()
        ),
        today=ValueState.available(TodayStats(186, 14, 4_920, 26.5)),
        queue=ValueState.available(QueueStats(32, 14, 78, 124, 3_480)),
        buried=ValueState.available(BuriedStats(2, 1, 4)),
        events=ValueState.available((event,)),
        last_seven_days=ValueState.available(
            LastSevenDaysStats(
                cards_studied=1_214,
                new_cards_studied=148,
                retention=RateMetric.from_counts(1_008, 1_214),
                again_rate=RateMetric.from_counts(206, 1_214),
            )
        ),
        long_term=ValueState.available(
            LongTermStats(
                average_reviews_per_active_day=214,
                active_days_percent=86,
                longest_streak=73,
                current_streak=19,
                lifetime_retention=RateMetric.from_counts(68_420, 82_640),
                lifetime_cards_studied=82_640,
            )
        ),
        history_coverage=ValueState.available(
            DateCoverage("", scheduling_day.isoformat())
        ),
        forecast_coverage=ValueState.available(
            DateCoverage(
                scheduling_day.isoformat(),
                (scheduling_day + timedelta(days=90)).isoformat(),
            )
        ),
        due_load_reference=132.0,
        days=days,
    )
    return DashboardSnapshot(
        facts=facts,
        verse=VerseContent(
            "For God has not given us a spirit of fear and timidity, but of power, love, and self-discipline.",
            "2 Timothy 1:7 (NLT)",
        ),
    )


def collect_snapshot(col: Any, config: Mapping[str, Any], verse: VerseContent) -> DashboardSnapshot:
    """Collect the canonical facts and presentation-only verse content."""
    facts = collect_dashboard_facts(col, config)
    return DashboardSnapshot(
        facts=facts,
        verse=verse,
    )
