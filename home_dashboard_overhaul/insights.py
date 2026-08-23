"""Lazy, exact selected-day Most missed card-set calculation.

The dashboard never renders card fronts, answers, deck previews, or due-deck
breakdowns. This module exists only to resolve the optional Browser target for
a selected historical/current date. The primary Reviewed/Due action remains
owned by ``DayFacts.browse_target`` from the canonical dashboard query.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any, List, Mapping

from .analytics import _history_conditions_for_day, collect_day_facts
from .models import (
    AvailabilityReason,
    BrowseTarget,
    BrowseTargetKind,
    DayDomainState,
    DayFacts,
    DayInsight,
    DayRelation,
    ValueState,
)


def _history_insight(
    col: Any,
    config: Mapping[str, Any],
    facts: DayFacts,
) -> DayFacts:
    """Attach one exact, deterministically ranked Most missed target."""

    del config
    if (
        facts.relation == DayRelation.FUTURE
        or not facts.again_count.is_available
        or int(facts.again_count.value) <= 0
    ):
        return replace(facts, most_missed_target=BrowseTarget())

    conditions, args = _history_conditions_for_day(
        col,
        facts.filter_scope,
        date.fromisoformat(facts.date),
    )
    rows = col.db.all(
        "SELECT r.cid, "
        "coalesce(sum(CASE WHEN r.ease = 1 THEN 1 ELSE 0 END), 0) AS again_count, "
        "count(*) AS total_answers "
        "FROM revlog r JOIN cards c ON c.id = r.cid "
        "WHERE {} GROUP BY r.cid HAVING again_count > 0 "
        "ORDER BY again_count DESC, total_answers DESC, r.cid ASC".format(
            " AND ".join(conditions),
        ),
        *args,
    ) or []
    ranked_ids: List[int] = []
    seen = set()
    for row in rows:
        try:
            card_id = int(row[0])
        except (TypeError, ValueError, OverflowError, IndexError):
            continue
        if card_id <= 0 or card_id in seen:
            continue
        seen.add(card_id)
        ranked_ids.append(card_id)

    target_ids = tuple(ranked_ids)
    target = (
        BrowseTarget(
            kind=BrowseTargetKind.MOST_MISSED,
            query="cid:{}".format(",".join(str(card_id) for card_id in target_ids)),
            exact=True,
            card_ids=target_ids,
        )
        if target_ids
        else BrowseTarget()
    )
    domain_state = facts.domain_state
    if not target_ids and facts.domain_state == DayDomainState.TROUBLE:
        # Revlog can retain misses for cards that have since been deleted.
        domain_state = DayDomainState.DELETED_MISSES
    return replace(
        facts,
        domain_state=domain_state,
        most_missed_target=target,
    )


def enrich_day_facts(
    col: Any,
    config: Mapping[str, Any],
    facts: DayFacts,
) -> DayFacts:
    """Resolve only the optional Most missed Browser target."""

    return _history_insight(col, config, facts)


def project_day_insight(facts: DayFacts) -> DayInsight:
    """Project the callback envelope without preview content."""
    target = facts.most_missed_target
    return DayInsight(
        date=facts.date,
        browse_target=target,
        day_facts=facts,
    )


def unavailable_day_insight(selected_date: date, scheduling_date: date) -> DayInsight:
    """Build a typed lazy-query failure for controller callbacks."""

    failed = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)
    facts = DayFacts(
        date=selected_date.isoformat(),
        scheduling_date=scheduling_date.isoformat(),
        relation=(
            DayRelation.PAST
            if selected_date < scheduling_date
            else DayRelation.FUTURE
            if selected_date > scheduling_date
            else DayRelation.CURRENT
        ),
        reviews_completed=failed,
        new_cards_studied=failed,
        reviews_due=failed,
        again_count=failed,
        events=failed,
        domain_state=DayDomainState.UNAVAILABLE,
    )
    return project_day_insight(facts)


def collect_day_insight(
    col: Any,
    config: Mapping[str, Any],
    selected_date: date,
    scheduling_date: date,
    calendar_today: date,
    day_facts: DayFacts | None = None,
) -> DayInsight:
    """Collect and rank an exact Most missed set for one selected date."""

    try:
        facts = day_facts or collect_day_facts(
            col,
            config,
            selected_date,
            scheduling_date,
            calendar_today,
        )
        return project_day_insight(enrich_day_facts(col, config, facts))
    except Exception:
        return unavailable_day_insight(selected_date, scheduling_date)
