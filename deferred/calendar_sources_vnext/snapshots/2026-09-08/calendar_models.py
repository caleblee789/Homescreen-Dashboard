"""Deferred external-calendar types.

This module is intentionally source-only for the future calendar-sources patch.
It is excluded from the release package together with the repository, manager,
and vendored parser runtime.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CalendarOccurrence:
    """One local or externally sourced calendar occurrence."""

    occurrence_id: str
    name: str
    start_date: str
    end_date_exclusive: str
    source_id: str = "local"
    source_name: str = "Local"
    series_id: str = ""
    editable: bool = False
    archived: bool = False
    hidden: bool = False


@dataclass(frozen=True)
class CalendarDayEvent:
    """Date-projected event used by the deferred dashboard bridge."""

    event_id: str
    occurrence_id: str
    name: str
    date: str
    source_id: str = "local"
    source_name: str = "Local"
    editable: bool = False
