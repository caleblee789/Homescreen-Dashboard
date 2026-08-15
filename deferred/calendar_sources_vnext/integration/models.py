"""Typed, UI-independent dashboard data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class TodayStats:
    answers: int = 0
    new_cards_studied: int = 0
    seconds: float = 0.0
    pace_value: Optional[float] = None
    pace_unit: str = "seconds_per_card"


@dataclass(frozen=True)
class QueueStats:
    new: int = 0
    learning: int = 0
    review: int = 0
    total: int = 0
    estimated_duration_seconds: Optional[int] = None


@dataclass(frozen=True)
class BuriedStats:
    new: int = 0
    learning: int = 0
    review: int = 0


@dataclass(frozen=True)
class EventItem:
    event_id: str
    name: str
    date: str
    days_remaining: int
    archived: bool = False


@dataclass(frozen=True)
class CalendarOccurrence:
    """One local or externally sourced calendar occurrence.

    Dates use civil-calendar semantics. ``end_date_exclusive`` is always later
    than ``start_date`` so multi-day occurrences can be projected without
    provider-specific end-date rules leaking into the UI.
    """

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
    """Date-projected calendar item consumed by the dashboard renderer."""

    event_id: str
    occurrence_id: str
    name: str
    date: str
    source_id: str = "local"
    source_name: str = "Local"
    editable: bool = False


@dataclass(frozen=True)
class DailyActivity:
    date: str
    reviews_completed: int = 0
    reviews_due: int = 0
    new_cards_studied: int = 0


@dataclass(frozen=True)
class LongTermStats:
    average_reviews_per_active_day: int = 0
    active_days_percent: int = 0
    longest_streak: int = 0
    current_streak: int = 0


@dataclass(frozen=True)
class VerseContent:
    body_html: str = ""
    reference_html: str = ""


@dataclass(frozen=True)
class DashboardSnapshot:
    today: TodayStats = field(default_factory=TodayStats)
    queue: QueueStats = field(default_factory=QueueStats)
    buried: BuriedStats = field(default_factory=BuriedStats)
    events: List[EventItem] = field(default_factory=list)
    activity: List[DailyActivity] = field(default_factory=list)
    long_term: LongTermStats = field(default_factory=LongTermStats)
    verse: VerseContent = field(default_factory=VerseContent)
    generated_at: str = ""
    scheduling_date: str = ""
    day_cutoff_iso: str = ""
    errors: Dict[str, str] = field(default_factory=dict)
