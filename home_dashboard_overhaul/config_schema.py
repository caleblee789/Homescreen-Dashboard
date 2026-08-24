"""Versioned, defensive configuration normalization."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Tuple

from .themes import (
    DEFAULT_CUSTOM_BIBLE_COLOR,
    DEFAULT_HEATMAP_PRESETS,
    HEATMAP_PRESETS,
    PRESETS,
)
from .verse import load_default_quotes


SCHEMA_VERSION = 8
PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "config.json"
DEFAULT_VERSES_PATH = PACKAGE_ROOT / "default_verses.json"
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
FONT_SIZE_RE = re.compile(r"^(?:[89]|[1-8]\d|9[0-6])px$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def default_config() -> Dict[str, Any]:
    defaults = _read_json(DEFAULT_CONFIG_PATH)
    defaults.setdefault("bible", {})["quotes"] = load_default_quotes(DEFAULT_VERSES_PATH)
    return defaults


def _deep_merge(defaults: Mapping[str, Any], raw: Mapping[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = deepcopy(dict(raw))
    for key, default in defaults.items():
        if key not in result:
            result[key] = deepcopy(default)
        elif isinstance(default, Mapping) and isinstance(result[key], Mapping):
            result[key] = _deep_merge(default, result[key])
    return result


def _choice(value: object, options: Iterable[str], default: str) -> str:
    return value if isinstance(value, str) and value in options else default


def _bool(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _int(value: object, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return default
    return min(maximum, max(minimum, parsed))


def _float(value: object, default: float, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return default
    return min(maximum, max(minimum, parsed))


def _text(value: object, default: str, maximum: int) -> str:
    if not isinstance(value, str):
        return default
    candidate = value.strip()
    return candidate[:maximum] if candidate else default


def _font_family(value: object) -> str:
    candidate = _text(value, "Georgia, serif", 120)
    return "Georgia, serif" if any(char in candidate for char in '<>;"\'') else candidate


def _date(value: object) -> str:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return ""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return ""


def _normalize_event(value: object, index: int) -> Dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    event_date = _date(value.get("date"))
    name = _text(value.get("name"), "", 160)
    if not event_date or not name:
        return None
    raw_id = value.get("id")
    if isinstance(raw_id, (str, int)) and str(raw_id).strip():
        event_id = str(raw_id).strip()[:80]
    else:
        material = "{}\0{}\0{}".format(event_date, name, index).encode("utf-8")
        event_id = "event-{}".format(hashlib.sha256(material).hexdigest()[:16])
    return {
        "id": event_id,
        "date": event_date,
        "name": name,
        "archived": _bool(value.get("archived"), False),
        "created_at": _text(value.get("created_at"), "", 40),
        "archived_at": _text(value.get("archived_at"), "", 40),
    }


def normalize_config(raw: object) -> Dict[str, Any]:
    defaults = default_config()
    source = raw if isinstance(raw, Mapping) else {}
    raw_introduced = source.get("introduced", {}) if isinstance(source, Mapping) else {}
    raw_introduced = raw_introduced if isinstance(raw_introduced, Mapping) else {}
    raw_new_cards = source.get("new_cards", {}) if isinstance(source, Mapping) else {}
    raw_new_cards = raw_new_cards if isinstance(raw_new_cards, Mapping) else {}
    raw_heatmap = source.get("heatmap", {}) if isinstance(source, Mapping) else {}
    raw_heatmap = raw_heatmap if isinstance(raw_heatmap, Mapping) else {}
    config = _deep_merge(defaults, source)
    config["schema_version"] = SCHEMA_VERSION

    appearance = config["appearance"]
    appearance["preset"] = _choice(appearance.get("preset"), PRESETS.keys(), "Sapphire Glass")
    appearance["mode"] = _choice(appearance.get("mode"), {"auto", "light", "dark"}, "auto")
    # Schema 8 narrows glass controls to the range that keeps text-bearing
    # components legible over arbitrary host wallpapers. Non-Sapphire themes
    # retain these preferences for a future switch back, but render opaquely.
    appearance["opacity"] = _int(appearance.get("opacity"), 96, 94, 100)
    appearance["blur"] = _int(appearance.get("blur"), 12, 0, 16)
    # Layout density remains retired. Drop the known legacy
    # key while the deep merge continues to preserve unrelated future keys.
    appearance.pop("density", None)
    appearance["text_scale"] = _int(appearance.get("text_scale"), 100, 90, 150)

    home_screen = config["home_screen"]
    home_screen["position"] = _choice(home_screen.get("position"), {"top", "bottom"}, "top")

    visibility = config["visibility"]
    for key, default in defaults["visibility"].items():
        visibility[key] = _bool(visibility.get(key), bool(default))
    # Buried is a scheduler-authoritative Today’s Session metric in schema 8,
    # not an independently hideable dashboard surface.
    visibility.pop("buried", None)
    visibility.pop("introduced", None)

    study = config["study"]
    study["pace_unit"] = _choice(study.get("pace_unit"), {"seconds_per_card", "cards_per_minute"}, "seconds_per_card")
    study["retention_target"] = _int(study.get("retention_target"), 80, 50, 100)
    study.pop("pace_lookback_days", None)
    study.pop("new_card_weight", None)
    # Schema 7 makes ETA a stable Today’s Session row. Drop both known
    # preference spellings while preserving unrelated future study keys.
    study.pop("show_eta", None)
    study.pop("show_estimate", None)

    new_cards = config["new_cards"]
    raw_include_rescheduled = raw_new_cards.get(
        "include_rescheduled",
        raw_introduced.get("include_rescheduled", new_cards.get("include_rescheduled")),
    )
    new_cards["include_rescheduled"] = _bool(raw_include_rescheduled, True)
    config.pop("introduced", None)

    heatmap = config["heatmap"]
    raw_view = raw_heatmap.get("calendar_view")
    if raw_view in {"month", "year"}:
        heatmap["calendar_view"] = str(raw_view)
    elif "calendar_view" in raw_heatmap:
        heatmap["calendar_view"] = "year"
    elif raw_heatmap.get("calendar_mode") in {"year", "nine_months"}:
        # Both schema-1 display modes become the complete Year view.  The old
        # continuous nine-month mode is intentionally retired in schema 2.
        heatmap["calendar_view"] = "year"
    else:
        heatmap["calendar_view"] = "year"
    heatmap.pop("calendar_mode", None)
    raw_week_start = raw_heatmap.get("week_start", raw_introduced.get("week_start", heatmap.get("week_start")))
    heatmap["week_start"] = _int(raw_week_start, 0, 0, 6)
    heatmap["history_days"] = _int(heatmap.get("history_days"), 0, 0, 36500)
    heatmap["forecast_days"] = _int(heatmap.get("forecast_days"), 90, 0, 730)
    heatmap["ignore_before"] = _date(heatmap.get("ignore_before"))
    heatmap["exclude_manual_reschedules"] = _bool(heatmap.get("exclude_manual_reschedules"), True)
    heatmap["exclude_deleted_cards"] = _bool(heatmap.get("exclude_deleted_cards"), False)
    heatmap["show_due_forecast"] = _bool(heatmap.get("show_due_forecast"), True)
    raw_theme_presets = raw_heatmap.get("presets_by_theme", {})
    raw_theme_presets = raw_theme_presets if isinstance(raw_theme_presets, Mapping) else {}
    legacy_heatmap_preset = raw_heatmap.get("preset", raw_heatmap.get("heatmap_preset"))
    presets_by_theme: Dict[str, str] = {}
    for theme_name in PRESETS:
        candidate = raw_theme_presets.get(theme_name, legacy_heatmap_preset)
        presets_by_theme[theme_name] = _choice(
            candidate,
            HEATMAP_PRESETS[theme_name].keys(),
            DEFAULT_HEATMAP_PRESETS[theme_name],
        )
    heatmap["presets_by_theme"] = presets_by_theme
    heatmap.pop("preset", None)
    heatmap.pop("heatmap_preset", None)
    raw_decks = heatmap.get("excluded_deck_ids", [])
    deck_ids: List[int] = []
    if isinstance(raw_decks, list):
        for raw_id in raw_decks:
            try:
                deck_id = int(raw_id)
            except (TypeError, ValueError, OverflowError):
                continue
            if deck_id > 0 and deck_id not in deck_ids:
                deck_ids.append(deck_id)
    heatmap["excluded_deck_ids"] = deck_ids

    # Schema 6 retires the previous large selected-date/details surface and
    # its reserved slots. Preserve unrelated future keys, but remove the
    # exact known legacy identifiers and force the only supported ordering.
    visibility.pop("selected_date", None)
    visibility.pop("most_missed", None)
    visibility.pop("due_decks", None)
    layout = config.get("layout")
    if not isinstance(layout, MutableMapping):
        layout = {}
        config["layout"] = layout
    if isinstance(layout, MutableMapping):
        for key in ("selected_date_panel", "selected_date_details", "most_missed", "due_deck_breakdown"):
            layout.pop(key, None)
        removed_slots = {
            "selected_date_panel",
            "selected_date_details",
            "most_missed",
            "most_missed_preview",
            "due_deck_breakdown",
            "date_events_column",
        }
        raw_order = layout.get("order", [])
        order = [
            str(item)
            for item in raw_order
            if isinstance(item, str) and item not in removed_slots
        ] if isinstance(raw_order, list) else []
        canonical = ("study_calendar", "summary_metrics", "bible_verse")
        unrelated = [item for item in order if item not in canonical]
        layout["order"] = list(canonical) + unrelated

    events = config["events"]
    events["sort"] = _choice(events.get("sort"), {"ascending", "descending"}, "ascending")
    normalized_events: List[Dict[str, Any]] = []
    raw_events = events.get("items", [])
    if isinstance(raw_events, list):
        for index, raw_event in enumerate(raw_events):
            normalized = _normalize_event(raw_event, index)
            if normalized:
                normalized_events.append(normalized)
    events["items"] = normalized_events

    bible = config["bible"]
    raw_quotes = bible.get("quotes", [])
    quotes = [value.strip() for value in raw_quotes if isinstance(value, str) and value.strip()] if isinstance(raw_quotes, list) else []
    bible["quotes"] = quotes[:500] or defaults["bible"]["quotes"]
    color = bible.get("font_color")
    bible["font_color"] = (
        color
        if isinstance(color, str) and HEX_COLOR_RE.fullmatch(color.strip())
        else DEFAULT_CUSTOM_BIBLE_COLOR
    )
    bible["font_family"] = _font_family(bible.get("font_family"))
    size = bible.get("font_size")
    bible["font_size"] = size.lower() if isinstance(size, str) and FONT_SIZE_RE.fullmatch(size.lower()) else "28px"
    bible["theme_aware_color"] = _bool(bible.get("theme_aware_color"), True)
    bible["rotation_mode"] = _choice(bible.get("rotation_mode"), {"every render", "daily", "manual"}, "daily")

    migration = config["migration"]
    migration["completed"] = _bool(migration.get("completed"), False)
    migration["completed_at"] = _text(migration.get("completed_at"), "", 40)
    migration["sources"] = dict(migration.get("sources")) if isinstance(migration.get("sources"), Mapping) else {}
    warnings = migration.get("warnings", [])
    migration["warnings"] = [str(value)[:300] for value in warnings if isinstance(value, str)][:20] if isinstance(warnings, list) else []
    return config


def archive_expired_events(config: MutableMapping[str, Any], today: date | None = None) -> bool:
    current = today or date.today()
    changed = False
    items = config.get("events", {}).get("items", [])
    if not isinstance(items, list):
        return False
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    for item in items:
        if not isinstance(item, MutableMapping) or item.get("archived"):
            continue
        try:
            expired = date.fromisoformat(str(item.get("date", ""))) < current
        except ValueError:
            expired = False
        if expired:
            item["archived"] = True
            item["archived_at"] = stamp
            changed = True
    return changed


def analytics_config_fingerprint(config: Mapping[str, Any]) -> str:
    """Fingerprint only settings that change collection analytics.

    Calendar view, theme, visibility, events, and Bible presentation
    are render-only preferences.  Excluding them prevents a Month/Year switch
    or visual save from repeating collection SQL.
    """
    heatmap = config.get("heatmap", {})
    material = {
        "study": {"pace_unit": config.get("study", {}).get("pace_unit")},
        "new_cards": deepcopy(dict(config.get("new_cards", {}))),
        "heatmap": {
            key: deepcopy(heatmap.get(key))
            for key in (
                "history_days",
                "forecast_days",
                "ignore_before",
                "exclude_manual_reschedules",
                "exclude_deleted_cards",
                "excluded_deck_ids",
                "show_due_forecast",
            )
        },
    }
    encoded = json.dumps(material, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def config_fingerprint(config: Mapping[str, Any]) -> str:
    """Backward-compatible name for the analytics cache fingerprint."""
    return analytics_config_fingerprint(config)
