"""Pure Event Manager filtering and action-eligibility rules."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, List, Optional, Sequence, Tuple

from .calendar_models import CalendarOccurrence


class CalendarManagerRangeError(ValueError):
    pass


def add_year_safe(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, month=2, day=28)


def manager_date_range(
    preset: str,
    today: date,
    custom_start: Optional[date] = None,
    custom_end_inclusive: Optional[date] = None,
) -> Tuple[date, date]:
    if preset == "month":
        start = today.replace(day=1)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    elif preset == "year":
        start = date(today.year, 1, 1)
        end = date(today.year + 1, 1, 1)
    elif preset == "past":
        start = add_year_safe(today, -1)
        end = today
    elif preset == "custom":
        if custom_start is None or custom_end_inclusive is None:
            raise CalendarManagerRangeError("A custom event range requires both dates")
        start = custom_start
        end = custom_end_inclusive + timedelta(days=1)
    else:
        start = today
        end = add_year_safe(today, 1)
    if end <= start:
        raise CalendarManagerRangeError("The range end must be on or after the start date")
    if (end - start).days > 3660:
        raise CalendarManagerRangeError("Custom event ranges are limited to ten years")
    return start, end


def filter_occurrences(
    values: Iterable[CalendarOccurrence],
    *,
    view: str,
    today: date,
    source_id: str = "",
    search: str = "",
) -> List[CalendarOccurrence]:
    needle = search.strip().casefold()
    result = []
    for occurrence in values:
        occurrence_end = date.fromisoformat(occurrence.end_date_exclusive)
        if source_id and occurrence.source_id != source_id:
            continue
        if view == "upcoming" and (
            occurrence.archived or occurrence.hidden or occurrence_end <= today
        ):
            continue
        if view == "past" and (
            occurrence.hidden or (not occurrence.archived and occurrence_end > today)
        ):
            continue
        if view == "hidden" and not occurrence.hidden:
            continue
        haystack = "\n".join(
            (
                occurrence.name,
                occurrence.start_date,
                occurrence.end_date_exclusive,
                occurrence.source_name,
            )
        ).casefold()
        if needle and needle not in haystack:
            continue
        result.append(occurrence)
    return result


def eligible_for_action(
    values: Sequence[CalendarOccurrence], action: str
) -> Tuple[List[CalendarOccurrence], int]:
    local_actions = {"edit", "duplicate", "archive", "restore", "delete"}
    external_actions = {"hide", "unhide", "refresh", "manage"}
    if action in local_actions:
        eligible = [value for value in values if value.source_id == "local"]
    elif action in external_actions:
        eligible = [value for value in values if value.source_id != "local"]
    else:
        eligible = []
    if action in {"edit", "manage"} and len(values) != 1:
        eligible = []
    return eligible, len(values) - len(eligible)
