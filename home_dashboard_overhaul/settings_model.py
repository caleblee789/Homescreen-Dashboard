"""Pure staged-settings state, routing, merge, and verse-import helpers.

This module deliberately has no Qt or Anki imports so its data-loss and
compatibility behavior can be exercised without starting the application.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Sequence, Tuple

from .config_schema import default_config, normalize_config
from .verse import verse_within_limit


Path = Tuple[str, ...]
_MISSING = object()


SECTION_IDS = (
    "theme_layout",
    "home_screen",
    "calendar_data",
    "events",
    "bible_verse",
    "about",
)

SECTION_LABELS = {
    "theme_layout": "Theme & layout",
    "home_screen": "Home screen",
    "calendar_data": "Calendar & data",
    "events": "Events",
    "bible_verse": "Bible verse",
    "about": "About",
}

SECTION_GROUPS = {
    "theme_layout": "Personalize",
    "home_screen": "Personalize",
    "calendar_data": "Personalize",
    "events": "Content",
    "bible_verse": "Content",
    "about": "Support",
}

_ALIASES = {
    "": "theme_layout",
    "appearance": "theme_layout",
    "theme": "theme_layout",
    "theme & layout": "theme_layout",
    "theme_layout": "theme_layout",
    "dashboard": "home_screen",
    "home": "home_screen",
    "home screen": "home_screen",
    "home_screen": "home_screen",
    "activity": "calendar_data",
    "calendar": "calendar_data",
    "calendar & data": "calendar_data",
    "calendar_data": "calendar_data",
    "event": "events",
    "events": "events",
    "bible": "bible_verse",
    "bible verse": "bible_verse",
    "bible_verse": "bible_verse",
    "about": "about",
    "about & credits": "about",
}


def resolve_section(value: object) -> str:
    """Return a stable settings section ID while retaining legacy routes."""
    key = str(value or "").strip().casefold()
    return _ALIASES.get(key, "theme_layout")


def font_family_value(staged: object, selected: object, explicitly_changed: bool) -> str:
    """Keep an unavailable saved family until the user changes the control."""
    staged_value = str(staged or "").strip()
    selected_value = str(selected or "").strip()
    if explicitly_changed and selected_value:
        return selected_value
    return staged_value or selected_value


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


_SECTION_DEFAULT_PATHS = {
    "theme_layout": (("appearance",),),
    "home_screen": (("visibility",), ("study",), ("new_cards",)),
    "calendar_data": (("heatmap",),),
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
    def dependency_state(self) -> Dict[str, bool]:
        visibility = self.values["visibility"]
        return {
            "study.show_eta": bool(visibility["today"]),
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
        section_id = resolve_section(section)
        paths = _SECTION_DEFAULT_PATHS.get(section_id)
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
