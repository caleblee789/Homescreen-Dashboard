"""Pure staged-settings state, routing, merge, and verse-import helpers.

This module deliberately has no Qt or Anki imports so its data-loss and
compatibility behavior can be exercised without starting the application.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Sequence, Tuple

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

SETTINGS_DEFAULT_SIZE = (1080, 760)
SETTINGS_MINIMUM_SIZE = (860, 640)
SETTINGS_NORMAL_SCREEN_MARGIN = 48
SETTINGS_SMALL_SCREEN_MARGIN = 24
SETTINGS_MINIMUM_VISIBLE_RATIO = .80
SETTINGS_GEOMETRY_VERSION = 4
SETTINGS_PREVIOUS_GEOMETRY_VERSION = 3


def _effective_axis_margin(
    available: int,
    minimum: int,
    normal_margin: int = SETTINGS_NORMAL_SCREEN_MARGIN,
    small_screen_margin: int = SETTINGS_SMALL_SCREEN_MARGIN,
) -> int:
    """Choose the largest supported inset without shrinking a fitting minimum."""

    if available - (2 * normal_margin) >= minimum:
        return normal_margin
    if available - (2 * small_screen_margin) >= minimum:
        return small_screen_margin
    if available >= minimum:
        return max(0, (available - minimum) // 2)
    return small_screen_margin if available > (2 * small_screen_margin) else 0


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
    requested: object,
    available: Sequence[int],
    *,
    default: Tuple[int, int] = SETTINGS_DEFAULT_SIZE,
    minimum: Tuple[int, int] = SETTINGS_MINIMUM_SIZE,
    normal_margin: int = SETTINGS_NORMAL_SCREEN_MARGIN,
    small_screen_margin: int = SETTINGS_SMALL_SCREEN_MARGIN,
) -> Tuple[int, int]:
    """Clamp a logical size while retaining deliberate screen margins.

    Normal desktop screens reserve ``normal_margin`` on every edge.  When that
    cannot accommodate the normal minimum, the dialog uses the emergency
    fallback and reserves ``small_screen_margin`` on every edge instead.
    """

    try:
        available_width, available_height = (int(available[0]), int(available[1]))
    except (TypeError, ValueError, IndexError):
        available_width, available_height = default
    available_width = max(1, available_width)
    available_height = max(1, available_height)
    horizontal_margin = _effective_axis_margin(
        available_width,
        minimum[0],
        normal_margin,
        small_screen_margin,
    )
    vertical_margin = _effective_axis_margin(
        available_height,
        minimum[1],
        normal_margin,
        small_screen_margin,
    )
    maximum_width = max(1, available_width - (2 * horizontal_margin))
    maximum_height = max(1, available_height - (2 * vertical_margin))
    try:
        requested_width, requested_height = (
            int(requested[0]), int(requested[1])  # type: ignore[index]
        )
    except (TypeError, ValueError, IndexError):
        requested_width, requested_height = default
    minimum_width = min(minimum[0], maximum_width)
    minimum_height = min(minimum[1], maximum_height)
    return (
        min(maximum_width, max(minimum_width, requested_width)),
        min(maximum_height, max(minimum_height, requested_height)),
    )


def settings_screen_uses_compact_fallback(
    available: Sequence[int],
    *,
    minimum: Tuple[int, int] = SETTINGS_MINIMUM_SIZE,
    normal_margin: int = SETTINGS_NORMAL_SCREEN_MARGIN,
    small_screen_margin: int = SETTINGS_SMALL_SCREEN_MARGIN,
    rail_width: int = 184,
    minimum_main_width: int = 680,
) -> bool:
    """Return whether the usable dialog width cannot retain the sidebar."""

    try:
        width = int(available[0])
    except (TypeError, ValueError, IndexError):
        return False
    horizontal_margin = _effective_axis_margin(
        max(1, width),
        minimum[0],
        normal_margin,
        small_screen_margin,
    )
    usable_width = max(1, width - (2 * horizontal_margin))
    return usable_width < rail_width + minimum_main_width


def visible_geometry_ratio(requested: object, screens: Sequence[Sequence[int]]) -> float:
    """Return the fraction of a logical rectangle visible on connected screens."""

    try:
        x, y, width, height = (
            int(requested[0]),  # type: ignore[index]
            int(requested[1]),  # type: ignore[index]
            int(requested[2]),  # type: ignore[index]
            int(requested[3]),  # type: ignore[index]
        )
    except (TypeError, ValueError, IndexError):
        return 0.0
    if width <= 0 or height <= 0:
        return 0.0
    visible_area = 0
    for raw_screen in screens:
        try:
            screen_x, screen_y, screen_width, screen_height = (
                int(raw_screen[0]),
                int(raw_screen[1]),
                int(raw_screen[2]),
                int(raw_screen[3]),
            )
        except (TypeError, ValueError, IndexError):
            continue
        intersection_width = max(
            0,
            min(x + width, screen_x + max(0, screen_width)) - max(x, screen_x),
        )
        intersection_height = max(
            0,
            min(y + height, screen_y + max(0, screen_height)) - max(y, screen_y),
        )
        visible_area += intersection_width * intersection_height
    return min(1.0, visible_area / float(width * height))


def saved_window_geometry_is_valid(
    requested: object,
    screens: Sequence[Sequence[int]],
    *,
    saved_screen_exists: bool = True,
    minimum: Tuple[int, int] = SETTINGS_MINIMUM_SIZE,
    visible_ratio: float = SETTINGS_MINIMUM_VISIBLE_RATIO,
) -> bool:
    """Validate a normal-window rectangle before it can be restored."""

    if not saved_screen_exists:
        return False
    try:
        width, height = int(requested[2]), int(requested[3])  # type: ignore[index]
    except (TypeError, ValueError, IndexError):
        return False
    if width < minimum[0] or height < minimum[1]:
        return False
    valid_screens = []
    for screen in screens:
        try:
            parsed = tuple(int(screen[index]) for index in range(4))
        except (TypeError, ValueError, IndexError):
            continue
        if parsed[2] > 0 and parsed[3] > 0:
            valid_screens.append(parsed)
    if not valid_screens:
        return False
    left = min(screen[0] for screen in valid_screens)
    top = min(screen[1] for screen in valid_screens)
    right = max(screen[0] + screen[2] for screen in valid_screens)
    bottom = max(screen[1] + screen[3] for screen in valid_screens)
    if width > right - left or height > bottom - top:
        return False
    return visible_geometry_ratio(requested, valid_screens) >= visible_ratio


def migrate_saved_window_geometry(
    requested: object,
    screens: Sequence[Sequence[int]],
    *,
    source_version: object,
    saved_screen_exists: bool = True,
    minimum: Tuple[int, int] = SETTINGS_MINIMUM_SIZE,
    visible_ratio: float = SETTINGS_MINIMUM_VISIBLE_RATIO,
) -> Optional[Tuple[int, int, int, int]]:
    """Return a restorable v3/v4 logical rectangle for geometry storage v4.

    Geometry storage keys are versioned independently from the add-on config
    schema.  A v3 rectangle can therefore migrate without rewriting user
    configuration, but it must satisfy the current minimum size and visibility
    contract.  Unknown versions and disconnected-screen records fail closed.
    """

    try:
        version = int(source_version)
    except (TypeError, ValueError, OverflowError):
        return None
    if isinstance(source_version, bool) or version not in {
        SETTINGS_PREVIOUS_GEOMETRY_VERSION,
        SETTINGS_GEOMETRY_VERSION,
    }:
        return None
    if not saved_window_geometry_is_valid(
        requested,
        screens,
        saved_screen_exists=saved_screen_exists,
        minimum=minimum,
        visible_ratio=visible_ratio,
    ):
        return None
    try:
        return tuple(int(requested[index]) for index in range(4))  # type: ignore[index,return-value]
    except (TypeError, ValueError, IndexError):
        return None


def clamp_window_geometry(
    requested: object,
    available: Sequence[int],
    *,
    parent: object = None,
    default: Tuple[int, int] = SETTINGS_DEFAULT_SIZE,
    minimum: Tuple[int, int] = SETTINGS_MINIMUM_SIZE,
) -> Tuple[int, int, int, int]:
    """Return a fully visible logical window rectangle for the active screen.

    ``requested`` and ``parent`` use ``(x, y, width, height)`` tuples. A saved
    rectangle is retained only when its center still belongs to the active
    available geometry. This makes a disconnected-monitor restore recenter
    deterministically without consulting physical pixels or device ratios.
    """

    try:
        screen_x, screen_y, screen_width, screen_height = (
            int(available[0]),
            int(available[1]),
            int(available[2]),
            int(available[3]),
        )
    except (TypeError, ValueError, IndexError):
        screen_x, screen_y = 0, 0
        screen_width, screen_height = default
    screen_width = max(1, screen_width)
    screen_height = max(1, screen_height)

    try:
        requested_x, requested_y, requested_width, requested_height = (
            int(requested[0]),  # type: ignore[index]
            int(requested[1]),  # type: ignore[index]
            int(requested[2]),  # type: ignore[index]
            int(requested[3]),  # type: ignore[index]
        )
        requested_valid = requested_width > 0 and requested_height > 0
    except (TypeError, ValueError, IndexError):
        requested_x = requested_y = 0
        requested_width, requested_height = default
        requested_valid = False

    width, height = clamp_window_size(
        (requested_width, requested_height),
        (screen_width, screen_height),
        default=default,
        minimum=minimum,
    )
    horizontal_margin = _effective_axis_margin(
        screen_width,
        minimum[0],
    )
    vertical_margin = _effective_axis_margin(
        screen_height,
        minimum[1],
    )
    left = screen_x + horizontal_margin
    top = screen_y + vertical_margin
    right = max(left, screen_x + screen_width - horizontal_margin - width)
    bottom = max(top, screen_y + screen_height - vertical_margin - height)
    center_x = requested_x + requested_width // 2
    center_y = requested_y + requested_height // 2
    saved_screen_is_current = (
        requested_valid
        and screen_x <= center_x < screen_x + screen_width
        and screen_y <= center_y < screen_y + screen_height
    )

    if saved_screen_is_current:
        x = min(max(requested_x, left), right)
        y = min(max(requested_y, top), bottom)
        return x, y, width, height

    try:
        parent_x, parent_y, parent_width, parent_height = (
            int(parent[0]),  # type: ignore[index]
            int(parent[1]),  # type: ignore[index]
            int(parent[2]),  # type: ignore[index]
            int(parent[3]),  # type: ignore[index]
        )
        parent_center_x = parent_x + max(0, parent_width) // 2
        parent_center_y = parent_y + max(0, parent_height) // 2
        parent_is_current = (
            screen_x <= parent_center_x < screen_x + screen_width
            and screen_y <= parent_center_y < screen_y + screen_height
        )
    except (TypeError, ValueError, IndexError):
        parent_center_x = screen_x + screen_width // 2
        parent_center_y = screen_y + screen_height // 2
        parent_is_current = False
    if not parent_is_current:
        parent_center_x = screen_x + screen_width // 2
        parent_center_y = screen_y + screen_height // 2
    x = min(
        max(parent_center_x - width // 2, left),
        right,
    )
    y = min(
        max(parent_center_y - height // 2, top),
        bottom,
    )
    return x, y, width, height


SECTION_IDS = (
    "dashboard",
    "appearance",
    "calendar",
    "events",
    "bible_verse",
    "about_support",
)

SECTION_LABELS = {
    "dashboard": "Dashboard",
    "appearance": "Appearance",
    "calendar": "Calendar",
    "events": "Events",
    "bible_verse": "Bible verse",
    "about_support": "About & support",
}

SECTION_GROUPS = {
    section_id: "" for section_id in SECTION_IDS
}

_SECTION_TARGETS = {
    "": ("dashboard", ""),
    "appearance": ("appearance", ""),
    "theme": ("appearance", ""),
    "theme & layout": ("appearance", ""),
    "theme_layout": ("appearance", ""),
    "dashboard": ("dashboard", ""),
    "home": ("dashboard", "dashboard_sections"),
    "home screen": ("dashboard", "dashboard_sections"),
    "home_screen": ("dashboard", "dashboard_sections"),
    "activity": ("calendar", ""),
    "calendar": ("calendar", ""),
    "calendar & data": ("calendar", ""),
    "calendar_data": ("calendar", ""),
    "event": ("events", ""),
    "events": ("events", ""),
    "bible": ("bible_verse", ""),
    "bible verse": ("bible_verse", ""),
    "bible_verse": ("bible_verse", ""),
    "bible_library": ("bible_verse", "library"),
    "bible_display": ("bible_verse", "display"),
    "about": ("about_support", ""),
    "about & credits": ("about_support", ""),
    "about & support": ("about_support", ""),
    "about_support": ("about_support", ""),
}


def resolve_section(value: object) -> str:
    """Return a stable settings section ID while retaining legacy routes."""
    return resolve_section_target(value)[0]


def resolve_section_target(value: object) -> Tuple[str, str]:
    """Return the settings destination and an optional card or Bible view."""
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
    """Overlay configured local events without replacing canonical study data.

    The returned snapshot updates only event-bearing facts used by production
    rendering; collection-backed study values remain unchanged.
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


_APPEARANCE_RESET_PATHS: Tuple[Path, ...] = (
    ("appearance", "preset"),
    ("appearance", "mode"),
    ("appearance", "opacity"),
    ("appearance", "blur"),
    ("appearance", "text_scale"),
    ("heatmap", "presets_by_theme"),
)
_DASHBOARD_SECTIONS_RESET_PATHS: Tuple[Path, ...] = (
    ("visibility", "heatmap"),
    ("visibility", "remaining"),
    ("visibility", "today"),
    ("visibility", "heatmap_metrics"),
    ("visibility", "bible"),
)
_STUDY_METRICS_RESET_PATHS: Tuple[Path, ...] = (
    ("study", "pace_unit"),
    ("study", "retention_target"),
    ("new_cards", "include_rescheduled"),
)
_CALENDAR_DISPLAY_RESET_PATHS: Tuple[Path, ...] = (
    ("heatmap", "calendar_view"),
    ("heatmap", "week_start"),
    ("visibility", "events"),
)
_CALENDAR_RANGE_RESET_PATHS: Tuple[Path, ...] = (
    ("heatmap", "history_days"),
    ("heatmap", "ignore_before"),
    ("heatmap", "show_due_forecast"),
    ("heatmap", "forecast_days"),
)
_LOCAL_DATA_RESET_PATHS: Tuple[Path, ...] = (
    ("heatmap", "exclude_manual_reschedules"),
    ("heatmap", "exclude_deleted_cards"),
    ("heatmap", "excluded_deck_ids"),
)
_BIBLE_APPEARANCE_RESET_PATHS: Tuple[Path, ...] = (
    ("bible", "font_family"),
    ("bible", "font_size"),
    ("bible", "font_color"),
    ("bible", "theme_aware_color"),
)
_BIBLE_ROTATION_RESET_PATHS: Tuple[Path, ...] = (
    ("bible", "rotation_mode"),
)


_RESET_DEFAULT_PATHS = {
    "appearance": _APPEARANCE_RESET_PATHS,
    "panel_placement": (("home_screen", "position"),),
    "dashboard_sections": _DASHBOARD_SECTIONS_RESET_PATHS,
    "study_metrics": _STUDY_METRICS_RESET_PATHS,
    "home_screen_legacy": (
        _DASHBOARD_SECTIONS_RESET_PATHS
        + _STUDY_METRICS_RESET_PATHS
        + (("home_screen", "position"),)
    ),
    "calendar_display": _CALENDAR_DISPLAY_RESET_PATHS,
    "calendar_range": _CALENDAR_RANGE_RESET_PATHS,
    "local_data": _LOCAL_DATA_RESET_PATHS,
    "calendar": (
        _CALENDAR_DISPLAY_RESET_PATHS
        + _CALENDAR_RANGE_RESET_PATHS
        + _LOCAL_DATA_RESET_PATHS
    ),
    "dashboard": (
        _DASHBOARD_SECTIONS_RESET_PATHS
        + _STUDY_METRICS_RESET_PATHS
        + _LOCAL_DATA_RESET_PATHS
        + (("home_screen", "position"),)
    ),
    "bible_appearance": _BIBLE_APPEARANCE_RESET_PATHS,
    "bible_rotation": _BIBLE_ROTATION_RESET_PATHS,
    "bible_verse": (
        _BIBLE_APPEARANCE_RESET_PATHS + _BIBLE_ROTATION_RESET_PATHS
    ),
}


def _path_value(source: Mapping[str, Any], path: Path) -> object:
    value: object = source
    for part in path:
        value = value[part]  # type: ignore[index]
    return value


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
            "heatmap.forecast_days": True,
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
            _assign_path(self.values, path, _path_value(self.defaults, path))
        self.values = normalize_config(self.values)
        return True

    def scope_snapshot(self, scope: object) -> Dict[Path, object]:
        """Copy only the fields owned by one Reset action."""

        paths = _RESET_DEFAULT_PATHS.get(str(scope or "").strip().casefold())
        if not paths:
            return {}
        return {
            path: deepcopy(_path_value(self.values, path))
            for path in paths
        }

    def restore_scope(
        self,
        scope: object,
        snapshot: Mapping[Path, object],
    ) -> bool:
        """Restore one scoped snapshot while preserving all other edits."""

        paths = _RESET_DEFAULT_PATHS.get(str(scope or "").strip().casefold())
        if not paths or any(path not in snapshot for path in paths):
            return False
        for path in paths:
            _assign_path(self.values, path, snapshot[path])
        self.values = normalize_config(self.values)
        return True

    def scope_differs_from_defaults(self, scope: object) -> bool:
        """Return whether a scoped Reset action would change staged values."""

        paths = _RESET_DEFAULT_PATHS.get(str(scope or "").strip().casefold())
        if not paths:
            return False
        for path in paths:
            try:
                current = _path_value(self.values, path)
                default = _path_value(self.defaults, path)
            except (KeyError, TypeError):
                return True
            if current != default:
                return True
        return False

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
