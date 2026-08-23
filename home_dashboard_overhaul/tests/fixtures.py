"""Canonical test fixtures for the corrected compact dashboard."""

from __future__ import annotations

from datetime import date, timedelta

from home_dashboard_overhaul.models import (
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
    LastSevenDaysStats,
    LongTermStats,
    QueueStats,
    RateMetric,
    TodayStats,
    ValueState,
    VerseContent,
)


def sample_snapshot(today: date | None = None) -> DashboardSnapshot:
    scheduling_day = today or date(2026, 8, 17)
    event_day = scheduling_day + timedelta(days=11)
    event = EventItem(
        "fixture-event",
        "Pediatric NBME",
        event_day.isoformat(),
        11,
    )
    days: dict[str, DayFacts] = {}
    positive_forecast: list[int] = []

    for offset in range(-21, 91):
        current = scheduling_day + timedelta(days=offset)
        iso = current.isoformat()
        relation = (
            DayRelation.PAST if offset < 0 else
            DayRelation.FUTURE if offset > 0 else
            DayRelation.CURRENT
        )
        completed = 0 if offset > 0 else max(0, 567 - abs(offset) * 19)
        new_cards = 0 if offset > 0 else max(0, 12 - abs(offset) // 3)
        again = 0 if offset > 0 else max(0, 17 - abs(offset))
        due = 0 if offset < 0 else (0 if offset % 9 == 0 else 28 + (offset * 17) % 127)
        if due > 0:
            positive_forecast.append(due)

        if offset <= 0:
            completed_state = ValueState.available(completed)
            new_state = ValueState.available(new_cards)
            again_state = ValueState.available(again)
        else:
            completed_state = ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE)
            new_state = ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE)
            again_state = ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE)
        due_state = (
            ValueState.available(due)
            if offset >= 0
            else ValueState.unavailable(AvailabilityReason.FORECAST_OUT_OF_RANGE)
        )

        reviewed_ids = tuple(range(100_000 + (offset + 21) * 10, 100_000 + (offset + 21) * 10 + 3))
        due_ids = tuple(range(200_000 + offset * 10, 200_000 + offset * 10 + min(due, 3))) if due else ()
        if completed > 0:
            primary_target = BrowseTarget(
                BrowseTargetKind.REVIEWED,
                "cid:{}".format(",".join(str(card_id) for card_id in reviewed_ids)),
                True,
                reviewed_ids,
            )
            domain = DayDomainState.TROUBLE if again else DayDomainState.NO_AGAIN
        elif due > 0:
            primary_target = BrowseTarget(
                BrowseTargetKind.DUE,
                "cid:{}".format(",".join(str(card_id) for card_id in due_ids)),
                True,
                due_ids,
            )
            domain = DayDomainState.FUTURE_DUE
        else:
            primary_target = BrowseTarget()
            domain = (
                DayDomainState.NO_HISTORICAL_ACTIVITY
                if offset <= 0 else DayDomainState.NO_DUE
            )

        most_missed = BrowseTarget()
        if offset == 0:
            ranked_ids = (100_002, 100_001, 100_003)
            most_missed = BrowseTarget(
                BrowseTargetKind.MOST_MISSED,
                "cid:{}".format(",".join(str(card_id) for card_id in ranked_ids)),
                True,
                ranked_ids,
            )

        day_events = (event,) if current == event_day else ()
        days[iso] = DayFacts(
            date=iso,
            scheduling_date=scheduling_day.isoformat(),
            relation=relation,
            reviews_completed=completed_state,
            new_cards_studied=new_state,
            reviews_due=due_state,
            again_count=again_state,
            events=ValueState.available(day_events),
            browse_target=primary_target,
            most_missed_target=most_missed,
            domain_state=domain,
        )

    positive_forecast.sort()
    reference = positive_forecast[max(0, min(len(positive_forecast) - 1, (len(positive_forecast) * 9 + 9) // 10 - 1))]
    facts = DashboardFacts(
        scheduling_date=scheduling_day.isoformat(),
        calendar_date=scheduling_day.isoformat(),
        revision="fixture-revision",
        next_rollover="{}T04:00:00-05:00".format((scheduling_day + timedelta(days=1)).isoformat()),
        today=ValueState.available(TodayStats(567, 12, 14_760, 26.03)),
        queue=ValueState.available(QueueStats(42, 18, 109, 169, 4_860)),
        buried=ValueState.available(BuriedStats(3, 2, 7)),
        events=ValueState.available((event,)),
        last_seven_days=ValueState.available(LastSevenDaysStats(
            cards_studied=1_754,
            new_cards_studied=312,
            retention=RateMetric.from_counts(1_368, 1_754),
            again_rate=RateMetric.from_counts(386, 1_754),
        )),
        long_term=ValueState.available(LongTermStats(
            average_reviews_per_active_day=428,
            active_days_percent=83,
            longest_streak=127,
            current_streak=42,
            lifetime_retention=RateMetric.from_counts(251_254, 322_120),
            lifetime_cards_studied=322_120,
        )),
        history_coverage=ValueState.available(DateCoverage("", scheduling_day.isoformat())),
        forecast_coverage=ValueState.available(DateCoverage(
            scheduling_day.isoformat(),
            (scheduling_day + timedelta(days=90)).isoformat(),
        )),
        due_load_reference=float(reference),
        days=days,
    )
    return DashboardSnapshot(
        facts=facts,
        verse=VerseContent(
            "For God has not given us a spirit of fear and timidity, but of power, love, and self-discipline.",
            "2 Timothy 1:7 (NLT)",
        ),
    )
