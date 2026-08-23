"""Read-only, idempotent migration from the five preserved legacy add-ons."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

from .config_schema import normalize_config
from .verse import quote_fingerprint


LEGACY_IDS = ("1771074083", "635082046", "1556734708", "1143540799", "290511870")
PALETTE_MAP = {
    # Schema 5 deliberately does not retain or approximate legacy palettes.
    # Every legacy alias enters the same predictable Sapphire fallback.
    "lime": "Sapphire Glass",
    "olive": "Sapphire Glass",
    "ice": "Sapphire Glass",
    "magenta": "Sapphire Glass",
    "flame": "Sapphire Glass",
}


def _enabled(manager: Any, addon_id: str) -> bool:
    if _addon_root(manager, addon_id) is None:
        return False
    checker = getattr(manager, "isEnabled", None)
    if callable(checker):
        try:
            return bool(checker(addon_id))
        except Exception:
            pass
    try:
        metadata = manager.addonMeta(addon_id)
    except Exception:
        return False
    disabled = getattr(metadata, "disabled", None)
    if isinstance(disabled, bool):
        return not disabled
    return bool(getattr(metadata, "enabled", False))


def enabled_legacy_ids(manager: Any) -> List[str]:
    return [addon_id for addon_id in LEGACY_IDS if _enabled(manager, addon_id)]


def _addon_root(manager: Any, addon_id: str) -> Path | None:
    getter = getattr(manager, "addonsFolder", None)
    try:
        folder = getter() if callable(getter) else getter
    except Exception:
        folder = None
    if folder:
        candidate = Path(str(folder)) / addon_id
        return candidate if candidate.is_dir() else None
    return None


def _legacy_config(manager: Any, addon_id: str) -> Dict[str, Any]:
    try:
        value = manager.getConfig(addon_id)
    except Exception:
        return {}
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def _source_digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _heatmap_config(mw: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    synced: object = {}
    col = getattr(mw, "col", None)
    if col is not None:
        getter = getattr(col, "get_config", None)
        if callable(getter):
            try:
                synced = getter("heatmap")
            except Exception:
                synced = {}
        if not synced:
            conf = getattr(col, "conf", {})
            if isinstance(conf, Mapping):
                synced = conf.get("heatmap", {})
    if isinstance(synced, Mapping) and isinstance(synced.get("synced"), Mapping):
        synced = synced["synced"]
    profile: object = {}
    manager = getattr(mw, "pm", None)
    raw_profile = getattr(manager, "profile", {}) if manager is not None else {}
    if isinstance(raw_profile, Mapping):
        profile = raw_profile.get("heatmap", {})
    if isinstance(profile, Mapping) and isinstance(profile.get("profile"), Mapping):
        profile = profile["profile"]
    return (dict(synced) if isinstance(synced, Mapping) else {}, dict(profile) if isinstance(profile, Mapping) else {})


def _event_rows(manager: Any) -> Tuple[List[Dict[str, Any]], str]:
    root = _addon_root(manager, "1143540799")
    database = root / "user_files" / "events.db" if root else None
    if database is None or not database.is_file():
        return [], ""
    rows: List[Dict[str, Any]] = []
    try:
        connection = sqlite3.connect("file:{}?mode=ro".format(database), uri=True)
        try:
            for event_id, event_date, name in connection.execute("SELECT id, date, name FROM events ORDER BY id"):
                rows.append({
                    "id": "legacy-event-{}".format(event_id),
                    "date": str(event_date),
                    "name": str(name),
                    "archived": False,
                    "created_at": "",
                    "archived_at": "",
                })
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        return [], ""
    return rows, _source_digest(rows)


def _valid_rotation_state(manager: Any, quotes: Sequence[str]) -> Dict[str, Any] | None:
    root = _addon_root(manager, "290511870")
    state_path = root / "user_files" / "rotation_state.json" if root else None
    if state_path is None:
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(state, Mapping):
        return None
    if state.get("version") != 1 or state.get("quote") not in quotes:
        return None
    if state.get("quote_fingerprint") != quote_fingerprint(quotes):
        return None
    refresh_key = state.get("refresh_key")
    if not isinstance(refresh_key, str) or not (refresh_key == "manual" or refresh_key.startswith("daily:")):
        return None
    return dict(state)


def _apply_heatmap(config: MutableMapping[str, Any], synced: Mapping[str, Any], profile: Mapping[str, Any], warnings: List[str]) -> None:
    appearance = config["appearance"]
    heatmap = config["heatmap"]
    palette = synced.get("colors")
    if isinstance(palette, str):
        appearance["preset"] = PALETTE_MAP.get(palette.lower(), "Sapphire Glass")
    # Schema 2 removes the legacy continuous nine-month presentation.  Either
    # legacy mode opens in the complete Year view after migration.
    heatmap["calendar_view"] = "year"
    heatmap["history_days"] = synced.get("limhist") or 0
    legacy_forecast = synced.get("limfcst")
    if legacy_forecast == 0:
        heatmap["forecast_days"] = 730
        warnings.append("Review Heatmap's unlimited forecast was capped at 730 days to avoid invalid far-future scheduling data.")
    elif isinstance(legacy_forecast, int):
        heatmap["forecast_days"] = legacy_forecast
    heatmap["exclude_deleted_cards"] = bool(synced.get("limcdel", False))
    heatmap["exclude_manual_reschedules"] = bool(synced.get("limresched", True))
    heatmap["excluded_deck_ids"] = list(synced.get("limdecks", [])) if isinstance(synced.get("limdecks"), list) else []
    raw_date = synced.get("limdate")
    if isinstance(raw_date, (int, float)) and raw_date > 0:
        heatmap["ignore_before"] = datetime.fromtimestamp(raw_date).astimezone().date().isoformat()
    display = profile.get("display")
    if isinstance(display, Mapping) and isinstance(display.get("deckbrowser"), bool):
        config["visibility"]["heatmap"] = display["deckbrowser"]
    if isinstance(profile.get("statsvis"), bool):
        config["visibility"]["heatmap_metrics"] = profile["statsvis"]


def _apply_new_counter(config: MutableMapping[str, Any], legacy: Mapping[str, Any]) -> None:
    target = config["new_cards"]
    if isinstance(legacy.get("Count rescheduled"), bool):
        target["include_rescheduled"] = legacy["Count rescheduled"]
    week_start = legacy.get("Week start")
    if isinstance(week_start, int) and 0 <= week_start <= 6:
        config["heatmap"]["week_start"] = week_start


def _apply_more_stats(config: MutableMapping[str, Any], legacy: Mapping[str, Any]) -> None:
    # The schema-7 dashboard always exposes the ETA row. The retired
    # ShowTimeLeft preference is intentionally not imported.
    del config, legacy


def _apply_bible(config: MutableMapping[str, Any], legacy: Mapping[str, Any]) -> None:
    target = config["bible"]
    mappings = {
        "quote": "quotes",
        "font color": "font_color",
        "font family": "font_family",
        "font size": "font_size",
        "use theme-aware color": "theme_aware_color",
        "rotation mode": "rotation_mode",
    }
    for source, destination in mappings.items():
        if source in legacy:
            target[destination] = deepcopy(legacy[source])


def prepare_migration(mw: Any, current: object) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
    config = normalize_config(current)
    if config["migration"].get("completed"):
        return config, None
    manager = mw.addonManager
    new_counter = _legacy_config(manager, "635082046")
    more_stats = _legacy_config(manager, "1556734708")
    events_config = _legacy_config(manager, "1143540799")
    bible = _legacy_config(manager, "290511870")
    heatmap_synced, heatmap_profile = _heatmap_config(mw)
    event_rows, event_digest = _event_rows(manager)
    warnings: List[str] = []
    _apply_heatmap(config, heatmap_synced, heatmap_profile, warnings)
    _apply_new_counter(config, new_counter)
    _apply_more_stats(config, more_stats)
    _apply_bible(config, bible)
    if events_config.get("sort") == "DESC":
        config["events"]["sort"] = "descending"
    if event_rows:
        existing_ids = {str(item.get("id")) for item in config["events"].get("items", [])}
        config["events"]["items"].extend(row for row in event_rows if row["id"] not in existing_ids)
    config = normalize_config(config)
    rotation_state = _valid_rotation_state(manager, config["bible"]["quotes"])
    source_values = {
        "1771074083": {"synced": heatmap_synced, "profile": heatmap_profile},
        "635082046": new_counter,
        "1556734708": more_stats,
        "1143540799": {"config": events_config, "events_sha256": event_digest},
        "290511870": bible,
    }
    config["migration"].update({
        "completed": True,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sources": {addon_id: _source_digest(value) for addon_id, value in source_values.items()},
        "warnings": warnings,
    })
    return config, rotation_state
