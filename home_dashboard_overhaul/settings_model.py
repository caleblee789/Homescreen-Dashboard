"""Pure staged-settings state, routing, merge, and verse-import helpers.

This module deliberately has no Qt or Anki imports so its data-loss and
compatibility behavior can be exercised without starting the application.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Sequence, Tuple

from .config_schema import default_config, normalize_config
from .models import DashboardSnapshot, EventItem, ValueState
from .verse import verse_within_limit


Path = Tuple[str, ...]
_MISSING = object()

HISTORY_RANGE_ALL = "all"
HISTORY_RANGE_90 = "90"
HISTORY_RANGE_180 = "180"
HISTORY_RANGE_365 = "365"
HISTORY_RANGE_CUSTOM = "custom"
HISTORY_RANGE_VALUES = (
    HISTORY_RANGE_ALL,
    HISTORY_RANGE_90,
    HISTORY_RANGE_180,
    HISTORY_RANGE_365,
    HISTORY_RANGE_CUSTOM,
)


def history_range_choice(history_days: object, ignore_before: object) -> str:
    """Project the persisted range fields into the compact Settings choice."""

    if isinstance(ignore_before, str) and ignore_before.strip():
        return HISTORY_RANGE_CUSTOM
    try:
        days = int(history_days)
    except (TypeError, ValueError, OverflowError):
        days = 0
    return str(days) if days in {90, 180, 365} else HISTORY_RANGE_ALL


def history_range_values(choice: object, custom_start: object) -> Tuple[int, str]:
    """Return canonical ``history_days`` and ``ignore_before`` values."""

    selected = str(choice or "")
    if selected in {HISTORY_RANGE_90, HISTORY_RANGE_180, HISTORY_RANGE_365}:
        return int(selected), ""
    if selected == HISTORY_RANGE_CUSTOM:
        try:
            return 0, date.fromisoformat(str(custom_start)).isoformat()
        except (TypeError, ValueError):
            return 0, ""
    return 0, ""


def clamp_window_size(
    saved: object,
    available: Sequence[int],
    *,
    default: Tuple[int, int] = (1200, 800),
    minimum: Tuple[int, int] = (1040, 700),
    margin: int = 32,
) -> Tuple[int, int]:
    """Clamp a remembered Qt size to the screen without inventing a UI mode."""

    try:
        available_width, available_height = (int(available[0]), int(available[1]))
    except (TypeError, ValueError, IndexError):
        available_width, available_height = default
    maximum_width = max(1, available_width - max(0, int(margin)))
    maximum_height = max(1, available_height - max(0, int(margin)))
    try:
        saved_width, saved_height = (int(saved[0]), int(saved[1]))  # type: ignore[index]
    except (TypeError, ValueError, IndexError):
        saved_width, saved_height = default
    minimum_width = min(minimum[0], maximum_width)
    minimum_height = min(minimum[1], maximum_height)
    return (
        min(maximum_width, max(minimum_width, saved_width)),
        min(maximum_height, max(minimum_height, saved_height)),
    )


SECTION_IDS = (
    "dashboard",
    "events",
    "bible_verse",
    "about_support",
)

SECTION_LABELS = {
    "dashboard": "Dashboard",
    "events": "Events",
    "bible_verse": "Bible verse",
    "about_support": "About & support",
}

SECTION_GROUPS = {
    section_id: "" for section_id in SECTION_IDS
}

_SECTION_TARGETS = {
    "": ("dashboard", "appearance"),
    "appearance": ("dashboard", "appearance"),
    "theme": ("dashboard", "appearance"),
    "theme & layout": ("dashboard", "appearance"),
    "theme_layout": ("dashboard", "appearance"),
    "dashboard": ("dashboard", ""),
    "home": ("dashboard", "dashboard_sections"),
    "home screen": ("dashboard", "dashboard_sections"),
    "home_screen": ("dashboard", "dashboard_sections"),
    "activity": ("dashboard", "calendar"),
    "calendar": ("dashboard", "calendar"),
    "calendar & data": ("dashboard", "calendar"),
    "calendar_data": ("dashboard", "calendar"),
    "event": ("events", ""),
    "events": ("events", ""),
    "bible": ("bible_verse", ""),
    "bible verse": ("bible_verse", ""),
    "bible_verse": ("bible_verse", ""),
    "about": ("about_support", ""),
    "about & credits": ("about_support", ""),
    "about & support": ("about_support", ""),
    "about_support": ("about_support", ""),
}


def resolve_section(value: object) -> str:
    """Return a stable settings section ID while retaining legacy routes."""
    return resolve_section_target(value)[0]


def resolve_section_target(value: object) -> Tuple[str, str]:
    """Return the four-page route and an optional Dashboard card anchor."""
    key = str(value or "").strip().casefold()
    return _SECTION_TARGETS.get(key, ("dashboard", ""))


def font_family_value(staged: object, selected: object, explicitly_changed: bool) -> str:
    """Keep an unavailable saved family until the user changes the control."""
    staged_value = str(staged or "").strip()
    selected_value = str(selected or "").strip()
    if explicitly_changed and selected_value:
        return selected_value
    return staged_value or selected_value


def preview_snapshot_with_staged_events(
    snapshot: DashboardSnapshot,
    config: Mapping[str, Any],
    reference_date: str,
) -> DashboardSnapshot:
    """Overlay staged local events without reading or replacing study data.

    Settings previews are allowed to reflect unsaved appearance and event edits,
    but collection-backed values remain the controller's saved snapshot.  The
    returned snapshot updates only the canonical facts used by every renderer.
    """

    try:
        today = date.fromisoformat(reference_date)
    except (TypeError, ValueError):
        raise ValueError("reference_date must be an ISO civil date")

    event_config = config.get("events", {})
    if not isinstance(event_config, Mapping):
        event_config = {}
    staged: list[EventItem] = []
    raw_items = event_config.get("items", [])
    if isinstance(raw_items, Sequence) and not isinstance(raw_items, (str, bytes)):
        for raw in raw_items:
            if not isinstance(raw, Mapping) or raw.get("archived"):
                continue
            try:
                event_date = date.fromisoformat(str(raw["date"]))
                event_id = str(raw["id"])
                name = str(raw["name"])
            except (KeyError, TypeError, ValueError):
                continue
            staged.append(
                EventItem(
                    event_id=event_id,
                    name=name,
                    date=event_date.isoformat(),
                    days_remaining=(event_date - today).days,
                )
            )
    order = event_config.get("sort")
    staged.sort(
        key=(
            (lambda item: (item.name.casefold(), item.date, item.event_id))
            if order == "name"
            else (lambda item: (item.date, item.name.casefold(), item.event_id))
        ),
        reverse=order == "descending",
    )
    event_items = tuple(staged)
    event_state = ValueState.available(event_items)
    facts_with_events = replace(snapshot.facts, events=event_state)
    dates = set(snapshot.facts.days)
    dates.update(item.date for item in event_items)
    days = {}
    for iso_date in dates:
        day = snapshot.facts.days.get(iso_date) or facts_with_events.for_date(iso_date)
        day_events = tuple(item for item in event_items if item.date == iso_date)
        days[iso_date] = replace(day, events=ValueState.available(day_events))
    facts = replace(facts_with_events, days=days)
    return replace(snapshot, facts=facts)


def _leaf_values(value: object, prefix: Path = ()) -> Dict[Path, object]:
    """Flatten mappings while treating ordered collections as atomic values."""
    if isinstance(value, Mapping):
        if not value:
            return {prefix: {}}
        flattened: Dict[Path, object] = {}
        for key, child in value.items():
            flattened.update(_leaf_values(child, prefix + (str(key),)))
        return flattened
    return {prefix: deepcopy(value)}


def changed_paths(left: Mapping[str, Any], right: Mapping[str, Any]) -> frozenset[Path]:
    left_values = _leaf_values(left)
    right_values = _leaf_values(right)
    paths = set(left_values) | set(right_values)
    return frozenset(
        path
        for path in paths
        if left_values.get(path, _MISSING) != right_values.get(path, _MISSING)
    )


def path_label(path: Sequence[str]) -> str:
    return " › ".join(str(part).replace("_", " ").title() for part in path)


def _assign_path(target: MutableMapping[str, Any], path: Path, value: object) -> None:
    if not path:
        return
    cursor: MutableMapping[str, Any] = target
    for part in path[:-1]:
        child = cursor.get(part)
        if not isinstance(child, MutableMapping):
            child = {}
            cursor[part] = child
        cursor = child
    if value is _MISSING:
        cursor.pop(path[-1], None)
    else:
        cursor[path[-1]] = deepcopy(value)


@dataclass(frozen=True)
class MergeConflict:
    path: Path
    baseline: object
    staged: object
    latest: object

    @property
    def label(self) -> str:
        return path_label(self.path)


@dataclass(frozen=True)
class MergeResult:
    values: Dict[str, Any]
    conflicts: Tuple[MergeConflict, ...]


def three_way_merge(
    baseline: Mapping[str, Any],
    staged: Mapping[str, Any],
    latest: Mapping[str, Any],
) -> MergeResult:
    """Merge untouched latest paths and retain local values for conflicts.

    Lists (including events, verses, and excluded deck IDs) are atomic so a
    concurrent edit can never be silently interleaved or partially discarded.
    Unknown future keys participate in the same merge and remain intact.
    """
    base_values = _leaf_values(baseline)
    staged_values = _leaf_values(staged)
    latest_values = _leaf_values(latest)
    paths = set(base_values) | set(staged_values) | set(latest_values)
    merged: Dict[str, Any] = {}
    conflicts = []
    for path in sorted(paths):
        base_value = base_values.get(path, _MISSING)
        staged_value = staged_values.get(path, _MISSING)
        latest_value = latest_values.get(path, _MISSING)
        local_changed = staged_value != base_value
        external_changed = latest_value != base_value
        if local_changed and external_changed and staged_value != latest_value:
            conflicts.append(
                MergeConflict(
                    path,
                    deepcopy(base_value),
                    deepcopy(staged_value),
                    deepcopy(latest_value),
                )
            )
            selected = staged_value
        elif local_changed:
            selected = staged_value
        else:
            selected = latest_value
        _assign_path(merged, path, selected)
    return MergeResult(merged, tuple(conflicts))


_RESET_DEFAULT_PATHS = {
    "appearance": (("appearance",), ("home_screen",)),
    "dashboard_sections": (("visibility",), ("study",), ("new_cards",)),
    "home_screen_legacy": (
        ("visibility",),
        ("study",),
        ("new_cards",),
        ("home_screen",),
    ),
    "calendar": (("heatmap",),),
    "dashboard": (
        ("appearance",),
        ("home_screen",),
        ("visibility",),
        ("study",),
        ("new_cards",),
        ("heatmap",),
    ),
    "bible_appearance": (
        ("bible", "font_family"),
        ("bible", "font_size"),
        ("bible", "font_color"),
        ("bible", "theme_aware_color"),
    ),
    "bible_rotation": (
        ("bible", "rotation_mode"),
    ),
    "bible_verse": (
        ("bible", "font_family"),
        ("bible", "font_size"),
        ("bible", "font_color"),
        ("bible", "theme_aware_color"),
        ("bible", "rotation_mode"),
    ),
}


class SettingsDraft:
    """Normalized baseline plus staged values and reversible operations."""

    def __init__(self, baseline: Mapping[str, Any]) -> None:
        self.defaults = normalize_config(default_config())
        self.baseline = normalize_config(deepcopy(dict(baseline)))
        self.values = deepcopy(self.baseline)

    @property
    def dirty(self) -> bool:
        return bool(self.changed_paths)

    @property
    def changed_paths(self) -> frozenset[Path]:
        return changed_paths(self.baseline, self.values)

    @property
    def changed_leaf_count(self) -> int:
        """Count changed persisted leaves; managed lists remain one leaf each."""
        return len(self.changed_paths)

    @property
    def dependency_state(self) -> Dict[str, bool]:
        visibility = self.values["visibility"]
        return {
            "visibility.events": bool(visibility["heatmap"]),
            "heatmap.forecast_days": bool(self.values["heatmap"]["show_due_forecast"]),
            "bible.font_color": not bool(self.values["bible"]["theme_aware_color"]),
        }

    def replace_values(self, values: Mapping[str, Any]) -> None:
        self.values = normalize_config(deepcopy(dict(values)))

    def replace_all(self, latest: Mapping[str, Any]) -> None:
        self.baseline = normalize_config(deepcopy(dict(latest)))
        self.values = deepcopy(self.baseline)

    def reset_section(self, section: object) -> bool:
        """Compatibility reset for old callers; new UI uses ``reset_card``."""
        key = str(section or "").strip().casefold()
        legacy_scope = {
            "appearance": "appearance",
            "theme": "appearance",
            "theme & layout": "appearance",
            "theme_layout": "appearance",
            "home": "home_screen_legacy",
            "home screen": "home_screen_legacy",
            "home_screen": "home_screen_legacy",
            "activity": "calendar",
            "calendar": "calendar",
            "calendar & data": "calendar",
            "calendar_data": "calendar",
            "bible": "bible_verse",
            "bible verse": "bible_verse",
            "bible_verse": "bible_verse",
        }.get(key, resolve_section(section))
        return self.reset_card(legacy_scope)

    def reset_card(self, scope: object) -> bool:
        """Restore one card's fields without touching managed content lists."""
        paths = _RESET_DEFAULT_PATHS.get(str(scope or "").strip().casefold())
        if not paths:
            return False
        for path in paths:
            source: object = self.defaults
            for part in path:
                source = source[part]  # type: ignore[index]
            _assign_path(self.values, path, source)
        self.values = normalize_config(self.values)
        return True

    def rebase(self, latest: Mapping[str, Any]) -> Tuple[MergeConflict, ...]:
        normalized_latest = normalize_config(deepcopy(dict(latest)))
        result = three_way_merge(self.baseline, self.values, normalized_latest)
        self.baseline = normalized_latest
        self.values = normalize_config(result.values)
        return result.conflicts


@dataclass(frozen=True)
class VerseImportSummary:
    imported: int
    duplicates: int
    limited: int
    empty: int
    oversized: int

    @property
    def skipped(self) -> int:
        return self.duplicates + self.limited + self.empty + self.oversized


def import_quotes(
    existing: Iterable[object],
    candidates: Iterable[object],
    limit: int = 500,
) -> tuple[list[str], VerseImportSummary]:
    """Trim candidates, skip exact duplicates, and enforce the library cap."""
    result = [value.strip() for value in existing if isinstance(value, str) and value.strip()]
    result = result[: max(0, limit)]
    known = set(result)
    imported = duplicates = limited = empty = oversized = 0
    for raw in candidates:
        if not isinstance(raw, str) or not raw.strip():
            empty += 1
            continue
        value = raw.strip()
        if not verse_within_limit(value):
            oversized += 1
            continue
        if value in known:
            duplicates += 1
            continue
        if len(result) >= limit:
            limited += 1
            continue
        result.append(value)
        known.add(value)
        imported += 1
    return result, VerseImportSummary(imported, duplicates, limited, empty, oversized)
