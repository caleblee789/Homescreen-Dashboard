"""Full scheduling-day trouble-card and future-due insight queries."""

from __future__ import annotations

from datetime import date
import html
import re
from typing import Any, List, Mapping, Sequence, Tuple

from .analytics import (
    REVLOG_MANUAL_RESCHEDULE,
    _excluded_deck_ids,
    _rollover_seconds,
    browser_search_for_day,
    history_start_date,
)
from .models import DayInsight, InsightItem


MAX_ITEMS = 3
MAX_PROMPT_CHARACTERS = 160
_SOUND_RE = re.compile(r"\[sound:[^\]]*\]", re.IGNORECASE)
_ANKI_PLAY_RE = re.compile(r"\[anki:play:[^\]]*\]", re.IGNORECASE)
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_MEDIA_BLOCK_RE = re.compile(
    r"<(audio|video|object|svg|math)\b[^>]*>.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_MEDIA_TAG_RE = re.compile(
    r"<(?:img|audio|video|source|object|embed|svg|math)\b[^>]*>",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _plain_text(value: object) -> str:
    source = str(value or "")
    source = _SCRIPT_STYLE_RE.sub(" ", source)
    source = _MEDIA_BLOCK_RE.sub(" ", source)
    source = _MEDIA_TAG_RE.sub(" ", source)
    source = _SOUND_RE.sub(" ", source)
    source = _ANKI_PLAY_RE.sub(" ", source)
    try:
        from anki.utils import strip_html_media  # type: ignore

        source = strip_html_media(source)
    except Exception:
        pass
    source = _SOUND_RE.sub(" ", source)
    source = _ANKI_PLAY_RE.sub(" ", source)
    source = _MEDIA_BLOCK_RE.sub(" ", source)
    source = _MEDIA_TAG_RE.sub(" ", source)
    source = _TAG_RE.sub(" ", source)
    source = html.unescape(source)
    return _WHITESPACE_RE.sub(" ", source).strip()


def _capped_prompt(value: object) -> str:
    prompt = _plain_text(value)
    if len(prompt) <= MAX_PROMPT_CHARACTERS:
        return prompt
    return prompt[: MAX_PROMPT_CHARACTERS - 1].rstrip() + "…"


def _card_prompt(card: Any, card_id: int) -> str:
    try:
        prompt = _capped_prompt(card.question())
    except Exception:
        prompt = ""
    if prompt:
        return prompt
    try:
        fields = getattr(card.note(), "fields", [])
    except Exception:
        fields = []
    for field in fields or []:
        prompt = _capped_prompt(field)
        if prompt:
            return prompt
    return "Media-only card {}".format(card_id)


def _deck_name(col: Any, deck_id: int) -> str:
    decks = getattr(col, "decks", None)
    name_if_exists = getattr(decks, "name_if_exists", None)
    if callable(name_if_exists):
        try:
            value = name_if_exists(deck_id)
            if value:
                return _plain_text(value)
        except Exception:
            pass
    get_deck = getattr(decks, "get", None)
    if callable(get_deck):
        try:
            value = get_deck(deck_id)
            if isinstance(value, Mapping) and value.get("name"):
                return _plain_text(value["name"])
        except Exception:
            pass
    return "Unknown deck"


def _card_deck_id(card: Any) -> int:
    current = getattr(card, "current_deck_id", None)
    if callable(current):
        try:
            return int(current())
        except (TypeError, ValueError, OverflowError):
            pass
    try:
        return int(getattr(card, "did", 0) or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _history_conditions(
    col: Any,
    config: Mapping[str, Any],
    study_date: date,
    join_cards: bool,
) -> Tuple[List[str], List[object], set[int]]:
    heatmap = config["heatmap"]
    excluded = _excluded_deck_ids(col, heatmap.get("excluded_deck_ids", []))
    rollover = _rollover_seconds(int(col.sched.day_cutoff))
    day_expression = "date(r.id / 1000, 'unixepoch', 'localtime', '-{} seconds')".format(rollover)
    conditions = ["{} = ?".format(day_expression), "r.ease > 0"]
    args: List[object] = [study_date.isoformat()]
    if heatmap.get("exclude_manual_reschedules", True):
        conditions.append("r.type != ?")
        args.append(REVLOG_MANUAL_RESCHEDULE)
    if join_cards and excluded:
        placeholders = ",".join("?" for _ in excluded)
        conditions.append("c.did NOT IN ({})".format(placeholders))
        args.extend(sorted(excluded))
    return conditions, args, excluded


def _append_excluded_decks(query: str, excluded: Sequence[int]) -> str:
    suffix = " ".join("-did:{}".format(deck_id) for deck_id in sorted(set(excluded)))
    return "{} {}".format(query, suffix).strip()


def _history_insight(
    col: Any,
    config: Mapping[str, Any],
    selected_date: date,
    study_date: date,
    scheduling_date: date,
    is_current: bool,
) -> DayInsight:
    visible_start = history_start_date(config, scheduling_date, True)
    if not is_current and visible_start is not None and study_date < visible_start:
        return DayInsight(
            date=selected_date.isoformat(),
            study_date=study_date.isoformat(),
            insight_kind="trouble_cards",
            empty_reason="history_out_of_range",
        )

    heatmap = config["heatmap"]
    excluded = _excluded_deck_ids(col, heatmap.get("excluded_deck_ids", []))
    count_join = bool(excluded or heatmap.get("exclude_deleted_cards"))
    count_conditions, count_args, _ = _history_conditions(
        col,
        config,
        study_date,
        count_join,
    )
    count_row = col.db.first(
        "SELECT count(*), coalesce(sum(CASE WHEN r.ease = 1 THEN 1 ELSE 0 END), 0) "
        "FROM revlog r {} WHERE {}".format(
            "JOIN cards c ON c.id = r.cid" if count_join else "",
            " AND ".join(count_conditions),
        ),
        *count_args,
    )
    answers = max(0, int(count_row[0] or 0)) if count_row else 0
    again_count = max(0, int(count_row[1] or 0)) if count_row and len(count_row) > 1 else 0
    base_query = _append_excluded_decks(
        browser_search_for_day(study_date, scheduling_date),
        sorted(excluded),
    )

    if answers == 0:
        return DayInsight(
            date=selected_date.isoformat(),
            study_date=study_date.isoformat(),
            valid_answer_count=0,
            again_count=0,
            insight_kind="trouble_cards",
            empty_reason="today_no_answers" if is_current else "past_no_answers",
            browse_action="today" if is_current else "none",
            browser_query=base_query if is_current else "",
        )
    if again_count == 0:
        return DayInsight(
            date=selected_date.isoformat(),
            study_date=study_date.isoformat(),
            valid_answer_count=answers,
            again_count=0,
            insight_kind="trouble_cards",
            empty_reason="no_again",
            browse_action="today" if is_current else "day",
            browser_query=base_query,
        )

    rank_conditions, rank_args, _ = _history_conditions(col, config, study_date, True)
    rank_conditions.append("r.ease = 1")
    rows = col.db.all(
        "SELECT r.cid, count(*), max(r.id) FROM revlog r "
        "JOIN cards c ON c.id = r.cid WHERE {} GROUP BY r.cid "
        "ORDER BY count(*) DESC, max(r.id) DESC, r.cid ASC LIMIT {}".format(
            " AND ".join(rank_conditions),
            MAX_ITEMS,
        ),
        *rank_args,
    ) or []
    items: List[InsightItem] = []
    card_ids: List[int] = []
    for raw_card_id, raw_count, _raw_latest in rows:
        try:
            card_id = int(raw_card_id)
            count = max(0, int(raw_count or 0))
            card = col.get_card(card_id)
        except Exception:
            continue
        items.append(
            InsightItem(
                primary_text=_card_prompt(card, card_id),
                secondary_text=_deck_name(col, _card_deck_id(card)),
                count=count,
                count_label="Again ×{}".format(count),
            )
        )
        card_ids.append(card_id)

    if not items:
        return DayInsight(
            date=selected_date.isoformat(),
            study_date=study_date.isoformat(),
            valid_answer_count=answers,
            again_count=again_count,
            insight_kind="trouble_cards",
            empty_reason="deleted_misses",
            browse_action="today" if is_current else "day",
            browser_query=base_query,
        )
    return DayInsight(
        date=selected_date.isoformat(),
        study_date=study_date.isoformat(),
        valid_answer_count=answers,
        again_count=again_count,
        insight_kind="trouble_cards",
        items=items,
        browse_action="trouble_cards",
        browser_query="cid:{}".format(",".join(str(card_id) for card_id in card_ids)),
    )


def _future_insight(
    col: Any,
    config: Mapping[str, Any],
    selected_date: date,
    scheduling_date: date,
) -> DayInsight:
    heatmap = config["heatmap"]
    forecast_days = max(0, int(heatmap.get("forecast_days", 0)))
    offset = (selected_date - scheduling_date).days
    if not heatmap.get("show_due_forecast", True) or forecast_days <= 0:
        return DayInsight(
            date=selected_date.isoformat(),
            study_date=selected_date.isoformat(),
            insight_kind="future_due_decks",
            empty_reason="forecast_disabled",
        )
    if offset < 0 or offset >= forecast_days:
        return DayInsight(
            date=selected_date.isoformat(),
            study_date=selected_date.isoformat(),
            insight_kind="future_due_decks",
            empty_reason="forecast_out_of_range",
        )

    excluded = _excluded_deck_ids(col, heatmap.get("excluded_deck_ids", []))
    conditions = ["queue IN (2, 3)", "due = ?"]
    args: List[object] = [int(getattr(col.sched, "today", 0)) + offset]
    if excluded:
        placeholders = ",".join("?" for _ in excluded)
        conditions.append("did NOT IN ({})".format(placeholders))
        args.extend(sorted(excluded))
    rows = col.db.all(
        "SELECT did, count(*) FROM cards WHERE {} GROUP BY did "
        "ORDER BY count(*) DESC, did ASC LIMIT {}".format(
            " AND ".join(conditions),
            MAX_ITEMS,
        ),
        *args,
    ) or []
    items = [
        InsightItem(
            primary_text=_deck_name(col, int(raw_deck_id)),
            count=max(0, int(raw_count or 0)),
            count_label="{} {} due".format(
                max(0, int(raw_count or 0)),
                "card" if int(raw_count or 0) == 1 else "cards",
            ),
        )
        for raw_deck_id, raw_count in rows
    ]
    if not items:
        return DayInsight(
            date=selected_date.isoformat(),
            study_date=selected_date.isoformat(),
            insight_kind="future_due_decks",
            empty_reason="no_due",
        )
    query = _append_excluded_decks("prop:due={}".format(offset), sorted(excluded))
    return DayInsight(
        date=selected_date.isoformat(),
        study_date=selected_date.isoformat(),
        insight_kind="future_due_decks",
        items=items,
        browse_action="future_due",
        browser_query=query,
    )


def collect_day_insight(
    col: Any,
    config: Mapping[str, Any],
    selected_date: date,
    scheduling_date: date,
    calendar_today: date,
) -> DayInsight:
    """Collect one selected civil date without allowing query failures to escape."""
    try:
        if selected_date > calendar_today:
            return _future_insight(col, config, selected_date, scheduling_date)
        study_date = scheduling_date if selected_date == calendar_today else selected_date
        return _history_insight(
            col,
            config,
            selected_date,
            study_date,
            scheduling_date,
            selected_date == calendar_today,
        )
    except Exception:
        return DayInsight(
            date=selected_date.isoformat(),
            study_date=(scheduling_date if selected_date == calendar_today else selected_date).isoformat(),
            insight_kind="unavailable",
            empty_reason="unavailable",
        )
