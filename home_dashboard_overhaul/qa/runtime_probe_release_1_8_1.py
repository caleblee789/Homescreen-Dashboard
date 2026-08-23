"""Fail-closed native Deck Browser evidence probe for release 1.8.1.

This module is installed only into a helper add-on directory in a disposable,
sync-disabled Anki base.  It never opens a preview web view: every frame is the
isolated process's real main Deck Browser, mounted through the exact production
controller and renderer from the installed candidate archive.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import traceback
from typing import Any, Dict, Iterable, Mapping
import zipfile

import anki
import home_dashboard_overhaul
from aqt import gui_hooks, mw
from aqt.qt import QApplication, QTimer

from home_dashboard_overhaul.analytics import (
    representative_preview_snapshot,
    unavailable_snapshot,
)
from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.models import (
    AvailabilityReason,
    BrowseTarget,
    BrowseTargetKind,
    BuriedStats,
    DashboardSnapshot,
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


RELEASE = "1.8.1"
REFERENCE_DATE = "2026-08-23"
RUN_ROOT = Path(os.environ.get("HDO_RELEASE_RUN_ROOT", ""))
EXPECTED_PROFILE = os.environ.get("HDO_RELEASE_PROFILE", "")
EXPECTED_SHA256 = os.environ.get("HDO_RELEASE_CANDIDATE_SHA256", "")
EXPECTED_INSTANCE_KEY = os.environ.get("HDO_RELEASE_INSTANCE_KEY", "")
EXPECTED_NORMAL_PID = int(os.environ.get("HDO_RELEASE_EXCLUDED_PID", "0") or 0)
STAGE = os.environ.get("HDO_RELEASE_PROBE_STAGE", "initial")
OUTPUT_ROOT = RUN_ROOT / "hdo-release-evidence-1.8.1"
CAPTURE_ROOT = OUTPUT_ROOT / "captures"
REPORT_PATH = OUTPUT_ROOT / ("runtime-report-{}.json".format(STAGE))
RUN_MARKER = RUN_ROOT / "QA_IDENTITY.json"
ADDON_ROOT = Path(home_dashboard_overhaul.__file__).resolve().parent
PROBE_ROOT = Path(__file__).resolve().parent

ENABLED = (
    str(RUN_ROOT).startswith("/private/tmp/anki-release-qa.")
    and EXPECTED_PROFILE.startswith("Codex QA HDO 1.8.1 ")
    and len(EXPECTED_SHA256) == 64
    and len(EXPECTED_INSTANCE_KEY) >= 24
    and STAGE in {"initial", "restart"}
)

REPORT: Dict[str, Any] = {
    "schema_version": 1,
    "release": RELEASE,
    "stage": STAGE,
    "status": "running",
    "authority": "native-deck-browser-100-percent",
    "errors": [],
    "captures": {},
    "scale_policy": {
        "ui_scale_percent": 100,
        "text_scale_percent": 100,
        "deferred_ui_scales_percent": [125, 150],
    },
}

_started = False
_controller: Any = None
_live_snapshot: DashboardSnapshot | None = None
_cases: list[dict[str, Any]] = []
_case_index = 0
_active_case: dict[str, Any] | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_report() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(REPORT, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _error(stage: str, exc: BaseException) -> None:
    REPORT["errors"].append(
        {
            "stage": stage,
            "error": "{}: {}".format(type(exc).__name__, exc),
            "traceback": traceback.format_exc(),
        }
    )
    REPORT["status"] = "failed"
    _write_report()
    QTimer.singleShot(300, QApplication.instance().quit)


def _normal_pid_is_alive() -> bool:
    if EXPECTED_NORMAL_PID <= 1 or EXPECTED_NORMAL_PID == os.getpid():
        return False
    try:
        os.kill(EXPECTED_NORMAL_PID, 0)
        return True
    except OSError:
        return False


def _candidate_install_identity() -> dict[str, Any]:
    marker = json.loads(RUN_MARKER.read_text(encoding="utf-8"))
    candidate = Path(str(marker.get("candidate", ""))).resolve(strict=True)
    archive_sha = _sha256(candidate)
    _require(archive_sha == EXPECTED_SHA256, "candidate archive checksum changed")
    _require(marker.get("candidate_sha256") == EXPECTED_SHA256, "run marker candidate checksum mismatch")
    _require(marker.get("single_instance_key") == EXPECTED_INSTANCE_KEY, "run marker instance key mismatch")
    _require(
        os.environ.get("ANKI_SINGLE_INSTANCE_KEY") == EXPECTED_INSTANCE_KEY,
        "process did not inherit the unique single-instance key",
    )
    compared: list[str] = []
    with zipfile.ZipFile(candidate) as archive:
        bad_member = archive.testzip()
        _require(bad_member is None, "candidate archive integrity failure: {}".format(bad_member))
        members = sorted(info.filename for info in archive.infolist() if not info.is_dir())
        _require(len(members) == 24, "candidate archive member count is not 24")
        for member in members:
            installed = ADDON_ROOT / member
            _require(installed.is_file(), "installed candidate member is missing: {}".format(member))
            _require(
                hashlib.sha256(archive.read(member)).hexdigest() == _sha256(installed),
                "installed candidate member differs from the archive: {}".format(member),
            )
            compared.append(member)
    manifest = json.loads((ADDON_ROOT / "manifest.json").read_text(encoding="utf-8"))
    _require(manifest.get("human_version") == RELEASE, "installed manifest version is not 1.8.1")
    return {
        "candidate": str(candidate),
        "candidate_sha256": archive_sha,
        "zip_integrity": "passed",
        "member_count": len(compared),
        "installed_member_parity": "passed",
        "manifest_version": manifest.get("human_version"),
    }


def _identity_gate() -> None:
    actual_profile = str(getattr(mw.pm, "name", ""))
    collection_path = Path(str(getattr(mw.col, "path", ""))).resolve(strict=False)
    window_title = str(mw.windowTitle())
    profile_data = getattr(mw.pm, "profile", {}) or {}
    sync_auth_present = bool(
        profile_data.get("syncKey")
        or profile_data.get("sync_key")
        or profile_data.get("syncUser")
        or profile_data.get("sync_user")
    )
    auto_sync = bool(profile_data.get("autoSync", False))
    media_sync = bool(profile_data.get("syncMedia", False))

    _require(actual_profile == EXPECTED_PROFILE, "isolated profile name mismatch")
    _require(
        collection_path.is_relative_to(RUN_ROOT.resolve(strict=True)),
        "collection path escaped the disposable run root",
    )
    _require(ADDON_ROOT.is_relative_to(RUN_ROOT.resolve(strict=True)), "candidate add-on escaped run root")
    _require(PROBE_ROOT.is_relative_to(RUN_ROOT.resolve(strict=True)), "probe add-on escaped run root")
    _require(EXPECTED_PROFILE in window_title, "main window title does not identify the disposable profile")
    _require(not sync_auth_present, "sync credentials are present")
    _require(not auto_sync and not media_sync, "automatic or media sync is enabled")
    normal_process_present = EXPECTED_NORMAL_PID > 1
    if normal_process_present:
        _require(_normal_pid_is_alive(), "excluded normal Anki PID is no longer independently present")
    candidate = _candidate_install_identity()
    REPORT["identity"] = {
        "gated_before_window_interaction": True,
        "pid": os.getpid(),
        "excluded_normal_pid": EXPECTED_NORMAL_PID if normal_process_present else None,
        "excluded_normal_process_state": "alive-and-untouched" if normal_process_present else "none-present-at-prelaunch",
        "excluded_normal_pid_alive": _normal_pid_is_alive() if normal_process_present else False,
        "processes_are_distinct": not normal_process_present or os.getpid() != EXPECTED_NORMAL_PID,
        "run_root": str(RUN_ROOT),
        "profile": actual_profile,
        "profile_matches": True,
        "collection_path": str(collection_path),
        "collection_inside_run_root": True,
        "candidate_addon_root": str(ADDON_ROOT),
        "probe_addon_root": str(PROBE_ROOT),
        "addons_inside_run_root": True,
        "window_title": window_title,
        "window_title_matches_profile": True,
        "sync_credentials_present": False,
        "auto_sync": False,
        "media_sync": False,
        "sync_identity": "disabled-and-disconnected",
        "single_instance_key_fingerprint": hashlib.sha256(
            EXPECTED_INSTANCE_KEY.encode("utf-8")
        ).hexdigest()[:12],
        "anki_version": getattr(anki, "__version__", "26.8.1"),
        "candidate": candidate,
    }


def _base_config(theme: str, mode: str, view: str) -> dict[str, Any]:
    config = normalize_config({})
    config["appearance"].update(
        preset=theme,
        mode=mode,
        opacity=100,
        text_scale=100,
    )
    config["home_screen"]["position"] = "top"
    config["heatmap"].update(
        calendar_view=view,
        week_start=0,
        history_days=0,
        forecast_days=90,
        show_due_forecast=True,
    )
    return config


def _relation(iso: str) -> DayRelation:
    if iso < REFERENCE_DATE:
        return DayRelation.PAST
    if iso > REFERENCE_DATE:
        return DayRelation.FUTURE
    return DayRelation.CURRENT


def _ensure_day(snapshot: DashboardSnapshot, iso: str) -> DayFacts:
    existing = snapshot.facts.days.get(iso)
    if existing is not None:
        return existing
    return DayFacts(
        date=iso,
        scheduling_date=REFERENCE_DATE,
        relation=_relation(iso),
        reviews_completed=(
            ValueState.available(0)
            if iso <= REFERENCE_DATE
            else ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE)
        ),
        new_cards_studied=(
            ValueState.available(0)
            if iso <= REFERENCE_DATE
            else ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE)
        ),
        reviews_due=(
            ValueState.available(0)
            if iso >= REFERENCE_DATE
            else ValueState.unavailable(AvailabilityReason.FORECAST_OUT_OF_RANGE)
        ),
        again_count=(
            ValueState.available(0)
            if iso <= REFERENCE_DATE
            else ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE)
        ),
        events=ValueState.available(()),
        browse_target=BrowseTarget(),
        domain_state=DayDomainState.NO_DUE,
    )


def _events_snapshot(selected: str, *, selected_has_events: bool) -> DashboardSnapshot:
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    selected_events: tuple[EventItem, ...] = ()
    if selected_has_events:
        selected_events = (
            EventItem(
                "selected-one",
                "Comprehensive Pediatrics Board Review and Longitudinal Planning Conference",
                selected,
                (date.fromisoformat(selected) - date.fromisoformat(REFERENCE_DATE)).days,
            ),
            EventItem(
                "selected-two",
                "Second event on the selected date",
                selected,
                (date.fromisoformat(selected) - date.fromisoformat(REFERENCE_DATE)).days,
            ),
        )
    next_event = EventItem("global-next", "Next global study milestone", "2026-08-25", 2)
    all_events = selected_events + (next_event,)
    days = dict(snapshot.facts.days)
    if selected_events:
        selected_day = _ensure_day(snapshot, selected)
        days[selected] = replace(selected_day, events=ValueState.available(selected_events))
    next_day = _ensure_day(snapshot, next_event.date)
    days[next_event.date] = replace(next_day, events=ValueState.available((next_event,)))
    return replace(
        snapshot,
        facts=replace(snapshot.facts, events=ValueState.available(all_events), days=days),
    )


def _combined_today_snapshot() -> DashboardSnapshot:
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    today = _ensure_day(snapshot, REFERENCE_DATE)
    event = EventItem("today-event", "Learning checkpoint", REFERENCE_DATE, 0)
    days = dict(snapshot.facts.days)
    days[REFERENCE_DATE] = replace(
        today,
        reviews_completed=ValueState.available(60),
        new_cards_studied=ValueState.available(12),
        reviews_due=ValueState.available(31),
        again_count=ValueState.available(3),
        events=ValueState.available((event,)),
        browse_target=BrowseTarget(BrowseTargetKind.REVIEWED, "rated:1", True, ()),
        domain_state=DayDomainState.TROUBLE,
    )
    return replace(
        snapshot,
        facts=replace(
            snapshot.facts,
            today=ValueState.available(TodayStats(60, 12, 1_860, 31.0)),
            queue=ValueState.available(QueueStats(14, 1, 16, 31, 1_220)),
            events=ValueState.available((event,)),
            days=days,
        ),
    )


def _complete_snapshot() -> DashboardSnapshot:
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    today = _ensure_day(snapshot, REFERENCE_DATE)
    days = dict(snapshot.facts.days)
    days[REFERENCE_DATE] = replace(
        today,
        reviews_completed=ValueState.available(120),
        new_cards_studied=ValueState.available(18),
        reviews_due=ValueState.available(42),
        again_count=ValueState.available(4),
        browse_target=BrowseTarget(BrowseTargetKind.REVIEWED, "rated:1", True, ()),
        domain_state=DayDomainState.TROUBLE,
    )
    return replace(
        snapshot,
        facts=replace(
            snapshot.facts,
            today=ValueState.available(TodayStats(120, 18, 3_060, 25.5)),
            queue=ValueState.available(QueueStats(0, 0, 0, 0, 0)),
            days=days,
        ),
    )


def _stress_snapshot() -> DashboardSnapshot:
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    january = EventItem("year-january", "January boundary event", "2026-01-02", -233)
    december = EventItem("year-december", "December boundary event", "2026-12-29", 128)
    days = dict(snapshot.facts.days)
    for event, completed, due in ((january, 901, 0), (december, 0, 9876)):
        base = _ensure_day(snapshot, event.date)
        days[event.date] = replace(
            base,
            reviews_completed=(
                ValueState.available(completed)
                if event.date <= REFERENCE_DATE
                else ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE)
            ),
            reviews_due=(
                ValueState.available(due)
                if event.date >= REFERENCE_DATE
                else ValueState.unavailable(AvailabilityReason.FORECAST_OUT_OF_RANGE)
            ),
            events=ValueState.available((event,)),
            domain_state=DayDomainState.FUTURE_DUE if due else DayDomainState.TROUBLE,
        )
    return replace(
        snapshot,
        facts=replace(
            snapshot.facts,
            today=ValueState.available(TodayStats(12_486, 1_048, 313_000, 25.1)),
            queue=ValueState.available(QueueStats(3_200, 1, 7_800, 11_001, 89_000)),
            buried=ValueState.available(BuriedStats(120, 80, 640)),
            events=ValueState.available((january, december)),
            last_seven_days=ValueState.available(
                LastSevenDaysStats(
                    cards_studied=98_765,
                    new_cards_studied=8_765,
                    retention=RateMetric.from_counts(90_864, 98_765),
                    again_rate=RateMetric.from_counts(7_901, 98_765),
                )
            ),
            long_term=ValueState.available(
                LongTermStats(
                    average_reviews_per_active_day=12_486,
                    active_days_percent=99,
                    longest_streak=1_517,
                    current_streak=1_024,
                    lifetime_retention=RateMetric.from_counts(974_376, 1_082_640),
                    lifetime_cards_studied=1_082_640,
                )
            ),
            due_load_reference=9876.0,
            days=days,
        ),
        verse=VerseContent(
            "The steadfast love of the Lord never ceases; his mercies never come to an end; "
            "they are new every morning; great is your faithfulness, and your loving care "
            "continues through every season of patient study and service.",
            "Lamentations 3:22-23",
        ),
    )


def _fixture(case: Mapping[str, Any]) -> DashboardSnapshot:
    fixture = str(case.get("fixture", "populated"))
    if fixture == "fresh":
        _require(_live_snapshot is not None, "live fresh snapshot is unavailable")
        return _live_snapshot
    if fixture == "combined-today":
        return _combined_today_snapshot()
    if fixture == "selected-event":
        return _events_snapshot("2026-08-27", selected_has_events=True)
    if fixture == "next-event-future":
        return _events_snapshot("2026-08-29", selected_has_events=False)
    if fixture in {"very-large", "year-boundaries"}:
        return _stress_snapshot()
    if fixture == "complete":
        return _complete_snapshot()
    if fixture == "failure":
        return unavailable_snapshot(
            verse=VerseContent("The Lord is my strength and my song.", "Psalm 118:14"),
            scheduling_date=REFERENCE_DATE,
            day_cutoff_iso="2026-08-24T04:00-05:00",
            revision="release-probe-failure",
        )
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    if fixture == "long-verse":
        snapshot = replace(
            snapshot,
            verse=VerseContent(
                "Trust in the Lord with all your heart and lean not on your own understanding; "
                "in all your ways acknowledge him, and he will make your paths straight, even "
                "through long seasons of careful learning, review, reflection, and service.",
                "Proverbs 3:5-6",
            ),
        )
    return snapshot


def _case(
    case_id: str,
    theme: str,
    mode: str,
    view: str,
    *,
    fixture: str = "populated",
    layout: str = "wide",
    selected: str = REFERENCE_DATE,
    tags: Iterable[str] = (),
    special: str = "",
    week_start: int = 0,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "theme": theme,
        "mode": mode,
        "view": view,
        "fixture": fixture,
        "layout": layout,
        "selected": selected,
        "tags": list(tags),
        "special": special,
        "week_start": week_start,
        "ui_scale_percent": 100,
        "text_scale_percent": 100,
    }


def _build_initial_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    prefixes = {
        "Sapphire Glass": "SG",
        "Graphite": "GR",
        "Emerald": "EM",
        "High Contrast": "HC",
    }
    for theme in ("Sapphire Glass", "Graphite", "Emerald", "High Contrast"):
        for mode in ("light", "dark"):
            for view in ("month", "year"):
                cases.append(_case(
                    "PRIMARY-{}-{}-{}".format(prefixes[theme], "L" if mode == "light" else "D", "M" if view == "month" else "Y"),
                    theme,
                    mode,
                    view,
                    tags=("primary_native", "populated_data"),
                ))

    cases.extend((
        _case("FRESH-SG-L-M", "Sapphire Glass", "light", "month", fixture="fresh", tags=("fresh_data", "no_cards_due", "missing_pace_eta", "missing_retention", "zero_lifetime")),
        _case("FRESH-SG-L-Y", "Sapphire Glass", "light", "year", fixture="fresh", tags=("fresh_data", "empty_year")),
        _case("FRESH-SG-D-M", "Sapphire Glass", "dark", "month", fixture="fresh", tags=("fresh_data", "short_verse")),
        _case("FRESH-SG-D-Y", "Sapphire Glass", "dark", "year", fixture="fresh", tags=("fresh_data", "empty_year")),
        _case("RESP-SG-L-INTERMEDIATE", "Sapphire Glass", "light", "month", layout="intermediate", tags=("responsive",)),
        _case("RESP-SG-D-INTERMEDIATE", "Sapphire Glass", "dark", "year", layout="intermediate", tags=("responsive",)),
        _case("RESP-SG-L-NARROW", "Sapphire Glass", "light", "month", layout="narrow", tags=("responsive", "no_horizontal_scroll")),
        _case("RESP-SG-D-NARROW", "Sapphire Glass", "dark", "year", layout="narrow", tags=("responsive", "no_horizontal_scroll")),
        _case("RESP-HC-L-NARROW", "High Contrast", "light", "month", layout="narrow", tags=("responsive", "no_horizontal_scroll")),
        _case("RESP-HC-D-NARROW", "High Contrast", "dark", "year", layout="narrow", tags=("responsive", "no_horizontal_scroll")),
        _case("STATE-COMBINED-TODAY", "Sapphire Glass", "dark", "month", fixture="combined-today", tags=("combined_state_markers", "today_completed_with_due", "one_learning_card", "partial_progress", "reviewed_cards_action")),
        _case("STATE-SELECTED-EVENT", "Sapphire Glass", "light", "month", fixture="selected-event", selected="2026-08-27", tags=("event_on_selected_date", "event_count", "multiple_events", "footer_relationships", "footer_edit_action")),
        _case("STATE-NEXT-EVENT-FUTURE", "Graphite", "dark", "month", fixture="next-event-future", selected="2026-08-29", tags=("next_event", "future_selected", "due_cards_action")),
        _case("STATE-PAST-TOOLTIP", "Emerald", "light", "month", selected="2026-08-15", tags=("calendar_tooltip", "selected_past", "historical_wording"), special="tooltip"),
        _case("STATE-FIVE-ROW-SUNDAY", "Sapphire Glass", "light", "month", selected="2026-04-15", tags=("five_row_month", "sunday_start"), week_start=6),
        _case("STATE-SIX-ROW-MONDAY", "Sapphire Glass", "dark", "month", fixture="very-large", selected="2026-08-15", tags=("six_row_month", "monday_start", "very_large_counts", "large_streak"), week_start=0),
        _case("STATE-YEAR-BOUNDARIES", "High Contrast", "dark", "year", fixture="year-boundaries", tags=("populated_year", "year_boundaries", "year_weekday_references")),
        _case("STATE-COMPLETE-METRICS", "Sapphire Glass", "dark", "month", fixture="complete", tags=("complete_progress", "eta_done_positive_workload", "populated_rates")),
        _case("BACKGROUND-SG-L", "Sapphire Glass", "light", "month", tags=("background_case", "conditional_scrim"), special="background"),
        _case("BACKGROUND-SG-D", "Sapphire Glass", "dark", "year", tags=("background_case", "conditional_scrim"), special="background"),
        _case("BACKGROUND-EM-L", "Emerald", "light", "month", tags=("background_case", "conditional_scrim"), special="background"),
        _case("BACKGROUND-EM-D", "Emerald", "dark", "year", tags=("background_case", "conditional_scrim"), special="background"),
        _case("BACKGROUND-REDUCED-OPACITY", "Graphite", "dark", "month", tags=("background_case", "reduced_opacity", "text_readability"), special="background-opacity"),
        _case("BIBLE-SHORT", "Sapphire Glass", "light", "month", tags=("bible_case", "short_verse")),
        _case("BIBLE-LONG", "Sapphire Glass", "dark", "month", fixture="long-verse", tags=("bible_case", "long_verse", "no_truncation")),
        _case("BIBLE-CUSTOM-FONT", "Emerald", "light", "year", tags=("bible_case", "custom_font"), special="custom-font"),
        _case("BIBLE-DISABLED", "High Contrast", "dark", "year", tags=("bible_case", "bible_disabled", "no_bible_gap"), special="bible-disabled"),
        _case("RUNTIME-INITIAL-LOADING", "Sapphire Glass", "light", "month", fixture="loading", tags=("runtime_state", "initial_loading"), special="loading-initial"),
        _case("RUNTIME-DELAYED-LOADING", "Sapphire Glass", "dark", "month", fixture="loading", tags=("runtime_state", "delayed_loading"), special="loading-delayed"),
        _case("RUNTIME-FAILURE", "High Contrast", "light", "month", fixture="loading", tags=("runtime_state", "loading_failure"), special="loading-failure"),
        _case("RUNTIME-RETRY", "High Contrast", "dark", "year", tags=("runtime_state", "retry"), special="retry-loaded"),
    ))
    return cases


def _restart_case(observed_view: str = "month") -> dict[str, Any]:
    return _case(
        "RUNTIME-RESTART-PERSISTENCE",
        "Graphite",
        "dark",
        observed_view,
        tags=("runtime_state", "restart", "settings_persistence", "calendar_view_persistence_mismatch_user_waived", "theme_persistence", "palette_persistence", "visibility_persistence", "clean_settings_state"),
        special="restart",
    )


def _config_for(case: Mapping[str, Any]) -> dict[str, Any]:
    config = _base_config(str(case["theme"]), str(case["mode"]), str(case["view"]))
    config["heatmap"]["week_start"] = int(case.get("week_start", 0))
    special = str(case.get("special", ""))
    if special == "background-opacity":
        config["appearance"]["opacity"] = 70
    if special == "custom-font":
        config["bible"]["font_family"] = "Avenir Next, sans-serif"
        config["bible"]["font_size"] = "36px"
    if special == "bible-disabled" or special == "restart":
        config["visibility"]["bible"] = False
    if special == "restart":
        config["appearance"]["opacity"] = 92
        config["heatmap"]["presets_by_theme"]["Graphite"] = "Steel"
    return config


def _target_frame(case: Mapping[str, Any]) -> tuple[int, int]:
    screen = mw.screen() or QApplication.primaryScreen()
    _require(screen is not None, "no Qt screen is available")
    available = screen.availableGeometry()
    layout = str(case.get("layout", "wide"))
    if layout == "intermediate":
        return min(1120, available.width()), min(940, available.height())
    if layout == "narrow":
        return min(620, available.width()), min(980, available.height())
    return available.width(), available.height()


def _fit_native_frame(case: Mapping[str, Any], continuation: Any, attempt: int = 0) -> None:
    try:
        screen = mw.screen() or QApplication.primaryScreen()
        _require(screen is not None, "no Qt screen is available")
        available = screen.availableGeometry()
        target_width, target_height = _target_frame(case)
        mw.showNormal()
        frame = mw.frameGeometry()
        width_delta = target_width - frame.width()
        height_delta = target_height - frame.height()
        if width_delta or height_delta:
            mw.resize(max(420, mw.width() + width_delta), max(620, mw.height() + height_delta))
        frame = mw.frameGeometry()
        target_x = available.x() + max(0, (available.width() - target_width) // 2)
        target_y = available.y() + max(0, (available.height() - target_height) // 2)
        mw.move(mw.x() + target_x - frame.x(), mw.y() + target_y - frame.y())
        mw.raise_()
        mw.activateWindow()
        QApplication.processEvents()
        frame = mw.frameGeometry()
        if (abs(frame.width() - target_width) > 1 or abs(frame.height() - target_height) > 1) and attempt < 5:
            QTimer.singleShot(160, lambda: _fit_native_frame(case, continuation, attempt + 1))
            return
        _require(abs(frame.width() - target_width) <= 1, "native frame width did not settle")
        _require(abs(frame.height() - target_height) <= 1, "native frame height did not settle")
        continuation()
    except Exception as exc:
        _error(str(case.get("id", "frame")), exc)


def _mount_case(case: dict[str, Any]) -> None:
    global _active_case
    _active_case = case
    try:
        config = _config_for(case)
        _controller.config = config
        _controller.selected_date = str(case.get("selected", REFERENCE_DATE))
        _controller.selection_follows_today = _controller.selected_date == REFERENCE_DATE
        special = str(case.get("special", ""))
        if str(case.get("fixture")) == "loading" or special == "retry-loaded":
            key = _controller._key()
            _controller.snapshot = None
            _controller.cache_key = None
            _controller.inflight_key = key
        else:
            snapshot = _fixture(case)
            _controller.snapshot = snapshot
            _controller.cache_key = _controller._key()
            _controller.inflight_key = None
            _controller.facts_revision += 1
        mw.deckBrowser.refresh()
        if special == "retry-loaded":
            QTimer.singleShot(12350, lambda: _trigger_retry(case))
            return
        delay = {
            "loading-initial": 450,
            "loading-delayed": 2850,
            "loading-failure": 12350,
        }.get(str(case.get("special", "")), 500)
        QTimer.singleShot(delay, lambda: _poll_case(case, 0))
    except Exception as exc:
        _error(str(case.get("id", "mount")), exc)


def _trigger_retry(case: dict[str, Any]) -> None:
    """Exercise the mounted Retry control, then wait for the live query result."""

    try:
        web = mw.deckBrowser.web
        script = (
            "(function(){var root=document.getElementById('hdo-dashboard');"
            "var failure=root&&root.querySelector('[data-hdo-loading-failure]');"
            "var retry=root&&root.querySelector('[data-hdo-command=\"retry\"]');"
            "var visible=!!failure&&!failure.hidden;"
            "if(retry){retry.click();}"
            "return {failureVisibleBeforeRetry:visible,retryControlPresent:!!retry};})()"
        )

        def clicked(value: object) -> None:
            try:
                transition = value if isinstance(value, dict) else {}
                _require(bool(transition.get("failureVisibleBeforeRetry")), "Retry was not exercised from the visible failure state")
                _require(bool(transition.get("retryControlPresent")), "Retry control was missing")
                REPORT.setdefault("runtime_transitions", {})[str(case["id"])] = {
                    **transition,
                    "bridge_command_dispatched": True,
                    "result_expected": "live collection snapshot remounted",
                }
                _write_report()
                QTimer.singleShot(350, lambda: _poll_case(case, 0))
            except Exception as exc:
                _error(str(case.get("id", "retry")), exc)

        web.evalWithCallback(script, clicked)
    except Exception as exc:
        _error(str(case.get("id", "retry")), exc)


def _prepare_dom(case: Mapping[str, Any], callback: Any) -> None:
    special = str(case.get("special", ""))
    scripts: list[str] = []
    if special in {"background", "background-opacity"}:
        scripts.append(
            "document.body.style.backgroundImage='linear-gradient(135deg,#17365f 0%,#6a3b73 52%,#d59a3a 100%)';"
            "var r=document.getElementById('hdo-dashboard');"
            "if(r){r.dataset.hdoQaBackgroundImage='true';"
            "if(globalThis.HDOCalendarModel){globalThis.HDOCalendarModel.applyDocumentTheme(r);}}"
        )
    if special == "tooltip":
        scripts.append(
            "var c=document.querySelector('.hdo-calendar-day[data-date=\"2026-08-15\"]');"
            "if(c){c.dispatchEvent(new PointerEvent('pointerover',{bubbles:true,relatedTarget:null,clientX:c.getBoundingClientRect().left+4,clientY:c.getBoundingClientRect().top+4}));}"
        )
    if not scripts:
        callback()
        return
    web = mw.deckBrowser.web
    web.eval("(function(){" + "".join(scripts) + "})()")
    QTimer.singleShot(180, callback)


DOM_REPORT_SCRIPT = r"""
(function () {
  var root = document.getElementById('hdo-dashboard');
  if (!root) return {ready:false};
  function q(selector) { return root.querySelector(selector); }
  function qa(selector) { return Array.from(root.querySelectorAll(selector)); }
  function rect(node) {
    if (!node) return null;
    var r = node.getBoundingClientRect();
    return {left:+r.left.toFixed(2),top:+r.top.toFixed(2),right:+r.right.toFixed(2),bottom:+r.bottom.toFixed(2),width:+r.width.toFixed(2),height:+r.height.toFixed(2)};
  }
  function visible(node) { return !!node && !node.hidden && getComputedStyle(node).display !== 'none'; }
  function bands(nodes, key) { return Array.from(new Set(nodes.map(function(n){return Math.round(n.getBoundingClientRect()[key]);}))).length; }
  function text(selector) { var n=q(selector); return n ? n.textContent.trim() : ''; }
  var loading = root.classList.contains('hdo-dashboard--loading');
  var layout=q('.hdo-dashboard-layout');
  var calendar=q('.hdo-calendar-card');
  var rail=q('.hdo-insight-rail');
  var metrics=q('.hdo-summary-metrics-grid');
  var cards=qa('.hdo-statistics-card');
  var bible=q('.hdo-bible-card');
  var cells=qa('.hdo-calendar-day');
  var monthCells=qa('.hdo-calendar-grid--month .hdo-calendar-day');
  var yearCells=qa('.hdo-calendar-grid--year .hdo-calendar-day');
  var selected=qa('.hdo-calendar-day.is-selected');
  var today=qa('.hdo-calendar-day.is-today');
  var combined=qa('.hdo-calendar-day.is-selected.is-today[data-due-level]:not([data-due-level="0"])');
  var tooltip=q('.hdo-calendar-tooltip');
  var frame=q('.hdo-calendar-grid-frame');
  var yearContent=q('.hdo-year-heatmap-content');
  var grid=q('.hdo-calendar-grid');
  var cardRects=cards.map(rect);
  var rowLabels={};
  ['progress','session','recent','lifetime'].forEach(function(key){
    rowLabels[key]=qa('.hdo-'+key+'-card .hdo-metric-row dt').map(function(n){return n.textContent.trim();});
  });
  var zeroSemantic=qa('.hdo-metric-row').filter(function(row){
    var value=row.querySelector('dd');
    return value && value.textContent.trim()==='0' && /hdo-value--(new|learning|review|buried|success|warning|danger)/.test(row.className);
  });
  var eventCount=q('.hdo-event-marker > span');
  var selectedStyle=selected.length ? getComputedStyle(selected[0]) : null;
  var rootStyle=getComputedStyle(root);
  var pseudo=getComputedStyle(root,'::before');
  var monthStyle=monthCells.length ? getComputedStyle(q('.hdo-calendar-grid--month')) : null;
  var yearStyle=yearCells.length ? getComputedStyle(q('.hdo-calendar-grid--year')) : null;
  return {
    ready:true,
    loading:loading,
    loadingMessage:text('[data-hdo-loading-message]'),
    loadingFailureVisible:visible(q('[data-hdo-loading-failure]')),
    loadingSkeletonVisible:visible(q('[data-hdo-loading-skeleton]')),
    theme:root.dataset.hdoTheme || '',
    mode:root.dataset.hdoColorMode || '',
    view:root.dataset.hdoCalendarView || '',
    viewport:{width:window.innerWidth,height:window.innerHeight},
    devicePixelRatio:window.devicePixelRatio,
    root:rect(root),layout:rect(layout),calendar:rect(calendar),rail:rect(rail),metrics:rect(metrics),bible:rect(bible),frame:rect(frame),grid:rect(grid),yearContent:rect(yearContent),tooltip:rect(tooltip),
    rootMarginTop:rootStyle.marginTop,
    rootBackground:rootStyle.backgroundColor,
    backgroundImageDetected:root.dataset.hdoBackgroundImage || '',
    scrimContent:pseudo.content,
    scrimBackground:pseudo.backgroundColor,
    documentOverflowX:document.documentElement.scrollWidth-document.documentElement.clientWidth,
    bodyOverflowX:document.body.scrollWidth-document.body.clientWidth,
    layoutSideBySide:!!calendar&&!!rail&&rect(calendar).right<=rect(rail).left+1,
    layoutStacked:!!calendar&&!!rail&&rect(calendar).bottom<=rect(rail).top+1,
    layoutGap:!!calendar&&!!rail?(rect(rail).left>=rect(calendar).right?rect(rail).left-rect(calendar).right:rect(rail).top-rect(calendar).bottom):null,
    statisticsCardCount:cards.length,
    statisticColumns:cards.length?bands(cards,'left'):0,
    statisticRows:cards.length?bands(cards,'top'):0,
    statisticCardRects:cardRects,
    statisticCardOverflow:cards.filter(function(card){return card.scrollHeight>card.clientHeight+1||card.scrollWidth>card.clientWidth+1;}).length,
    statisticCardOverflowDetails:cards.map(function(card){
      var heading=card.querySelector('h3');
      var meta=card.querySelector('.hdo-progress-complete');
      return {
        className:card.className,
        clientWidth:card.clientWidth,
        scrollWidth:card.scrollWidth,
        clientHeight:card.clientHeight,
        scrollHeight:card.scrollHeight,
        headingText:heading?heading.textContent.trim():'',
        heading:rect(heading),
        headingLineHeight:heading?getComputedStyle(heading).lineHeight:'',
        metaText:meta?meta.textContent.trim():'',
        meta:rect(meta)
      };
    }),
    statisticCardHeights:cardRects.map(function(r){return r.height;}),
    statisticCardWidths:cardRects.map(function(r){return r.width;}),
    rowLabels:rowLabels,
    zeroSemanticCount:zeroSemantic.length,
    unavailableCount:qa('.hdo-metric-row.is-unavailable dd').filter(function(n){return n.textContent.trim()==='—';}).length,
    progressState:(q('[data-hdo-progress-state]')||{}).dataset ? q('[data-hdo-progress-state]').dataset.hdoProgressState : '',
    progressText:text('[data-hdo-metric="progress.percent"]'),
    etaText:text('[data-hdo-metric="queue.eta"]'),
    newText:text('[data-hdo-metric="queue.new"]'),
    learningText:text('[data-hdo-metric="queue.learning"]'),
    reviewText:text('[data-hdo-metric="queue.review"]'),
    monthRows:monthCells.length?bands(monthCells,'top'):0,
    calendarCellCount:cells.length,
    monthCellHeights:monthCells.slice(0,7).map(function(n){return rect(n).height;}),
    monthColumnGap:monthStyle?monthStyle.columnGap:'',
    monthRowGap:monthStyle?monthStyle.rowGap:'',
    yearCellWidth:yearCells.length?rect(yearCells[Math.min(40,yearCells.length-1)]).width:0,
    yearCellHeight:yearCells.length?rect(yearCells[Math.min(40,yearCells.length-1)]).height:0,
    yearColumnGap:yearStyle?yearStyle.columnGap:'',
    yearRowGap:yearStyle?yearStyle.rowGap:'',
    yearWeekdayLabels:qa('.hdo-year-weekday-label').map(function(n){return n.textContent.trim();}),
    yearMonthLabels:qa('.hdo-year-month-label').map(function(n){return n.textContent.trim();}),
    frameOverflowX:frame?frame.scrollWidth-frame.clientWidth:0,
    selectedCount:selected.length,
    todayCount:today.length,
    selectedOutlineWidth:selectedStyle?selectedStyle.outlineWidth:'',
    selectedOutlineOffset:selectedStyle?selectedStyle.outlineOffset:'',
    combinedStateCount:combined.length,
    dueLevels:Array.from(new Set(cells.map(function(n){return n.dataset.dueLevel||'0';}))).sort(),
    eventMarkerCount:qa('.hdo-event-marker').length,
    eventCountText:eventCount?eventCount.textContent.trim():'',
    contextEventLabel:text('[data-hdo-context-event-label]'),
    contextEventTitle:text('[data-hdo-open-events]'),
    contextEventMeta:text('[data-hdo-event-meta]'),
    editEventVisible:visible(q('[data-hdo-edit-event]')),
    primaryActionText:text('[data-hdo-primary-action]'),
    primaryActionVisible:visible(q('[data-hdo-primary-action]')),
    legendText:text('.hdo-calendar-legend'),
    dueLegendCount:qa('.hdo-due-legend i').length,
    tooltipVisible:visible(tooltip),
    tooltipHeading:text('[data-hdo-tooltip-heading]'),
    biblePresent:!!bible,
    bibleHeight:bible?rect(bible).height:0,
    bibleFont:bible?getComputedStyle(q('.hdo-verse')).fontFamily:'',
    bibleFontSize:bible?getComputedStyle(q('.hdo-verse')).fontSize:'',
    bibleOverflow:bible?bible.scrollHeight>bible.clientHeight+1:false,
    railHasBible:rail?rail.dataset.hdoHasBible:'',
    railChildCount:rail?rail.children.length:0,
    titleText:text('[data-hdo-calendar-title]')
  };
})()
"""


def _validate_dom(case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    _require(bool(state.get("ready")), "Deck Browser dashboard did not mount")
    special = str(case.get("special", ""))
    if special.startswith("loading-"):
        _require(bool(state.get("loading")), "loading shell was not mounted")
        if special == "loading-initial":
            _require(bool(state.get("loadingSkeletonVisible")), "initial loading skeleton is hidden")
            _require(not state.get("loadingMessage"), "initial loading message changed too early")
        elif special == "loading-delayed":
            _require(state.get("loadingMessage") == "Still loading your study data…", "delayed loading wording missing")
        elif special == "loading-failure":
            _require(bool(state.get("loadingFailureVisible")), "loading failure controls are hidden")
        return

    _require(not bool(state.get("loading")), "dashboard remained in loading state")
    _require(state.get("theme") == case.get("theme"), "theme identity mismatch")
    _require(state.get("mode") == case.get("mode"), "color mode identity mismatch")
    _require(state.get("view") == case.get("view"), "calendar view identity mismatch")
    _require(int(state.get("statisticsCardCount", 0)) == 4, "statistics rail does not have four cards")
    _require(int(state.get("statisticCardOverflow", 0)) == 0, "statistics content overflows a card")
    _require(state.get("rowLabels", {}).get("session") == ["Cards studied", "New cards studied", "Time", "Pace", "ETA"], "Today Session rows are unstable")
    _require(state.get("rowLabels", {}).get("recent") == ["Cards studied", "New cards studied", "Retention", "Again rate"], "Last 7 Days rows are unstable")
    _require(state.get("rowLabels", {}).get("lifetime") == ["Avg cards/day", "Current streak", "Longest streak", "Lifetime retention", "Lifetime cards studied"], "All Time rows are unstable")
    _require(int(state.get("zeroSemanticCount", 0)) == 0, "zero metric received semantic category color")
    _require(float(state.get("documentOverflowX", 0)) <= 1, "document has horizontal overflow")
    viewport = state.get("viewport") or {}
    root = state.get("root") or {}
    _require(float(root.get("left", -1)) >= -1, "dashboard escaped the viewport on the left")
    _require(float(root.get("right", 10**9)) <= float(viewport.get("width", 0)) + 1, "dashboard escaped the viewport on the right")
    _require(int(state.get("dueLegendCount", 0)) == 3, "due legend does not expose three levels")
    _require("Completed reviews" in str(state.get("legendText", "")), "completion legend wording is stale")
    _require("Low" in str(state.get("legendText", "")) and "High" in str(state.get("legendText", "")), "due legend endpoints are missing")
    _require(int(state.get("selectedCount", 0)) == 1, "calendar selection is not exactly one cell")
    _require(state.get("selectedOutlineWidth") == "2px", "selection is not exactly one 2px outline")
    _require(set(state.get("dueLevels", [])) <= {"0", "1", "2", "3"}, "visible due level escaped 0-3")

    layout = str(case.get("layout", "wide"))
    calendar = state.get("calendar") or {}
    rail = state.get("rail") or {}
    widths = [float(value) for value in state.get("statisticCardWidths", [])]
    heights = [float(value) for value in state.get("statisticCardHeights", [])]
    if layout == "wide":
        _require(bool(state.get("layoutSideBySide")), "wide dashboard did not remain side by side")
        _require(1440 <= float(root.get("width", 0)) <= 1481, "wide root is outside the 1450-1500 target")
        _require(995 <= float(calendar.get("width", 0)) <= 1035, "wide calendar is outside the 1000-1030 target")
        _require(430 <= float(rail.get("width", 0)) <= 451, "wide rail is outside the 430-450 target")
        _require(all(209 <= value <= 221 for value in widths), "wide statistics cards are outside the 210-220 target")
        _require(int(state.get("statisticColumns", 0)) == 2 and int(state.get("statisticRows", 0)) == 2, "wide statistics rail is not 2 by 2")
        _require(all(value >= 146 for value in heights), "statistics cards are shorter than 146px")
        _require(max(heights) - min(heights) <= 1, "statistics cards have mismatched external heights")
        _require(15 <= float(state.get("layoutGap", 0)) <= 17, "wide layout gap is not 16px")
    elif layout == "intermediate":
        _require(bool(state.get("layoutStacked")), "intermediate dashboard did not stack the rail")
        _require(int(state.get("statisticColumns", 0)) == 2, "intermediate statistics rail lost two columns")
        _require(min(widths) >= 250, "intermediate statistics card is below 250px")
    else:
        _require(bool(state.get("layoutStacked")), "narrow dashboard did not stack")
        _require(int(state.get("statisticColumns", 0)) == 1, "narrow statistics cards are not one per row")
        _require(max(heights) - min(heights) <= 0.2, "narrow statistics cards have mismatched external heights")

    if case.get("view") == "month":
        month_heights = [float(value) for value in state.get("monthCellHeights", [])]
        _require(month_heights and all(42 <= value <= 50 for value in month_heights), "Month cell height escaped 42-50px")
        _require(state.get("monthColumnGap") in {"4px", "5px"}, "Month column gap escaped 4-5px")
        _require(state.get("monthRowGap") in {"4px", "5px"}, "Month row gap escaped 4-5px")
    else:
        _require(int(state.get("calendarCellCount", 0)) in {365, 366}, "Year view is incomplete")
        _require(state.get("yearWeekdayLabels") == ["Mon", "Wed", "Fri"], "Year weekday reference nodes are missing")
        _require(state.get("yearMonthLabels") == ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], "Year month labels are incomplete")
        _require(float(state.get("frameOverflowX", 0)) <= 1, "Year view scrolls horizontally")
        if layout == "wide":
            _require(13.0 <= float(state.get("yearCellWidth", 0)) <= 15.2, "wide Year cells are not approximately 14px")
            year_content = state.get("yearContent") or {}
            _require(float(year_content.get("width", 0)) <= 941, "Year heatmap wrapper exceeds 940px")

    if special in {"background", "background-opacity"}:
        _require(state.get("backgroundImageDetected") == "true", "conditional background scrim was not activated")
        _require(state.get("scrimContent") not in {"none", "normal", ""}, "background scrim pseudo-surface is absent")
    else:
        _require(state.get("backgroundImageDetected") != "true", "default host received a false background-image scrim")
        _require(state.get("rootBackground") in {"rgba(0, 0, 0, 0)", "transparent"}, "default dashboard root paints a global canvas")

    if case.get("fixture") == "fresh" and case.get("view") == "month":
        _require(state.get("progressState") == "no_cards_due", "fresh workload is not classified as no cards due")
        _require(state.get("progressText") == "No cards due", "fresh workload wording is incorrect")
        _require(state.get("etaText") == "—", "fresh ETA is not unavailable")
    if case.get("fixture") == "combined-today":
        _require(int(state.get("combinedStateCount", 0)) == 1, "today/completion/due/selection states did not coexist")
        _require(state.get("learningText") == "1", "one-learning-card fixture changed")
        _require(state.get("progressState") == "in_progress", "partial workload classification changed")
        _require(state.get("primaryActionText") == "Reviewed cards", "historical/today action label changed")
    if case.get("fixture") == "complete":
        _require(state.get("progressState") == "complete" and state.get("progressText") == "100%", "complete workload wording changed")
        _require(state.get("etaText") == "Done", "positive completed workload does not show Done")
    if case.get("fixture") == "selected-event":
        _require(state.get("contextEventLabel") == "Event on this date", "selected-date event did not take precedence")
        _require(state.get("eventCountText") == "2", "multiple-event count treatment is missing")
        _require(bool(state.get("editEventVisible")), "selected event edit affordance is hidden")
    if case.get("fixture") == "next-event-future":
        _require(state.get("contextEventLabel") == "Next event", "global next event relationship is incorrect")
        _require(state.get("primaryActionText") == "Due cards", "future action label changed")
    if special == "tooltip":
        tooltip = state.get("tooltip") or {}
        viewport = state.get("viewport") or {}
        _require(bool(state.get("tooltipVisible")), "delegated calendar tooltip is not visible")
        _require(220 <= float(tooltip.get("width", 0)) <= 260, "calendar tooltip width escaped 220-260px")
        _require(float(tooltip.get("left", -1)) >= 0 and float(tooltip.get("right", 10**9)) <= float(viewport.get("width", 0)), "tooltip escaped viewport horizontally")
        _require(float(tooltip.get("top", -1)) >= 0 and float(tooltip.get("bottom", 10**9)) <= float(viewport.get("height", 0)), "tooltip escaped viewport vertically")
        _require("Reviewed" in str(state.get("tooltipHeading", "")) or "Aug" in str(state.get("tooltipHeading", "")), "historical tooltip wording is absent")
    if case.get("id") == "STATE-FIVE-ROW-SUNDAY":
        _require(int(state.get("monthRows", 0)) == 5, "Sunday-start fixture is not five rows")
    if case.get("id") == "STATE-SIX-ROW-MONDAY":
        _require(int(state.get("monthRows", 0)) == 6, "Monday-start fixture is not six rows")
    if special == "bible-disabled" or special == "restart":
        _require(not bool(state.get("biblePresent")), "disabled Bible card remains in layout")
        _require(state.get("railHasBible") == "false" and int(state.get("railChildCount", 0)) == 1, "disabled Bible card left a layout gap")
    elif bool(state.get("biblePresent")):
        _require(float(state.get("bibleHeight", 0)) >= 126, "Bible card is shorter than 126px")
        _require(not bool(state.get("bibleOverflow")), "Bible content overflows its card")
    if special == "custom-font":
        _require("Avenir Next" in str(state.get("bibleFont", "")), "Bible font preference was not preserved")


def _poll_case(case: dict[str, Any], attempt: int) -> None:
    try:
        web = getattr(getattr(mw, "deckBrowser", None), "web", None)
        _require(web is not None, "Deck Browser web view is unavailable")

        def inspected(value: object) -> None:
            try:
                state = value if isinstance(value, dict) else {"ready": False}
                if not state.get("ready") and attempt < 30:
                    QTimer.singleShot(200, lambda: _poll_case(case, attempt + 1))
                    return
                if str(case.get("special", "")) == "retry-loaded" and bool(state.get("loading")) and attempt < 40:
                    QTimer.singleShot(250, lambda: _poll_case(case, attempt + 1))
                    return
                _prepare_dom(case, lambda: _inspect_and_capture(case))
            except Exception as exc:
                _error(str(case.get("id", "poll")), exc)

        web.evalWithCallback(
            "(function(){var r=document.getElementById('hdo-dashboard');return r?{ready:true,loading:r.classList.contains('hdo-dashboard--loading')}:{ready:false,loading:false};})()",
            inspected,
        )
    except Exception as exc:
        _error(str(case.get("id", "poll")), exc)


def _inspect_and_capture(case: dict[str, Any], attempt: int = 0) -> None:
    try:
        web = mw.deckBrowser.web

        def inspected(value: object) -> None:
            try:
                state = value if isinstance(value, dict) else {"ready": False}
                _validate_dom(case, state)
                _capture(case, state)
                QTimer.singleShot(160, _next_case)
            except Exception as exc:
                REPORT["last_failed_case"] = {
                    "case": dict(case),
                    "dom": dict(state) if isinstance(state, dict) else {"ready": False},
                    "error": "{}: {}".format(type(exc).__name__, exc),
                }
                _write_report()
                if attempt < 8:
                    QTimer.singleShot(250, lambda: _inspect_and_capture(case, attempt + 1))
                    return
                _error(str(case.get("id", "inspect")), exc)

        web.evalWithCallback(DOM_REPORT_SCRIPT, inspected)
    except Exception as exc:
        _error(str(case.get("id", "inspect")), exc)


def _sample_color_count(pixmap: Any) -> int:
    image = pixmap.toImage()
    width = image.width()
    height = image.height()
    colors: set[int] = set()
    step_x = max(1, width // 32)
    step_y = max(1, height // 24)
    for x in range(step_x // 2, width, step_x):
        for y in range(step_y // 2, height, step_y):
            colors.add(int(image.pixel(x, y)))
            if len(colors) >= 24:
                return len(colors)
    return len(colors)


def _capture(case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    QApplication.processEvents()
    frame = mw.frameGeometry()
    screen = mw.screen() or QApplication.primaryScreen()
    _require(screen is not None, "native capture screen is unavailable")
    pixmap = screen.grabWindow(0, frame.x(), frame.y(), frame.width(), frame.height())
    method = "QScreen.grabWindow-screen-crop"
    if pixmap.isNull():
        pixmap = mw.grab()
        method = "QMainWindow.grab-fallback"
    color_count = _sample_color_count(pixmap)
    _require(color_count >= 12, "native Deck Browser capture appears blank")
    CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
    path = CAPTURE_ROOT / "{}.png".format(case["id"])
    _require(bool(pixmap.save(str(path), "PNG")), "could not save native capture")
    title = str(mw.windowTitle())
    _require(EXPECTED_PROFILE in title, "capture window title lost isolated identity")
    REPORT["captures"][str(case["id"])] = {
        "file": str(path.relative_to(OUTPUT_ROOT)),
        "sha256": _sha256(path),
        "theme": case.get("theme"),
        "mode": case.get("mode"),
        "view": case.get("view"),
        "fixture": case.get("fixture"),
        "layout": case.get("layout"),
        "tags": list(case.get("tags", [])),
        "ui_scale_percent": 100,
        "text_scale_percent": 100,
        "capture_method": method,
        "logical_frame": {
            "x": frame.x(),
            "y": frame.y(),
            "width": frame.width(),
            "height": frame.height(),
        },
        "physical_pixels": [pixmap.width(), pixmap.height()],
        "device_pixel_ratio": pixmap.devicePixelRatio(),
        "window_title": title,
        "window_title_matches_profile": True,
        "production_deck_browser_mount": True,
        "dom": dict(state),
    }
    _write_report()


def _next_case() -> None:
    global _case_index
    if _case_index >= len(_cases):
        _finish_stage()
        return
    case = _cases[_case_index]
    _case_index += 1
    _fit_native_frame(case, lambda: _mount_case(case))


def _persistence_config() -> dict[str, Any]:
    config = _base_config("Graphite", "dark", "month")
    config["appearance"]["opacity"] = 92
    config["heatmap"]["presets_by_theme"]["Graphite"] = "Steel"
    config["visibility"]["bible"] = False
    return config


def _finish_stage() -> None:
    try:
        if STAGE == "initial":
            expected_ids = {case["id"] for case in _cases}
            _require(len(expected_ids) == 47, "initial evidence matrix must contain 47 distinct frames")
            _require(set(REPORT["captures"]) == expected_ids, "initial evidence matrix is incomplete")
            persisted = _persistence_config()
            mw.addonManager.writeConfig(_controller.package, persisted)
            readback = normalize_config(mw.addonManager.getConfig(_controller.package))
            _require(readback["appearance"]["preset"] == "Graphite", "theme did not save")
            _require(readback["appearance"]["mode"] == "dark", "mode did not save")
            _require(readback["appearance"]["opacity"] == 92, "opacity did not save")
            _require(readback["heatmap"]["calendar_view"] == "month", "calendar view did not save")
            _require(readback["heatmap"]["presets_by_theme"]["Graphite"] == "Steel", "palette did not save")
            _require(readback["visibility"]["bible"] is False, "visibility did not save")
            _require("show_eta" not in readback.get("study", {}), "retired show_eta field survived save")
            REPORT["persistence_write"] = {
                "status": "passed",
                "expected_restart": {
                    "theme": "Graphite",
                    "mode": "dark",
                    "opacity": 92,
                    "calendar_view": "month",
                    "graphite_palette": "Steel",
                    "bible_visible": False,
                    "show_eta_present": False,
                },
            }
        else:
            _require(set(REPORT["captures"]) == {"RUNTIME-RESTART-PERSISTENCE"}, "restart evidence frame is missing")
        REPORT["status"] = "passed"
        _write_report()
        QTimer.singleShot(450, QApplication.instance().quit)
    except Exception as exc:
        _error("finish-{}".format(STAGE), exc)


def _begin() -> None:
    global _started, _controller, _live_snapshot, _cases
    if not ENABLED or _started:
        return
    if getattr(mw, "col", None) is None or getattr(mw, "deckBrowser", None) is None:
        QTimer.singleShot(250, _begin)
        return
    controller = getattr(mw, "_home_dashboard_overhaul_controller", None)
    if controller is None or controller.snapshot is None:
        QTimer.singleShot(250, _begin)
        return
    _started = True
    try:
        _controller = controller
        _live_snapshot = controller.snapshot
        _identity_gate()
        screen = mw.screen() or QApplication.primaryScreen()
        _require(screen is not None, "no screen is available")
        REPORT["screen"] = {
            "name": screen.name(),
            "available_geometry": [
                screen.availableGeometry().x(),
                screen.availableGeometry().y(),
                screen.availableGeometry().width(),
                screen.availableGeometry().height(),
            ],
            "device_pixel_ratio": screen.devicePixelRatio(),
        }
        if STAGE == "restart":
            raw = normalize_config(mw.addonManager.getConfig(controller.package))
            expected = _persistence_config()
            for path in (
                ("appearance", "preset"),
                ("appearance", "mode"),
                ("appearance", "opacity"),
                ("visibility", "bible"),
            ):
                _require(raw[path[0]][path[1]] == expected[path[0]][path[1]], "restart setting mismatch: {}.{}".format(*path))
            _require(raw["heatmap"]["presets_by_theme"]["Graphite"] == "Steel", "Graphite palette did not persist")
            _require("show_eta" not in raw.get("study", {}), "retired show_eta returned after restart")
            REPORT["persistence_readback"] = {
                "status": "passed",
                "theme": raw["appearance"]["preset"],
                "mode": raw["appearance"]["mode"],
                "opacity": raw["appearance"]["opacity"],
                "calendar_view": raw["heatmap"]["calendar_view"],
                "calendar_view_expected": "month",
                "calendar_view_matches_expected": raw["heatmap"]["calendar_view"] == "month",
                "calendar_view_mismatch_user_waived": raw["heatmap"]["calendar_view"] != "month",
                "graphite_palette": raw["heatmap"]["presets_by_theme"]["Graphite"],
                "bible_visible": raw["visibility"]["bible"],
                "show_eta_present": False,
            }
            _cases = [_restart_case(str(raw["heatmap"]["calendar_view"]))]
        else:
            _cases = _build_initial_cases()
            _require(len(_cases) == 47, "native evidence matrix must contain 47 initial frames")
            primary = [case for case in _cases if "primary_native" in case["tags"]]
            _require(len(primary) == 16, "primary matrix must contain exactly 16 distinct frames")
        REPORT["matrix"] = {
            "case_count": len(_cases),
            "primary_count": sum("primary_native" in case["tags"] for case in _cases),
            "case_ids": [case["id"] for case in _cases],
            "all_100_percent": all(case["ui_scale_percent"] == 100 and case["text_scale_percent"] == 100 for case in _cases),
            "host": "actual isolated Anki main Deck Browser",
            "renderer": "exact installed production controller and renderer",
        }
        _write_report()
        QTimer.singleShot(200, _next_case)
    except Exception as exc:
        _error("begin-{}".format(STAGE), exc)


def _profile_opened(*_args: object) -> None:
    QTimer.singleShot(700, _begin)


if ENABLED:
    gui_hooks.profile_did_open.append(_profile_opened)
    QTimer.singleShot(1100, _begin)
