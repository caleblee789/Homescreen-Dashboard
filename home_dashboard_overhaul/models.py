"""Typed, UI-independent dashboard data models.

``DashboardFacts`` is the sole source of collection-backed dashboard values.
Consumers must use ``ValueState`` instead of interpreting a missing value or a
numeric default as availability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Mapping, Optional, Tuple, TypeVar


T = TypeVar("T")


class ValueStatus(str, Enum):
    """Whether a value is ready, pending, or unavailable."""

    LOADING = "loading"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class AvailabilityReason(str, Enum):
    """Stable unavailability reasons; domain/empty states live on DayFacts."""

    NONE = ""
    QUERY_FAILED = "query_failed"
    HISTORY_OUT_OF_RANGE = "history_out_of_range"
    FORECAST_DISABLED = "forecast_disabled"
    FORECAST_OUT_OF_RANGE = "forecast_out_of_range"


class RateStatus(str, Enum):
    """Whether a percentage has a real graded-answer denominator."""

    AVAILABLE = "available"
    NO_ACTIVITY = "no_activity"


@dataclass(frozen=True)
class RateMetric:
    """A percentage that cannot confuse no activity with a measured zero.

    ``0%`` is a valid available measurement. ``NO_ACTIVITY`` carries no
    percentage because its denominator is zero.
    """

    status: RateStatus = RateStatus.NO_ACTIVITY
    percent: Optional[int] = None
    numerator: int = 0
    denominator: int = 0

    def __post_init__(self) -> None:
        numerator = int(self.numerator)
        denominator = int(self.denominator)
        if numerator < 0 or denominator < 0 or numerator > denominator:
            raise ValueError("rate counts must satisfy 0 <= numerator <= denominator")
        if self.status == RateStatus.NO_ACTIVITY:
            if denominator != 0 or numerator != 0 or self.percent is not None:
                raise ValueError("a no-activity rate cannot carry counts or a percentage")
            return
        if denominator <= 0 or self.percent is None:
            raise ValueError("an available rate requires a positive denominator and percentage")
        if not 0 <= int(self.percent) <= 100:
            raise ValueError("rate percentage must be between zero and one hundred")
        expected = (numerator * 100 + denominator // 2) // denominator
        if int(self.percent) != expected:
            raise ValueError("rate percentage must match its counts")

    @classmethod
    def from_counts(cls, numerator: int, denominator: int) -> "RateMetric":
        resolved_denominator = int(denominator)
        resolved_numerator = int(numerator)
        if (
            resolved_denominator < 0
            or resolved_numerator < 0
            or resolved_numerator > resolved_denominator
        ):
            raise ValueError("rate counts must satisfy 0 <= numerator <= denominator")
        if resolved_denominator == 0:
            return cls()
        percent = min(
            100,
            max(0, (resolved_numerator * 100 + resolved_denominator // 2) // resolved_denominator),
        )
        return cls(
            status=RateStatus.AVAILABLE,
            percent=percent,
            numerator=resolved_numerator,
            denominator=resolved_denominator,
        )


@dataclass(frozen=True)
class ValueState(Generic[T]):
    """A typed value whose availability never depends on truthiness.

    ``available(0)`` is intentionally different from ``unavailable(...)``.
    Available values never carry a reason. Empty/deleted/no-due meanings are
    represented by ``DayDomainState`` instead of being smuggled through the
    availability channel.
    """

    status: ValueStatus
    value: Optional[T] = None
    reason: AvailabilityReason = AvailabilityReason.NONE

    def __post_init__(self) -> None:
        if self.status == ValueStatus.AVAILABLE and self.value is None:
            raise ValueError("an available ValueState requires a value")
        if self.status != ValueStatus.AVAILABLE and self.value is not None:
            raise ValueError("a non-available ValueState cannot carry a value")
        if self.status == ValueStatus.AVAILABLE and self.reason != AvailabilityReason.NONE:
            raise ValueError("an available ValueState cannot carry an unavailability reason")
        if self.status == ValueStatus.LOADING and self.reason != AvailabilityReason.NONE:
            raise ValueError("a loading ValueState cannot carry an availability reason")
        if self.status == ValueStatus.UNAVAILABLE and self.reason == AvailabilityReason.NONE:
            raise ValueError("an unavailable ValueState requires a reason")

    @classmethod
    def available(cls, value: T) -> "ValueState[T]":
        return cls(ValueStatus.AVAILABLE, value)

    @classmethod
    def loading(cls) -> "ValueState[T]":
        return cls(ValueStatus.LOADING)

    @classmethod
    def unavailable(cls, reason: AvailabilityReason) -> "ValueState[T]":
        if reason == AvailabilityReason.NONE:
            raise ValueError("an unavailable ValueState requires a reason")
        return cls(ValueStatus.UNAVAILABLE, reason=reason)

    @property
    def is_available(self) -> bool:
        return self.status == ValueStatus.AVAILABLE


class DayRelation(str, Enum):
    PAST = "past"
    CURRENT = "current"
    FUTURE = "future"


class BrowseTargetKind(str, Enum):
    NONE = "none"
    REVIEWED = "reviewed"
    DUE = "due"
    MOST_MISSED = "most_missed"
    # Stable aliases retained for native cache compatibility during migration.
    TODAY = "reviewed"
    DAY = "reviewed"
    TROUBLE_CARDS = "most_missed"
    FUTURE_DUE = "due"


class DayDomainState(str, Enum):
    """Selected-date content state derived from the same canonical facts."""

    LOADING = "loading"
    UNAVAILABLE = "unavailable"
    TROUBLE = "trouble"
    NO_AGAIN = "no_again"
    DELETED_MISSES = "deleted_misses"
    NO_HISTORICAL_ACTIVITY = "no_historical_activity"
    FUTURE_DUE = "future_due"
    NO_DUE = "no_due"


@dataclass(frozen=True)
class FilterScope:
    """Resolved filters shared by every collection-backed dashboard consumer."""

    excluded_deck_ids: Tuple[int, ...] = ()
    exclude_manual_reschedules: bool = True
    exclude_deleted_cards: bool = False
    include_rescheduled_new_cards: bool = True
    ignore_before: str = ""


@dataclass(frozen=True)
class BrowseTarget:
    """Controller-owned Browser intent.

    ``exact`` is false when Anki's search language cannot fully express the
    canonical filter scope (for example, manual-reschedule filtering).
    """

    kind: BrowseTargetKind = BrowseTargetKind.NONE
    query: str = ""
    exact: bool = False
    card_ids: Tuple[int, ...] = ()


@dataclass(frozen=True)
class DateCoverage:
    """Inclusive ISO-date coverage; a blank bound is intentionally open."""

    start: str = ""
    end: str = ""

    def contains(self, iso_date: str) -> bool:
        return (not self.start or iso_date >= self.start) and (not self.end or iso_date <= self.end)


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

    def __post_init__(self) -> None:
        categories = (int(self.new), int(self.learning), int(self.review))
        total = int(self.total)
        if any(value < 0 for value in categories) or total < 0:
            raise ValueError("queue counts cannot be negative")
        if total != sum(categories):
            raise ValueError("queue total must equal new + learning + review")
        if self.estimated_duration_seconds is not None and int(self.estimated_duration_seconds) < 0:
            raise ValueError("queue estimate cannot be negative")


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
class LongTermStats:
    average_reviews_per_active_day: int = 0
    active_days_percent: int = 0
    longest_streak: int = 0
    current_streak: int = 0
    lifetime_retention: RateMetric = field(default_factory=RateMetric)
    lifetime_cards_studied: int = 0


@dataclass(frozen=True)
class LastSevenDaysStats:
    cards_studied: int = 0
    new_cards_studied: int = 0
    seconds: float = 0.0
    retention: RateMetric = field(default_factory=RateMetric)
    again_rate: RateMetric = field(default_factory=RateMetric)


@dataclass(frozen=True)
class VerseContent:
    body_html: str = ""
    reference_html: str = ""


def _loading_int() -> ValueState[int]:
    return ValueState.loading()


def _available_events() -> ValueState[Tuple[EventItem, ...]]:
    return ValueState.available(())


@dataclass(frozen=True)
class DayFacts:
    """Canonical facts for one Anki scheduling date."""

    date: str = ""
    scheduling_date: str = ""
    relation: DayRelation = DayRelation.CURRENT
    reviews_completed: ValueState[int] = field(default_factory=_loading_int)
    new_cards_studied: ValueState[int] = field(default_factory=_loading_int)
    reviews_due: ValueState[int] = field(default_factory=_loading_int)
    again_count: ValueState[int] = field(default_factory=_loading_int)
    events: ValueState[Tuple[EventItem, ...]] = field(default_factory=_available_events)
    browse_target: BrowseTarget = field(default_factory=BrowseTarget)
    most_missed_target: BrowseTarget = field(default_factory=BrowseTarget)
    filter_scope: FilterScope = field(default_factory=FilterScope)
    domain_state: DayDomainState = DayDomainState.LOADING

    @property
    def scheduled_due(self) -> ValueState[int]:
        """Explicit alias for the scheduler-date due metric."""
        return self.reviews_due


@dataclass(frozen=True)
class DayInsight:
    """Capability-only result for a lazily resolved Most-missed action."""

    date: str = ""
    browse_target: BrowseTarget = field(default_factory=BrowseTarget)
    day_facts: Optional[DayFacts] = None


@dataclass(frozen=True)
class DashboardFacts:
    """One authoritative dashboard result with explicit data-domain scopes.

    ``days`` contains every date in the collector's declared history and
    forecast coverage, plus any explicitly materialized event dates.  A
    missing key is therefore a schema failure, never evidence that the date
    contains numeric zeroes. ``filter_scope`` applies to every collection-backed
    fact in this result.
    """

    scheduling_date: str = ""
    calendar_date: str = ""
    revision: str = ""
    next_rollover: str = ""
    filter_scope: FilterScope = field(default_factory=FilterScope)
    today: ValueState[TodayStats] = field(default_factory=ValueState.loading)
    queue: ValueState[QueueStats] = field(default_factory=ValueState.loading)
    buried: ValueState[BuriedStats] = field(default_factory=ValueState.loading)
    events: ValueState[Tuple[EventItem, ...]] = field(default_factory=ValueState.loading)
    last_seven_days: ValueState[LastSevenDaysStats] = field(default_factory=ValueState.loading)
    long_term: ValueState[LongTermStats] = field(default_factory=ValueState.loading)
    history_coverage: ValueState[DateCoverage] = field(default_factory=ValueState.loading)
    forecast_coverage: ValueState[DateCoverage] = field(default_factory=ValueState.loading)
    due_load_reference: float = 0.0
    days: Mapping[str, DayFacts] = field(default_factory=dict)

    @classmethod
    def unavailable(
        cls,
        scheduling_date: str = "",
        calendar_date: str = "",
        revision: str = "",
        next_rollover: str = "",
        scope: Optional[FilterScope] = None,
    ) -> "DashboardFacts":
        failed = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)
        return cls(
            scheduling_date=scheduling_date,
            calendar_date=calendar_date,
            revision=revision,
            next_rollover=next_rollover,
            filter_scope=scope or FilterScope(),
            today=failed,
            queue=failed,
            buried=failed,
            events=failed,
            last_seven_days=failed,
            long_term=failed,
            history_coverage=failed,
            forecast_coverage=failed,
        )

    def for_date(self, iso_date: str) -> DayFacts:
        """Return an explicit date record or a typed schema-failure record."""
        existing = self.days.get(iso_date)
        if existing is not None:
            return existing

        relation = (
            DayRelation.PAST
            if iso_date < self.scheduling_date
            else DayRelation.FUTURE
            if iso_date > self.scheduling_date
            else DayRelation.CURRENT
        )
        failed = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)

        return DayFacts(
            date=iso_date,
            scheduling_date=self.scheduling_date,
            relation=relation,
            reviews_completed=failed,
            new_cards_studied=failed,
            reviews_due=failed,
            again_count=failed,
            events=failed,
            browse_target=BrowseTarget(),
            filter_scope=self.filter_scope,
            domain_state=DayDomainState.UNAVAILABLE,
        )

    def day(self, iso_date: str) -> DayFacts:
        """Backward-compatible alias for ``for_date``."""
        return self.for_date(iso_date)


@dataclass(frozen=True)
class DashboardSnapshot:
    facts: DashboardFacts = field(default_factory=DashboardFacts)
    verse: VerseContent = field(default_factory=VerseContent)
